#!/usr/bin/env python3
"""Drop vision-track edges that fail the gated audit from graph artifacts.

Per the 2026-05-07 retroactive audit (`artifacts/vision_gated_audit.jsonl`)
and direct image inspection:

  KEEP:  PMC10605408_g004 — prevotella_nigrescens ↔ GLCM_Correlation, r=0.95.
         Real Spearman correlation heatmap with -1 to +1 colorbar.
         Session-4 pixel verifier had distance 0.05, support 1.0.
         Today's REVIEW is from a pixel-inconclusive flicker, not a refutation.

  DROP:  PMC6178902_g0006 — firmicutes ↔ Total fat %, r=-0.95.
         Direct image inspection: firmicutes × total_fat_% cell is deep RED
         (positive, magnitude near +1.0), not blue. Proposer's r=-0.95 has
         wrong sign. Colorbar is -1.5 to +1.5 (LFC scale, not Pearson r).
         Pixel verifier originally passed on proposer's hallucinated bbox
         (consistency check on a self-consistent fabrication, not grounding).

This script removes the firmicutes edge from each verified_edges*.jsonl /
verified_edges*.csv / neo4j_relationships*.csv that contains it. Original
files are backed up alongside as ``<file>.pre_vision_audit_2026_05_07.bak``
so the cleanup is reversible.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

# Drop policy: by figure_id (firmicutes edge is the only one removed).
DROP_FIGURE_IDS: set[str] = {"PMC6178902_g0006"}
DROP_REASON = (
    "vision_audit_2026-05-07: wrong-sign + LFC-scale per manual image "
    "inspection; pixel verifier passed on proposer's hallucinated bbox "
    "(consistency, not grounding)"
)
BACKUP_SUFFIX = ".pre_vision_audit_2026_05_07.bak"


def _backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not bak.exists():
        shutil.copy2(path, bak)


def _clean_jsonl(path: Path) -> tuple[int, int]:
    """Return (kept, dropped) row counts."""
    if not path.exists():
        return (0, 0)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    kept: list[dict] = []
    dropped = 0
    for r in rows:
        fig_id = str(r.get("figure_id") or "")
        if fig_id in DROP_FIGURE_IDS and (r.get("evidence_type") == "vision_verified"
                                           or r.get("relation_type") == "VISION_CORRELATION"):
            dropped += 1
            continue
        kept.append(r)
    if dropped > 0:
        _backup(path)
        path.write_text("\n".join(json.dumps(r) for r in kept) + ("\n" if kept else ""))
    return (len(kept), dropped)


def _clean_csv(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    kept: list[dict[str, str]] = []
    dropped = 0
    for r in rows:
        fig_id = str(r.get("figure_id") or "")
        ev = str(r.get("evidence_type") or "").lower()
        rel = str(r.get("relation_type") or "").lower()
        if fig_id in DROP_FIGURE_IDS and ("vision_verified" in ev or "vision_correlation" in rel):
            dropped += 1
            continue
        kept.append(r)
    if dropped > 0:
        _backup(path)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)
    return (len(kept), dropped)


def main() -> int:
    targets_jsonl = sorted(ARTIFACTS.glob("verified_edges*.jsonl"))
    targets_csv = sorted(
        list(ARTIFACTS.glob("verified_edges*.csv"))
        + list(ARTIFACTS.glob("neo4j_relationships*.csv"))
    )

    total_dropped = 0
    print(f"Drop policy: figure_ids={sorted(DROP_FIGURE_IDS)} (vision_verified rows only)")
    print(f"Reason: {DROP_REASON}\n")

    print("--- JSONL artifacts ---")
    for p in targets_jsonl:
        kept, dropped = _clean_jsonl(p)
        flag = " (BACKUP MADE)" if dropped > 0 else ""
        print(f"  {p.relative_to(ROOT)}: kept={kept}, dropped={dropped}{flag}")
        total_dropped += dropped

    print("\n--- CSV artifacts ---")
    for p in targets_csv:
        kept, dropped = _clean_csv(p)
        flag = " (BACKUP MADE)" if dropped > 0 else ""
        print(f"  {p.relative_to(ROOT)}: kept={kept}, dropped={dropped}{flag}")
        total_dropped += dropped

    print(f"\nTotal rows dropped: {total_dropped}")
    print(f"Backups have suffix '{BACKUP_SUFFIX}' if rollback needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
