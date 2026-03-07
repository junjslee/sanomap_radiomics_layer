import tempfile
import unittest
from pathlib import Path

from src.download_pmc_fulltext import download_pmc_fulltext, extract_article_text_from_html
from src.types import PaperRecord


class TestDownloadPmcFulltext(unittest.TestCase):
    def test_extract_article_text_from_html_trims_to_abstract_references_window(self) -> None:
        html = """
        <html>
          <body>
            <header>PMC banner</header>
            <article>
              <h2>Abstract</h2>
              <p>Important microbiome and radiomics findings.</p>
              <h2>Methods</h2>
              <p>More useful body text.</p>
              <h2>References</h2>
              <p>Reference one.</p>
            </article>
          </body>
        </html>
        """
        extracted = extract_article_text_from_html(html)
        self.assertIn("Abstract Important microbiome and radiomics findings.", extracted)
        self.assertIn("Methods More useful body text.", extracted)
        self.assertNotIn("Reference one.", extracted)
        self.assertNotIn("PMC banner", extracted)

    def test_download_pmc_fulltext_reuses_existing_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_dir = Path(tmpdir) / "html"
            text_dir = Path(tmpdir) / "text"
            text_dir.mkdir(parents=True, exist_ok=True)
            existing = text_dir / "PMC123.txt"
            existing.write_text("cached text", encoding="utf-8")
            paper = PaperRecord(
                pmid="1",
                pmcid="PMC123",
                doi=None,
                title="Paper",
                abstract="Abstract",
                journal=None,
                issn=None,
                year=2024,
                language="english",
                query="q",
                retrieval_date="2026-03-07T00:00:00Z",
                source="pubmed",
            )
            updated, metrics = download_pmc_fulltext(
                papers=[paper],
                html_dir=html_dir,
                text_dir=text_dir,
                overwrite=False,
            )
            self.assertEqual(metrics["reused_existing"], 1)
            self.assertEqual(metrics["downloaded"], 0)
            self.assertEqual(updated[0].full_text_path, str(existing.resolve()))


if __name__ == "__main__":
    unittest.main()
