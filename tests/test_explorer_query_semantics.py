"""Tests for the explorer's canonical queries — parity + non-empty invariants.

The static explorer (`docs/explorer/index.html`) implements the same six
canonical traversals that `src/graph_queries.py` ships as Cypher. The JS
implementation operates on the loaded JSONL records; the Cypher implementation
operates on Neo4j. Both have to agree because the manuscript will cite the
Cypher form and reviewers will spot-check the explorer.

This test file re-implements each canonical query in Python over the emitted
`docs/explorer/data.jsonl` and pins the invariants that:

1. each query returns a non-empty result against the current post-audit graph,
2. the load-bearing thesis claims (vision-verified edge surviving, 3 thesis
   3-hop closers present) hold for the queries that touch them.

If a future schema change silently drops a field these queries depend on, this
test breaks BEFORE the explorer ships broken. That's the whole point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSONL = REPO_ROOT / "docs" / "explorer" / "data.jsonl"


def _load_records() -> list[dict[str, Any]]:
    if not DATA_JSONL.exists():
        return []
    with DATA_JSONL.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _dedupe_by_edge_id(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        eid = r.get("edge_id")
        if eid and eid not in seen:
            seen.add(eid)
            out.append(r)
    return out


# --- Python mirrors of the JS canonical queries ----------------------------

def q_three_hop_paths(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    correlates = [
        r for r in records
        if r["graph_rel_type"] == "CORRELATES_WITH" and r["subject_node_type"] == "Microbe"
    ]
    feature_names = {r["object_node"] for r in correlates}
    feature_disease = [
        r for r in records
        if r["graph_rel_type"] == "ASSOCIATED_WITH" and r["subject_node"] in feature_names
    ]
    return _dedupe_by_edge_id([*correlates, *feature_disease])


def q_features_for_disease(records: list[dict[str, Any]], substring: str) -> list[dict[str, Any]]:
    needle = (substring or "").strip().lower()
    if not needle:
        return [r for r in records if r["graph_rel_type"] == "ASSOCIATED_WITH"]
    return [
        r for r in records
        if r["graph_rel_type"] == "ASSOCIATED_WITH"
        and needle in (r.get("disease") or "").lower()
    ]


def q_signed_microbe_disease(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signed = [
        r for r in records
        if r["graph_rel_type"] in {"POSITIVELY_CORRELATED_WITH", "NEGATIVELY_CORRELATED_WITH"}
    ]
    signed.sort(key=lambda r: r.get("confidence") or 0.0, reverse=True)
    return signed


def q_features_at_location(records: list[dict[str, Any]], loc: str) -> list[dict[str, Any]]:
    needle = (loc or "").strip().lower()
    if not needle:
        return [r for r in records if r["graph_rel_type"] == "MEASURED_AT"]
    return [
        r for r in records
        if r["graph_rel_type"] == "MEASURED_AT"
        and (r.get("object_node") or "").lower() == needle
    ]


def q_full_modality_chain(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    correlates = [
        r for r in records
        if r["graph_rel_type"] == "CORRELATES_WITH" and r["subject_node_type"] == "Microbe"
    ]
    feature_names = {r["object_node"] for r in correlates}
    modality = [
        r for r in records
        if r["graph_rel_type"] == "ACQUIRED_VIA" and r["subject_node"] in feature_names
    ]
    disease = [
        r for r in records
        if r["graph_rel_type"] == "ASSOCIATED_WITH" and r["subject_node"] in feature_names
    ]
    return _dedupe_by_edge_id([*correlates, *modality, *disease])


def q_vision_verified_edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r for r in records
        if r["graph_rel_type"] == "CORRELATES_WITH"
        and "Vision proposal" in (r.get("evidence") or "")
    ]


# --- Invariants ------------------------------------------------------------

def test_data_jsonl_exists_and_has_post_audit_count():
    recs = _load_records()
    if not recs:
        return  # CI without artifacts; build_explorer_data tests already cover counts
    assert len(recs) == 189, (
        f"data.jsonl has {len(recs)} rows; expected 189 (Stage A post-audit). "
        "Re-run scripts/build_explorer_data.py."
    )


def test_three_hop_paths_returns_microbe_feature_and_feature_disease_legs():
    recs = _load_records()
    if not recs:
        return
    rows = q_three_hop_paths(recs)
    # Both legs must be present in the returned subset so the table + graph
    # render the full 3-hop chain, not just one half.
    rel_types = {r["graph_rel_type"] for r in rows}
    assert "CORRELATES_WITH" in rel_types
    assert "ASSOCIATED_WITH" in rel_types
    assert len(rows) > 0


def test_three_thesis_closers_traversable_in_three_hop_query():
    """The 3 thesis-load-bearing 3-hop closers must be reachable from this query.

    These are the load-bearing novelty demos the paper cites; if a future
    schema change drops their microbe→feature edge, this fails immediately.
    """
    recs = _load_records()
    if not recs:
        return
    rows = q_three_hop_paths(recs)
    correlates_pairs = {
        (r["subject_node"], r["object_node"])
        for r in rows
        if r["graph_rel_type"] == "CORRELATES_WITH"
    }
    expected = {
        ("ruminococcus", "sarcopenia"),
        ("peptostreptococcus stomatis", "skeletal_muscle_index"),
        ("eubacterium", "visceral_adipose_tissue"),
    }
    missing = expected - correlates_pairs
    assert not missing, f"thesis 3-hop closers missing from data: {missing}"


def test_features_for_disease_cirrhosis_yields_results():
    recs = _load_records()
    if not recs:
        return
    rows = q_features_for_disease(recs, "cirrhosis")
    assert len(rows) > 0
    # All returned rows must actually mention cirrhosis on the disease side.
    for r in rows:
        assert "cirrhosis" in (r["disease"] or "").lower()


def test_signed_microbe_disease_count_matches_manifest():
    """Manifest says 14 POSITIVELY + 15 NEGATIVELY = 29 signed microbe-disease."""
    recs = _load_records()
    if not recs:
        return
    rows = q_signed_microbe_disease(recs)
    pos = sum(1 for r in rows if r["graph_rel_type"] == "POSITIVELY_CORRELATED_WITH")
    neg = sum(1 for r in rows if r["graph_rel_type"] == "NEGATIVELY_CORRELATED_WITH")
    assert pos == 14, f"POSITIVELY_CORRELATED_WITH count drifted: {pos} vs 14"
    assert neg == 15, f"NEGATIVELY_CORRELATED_WITH count drifted: {neg} vs 15"
    # And sort order: highest-confidence first.
    confidences = [r.get("confidence") or 0.0 for r in rows]
    assert confidences == sorted(confidences, reverse=True)


def test_features_at_location_abdomen_yields_results():
    recs = _load_records()
    if not recs:
        return
    rows = q_features_at_location(recs, "abdomen")
    assert len(rows) > 0
    for r in rows:
        assert (r["object_node"] or "").lower() == "abdomen"
        assert r["graph_rel_type"] == "MEASURED_AT"


def test_full_modality_chain_yields_at_least_one_complete_chain():
    """For at least one Microbe→Feature, BOTH ACQUIRED_VIA and ASSOCIATED_WITH
    legs must be present in the returned subset — otherwise the 'chain'
    label is misleading."""
    recs = _load_records()
    if not recs:
        return
    rows = q_full_modality_chain(recs)
    correlates_features = {
        r["object_node"]
        for r in rows
        if r["graph_rel_type"] == "CORRELATES_WITH"
    }
    modality_features = {
        r["subject_node"]
        for r in rows
        if r["graph_rel_type"] == "ACQUIRED_VIA"
    }
    disease_features = {
        r["subject_node"]
        for r in rows
        if r["graph_rel_type"] == "ASSOCIATED_WITH"
    }
    full_chain = correlates_features & modality_features & disease_features
    assert len(full_chain) > 0, (
        "No Microbe→Feature feature has BOTH a modality AND a disease edge — "
        "the 'full_modality_chain' query degenerates to a partial chain."
    )


def test_vision_verified_edges_returns_exactly_the_surviving_audit_edge():
    """Post-2026-05-07 vision audit: exactly one CORRELATES_WITH edge with a
    'Vision proposal' provenance survived (prevotella_nigrescens ↔
    GLCM_Correlation, retained per direct image inspection). The other 6
    CORRELATES_WITH edges are text-track Gemini self-consistency, NOT
    vision-verified.

    If this number changes, either (a) a new vision edge passed gates and was
    promoted to the graph, or (b) the surviving edge was dropped. Either
    materially changes the manuscript's vision-track claim and must be
    explicitly acknowledged before the data.jsonl ships."""
    recs = _load_records()
    if not recs:
        return
    rows = q_vision_verified_edges(recs)
    assert len(rows) == 1, f"vision-verified count drifted: {len(rows)} (expected 1)"
    edge = rows[0]
    assert edge["subject_node"] == "prevotella_nigrescens"
    assert edge["object_node"] == "GLCM_Correlation"


def test_text_track_correlates_with_count_is_six():
    """7 CORRELATES_WITH total, minus 1 vision-verified, = 6 text-track."""
    recs = _load_records()
    if not recs:
        return
    correlates = [r for r in recs if r["graph_rel_type"] == "CORRELATES_WITH"]
    vision = q_vision_verified_edges(recs)
    text_track = [r for r in correlates if r not in vision]
    assert len(correlates) == 7
    assert len(text_track) == 6
