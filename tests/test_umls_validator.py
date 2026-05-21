"""Unit tests for src/umls_validator.py.

These tests use a stub normalizer that mimics the UMLSNormalizer.normalize()
contract: returns a dict with cui/tui/similarity/official_name, or None.

The stub avoids loading scispacy + UMLS KB (~5GB), which by repo policy
must run from Terminal.app rather than VSCode/Claude Code subprocesses.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.umls_validator import (
    MICROBE_TUIS_ACCEPT,
    EntityGate,
    GroundedEntity,
    make_microbe_gate,
)


class StubNormalizer:
    """Mimics UMLSNormalizer.normalize() with a hand-crafted lookup table."""

    def __init__(self, table: dict[str, dict[str, Any]] | None = None) -> None:
        self.table: dict[str, dict[str, Any]] = table or {}
        self.calls: list[tuple[str, frozenset[str] | None]] = []

    def normalize(self, text: str, allowed_tuis: set[str] | None = None) -> dict[str, Any] | None:
        key = text.strip().lower()
        self.calls.append((key, frozenset(allowed_tuis) if allowed_tuis else None))
        record = self.table.get(key)
        if record is None:
            return None
        if allowed_tuis is not None and record["tui"] not in allowed_tuis:
            return None
        return dict(record)


# --------------------------------------------------------------------------- #
#  Construction
# --------------------------------------------------------------------------- #
def test_gate_rejects_non_normalizer():
    with pytest.raises(TypeError):
        EntityGate(normalizer="not a normalizer", accepted_tuis=MICROBE_TUIS_ACCEPT)  # type: ignore[arg-type]


def test_microbe_gate_default_policy():
    stub = StubNormalizer()
    gate = make_microbe_gate(stub)
    assert gate.accepted_tuis == MICROBE_TUIS_ACCEPT
    assert "C0086418" in gate.deny_cuis  # Homo sapiens denied by default


# --------------------------------------------------------------------------- #
#  Acceptance paths
# --------------------------------------------------------------------------- #
def test_accepts_well_grounded_bacterium():
    stub = StubNormalizer({
        "akkermansia muciniphila": {
            "cui": "C1287450",
            "tui": "T007",
            "similarity": 0.97,
            "official_name": "Akkermansia muciniphila",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("Akkermansia muciniphila")
    assert result.accepted is True
    assert result.cui == "C1287450"
    assert result.tui == "T007"
    assert result.drop_reason == ""


def test_accepts_archaeon():
    stub = StubNormalizer({
        "methanobrevibacter smithii": {
            "cui": "C1080039",
            "tui": "T194",
            "similarity": 0.92,
            "official_name": "Methanobrevibacter smithii",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("Methanobrevibacter smithii")
    assert result.accepted is True
    assert result.tui == "T194"


def test_accepts_eukaryote_fungus_via_t204():
    stub = StubNormalizer({
        "candida albicans": {
            "cui": "C0006840",
            "tui": "T204",
            "similarity": 0.95,
            "official_name": "Candida albicans",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("Candida albicans")
    assert result.accepted is True


def test_accepts_virus_via_t005():
    """Virome future-proofing — T005 was added to the accept set 2026-05-04."""
    stub = StubNormalizer({
        "crassphage": {
            "cui": "C5212385",
            "tui": "T005",
            "similarity": 0.91,
            "official_name": "crAssphage",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("crAssphage")
    assert result.accepted is True
    assert result.tui == "T005"


# --------------------------------------------------------------------------- #
#  Rejection paths — these are the Edge #5 class of failures
# --------------------------------------------------------------------------- #
def test_rejects_unmatched_surface():
    """The Edge #5 case: NER tagged a phrase that has no UMLS match at all."""
    stub = StubNormalizer({})  # empty table → always None
    gate = make_microbe_gate(stub)
    result = gate.evaluate("gut bacterial clpb-like gene function")
    assert result.accepted is False
    assert result.drop_reason == "no_umls_match"
    assert result.cui == ""


def test_rejects_when_grounded_but_wrong_tui():
    """A surface form that grounds to a non-microbe Semantic Type."""
    stub = StubNormalizer({
        "clpb gene": {
            "cui": "C1334144",
            "tui": "T028",  # Gene or Genome
            "similarity": 0.91,
            "official_name": "CLPB gene",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("CLPB gene")
    # First call (with allowed_tuis) returns None; gate retries unrestricted
    # and gets the non-microbe match. Drop reason names the wrong TUI.
    assert result.accepted is False
    assert result.drop_reason == "tui_not_in_accept_set"
    assert result.tui == "T028"


def test_rejects_low_similarity_match():
    stub = StubNormalizer({
        "vague microbe": {
            "cui": "C1234567",
            "tui": "T007",
            "similarity": 0.51,  # below default 0.85 floor
            "official_name": "Some bacterium",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("vague microbe")
    assert result.accepted is False
    assert result.drop_reason.startswith("low_similarity")


def test_rejects_human_via_deny_list():
    """T204 admits humans by Semantic Type alone — deny-list catches them."""
    stub = StubNormalizer({
        "homo sapiens": {
            "cui": "C0086418",  # in NON_MICROBE_EUKARYOTE_DENY
            "tui": "T204",
            "similarity": 0.99,
            "official_name": "Homo sapiens",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("Homo sapiens")
    assert result.accepted is False
    assert result.drop_reason.startswith("deny_cui:")
    assert "Homo sapiens" in result.drop_reason


def test_rejects_mouse_via_deny_list():
    stub = StubNormalizer({
        "mus musculus": {
            "cui": "C0025929",
            "tui": "T204",
            "similarity": 0.98,
            "official_name": "Mus musculus",
        }
    })
    gate = make_microbe_gate(stub)
    result = gate.evaluate("Mus musculus")
    assert result.accepted is False
    assert "Mus musculus" in result.drop_reason


def test_rejects_empty_surface():
    stub = StubNormalizer({})
    gate = make_microbe_gate(stub)
    result = gate.evaluate("")
    assert result.accepted is False
    assert result.drop_reason == "empty_surface"


# --------------------------------------------------------------------------- #
#  Batch interface
# --------------------------------------------------------------------------- #
def test_filter_entity_dicts_splits_kept_and_dropped():
    stub = StubNormalizer({
        "akkermansia": {
            "cui": "C1287449",
            "tui": "T007",
            "similarity": 0.93,
            "official_name": "Akkermansia",
        },
        "homo sapiens": {
            "cui": "C0086418",
            "tui": "T204",
            "similarity": 0.99,
            "official_name": "Homo sapiens",
        },
    })
    gate = make_microbe_gate(stub)
    inputs = [
        {"text": "Akkermansia", "score": 0.92},
        {"text": "Homo sapiens", "score": 0.99},
        {"text": "gut bacterial clpb-like gene function", "score": 0.88},
    ]
    kept, dropped = gate.filter_entity_dicts(inputs)
    assert len(kept) == 1
    assert kept[0]["cui"] == "C1287449"
    assert kept[0]["umls_similarity"] == pytest.approx(0.93)
    assert kept[0]["score"] == pytest.approx(0.92)  # original fields preserved
    assert len(dropped) == 2
    drop_reasons = {str(d["drop_reason"]) for d in dropped}
    assert any(r.startswith("deny_cui:") for r in drop_reasons)
    assert "no_umls_match" in drop_reasons


def test_filter_preserves_original_fields():
    stub = StubNormalizer({
        "akkermansia": {
            "cui": "C1287449",
            "tui": "T007",
            "similarity": 0.93,
            "official_name": "Akkermansia",
        }
    })
    gate = make_microbe_gate(stub)
    inputs = [{"text": "Akkermansia", "start": 12, "end": 23, "label": "B-Microbe"}]
    kept, _ = gate.filter_entity_dicts(inputs)
    assert kept[0]["start"] == 12
    assert kept[0]["end"] == 23
    assert kept[0]["label"] == "B-Microbe"
    assert kept[0]["cui"] == "C1287449"


def test_custom_text_field():
    stub = StubNormalizer({
        "akkermansia": {
            "cui": "C1287449",
            "tui": "T007",
            "similarity": 0.93,
            "official_name": "Akkermansia",
        }
    })
    gate = make_microbe_gate(stub)
    inputs = [{"surface_form": "Akkermansia"}]
    kept, _ = gate.filter_entity_dicts(inputs, text_field="surface_form")
    assert len(kept) == 1


# --------------------------------------------------------------------------- #
#  Disease gate sanity
# --------------------------------------------------------------------------- #
def test_disease_gate_accepts_disease_tui():
    stub = StubNormalizer({
        "colorectal cancer": {
            "cui": "C0009402",
            "tui": "T191",
            "similarity": 0.96,
            "official_name": "Colorectal Carcinoma",
        }
    })
    from src.umls_validator import make_disease_gate
    gate = make_disease_gate(stub)
    result = gate.evaluate("colorectal cancer")
    assert result.accepted is True
    assert result.tui == "T191"


# --------------------------------------------------------------------------- #
#  Grounded entity dataclass
# --------------------------------------------------------------------------- #
def test_grounded_entity_as_dict_round_trip():
    g = GroundedEntity("Akkermansia", "C1", "T007", 0.93, "Akkermansia", True)
    payload = g.as_dict()
    assert payload["surface"] == "Akkermansia"
    assert payload["accepted"] is True
    assert payload["drop_reason"] == ""
