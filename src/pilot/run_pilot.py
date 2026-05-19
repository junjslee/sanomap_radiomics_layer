# src/pilot/run_pilot.py
"""Phase-0 pilot harness. Reads already-labeled artifacts, runs the
cross-family unanimity judge SEQUENTIALLY per model (8 GB constraint:
all model-A, then all model-B — never both resident), computes precision +
coverage on the accepted_edge stratum, and applies the spec §3 crisp
disconfirmation predicates. Emits artifacts/pilot/pilot_report.json.
NO graph writes."""
from __future__ import annotations
import argparse, json, os
from .local_judge import JudgeConfig, judge_unanimous, cross_family

# spec §3: the 3 thesis-load-bearing three-hop closers (subject, object)
THESIS_CLOSERS = [
    ("Ruminococcus", "sarcopenia"),
    ("Peptostreptococcus", "skeletal_muscle_index"),
    ("Eubacterium", "visceral_adipose_tissue"),
]
POSITIVE_LABELS = {"associated_positive", "associated_negative",
                   "associated_unsigned"}

def compute_report(judged: list[tuple[dict, str]]) -> dict:
    acc = [(r, d) for (r, d) in judged if r["stratum"] == "accepted_edge"]
    asserted = [(r, d) for (r, d) in acc if d == "ASSERT"]
    tp = sum(1 for (r, _) in asserted if r["label"] in POSITIVE_LABELS)
    precision = tp / len(asserted) if asserted else 0.0
    coverage = len(asserted) / len(acc) if acc else 0.0

    def survived(subj, obj):
        for (r, d) in judged:
            if r["subject"] == subj and r["object"] == obj:
                return d == "ASSERT"
        return False
    closers_ok = all(survived(s, o) for (s, o) in THESIS_CLOSERS)
    n_accepted_kept = len(asserted)

    if not closers_ok:
        verdict, reason = "FAIL", "lost >=1 thesis closer (spec §3 i)"
    elif n_accepted_kept < 5:
        verdict, reason = "FAIL", f"only {n_accepted_kept}/8 accepted retained (spec §3 ii)"
    else:
        verdict, reason = "PASS", "closers retained and >=5/8 accepted retained"
    return {
        "accepted_edge": {"n_total": len(acc), "n_asserted": len(asserted),
                          "precision": precision, "coverage": coverage,
                          "true_positives": tp},
        "thesis_closers_survived": closers_ok,
        "verdict": verdict, "verdict_reason": reason,
    }

def _load_records(gold_path: str, accepted_path: str) -> list[dict]:
    recs: list[dict] = []
    with open(gold_path) as f:
        for line in f:
            o = json.loads(line)
            recs.append({"sentence": o.get("sentence", ""),
                         "subject": o.get("microbe") or o.get("subject", ""),
                         "object": o.get("feature") or o.get("object", ""),
                         "label": o.get("label", "not_associated"),
                         "stratum": o.get("stratum", "unknown")})
    return recs

def run(gold_path: str, accepted_path: str, model_a: str, model_b: str,
        out_path: str) -> dict:
    from openai import OpenAI
    recs = _load_records(gold_path, accepted_path)
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
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
    ap.add_argument("--gold", default="artifacts/gold_set_v1_LABELED_pass1.jsonl")
    ap.add_argument("--accepted", default="artifacts/microbe_feature_relations.jsonl")
    ap.add_argument("--model-a", default="medgemma-1.5-4b-it")
    ap.add_argument("--model-b", default="qwen3:4b")
    ap.add_argument("--out", default="artifacts/pilot/pilot_report.json")
    a = ap.parse_args()
    rep = run(a.gold, a.accepted, a.model_a, a.model_b, a.out)
    print(json.dumps(rep, indent=2))
    return 0 if rep["verdict"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
