#!/usr/bin/env python3
"""Vision Track pipeline orchestrator.

Chains all Vision Track stages in sequence:
  fetch PMC figures → classify topology → (cost estimate gate) → VLM propose → verify → summary

COMPUTE NOTE: Qwen2.5-VL-7B-Instruct requires ~14 GB in FP16 and cannot run on 8 GB M2.
Use --backend qwen_api with GEMINI_API_KEY set (default) for remote Gemini inference.

Usage:
    # Dry-run: show qualifying figures and cost estimate, skip API calls:
    conda run -n base python scripts/run_vision_pipeline.py --dry-run

    # Full run on the merged fulltext corpus (77 PMCIDs):
    conda run -n base python scripts/run_vision_pipeline.py

    # Skip slow PMC fetch (use existing figures_pmc.jsonl):
    conda run -n base python scripts/run_vision_pipeline.py --skip-fetch

    # Run on strict radiomics lane only (8 papers, highest heatmap yield):
    conda run -n base python scripts/run_vision_pipeline.py \\
        --papers artifacts/papers_microbe_radiomics_strict_fulltext.jsonl

    # Run with looser verification tolerance for exploration:
    conda run -n base python scripts/run_vision_pipeline.py --tolerance 0.12

    # Specific PMCIDs only (no papers file needed):
    conda run -n base python scripts/run_vision_pipeline.py \\
        --pmcids PMC10176953,PMC10605408 --skip-fetch
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

# Allow running as a script from any CWD
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in [str(_PROJECT_ROOT), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fetch_pmc_figures import process_pmcid  # noqa: E402
from src.artifact_utils import read_jsonl, write_jsonl  # noqa: E402
from src.index_figures import classify_figure  # noqa: E402
from src.propose_vision_qwen import ProposerOptions, run_proposer  # noqa: E402
from src.verify_heatmap import _build_figure_lookup, verify_proposals  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PAPERS = "artifacts/papers_microbe_merged_fulltext.jsonl"
DEFAULT_FIGURES_PMC = "artifacts/figures_pmc.jsonl"
DEFAULT_SAMPLE_DIR = "sample_papers"
DEFAULT_PROPOSALS_OUT = "artifacts/vision_proposals_pipeline.jsonl"
DEFAULT_VERIFICATION_OUT = "artifacts/verification_results_pipeline.jsonl"

_QUALIFYING_TOPOLOGIES = {"heatmap", "forest_plot", "scatter_plot", "dot_plot"}

# Caption keyword pre-filter: any caption hinting at a qualifying figure type.
_QUALIFYING_CAPTION_KEYWORDS = {
    # heatmap / correlation matrix
    "heatmap", "heat map", "correlation matrix", "cluster map", "clustermap",
    "spearman", "pearson", "colormap", "color map",
    # forest plot / meta-analysis
    "forest plot", "hazard ratio", "odds ratio", "confidence interval", "meta-analysis",
    # scatter plot
    "scatter", "correlation scatter",
    # dot / bubble plot
    "dot plot", "lollipop", "bubble plot",
}


def _caption_suggests_qualifying(caption: str) -> bool:
    lower = caption.lower()
    return any(kw in lower for kw in _QUALIFYING_CAPTION_KEYWORDS)


# Gemini 2.5 Flash-Lite: images ≤1MP = 258 tokens; text prompt ≈ 250 tokens.
_TOKENS_PER_CALL = 258 + 250
_COST_PER_M_INPUT_TOKENS_USD = 0.075  # Gemini Flash-Lite input rate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cost_estimate_usd(n_figures: int) -> float:
    return n_figures * _TOKENS_PER_CALL * _COST_PER_M_INPUT_TOKENS_USD / 1_000_000


def _load_processed_figure_ids(proposals_path: str) -> set[str]:
    """Return figure_ids already present in an existing proposals file."""
    p = Path(proposals_path)
    if not p.exists():
        return set()
    seen: set[str] = set()
    for row in read_jsonl(p):
        fid = str(row.get("figure_id") or "")
        if fid:
            seen.add(fid)
    return seen


def _fetch_figures(
    *,
    papers: list[dict[str, Any]],
    pmcids_override: list[str],
    sample_dir: str,
    figures_pmc_path: str,
    fetch_limit: int,
    skip_existing: bool,
) -> list[dict[str, Any]]:
    """Fetch figure images + captions from PMC for each PMCID."""
    if pmcids_override:
        targets: list[tuple[str, str]] = [(pmcid, "") for pmcid in pmcids_override]
    else:
        seen: set[str] = set()
        targets = []
        for p in papers:
            pmcid = (p.get("pmcid") or "").strip()
            pmid = str(p.get("pmid") or "")
            if pmcid and pmcid not in seen:
                seen.add(pmcid)
                targets.append((pmcid, pmid))

    if fetch_limit > 0:
        targets = targets[:fetch_limit]

    # Skip PMCIDs already in the figures output
    existing_figures: list[dict[str, Any]] = []
    if Path(figures_pmc_path).exists():
        existing_figures = read_jsonl(Path(figures_pmc_path))

    if skip_existing:
        already_fetched = {str(f.get("pmcid") or "") for f in existing_figures}
        targets = [(pmcid, pmid) for pmcid, pmid in targets if pmcid not in already_fetched]

    if not targets:
        print(f"  All PMCIDs already fetched. Using {len(existing_figures)} existing figures.")
        return existing_figures

    print(f"  Fetching {len(targets)} PMCIDs...")
    new_figures: list[dict[str, Any]] = []
    for i, (pmcid, pmid) in enumerate(targets):
        print(f"  [{i+1}/{len(targets)}] {pmcid}")
        figs = process_pmcid(pmcid, pmid, sample_dir)
        new_figures.extend(figs)
        time.sleep(0.8)

    all_figures = existing_figures + new_figures
    write_jsonl(figures_pmc_path, all_figures)
    print(f"  Figures after fetch: {len(all_figures)} total ({len(new_figures)} new)")
    return all_figures


def _classify_and_filter(
    figures: list[dict[str, Any]],
    min_confidence: float,
    require_caption_keyword: bool,
) -> list[dict[str, Any]]:
    """Enrich figures with topology classification and return qualifying figures."""
    enriched: list[dict[str, Any]] = []
    for fig in figures:
        caption = str(fig.get("caption") or "")
        image_path = fig.get("image_path")

        # Quick caption pre-filter to skip obviously non-qualifying figures
        if require_caption_keyword and not _caption_suggests_qualifying(caption):
            continue

        topology, confidence, hits = classify_figure(
            caption, Path(image_path) if image_path else None
        )
        enriched_fig = dict(fig)
        enriched_fig["topology"] = topology
        enriched_fig["topology_confidence"] = confidence
        enriched_fig["heuristic_hits"] = hits
        enriched.append(enriched_fig)

    qualifying = [
        f for f in enriched
        if f["topology"] in _QUALIFYING_TOPOLOGIES and f["topology_confidence"] >= min_confidence
    ]
    return qualifying


def _run_proposals(
    qualifying: list[dict[str, Any]],
    options: ProposerOptions,
    skip_figure_ids: set[str],
) -> list[dict[str, Any]]:
    """Run VLM proposals, skipping already-processed figures."""
    to_process = [f for f in qualifying if f.get("figure_id") not in skip_figure_ids]
    skipped = len(qualifying) - len(to_process)
    if skipped:
        print(f"  Skipping {skipped} already-processed figures.")

    proposals = run_proposer(
        figures=to_process,
        options=options,
        min_topology_confidence=0.0,  # Already filtered upstream
        include_non_heatmap=True,
    )

    for p in proposals:
        fid = str(p.get("figure_id") or "")[:12]
        status = p.get("status", "?")
        cand_r = p.get("candidate_r")
        microbe = p.get("microbe") or "-"
        feature = p.get("radiomic_feature") or "-"
        r_str = f"{cand_r:.3f}" if cand_r is not None else "null"
        print(f"  {fid}  status={status}  r={r_str}  [{microbe}] → [{feature}]")

    return proposals


def _run_verification(
    proposals: list[dict[str, Any]],
    all_figures: list[dict[str, Any]],
    tolerance: float,
    min_support_pixels: int,
    min_support_fraction: float,
) -> list[dict[str, Any]]:
    figure_lookup = _build_figure_lookup(all_figures)
    ok_proposals = [p for p in proposals if p.get("status") == "ok" and p.get("candidate_r") is not None]
    if not ok_proposals:
        print("  No proposals with status=ok to verify.")
        return []
    return verify_proposals(
        proposals=ok_proposals,
        figure_lookup=figure_lookup,
        tolerance=tolerance,
        r_min=-1.0,
        r_max=1.0,
        min_support_pixels=min_support_pixels,
        min_support_fraction=min_support_fraction,
    )


def _print_summary(
    *,
    qualifying_count: int,
    new_proposals: list[dict[str, Any]],
    new_results: list[dict[str, Any]],
    proposals_out: str,
    verification_out: str,
    tolerance: float,
) -> None:
    ok = sum(1 for p in new_proposals if p.get("status") == "ok")
    err = sum(1 for p in new_proposals if p.get("status") == "model_error")
    missing = sum(1 for p in new_proposals if p.get("status") == "missing_image")
    verified = sum(1 for r in new_results if r.get("verified"))
    rejected = sum(1 for r in new_results if not r.get("verified"))

    print("\n" + "=" * 62)
    print("VISION TRACK PIPELINE — RUN SUMMARY")
    print("=" * 62)
    print(f"  Qualifying figures:          {qualifying_count}")
    print(f"  Proposals this run:")
    print(f"    ok:              {ok}")
    print(f"    model_error:     {err}")
    print(f"    missing_image:   {missing}")
    print(f"  Verification (tolerance={tolerance}):")
    print(f"    verified:        {verified}")
    print(f"    rejected:        {rejected}")

    if verified:
        print("\n  VERIFIED CORRELATES_WITH EDGES:")
        for r in new_results:
            if r.get("verified"):
                pid = str(r.get("proposal_id") or "?")[:12]
                nr = r.get("nearest_r")
                sf = r.get("support_fraction", 0.0)
                fid = str(r.get("figure_id") or "?")[:12]
                nr_str = f"{nr:.3f}" if nr is not None else "?"
                print(f"    figure={fid}  proposal={pid}  nearest_r={nr_str}  support={sf:.4f}")

    if rejected and not verified:
        print("\n  TIP: All proposals failed verification. If figures are real heatmaps,")
        print("  try --tolerance 0.12 or --min-support-fraction 0.0001 for exploration.")

    print(f"\n  Proposals written to:     {proposals_out}")
    print(f"  Verifications written to: {verification_out}")
    print("=" * 62)
    print(
        "\nNext step: if verified > 0, run assemble_edges.py with "
        f"--vision-proposals {proposals_out} "
        f"--vision-verification {verification_out}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Vision Track pipeline: fetch PMC figures → classify → propose (VLM) → verify.\n\n"
            "Compute note: Qwen2.5-VL-7B needs ~14 GB and cannot run on 8 GB M2. "
            "Set GEMINI_API_KEY and use --backend qwen_api (default)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input
    parser.add_argument(
        "--papers",
        default=DEFAULT_PAPERS,
        help=f"Papers JSONL with PMCID field (default: {DEFAULT_PAPERS}).",
    )
    parser.add_argument(
        "--pmcids",
        default="",
        help="Comma-separated PMCIDs to process, bypassing --papers.",
    )

    # Fetch
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip PMC fetch step and use existing --figures-pmc file.",
    )
    parser.add_argument(
        "--figures-pmc",
        default=DEFAULT_FIGURES_PMC,
        help=f"Path for fetched figures JSONL (default: {DEFAULT_FIGURES_PMC}).",
    )
    parser.add_argument(
        "--sample-dir",
        default=DEFAULT_SAMPLE_DIR,
        help=f"Directory for downloaded figure images (default: {DEFAULT_SAMPLE_DIR}).",
    )
    parser.add_argument(
        "--fetch-limit",
        type=int,
        default=0,
        help="Max PMCIDs to fetch (0 = all).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip figures already in the proposals output (default: True).",
    )

    # Classification filter
    parser.add_argument(
        "--min-topology-confidence",
        type=float,
        default=0.2,
        help="Minimum topology confidence to qualify a figure (default: 0.2).",
    )
    parser.add_argument(
        "--no-caption-filter",
        action="store_true",
        help="Disable caption keyword pre-filter (process all figures regardless of caption).",
    )

    # VLM backend
    parser.add_argument(
        "--backend",
        choices=["auto", "qwen_local", "qwen_api"],
        default="qwen_api",
        help="VLM backend. Use qwen_api with GEMINI_API_KEY for Gemini (default).",
    )
    parser.add_argument(
        "--model-id",
        default=os.environ.get("VISION_MODEL_ID") or "gemini-2.5-flash-lite",
        help="Model ID for the VLM (default: gemini-2.5-flash-lite).",
    )
    parser.add_argument(
        "--api-base-url",
        default=(
            os.environ.get("GEMINI_API_BASE_URL")
            or os.environ.get("QWEN_API_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://generativelanguage.googleapis.com/v1beta/openai"
        ),
        help="API base URL for VLM (default: Gemini OpenAI-compatible endpoint).",
    )
    parser.add_argument(
        "--api-key",
        default=(
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("QWEN_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ),
        help="API key (reads GEMINI_API_KEY by default).",
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=300)

    # Verification
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.08,
        help="Verification tolerance |proposed_r - observed_r| (default: 0.08; try 0.12 for exploration).",
    )
    parser.add_argument(
        "--min-support-pixels",
        type=int,
        default=20,
        help="Minimum pixel support count for verification pass (default: 20).",
    )
    parser.add_argument(
        "--min-support-fraction",
        type=float,
        default=0.001,
        help="Minimum support fraction for verification pass (default: 0.001).",
    )

    # Output
    parser.add_argument("--proposals-out", default=DEFAULT_PROPOSALS_OUT)
    parser.add_argument("--verification-out", default=DEFAULT_VERIFICATION_OUT)

    # Mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show qualifying figures and cost estimate; skip VLM and verification.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    pmcids_override = [p.strip() for p in args.pmcids.split(",") if p.strip()]

    # -----------------------------------------------------------------------
    # Step 1: Fetch / load figures
    # -----------------------------------------------------------------------
    print("[1/4] Figure acquisition")
    if args.skip_fetch and not pmcids_override:
        figs_path = Path(args.figures_pmc)
        if not figs_path.exists():
            print(f"ERROR: --skip-fetch set but {args.figures_pmc} not found. Run without --skip-fetch first.")
            return 1
        raw_figures = read_jsonl(figs_path)
        print(f"  Loaded {len(raw_figures)} figures from {args.figures_pmc} (fetch skipped)")
    else:
        papers: list[dict[str, Any]] = []
        if not pmcids_override:
            papers_path = Path(args.papers)
            if not papers_path.exists():
                print(f"ERROR: Papers file not found: {args.papers}")
                return 1
            papers = read_jsonl(papers_path)
            print(f"  Source: {args.papers} ({len(papers)} papers)")

        raw_figures = _fetch_figures(
            papers=papers,
            pmcids_override=pmcids_override,
            sample_dir=args.sample_dir,
            figures_pmc_path=args.figures_pmc,
            fetch_limit=args.fetch_limit,
            skip_existing=args.skip_existing,
        )

    # -----------------------------------------------------------------------
    # Step 2: Classify topology and filter
    # -----------------------------------------------------------------------
    require_caption_kw = not args.no_caption_filter
    print(f"\n[2/4] Topology classification ({len(raw_figures)} figures, caption_filter={require_caption_kw})")
    qualifying = _classify_and_filter(raw_figures, args.min_topology_confidence, require_caption_kw)
    print(f"  Qualifying (heatmap/forest_plot/scatter/dot, confidence >= {args.min_topology_confidence}): {len(qualifying)}")

    for fig in qualifying:
        fid = str(fig.get("figure_id") or "?")[:12]
        pmcid = fig.get("pmcid") or fig.get("pmid") or "?"
        conf = fig.get("topology_confidence", 0.0)
        cap = (fig.get("caption") or "")[:70]
        print(f"  {fid}  pmcid={pmcid}  conf={conf:.2f}  {cap!r}")

    if not qualifying:
        print("  No qualifying figures found.")
        print("  Tips: lower --min-topology-confidence, or use --no-caption-filter to include all figure types.")
        return 0

    # Cost estimate and confirmation gate
    est_cost = _cost_estimate_usd(len(qualifying))
    print(f"\n  Estimated API cost: ${est_cost:.4f} USD ({len(qualifying)} figures × {_TOKENS_PER_CALL} tokens)")

    if args.dry_run:
        print("\n[DRY RUN] Stopping before VLM. Remove --dry-run to proceed.")
        return 0

    if not args.api_key and args.backend in {"qwen_api", "auto"}:
        print("\nWARNING: No API key found. Set GEMINI_API_KEY (or OPENAI_API_KEY) before running.")
        print("  export GEMINI_API_KEY=your-key-here")
        return 1

    # -----------------------------------------------------------------------
    # Step 3: VLM proposals
    # -----------------------------------------------------------------------
    print(f"\n[3/4] VLM proposals ({args.backend} / {args.model_id})")
    options = ProposerOptions(
        backend=args.backend,
        model_id=args.model_id,
        prompt_id="qwen_heatmap_v2_json",
        api_base_url=args.api_base_url or None,
        api_key=args.api_key or None,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    skip_ids = _load_processed_figure_ids(args.proposals_out) if args.skip_existing else set()
    new_proposals = _run_proposals(qualifying, options, skip_ids)

    # Merge new proposals with any existing output
    existing_proposals: list[dict[str, Any]] = []
    if Path(args.proposals_out).exists() and args.skip_existing:
        existing_proposals = read_jsonl(Path(args.proposals_out))
    all_proposals = existing_proposals + new_proposals
    write_jsonl(args.proposals_out, all_proposals)
    print(f"  Proposals total in {args.proposals_out}: {len(all_proposals)}")

    # -----------------------------------------------------------------------
    # Step 4: Verification
    # -----------------------------------------------------------------------
    print(f"\n[4/4] Verification (tolerance={args.tolerance})")
    new_results = _run_verification(
        proposals=new_proposals,
        all_figures=raw_figures,
        tolerance=args.tolerance,
        min_support_pixels=args.min_support_pixels,
        min_support_fraction=args.min_support_fraction,
    )

    existing_verifications: list[dict[str, Any]] = []
    if Path(args.verification_out).exists() and args.skip_existing:
        existing_verifications = read_jsonl(Path(args.verification_out))
    all_results = existing_verifications + new_results
    write_jsonl(args.verification_out, all_results)

    # Summary
    _print_summary(
        qualifying_count=len(qualifying),
        new_proposals=new_proposals,
        new_results=new_results,
        proposals_out=args.proposals_out,
        verification_out=args.verification_out,
        tolerance=args.tolerance,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
