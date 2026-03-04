import unittest

from src.journal_metrics import (
    ImpactFactorResolver,
    normalize_impact_factor,
    normalize_quartile,
    resolve_paper_metrics,
)


class TestJournalMetrics(unittest.TestCase):
    def test_normalizers(self) -> None:
        self.assertEqual(normalize_quartile("Q1"), "Q1")
        self.assertEqual(normalize_quartile("2"), "Q2")
        self.assertIsNone(normalize_quartile(""))

        self.assertEqual(normalize_impact_factor("3.2"), 3.2)
        self.assertIsNone(normalize_impact_factor("NA"))

    def test_resolve_from_inline_paper_fields(self) -> None:
        paper = {"impact_factor": "5.1", "quartile": "Q1"}
        out = resolve_paper_metrics(paper, resolver=None)
        self.assertEqual(out.impact_factor, 5.1)
        self.assertEqual(out.quartile, "Q1")
        self.assertEqual(out.source, "paper_record")

    def test_resolver_unavailable_fallback(self) -> None:
        resolver = ImpactFactorResolver()
        paper = {"issn": "1234-5678"}
        out = resolve_paper_metrics(paper, resolver=resolver)
        self.assertIn(out.source, {"impact_factor_core", "not_found", "lookup_error", "resolver_unavailable"})


if __name__ == "__main__":
    unittest.main()
