import unittest

from src.model_backends import (
    NEGATIVE,
    POSITIVE,
    UNRELATED,
    build_minerva_prompt_messages,
    format_prompt_for_model,
    normalize_relation_label,
)


class TestModelBackends(unittest.TestCase):
    def test_normalize_relation_label_handles_alternative_tokens(self) -> None:
        self.assertEqual(normalize_relation_label("a"), POSITIVE)
        self.assertEqual(normalize_relation_label("B"), NEGATIVE)
        self.assertEqual(normalize_relation_label("d"), UNRELATED)

    def test_minerva_prompt_builder(self) -> None:
        system, user = build_minerva_prompt_messages(
            sentence="Evidence sentence",
            microbe="E.coli",
            disease="diabetes",
        )
        self.assertIn("expert microbiologist", system)
        self.assertIn("Evidence sentence", user)
        self.assertIn("E.coli", user)
        self.assertIn("diabetes", user)

    def test_model_family_prompt_formatting(self) -> None:
        prompt = format_prompt_for_model(
            system="sys",
            user="usr",
            model_family="mixtral_8x7b_instruct",
        )
        self.assertIn("[INST]", prompt)
        self.assertIn("sys", prompt)
        self.assertIn("usr", prompt)


if __name__ == "__main__":
    unittest.main()
