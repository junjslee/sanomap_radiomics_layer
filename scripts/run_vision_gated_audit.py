#!/usr/bin/env python3
"""Run the 3-gate + dual-verifier pipeline against current proposals AND
the 2 historical 'vision_verified' edges that already sit in the graph.

Pipeline order:
    caption_gate → colorbar_detect_gate → range_sanity_gate
        → (only if all 3 pass) pixel + Qwen consensus

Inputs:
    artifacts/vision_proposals_pipeline.jsonl       (current 13 proposals)
    artifacts/verification_results_gemini_vision.jsonl  (historical 2 edges)
    artifacts/figures_pmc.jsonl                     (caption lookup)
    artifacts/figures/                              (image files)

Outputs:
    artifacts/vision_gated_audit.jsonl              (full per-row trace)
    artifacts/vision_gated_summary.json             (aggregate counts)

The audit includes a ``provenance`` tag distinguishing current proposals
from historical graph edges, so downstream graph cleanup can act on the
audit's verdicts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.verify_vision_dual import (  # noqa: E402
    VisionVerifierConfig,
    dual_verify,
)
from src.vision_gates import (  # noqa: E402
    run_all_gates,
    extract_colorbar_range_via_vlm,
)

PROPOSALS = ROOT / "artifacts" / "vision_proposals_pipeline.jsonl"
HIST_VERIF = ROOT / "artifacts" / "verification_results_gemini_vision.jsonl"
HIST_PROPS = ROOT / "artifacts" / "vision_proposals_gemini_vision.jsonl"
CAPTIONS = ROOT / "artifacts" / "figures_pmc.jsonl"
FIGURES_DIR = ROOT / "artifacts" / "figures"
OUTPUT = ROOT / "artifacts" / "vision_gated_audit.jsonl"
SUMMARY = ROOT / "artifacts" / "vision_gated_summary.json"

OLLAMA_URL = "http://localhost:11434/v1"
MODEL_ID = "qwen2.5vl:3b"

# Historical edge → figure_id manual map.
# (verified_edges file uses hashed figure_ids; map them to PMC figure_ids
#  using the cross-reference logged in PROGRESS.md and figures_pmc.jsonl.)
HISTORICAL_FIGURE_MAP = {
    "89b1e3b5e8a4e447": "PMC10605408_g004",  # prevotella_nigrescens ↔ GLCM_Correlation
    # PMC6178902_g0006 keeps its own figure_id in the verified_edges file.
}


# --------------------------------------------------------------------------- #
#  Loaders
# --------------------------------------------------------------------------- #

def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _build_caption_index(figures_pmc: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rec in figures_pmc:
        fid = str(rec.get("figure_id") or "").strip()
        cap = str(rec.get("caption") or "").strip()
        if fid:
            out[fid] = cap
    return out


def _resolve_figure(figure_id: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = FIGURES_DIR / f"{figure_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def _map_proposal_to_verifier_schema(p: dict) -> dict:
    r_val = p.get("candidate_r") if p.get("candidate_r") is not None else p.get("proposed_r")
    return {
        **p,
        "subject": p.get("microbe") or p.get("subject_node") or "",
        "feature": p.get("radiomic_feature") or "",
        "value": r_val,
        "r_value": r_val,
        "topology": p.get("topology") or "heatmap",
    }


# --------------------------------------------------------------------------- #
#  Run a single proposal through the gate chain + (conditionally) dual verifier
# --------------------------------------------------------------------------- #

def _audit_one(
    raw: dict,
    *,
    provenance: str,
    captions: dict[str, str],
    vision_config: VisionVerifierConfig,
) -> dict | None:
    """Return one audit row, or None if the figure is not on disk."""
    figure_id = raw.get("figure_id") or ""
    figure_id = HISTORICAL_FIGURE_MAP.get(figure_id, figure_id)
    image_path = _resolve_figure(figure_id)
    if image_path is None:
        return None

    proposal = _map_proposal_to_verifier_schema(raw)
    caption = captions.get(figure_id, "")

    # Extract the figure's actual colorbar tick range so range_sanity_gate
    # uses the real bounds, not the default ±1.0. If extraction fails the
    # gate reverts to ±1.0.
    cmin, cmax, range_reason = extract_colorbar_range_via_vlm(
        image_path=str(image_path), config=vision_config
    )
    extracted_range = (cmin, cmax) if (cmin is not None and cmax is not None) else None
    cb_range = extracted_range or (-1.0, 1.0)

    gates = run_all_gates(
        image_path=str(image_path),
        proposal=proposal,
        caption=caption,
        colorbar_range=cb_range,
    )

    row = {
        "provenance": provenance,
        "figure_id": figure_id,
        "panel_id": raw.get("panel_id"),
        "subject": proposal["subject"],
        "feature": proposal["feature"],
        "candidate_r": proposal["value"],
        "topology_proposer": proposal["topology"],
        "image_path": str(image_path.relative_to(ROOT)),
        "caption_excerpt": caption[:200],
        "extracted_colorbar_range": list(extracted_range) if extracted_range else None,
        "extracted_colorbar_reason": range_reason,
        "gate_chain": gates.as_dict(),
    }

    if not gates.passed:
        row["dual_verify"] = None
        row["final_verdict"] = "REJECT_GATE"
        return row

    # Gates passed → run dual verifier.
    from src.verify_heatmap import verify_heatmap_r_value
    try:
        outcome = dual_verify(
            image_path=str(image_path),
            proposal=proposal,
            pixel_verifier=verify_heatmap_r_value,
            vision_config=vision_config,
        )
        row["dual_verify"] = outcome.as_dict()
        if outcome.accepted:
            row["final_verdict"] = "ACCEPT"
        elif outcome.needs_review:
            row["final_verdict"] = "REVIEW"
        else:
            row["final_verdict"] = "REJECT_DUAL"
    except Exception as exc:  # noqa: BLE001
        row["dual_verify"] = {"error": f"{type(exc).__name__}: {exc}"}
        row["final_verdict"] = "ERROR"
    return row


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #

def main() -> int:
    figures_pmc = _load_jsonl(CAPTIONS)
    captions = _build_caption_index(figures_pmc)
    print(f"Loaded {len(captions)} captions from figures_pmc.jsonl")

    current_props = _load_jsonl(PROPOSALS)
    historical = _load_jsonl(HIST_VERIF)
    historical_props = _load_jsonl(HIST_PROPS)
    historical_props_by_figid = {
        str(p.get("figure_id") or ""): p for p in historical_props
    }
    # For each historical verification, splice in the original proposal so we
    # have candidate_r / microbe / feature fields.
    enriched_historical: list[dict] = []
    seen_current_figs = {p.get("figure_id") for p in current_props}
    for v in historical:
        # Both fields appear in the wild — verification_results uses `verified`,
        # verified_edges uses `verification_passed`.
        if not (v.get("verified") or v.get("verification_passed")):
            continue
        fig_id = str(v.get("figure_id") or "")
        # Map hashed ids to PMC ids if known
        fig_id = HISTORICAL_FIGURE_MAP.get(fig_id, fig_id)
        # Avoid double-counting figures that already appear in current proposals
        if fig_id in seen_current_figs:
            continue
        prop = historical_props_by_figid.get(fig_id, {})
        merged = {
            **prop,
            **v,
            "figure_id": fig_id,
            "candidate_r": v.get("proposed_r", v.get("r_value", prop.get("candidate_r"))),
            "microbe": v.get("subject_node") or prop.get("microbe"),
            "radiomic_feature": v.get("object_node") or prop.get("radiomic_feature"),
        }
        enriched_historical.append(merged)
    print(f"Loaded {len(current_props)} current + {len(enriched_historical)} "
          f"historical (verified) edges")

    vision_config = VisionVerifierConfig(
        api_base_url=OLLAMA_URL,
        model_id=MODEL_ID,
        api_key=None,
        temperature=0.0,
        max_tokens=256,
        timeout_s=420.0,  # local Qwen 3B image inference can be slow on M2
    )

    rows: list[dict] = []
    skipped: list[str] = []
    for p in current_props:
        r = _audit_one(p, provenance="current_proposal",
                       captions=captions, vision_config=vision_config)
        if r is None:
            skipped.append(str(p.get("figure_id", "?")))
        else:
            rows.append(r)

    for v in enriched_historical:
        r = _audit_one(v, provenance="historical_graph_edge",
                       captions=captions, vision_config=vision_config)
        if r is None:
            skipped.append(str(v.get("figure_id", "?")))
        else:
            rows.append(r)

    OUTPUT.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))

    # Aggregate
    from collections import Counter
    verdict_counter = Counter(r["final_verdict"] for r in rows)
    failing_gate_counter = Counter(
        r["gate_chain"]["failing_gate"] for r in rows
        if not r["gate_chain"]["all_passed"]
    )
    by_provenance = Counter((r["provenance"], r["final_verdict"]) for r in rows)
    summary = {
        "total_audited": len(rows),
        "skipped_no_image": skipped,
        "verdict_counts": dict(verdict_counter),
        "failing_gate_counts": dict(failing_gate_counter),
        "by_provenance": {f"{prov}|{verd}": n for (prov, verd), n in by_provenance.items()},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2))

    print(f"\nWrote {len(rows)} audit rows → {OUTPUT.relative_to(ROOT)}")
    print(f"Summary → {SUMMARY.relative_to(ROOT)}")
    print(json.dumps(summary, indent=2))

    # Per-row terse trace
    print("\nPer-row verdicts:")
    for r in rows:
        gc = r["gate_chain"]
        gate_tag = "ALL_GATES_PASS" if gc["all_passed"] else f"FAIL@{gc['failing_gate']}"
        print(f"  {r['provenance']:25s} {r['figure_id']:32s} {gate_tag:25s} → {r['final_verdict']}")
    if skipped:
        print(f"\nSkipped (no local image): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
