import unittest

from src.model_backends import BaseRelationBackend, NEGATIVE, POSITIVE, UNRELATED
from src.relation_fidelity import (
    aggregate_within_paper,
    compute_strength_scores,
    self_consistency_predict,
)


class SequenceBackend(BaseRelationBackend):
    def __init__(self, sequence):
        self.sequence = sequence
        self.idx = 0

    def predict_relation(self, *, sentence, microbe, disease, temperature=0.7, max_new_tokens=16):
        _ = sentence, microbe, disease, temperature, max_new_tokens
        label = self.sequence[self.idx]
        self.idx += 1
        return label


class TestRelationFidelity(unittest.TestCase):
    def test_self_consistency_strict_rejects_mixed_votes(self) -> None:
        backend = SequenceBackend([POSITIVE, POSITIVE, NEGATIVE])
        out = self_consistency_predict(
            backend=backend,
            sentence="x",
            microbe="m",
            disease="d",
            temperatures=[0.4, 0.6, 0.8],
            require_complete_consistency=True,
        )
        self.assertEqual(out.final_label, UNRELATED)
        self.assertFalse(out.accepted)

    def test_self_consistency_majority_allowed(self) -> None:
        backend = SequenceBackend([POSITIVE, POSITIVE, NEGATIVE])
        out = self_consistency_predict(
            backend=backend,
            sentence="x",
            microbe="m",
            disease="d",
            temperatures=[0.4, 0.6, 0.8],
            require_complete_consistency=False,
        )
        self.assertEqual(out.final_label, POSITIVE)
        self.assertTrue(out.accepted)

    def test_within_paper_majority(self) -> None:
        rows = [
            {"pmid": "1", "microbe": "a", "disease": "b", "final_label": POSITIVE, "sentence": "s1"},
            {"pmid": "1", "microbe": "a", "disease": "b", "final_label": POSITIVE, "sentence": "s2"},
            {"pmid": "1", "microbe": "a", "disease": "b", "final_label": NEGATIVE, "sentence": "s3"},
        ]
        agg = aggregate_within_paper(rows)
        self.assertEqual(len(agg), 1)
        self.assertEqual(agg[0]["final_label"], POSITIVE)
        self.assertTrue(agg[0]["accepted"])

    def test_strength_scores(self) -> None:
        aggregated = [
            {
                "microbe": "a",
                "disease": "b",
                "accepted": True,
                "final_label": POSITIVE,
                "impact_factor": 10.0,
                "quartile": "Q1",
            },
            {
                "microbe": "a",
                "disease": "b",
                "accepted": True,
                "final_label": NEGATIVE,
                "impact_factor": 2.0,
                "quartile": "Q2",
            },
        ]
        strengths = compute_strength_scores(aggregated)
        self.assertEqual(len(strengths), 1)
        self.assertEqual(strengths[0]["support_count"], 2)
        self.assertEqual(strengths[0]["total_strength_raw"], 0)


if __name__ == "__main__":
    unittest.main()
