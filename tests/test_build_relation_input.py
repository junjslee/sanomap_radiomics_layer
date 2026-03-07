import unittest

from src.build_relation_input import build_relation_rows


class TestBuildRelationInput(unittest.TestCase):
    def test_builds_rows_with_radiomics_context(self) -> None:
        entity_sentences = [
            {
                "record_id": "r1",
                "pmid": "111",
                "sentence": "Escherichia coli is associated with liver cancer.",
                "microbes": [{"text": "Escherichia coli", "cui": "C1"}],
                "diseases": [{"text": "liver cancer", "cui": "C2"}],
            }
        ]
        text_mentions = [
            {
                "pmid": "111",
                "canonical_feature": "glcm_entropy",
            }
        ]
        papers = [{"pmid": "111", "impact_factor": 3.2, "quartile": "Q2"}]

        rows, metrics = build_relation_rows(
            entity_sentences=entity_sentences,
            text_mentions=text_mentions,
            papers=papers,
            max_words=500,
            max_chars=5000,
            require_radiomics_context=True,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pmid, "111")
        self.assertEqual(rows[0].microbe, "escherichia coli")
        self.assertEqual(rows[0].subject_node_type, "Microbe")
        self.assertEqual(rows[0].subject_node, "escherichia coli")
        self.assertEqual(rows[0].radiomic_features, ["glcm_entropy"])
        self.assertEqual(metrics["rows_out"], 1)

    def test_filters_without_radiomics_context(self) -> None:
        entity_sentences = [
            {
                "record_id": "r1",
                "pmid": "222",
                "sentence": "Lactobacillus was associated with obesity.",
                "microbes": [{"text": "Lactobacillus"}],
                "diseases": [{"text": "obesity"}],
            }
        ]

        rows, metrics = build_relation_rows(
            entity_sentences=entity_sentences,
            text_mentions=[],
            papers=[],
            max_words=500,
            max_chars=5000,
            require_radiomics_context=True,
        )

        self.assertEqual(rows, [])
        self.assertIn("missing_radiomics_context", metrics["filtered_reason_counts"])


if __name__ == "__main__":
    unittest.main()
