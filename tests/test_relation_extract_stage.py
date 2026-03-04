import unittest

from src.relation_extract_stage import run_relation_extraction


class TestRelationExtractStage(unittest.TestCase):
    def test_run_with_heuristic_backend(self) -> None:
        input_rows = [
            {
                "pmid": "101",
                "microbe": "lactobacillus",
                "disease": "obesity",
                "sentence": "Lactobacillus reduced obesity markers and showed protective effects.",
                "impact_factor": 5.0,
                "quartile": "Q1",
            },
            {
                "pmid": "101",
                "microbe": "lactobacillus",
                "disease": "obesity",
                "sentence": "Lactobacillus reduced obesity markers in repeat analysis.",
                "impact_factor": 5.0,
                "quartile": "Q1",
            },
        ]

        predictions, aggregated, strengths = run_relation_extraction(
            input_rows=input_rows,
            backend_name="heuristic",
            model_family="biomistral_7b",
            model_id=None,
            device="cpu",
            temperatures=[0.5, 0.6, 0.7],
            max_new_tokens=8,
            require_complete_consistency=True,
        )

        self.assertEqual(len(predictions), 2)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(len(strengths), 1)
        self.assertTrue(aggregated[0]["accepted"])


if __name__ == "__main__":
    unittest.main()
