import unittest

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


if __name__ == "__main__":
    unittest.main()
