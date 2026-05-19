# tests/test_pilot_run.py
import json, os, tempfile
from src.pilot.run_pilot import compute_report, _load_records, THESIS_ANCHORS

def _row(subj, obj, label, stratum, decision):
    return ({"subject": subj, "object": obj, "label": label,
             "stratum": stratum}, decision)

_E = ("eubacterium", "visceral_adipose_tissue")
_R = ("ruminococcus", "sarcopenia")
_P = ("peptostreptococcus stomatis", "skeletal_muscle_index")

def _anchor_rows(correct=True):
    # E/R gold-assertable -> ASSERT; P gold not_associated -> ABSTAIN.
    # correct=False flips P to a wrong ASSERT.
    return [
        _row(*_E, "associated_positive", "accepted_edge", "ASSERT"),
        _row(*_R, "associated_negative", "accepted_edge", "ASSERT"),
        _row(*_P, "not_associated", "accepted_edge",
             "ABSTAIN" if correct else "ASSERT"),
    ]

def test_precision_and_coverage_math():
    judged = _anchor_rows() + [
        _row("x", "y", "associated_positive", "accepted_edge", "ASSERT"),
        _row("z", "w", "not_associated", "accepted_edge", "ASSERT"),  # FP
    ]
    rep = compute_report(judged)["accepted_edge"]
    assert rep["n_asserted"] == 4
    assert abs(rep["precision"] - 0.75) < 1e-9   # E,R,x correct of E,R,x,z
    assert abs(rep["coverage"] - 0.8) < 1e-9     # 4 asserted / 5 accepted

def test_pass_when_precision_high_and_anchors_correct():
    judged = _anchor_rows() + [
        _row(f"m{i}", f"f{i}", "associated_positive", "accepted_edge", "ASSERT")
        for i in range(8)]
    rep = compute_report(judged)
    assert rep["verdict"] == "PASS", rep["verdict_reason"]

def test_fail_when_precision_below_target():
    judged = _anchor_rows() + [
        _row(f"b{i}", f"c{i}", "not_associated", "accepted_edge", "ASSERT")
        for i in range(8)]
    rep = compute_report(judged)
    assert rep["verdict"] == "FAIL"
    assert "precision" in rep["verdict_reason"]

def test_fail_when_anchor_decision_wrong():
    judged = _anchor_rows(correct=False) + [
        _row(f"m{i}", f"f{i}", "associated_positive", "accepted_edge", "ASSERT")
        for i in range(8)]
    rep = compute_report(judged)
    assert rep["verdict"] == "FAIL"
    assert "anchor" in rep["verdict_reason"].lower()

def test_load_records_real_schema_keys():
    rows = [
        {"sentence": "s1", "microbe": "eubacterium",
         "candidate_feature_canonical": "visceral_adipose_tissue",
         "label": "associated_positive", "stratum": "accepted_edge"},
        {"sentence": "s2", "microbe": "peptostreptococcus stomatis",
         "candidate_feature_canonical": "skeletal_muscle_index",
         "label": "not_associated", "stratum": "accepted_edge"},
    ]
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    try:
        recs = _load_records(p)
    finally:
        os.unlink(p)
    assert recs[0]["subject"] == "eubacterium"
    assert recs[0]["object"] == "visceral_adipose_tissue"
    assert recs[1]["subject"] == "peptostreptococcus stomatis"
    assert recs[1]["object"] == "skeletal_muscle_index"
    assert recs[1]["label"] == "not_associated"

def test_thesis_anchors_constant():
    # regression guard on the operator-confirmed spec §3 criterion: the
    # peptostrep ABSTAIN was previously inverted (the governance incident).
    assert THESIS_ANCHORS == {
        ("eubacterium", "visceral_adipose_tissue"): "ASSERT",
        ("ruminococcus", "sarcopenia"): "ASSERT",
        ("peptostreptococcus stomatis", "skeletal_muscle_index"): "ABSTAIN",
    }
