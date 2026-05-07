"""Three deterministic gates that run BEFORE the dual-verifier consensus.

These gates close a structural hole that the dual-verifier alone cannot:
the pixel HSV verifier and the independent VLM verifier both consume
the proposer's bbox and r-value. When the proposer hallucinates both,
the verifiers can only check internal consistency, not source-grounding.
A proposer that fabricates ``r=+0.78`` for a figure whose colorbar is
``±0.23`` will be silently passed by the dual gate when the predicted
cell coincidentally maps to a colorbar position consistent with +0.78
*on the assumed default ±1.0 scale*.

These gates remove the most common hallucination shapes for free
(deterministic, no paid LLM call) before the verifier pair runs:

  Gate 1 — caption_gate
      The figure caption must contain explicit correlation-heatmap
      vocabulary (Spearman / Pearson / correlation matrix / r= / ρ=).
      Captions that only mention LFC / log fold change / z-score
      auto-fail the gate even if a positive token appears.

  Gate 2 — colorbar_detect_gate
      A gradient colorbar legend must be detectable in the figure.
      Reuses the existing ``_detect_legend`` from verify_heatmap.
      Network diagrams, pathway diagrams, and figures without a
      colorbar fail here.

  Gate 3 — range_sanity_gate
      ``|proposed_r| ≤ max(|colorbar_min|, |colorbar_max|) + tol``.
      Catches values exceeding the figure's actual colorbar range.
      Default colorbar bounds (-1.0, +1.0) used when no override is
      supplied; callers SHOULD pass an extracted (cmin, cmax) when
      available so out-of-range hallucinations on tighter colorbars
      (e.g., ±0.23 in PMC7889099) are caught.

Failure of any gate produces a typed reject before the proposer's bbox
is ever forwarded to the verifier pair.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass
class GateResult:
    passed: bool
    gate: str
    reason: str
    detail: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "gate": self.gate,
            "reason": self.reason,
            "detail": self.detail or {},
        }


# --------------------------------------------------------------------------- #
#  Gate 1 — caption gate
# --------------------------------------------------------------------------- #

# Positive tokens (any one matches → caption is heatmap-suggestive)
_POSITIVE_PATTERNS = [
    r"correlation\s+matrix",
    r"correlation\s+heatmap",
    r"\bspearman'?s?\b",
    r"\bpearson'?s?\b",
    r"\brho\b\s*=",
    r"ρ\s*=",
    r"\br\s*=",          # "r = -0.43"
    r"\br\s*-?\s*value",
    r"\bcorrelation\s+coefficient",
    r"\bcorrelogram\b",
]

# Auto-fail tokens (caption describes a non-r quantity → reject regardless)
_NEGATIVE_PATTERNS = [
    r"log\s*fold\s*change",
    r"\blfc\b",
    r"log\s*2\s*fold",
    r"\blog2fc\b",
    r"\bz\s*-?\s*score",
    r"\bp\s*-?\s*value\s+matrix",
    r"differential\s+(abundance|expression)",
]


def caption_gate(caption: str | None) -> GateResult:
    """Pass when caption asserts a Pearson / Spearman correlation context."""
    if not caption or not caption.strip():
        return GateResult(
            passed=False, gate="caption",
            reason="caption_missing",
            detail={"caption_length": 0},
        )
    text = caption.lower()

    matched_neg = [p for p in _NEGATIVE_PATTERNS if re.search(p, text, re.IGNORECASE)]
    if matched_neg:
        return GateResult(
            passed=False, gate="caption",
            reason=f"non_r_quantity_indicated",
            detail={"matched_negative": matched_neg},
        )

    matched_pos = [p for p in _POSITIVE_PATTERNS if re.search(p, text, re.IGNORECASE)]
    if not matched_pos:
        return GateResult(
            passed=False, gate="caption",
            reason="no_correlation_vocabulary",
            detail={"caption_excerpt": caption[:160]},
        )

    return GateResult(
        passed=True, gate="caption",
        reason="correlation_vocabulary_matched",
        detail={"matched_positive": matched_pos[:3]},
    )


# --------------------------------------------------------------------------- #
#  Gate 2 — colorbar detection gate
# --------------------------------------------------------------------------- #

def colorbar_detect_gate(
    image_path: str,
    legend_bbox: tuple[int, int, int, int] | None = None,
    min_confidence: float = 0.5,
) -> GateResult:
    """Pass when a gradient colorbar legend is detectable in the figure.

    Reuses the legend detector from ``src.verify_heatmap`` so the gate
    is consistent with the downstream pixel verifier.
    """
    if not Path(image_path).exists():
        return GateResult(
            passed=False, gate="colorbar_detect",
            reason="image_missing",
            detail={"image_path": image_path},
        )
    try:
        from src.verify_heatmap import _detect_legend, _load_rgb, _rgb_to_hsv, _require_deps
        _require_deps()
    except Exception as exc:  # noqa: BLE001
        return GateResult(
            passed=False, gate="colorbar_detect",
            reason=f"deps_unavailable:{type(exc).__name__}",
        )

    try:
        rgb = _load_rgb(image_path)
        hsv = _rgb_to_hsv(rgb)
        result = _detect_legend(rgb, hsv, legend_bbox)
    except Exception as exc:  # noqa: BLE001
        return GateResult(
            passed=False, gate="colorbar_detect",
            reason=f"detection_error:{type(exc).__name__}",
            detail={"err": str(exc)[:140]},
        )

    if result is None:
        return GateResult(
            passed=False, gate="colorbar_detect",
            reason="legend_not_found",
        )

    detected_bbox, orientation, confidence = result
    if confidence < min_confidence:
        return GateResult(
            passed=False, gate="colorbar_detect",
            reason="low_confidence",
            detail={"confidence": float(confidence),
                    "min_confidence": min_confidence},
        )

    return GateResult(
        passed=True, gate="colorbar_detect",
        reason="legend_detected",
        detail={
            "bbox": [int(v) for v in detected_bbox],
            "orientation": orientation,
            "confidence": float(confidence),
        },
    )


# --------------------------------------------------------------------------- #
#  Gate 3 — colorbar-range sanity gate
# --------------------------------------------------------------------------- #

def range_sanity_gate(
    proposed_r: float | None,
    colorbar_min: float = -1.0,
    colorbar_max: float = 1.0,
    tol: float = 0.05,
) -> GateResult:
    """Pass when ``|proposed_r| ≤ max(|cmin|, |cmax|) + tol``.

    Default bounds are Pearson r (-1, +1). Callers should override with
    the figure's actual colorbar tick range when known — otherwise the
    gate only catches values that exceed unity in absolute terms (which
    still kills a meaningful fraction of LFC / log2-fold mis-labellings).
    """
    if proposed_r is None:
        return GateResult(
            passed=False, gate="range_sanity",
            reason="proposed_r_missing",
        )
    abs_max = max(abs(colorbar_min), abs(colorbar_max))
    threshold = abs_max + tol
    if abs(proposed_r) > threshold:
        return GateResult(
            passed=False, gate="range_sanity",
            reason="out_of_range",
            detail={
                "proposed_r": float(proposed_r),
                "colorbar_range": [float(colorbar_min), float(colorbar_max)],
                "threshold": float(threshold),
                "excess": float(abs(proposed_r) - threshold),
            },
        )
    return GateResult(
        passed=True, gate="range_sanity",
        reason="within_range",
        detail={
            "proposed_r": float(proposed_r),
            "colorbar_range": [float(colorbar_min), float(colorbar_max)],
        },
    )


# --------------------------------------------------------------------------- #
#  Composite runner
# --------------------------------------------------------------------------- #

@dataclass
class GateChainResult:
    passed: bool                 # True iff all three gates passed
    failing_gate: str | None     # name of the first failing gate, or None
    results: list[GateResult]    # full per-gate trace

    def as_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.passed,
            "failing_gate": self.failing_gate,
            "gate_results": [r.as_dict() for r in self.results],
        }


def run_all_gates(
    *,
    image_path: str,
    proposal: Mapping[str, Any],
    caption: str | None,
    colorbar_range: tuple[float, float] = (-1.0, 1.0),
    range_tol: float = 0.05,
) -> GateChainResult:
    """Run gates in order; short-circuit on first failure."""
    results: list[GateResult] = []

    g1 = caption_gate(caption)
    results.append(g1)
    if not g1.passed:
        return GateChainResult(passed=False, failing_gate="caption", results=results)

    legend_bbox: tuple[int, int, int, int] | None = None
    raw_legend_bbox = proposal.get("legend_bbox")
    if isinstance(raw_legend_bbox, (list, tuple)) and len(raw_legend_bbox) == 4:
        a, b, c, d = (int(v) for v in raw_legend_bbox)
        legend_bbox = (a, b, c, d)
    g2 = colorbar_detect_gate(image_path, legend_bbox=legend_bbox)
    results.append(g2)
    if not g2.passed:
        return GateChainResult(passed=False, failing_gate="colorbar_detect", results=results)

    proposed_r = proposal.get("candidate_r", proposal.get("r_value", proposal.get("value")))
    g3 = range_sanity_gate(
        proposed_r=proposed_r,
        colorbar_min=colorbar_range[0],
        colorbar_max=colorbar_range[1],
        tol=range_tol,
    )
    results.append(g3)
    if not g3.passed:
        return GateChainResult(passed=False, failing_gate="range_sanity", results=results)

    return GateChainResult(passed=True, failing_gate=None, results=results)


__all__ = [
    "GateResult",
    "GateChainResult",
    "caption_gate",
    "colorbar_detect_gate",
    "range_sanity_gate",
    "run_all_gates",
    "extract_colorbar_range_via_vlm",
]


# --------------------------------------------------------------------------- #
#  Optional helper — VLM-based colorbar range extraction
# --------------------------------------------------------------------------- #

_RANGE_EXTRACT_SYSTEM = (
    "You are a quantitative figure inspector. Read the END tick labels of "
    "the gradient colorbar legend in this figure. Return strict JSON only."
)

_RANGE_EXTRACT_USER = (
    "Read the colorbar legend on this figure. Identify the SMALLEST and "
    "LARGEST tick label values on the colorbar (these are the bounds of "
    "the gradient).\n"
    "\n"
    "RULES\n"
    "  - If you cannot see a colorbar with numeric tick labels, reply "
    "    {\"min\": null, \"max\": null, \"reason\": \"no_numeric_ticks\"}.\n"
    "  - Do NOT guess. Read the actual numbers printed at the colorbar ends.\n"
    "  - Do NOT return a default like -1, 1 unless those are literally on the colorbar.\n"
    "\n"
    "OUTPUT (strict JSON, single object, no markdown)\n"
    "  {\"min\": <number or null>, \"max\": <number or null>, "
    "   \"reason\": \"<2-6 word rationale>\"}"
)


def extract_colorbar_range_via_vlm(
    image_path: str,
    config: Any,
    http_post: Any = None,
) -> tuple[float | None, float | None, str]:
    """Ask the VLM to read the colorbar's end-tick values.

    Returns (min, max, reason). On any failure mode (missing colorbar,
    parse error, network error), returns (None, None, <reason>).

    The caller decides what to do with None/None — typically fall back to
    default ±1.0 or fail the range_sanity_gate explicitly.
    """
    from src.verify_vision_dual import (
        _encode_image_data_uri,
        _completion_url,
        _default_http_post,
        _parse_verifier_response,
    )
    import json
    from urllib import error as urlerror

    body = {
        "model": config.model_id,
        "temperature": float(config.temperature),
        "max_tokens": 96,
        "messages": [
            {"role": "system", "content": _RANGE_EXTRACT_SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": _RANGE_EXTRACT_USER},
                {"type": "image_url",
                 "image_url": {"url": _encode_image_data_uri(image_path)}},
            ]},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    poster = http_post or _default_http_post
    try:
        raw = poster(_completion_url(config.api_base_url), headers,
                     json.dumps(body).encode("utf-8"), config.timeout_s)
    except (urlerror.HTTPError, urlerror.URLError) as exc:
        return None, None, f"network_error:{type(exc).__name__}"
    payload = json.loads(raw.decode("utf-8"))
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices:
        return None, None, "missing_choices"
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        text = "\n".join(p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text")
    else:
        text = str(content or "")
    parsed = _parse_verifier_response(text)
    cmin = parsed.get("min")
    cmax = parsed.get("max")
    reason = str(parsed.get("reason") or "vlm_extracted")
    if cmin is None or cmax is None:
        return None, None, reason
    try:
        cmin_f = float(cmin)
        cmax_f = float(cmax)
    except (TypeError, ValueError):
        return None, None, "non_numeric_response"
    if cmin_f > cmax_f:
        cmin_f, cmax_f = cmax_f, cmin_f
    return cmin_f, cmax_f, reason
