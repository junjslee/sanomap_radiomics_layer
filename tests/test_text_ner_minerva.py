import unittest
import tempfile
from pathlib import Path

from src.text_ner_minerva import (
    DiseaseExtractor,
    UMLSNormalizer,
    build_entity_and_relation_rows,
    split_sentences,
)


class DummyMicrobeExtractor:
    model_id = "dummy/microbe"

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, sentence: str):
        self.calls += 1
        return [
            {
                "text": "Escherichia coli",
                "start": 0,
                "end": 16,
                "score": 0.9,
                "label": "MICROBE",
                "extractor": "dummy",
            }
        ]


class DummyDiseaseExtractor:
    effective_mode = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def extract_many(self, sentences: list[str]):
        self.calls += 1
        out = []
        for sentence in sentences:
            if "liver cancer" in sentence.lower():
                out.append(
                    [
                        {
                            "text": "liver cancer",
                            "start": 0,
                            "end": 12,
                            "score": 1.0,
                            "label": "DISEASE",
                            "extractor": "dummy",
                        }
                    ]
                )
            else:
                out.append([])
        return out


class TestTextNerMinerva(unittest.TestCase):
    def test_disease_extractor_fallback_without_checkpoint(self) -> None:
        extractor = DiseaseExtractor(
            mode="scibert_adapter",
            base_model="allenai/scibert_scivocab_uncased",
            checkpoint=None,
        )
        self.assertEqual(extractor.effective_mode, "bc5cdr")
        out = extractor.extract("Liver cancer was associated with outcomes.")
        self.assertGreaterEqual(len(out), 1)

    def test_build_entity_and_relation_rows(self) -> None:
        papers = [
            {
                "pmid": "123",
                "title": "Radiomics and microbiome",
                "abstract": "Escherichia coli is associated with liver cancer in this cohort.",
                "impact_factor": 5.5,
                "quartile": "Q1",
            }
        ]

        disease_extractor = DiseaseExtractor(
            mode="bc5cdr",
            base_model="allenai/scibert_scivocab_uncased",
            checkpoint=None,
        )
        microbe_extractor = DummyMicrobeExtractor()
        normalizer = UMLSNormalizer(enabled=False)

        entity_rows, relation_rows, metrics = build_entity_and_relation_rows(
            papers=papers,
            disease_extractor=disease_extractor,
            microbe_extractor=microbe_extractor,
            normalizer=normalizer,
        )

        self.assertGreaterEqual(len(entity_rows), 1)
        self.assertGreaterEqual(len(relation_rows), 1)
        self.assertEqual(metrics["papers_processed"], 1)
        self.assertEqual(relation_rows[0].pmid, "123")
        self.assertIn("liver cancer", relation_rows[0].disease)

    def test_build_entity_and_relation_rows_uses_full_text_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full_text_path = Path(tmpdir) / "PMC1.txt"
            full_text_path.write_text(
                "Escherichia coli is associated with liver cancer in this cohort.",
                encoding="utf-8",
            )
            papers = [
                {
                    "pmid": "124",
                    "title": "Title",
                    "abstract": "",
                    "full_text_path": str(full_text_path),
                }
            ]

            disease_extractor = DiseaseExtractor(
                mode="bc5cdr",
                base_model="allenai/scibert_scivocab_uncased",
                checkpoint=None,
            )
            microbe_extractor = DummyMicrobeExtractor()
            normalizer = UMLSNormalizer(enabled=False)

            entity_rows, relation_rows, _ = build_entity_and_relation_rows(
                papers=papers,
                disease_extractor=disease_extractor,
                microbe_extractor=microbe_extractor,
                normalizer=normalizer,
            )

            self.assertGreaterEqual(len(entity_rows), 1)
            self.assertGreaterEqual(len(relation_rows), 1)
            self.assertEqual(entity_rows[0].source_text, "pmc_full_text")

    def test_long_sentences_are_chunked(self) -> None:
        text = " ".join(["token"] * 205) + "."
        sentences = split_sentences(text)
        self.assertGreaterEqual(len(sentences), 3)
        self.assertTrue(all(len(sentence.split()) <= 100 for sentence in sentences))

    def test_microbe_extraction_runs_only_on_disease_positive_sentences(self) -> None:
        papers = [
            {
                "pmid": "125",
                "title": "Mixed text",
                "abstract": (
                    "This sentence discusses imaging only. "
                    "Escherichia coli is associated with liver cancer in this cohort."
                ),
            }
        ]

        disease_extractor = DummyDiseaseExtractor()
        microbe_extractor = DummyMicrobeExtractor()
        normalizer = UMLSNormalizer(enabled=False)

        entity_rows, relation_rows, metrics = build_entity_and_relation_rows(
            papers=papers,
            disease_extractor=disease_extractor,  # type: ignore[arg-type]
            microbe_extractor=microbe_extractor,  # type: ignore[arg-type]
            normalizer=normalizer,
            ner_batch_size=8,
        )

        self.assertEqual(len(entity_rows), 1)
        self.assertEqual(len(relation_rows), 1)
        self.assertEqual(microbe_extractor.calls, 1)
        self.assertEqual(metrics["microbe_sentences_evaluated"], 1)
        self.assertGreaterEqual(metrics["microbe_sentences_skipped_no_disease"], 1)


if __name__ == "__main__":
    unittest.main()
