import unittest

from src.verify_heatmap import verify_proposals


class TestVerifyHeatmapBatch(unittest.TestCase):
    def test_missing_image_and_candidate_are_rejected_structurally(self) -> None:
        proposals = [
            {
                "proposal_id": "p1",
                "pmid": "123",
                "figure_id": "f1",
                "candidate_r": 0.3,
            },
            {
                "proposal_id": "p2",
                "pmid": "124",
                "figure_id": "f2",
            },
        ]
        out = verify_proposals(
            proposals=proposals,
            figure_lookup={},
            tolerance=0.05,
            r_min=-1.0,
            r_max=1.0,
            min_support_pixels=20,
            min_support_fraction=0.001,
        )
        self.assertEqual(len(out), 2)

        by_id = {row["proposal_id"]: row for row in out}
        self.assertEqual(by_id["p1"]["reason_code"], "missing_image")
        self.assertFalse(by_id["p1"]["pass_fail"])
        self.assertEqual(by_id["p2"]["reason_code"], "missing_candidate_r")
        self.assertFalse(by_id["p2"]["pass_fail"])


if __name__ == "__main__":
    unittest.main()
