import unittest

from src.index_figures import classify_figure


class TestIndexFigures(unittest.TestCase):
    def test_heatmap_caption_classification(self) -> None:
        topology, confidence, hits = classify_figure("Correlation heatmap of CT radiomics features")
        self.assertEqual(topology, "heatmap")
        self.assertGreater(confidence, 0.0)
        self.assertTrue(any("heatmap" in h for h in hits))

    def test_forest_caption_classification(self) -> None:
        topology, confidence, _ = classify_figure("Forest plot with confidence interval for hazard ratio")
        self.assertEqual(topology, "forest_plot")
        self.assertGreater(confidence, 0.0)

    def test_unknown_classification(self) -> None:
        topology, confidence, _ = classify_figure("Overview diagram")
        self.assertEqual(topology, "unknown")
        self.assertEqual(confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
