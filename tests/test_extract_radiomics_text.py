import unittest
import tempfile
from pathlib import Path

from src.extract_radiomics_text import extract_mentions_from_paper


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


if __name__ == "__main__":
    unittest.main()
