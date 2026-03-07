import tempfile
import unittest
from pathlib import Path

from src.paper_text_utils import paper_text


class TestPaperTextUtils(unittest.TestCase):
    def test_prefers_full_text_path_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full_text_path = Path(tmpdir) / "PMC1.txt"
            full_text_path.write_text("Full text microbiome radiomics content.", encoding="utf-8")
            text, source = paper_text(
                {
                    "title": "Title",
                    "abstract": "Abstract",
                    "full_text_path": str(full_text_path),
                }
            )
            self.assertEqual(source, "pmc_full_text")
            self.assertIn("Full text microbiome radiomics content.", text)

    def test_falls_back_to_title_abstract(self) -> None:
        text, source = paper_text({"title": "Title", "abstract": "Abstract"})
        self.assertEqual(source, "title_abstract")
        self.assertEqual(text, "Title. Abstract")


if __name__ == "__main__":
    unittest.main()
