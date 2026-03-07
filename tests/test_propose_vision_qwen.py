import unittest

from src.propose_vision_qwen import (
    DEFAULT_MODEL_ID,
    DEFAULT_PROMPT_ID,
    ProposerOptions,
    run_proposer,
)


class TestProposeVisionQwen(unittest.TestCase):
    def setUp(self) -> None:
        self.options = ProposerOptions(
            backend="heuristic",
            model_id=DEFAULT_MODEL_ID,
            prompt_id=DEFAULT_PROMPT_ID,
            api_base_url=None,
            api_key=None,
            temperature=0.1,
            max_tokens=120,
            allow_fallback=True,
        )

    def test_skips_non_heatmap_by_default(self) -> None:
        figures = [
            {
                "figure_id": "f1",
                "pmid": "123",
                "topology": "forest_plot",
                "topology_confidence": 0.9,
            }
        ]
        out = run_proposer(
            figures=figures,
            options=self.options,
            min_topology_confidence=0.1,
            include_non_heatmap=False,
        )
        self.assertEqual(out, [])

    def test_structured_missing_image_row(self) -> None:
        figures = [
            {
                "figure_id": "f2",
                "pmid": "123",
                "topology": "heatmap",
                "topology_confidence": 0.9,
                "caption": "Heatmap of correlation coefficients",
            }
        ]
        out = run_proposer(
            figures=figures,
            options=self.options,
            min_topology_confidence=0.1,
            include_non_heatmap=False,
        )
        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["status"], "missing_image")
        self.assertIsNone(row["candidate_r"])
        self.assertEqual(row["model_id"], DEFAULT_MODEL_ID)
        self.assertEqual(row["prompt_id"], DEFAULT_PROMPT_ID)
        self.assertIn("raw_response", row)
        self.assertIn("subject_node_type", row)
        self.assertIn("subject_node", row)


if __name__ == "__main__":
    unittest.main()
