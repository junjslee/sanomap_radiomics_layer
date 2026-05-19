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

def validate_verdict(obj: dict, *, source_sentence: str) -> Verdict:
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
