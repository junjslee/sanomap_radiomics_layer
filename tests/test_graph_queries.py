"""Tests for the read-only canonical graph query layer.

The single most important invariant: the application/query layer can never
contain a write clause. `assert_read_only` enforces it and these tests pin
it across every canonical query so a regression is impossible to merge
silently.
"""

from __future__ import annotations

import pytest

from src.graph_queries import (
    CANONICAL_QUERIES,
    assert_read_only,
    entity_search,
    features_for_disease,
    neighborhood,
    signed_microbe_disease,
    three_hop_paths,
    vision_verified_edges,
)


def test_all_canonical_queries_are_read_only() -> None:
    for name, fn in CANONICAL_QUERIES.items():
        cypher, params = fn() if name not in (
            "features_for_disease", "features_at_location",
            "entity_search", "neighborhood",
        ) else fn("x")
        assert_read_only(cypher)  # raises AssertionError on any write clause
        assert isinstance(params, dict), name


def test_assert_read_only_rejects_writes() -> None:
    for bad in [
        "MATCH (n) DETACH DELETE n",
        "CREATE (n:X)",
        "MATCH (n) SET n.x = 1",
        "MERGE (n:X {name:'y'})",
        "MATCH (n) REMOVE n.x",
    ]:
        with pytest.raises(AssertionError):
            assert_read_only(bad)


def test_parameters_not_interpolated() -> None:
    # User input must travel as a $param, never be baked into the string.
    cypher, params = features_for_disease("colorectal'; MATCH (x) DELETE x //")
    assert "DELETE" not in cypher.upper()
    assert params["disease"] == "colorectal'; MATCH (x) DELETE x //"
    assert "$disease" in cypher


def test_three_hop_shape() -> None:
    cypher, params = three_hop_paths(limit=25)
    assert "CORRELATES_WITH" in cypher and "ASSOCIATED_WITH" in cypher
    assert params == {"limit": 25}


def test_signed_query_uses_both_directions() -> None:
    cypher, _ = signed_microbe_disease()
    assert "POSITIVELY_CORRELATED_WITH" in cypher
    assert "NEGATIVELY_CORRELATED_WITH" in cypher


def test_vision_query_filters_vision_evidence() -> None:
    cypher, _ = vision_verified_edges()
    assert "Vision proposal" in cypher


def test_entity_search_and_neighborhood_are_app_entrypoints() -> None:
    c1, p1 = entity_search("prevo")
    c2, p2 = neighborhood("sarcopenia")
    assert "$q" in c1 and p1["q"] == "prevo"
    assert "$name" in c2 and p2["name"] == "sarcopenia"
    assert_read_only(c1)
    assert_read_only(c2)
