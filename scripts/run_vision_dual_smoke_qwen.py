#!/usr/bin/env python3
"""Vision verifier smoke test (Task 3 closure) — local Qwen2.5-VL-3B via Ollama.

Reads ``artifacts/vision_proposals_pipeline.jsonl``, resolves each
proposal's figure from ``artifacts/figures/{figure_id}.jpg`` (the
``image_path`` in the proposals points at a stale Desktop location),
maps proposal fields to the dual-verifier's expected schema, and runs
the dual gate with:
  - Verifier A: pixel HSV (``src.verify_heatmap.verify_heatmap_r_value``)
  - Verifier B: local Ollama Qwen2.5-VL-3B at ``localhost:11434/v1``

Outputs:
  - artifacts/vision_dual_verification.jsonl  (full per-proposal rows)
  - artifacts/vision_review_queue.jsonl       (XOR-disagreement subset)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.verify_vision_dual import (
    VisionVerifierConfig,
    dual_verify,
)


PROPOSALS = ROOT / "artifacts" / "vision_proposals_pipeline.jsonl"
FIGURES_DIR = ROOT / "artifacts" / "figures"
OUTPUT = ROOT / "artifacts" / "vision_dual_verification.jsonl"
REVIEW_QUEUE = ROOT / "artifacts" / "vision_review_queue.jsonl"

OLLAMA_URL = "http://localhost:11434/v1"
MODEL_ID = "qwen2.5vl:3b"


def _map_proposal_to_verifier_schema(p: dict) -> dict:
    """Map vision_proposals_pipeline fields → dual_verify expected fields."""
    r_val = p.get("candidate_r") if p.get("candidate_r") is not None else p.get("proposed_r")
    return {
        **p,
        "subject": p.get("microbe") or p.get("subject_node") or "",
        "feature": p.get("radiomic_feature") or "",
        "value": r_val,
        "r_value": r_val,
        "topology": p.get("topology") or "heatmap",
    }


def _resolve_figure(figure_id: str) -> Path | None:
    """Look up local figure file from artifacts/figures/."""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = FIGURES_DIR / f"{figure_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    if not PROPOSALS.exists():
        print(f"ERROR: proposals not found: {PROPOSALS}", file=sys.stderr)
        return 1
    if not FIGURES_DIR.exists():
        print(f"ERROR: figures dir not found: {FIGURES_DIR}", file=sys.stderr)
        return 1

    from src.verify_heatmap import verify_heatmap_r_value

    config = VisionVerifierConfig(
        api_base_url=OLLAMA_URL,
        model_id=MODEL_ID,
        api_key=None,             # Ollama doesn't require a key
        temperature=0.0,
        max_tokens=256,
        timeout_s=180.0,          # local inference can be slower than hosted
    )

    proposals = [
        json.loads(line) for line in PROPOSALS.read_text().splitlines() if line.strip()
    ]
    print(f"Loaded {len(proposals)} proposals from {PROPOSALS.name}")

    rows: list[dict] = []
    review_rows: list[dict] = []
    skipped: list[str] = []

    for raw in proposals:
        figure_id = raw.get("figure_id") or ""
        image_path = _resolve_figure(figure_id)
        if image_path is None:
            print(f"  SKIP {figure_id}: no local image", file=sys.stderr)
            skipped.append(figure_id)
            continue

        proposal = _map_proposal_to_verifier_schema(raw)
        try:
            outcome = dual_verify(
                image_path=str(image_path),
                proposal=proposal,
                pixel_verifier=verify_heatmap_r_value,
                vision_config=config,
            )
        except Exception as exc:  # noqa: BLE001 — log shape, do not crash
            print(f"  ERROR {figure_id}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            continue

        row = {
            "proposal_id": raw.get("proposal_id"),
            "figure_id": figure_id,
            "panel_id": raw.get("panel_id"),
            "subject": proposal["subject"],
            "feature": proposal["feature"],
            "value": proposal["value"],
            "topology": proposal["topology"],
            "image_path": str(image_path.relative_to(ROOT)),
            **outcome.as_dict(),
        }
        rows.append(row)
        if outcome.needs_review:
            review_rows.append(row)

        verdict = (
            "ACCEPT" if outcome.accepted
            else ("REVIEW" if outcome.needs_review else "REJECT")
        )
        print(f"  {verdict}  {figure_id}/{raw.get('panel_id')}  "
              f"pixel={outcome.pixel.value}  vision={outcome.vision.value}")

    OUTPUT.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    print(f"\nWrote {len(rows)} dual-verification rows → {OUTPUT.relative_to(ROOT)}")
    if review_rows:
        REVIEW_QUEUE.write_text("\n".join(json.dumps(r) for r in review_rows) + "\n")
        print(f"Review queue: {len(review_rows)} → {REVIEW_QUEUE.relative_to(ROOT)}")
    if skipped:
        print(f"Skipped {len(skipped)} proposals (no local image): {skipped}")

    # Brief summary
    accepted = sum(1 for r in rows if r["accepted"])
    review = sum(1 for r in rows if r["needs_review"])
    rejected = len(rows) - accepted - review
    print(f"\nSummary: {accepted} accept, {review} review, {rejected} reject (n={len(rows)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
