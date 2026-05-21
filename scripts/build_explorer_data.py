#!/usr/bin/env python3
"""Stage B.a — emit the explorer-ready JSONL from the canonical graph export.

Reads:
    artifacts/graph_export/relationships.csv   (Stage A canonical bundle)
    artifacts/graph_export/manifest.json       (post-audit counts + provenance)

Writes:
    docs/explorer/data.jsonl                   (record-per-edge, post-audit truth)

This is the rewire piece of Stage B (item a per `docs/PLAN.md` Status
(2026-05-21)): point `docs/explorer/index.html` off the frozen 2026-04-05
JSONL onto the canonical export. Schema mirrors the prior data.jsonl
record shape so the explorer JS needs no UI changes — the swap is purely
in the data layer.

Graph-eligible only: bridge hypotheses and other AUDIT_ONLY records do NOT
appear here (Stage A discipline — direct-evidence-only policy in CLAUDE.md
Critical Guardrails). To browse audit-only artifacts, use the file-picker
in the Explorer Table View.

Invariant: emitted row count MUST equal manifest.json `counts.post_total`.
If those disagree, refuse to write — the canonical export is the source of
truth and a count mismatch means an input drifted.

Run:
    conda run -n base python scripts/build_explorer_data.py
    conda run -n base python scripts/build_explorer_data.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH_EXPORT = REPO_ROOT / "artifacts" / "graph_export"
DEFAULT_ARTIFACTS = REPO_ROOT / "artifacts"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "explorer" / "data.jsonl"

# Artifacts that may carry vision proposal_id → (figure_id, image_path) mappings.
# Order matters: earlier files take precedence. Current pipeline first; Session-4
# fallback for the surviving historical edge whose proposal_id predates the
# unified pipeline.
VISION_PROPOSAL_SOURCES = [
    "vision_proposals_pipeline.jsonl",
    "vision_proposals_gemini_vision.jsonl",
]

# Audit log carries the PMC-prefixed figure_id (e.g. "PMC10605408_g004") for
# historical_graph_edge rows where the original proposal recorded only a hash.
# Also carries candidate_r (the verified Pearson/Spearman value) and image_path
# for the post-fetch figure cache. We index audit rows by their PMCID prefix
# so we can join CORRELATES_WITH explorer rows (which now carry PMCID via the
# proposal-chain backfill above) to their PMC-form figure_id + r_value.
VISION_AUDIT_SOURCES = ["vision_gated_audit.jsonl"]

# Retained vision-edge verdicts (REJECT_GATE rows are dropped by the audit and
# should not be matched into the explorer record).
RETAINED_VISION_VERDICTS = {"ACCEPT", "REVIEW", None}  # None = legacy rows w/o verdict

# Paper corpora for PMCID ↔ PMID + title/journal enrichment.
PAPER_CORPUS_SOURCES = [
    "papers_microbe_merged_fulltext.jsonl",
    "papers_microbe_merged.jsonl",
    "papers_new_lanes_fulltext.jsonl",
    "papers_new_lanes_merged.jsonl",
    "papers_microbe_radiomics_strict_fulltext.jsonl",
]

# Regex for extracting identifiers from filenames and figure_id strings.
_PMID_PREFIX_RE = re.compile(r"^(\d{6,9})_")          # filename like "37894458_correlation_..."
_PMCID_PREFIX_RE = re.compile(r"^(PMC\d+)")           # filename or figure_id like "PMC10605408_g004"
_PROPOSAL_RE = re.compile(r"Vision proposal ([0-9a-fA-F]{16})")

# rel_type → explorer-display semantic relation_type. Mirrors the prior
# data.jsonl conventions so the UI's filters/legends keep working.
REL_TO_RELATION_TYPE: dict[str, str] = {
    "ASSOCIATED_WITH": "TEXT_ASSOCIATION",
    "CORRELATES_WITH": "VISION_OR_TEXT_CORRELATION",
    "POSITIVELY_CORRELATED_WITH": "MICROBE_DISEASE_POS",
    "NEGATIVELY_CORRELATED_WITH": "MICROBE_DISEASE_NEG",
    "MEASURED_AT": "BACKBONE_LOCATION",
    "ACQUIRED_VIA": "BACKBONE_MODALITY",
    "REPRESENTED_BY": "BACKBONE_IMAGE",
}

REL_TO_EVIDENCE_TYPE: dict[str, str] = {
    "ASSOCIATED_WITH": "text_rule_verified",
    "CORRELATES_WITH": "quantitatively_verified",
    "POSITIVELY_CORRELATED_WITH": "text_signed_co_mention",
    "NEGATIVELY_CORRELATED_WITH": "text_signed_co_mention",
    "MEASURED_AT": "schema_backbone",
    "ACQUIRED_VIA": "schema_backbone",
    "REPRESENTED_BY": "schema_backbone",
}

FEATURE_NODE_TYPES = {"RadiomicFeature", "BodyCompositionFeature"}


def edge_id(subject: str, obj: str, rel: str) -> str:
    """Deterministic 16-hex hash so re-runs produce stable edge_ids."""
    key = f"{subject}|{rel}|{obj}".encode()
    return hashlib.sha1(key).hexdigest()[:16]


def feature_family(node_type: str) -> str | None:
    if node_type == "BodyCompositionFeature":
        return "body_composition"
    if node_type == "RadiomicFeature":
        return "radiomic"
    return None


def safe_float(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def safe_int(v: str | None) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def safe_bool(v: str | None) -> bool | None:
    if v is None or v == "":
        return None
    return v.strip().lower() in {"true", "1", "yes"}


def row_to_record(row: dict[str, str]) -> dict[str, Any]:
    subj_type = row["source_node_type"]
    subj = row["source_node"]
    obj_type = row["target_node_type"]
    obj = row["target_node"]
    rel = row["rel_type"]

    is_feature_subj = subj_type in FEATURE_NODE_TYPES
    is_feature_obj = obj_type in FEATURE_NODE_TYPES

    return {
        "edge_id": edge_id(subj, obj, rel),
        "pmid": row.get("pmid") or None,
        "pmcid": row.get("pmcid") or None,
        "subject_node_type": subj_type,
        "subject_node": subj,
        "object_node_type": obj_type,
        "object_node": obj,
        "graph_rel_type": rel,
        "relation_type": REL_TO_RELATION_TYPE.get(rel, rel),
        "evidence_type": REL_TO_EVIDENCE_TYPE.get(rel, "unspecified"),
        "evidence": row.get("evidence") or None,
        "confidence": safe_float(row.get("confidence")),
        "verification_passed": safe_bool(row.get("verification_passed")),
        "microbe": subj if subj_type == "Microbe" else None,
        "disease": (
            obj if obj_type == "Disease"
            else (subj if subj_type == "Disease" else None)
        ),
        "radiomic_feature": (
            subj if is_feature_subj
            else (obj if is_feature_obj else None)
        ),
        "feature_family": (
            feature_family(subj_type) if is_feature_subj
            else feature_family(obj_type)
        ),
        "microbe_cui": row.get("microbe_cui") or None,
        "microbe_official_name": row.get("microbe_official_name") or None,
        "disease_cui": row.get("disease_cui") or None,
        "disease_official_name": row.get("disease_official_name") or None,
        "journal": row.get("journal") or None,
        "title": row.get("title") or None,
        "publication_year": safe_int(row.get("publication_year")),
        "issn": row.get("issn") or None,
        # r_value + figure_id are reserved for Stage B v2 evidence enrichment.
        # The canonical relationships.csv does not carry them today; the
        # surviving vision edge's evidence text in relationships.csv already
        # references the vision proposal id, which is enough for v1.
        "r_value": None,
        "figure_id": None,
        "claim_hint": None,
        "assertion_level": "direct_evidence",
    }


def build_records(relationships_csv: Path) -> list[dict[str, Any]]:
    with relationships_csv.open() as f:
        reader = csv.DictReader(f)
        return [row_to_record(row) for row in reader]


def summarize_by_rel(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        rel = r["graph_rel_type"]
        counts[rel] = counts.get(rel, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# Vision-edge PMID / PMCID backfill (Stage B item c — evidence drill-down).
# --------------------------------------------------------------------------- #
#
# The Stage A export does not propagate PMID/PMCID for vision-track
# CORRELATES_WITH rows: the original proposal recorded only a hash-form
# figure_id, and the audit log later attached the PMC-form figure_id and
# `image_path` separately. The relationships.csv `evidence` field carries
# the proposal_id (e.g. "Vision proposal 5549945ad4a32b2f; ..."), which is
# the stable identifier we can chain through.
#
# Lookup chain:
#   1. evidence  →  proposal_id           (regex on `evidence`)
#   2. proposal_id  →  figure_id_pmc      (vision_proposals_*.jsonl image_path,
#                                          or vision_gated_audit.jsonl figure_id)
#   3. figure_id_pmc  →  PMCID            (string prefix parse)
#   4. PMCID (or PMID-in-filename) →  PMID + title + journal
#                                         (papers_*.jsonl corpus)
#
# This enrichment runs against the explorer JSONL only; the canonical
# Stage A bundle is not mutated. A future Stage A v2 should add PMID +
# figure_id_pmc columns to relationships.csv so this lateral join is no
# longer needed.

def extract_pmid_pmcid(obj: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pull PMID / PMCID from a vision-proposal record.

    Inspects three fields in priority order:
      - figure_id (e.g. 'PMC10605408_g004' → PMCID)
      - image_path basename (e.g. '37894458_correlation_...' → PMID;
                             'PMC9466706_g004.jpg' → PMCID)
      - pmid / pmcid fields directly
    """
    pmid = (obj.get("pmid") or "").strip() or None
    pmcid = (obj.get("pmcid") or "").strip() or None

    fig = obj.get("figure_id") or ""
    if not pmcid:
        m = _PMCID_PREFIX_RE.match(fig)
        if m:
            pmcid = m.group(1)

    img = obj.get("image_path") or ""
    basename = Path(img).name if img else ""
    if not pmcid:
        m = _PMCID_PREFIX_RE.match(basename)
        if m:
            pmcid = m.group(1)
    if not pmid:
        m = _PMID_PREFIX_RE.match(basename)
        if m:
            pmid = m.group(1)

    return pmid, pmcid


def load_vision_proposal_index(artifacts_dir: Path) -> dict[str, dict[str, str | None]]:
    """Index by proposal_id → {pmid, pmcid, image_path}, merging across pipeline +
    Session-4 vintages. Current pipeline overrides Session-4 on key collision."""
    index: dict[str, dict[str, str | None]] = {}
    for name in VISION_PROPOSAL_SOURCES:
        path = artifacts_dir / name
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid = obj.get("proposal_id")
                if not pid or pid in index:
                    continue
                pmid, pmcid = extract_pmid_pmcid(obj)
                if not (pmid or pmcid):
                    continue
                index[pid] = {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "image_path": obj.get("image_path") or None,
                }
    return index


def load_vision_audit_index(artifacts_dir: Path) -> dict[str, dict[str, Any]]:
    """Index retained-vision-edge audit rows by PMCID prefix (parsed from the
    PMC-form figure_id, e.g. 'PMC10605408_g004' → 'PMC10605408').

    Returns dict mapping PMCID → {figure_id_pmc, r_value, image_path}. Rows
    with `final_verdict == 'REJECT_GATE'` are excluded (they were dropped
    from the graph by the audit). On PMCID collision, last-write-wins —
    historical_graph_edge entries are written after current proposals so
    they win when a paper appears in both lanes.
    """
    index: dict[str, dict[str, Any]] = {}
    for name in VISION_AUDIT_SOURCES:
        path = artifacts_dir / name
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                verdict = obj.get("final_verdict")
                if verdict not in RETAINED_VISION_VERDICTS:
                    continue
                fig_pmc = obj.get("figure_id") or ""
                m = _PMCID_PREFIX_RE.match(fig_pmc)
                if not m:
                    continue
                pmcid = m.group(1)
                index[pmcid] = {
                    "figure_id_pmc": fig_pmc,
                    "r_value": obj.get("candidate_r"),
                    "image_path": obj.get("image_path"),
                }
    return index


def load_papers_corpus(artifacts_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build (by_pmid, by_pmcid) lookup tables from the harvested paper corpora.
    Either direction works; whichever id we have on hand resolves to the other."""
    by_pmid: dict[str, dict[str, Any]] = {}
    by_pmcid: dict[str, dict[str, Any]] = {}
    for name in PAPER_CORPUS_SOURCES:
        path = artifacts_dir / name
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pmid = str(obj.get("pmid") or obj.get("PMID") or "").strip() or None
                pmcid = (obj.get("pmcid") or obj.get("PMCID") or "").strip() or None
                if not (pmid or pmcid):
                    continue
                paper = {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "title": obj.get("title") or None,
                    "journal": obj.get("journal") or None,
                }
                if pmid and pmid not in by_pmid:
                    by_pmid[pmid] = paper
                if pmcid and pmcid not in by_pmcid:
                    by_pmcid[pmcid] = paper
    return by_pmid, by_pmcid


def backfill_vision_provenance(
    records: list[dict[str, Any]],
    proposal_index: dict[str, dict[str, str | None]],
    papers_by_pmid: dict[str, dict[str, Any]],
    papers_by_pmcid: dict[str, dict[str, Any]],
    audit_by_pmcid: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Mutate records in place: for any CORRELATES_WITH row with empty pmid,
    chain proposal_id → image_path → PMID/PMCID → papers corpus to fill in
    pmid, pmcid, title, journal. If `audit_by_pmcid` is provided, also
    backfill figure_id_pmc + r_value from the gated-audit log. Returns a
    counter dict for reporting."""
    audit_by_pmcid = audit_by_pmcid or {}
    stats = {
        "considered": 0, "backfilled_pmid": 0, "backfilled_pmcid": 0,
        "backfilled_title": 0, "backfilled_figure_id": 0, "backfilled_r_value": 0,
    }
    for r in records:
        if r["graph_rel_type"] != "CORRELATES_WITH":
            continue
        if r.get("pmid"):
            continue
        stats["considered"] += 1
        ev = r.get("evidence") or ""
        m = _PROPOSAL_RE.search(ev)
        if not m:
            continue
        pid = m.group(1).lower()
        prov = proposal_index.get(pid)
        if not prov:
            continue

        if prov.get("pmcid") and not r.get("pmcid"):
            r["pmcid"] = prov["pmcid"]
            stats["backfilled_pmcid"] += 1
        if prov.get("pmid") and not r.get("pmid"):
            r["pmid"] = prov["pmid"]
            stats["backfilled_pmid"] += 1

        # Cross-resolve PMID ↔ PMCID and pull title/journal from the corpus.
        paper = None
        if r.get("pmcid") and r["pmcid"] in papers_by_pmcid:
            paper = papers_by_pmcid[r["pmcid"]]
        elif r.get("pmid") and r["pmid"] in papers_by_pmid:
            paper = papers_by_pmid[r["pmid"]]
        if paper:
            if paper.get("pmid") and not r.get("pmid"):
                r["pmid"] = paper["pmid"]
                stats["backfilled_pmid"] += 1
            if paper.get("pmcid") and not r.get("pmcid"):
                r["pmcid"] = paper["pmcid"]
                stats["backfilled_pmcid"] += 1
            if paper.get("title") and not r.get("title"):
                r["title"] = paper["title"]
                stats["backfilled_title"] += 1
            if paper.get("journal") and not r.get("journal"):
                r["journal"] = paper["journal"]

        # Audit-side: figure_id_pmc + r_value for the surviving vision edge.
        if r.get("pmcid") and r["pmcid"] in audit_by_pmcid:
            audit = audit_by_pmcid[r["pmcid"]]
            if audit.get("figure_id_pmc") and not r.get("figure_id"):
                r["figure_id"] = audit["figure_id_pmc"]
                stats["backfilled_figure_id"] += 1
            if audit.get("r_value") is not None and r.get("r_value") is None:
                r["r_value"] = audit["r_value"]
                stats["backfilled_r_value"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-export", type=Path, default=DEFAULT_GRAPH_EXPORT,
                        help="Path to artifacts/graph_export/ (Stage A bundle).")
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS,
                        help="Path to artifacts/ for vision-provenance backfill lookups.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Path to write explorer JSONL.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate inputs and report counts; do not write.")
    args = parser.parse_args()

    relationships_csv = args.graph_export / "relationships.csv"
    manifest_path = args.graph_export / "manifest.json"

    if not relationships_csv.exists():
        raise SystemExit(f"missing input: {relationships_csv}")
    if not manifest_path.exists():
        raise SystemExit(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    post_total = manifest["counts"]["post_total"]

    records = build_records(relationships_csv)
    if len(records) != post_total:
        raise SystemExit(
            f"row-count drift: emitted {len(records)} but manifest.json says {post_total} "
            "post_total — inputs disagree, refusing to write."
        )

    # Vision-edge PMID/PMCID + figure_id_pmc + r_value backfill: lateral join
    # through the proposal_id encoded in `evidence`, augmented by the audit
    # log's PMC-form figure_id indexed by PMCID. Stage A bundle stays unchanged.
    proposal_index = load_vision_proposal_index(args.artifacts)
    audit_index = load_vision_audit_index(args.artifacts)
    papers_by_pmid, papers_by_pmcid = load_papers_corpus(args.artifacts)
    backfill_stats = backfill_vision_provenance(
        records, proposal_index, papers_by_pmid, papers_by_pmcid,
        audit_by_pmcid=audit_index,
    )

    by_rel = summarize_by_rel(records)

    if args.dry_run:
        print(f"DRY RUN — would write {len(records)} records to {args.output}")
        print(f"manifest post_total: {post_total}")
        print(f"vision-edge backfill: {backfill_stats}")
        print(f"breakdown by graph_rel_type:")
        for rel, n in sorted(by_rel.items()):
            print(f"  {rel}: {n}")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"wrote {len(records)} records to {args.output}")
    print(f"vision-edge backfill: {backfill_stats}")
    print(f"breakdown by graph_rel_type:")
    for rel, n in sorted(by_rel.items()):
        print(f"  {rel}: {n}")


if __name__ == "__main__":
    main()
