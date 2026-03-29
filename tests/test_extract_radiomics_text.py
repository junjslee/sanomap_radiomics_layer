import unittest
import tempfile
from pathlib import Path

from src.extract_radiomics_text import _detect_disease, extract_mentions_from_paper


class TestExtractRadiomicsText(unittest.TestCase):
    def test_extracts_canonical_feature(self) -> None:
        paper = {
            "pmid": "99999999",
            "title": "CT radiomics in hepatocellular carcinoma",
            "abstract": "We found that GLCM entropy in liver CT scans was associated with carcinoma outcomes.",
        }
        mentions, _ = extract_mentions_from_paper(paper)
        self.assertGreaterEqual(len(mentions), 1)
        canonical = {m.canonical_feature for m in mentions}
        self.assertIn("glcm_entropy", canonical)

    def test_fuzzy_feature_mapping(self) -> None:
        paper = {
            "pmid": "99999998",
            "title": "MRI analysis",
            "abstract": "Haralick entropi was significantly associated with tumor burden.",
        }
        mentions, _ = extract_mentions_from_paper(paper)
        self.assertGreaterEqual(len(mentions), 1)
        self.assertEqual(mentions[0].canonical_feature, "glcm_entropy")

    def test_extracts_body_composition_feature_and_signature(self) -> None:
        paper = {
            "pmid": "99999997",
            "title": "Gut microbiota composition and visceral adipose tissue",
            "abstract": "Gut microbiota composition was associated with visceral adipose tissue in adults.",
        }
        mentions, _ = extract_mentions_from_paper(paper)
        self.assertGreaterEqual(len(mentions), 1)
        mention = mentions[0]
        self.assertEqual(mention.node_type, "BodyCompositionFeature")
        self.assertEqual(mention.feature_family, "body_composition")
        self.assertEqual(mention.subject_node_type, "MicrobialSignature")
        self.assertEqual(mention.subject_node, "gut microbiota composition")

    def test_extracts_taxon_specific_microbe_subject(self) -> None:
        paper = {
            "pmid": "99999996",
            "title": "CT radiomics and microbiome in colorectal cancer",
            "abstract": "Fusobacterium nucleatum abundance correlated with GLCM entropy on CT in colorectal cancer.",
        }
        mentions, _ = extract_mentions_from_paper(paper)
        self.assertGreaterEqual(len(mentions), 1)
        mention = mentions[0]
        self.assertEqual(mention.node_type, "RadiomicFeature")
        self.assertEqual(mention.subject_node_type, "Microbe")
        self.assertEqual(mention.subject_node, "fusobacterium nucleatum")

    def test_prefers_full_text_path_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full_text_path = Path(tmpdir) / "PMC1.txt"
            full_text_path.write_text(
                "Respiratory microbiota and radiomics features. GLCM entropy on CT was associated with COPD.",
                encoding="utf-8",
            )
            paper = {
                "pmid": "99999995",
                "title": "Title only",
                "abstract": "",
                "full_text_path": str(full_text_path),
            }
            mentions, _ = extract_mentions_from_paper(paper)
            self.assertGreaterEqual(len(mentions), 1)
            self.assertEqual(mentions[0].canonical_feature, "glcm_entropy")


class TestDetectDisease(unittest.TestCase):
    def test_rejects_sentence_fragment_verb_lead(self) -> None:
        self.assertIsNone(_detect_disease("is related with sarcopenia in cirrhosis patients", ""))

    def test_rejects_sentence_fragment_with_humans(self) -> None:
        self.assertIsNone(_detect_disease("exercise training in humans with obesity", ""))

    def test_rejects_components_prefix(self) -> None:
        self.assertIsNone(_detect_disease("components of liver steatosis and fibrosis", ""))

    def test_rejects_distribution_context(self) -> None:
        self.assertIsNone(_detect_disease("body fat distribution and systemic inflammation", ""))

    def test_rejects_verb_lessens(self) -> None:
        self.assertIsNone(_detect_disease("pepper lessens high fat diet-induced inflammation", ""))

    def test_rejects_is_affected_by(self) -> None:
        self.assertIsNone(_detect_disease("tissue phenotype is affected by obesity", ""))

    def test_keeps_colorectal_cancer(self) -> None:
        self.assertEqual(_detect_disease("colorectal cancer was associated with Fusobacterium", ""), "colorectal cancer")

    def test_keeps_liver_fibrosis(self) -> None:
        self.assertEqual(_detect_disease("liver fibrosis was predicted by microbiome features", ""), "liver fibrosis")

    def test_keeps_metabolic_syndrome(self) -> None:
        self.assertEqual(_detect_disease("metabolic syndrome risk was increased", ""), "metabolic syndrome")

    def test_keeps_mafld_multiword(self) -> None:
        self.assertEqual(
            _detect_disease("metabolic dysfunction-associated fatty liver disease", ""),
            "metabolic dysfunction-associated fatty liver disease",
        )

    def test_keeps_low_grade_chronic_inflammation(self) -> None:
        self.assertEqual(
            _detect_disease("low-grade chronic inflammation correlated with muscle loss", ""),
            "low-grade chronic inflammation",
        )

    def test_keeps_systemic_inflammation(self) -> None:
        self.assertEqual(_detect_disease("systemic inflammation was elevated", ""), "systemic inflammation")


if __name__ == "__main__":
    unittest.main()
