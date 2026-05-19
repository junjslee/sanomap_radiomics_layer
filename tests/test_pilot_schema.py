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
