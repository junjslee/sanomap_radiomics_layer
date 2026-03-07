import unittest

from src.assemble_edges import build_bridge_hypotheses, build_edge_candidates


class TestAssembleEdges(unittest.TestCase):
    def test_builds_text_and_verified_vision_edges(self) -> None:
        text_mentions = [
            {
                "mention_id": "m1",
                "pmid": "123",
                "canonical_feature": "glcm_entropy",
                "feature_family": "radiomic",
                "node_type": "RadiomicFeature",
                "disease": "liver cancer",
                "claim_hint": "association",
                "confidence": 0.8,
                "evidence": "sentence evidence",
            },
            {
                "mention_id": "m2",
                "pmid": "123",
                "canonical_feature": "glcm_entropy",
                "feature_family": "radiomic",
                "node_type": "RadiomicFeature",
                "disease": "liver cancer",
                "confidence": 0.3,
                "evidence": "weak evidence",
            },
        ]
        vision_proposals = [
            {
                "proposal_id": "p1",
                "pmid": "123",
                "figure_id": "f1",
                "radiomic_feature": "glcm_entropy",
                "disease": "liver cancer",
                "microbe": "bacteroides",
                "candidate_r": 0.42,
            }
        ]
        verification_results = [
            {
                "proposal_id": "p1",
                "pass_fail": True,
                "verified": True,
                "support_fraction": 0.7,
                "reason_code": "verified",
                "distance_metric": 0.01,
            }
        ]
        papers = [
            {
                "pmid": "123",
                "title": "A paper",
                "journal": "Journal X",
                "pmcid": "PMC1",
                "year": 2024,
                "issn": "1111-2222",
                "impact_factor": 4.2,
                "quartile": "Q2",
            }
        ]

        edges = build_edge_candidates(
            text_mentions,
            vision_proposals,
            verification_results=verification_results,
            text_min_confidence=0.6,
            papers=papers,
        )
        relation_types = [e.relation_type for e in edges]
        self.assertIn("TEXT_ASSOCIATION", relation_types)
        self.assertIn("VISION_CORRELATION", relation_types)

        text_edges = [e for e in edges if e.relation_type == "TEXT_ASSOCIATION"]
        self.assertEqual(len(text_edges), 1)
        self.assertEqual(text_edges[0].journal, "Journal X")
        self.assertEqual(text_edges[0].graph_rel_type, "ASSOCIATED_WITH")
        self.assertEqual(text_edges[0].subject_node_type, "RadiomicFeature")
        self.assertEqual(text_edges[0].object_node_type, "Disease")

        vision_edges = [e for e in edges if e.relation_type == "VISION_CORRELATION"]
        self.assertEqual(len(vision_edges), 1)
        self.assertEqual(vision_edges[0].graph_rel_type, "CORRELATES_WITH")
        self.assertEqual(vision_edges[0].subject_node_type, "Microbe")
        self.assertEqual(vision_edges[0].object_node_type, "RadiomicFeature")

    def test_rejects_unverified_vision_by_default(self) -> None:
        vision_proposals = [
            {
                "proposal_id": "p2",
                "pmid": "123",
                "figure_id": "f1",
                "radiomic_feature": "glcm_entropy",
                "microbe": "bacteroides",
                "candidate_r": 0.21,
            }
        ]
        verification_results = [
            {
                "proposal_id": "p2",
                "pass_fail": False,
                "verified": False,
                "support_fraction": 0.1,
                "reason_code": "insufficient_support",
                "distance_metric": 0.22,
            }
        ]

        edges = build_edge_candidates(
            [],
            vision_proposals,
            verification_results=verification_results,
            papers=[],
        )
        self.assertEqual(len(edges), 0)

        edges_unverified = build_edge_candidates(
            [],
            vision_proposals,
            verification_results=verification_results,
            include_unverified_vision=True,
            papers=[],
        )
        self.assertEqual(len(edges_unverified), 1)
        self.assertFalse(edges_unverified[0].verification_passed)

    def test_builds_bridge_hypotheses_without_emitting_graph_edge(self) -> None:
        text_mentions = [
            {
                "mention_id": "m1",
                "pmid": "500",
                "canonical_feature": "glcm_entropy",
                "feature_family": "radiomic",
                "node_type": "RadiomicFeature",
                "disease": "colitis",
                "claim_hint": "association",
                "confidence": 0.91,
                "evidence": "PMID 500 sentence 2",
            }
        ]
        relation_aggregated = [
            {
                "pmid": "500",
                "microbe": "escherichia coli",
                "disease": "colitis",
                "final_label": "positive",
                "accepted": True,
                "evidence": "E. coli increased disease markers.",
            }
        ]

        hypotheses, rejected = build_bridge_hypotheses(
            text_mentions=text_mentions,
            relation_aggregated=relation_aggregated,
            text_min_confidence=0.6,
            _paper_index={},
            _resolver=None,
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0].microbe_or_signature_type, "Microbe")
        self.assertEqual(hypotheses[0].phenotype_node_type, "RadiomicFeature")
        self.assertTrue(hypotheses[0].not_for_graph_ingestion)

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=relation_aggregated,
            papers=[],
        )
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].graph_rel_type, "ASSOCIATED_WITH")


if __name__ == "__main__":
    unittest.main()
