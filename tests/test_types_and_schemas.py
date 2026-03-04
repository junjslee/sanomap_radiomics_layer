import unittest
from pathlib import Path

from src.schema_utils import load_schema, validate_record
from src.types import PaperRecord, to_dict


class TestTypesAndSchemas(unittest.TestCase):
    def test_paper_roundtrip_shape(self) -> None:
        rec = PaperRecord(
            pmid="12345678",
            title="Test",
            abstract="Abstract",
            query="radiomics",
            retrieval_date="2026-03-03T00:00:00Z",
        )
        payload = to_dict(rec)
        self.assertEqual(payload["pmid"], "12345678")
        self.assertIn("source", payload)

    def test_schema_files_exist(self) -> None:
        schema_dir = Path("src/schemas")
        expected = {
            "papers.schema.json",
            "figures.schema.json",
            "text_mentions.schema.json",
            "vision_proposals.schema.json",
            "verified_edges.schema.json",
        }
        names = {p.name for p in schema_dir.glob("*.json")}
        self.assertTrue(expected.issubset(names))

    def test_paper_schema_validation(self) -> None:
        schema = load_schema("papers.schema.json")
        payload = {
            "pmid": "11111111",
            "title": "Sample",
            "abstract": "Sample abstract",
            "query": "radiomics",
            "retrieval_date": "2026-03-03T00:00:00Z",
            "source": "pubmed",
        }
        validate_record(payload, schema)


if __name__ == "__main__":
    unittest.main()
