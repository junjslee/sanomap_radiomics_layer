"""Unit tests for src/vision_gates.py — caption, colorbar-detect, range-sanity."""
from __future__ import annotations

from src.vision_gates import (
    caption_gate,
    range_sanity_gate,
    run_all_gates,
)


# --------------------------------------------------------------------------- #
#  caption_gate
# --------------------------------------------------------------------------- #

class TestCaptionGate:
    def test_pass_on_spearman(self):
        r = caption_gate("Heatmap of Spearman's correlation between microbes and features.")
        assert r.passed
        assert r.gate == "caption"

    def test_pass_on_pearson(self):
        r = caption_gate("Pearson correlation matrix of taxa abundance.")
        assert r.passed

    def test_pass_on_correlation_matrix(self):
        r = caption_gate("Figure 3. Correlation matrix highlighting microbe-feature pairs.")
        assert r.passed

    def test_pass_on_r_equals(self):
        r = caption_gate("Scatter plot showing relationship; r = 0.42 (p = 0.001).")
        assert r.passed

    def test_pass_on_rho(self):
        r = caption_gate("Annotated rho = -0.41 between Indole and feature X.")
        assert r.passed

    def test_fail_on_empty(self):
        r = caption_gate("")
        assert not r.passed
        assert r.reason == "caption_missing"

    def test_fail_on_none(self):
        r = caption_gate(None)
        assert not r.passed
        assert r.reason == "caption_missing"

    def test_fail_on_no_correlation_vocab(self):
        r = caption_gate("Workflow diagram showing study design and sample collection.")
        assert not r.passed
        assert r.reason == "no_correlation_vocabulary"

    def test_fail_on_lfc_even_if_correlation_word_present(self):
        # Negative tokens auto-fail even when "correlation" appears.
        r = caption_gate("Heatmap of log fold change values; correlation analysis follows.")
        assert not r.passed
        assert r.reason == "non_r_quantity_indicated"

    def test_fail_on_log2(self):
        r = caption_gate("log2 fold change of taxa relative to control. Pearson follow-up in S2.")
        assert not r.passed
        assert r.reason == "non_r_quantity_indicated"

    def test_fail_on_zscore(self):
        r = caption_gate("z-score-normalized abundance; correlation matrix elsewhere.")
        assert not r.passed


# --------------------------------------------------------------------------- #
#  range_sanity_gate
# --------------------------------------------------------------------------- #

class TestRangeSanity:
    def test_pass_within_default_pearson(self):
        r = range_sanity_gate(0.42)
        assert r.passed

    def test_pass_at_boundary(self):
        r = range_sanity_gate(1.0)
        assert r.passed  # tol covers it

    def test_fail_above_unity(self):
        r = range_sanity_gate(1.06)
        assert not r.passed
        assert r.reason == "out_of_range"

    def test_pass_negative_within(self):
        r = range_sanity_gate(-0.6)
        assert r.passed

    def test_fail_below_minus_unity(self):
        r = range_sanity_gate(-1.06)
        assert not r.passed

    def test_fail_on_none(self):
        r = range_sanity_gate(None)
        assert not r.passed
        assert r.reason == "proposed_r_missing"

    def test_tighter_colorbar_catches_pmc7889099_case(self):
        # PMC7889099 colorbar is ±0.23; proposer claimed +0.78.
        r = range_sanity_gate(0.78, colorbar_min=-0.23, colorbar_max=0.23)
        assert not r.passed
        assert r.detail and r.detail["excess"] > 0.0

    def test_tighter_colorbar_passes_within(self):
        r = range_sanity_gate(-0.18, colorbar_min=-0.23, colorbar_max=0.23)
        assert r.passed

    def test_asymmetric_colorbar(self):
        # Some colorbars are asymmetric e.g. -0.2 to +0.5.
        # Threshold is max(|min|, |max|) = 0.5; -0.45 is within.
        r = range_sanity_gate(-0.45, colorbar_min=-0.2, colorbar_max=0.5)
        assert r.passed

    def test_asymmetric_colorbar_negative_excess(self):
        # Same colorbar, -0.6 should fail because |0.6| > 0.5 + tol.
        r = range_sanity_gate(-0.6, colorbar_min=-0.2, colorbar_max=0.5)
        assert not r.passed


# --------------------------------------------------------------------------- #
#  run_all_gates — composite short-circuit
# --------------------------------------------------------------------------- #

class TestRunAllGates:
    def test_short_circuit_on_caption_fail(self, tmp_path):
        # Even if image were valid, caption failure prevents image inspection.
        result = run_all_gates(
            image_path=str(tmp_path / "nonexistent.jpg"),
            proposal={"candidate_r": 0.5},
            caption="Workflow diagram only.",
            colorbar_range=(-1.0, 1.0),
        )
        assert not result.passed
        assert result.failing_gate == "caption"
        assert len(result.results) == 1  # short-circuited; gate 2/3 not run

    def test_short_circuit_on_colorbar_fail(self, tmp_path):
        # Caption passes but image is missing → colorbar gate fails next.
        result = run_all_gates(
            image_path=str(tmp_path / "missing.jpg"),
            proposal={"candidate_r": 0.5},
            caption="Pearson correlation heatmap of microbes.",
            colorbar_range=(-1.0, 1.0),
        )
        assert not result.passed
        assert result.failing_gate == "colorbar_detect"
        assert len(result.results) == 2

    def test_range_gate_runs_only_when_first_two_pass(self, tmp_path):
        # Manufacture: caption fails → range gate never evaluates → r=99.0 OK.
        result = run_all_gates(
            image_path=str(tmp_path / "x.jpg"),
            proposal={"candidate_r": 99.0},
            caption=None,
            colorbar_range=(-1.0, 1.0),
        )
        assert result.failing_gate == "caption"
        assert all(r.gate != "range_sanity" for r in result.results)
