import unittest

from src.harvest_pubmed import build_query


class TestHarvestPubmed(unittest.TestCase):
    def test_build_query_adds_language(self) -> None:
        q = build_query("radiomics", "english")
        self.assertIn("radiomics", q)
        self.assertIn("english[Language]", q)


if __name__ == "__main__":
    unittest.main()
