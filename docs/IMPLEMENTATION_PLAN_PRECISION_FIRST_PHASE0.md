# Phase 0 — Local Cross-Family Unanimity Pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure whether a local-only, no-API, Q8, sequential cross-family unanimity judge (MedGemma × Qwen) can reach the spec's precision/coverage bar on the *already-labeled* data — the go/no-go before any B–G investment.

**Architecture:** Three focused modules — a locked judge schema (`schema.py`), an Ollama-backed N-sample-unanimity + cross-family judge (`local_judge.py`), and an evaluation/verdict runner (`run_pilot.py`) — plus a one-shot environment-feasibility probe. No graph writes, no production-path edits: the pilot only reads existing labeled artifacts and emits a report. It is the seed of spec units B2/C with the model backend already config-swappable (spec unit G requirement, designed-in from day one).

**Tech Stack:** Python (Conda `base` at `/Users/junlee/miniconda3`), pytest, Ollama (OpenAI-compatible endpoint at `http://localhost:11434/v1`, the pattern already used by the vision track), JSONL artifacts. No paid API. No new heavy deps.

**Governance:** This plan implements only DESIGN_PRECISION_FIRST_V1.md §3 (pilot gate) + the §2C judge seed. It does **not** write graph edges and does **not** modify relation/entity/edge-assembly production code, so it is outside the CLAUDE.md "review required before merge" class — but its graduation to production (post-pilot B/C) is review-gated. Commits: Conventional Commits, **no AI-attribution trailer** (AGENTS.md + operator global rule).

---

## File Structure (decomposition locked here)

- Create `src/pilot/__init__.py` — package marker (empty).
- Create `src/pilot/schema.py` — the locked judge verdict contract + validator. One responsibility: the I/O contract and the evidence-span-exists precision-safety guard (spec §6).
- Create `src/pilot/local_judge.py` — Ollama-backed judge: one-sample call → N-sample per-model unanimity → cross-family agreement. Config-driven `model_id` (spec G swappable backend). One responsibility: turn a (sentence, subject, object) record into a final ASSERT/ABSTAIN verdict.
- Create `src/pilot/run_pilot.py` — load already-labeled artifacts, run the judge sequentially per model, compute precision/coverage + the spec §3 disconfirmation predicates, emit `artifacts/pilot/pilot_report.json` with a PASS/FAIL verdict. One responsibility: eval harness + verdict.
- Create `scripts/pilot_env_check.py` — one-shot Step-0 feasibility probe (model availability, JSON+ABSTAIN fidelity, peak RSS within 8 GB). One responsibility: cheapest disconfirmation, run first.
- Create tests: `tests/test_pilot_schema.py`, `tests/test_pilot_local_judge.py`, `tests/test_pilot_run.py`.

Test command everywhere: `conda run -n base python -m pytest <path> -v`. Full-suite regression check: `conda run -n base python -m pytest -q` (must stay green; baseline 321 passed).

---

### Task 1: Environment feasibility probe (cheapest disconfirmation — run first)

**Files:**
- Create: `scripts/pilot_env_check.py`

This is an ops probe, not a pure function; its "test" is its own explicit success assertions. It is Task 1 because if no MedGemma variant runs in 8 GB at Q8 with JSON fidelity, the entire local-only premise fails and the operator must be escalated (MGH-compute path) before any code is written.

- [ ] **Step 1: Write the probe script**

```python
# scripts/pilot_env_check.py
"""Phase-0 Step-0 feasibility probe. Read-only; no graph writes.
Verifies a MedGemma variant + a Qwen variant are reachable via local Ollama,
honor a strict JSON+ABSTAIN reply, and stay within the 8 GB budget.
Exits non-zero (and prints REASON) on any failure."""
from __future__ import annotations
import json, os, resource, sys, urllib.request

BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
# Candidate tags in preference order. The probe DISCOVERS which exist; it does
# not assume. Operator may extend this list.
MEDGEMMA_CANDIDATES = ["medgemma-1.5-4b-it", "medgemma:4b", "medgemma-4b-it"]
QWEN_CANDIDATES = ["qwen3:4b", "qwen2.5:3b-instruct", "qwen2.5:3b"]

PROMPT = (
    'Return ONLY JSON. Schema: {"decision":"ASSERT"|"ABSTAIN",'
    '"relation_type":string|null,"evidence_quote":string|null}. '
    'Sentence: "Akkermansia muciniphila was inversely associated with hepatic steatosis." '
    'Is there a microbe<->feature/disease relation? If unsure, ABSTAIN.'
)

def _tags() -> list[str]:
    with urllib.request.urlopen(f"{BASE}/api/tags", timeout=10) as r:
        return [m["name"] for m in json.load(r).get("models", [])]

def _chat(model: str) -> str:
    body = json.dumps({"model": model, "stream": False,
                        "messages": [{"role": "user", "content": PROMPT}],
                        "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{BASE}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["message"]["content"]

def _pick(cands: list[str], have: list[str]) -> str | None:
    for c in cands:
        matched = next((h for h in have if h == c or h.startswith(c)), None)
        if matched:
            return matched
    return None

def main() -> int:
    try:
        have = _tags()
    except Exception as e:
        print(f"FAIL: Ollama not reachable at {BASE}: {e}"); return 2
    med = _pick(MEDGEMMA_CANDIDATES, have)
    qwen = _pick(QWEN_CANDIDATES, have)
    if not med:
        print(f"FAIL: no MedGemma candidate present. `ollama pull` one of "
              f"{MEDGEMMA_CANDIDATES}. Have: {have}"); return 3
    if not qwen:
        print(f"FAIL: no Qwen candidate present. `ollama pull` one of "
              f"{QWEN_CANDIDATES}. Have: {have}"); return 3
    ok = True
    for label, model in (("medgemma", med), ("qwen", qwen)):
        try:
            raw = _chat(model)
            obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            if obj.get("decision") not in ("ASSERT", "ABSTAIN"):
                raise ValueError(f"unexpected decision value: {obj}")
            print(f"PASS {label} [{model}] -> decision={obj['decision']}")
        except Exception as e:
            print(f"FAIL {label} [{model}] bad JSON/schema: {e}"); ok = False
    divisor = 1024**3 if sys.platform == "darwin" else 1024**2
    rss_gb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / divisor
    print(f"INFO probe peak child RSS ~ {rss_gb:.2f} GB (Ollama server RSS is separate; "
          f"check `ollama ps` for model resident size — must fit 8 GB).")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 4

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Ensure models are present, then run the probe**

Run:
```bash
ollama pull medgemma-1.5-4b-it || ollama pull medgemma:4b
ollama pull qwen3:4b || ollama pull qwen2.5:3b-instruct
ollama ps   # confirm resident size fits 8 GB
conda run -n base python scripts/pilot_env_check.py
```
Expected: final line `RESULT: PASS`, two `PASS` model lines, and `ollama ps` showing the model resident size within budget.
**Decision rule (gate):** if `RESULT: FAIL` for MedGemma specifically after trying all candidate tags → STOP the pilot and escalate to the operator: the no-API + 8 GB premise is not satisfiable locally; the MGH-compute path (spec G makes this a rerun) must be decided before proceeding. Record the probe output verbatim in the escalation.

- [ ] **Step 3: Commit**

```bash
git add scripts/pilot_env_check.py
git commit -m "feat(pilot): add Phase-0 environment feasibility probe"
```

---

### Task 2: Judge verdict schema + evidence-span guard

**Files:**
- Create: `src/pilot/__init__.py`
- Create: `src/pilot/schema.py`
- Test: `tests/test_pilot_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pilot_schema.py
import pytest
from src.pilot.schema import validate_verdict, SchemaError

SENT = "Ruminococcus was positively associated with sarcopenia in cirrhotic patients."

def test_valid_assert_parses():
    v = validate_verdict({
        "decision": "ASSERT", "relation_type": "ASSOCIATED_WITH",
        "sign": "positive", "evidence_quote": "Ruminococcus was positively associated with sarcopenia",
        "confidence": 0.9}, source_sentence=SENT)
    assert v.decision == "ASSERT" and v.sign == "positive"

def test_abstain_minimal_ok():
    v = validate_verdict({"decision": "ABSTAIN", "relation_type": None,
                          "sign": None, "evidence_quote": None, "confidence": 0.0},
                         source_sentence=SENT)
    assert v.decision == "ABSTAIN"

def test_missing_field_raises():
    with pytest.raises(SchemaError):
        validate_verdict({"decision": "ASSERT"}, source_sentence=SENT)

def test_assert_with_quote_not_in_sentence_raises():
    # precision-safety guard (spec §6): evidence must exist in the source
    with pytest.raises(SchemaError):
        validate_verdict({"decision": "ASSERT", "relation_type": "ASSOCIATED_WITH",
                          "sign": "positive", "evidence_quote": "fabricated text not present",
                          "confidence": 0.8}, source_sentence=SENT)

def test_bad_relation_type_raises():
    with pytest.raises(SchemaError):
        validate_verdict({"decision": "ASSERT", "relation_type": "CAUSES",
                          "sign": "positive", "evidence_quote": "Ruminococcus was positively associated with sarcopenia",
                          "confidence": 0.8}, source_sentence=SENT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n base python -m pytest tests/test_pilot_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pilot.schema'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/pilot/__init__.py
```
```python
# src/pilot/schema.py
"""Locked judge verdict contract. Relation vocabulary is the CLAUDE.md
locked set; ABSTAIN is fail-closed. The evidence-span-exists check is the
only deterministic precision-safety guard in the judge path (spec §6)."""
from __future__ import annotations
from dataclasses import dataclass

class SchemaError(ValueError):
    pass

ALLOWED_RELATIONS = {
    "ASSOCIATED_WITH", "CORRELATES_WITH",
    "POSITIVELY_CORRELATED_WITH", "NEGATIVELY_CORRELATED_WITH",
}
ALLOWED_SIGN = {"positive", "negative", "unsigned", None}

@dataclass(frozen=True)
class Verdict:
    decision: str            # "ASSERT" | "ABSTAIN"
    relation_type: str | None
    sign: str | None
    evidence_quote: str | None
    confidence: float

def _norm(s: str) -> str:
    return " ".join(s.lower().split())

def validate_verdict(obj: object, *, source_sentence: str) -> Verdict:
    if not isinstance(obj, dict):
        raise SchemaError(f"verdict not an object: {type(obj)}")
    for k in ("decision", "relation_type", "sign", "evidence_quote", "confidence"):
        if k not in obj:
            raise SchemaError(f"missing field: {k}")
    d = obj["decision"]
    if d not in ("ASSERT", "ABSTAIN"):
        raise SchemaError(f"bad decision: {d!r}")
    if d == "ABSTAIN":
        return Verdict("ABSTAIN", None, None, None, float(obj.get("confidence") or 0.0))
    if obj["relation_type"] not in ALLOWED_RELATIONS:
        raise SchemaError(f"bad relation_type: {obj['relation_type']!r}")
    if obj["sign"] not in ALLOWED_SIGN:
        raise SchemaError(f"bad sign: {obj['sign']!r}")
    q = obj["evidence_quote"]
    if not q or not isinstance(q, str):
        raise SchemaError("ASSERT requires non-empty evidence_quote")
    if _norm(q) not in _norm(source_sentence):
        raise SchemaError("evidence_quote not a span of source sentence")
    return Verdict("ASSERT", obj["relation_type"], obj["sign"], q,
                   float(obj["confidence"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n base python -m pytest tests/test_pilot_schema.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pilot/__init__.py src/pilot/schema.py tests/test_pilot_schema.py
git commit -m "feat(pilot): locked judge verdict schema with evidence-span guard"
```

---

### Task 3: N-sample per-model unanimity + cross-family agreement

**Files:**
- Create: `src/pilot/local_judge.py`
- Test: `tests/test_pilot_local_judge.py`

- [ ] **Step 1: Write the failing test** (mocked OpenAI-compatible client — same mocking pattern as `tests/test_verify_vision_dual.py`)

```python
# tests/test_pilot_local_judge.py
from unittest.mock import MagicMock
from src.pilot.local_judge import JudgeConfig, judge_unanimous, cross_family
from src.pilot.schema import Verdict

SENT = "Eubacterium correlated with visceral adipose tissue on CT."
REC = {"sentence": SENT, "subject": "Eubacterium", "object": "visceral adipose tissue"}

def _client(payloads):
    c = MagicMock()
    c.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=p))]) for p in payloads
    ]
    return c

ASSERT = ('{"decision":"ASSERT","relation_type":"CORRELATES_WITH","sign":"positive",'
          '"evidence_quote":"Eubacterium correlated with visceral adipose tissue","confidence":0.9}')
OTHER  = ('{"decision":"ASSERT","relation_type":"CORRELATES_WITH","sign":"negative",'
          '"evidence_quote":"Eubacterium correlated with visceral adipose tissue","confidence":0.9}')
ABSTAIN = '{"decision":"ABSTAIN","relation_type":null,"sign":null,"evidence_quote":null,"confidence":0.0}'

def test_unanimous_assert():
    cfg = JudgeConfig(model_id="m", n_samples=5)
    v = judge_unanimous(_client([ASSERT]*5), cfg, REC)
    assert v.decision == "ASSERT" and v.sign == "positive"

def test_one_dissent_breaks_unanimity():
    cfg = JudgeConfig(model_id="m", n_samples=5)
    v = judge_unanimous(_client([ASSERT]*4 + [OTHER]), cfg, REC)
    assert v.decision == "ABSTAIN"

def test_parse_failure_is_fail_closed_abstain():
    cfg = JudgeConfig(model_id="m", n_samples=3)
    v = judge_unanimous(_client(["not json", ASSERT, ASSERT]), cfg, REC)
    assert v.decision == "ABSTAIN"

def test_cross_family_agreement():
    a = Verdict("ASSERT", "CORRELATES_WITH", "positive", "x", 0.9)
    b = Verdict("ASSERT", "CORRELATES_WITH", "positive", "y", 0.8)
    assert cross_family(a, b).decision == "ASSERT"

def test_cross_family_disagreement_abstains():
    a = Verdict("ASSERT", "CORRELATES_WITH", "positive", "x", 0.9)
    b = Verdict("ASSERT", "CORRELATES_WITH", "negative", "y", 0.8)
    assert cross_family(a, b).decision == "ABSTAIN"

def test_one_sample_fail_closed_on_transport_error():
    # Task 5a regression guard: any exception from the client (e.g. transport
    # timeout, connection error) must degrade to ABSTAIN, never raise. The
    # narrow except tuple {SchemaError,ValueError,KeyError,IndexError} crashed
    # a 95-min run on openai.APITimeoutError; the boundary is now broad.
    c = MagicMock()
    c.chat.completions.create.side_effect = RuntimeError("simulated transport timeout")
    cfg = JudgeConfig(model_id="m", n_samples=3)
    v = judge_unanimous(c, cfg, REC)
    assert v.decision == "ABSTAIN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n base python -m pytest tests/test_pilot_local_judge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pilot.local_judge'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/pilot/local_judge.py
"""Local cross-family unanimity judge (spec §2C seed).
MINERVA-faithful: unanimous-N per model, discard on any disagreement.
SanoMap substitute for fine-tuning: two independent families must also agree.
Model backend is config-driven (spec G: MGH-compute upgrade = rerun)."""
from __future__ import annotations
from dataclasses import dataclass
import logging
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
    except Exception as e:  # noqa: BLE001 — fail-closed boundary, see docstring
        logging.warning("_one_sample: exception -> ABSTAIN: %s: %s",
                        type(e).__name__, e)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n base python -m pytest tests/test_pilot_local_judge.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pilot/local_judge.py tests/test_pilot_local_judge.py
git commit -m "feat(pilot): N-sample unanimity + cross-family agreement judge"
```

---

### Task 4: Pilot runner — metrics + spec §3 disconfirmation verdict

**Files:**
- Create: `src/pilot/run_pilot.py`
- Test: `tests/test_pilot_run.py`

- [ ] **Step 1: Write the failing test**

```python
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

def test_checkpoint_roundtrip_and_resume_skip(tmp_path):
    # Task 5a regression guard: _load_checkpoint round-trips per-record
    # decisions; _judge_all skips records already in the checkpoint without
    # invoking the client; new judgements are appended with flush.
    from unittest.mock import MagicMock
    from src.pilot.run_pilot import _load_checkpoint, _judge_all
    from src.pilot.schema import Verdict
    ckpt = tmp_path / "ck.jsonl"
    with open(ckpt, "w") as f:
        f.write(json.dumps({
            "idx": 0, "model": "m",
            "decision": "ASSERT", "relation_type": "CORRELATES_WITH",
            "sign": "positive", "evidence_quote": "q", "confidence": 0.9,
        }) + "\n")
    done = _load_checkpoint(str(ckpt))
    assert (0, "m") in done and done[(0, "m")].decision == "ASSERT"
    assert isinstance(done[(0, "m")], Verdict)  # type contract of _load_checkpoint
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(choices=[
        MagicMock(message=MagicMock(content=(
            '{"decision":"ABSTAIN","relation_type":null,"sign":null,'
            '"evidence_quote":null,"confidence":0.0}')))])
    recs = [
        {"sentence": "s0", "subject": "a", "object": "b",
         "label": "associated_positive", "stratum": "accepted_edge"},
        {"sentence": "s1", "subject": "c", "object": "d",
         "label": "not_associated", "stratum": "accepted_edge"},
    ]
    out = _judge_all(client, "m", recs, done, str(ckpt))
    assert len(out) == 2
    assert out[0].decision == "ASSERT"      # from checkpoint, no client call
    assert out[1].decision == "ABSTAIN"     # judged via client
    assert client.chat.completions.create.call_count == 5  # n_samples=5 default
    lines = open(ckpt).read().strip().split("\n")
    assert len(lines) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n base python -m pytest tests/test_pilot_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pilot.run_pilot'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/pilot/run_pilot.py
"""Phase-0 pilot harness. Reads the already-labeled gold set, runs the
cross-family unanimity judge SEQUENTIALLY per model (8 GB constraint:
all model-A, then all model-B — never both resident), and applies the
estimand-aligned spec §3 disconfirmation: judge-vs-gold precision on the
accepted_edge stratum plus the three gold-anchored thesis decisions.
Emits artifacts/pilot/pilot_report.json. NO graph writes.

Resilience (Task 5a): per-record checkpoint JSONL + resume-skip so a
crash or interrupt is recoverable; explicit per-request client timeout
so a wedged generation fails fast (caught by local_judge's fail-closed
boundary → ABSTAIN) instead of hanging."""
from __future__ import annotations
import argparse, json, os
from .local_judge import JudgeConfig, judge_unanimous, cross_family
from .schema import Verdict

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
DEFAULT_TIMEOUT = 120.0   # per-request OpenAI client timeout (seconds)

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

def _load_checkpoint(path: str) -> dict[tuple[int, str], Verdict]:
    """Load per-(record_idx, model_id) verdicts from a JSONL checkpoint."""
    done: dict[tuple[int, str], Verdict] = {}
    if not os.path.exists(path):
        return done
    with open(path) as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip a partially-written trailing line (crash mid-write)
            done[(o["idx"], o["model"])] = Verdict(
                o["decision"], o["relation_type"], o["sign"],
                o["evidence_quote"], o["confidence"])
    return done

def _judge_all(client, model_id: str, recs: list[dict],
               done: dict[tuple[int, str], Verdict],
               ckpt_path: str) -> list[Verdict]:
    """Judge all records with one model. Resume-skip from `done`; append each
    fresh verdict to the checkpoint JSONL with flush so a crash loses nothing."""
    cfg = JudgeConfig(model_id=model_id)
    out: list[Verdict] = []
    with open(ckpt_path, "a") as ck:
        for i, r in enumerate(recs):
            key = (i, model_id)
            if key in done:
                out.append(done[key])
                continue
            v = judge_unanimous(client, cfg, r)
            ck.write(json.dumps({
                "idx": i, "model": model_id,
                "decision": v.decision, "relation_type": v.relation_type,
                "sign": v.sign, "evidence_quote": v.evidence_quote,
                "confidence": v.confidence,
            }) + "\n")
            ck.flush()
            out.append(v)
    return out

def run(gold_path: str, model_a: str, model_b: str, out_path: str,
        checkpoint_path: str | None = None,
        request_timeout: float = DEFAULT_TIMEOUT,
        fresh: bool = False) -> dict:
    from openai import OpenAI
    recs = _load_records(gold_path)
    ckpt = checkpoint_path or os.path.join(
        os.path.dirname(out_path) or ".", "pilot_checkpoint.jsonl")
    os.makedirs(os.path.dirname(ckpt) or ".", exist_ok=True)
    done = _load_checkpoint(ckpt)
    if fresh:
        done = {}  # --fresh: ignore prior checkpoint; file left on disk
    client = OpenAI(base_url="http://localhost:11434/v1",
                    api_key="ollama", timeout=request_timeout)
    # SEQUENTIAL: all model-A first, then all model-B (8 GB: never both resident)
    va = _judge_all(client, model_a, recs, done, ckpt)
    vb = _judge_all(client, model_b, recs, done, ckpt)
    judged = [(recs[i], cross_family(va[i], vb[i]).decision)
              for i in range(len(recs))]
    report = compute_report(judged)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
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
    ap.add_argument("--checkpoint", default=None,
                    help="per-record checkpoint JSONL (resume-skip); "
                         "defaults to <out-dir>/pilot_checkpoint.jsonl")
    ap.add_argument("--request-timeout", type=float, default=DEFAULT_TIMEOUT,
                    help="per-request OpenAI client timeout in seconds")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore any existing checkpoint and start fresh "
                         "(prior checkpoint file is left on disk untouched)")
    a = ap.parse_args()
    rep = run(a.gold, a.model_a, a.model_b, a.out,
              checkpoint_path=a.checkpoint, request_timeout=a.request_timeout,
              fresh=a.fresh)
    print(json.dumps(rep, indent=2))
    return 0 if rep["verdict"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n base python -m pytest tests/test_pilot_run.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pilot/run_pilot.py tests/test_pilot_run.py
git commit -m "feat(pilot): runner with spec §3 disconfirmation verdict"
```

---

### Task 5: Full-suite regression + live pilot run + verdict handoff

**Files:** none created (verification + execution task).

- [ ] **Step 1: Regression — full suite stays green**

Run: `conda run -n base python -m pytest -q`
Expected: previous baseline (321 passed) + the 13 new pilot tests, 0 failed. If any prior test regressed, STOP and fix before the live run.

- [ ] **Step 2: Live pilot run on already-labeled data**

Run (after Task 1 `RESULT: PASS`; use the exact model tags Task 1 discovered):
```bash
conda run -n base python -m src.pilot.run_pilot \
  --model-a <medgemma-tag-from-task1> --model-b <qwen-tag-from-task1>
```
Expected: `artifacts/pilot/pilot_report.json` written; stdout shows `accepted_edge` precision/coverage and `verdict`.

- [ ] **Step 3: Record the verdict (no auto-progression)**

This is a **human gate**, not an automated branch. Capture `pilot_report.json` and present it. Decision rule (spec §3):
- `verdict == "PASS"` → the local-only approach is validated; the B–G implementation plan may be written, parameterized by the *measured* precision/coverage.
- `verdict == "FAIL"` → do **not** build B–G. Trigger the spec §3 fallback ladder (raise N/abstention; defer to MGH compute as a rerun; or consciously scope the graph smaller) — operator decision.

Do not commit `artifacts/pilot/` (it is gitignored like all of `artifacts/`); reference the report inline in the handoff.

- [ ] **Step 4: Commit the plan-completion marker**

```bash
git add docs/IMPLEMENTATION_PLAN_PRECISION_FIRST_PHASE0.md
git commit -m "docs(pilot): Phase-0 plan executed; verdict recorded in handoff"
```

---

## Self-Review

**1. Spec coverage (DESIGN_PRECISION_FIRST_V1.md):** §3 Step-0 → Task 1. §3 Step-1 + crisp disconfirmation (3 closers / ≥5-of-8) → Task 4 `compute_report` + Task 5 Step 3. §2C unanimous-N + cross-family + independent evidence re-location → Task 3 + the `build_prompt` "independently quote" instruction. §4 fail-closed ABSTAIN-on-parse-failure → `_one_sample` except-clause + `test_parse_failure_is_fail_closed_abstain`. §6 evidence-span-exists guard → `schema.py` + `test_assert_with_quote_not_in_sentence_raises`. §2G config-swappable backend → `JudgeConfig.model_id` + `--model-a/-b`. Out of Phase-0 scope by design: B1 retrieval, D calibration, E power-sized sample, F concordance, G hardening — explicitly deferred until a PASS verdict (documented in plan header + Task 5 Step 3).

**2. Placeholder scan:** No "TBD/TODO". The `<medgemma-tag-from-task1>` / `<qwen-tag-from-task1>` in Task 5 Step 2 are not placeholders — they are explicit references to the concrete tags Task 1's probe *discovers and records* (genuine environment uncertainty handled by a real discovery step + decision rule, per the no-fabrication principle), not unspecified work.

**3. Type consistency:** `Verdict` (decision, relation_type, sign, evidence_quote, confidence) is defined once in `schema.py` and consumed unchanged in `local_judge.py` and tests. `judge_unanimous`/`cross_family` signatures match their test call sites. `compute_report` consumes `(record, decision_str)` tuples consistently across `run()` and all `test_pilot_run.py` cases. `THESIS_CLOSERS` defined once, imported by tests. `JudgeConfig.model_id` is the single backend knob across judge + runner.

No issues found requiring further edits.
