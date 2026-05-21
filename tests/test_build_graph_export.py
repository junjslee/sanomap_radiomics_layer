"""Tests for the Stage-A graph-export reconciler.

The graph export is a graph-touching artifact, so per the project's
testing-rigor policy it must be unit-gated. These tests pin the
deterministic reconciliation logic against synthetic fixtures so a future
change to the drop rules cannot silently alter the graph.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_graph_export import (
    apply_drops,
    build_export,
    count_by_rel,
    derive_nodes,
    load_umls_drops,
    render_import_cypher,
)

# A 4-row superset mirroring the real schema: one UMLS casualty, one vision
# casualty, two survivors (one of which is the kept vision edge).
_ROWS = [
    {
        "source_node_type": "Microbe", "source_node": "prevotella_nigrescens",
        "target_node_type": "RadiomicFeature", "target_node": "GLCM_Correlation",
        "rel_type": "CORRELATES_WITH", "pmid": "", "pmcid": "",
        "evidence": "Vision proposal abc; reason=verified", "confidence": "1.0",
    },
    {
        "source_node_type": "Microbe", "source_node": "firmicutes",
        "target_node_type": "RadiomicFeature", "target_node": "Total fat %",
        "rel_type": "CORRELATES_WITH", "pmid": "30337914", "pmcid": "PMC6178902",
        "evidence": "Vision proposal d2b; reason=verified", "confidence": "1.0",
    },
    {
        "source_node_type": "Microbe", "source_node": "bacteriodetes",
        "target_node_type": "BodyCompositionFeature", "target_node": "body_fat",
        "rel_type": "CORRELATES_WITH", "pmid": "30105955", "pmcid": "",
        "evidence": "PMID 30105955: ...", "confidence": "1.0",
    },
    {
        "source_node_type": "Microbe", "source_node": "ruminococcus",
        "target_node_type": "BodyCompositionFeature", "target_node": "sarcopenia",
        "rel_type": "CORRELATES_WITH", "pmid": "36536957", "pmcid": "",
        "evidence": "PMID 36536957: ...", "confidence": "0.85",
    },
]


@pytest.fixture()
def umls_audit(tmp_path: Path) -> Path:
    """Synthetic UMLS audit dropping only `bacteriodetes` (no_umls_match)."""
    p = tmp_path / "dropped_entities_audit.jsonl"
    p.write_text(json.dumps({
        "record_id": "x", "pmid": "30105955",
        "source_node": "bacteriodetes", "target_node": "body_fat",
        "rel_type": "CORRELATES_WITH", "drop_reason": "no_umls_match",
    }) + "\n", encoding="utf-8")
    return p


def test_load_umls_drops(umls_audit: Path) -> None:
    drops = load_umls_drops(umls_audit)
    assert len(drops) == 1
    assert drops[0].source_node == "bacteriodetes"
    assert drops[0].reason == "umls_gate:no_umls_match"
    assert str(umls_audit) in drops[0].source_of_truth


def test_load_umls_drops_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_umls_drops(tmp_path / "nope.jsonl") == []


def test_apply_drops_removes_umls_and_vision(umls_audit: Path) -> None:
    umls = load_umls_drops(umls_audit)
    kept, dropped = apply_drops(_ROWS, umls)
    kept_names = {r["source_node"] for r in kept}
    dropped_names = {d.source_node for d in dropped}

    # firmicutes (vision policy) + bacteriodetes (UMLS) dropped; 2 survive.
    assert dropped_names == {"firmicutes", "bacteriodetes"}
    assert kept_names == {"prevotella_nigrescens", "ruminococcus"}
    assert len(kept) == 2
    reasons = {d.source_node: d.reason for d in dropped}
    assert reasons["firmicutes"].startswith("vision_audit_retraction")
    assert reasons["bacteriodetes"] == "umls_gate:no_umls_match"


def test_apply_drops_is_deterministic(umls_audit: Path) -> None:
    umls = load_umls_drops(umls_audit)
    a = apply_drops(_ROWS, umls)
    b = apply_drops(_ROWS, umls)
    assert [r["source_node"] for r in a[0]] == [r["source_node"] for r in b[0]]


def test_vision_drop_requires_all_three_keys() -> None:
    # Same source_node but wrong pmcid → must NOT be dropped by vision policy.
    rows = [{
        "source_node_type": "Microbe", "source_node": "firmicutes",
        "target_node_type": "RadiomicFeature", "target_node": "Total fat %",
        "rel_type": "CORRELATES_WITH", "pmid": "x", "pmcid": "PMC_OTHER",
        "evidence": "", "confidence": "1.0",
    }]
    kept, dropped = apply_drops(rows, [])
    assert len(kept) == 1 and not dropped


def test_derive_nodes_unique_and_sorted() -> None:
    nodes = derive_nodes(_ROWS)
    pairs = [(n["label"], n["name"]) for n in nodes]
    assert pairs == sorted(pairs)
    assert ("Microbe", "firmicutes") in pairs
    assert ("RadiomicFeature", "GLCM_Correlation") in pairs
    # 4 distinct sources + 3 distinct targets (body_fat shared) = 7
    assert len(pairs) == len(set(pairs))


def test_count_by_rel() -> None:
    assert count_by_rel(_ROWS) == {"CORRELATES_WITH": 4}


def test_render_import_cypher_is_idempotent_and_safe() -> None:
    cypher = render_import_cypher(
        derive_nodes(_ROWS[:1]), _ROWS[:1]
    )
    assert "CREATE CONSTRAINT" in cypher
    assert "MERGE (:Microbe {name: 'prevotella_nigrescens'})" in cypher
    assert "MERGE (s)-[:CORRELATES_WITH" in cypher
    # idempotent: MATCH+MERGE, never CREATE for relationships
    assert "CREATE (s)-" not in cypher


def test_render_import_cypher_escapes_quotes() -> None:
    rows = [{
        "source_node_type": "Microbe", "source_node": "o'brien sp",
        "target_node_type": "Disease", "target_node": "x",
        "rel_type": "ASSOCIATED_WITH", "pmid": "1", "confidence": "0.7",
    }]
    cypher = render_import_cypher(derive_nodes(rows), rows)
    assert "o\\'brien sp" in cypher


def test_build_export_end_to_end(tmp_path: Path, umls_audit: Path) -> None:
    import csv

    src = tmp_path / "superset.csv"
    with open(src, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(_ROWS[0].keys()))
        w.writeheader()
        w.writerows(_ROWS)

    result = build_export(src, umls_audit)
    assert sum(result.pre_counts.values()) == 4
    assert sum(result.post_counts.values()) == 2
    assert len(result.dropped) == 2
