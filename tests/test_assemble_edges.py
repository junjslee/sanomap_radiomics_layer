import unittest

from src.assemble_edges import build_edge_candidates


class TestAssembleEdges(unittest.TestCase):
    def test_builds_text_and_verified_vision_edges(self) -> None:
        text_mentions = [
            {
                "mention_id": "m1",
                "pmid": "123",
                "canonical_feature": "glcm_entropy",
                "disease": "liver cancer",
                "confidence": 0.8,
                "evidence": "sentence evidence",
            }
        ]
        vision_proposals = [
            {
                "proposal_id": "p1",
                "pmid": "123",
                "figure_id": "f1",
                "radiomic_feature": "glcm_entropy",
                "disease": "liver cancer",
                "microbe": "bacteroides",
                "proposed_r": 0.42,
                "verification": {"verified": True, "support_fraction": 0.7, "reason": "verified"},
            }
        ]

        edges = build_edge_candidates(text_mentions, vision_proposals)
        relation_types = {e.relation_type for e in edges}
        self.assertIn("TEXT_ASSOCIATION", relation_types)
        self.assertIn("VISION_CORRELATION", relation_types)


if __name__ == "__main__":
    unittest.main()
