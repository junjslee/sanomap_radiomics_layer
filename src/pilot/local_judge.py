# src/pilot/local_judge.py
"""Local cross-family unanimity judge (spec §2C seed).
MINERVA-faithful: unanimous-N per model, discard on any disagreement.
SanoMap substitute for fine-tuning: two independent families must also agree.
Model backend is config-driven (spec G: MGH-compute upgrade = rerun)."""
from __future__ import annotations
from dataclasses import dataclass
from .schema import Verdict, validate_verdict

@dataclass(frozen=True)
class JudgeConfig:
    model_id: str
    base_url: str = "http://localhost:11434/v1"
    n_samples: int = 5
    temperature: float = 0.0

_ABSTAIN = Verdict("ABSTAIN", None, None, None, 0.0)

def build_prompt(rec: dict) -> str:
    return (
        "You are a careful biomedical relation verifier. Decide ONLY from the "
        "sentence whether the stated subject and object have a direct relation.\n"
        f'Sentence: "{rec["sentence"]}"\n'
        f'Subject: {rec["subject"]}\nObject: {rec["object"]}\n'
        "Independently quote the exact span of THIS sentence that licenses the "
        "relation (do not invent text). If the sentence does not directly state "
        "it, decision MUST be ABSTAIN.\n"
        'Return ONLY JSON: {"decision":"ASSERT"|"ABSTAIN",'
        '"relation_type":"ASSOCIATED_WITH"|"CORRELATES_WITH"|'
        '"POSITIVELY_CORRELATED_WITH"|"NEGATIVELY_CORRELATED_WITH"|null,'
        '"sign":"positive"|"negative"|"unsigned"|null,'
        '"evidence_quote":string|null,"confidence":number}'
    )

def _extract_json(text: str) -> dict:
    import json
    i, j = text.index("{"), text.rindex("}")
    return json.loads(text[i:j + 1])

def _one_sample(client, cfg: JudgeConfig, rec: dict) -> Verdict:
    # Fail-closed boundary (Task 5a): this function's contract is
    # "return a schema-valid Verdict or ABSTAIN; never raise." ANY failure
    # (parse error, schema violation, transport/timeout, client error, etc.)
    # degrades to ABSTAIN — a precision-first judge treats an unobtainable
    # judgement as "no assertable association." Broad `except Exception` is
    # deliberate: the narrow tuple {SchemaError, ValueError, KeyError,
    # IndexError} crashed a 95-min run on openai.APITimeoutError (2026-05-19).
    # KeyboardInterrupt/SystemExit (BaseException) still escape so the run
    # remains user-interruptible. (Spec §4: fail-closed = precision-safe.)
    try:
        resp = client.chat.completions.create(
            model=cfg.model_id, temperature=cfg.temperature,
            messages=[{"role": "user", "content": build_prompt(rec)}])
        raw = resp.choices[0].message.content
        return validate_verdict(_extract_json(raw), source_sentence=rec["sentence"])
    except Exception:
        return _ABSTAIN

def judge_unanimous(client, cfg: JudgeConfig, rec: dict) -> Verdict:
    samples = [_one_sample(client, cfg, rec) for _ in range(cfg.n_samples)]
    if any(s.decision == "ABSTAIN" for s in samples):
        return _ABSTAIN
    keys = {(s.relation_type, s.sign) for s in samples}
    if len(keys) != 1:
        return _ABSTAIN
    return samples[0]

def cross_family(a: Verdict, b: Verdict) -> Verdict:
    if a.decision == "ASSERT" and b.decision == "ASSERT" \
       and (a.relation_type, a.sign) == (b.relation_type, b.sign):
        return Verdict("ASSERT", a.relation_type, a.sign, a.evidence_quote,
                       min(a.confidence, b.confidence))
    return _ABSTAIN
