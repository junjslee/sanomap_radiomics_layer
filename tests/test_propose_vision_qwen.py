import unittest

from src.propose_vision_qwen import (
    DEFAULT_MODEL_ID,
    DEFAULT_PROMPT_ID,
    ProposerOptions,
    _build_prompt,
    _build_prompt_forest,
    _build_prompt_scatter,
    _extract_first_json_object,
    _parse_qwen_output,
    run_proposer,
)


class TestProposeVisionQwen(unittest.TestCase):
    def setUp(self) -> None:
        self.options = ProposerOptions(
            backend="auto",
            model_id=DEFAULT_MODEL_ID,
            prompt_id=DEFAULT_PROMPT_ID,
            api_base_url=None,
            api_key=None,
            temperature=0.1,
            max_tokens=120,
        )

    def test_skips_unknown_topology_by_default(self) -> None:
        # Only figures with a qualifying topology (heatmap, forest_plot, scatter_plot, dot_plot)
        # are processed. Figures with topology="unknown" are skipped when include_non_heatmap=False.
        figures = [
            {
                "figure_id": "f1",
                "pmid": "123",
                "topology": "unknown",
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


class TestBuildPromptV2(unittest.TestCase):
    def test_prompt_contains_axis_identification_guidance(self) -> None:
        prompt = _build_prompt("Spearman correlation heatmap of gut microbiota and CT features.")
        self.assertIn("MICROBIAL TAXA", prompt)
        self.assertIn("RADIOMIC or IMAGING FEATURES", prompt)

    def test_prompt_requires_exact_copy_of_axis_labels(self) -> None:
        prompt = _build_prompt("test caption")
        self.assertIn("EXACTLY", prompt)
        self.assertIn("axis label", prompt)

    def test_prompt_handles_null_when_no_microbe_axis(self) -> None:
        prompt = _build_prompt("feature-feature correlation matrix")
        self.assertIn("null", prompt)
        self.assertIn("no microbial taxon", prompt)

    def test_prompt_includes_multi_panel_instruction(self) -> None:
        prompt = _build_prompt("panels A and B correlation")
        self.assertIn("panel", prompt.lower())

    def test_prompt_id_is_v2(self) -> None:
        self.assertEqual(DEFAULT_PROMPT_ID, "qwen_heatmap_v2_json")

    def test_prompt_includes_caption(self) -> None:
        caption = "UNIQUE_CAPTION_MARKER_XYZ"
        prompt = _build_prompt(caption)
        self.assertIn(caption, prompt)


class TestParseQwenOutput(unittest.TestCase):
    def test_parses_valid_json_with_microbe_and_feature(self) -> None:
        raw = '{"candidate_r": 0.87, "panel_id": "A", "microbe": "Prevotella nigrescens", "radiomic_feature": "GLCM_Correlation", "disease": null, "modality": "CT", "bbox": null, "heatmap_bbox": null, "legend_bbox": null}'
        result = _parse_qwen_output(raw)
        self.assertAlmostEqual(result["candidate_r"], 0.87)
        self.assertEqual(result["microbe"], "Prevotella nigrescens")
        self.assertEqual(result["radiomic_feature"], "GLCM_Correlation")

    def test_clamps_r_value_to_valid_range(self) -> None:
        raw = '{"candidate_r": 1.5, "panel_id": "main"}'
        result = _parse_qwen_output(raw)
        self.assertAlmostEqual(result["candidate_r"], 1.0)

    def test_null_candidate_r_when_no_microbe_axis(self) -> None:
        raw = '{"candidate_r": null, "panel_id": "main", "microbe": null, "radiomic_feature": "GLCM_Entropy"}'
        result = _parse_qwen_output(raw)
        self.assertIsNone(result["candidate_r"])

    def test_extracts_json_from_markdown_wrapper(self) -> None:
        raw = '```json\n{"candidate_r": 0.42, "panel_id": "B"}\n```'
        obj = _extract_first_json_object(raw)
        self.assertAlmostEqual(obj["candidate_r"], 0.42)

    def test_raises_on_empty_response(self) -> None:
        with self.assertRaises(ValueError):
            _extract_first_json_object("")

    def test_raises_on_no_json_object(self) -> None:
        with self.assertRaises(ValueError):
            _extract_first_json_object("No JSON here at all")

    def test_parse_forest_plot_output_with_ci(self) -> None:
        raw = '{"candidate_r": 2.1, "effect_type": "odds_ratio", "ci_lower": 1.3, "ci_upper": 3.4, "p_value": 0.002, "panel_id": "main", "microbe": "Fusobacterium", "radiomic_feature": null}'
        result = _parse_qwen_output(raw)
        self.assertAlmostEqual(result["candidate_r"], 2.1)
        self.assertEqual(result["effect_type"], "odds_ratio")
        self.assertAlmostEqual(result["ci_lower"], 1.3)
        self.assertAlmostEqual(result["ci_upper"], 3.4)

    def test_parse_forest_plot_or_not_clamped(self) -> None:
        # OR values > 1.0 must NOT be clamped to 1.0 (only correlation r values are clamped)
        raw = '{"candidate_r": 3.8, "effect_type": "odds_ratio", "ci_lower": 2.1, "ci_upper": 6.9}'
        result = _parse_qwen_output(raw)
        self.assertAlmostEqual(result["candidate_r"], 3.8)


class TestBuildPromptForest(unittest.TestCase):
    def test_prompt_asks_for_effect_type(self) -> None:
        prompt = _build_prompt_forest("Forest plot of OR for gut microbiota and tumor stage.")
        self.assertIn("effect_type", prompt)

    def test_prompt_asks_for_ci(self) -> None:
        prompt = _build_prompt_forest("Forest plot of HR for Bacteroides and survival.")
        self.assertIn("ci_lower", prompt)
        self.assertIn("ci_upper", prompt)

    def test_prompt_includes_caption(self) -> None:
        caption = "UNIQUE_FOREST_CAPTION_XYZ"
        prompt = _build_prompt_forest(caption)
        self.assertIn(caption, prompt)

    def test_dispatcher_routes_forest_plot(self) -> None:
        prompt = _build_prompt("some caption", topology="forest_plot")
        self.assertIn("ci_lower", prompt)

    def test_dispatcher_routes_heatmap(self) -> None:
        prompt = _build_prompt("correlation heatmap", topology="heatmap")
        self.assertIn("MICROBIAL TAXA", prompt)


class TestBuildPromptScatter(unittest.TestCase):
    def test_prompt_asks_for_r_value(self) -> None:
        prompt = _build_prompt_scatter("Scatter plot of Spearman r between Prevotella and CT entropy.")
        self.assertIn("candidate_r", prompt)

    def test_prompt_includes_caption(self) -> None:
        caption = "UNIQUE_SCATTER_CAPTION_ABC"
        prompt = _build_prompt_scatter(caption)
        self.assertIn(caption, prompt)

    def test_dispatcher_routes_scatter_plot(self) -> None:
        prompt = _build_prompt("scatter caption", topology="scatter_plot")
        self.assertIn("candidate_r", prompt)


if __name__ == "__main__":
    unittest.main()
