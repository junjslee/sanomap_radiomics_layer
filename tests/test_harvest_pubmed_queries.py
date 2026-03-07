import unittest
from datetime import date

from src.harvest_pubmed import (
    BODYCOMP_DISEASE_ASSOCIATION_QUERY,
    BODYCOMP_DISEASE_QUERY,
    MICROBE_BODYCOMP_QUERY,
    MICROBE_IMAGING_ADJACENT_QUERY,
    MICROBE_RADIOMICS_STRICT_QUERY,
    QUERY_PROFILES,
    RADIOMICS_DISEASE_STRICT_QUERY,
    _dedupe_preserve_order,
    _midpoint_date,
    _parse_json_body,
)


class TestHarvestPubmedQueries(unittest.TestCase):
    def test_microbe_radiomics_strict_uses_signature_terms_without_seed_taxa(self) -> None:
        self.assertIn("alpha diversity[Title/Abstract]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertIn("microbiota composition[Title/Abstract]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertIn("glcm[Title/Abstract]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertIn("shape feature*[Title/Abstract]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertIn("review[Publication Type]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertIn("protocol[Title/Abstract]", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertNotIn("Fusobacterium nucleatum", MICROBE_RADIOMICS_STRICT_QUERY)
        self.assertNotIn("Akkermansia", MICROBE_RADIOMICS_STRICT_QUERY)

    def test_microbe_bodycomp_expands_bodycomp_vocabulary(self) -> None:
        self.assertIn("lean mass[Title/Abstract]", MICROBE_BODYCOMP_QUERY)
        self.assertIn("fat mass[Title/Abstract]", MICROBE_BODYCOMP_QUERY)
        self.assertIn("visceral adiposity[Title/Abstract]", MICROBE_BODYCOMP_QUERY)

    def test_microbe_imaging_adjacent_targets_adjacent_imaging_language(self) -> None:
        self.assertIn("CT change*[Title/Abstract]", MICROBE_IMAGING_ADJACENT_QUERY)
        self.assertIn("imaging phenotype[Title/Abstract]", MICROBE_IMAGING_ADJACENT_QUERY)
        self.assertIn("emphysema[Title/Abstract]", MICROBE_IMAGING_ADJACENT_QUERY)

    def test_radiomics_disease_query_includes_association_language(self) -> None:
        self.assertIn("associat*[Title/Abstract]", RADIOMICS_DISEASE_STRICT_QUERY)
        self.assertIn("correlat*[Title/Abstract]", RADIOMICS_DISEASE_STRICT_QUERY)

    def test_bodycomp_default_and_association_profiles_both_exist(self) -> None:
        self.assertIn("bodycomp_disease", QUERY_PROFILES)
        self.assertIn("bodycomp_disease_association", QUERY_PROFILES)
        self.assertNotEqual(BODYCOMP_DISEASE_QUERY, BODYCOMP_DISEASE_ASSOCIATION_QUERY)

    def test_imaging_adjacent_and_union_profiles_exist(self) -> None:
        self.assertIn("microbe_imaging_adjacent", QUERY_PROFILES)
        self.assertIn("microbe_imaging_phenotype", QUERY_PROFILES)
        self.assertIn("CT change*[Title/Abstract]", QUERY_PROFILES["microbe_imaging_phenotype"])

    def test_parse_json_body_tolerates_control_characters(self) -> None:
        payload = _parse_json_body('{"ok":"bad\\u0008value","count":1}')
        self.assertEqual(payload["count"], 1)

    def test_midpoint_date_splits_range(self) -> None:
        self.assertEqual(_midpoint_date(date(2020, 1, 1), date(2020, 1, 31)), date(2020, 1, 16))

    def test_dedupe_preserve_order(self) -> None:
        self.assertEqual(_dedupe_preserve_order(["1", "2", "1", "3", "2"]), ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
