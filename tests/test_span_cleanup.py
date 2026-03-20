import unittest

from src.span_cleanup import clean_disease_span, clean_relation_pair, clean_subject_span


class TestSpanCleanup(unittest.TestCase):
    def test_clean_subject_span_strips_measurement_tail(self) -> None:
        cleaned, reason = clean_subject_span("Escherichia coli abundance", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "escherichia coli")

    def test_clean_subject_span_rejects_wordpiece_artifacts(self) -> None:
        cleaned, reason = clean_subject_span("##fidobacteria", subject_node_type="Microbe")

        self.assertIsNone(cleaned)
        self.assertEqual(reason, "subject_wordpiece_fragment")

    def test_clean_disease_span_trims_context_tail(self) -> None:
        cleaned, reason = clean_disease_span("liver cancer in this cohort")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "liver cancer")

    def test_clean_subject_span_strips_trailing_clause_fragment(self) -> None:
        cleaned, reason = clean_subject_span("Fusobacteria were", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "fusobacteria")

    def test_clean_subject_span_strips_taxonomy_and_context_tail(self) -> None:
        cleaned, reason = clean_subject_span("Proteobacteria phylum", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "proteobacteria")

        cleaned, reason = clean_subject_span("Peptostreptococcaceae families", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "peptostreptococcaceae")

        cleaned, reason = clean_subject_span("Proteobacteria bearing", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "proteobacteria")

        cleaned, reason = clean_subject_span("Phascolarctobacterium abundances", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "phascolarctobacterium")

        cleaned, reason = clean_subject_span("Porphyromonadaceae with", subject_node_type="Microbe")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "porphyromonadaceae")

    def test_clean_disease_span_trims_leading_population_prefix(self) -> None:
        cleaned, reason = clean_disease_span("in adults with chronic HIV infection")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "chronic hiv infection")

    def test_clean_disease_span_trims_manifestation_prefix(self) -> None:
        cleaned, reason = clean_disease_span("one of the main manifestations of cirrhosis")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "cirrhosis")

    def test_clean_disease_span_trims_leading_conjunction_or_preposition(self) -> None:
        cleaned, reason = clean_disease_span("and metabolic syndrome")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "metabolic syndrome")

        cleaned, reason = clean_disease_span("in cirrhosis")

        self.assertIsNone(reason)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.canonical, "cirrhosis")

    def test_clean_disease_span_rejects_clause_like_sentence_fragment(self) -> None:
        cleaned, reason = clean_disease_span("Fusobacteria were more abundant in adults with obesity")

        self.assertIsNone(cleaned)
        self.assertEqual(reason, "disease_relation_language")

    def test_clean_disease_span_rejects_verb_led_relation_fragment(self) -> None:
        cleaned, reason = clean_disease_span("reduces inflammation")

        self.assertIsNone(cleaned)
        self.assertEqual(reason, "disease_relation_language")

    def test_clean_disease_span_rejects_generic_relation_like_disease_phrase(self) -> None:
        cleaned, reason = clean_disease_span("pro-inflammatory or disease")

        self.assertIsNone(cleaned)
        self.assertEqual(reason, "disease_relation_language")

    def test_clean_relation_pair_rejects_relation_language_disease(self) -> None:
        subject, disease, reason = clean_relation_pair(
            sentence="Escherichia coli was discussed with obesity-associated markers.",
            subject_node_type="Microbe",
            subject_node="Escherichia coli",
            disease="obesity associated with dysbiosis",
            max_evidence_words=500,
            max_evidence_chars=5000,
        )

        self.assertIsNone(subject)
        self.assertIsNone(disease)
        self.assertEqual(reason, "disease_relation_language")


if __name__ == "__main__":
    unittest.main()
