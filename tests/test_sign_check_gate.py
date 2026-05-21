"""Tests for the E1 sign-check gate (`src/vision_gates.py`).

The sign-check is the wrong-sign-hallucination guard added to close the gap
that range_sanity cannot catch: a proposer that hallucinates a bbox pointing
at a same-color cell elsewhere in the figure will pass dual-consensus
because both verifiers share the bbox. The sign-check asks the VLM
independently which colorbar hemisphere the cell sits in and rejects
mismatches.

Tests here cover the pure-function gate logic (no VLM call); the VLM
extraction helper (`extract_color_hemisphere_via_vlm`) is exercised with a
mocked HTTP poster so the suite stays offline-safe.
"""

from __future__ import annotations

import json
import unittest

from src.vision_gates import (
    SIGN_CHECK_NEAR_ZERO_TOL,
    extract_color_hemisphere_via_vlm,
    sign_check_gate,
)


class TestSignCheckLogic(unittest.TestCase):
    # --- happy paths --------------------------------------------------------

    def test_positive_r_and_positive_hemisphere_passes(self):
        r = sign_check_gate(proposed_r=0.95, observed_hemisphere="positive")
        self.assertTrue(r.passed)
        self.assertEqual(r.gate, "sign_check")
        self.assertEqual(r.reason, "sign_agrees")

    def test_negative_r_and_negative_hemisphere_passes(self):
        r = sign_check_gate(proposed_r=-0.43, observed_hemisphere="negative")
        self.assertTrue(r.passed)
        self.assertEqual(r.reason, "sign_agrees")

    # --- the load-bearing failure modes -------------------------------------

    def test_negative_r_with_positive_hemisphere_fails(self):
        # This is the firmicutes→Total fat % retraction shape:
        # proposer said -0.95, the cell was deep red (positive hemisphere).
        r = sign_check_gate(proposed_r=-0.95, observed_hemisphere="positive")
        self.assertFalse(r.passed)
        self.assertEqual(r.reason, "sign_disagrees")
        self.assertEqual(r.detail["proposed_sign"], "negative")
        self.assertEqual(r.detail["observed_hemisphere"], "positive")

    def test_positive_r_with_negative_hemisphere_fails(self):
        # Mirror shape: proposer overclaims positive on a blue cell.
        r = sign_check_gate(proposed_r=0.78, observed_hemisphere="negative")
        self.assertFalse(r.passed)
        self.assertEqual(r.reason, "sign_disagrees")

    # --- near-zero / inconclusive observations -------------------------------

    def test_near_zero_r_passes_regardless_of_hemisphere(self):
        # |r| < 0.10 (the default near-zero tol) → proposed_sign = neutral
        # → pass on any hemisphere observation (avoids over-blocking
        # low-signal cells where hemisphere reads are inherently noisy).
        for hemi in ("positive", "negative", "neutral", "unknown"):
            r = sign_check_gate(proposed_r=0.05, observed_hemisphere=hemi)
            self.assertTrue(
                r.passed,
                f"near-zero r with hemisphere={hemi} should pass; got {r}"
            )

    def test_unknown_or_neutral_observation_passes(self):
        # When the VLM can't read the cell color, we pass with a recorded
        # reason — sign-check is meant to catch CONFIDENT wrong-sign
        # hallucinations, not punish low-signal images.
        r = sign_check_gate(proposed_r=0.85, observed_hemisphere="unknown")
        self.assertTrue(r.passed)
        self.assertEqual(r.reason, "near_zero_or_inconclusive_pass")

        r2 = sign_check_gate(proposed_r=-0.85, observed_hemisphere="neutral")
        self.assertTrue(r2.passed)
        self.assertEqual(r2.reason, "near_zero_or_inconclusive_pass")

    # --- input validation ---------------------------------------------------

    def test_proposed_r_none_fails_with_typed_reason(self):
        r = sign_check_gate(proposed_r=None, observed_hemisphere="positive")
        self.assertFalse(r.passed)
        self.assertEqual(r.reason, "proposed_r_missing")

    def test_proposed_r_non_numeric_fails(self):
        r = sign_check_gate(proposed_r="banana", observed_hemisphere="positive")
        self.assertFalse(r.passed)
        self.assertEqual(r.reason, "proposed_r_not_numeric")

    def test_unrecognized_hemisphere_string_passes_with_typed_reason(self):
        # Be defensive — if the VLM returns a hemisphere outside the
        # vocabulary, we don't pretend to know better and over-fail.
        r = sign_check_gate(proposed_r=0.95, observed_hemisphere="warmish")
        self.assertTrue(r.passed)
        self.assertEqual(r.reason, "observed_hemisphere_unrecognized_pass")

    def test_case_insensitive_hemisphere_string(self):
        r = sign_check_gate(proposed_r=-0.5, observed_hemisphere="NEGATIVE")
        self.assertTrue(r.passed)
        self.assertEqual(r.reason, "sign_agrees")

    def test_custom_near_zero_tol_overrides_default(self):
        # With a stricter tol of 0.01, r=0.05 is no longer "neutral" and
        # the gate must enforce sign agreement.
        r = sign_check_gate(
            proposed_r=0.05, observed_hemisphere="negative",
            near_zero_tol=0.01,
        )
        self.assertFalse(r.passed)
        self.assertEqual(r.reason, "sign_disagrees")

    def test_default_near_zero_tol_constant_is_documented(self):
        # If someone changes the default in the module, the test pins it so
        # the manuscript's threshold table doesn't silently drift.
        self.assertEqual(SIGN_CHECK_NEAR_ZERO_TOL, 0.10)


class _StubConfig:
    """Mimics the verify_vision_dual config dataclass — only the fields
    extract_color_hemisphere_via_vlm reads."""
    model_id = "qwen2.5vl:3b"
    temperature = 0.0
    timeout_s = 30
    api_base_url = "http://localhost:11434/v1"
    api_key = None


class TestHemisphereVLMExtract(unittest.TestCase):
    """Mocked-HTTP tests for the VLM helper. No network or image deps."""

    def _fake_response(self, hemisphere: str, reason: str = "test"):
        body = {
            "choices": [{
                "message": {"content": json.dumps({
                    "hemisphere": hemisphere,
                    "reason": reason,
                })}
            }]
        }
        return json.dumps(body).encode("utf-8")

    def _fake_poster_returning(self, payload_bytes: bytes):
        def _post(url, headers, body, timeout):
            return payload_bytes
        return _post

    def test_extracts_positive_hemisphere(self):
        # Patch _encode_image_data_uri so we don't actually need a file.
        from unittest.mock import patch
        with patch("src.verify_vision_dual._encode_image_data_uri",
                   return_value="data:image/jpeg;base64,fake"):
            hemi, reason = extract_color_hemisphere_via_vlm(
                image_path="any.jpg",
                bbox=(10, 10, 30, 30),
                config=_StubConfig(),
                http_post=self._fake_poster_returning(
                    self._fake_response("positive", "red_warm")
                ),
            )
        self.assertEqual(hemi, "positive")
        self.assertEqual(reason, "red_warm")

    def test_extracts_negative_hemisphere(self):
        from unittest.mock import patch
        with patch("src.verify_vision_dual._encode_image_data_uri",
                   return_value="data:image/jpeg;base64,fake"):
            hemi, _ = extract_color_hemisphere_via_vlm(
                image_path="any.jpg",
                bbox=[0, 0, 10, 10],
                config=_StubConfig(),
                http_post=self._fake_poster_returning(
                    self._fake_response("negative", "deep_blue")
                ),
            )
        self.assertEqual(hemi, "negative")

    def test_invalid_bbox_returns_unknown(self):
        hemi, reason = extract_color_hemisphere_via_vlm(
            image_path="any.jpg",
            bbox=(1, 2, 3),  # only 3 elements
            config=_StubConfig(),
            http_post=lambda *a, **kw: b"unused",
        )
        self.assertEqual(hemi, "unknown")
        self.assertEqual(reason, "bbox_invalid")

    def test_unrecognized_hemisphere_in_response_returns_unknown(self):
        from unittest.mock import patch
        with patch("src.verify_vision_dual._encode_image_data_uri",
                   return_value="data:image/jpeg;base64,fake"):
            hemi, reason = extract_color_hemisphere_via_vlm(
                image_path="any.jpg",
                bbox=(0, 0, 10, 10),
                config=_StubConfig(),
                http_post=self._fake_poster_returning(
                    self._fake_response("magenta_ish", "n/a")
                ),
            )
        self.assertEqual(hemi, "unknown")
        self.assertEqual(reason, "hemisphere_unrecognized")


if __name__ == "__main__":
    unittest.main()
