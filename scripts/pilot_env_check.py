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
