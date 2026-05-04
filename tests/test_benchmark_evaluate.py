"""Unit tests for src/benchmark/evaluate.py.

Synthetic labeled JSONL + accepted-edge fixtures verify P/R/F1 math,
per-stratum bucketing, label-policy edge cases, multi-class breakdown,
and Cohen's κ for IAA.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.benchmark.evaluate import (
    ASSOCIATED_LABELS,
    Confusion,
    GoldLabel,
    cohens_kappa,
    gold_binary,
    load_accepted_edges,
    load_gold,
    multi_class_breakdown,
    pipeline_predict,
    score,
)


# --------------------------------------------------------------------------- #
#  Label policy
# --------------------------------------------------------------------------- #
def test_gold_binary_associated_positive():
    assert gold_binary("associated_positive") == 1


def test_gold_binary_associated_negative():
    assert gold_binary("associated_negative") == 1  # gold=1 means "any association"


def test_gold_binary_no_association_explicit():
    assert gold_binary("no_association_explicit") == 0


def test_gold_binary_not_associated():
    assert gold_binary("not_associated") == 0


def test_gold_binary_unclear_returns_none():
    assert gold_binary("unclear") is None


def test_gold_binary_none_label_returns_none():
    assert gold_binary(None) is None


def test_gold_binary_unknown_label_raises():
    with pytest.raises(ValueError):
        gold_binary("invented_label")


# --------------------------------------------------------------------------- #
#  Confusion math
# --------------------------------------------------------------------------- #
def test_confusion_perfect():
    c = Confusion(tp=10, fp=0, fn=0, tn=10)
    assert c.precision == pytest.approx(1.0)
    assert c.recall == pytest.approx(1.0)
    assert c.f1 == pytest.approx(1.0)


def test_confusion_zero_predicted():
    c = Confusion(tp=0, fp=0, fn=5, tn=5)
    assert c.precision == 0.0
    assert c.recall == 0.0
    assert c.f1 == 0.0


def test_confusion_partial():
    c = Confusion(tp=3, fp=1, fn=2, tn=4)  # precision 0.75, recall 0.6
    assert c.precision == pytest.approx(0.75)
    assert c.recall == pytest.approx(0.6)
    # F1 = 2*0.75*0.6 / (0.75+0.6) = 0.9 / 1.35 ≈ 0.6667
    assert c.f1 == pytest.approx(0.6667, abs=1e-3)


# --------------------------------------------------------------------------- #
#  Pipeline prediction
# --------------------------------------------------------------------------- #
def _gl(**kw):
    """Build a GoldLabel with sensible defaults."""
    defaults = {
        "record_id": "r0",
        "pmid": "P1",
        "stratum": "accepted_edge",
        "microbe": "akkermansia",
        "candidate_feature_canonical": "visceral_adipose_tissue",
        "inferred_feature_canonical": None,
        "label": "associated_positive",
        "evidence_type": "direct_measurement",
        "quantitative": "has_correlation_coef",
        "confidence": "high",
    }
    defaults.update(kw)
    return GoldLabel(**defaults)


def test_pipeline_predict_hit():
    accepted = {("P1", "akkermansia", "visceral_adipose_tissue")}
    assert pipeline_predict(_gl(), accepted) == 1


def test_pipeline_predict_miss():
    accepted: set = set()
    assert pipeline_predict(_gl(), accepted) == 0


def test_pipeline_predict_uses_inferred_feature_when_candidate_null():
    accepted = {("P1", "akkermansia", "psoas_muscle_area")}
    row = _gl(candidate_feature_canonical=None,
              inferred_feature_canonical="psoas_muscle_area")
    assert pipeline_predict(row, accepted) == 1


def test_pipeline_predict_zero_when_no_feature_at_all():
    row = _gl(candidate_feature_canonical=None,
              inferred_feature_canonical=None)
    assert pipeline_predict(row, set()) == 0


# --------------------------------------------------------------------------- #
#  Score aggregation
# --------------------------------------------------------------------------- #
def test_score_overall_metrics():
    gold = [
        # 2 TP
        _gl(record_id="r1", label="associated_positive"),
        _gl(record_id="r2", label="associated_negative",
            pmid="P2", microbe="bacteroides",
            candidate_feature_canonical="sarcopenia"),
        # 1 FP (pipeline predicts but gold says no)
        _gl(record_id="r3", label="not_associated",
            pmid="P3", microbe="prevotella",
            candidate_feature_canonical="body_fat"),
        # 1 FN (gold says yes but pipeline misses)
        _gl(record_id="r4", label="associated_unsigned",
            pmid="P4", microbe="lactobacillus",
            candidate_feature_canonical="sarcopenia"),
        # 1 TN
        _gl(record_id="r5", label="not_associated",
            pmid="P5", microbe="bifidobacterium",
            candidate_feature_canonical="body_fat"),
        # excluded
        _gl(record_id="r6", label="unclear"),
        # not labeled yet
        _gl(record_id="r7", label=None),
    ]
    accepted = {
        ("P1", "akkermansia", "visceral_adipose_tissue"),
        ("P2", "bacteroides", "sarcopenia"),
        ("P3", "prevotella", "body_fat"),  # FP
    }
    metrics = score(gold, accepted)
    assert metrics["n_total"] == 7
    assert metrics["skipped_unclear"] == 1
    assert metrics["skipped_no_label"] == 1
    assert metrics["n_scored"] == 5
    overall = metrics["overall"]
    assert overall["tp"] == 2
    assert overall["fp"] == 1
    assert overall["fn"] == 1
    assert overall["tn"] == 1
    assert overall["precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert overall["recall"] == pytest.approx(2 / 3, abs=1e-3)


def test_score_per_stratum_breakdown():
    gold = [
        _gl(record_id="r1", stratum="accepted_edge",
            label="associated_positive"),
        _gl(record_id="r2", stratum="gemini_rejected",
            label="associated_unsigned",
            pmid="P2", microbe="m2",
            candidate_feature_canonical="sarcopenia"),
    ]
    accepted = {("P1", "akkermansia", "visceral_adipose_tissue")}
    metrics = score(gold, accepted)
    assert "accepted_edge" in metrics["by_stratum"]
    assert "gemini_rejected" in metrics["by_stratum"]
    # accepted_edge: 1 TP
    assert metrics["by_stratum"]["accepted_edge"]["tp"] == 1
    # gemini_rejected: 1 FN (gold says associated, pipeline didn't emit)
    assert metrics["by_stratum"]["gemini_rejected"]["fn"] == 1


def test_score_per_feature_breakdown():
    gold = [
        _gl(record_id="r1", label="associated_positive"),  # VAT
        _gl(record_id="r2", label="associated_positive",
            pmid="P2", microbe="bact",
            candidate_feature_canonical="sarcopenia"),
    ]
    accepted = {
        ("P1", "akkermansia", "visceral_adipose_tissue"),
        ("P2", "bact", "sarcopenia"),
    }
    metrics = score(gold, accepted)
    assert "visceral_adipose_tissue" in metrics["by_feature"]
    assert "sarcopenia" in metrics["by_feature"]
    assert metrics["by_feature"]["visceral_adipose_tissue"]["tp"] == 1
    assert metrics["by_feature"]["sarcopenia"]["tp"] == 1


def test_score_label_distribution():
    gold = [
        _gl(record_id="r1", label="associated_positive"),
        _gl(record_id="r2", label="associated_positive",
            pmid="P2", microbe="m"),
        _gl(record_id="r3", label="unclear"),
    ]
    metrics = score(gold, set())
    assert metrics["label_distribution"]["associated_positive"] == 2
    assert metrics["label_distribution"]["unclear"] == 1


def test_score_unclear_rate():
    gold = [
        _gl(record_id="r1", label="associated_positive"),
        _gl(record_id="r2", label="unclear"),
        _gl(record_id="r3", label="unclear"),
        _gl(record_id="r4", label="not_associated"),
    ]
    metrics = score(gold, set())
    assert metrics["unclear_rate"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
#  Multi-class breakdown
# --------------------------------------------------------------------------- #
def test_multi_class_breakdown_counts():
    gold = [
        _gl(record_id="r1", label="associated_positive"),
        _gl(record_id="r2", label="associated_negative"),
        _gl(record_id="r3", label="associated_negative"),
        _gl(record_id="r4", label="associated_unsigned"),
        _gl(record_id="r5", label="not_associated"),
    ]
    breakdown = multi_class_breakdown(gold)
    assert breakdown["associated_positive"] == 1
    assert breakdown["associated_negative"] == 2
    assert breakdown["associated_unsigned"] == 1
    # not_associated is correctly excluded
    assert sum(breakdown.values()) == 4


# --------------------------------------------------------------------------- #
#  Cohen's κ
# --------------------------------------------------------------------------- #
def test_kappa_perfect_agreement():
    pass1 = [_gl(record_id=f"r{i}", label="associated_positive") for i in range(5)]
    pass2 = [_gl(record_id=f"r{i}", label="associated_positive") for i in range(5)]
    result = cohens_kappa(pass1, pass2)
    assert result["kappa"] == pytest.approx(1.0)
    assert result["n"] == 5


def test_kappa_chance_level():
    # Chance-level disagreement should give κ ≈ 0
    pass1 = [_gl(record_id=f"r{i}",
                 label="associated_positive" if i % 2 == 0 else "not_associated")
             for i in range(20)]
    pass2 = [_gl(record_id=f"r{i}",
                 label="not_associated" if i % 2 == 0 else "associated_positive")
             for i in range(20)]
    # Total disagreement → κ is very negative
    result = cohens_kappa(pass1, pass2)
    assert result["kappa"] < 0.0


def test_kappa_binary_collapse():
    # Pass 1: all associated_positive. Pass 2: mix of positive/negative.
    # Under multi-class, partial disagreement; under binary, full agreement.
    pass1 = [_gl(record_id=f"r{i}", label="associated_positive") for i in range(4)]
    pass2 = [_gl(record_id=f"r{i}",
                 label="associated_negative" if i % 2 else "associated_positive")
             for i in range(4)]
    result_multi = cohens_kappa(pass1, pass2, binary=False)
    result_bin = cohens_kappa(pass1, pass2, binary=True)
    assert result_bin["kappa"] == pytest.approx(1.0)
    assert result_bin["binary"] is True
    assert result_multi["binary"] is False


def test_kappa_handles_empty_intersection():
    pass1 = [_gl(record_id="rA", label="associated_positive")]
    pass2 = [_gl(record_id="rB", label="associated_positive")]
    result = cohens_kappa(pass1, pass2)
    assert result["n"] == 0
    assert math.isnan(result["kappa"])


# --------------------------------------------------------------------------- #
#  Loaders
# --------------------------------------------------------------------------- #
def test_load_gold_round_trip(tmp_path):
    p = tmp_path / "gold.jsonl"
    p.write_text("\n".join([
        json.dumps({
            "record_id": "r1", "pmid": "P1", "stratum": "accepted_edge",
            "microbe": "Akkermansia", "candidate_feature_canonical": "VAT",
            "inferred_feature_canonical": None,
            "label": "associated_positive", "evidence_type": "direct_measurement",
            "quantitative": "has_correlation_coef", "confidence": "high",
        }),
    ]))
    rows = load_gold(p)
    assert len(rows) == 1
    r = rows[0]
    assert r.microbe == "akkermansia"  # lowercased on load
    assert r.label == "associated_positive"


def test_load_accepted_edges_round_trip(tmp_path):
    p = tmp_path / "accepted.jsonl"
    p.write_text(json.dumps({
        "pmid": "P1", "source_node": "Akkermansia",
        "target_node": "visceral_adipose_tissue",
    }) + "\n")
    keys = load_accepted_edges(p)
    assert ("P1", "akkermansia", "visceral_adipose_tissue") in keys


def test_load_accepted_edges_empty_when_path_missing(tmp_path):
    keys = load_accepted_edges(tmp_path / "nonexistent.jsonl")
    assert keys == set()


# --------------------------------------------------------------------------- #
#  Sanity on label set
# --------------------------------------------------------------------------- #
def test_associated_labels_set_is_correct():
    assert ASSOCIATED_LABELS == frozenset({
        "associated_positive",
        "associated_negative",
        "associated_unsigned",
    })
