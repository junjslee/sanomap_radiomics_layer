# src/pilot/run_pilot.py
"""Phase-0 pilot harness. Reads the already-labeled gold set, runs the
cross-family unanimity judge SEQUENTIALLY per model (8 GB constraint:
all model-A, then all model-B — never both resident), and applies the
estimand-aligned spec §3 disconfirmation: judge-vs-gold precision on the
accepted_edge stratum plus the three gold-anchored thesis decisions.
Emits artifacts/pilot/pilot_report.json. NO graph writes."""
from __future__ import annotations
import argparse, json, os
from .local_judge import JudgeConfig, judge_unanimous, cross_family

# spec §3 gold label classes
GOLD_ASSERTABLE = {"associated_positive", "associated_negative",
                   "associated_unsigned"}
GOLD_NONASSERT = {"not_associated", "unclear", "no_association_explicit"}

# spec §3 anchors: (microbe, feature_canonical) -> required judge decision,
# taken from the human Pass-1 GOLD label (not graph structure):
#   eubacterium/visceral_adipose_tissue          assoc_positive -> ASSERT
#   ruminococcus/sarcopenia                      assoc_negative -> ASSERT
#   peptostreptococcus stomatis/skeletal_muscle_index  not_associated -> ABSTAIN
THESIS_ANCHORS = {
    ("eubacterium", "visceral_adipose_tissue"): "ASSERT",
    ("ruminococcus", "sarcopenia"): "ASSERT",
    ("peptostreptococcus stomatis", "skeletal_muscle_index"): "ABSTAIN",
}
TARGET_PRECISION = 0.90  # spec §2D default

def compute_report(judged: list[tuple[dict, str]]) -> dict:
    acc = [(r, d) for (r, d) in judged if r["stratum"] == "accepted_edge"]
    asserted = [(r, d) for (r, d) in acc if d == "ASSERT"]
    correct_assert = sum(1 for (r, _) in asserted
                         if r["label"] in GOLD_ASSERTABLE)
    precision = correct_assert / len(asserted) if asserted else 0.0
    coverage = len(asserted) / len(acc) if acc else 0.0
    correct = correct_assert + sum(
        1 for (r, d) in acc if d == "ABSTAIN" and r["label"] in GOLD_NONASSERT)
    accuracy = correct / len(acc) if acc else 0.0

    def decision_for(subj, obj):
        for (r, d) in acc:
            if r["subject"] == subj and r["object"] == obj:
                return d
        return None
    anchors = {}
    anchors_ok = True
    for (subj, obj), expected in THESIS_ANCHORS.items():
        got = decision_for(subj, obj)
        ok = got == expected
        anchors_ok = anchors_ok and ok
        anchors[f"{subj} -> {obj}"] = {"expected": expected, "got": got,
                                       "ok": ok}

    if not asserted:
        verdict, reason = "FAIL", "judge asserted nothing (vacuous precision)"
    elif precision < TARGET_PRECISION:
        verdict = "FAIL"
        reason = f"precision {precision:.3f} < target {TARGET_PRECISION} (spec §3)"
    elif not anchors_ok:
        bad = [k for k, v in anchors.items() if not v["ok"]]
        verdict, reason = "FAIL", f"thesis anchor(s) wrong decision: {bad}"
    else:
        verdict = "PASS"
        reason = (f"precision {precision:.3f} >= {TARGET_PRECISION} and all "
                  f"3 gold-anchored thesis decisions correct")
    return {
        "accepted_edge": {"n_total": len(acc), "n_asserted": len(asserted),
                          "precision": precision, "coverage": coverage,
                          "accuracy": accuracy,
                          "correct_assert": correct_assert},
        "thesis_anchors": anchors,
        "verdict": verdict, "verdict_reason": reason,
    }

def _load_records(gold_path: str) -> list[dict]:
    recs: list[dict] = []
    with open(gold_path) as f:
        for line in f:
            o = json.loads(line)
            recs.append({
                "sentence": o.get("sentence", ""),
                "subject": o.get("microbe", ""),
                "object": o.get("candidate_feature_canonical", ""),
                "label": o.get("label", "not_associated"),
                "stratum": o.get("stratum", "unknown"),
            })
    return recs

def run(gold_path: str, model_a: str, model_b: str, out_path: str) -> dict:
    from openai import OpenAI
    recs = _load_records(gold_path)
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    # SEQUENTIAL: all model-A first, then all model-B (8 GB: never both resident)
    cfg_a = JudgeConfig(model_id=model_a)
    va = [judge_unanimous(client, cfg_a, r) for r in recs]
    cfg_b = JudgeConfig(model_id=model_b)
    vb = [judge_unanimous(client, cfg_b, r) for r in recs]
    judged = [(recs[i], cross_family(va[i], vb[i]).decision)
              for i in range(len(recs))]
    report = compute_report(judged)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    return report

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold",
                    default="artifacts/gold_set_v1_LABELED_pass1.jsonl")
    ap.add_argument("--model-a", default="medgemma:4b")
    ap.add_argument("--model-b", default="qwen3:4b")
    ap.add_argument("--out", default="artifacts/pilot/pilot_report.json")
    a = ap.parse_args()
    rep = run(a.gold, a.model_a, a.model_b, a.out)
    print(json.dumps(rep, indent=2))
    return 0 if rep["verdict"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
