"""Unit tests for src/benchmark/sample_gold_set.py.

Synthetic JSONL fixtures so the test does not depend on production
artifacts. Verifies stratification logic, exclusivity across strata,
and deterministic seeding.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.benchmark.sample_gold_set import (
    DEFAULT_SEED,
    EXTENDED_FEATURE_KEYWORDS,
    _has_extended_feature_keyword,
    _has_generic_body_token,
    build_gold_set,
)


# --------------------------------------------------------------------------- #
#  Keyword helpers
# --------------------------------------------------------------------------- #
def test_extended_keyword_matches_psoas():
    match = _has_extended_feature_keyword("low psoas muscle area at l3")
    assert match is not None
    canonical, _ = match
    # "psoas muscle" wins over plain "psoas" because longer-first sort
    assert canonical == "psoas_muscle_area"


def test_extended_keyword_word_boundary_for_abbrev():
    # "fat" is not an abbrev; "PMI" is. PMI inside "PMID" must NOT match.
    match = _has_extended_feature_keyword("see pmid 12345 for context")
    assert match is None


def test_extended_keyword_matches_pmi_with_word_boundary():
    match = _has_extended_feature_keyword("pmi was reduced in cases")
    assert match is not None
    assert match[0] == "psoas_muscle_index"


def test_extended_keyword_misses_when_absent():
    assert _has_extended_feature_keyword("the cohort had n=200 patients") is None


def test_generic_body_token_matches_muscle():
    assert _has_generic_body_token("muscle and fat were measured") is True


def test_generic_body_token_word_boundary_bmi():
    # "bmi" must word-bound; embedded "abmis" should not match.
    assert _has_generic_body_token("abmis is not a real word") is False
    assert _has_generic_body_token("the bmi was calculated") is True


def test_generic_body_token_misses_when_absent():
    assert _has_generic_body_token("species diversity was high") is False


# --------------------------------------------------------------------------- #
#  build_gold_set on synthetic fixtures
# --------------------------------------------------------------------------- #
def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _accepted_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "microbe_feature_relations.jsonl"
    _write_jsonl(p, [
        {"record_id": "a1", "pmid": "P1",
         "source_node": "Akkermansia",
         "target_node": "visceral_adipose_tissue",
         "target_node_type": "BodyCompositionFeature",
         "rel_type": "CORRELATES_WITH",
         "evidence": "PMID P1: Akkermansia correlated with VAT.",
         "source_file": "microbe_feature_relations.jsonl"},
        {"record_id": "a2", "pmid": "P2",
         "source_node": "Bacteroides",
         "target_node": "sarcopenia",
         "target_node_type": "BodyCompositionFeature",
         "rel_type": "CORRELATES_WITH",
         "evidence": "PMID P2: Bacteroides depleted in sarcopenia.",
         "source_file": "microbe_feature_relations.jsonl"},
    ])
    return p


def _entity_sentences_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "entity_sentences_test.jsonl"
    _write_jsonl(p, [
        # vocab-matched sentences (will be candidates) — accepted
        {"pmid": "P1", "sentence": "Akkermansia correlated with VAT.",
         "microbes": [{"text": "Akkermansia"}]},
        {"pmid": "P2", "sentence": "Bacteroides depleted in sarcopenia.",
         "microbes": [{"text": "Bacteroides"}]},
        # vocab-matched (candidate) but not accepted → gemini_rejected
        {"pmid": "P3", "sentence": "Faecalibacterium and visceral adipose tissue both varied.",
         "microbes": [{"text": "Faecalibacterium"}]},
        {"pmid": "P4", "sentence": "Eubacterium and sarcopenia both noted in the cohort.",
         "microbes": [{"text": "Eubacterium"}]},
        # extended keyword → vocab_excluded
        {"pmid": "P5", "sentence": "Roseburia abundance correlated with psoas muscle area.",
         "microbes": [{"text": "Roseburia"}]},
        {"pmid": "P6", "sentence": "Prevotella was associated with epicardial fat.",
         "microbes": [{"text": "Prevotella"}]},
        # generic body token, no specific feature → recall_probe
        {"pmid": "P7", "sentence": "Lactobacillus correlated with muscle outcomes.",
         "microbes": [{"text": "Lactobacillus"}]},
        {"pmid": "P8", "sentence": "Bifidobacterium and bone development were studied.",
         "microbes": [{"text": "Bifidobacterium"}]},
        # has body token, also for random_co_occurrence pool
        {"pmid": "P9", "sentence": "Streptococcus and obesity correlation.",
         "microbes": [{"text": "Streptococcus"}]},
        # no body token at all — should be excluded from all strata
        {"pmid": "P10", "sentence": "Methodological details only here.",
         "microbes": [{"text": "Clostridium"}]},
    ])
    return p


def test_build_gold_set_basic_stratification(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    targets = {
        "accepted_edge": 5,
        "gemini_rejected": 5,
        "vocab_excluded": 5,
        "recall_probe": 5,
        "random_co_occurrence": 5,
    }
    rows, summary = build_gold_set(
        accepted_path=accepted,
        entity_sentences_paths=[sentences],
        seed=DEFAULT_SEED,
        targets=targets,
    )
    by_stratum = summary["by_stratum"]
    # Both accepted edges show up in the accepted_edge stratum
    assert by_stratum.get("accepted_edge", 0) == 2
    # Two non-accepted candidates are gemini_rejected
    assert by_stratum.get("gemini_rejected", 0) == 2
    # Two extended-keyword sentences become vocab_excluded
    assert by_stratum.get("vocab_excluded", 0) == 2
    # recall_probe and random_co_occurrence both fed by remaining body-token sentences
    assert by_stratum.get("recall_probe", 0) >= 1
    assert summary["seed"] == DEFAULT_SEED


def test_gold_set_deterministic_under_fixed_seed(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    rows1, _ = build_gold_set(accepted_path=accepted,
                              entity_sentences_paths=[sentences], seed=7)
    rows2, _ = build_gold_set(accepted_path=accepted,
                              entity_sentences_paths=[sentences], seed=7)
    assert [r.record_id for r in rows1] == [r.record_id for r in rows2]


def test_gold_set_differs_under_different_seeds(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    # Use a richer corpus so sampling has freedom to diverge
    extras = [
        {"pmid": f"PR{i}", "sentence": f"Microbe-{i} and muscle correlation observed.",
         "microbes": [{"text": f"Microbe{i}"}]}
        for i in range(20)
    ]
    p2 = tmp_path / "extra.jsonl"
    p2.write_text("\n".join(json.dumps(r) for r in extras) + "\n")
    rows_a, _ = build_gold_set(accepted_path=accepted,
                               entity_sentences_paths=[sentences, p2],
                               seed=1,
                               targets={
                                   "accepted_edge": 2, "gemini_rejected": 2,
                                   "vocab_excluded": 2, "recall_probe": 5,
                                   "random_co_occurrence": 5,
                               })
    rows_b, _ = build_gold_set(accepted_path=accepted,
                               entity_sentences_paths=[sentences, p2],
                               seed=999,
                               targets={
                                   "accepted_edge": 2, "gemini_rejected": 2,
                                   "vocab_excluded": 2, "recall_probe": 5,
                                   "random_co_occurrence": 5,
                               })
    assert {r.record_id for r in rows_a} != {r.record_id for r in rows_b}


def test_gold_row_unlabeled_jsonl_has_required_slots(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    rows, _ = build_gold_set(accepted_path=accepted,
                             entity_sentences_paths=[sentences],
                             seed=DEFAULT_SEED)
    payload = json.loads(rows[0].to_unlabeled_jsonl())
    for key in ("label", "evidence_type", "quantitative",
                "confidence", "evidence_span",
                "inferred_feature_canonical", "inferred_node_type",
                "annotator_notes", "labeled_at", "label_pass"):
        assert key in payload, f"missing slot: {key}"
    assert payload["label"] is None
    assert payload["annotator_notes"] == ""


def test_strata_are_mutually_exclusive_by_record_id(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    sample_rows, _ = build_gold_set(accepted_path=accepted,
                                    entity_sentences_paths=[sentences],
                                    seed=DEFAULT_SEED)
    ids = [r.record_id for r in sample_rows]
    assert len(ids) == len(set(ids))


def test_accepted_stratum_carries_canonical_feature(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    rows, _ = build_gold_set(accepted_path=accepted,
                             entity_sentences_paths=[sentences],
                             seed=DEFAULT_SEED)
    accepted_rows = [r for r in rows if r.stratum == "accepted_edge"]
    for r in accepted_rows:
        assert r.candidate_feature_canonical
        assert r.candidate_feature_node_type == "BodyCompositionFeature"
        assert r.pipeline_state == "accepted"


def test_recall_probe_has_no_candidate_feature(tmp_path):
    accepted = _accepted_fixture(tmp_path)
    sentences = _entity_sentences_fixture(tmp_path)
    rows, _ = build_gold_set(accepted_path=accepted,
                             entity_sentences_paths=[sentences],
                             seed=DEFAULT_SEED)
    recall_rows = [r for r in rows if r.stratum == "recall_probe"]
    for r in recall_rows:
        assert r.candidate_feature_canonical is None
        assert r.candidate_feature_node_type is None
        assert r.pipeline_state == "not_seen_by_pipeline"


def test_extended_feature_vocab_includes_radiomics_and_bodycomp():
    canonicals = set(EXTENDED_FEATURE_KEYWORDS.values())
    assert "psoas_muscle_area" in canonicals
    assert "epicardial_adipose_tissue" in canonicals
    assert "glcm_texture_feature" in canonicals
    assert "wavelet_texture_feature" in canonicals
