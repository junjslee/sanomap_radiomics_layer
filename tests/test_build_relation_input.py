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

    def test_cleans_subject_and_disease_spans_before_writing_rows(self) -> None:
        entity_sentences = [
            {
                "record_id": "r2",
                "pmid": "333",
                "sentence": "Escherichia coli abundance was associated with obesity markers.",
                "microbes": [{"text": "Escherichia coli abundance", "cui": "C1"}],
                "diseases": [{"text": "obesity markers", "cui": "C2"}],
            }
        ]
        text_mentions = [{"pmid": "333", "canonical_feature": "glcm_entropy"}]

        rows, metrics = build_relation_rows(
            entity_sentences=entity_sentences,
            text_mentions=text_mentions,
            papers=[],
            max_words=500,
            max_chars=5000,
            require_radiomics_context=True,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].microbe, "escherichia coli")
        self.assertEqual(rows[0].subject_node, "escherichia coli")
        self.assertEqual(rows[0].disease, "obesity")
        self.assertEqual(metrics["rows_out"], 1)

    def test_filters_relation_language_disease_spans(self) -> None:
        entity_sentences = [
            {
                "record_id": "r3",
                "pmid": "444",
                "sentence": "Escherichia coli was associated with obesity-associated markers.",
                "microbes": [{"text": "Escherichia coli"}],
                "diseases": [{"text": "obesity associated with dysbiosis"}],
            }
        ]
        text_mentions = [{"pmid": "444", "canonical_feature": "glcm_entropy"}]

        rows, metrics = build_relation_rows(
            entity_sentences=entity_sentences,
            text_mentions=text_mentions,
            papers=[],
            max_words=500,
            max_chars=5000,
            require_radiomics_context=True,
        )

        self.assertEqual(rows, [])
        self.assertIn("disease_relation_language", metrics["filtered_reason_counts"])

    def test_cleans_subject_tail_and_leading_disease_prefix(self) -> None:
        entity_sentences = [
            {
                "record_id": "r4",
                "pmid": "555",
                "sentence": "Fusobacteria were linked to chronic HIV infection in adults.",
                "microbes": [{"text": "Fusobacteria were", "cui": "C1"}],
                "diseases": [{"text": "in adults with chronic HIV infection", "cui": "C2"}],
            }
        ]
        text_mentions = [{"pmid": "555", "canonical_feature": "vat_area"}]

        rows, metrics = build_relation_rows(
            entity_sentences=entity_sentences,
            text_mentions=text_mentions,
            papers=[],
            max_words=500,
            max_chars=5000,
            require_radiomics_context=True,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].microbe, "fusobacteria")
        self.assertEqual(rows[0].subject_node, "fusobacteria")
        self.assertEqual(rows[0].disease, "chronic hiv infection")
        self.assertEqual(metrics["rows_out"], 1)


if __name__ == "__main__":
    unittest.main()
