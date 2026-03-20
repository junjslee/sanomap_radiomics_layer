import unittest

from src.assemble_edges import (
    build_bridge_hypotheses,
    build_edge_candidates,
    build_microbe_disease_edges,
    build_text_axis_candidates,
)


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

    def test_text_edges_clean_disease_spans_before_emission(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3",
                "pmid": "777",
                "canonical_feature": "skeletal_muscle_index",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "in adults with chronic HIV infection",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "SMI was associated with chronic HIV infection in adults.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].object_node_type, "Disease")
        self.assertEqual(edges[0].object_node, "chronic hiv infection")

    def test_text_edges_reject_clause_like_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3b",
                "pmid": "778",
                "canonical_feature": "sarcopenia",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "guidelines for the treatment of cirrhosis",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Guidelines for the treatment of cirrhosis were discussed with sarcopenia.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(edges, [])

    def test_text_edges_strip_presence_prefix_for_graph_target(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3c",
                "pmid": "779",
                "canonical_feature": "myosteatosis",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "presence of liver fibrosis",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Presence of liver fibrosis was associated with myosteatosis.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].object_node, "liver fibrosis")

    def test_text_edges_strip_biopsy_proven_prefix_for_graph_target(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3d",
                "pmid": "780",
                "canonical_feature": "myosteatosis",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "biopsy-proven liver fibrosis",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Biopsy-proven liver fibrosis was associated with myosteatosis.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].object_node, "liver fibrosis")

    def test_text_edges_normalize_mafld_alias_duplication(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3e",
                "pmid": "781",
                "canonical_feature": "skeletal_muscle_index",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "mafld metabolic dysfunction-associated fatty liver disease",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "MAFLD metabolic dysfunction-associated fatty liver disease was associated with SMI.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].object_node, "metabolic dysfunction-associated fatty liver disease")

    def test_text_edges_reject_measurement_phrase_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3f",
                "pmid": "782",
                "canonical_feature": "visceral_adipose_tissue",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "as a measure of obesity",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "VAT was discussed as a measure of obesity.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(edges, [])

    def test_text_edges_reject_subject_leakage_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3g",
                "pmid": "783",
                "canonical_feature": "subcutaneous_adipose_tissue",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "subcutaneous adipose tissue in colorectal cancer",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Subcutaneous adipose tissue in colorectal cancer was discussed.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(edges, [])

    def test_text_edges_reject_self_typed_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3h",
                "pmid": "784",
                "canonical_feature": "sarcopenia",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "sarcopenia is a disease",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Sarcopenia is a disease was discussed with sarcopenia.",
            }
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(edges, [])

    def test_text_edges_keep_qualified_inflammation_targets(self) -> None:
        text_mentions = [
            {
                "mention_id": "m3i",
                "pmid": "785",
                "canonical_feature": "visceral_adipose_tissue",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "systemic inflammation",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "VAT was associated with systemic inflammation.",
            },
            {
                "mention_id": "m3j",
                "pmid": "786",
                "canonical_feature": "visceral_adipose_tissue",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "disease": "low-grade chronic inflammation",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "VAT was associated with low-grade chronic inflammation.",
            },
        ]

        edges = build_edge_candidates(
            text_mentions=text_mentions,
            vision_proposals=[],
            relation_aggregated=[],
            papers=[],
        )

        self.assertEqual(len(edges), 2)
        self.assertEqual({edge.object_node for edge in edges}, {"systemic inflammation", "low-grade chronic inflammation"})

    def test_builds_text_axis_candidates_as_audit_only_rows(self) -> None:
        text_mentions = [
            {
                "mention_id": "m4",
                "pmid": "888",
                "canonical_feature": "skeletal_muscle_index",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "subject_node_type": "Microbe",
                "subject_node": "Proteobacteria phylum",
                "disease": "and metabolic syndrome",
                "claim_hint": "association",
                "confidence": 0.91,
                "evidence": "Proteobacteria phylum was discussed with skeletal muscle index and obesity and metabolic syndrome.",
            },
            {
                "mention_id": "m5",
                "pmid": "888",
                "canonical_feature": "skeletal_muscle_index",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "subject_node_type": "Microbe",
                "subject_node": "bacterial species",
                "disease": "obesity",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Generic bacterial species mention should be rejected.",
            },
        ]

        candidates, rejected = build_text_axis_candidates(
            text_mentions=text_mentions,
            text_min_confidence=0.6,
        )

        self.assertEqual(rejected, 1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].subject_node_type, "Microbe")
        self.assertEqual(candidates[0].subject_node, "proteobacteria")
        self.assertEqual(candidates[0].phenotype, "skeletal_muscle_index")
        self.assertEqual(candidates[0].disease_context, "metabolic syndrome")
        self.assertTrue(candidates[0].not_for_graph_ingestion)

    def test_axis_candidates_drop_non_graph_eligible_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m6",
                "pmid": "889",
                "canonical_feature": "sarcopenia",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "subject_node_type": "Microbe",
                "subject_node": "Akkermansia and",
                "disease": "guidelines for the treatment of cirrhosis",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Akkermansia and sarcopenia were discussed in guideline context.",
            }
        ]

        candidates, rejected = build_text_axis_candidates(
            text_mentions=text_mentions,
            text_min_confidence=0.6,
        )

        self.assertEqual(rejected, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].subject_node, "akkermansia")
        self.assertIsNone(candidates[0].disease_context)

    def test_axis_candidates_drop_measurement_phrase_disease_context(self) -> None:
        text_mentions = [
            {
                "mention_id": "m7",
                "pmid": "890",
                "canonical_feature": "visceral_adipose_tissue",
                "feature_family": "body_composition",
                "node_type": "BodyCompositionFeature",
                "subject_node_type": "Microbe",
                "subject_node": "Akkermansia",
                "disease": "as a measure of obesity",
                "claim_hint": "association",
                "confidence": 0.95,
                "evidence": "Akkermansia was discussed with VAT as a measure of obesity.",
            }
        ]

        candidates, rejected = build_text_axis_candidates(
            text_mentions=text_mentions,
            text_min_confidence=0.6,
        )

        self.assertEqual(rejected, 0)
        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].disease_context)


class TestMicrobeDiseaseEdges(unittest.TestCase):
    def _positive_relation(self) -> dict:
        return {
            "pmid": "999",
            "subject_node_type": "Microbe",
            "subject_node": "bifidobacterium",
            "microbe": "bifidobacterium",
            "disease": "obesity",
            "final_label": "positive",
            "accepted": True,
            "confidence": 0.85,
            "evidence": "Bifidobacterium was associated with reduced obesity.",
        }

    def _negative_relation(self) -> dict:
        return {
            "pmid": "999",
            "subject_node_type": "Microbe",
            "subject_node": "lactobacillus rhamnosus",
            "microbe": "lactobacillus rhamnosus",
            "disease": "metabolic syndrome",
            "final_label": "negative",
            "accepted": True,
            "confidence": 0.78,
            "evidence": "Lactobacillus rhamnosus negatively associated with metabolic syndrome.",
        }

    def test_positive_relation_emits_positively_associated_with(self) -> None:
        edges, rejected = build_microbe_disease_edges(
            [self._positive_relation()],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].graph_rel_type, "POSITIVELY_ASSOCIATED_WITH")
        self.assertEqual(edges[0].relation_direction, "positive")
        self.assertEqual(edges[0].subject_node, "bifidobacterium")
        self.assertEqual(edges[0].object_node, "obesity")
        self.assertEqual(edges[0].object_node_type, "Disease")
        self.assertEqual(edges[0].assertion_level, "direct_evidence")

    def test_negative_relation_emits_negatively_associated_with(self) -> None:
        edges, rejected = build_microbe_disease_edges(
            [self._negative_relation()],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].graph_rel_type, "NEGATIVELY_ASSOCIATED_WITH")
        self.assertEqual(edges[0].relation_direction, "negative")

    def test_unrelated_label_rejected(self) -> None:
        relation = self._positive_relation()
        relation["final_label"] = "unrelated"
        edges, rejected = build_microbe_disease_edges(
            [relation],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(len(edges), 0)
        self.assertEqual(rejected, 1)

    def test_clause_like_disease_rejected(self) -> None:
        relation = self._positive_relation()
        relation["disease"] = "development of colorectal cancer"
        edges, rejected = build_microbe_disease_edges(
            [relation],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(len(edges), 0)
        self.assertEqual(rejected, 1)

    def test_generic_microbe_rejected(self) -> None:
        relation = self._positive_relation()
        relation["subject_node"] = "bacterial species"
        relation["microbe"] = "bacterial species"
        edges, rejected = build_microbe_disease_edges(
            [relation],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(len(edges), 0)
        self.assertEqual(rejected, 1)

    def test_both_positive_and_negative_together(self) -> None:
        edges, rejected = build_microbe_disease_edges(
            [self._positive_relation(), self._negative_relation()],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(len(edges), 2)
        rel_types = {e.graph_rel_type for e in edges}
        self.assertIn("POSITIVELY_ASSOCIATED_WITH", rel_types)
        self.assertIn("NEGATIVELY_ASSOCIATED_WITH", rel_types)

    def test_deduplication_keeps_higher_confidence(self) -> None:
        r1 = self._positive_relation()
        r2 = {**r1, "confidence": 0.95}
        edges, _ = build_microbe_disease_edges(
            [r1, r2],
            paper_index={},
            resolver=None,
        )
        self.assertEqual(len(edges), 1)
        self.assertAlmostEqual(edges[0].confidence, 0.95)


if __name__ == "__main__":
    unittest.main()
