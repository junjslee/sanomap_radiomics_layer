# tests/test_pilot_run.py
from src.pilot.run_pilot import compute_report, THESIS_CLOSERS

def _row(subj, obj, label, stratum, decision):
    return ({"subject": subj, "object": obj, "label": label, "stratum": stratum},
            decision)

def test_precision_and_coverage_math():
    judged = [
        _row("Ruminococcus", "sarcopenia", "associated_positive", "accepted_edge", "ASSERT"),
        _row("Peptostreptococcus", "skeletal_muscle_index", "associated_negative", "accepted_edge", "ASSERT"),
        _row("Eubacterium", "visceral_adipose_tissue", "associated_unsigned", "accepted_edge", "ASSERT"),
        _row("X", "y", "not_associated", "accepted_edge", "ASSERT"),   # false positive
        _row("Z", "w", "not_associated", "accepted_edge", "ABSTAIN"),  # correctly held
    ]
    rep = compute_report(judged)
    assert rep["accepted_edge"]["n_asserted"] == 4
    assert abs(rep["accepted_edge"]["precision"] - 0.75) < 1e-9  # 3/4
    assert abs(rep["accepted_edge"]["coverage"] - 0.8) < 1e-9    # 4/5

def test_disconfirmation_pass_when_closers_survive_and_5of8():
    judged = [_row(s, o, "associated_positive", "accepted_edge", "ASSERT")
              for (s, o) in THESIS_CLOSERS] + [
        _row(f"A{i}", f"B{i}", "associated_positive", "accepted_edge", "ASSERT")
        for i in range(2)] + [
        _row(f"C{i}", f"D{i}", "associated_positive", "accepted_edge", "ABSTAIN")
        for i in range(3)]
    rep = compute_report(judged)
    assert rep["verdict"] == "PASS"

def test_disconfirmation_fail_when_a_closer_lost():
    judged = [_row("Ruminococcus", "sarcopenia", "associated_positive", "accepted_edge", "ABSTAIN")] + [
        _row(s, o, "associated_positive", "accepted_edge", "ASSERT")
        for (s, o) in THESIS_CLOSERS[1:]] + [
        _row(f"A{i}", f"B{i}", "associated_positive", "accepted_edge", "ASSERT")
        for i in range(5)]
    rep = compute_report(judged)
    assert rep["verdict"] == "FAIL"
    assert "thesis closer" in rep["verdict_reason"].lower()
