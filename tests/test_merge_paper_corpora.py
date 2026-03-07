import tempfile
import unittest
from pathlib import Path

from src.artifact_utils import write_jsonl
from src.merge_paper_corpora import merge_paper_corpora
from src.types import PaperRecord


class TestMergePaperCorpora(unittest.TestCase):
    def test_merge_paper_corpora_dedupes_and_preserves_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strict_path = Path(tmpdir) / "papers_microbe_radiomics_strict.jsonl"
            adjacent_path = Path(tmpdir) / "papers_microbe_imaging_adjacent.jsonl"

            write_jsonl(
                strict_path,
                [
                    PaperRecord(
                        pmid="1",
                        title="Strict title",
                        abstract="",
                        query="strict",
                        retrieval_date="2026-03-07T00:00:00Z",
                        source="pubmed",
                    )
                ],
            )
            write_jsonl(
                adjacent_path,
                [
                    PaperRecord(
                        pmid="1",
                        title="Strict title",
                        abstract="Useful abstract",
                        query="adjacent",
                        retrieval_date="2026-03-08T00:00:00Z",
                        source="pubmed",
                        pmcid="PMC123",
                    ),
                    PaperRecord(
                        pmid="2",
                        title="Another paper",
                        abstract="Another abstract",
                        query="adjacent",
                        retrieval_date="2026-03-08T00:00:00Z",
                        source="pubmed",
                    ),
                ],
            )

            merged_rows, provenance_rows, metrics = merge_paper_corpora([strict_path, adjacent_path])

            self.assertEqual(metrics["unique_pmids"], 2)
            self.assertEqual(metrics["duplicate_rows_removed"], 1)
            self.assertEqual(len(merged_rows), 2)
            self.assertEqual(merged_rows[0].abstract, "Useful abstract")
            self.assertEqual(merged_rows[0].pmcid, "PMC123")
            self.assertEqual(merged_rows[0].query, "merged:microbe_radiomics_strict|microbe_imaging_adjacent")
            self.assertEqual(provenance_rows[0]["source_count"], 2)


if __name__ == "__main__":
    unittest.main()
