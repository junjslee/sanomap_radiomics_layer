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

    def extract(self, sentence: str):
        return self.extract_many([sentence])[0]

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


class CleanupDummyMicrobeExtractor:
    model_id = "dummy/microbe-cleanup"

    def extract(self, sentence: str):
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]):
        out = []
        for sentence in sentences:
            if "escherichia coli abundance" in sentence.lower():
                out.append(
                    [
                        {
                            "text": "Escherichia coli abundance",
                            "start": 0,
                            "end": 27,
                            "score": 0.9,
                            "label": "MICROBE",
                            "extractor": "dummy",
                        },
                        {
                            "text": "bacterial presence",
                            "start": 29,
                            "end": 47,
                            "score": 0.7,
                            "label": "MICROBE",
                            "extractor": "dummy",
                        },
                    ]
                )
            else:
                out.append([])
        return out


class CleanupDummyDiseaseExtractor:
    effective_mode = "dummy-cleanup"

    def extract(self, sentence: str):
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]):
        out = []
        for sentence in sentences:
            if "liver cancer" in sentence.lower():
                out.append(
                    [
                        {
                            "text": "liver cancer in this cohort",
                            "start": 52,
                            "end": 80,
                            "score": 0.95,
                            "label": "DISEASE",
                            "extractor": "dummy",
                        }
                    ]
                )
            else:
                out.append([])
        return out


class PrefixCleanupDummyMicrobeExtractor:
    model_id = "dummy/microbe-prefix-cleanup"

    def extract(self, sentence: str):
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]):
        out = []
        for sentence in sentences:
            if "fusobacteria were" in sentence.lower():
                out.append(
                    [
                        {
                            "text": "Fusobacteria were",
                            "start": 0,
                            "end": 17,
                            "score": 0.9,
                            "label": "MICROBE",
                            "extractor": "dummy",
                        }
                    ]
                )
            else:
                out.append([])
        return out


class PrefixCleanupDummyDiseaseExtractor:
    effective_mode = "dummy-prefix-cleanup"

    def extract(self, sentence: str):
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]):
        out = []
        for sentence in sentences:
            if "chronic hiv infection" in sentence.lower():
                out.append(
                    [
                        {
                            "text": "in adults with chronic HIV infection",
                            "start": 30,
                            "end": 66,
                            "score": 0.95,
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

        disease_extractor = DummyDiseaseExtractor()
        microbe_extractor = DummyMicrobeExtractor()
        normalizer = UMLSNormalizer(enabled=False)

        entity_rows, relation_rows, metrics = build_entity_and_relation_rows(
            papers=papers,
            disease_extractor=disease_extractor,  # type: ignore[arg-type]
            microbe_extractor=microbe_extractor,  # type: ignore[arg-type]
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

            disease_extractor = DummyDiseaseExtractor()
            microbe_extractor = DummyMicrobeExtractor()
            normalizer = UMLSNormalizer(enabled=False)

            entity_rows, relation_rows, _ = build_entity_and_relation_rows(
                papers=papers,
                disease_extractor=disease_extractor,  # type: ignore[arg-type]
                microbe_extractor=microbe_extractor,  # type: ignore[arg-type]
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

    def test_build_entity_and_relation_rows_applies_shared_span_cleanup(self) -> None:
        papers = [
            {
                "pmid": "126",
                "title": "Cleanup test",
                "abstract": "Escherichia coli abundance was associated with liver cancer in this cohort.",
            }
        ]

        entity_rows, relation_rows, _ = build_entity_and_relation_rows(
            papers=papers,
            disease_extractor=CleanupDummyDiseaseExtractor(),  # type: ignore[arg-type]
            microbe_extractor=CleanupDummyMicrobeExtractor(),  # type: ignore[arg-type]
            normalizer=UMLSNormalizer(enabled=False),
            ner_batch_size=8,
        )

        self.assertEqual(len(entity_rows), 1)
        self.assertEqual(len(entity_rows[0].microbes), 1)
        self.assertEqual(len(entity_rows[0].diseases), 1)
        self.assertEqual(entity_rows[0].microbes[0]["text"], "escherichia coli")
        self.assertEqual(entity_rows[0].diseases[0]["text"], "liver cancer")
        self.assertEqual(len(relation_rows), 1)
        self.assertEqual(relation_rows[0].microbe, "escherichia coli")
        self.assertEqual(relation_rows[0].disease, "liver cancer")

    def test_build_entity_and_relation_rows_trims_population_prefix_fragments(self) -> None:
        papers = [
            {
                "pmid": "127",
                "title": "Prefix cleanup test",
                "abstract": "Fusobacteria were linked to in adults with chronic HIV infection.",
            }
        ]

        entity_rows, relation_rows, _ = build_entity_and_relation_rows(
            papers=papers,
            disease_extractor=PrefixCleanupDummyDiseaseExtractor(),  # type: ignore[arg-type]
            microbe_extractor=PrefixCleanupDummyMicrobeExtractor(),  # type: ignore[arg-type]
            normalizer=UMLSNormalizer(enabled=False),
            ner_batch_size=8,
        )

        self.assertEqual(len(entity_rows), 1)
        self.assertEqual(entity_rows[0].microbes[0]["text"], "fusobacteria")
        self.assertEqual(entity_rows[0].diseases[0]["text"], "chronic hiv infection")
        self.assertEqual(len(relation_rows), 1)
        self.assertEqual(relation_rows[0].microbe, "fusobacteria")
        self.assertEqual(relation_rows[0].disease, "chronic hiv infection")


if __name__ == "__main__":
    unittest.main()
