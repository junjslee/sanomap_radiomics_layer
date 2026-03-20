import unittest
from unittest import mock

from src.relation_extract_stage import filter_relation_input_rows, resolve_api_settings, run_relation_extraction


class TestRelationExtractStage(unittest.TestCase):
    def test_run_with_heuristic_backend(self) -> None:
        input_rows = [
            {
                "pmid": "101",
                "microbe": "lactobacillus",
                "subject_node_type": "Microbe",
                "subject_node": "lactobacillus",
                "disease": "obesity",
                "sentence": "Lactobacillus reduced obesity markers and showed protective effects.",
                "impact_factor": 5.0,
                "quartile": "Q1",
            },
            {
                "pmid": "101",
                "microbe": "lactobacillus",
                "subject_node_type": "Microbe",
                "subject_node": "lactobacillus",
                "disease": "obesity",
                "sentence": "Lactobacillus reduced obesity markers in repeat analysis.",
                "impact_factor": 5.0,
                "quartile": "Q1",
            },
            {
                "pmid": "101",
                "microbe": "bacteria",
                "subject_node_type": "Microbe",
                "subject_node": "bacteria",
                "disease": "obesity",
                "sentence": "Bacteria is linked to obesity.",
                "impact_factor": 5.0,
                "quartile": "Q1",
            },
        ]

        filtered_reasons: dict[str, int] = {}
        predictions, aggregated, strengths = run_relation_extraction(
            input_rows=input_rows,
            backend_name="heuristic",
            model_family="biomistral_7b",
            model_id=None,
            device="cpu",
            temperatures=[0.5, 0.6, 0.7],
            max_new_tokens=8,
            require_complete_consistency=True,
            filtered_reason_counts=filtered_reasons,
        )

        self.assertEqual(len(predictions), 2)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(len(strengths), 1)
        self.assertTrue(aggregated[0]["accepted"])
        self.assertIn("generic_microbe_term", filtered_reasons)
        self.assertIn("label_entropy", predictions[0])
        self.assertIn("zero_entropy", predictions[0])
        self.assertEqual(predictions[0]["subject_node_type"], "Microbe")
        self.assertEqual(predictions[0]["subject_node"], "lactobacillus")
        self.assertEqual(aggregated[0]["subject_node"], "lactobacillus")

    def test_filter_relation_input_rows_cleans_and_rejects_bad_spans(self) -> None:
        kept, reasons = filter_relation_input_rows(
            [
                {
                    "pmid": "201",
                    "microbe": "Escherichia coli abundance",
                    "subject_node_type": "Microbe",
                    "subject_node": "Escherichia coli abundance",
                    "disease": "liver cancer in this cohort",
                    "sentence": "Escherichia coli abundance was associated with liver cancer in this cohort.",
                },
                {
                    "pmid": "202",
                    "microbe": "##fidobacteria",
                    "subject_node_type": "Microbe",
                    "subject_node": "##fidobacteria",
                    "disease": "obesity",
                    "sentence": "##fidobacteria was associated with obesity.",
                },
            ]
        )

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["microbe"], "escherichia coli")
        self.assertEqual(kept[0]["subject_node"], "escherichia coli")
        self.assertEqual(kept[0]["disease"], "liver cancer")
        self.assertIn("subject_wordpiece_fragment", reasons)

    def test_filter_relation_input_rows_rejects_clause_like_disease_fragment(self) -> None:
        kept, reasons = filter_relation_input_rows(
            [
                {
                    "pmid": "203",
                    "microbe": "Fusobacteria were",
                    "subject_node_type": "Microbe",
                    "subject_node": "Fusobacteria were",
                    "disease": "indicators of body fat distribution and systemic inflammation",
                    "sentence": (
                        "Fusobacteria were associated with indicators of body fat distribution "
                        "and systemic inflammation."
                    ),
                }
            ]
        )

        self.assertEqual(kept, [])
        self.assertIn("disease_clause_like", reasons)

    def test_filter_relation_input_rows_trims_subject_taxonomy_and_disease_prefix(self) -> None:
        kept, reasons = filter_relation_input_rows(
            [
                {
                    "pmid": "204",
                    "microbe": "Proteobacteria phylum",
                    "subject_node_type": "Microbe",
                    "subject_node": "Proteobacteria phylum",
                    "disease": "and metabolic syndrome",
                    "sentence": "Proteobacteria phylum was reported in obesity and metabolic syndrome.",
                }
            ]
        )

        self.assertEqual(reasons, {})
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["microbe"], "proteobacteria")
        self.assertEqual(kept[0]["subject_node"], "proteobacteria")
        self.assertEqual(kept[0]["disease"], "metabolic syndrome")

    def test_filter_relation_input_rows_rejects_verb_led_disease_fragment(self) -> None:
        kept, reasons = filter_relation_input_rows(
            [
                {
                    "pmid": "205",
                    "microbe": "Clostridium symbiosum",
                    "subject_node_type": "Microbe",
                    "subject_node": "Clostridium symbiosum",
                    "disease": "reduces inflammation",
                    "sentence": "Clostridium symbiosum reduces inflammation in a mechanistic summary row.",
                }
            ]
        )

        self.assertEqual(kept, [])
        self.assertIn("disease_relation_language", reasons)

    def test_run_with_openai_compatible_backend(self) -> None:
        input_rows = [
            {
                "pmid": "301",
                "microbe": "lactobacillus",
                "subject_node_type": "Microbe",
                "subject_node": "lactobacillus",
                "disease": "obesity",
                "sentence": "Lactobacillus reduced obesity markers and showed protective effects.",
            }
        ]

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"negative"}}]}'

        with mock.patch("src.model_backends.urlrequest.urlopen", return_value=FakeResponse()):
            predictions, aggregated, strengths = run_relation_extraction(
                input_rows=input_rows,
                backend_name="openai_compatible",
                model_family="biomistral_7b",
                model_id=None,
                device="cpu",
                api_base_url="https://router.huggingface.co/v1",
                api_key="token",
                temperatures=[0.3],
                max_new_tokens=8,
                require_complete_consistency=True,
            )

        self.assertEqual(len(predictions), 1)
        self.assertEqual(predictions[0]["final_label"], "negative")
        self.assertEqual(predictions[0]["model_backend"], "openai_compatible")
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(len(strengths), 1)

    def test_resolve_api_settings_uses_gemini_specific_defaults(self) -> None:
        api_base_url, api_key = resolve_api_settings(
            model_id="gemini-2.5-flash-lite",
            cli_api_base_url=None,
            cli_api_key=None,
            environ={
                "RELATION_API_BASE_URL": "https://router.huggingface.co/v1",
                "HF_TOKEN": "hf_old_token",
                "GEMINI_API_KEY": "gemini_paid_key",
            },
        )

        self.assertEqual(api_base_url, "https://generativelanguage.googleapis.com/v1beta/openai")
        self.assertEqual(api_key, "gemini_paid_key")

    def test_resolve_api_settings_keeps_generic_env_for_non_gemini_models(self) -> None:
        api_base_url, api_key = resolve_api_settings(
            model_id="deepseek-ai/DeepSeek-V3-0324",
            cli_api_base_url=None,
            cli_api_key=None,
            environ={
                "RELATION_API_BASE_URL": "https://router.huggingface.co/v1",
                "HF_TOKEN": "hf_live_token",
            },
        )

        self.assertEqual(api_base_url, "https://router.huggingface.co/v1")
        self.assertEqual(api_key, "hf_live_token")


if __name__ == "__main__":
    unittest.main()
