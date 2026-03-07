import unittest

from src.augment_relations_mixtral import (
    MixtralAugmenter,
    _extract_seed_fields,
    build_augmented_rows,
)


class TestAugmentRelationsMixtral(unittest.TestCase):
    def test_extract_seed_fields(self) -> None:
        row = {
            "pmid": "100",
            "sentence": "Escherichia coli increases colitis severity.",
            "microbe": "Escherichia coli",
            "disease": "colitis",
            "label": "positive",
        }
        seed = _extract_seed_fields(row, 0)
        self.assertEqual(seed["pmid"], "100")
        self.assertEqual(seed["label"], "positive")
        self.assertTrue(seed["seed_id"])

    def test_template_augmentation_outputs_three_rows_per_seed(self) -> None:
        seeds = [
            {
                "seed_id": "s1",
                "pmid": "100",
                "sentence": "Escherichia coli increases colitis severity.",
                "microbe": "Escherichia coli",
                "disease": "colitis",
                "label": "positive",
            }
        ]
        augmenter = MixtralAugmenter(
            model_id="mistralai/Mixtral-8x7B-v0.1",
            backend="template",
            temperature=0.7,
            max_new_tokens=64,
        )
        rows = build_augmented_rows(
            seeds=seeds,
            augmenter=augmenter,
            prompt_id="mixtral_relation_aug_v1",
        )

        self.assertEqual(len(rows), 3)
        aug_types = {r.augmentation_type for r in rows}
        self.assertEqual(
            aug_types,
            {"paraphrase_1", "paraphrase_2", "entity_swap_template"},
        )


if __name__ == "__main__":
    unittest.main()
