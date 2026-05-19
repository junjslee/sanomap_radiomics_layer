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
