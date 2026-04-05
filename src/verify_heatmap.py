from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record

try:
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    _HAS_BASE_DEPS = True
except ImportError:
    np = None  # type: ignore
    Image = None  # type: ignore
    _HAS_BASE_DEPS = False

try:
    import cv2  # type: ignore

    _HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore
    _HAS_CV2 = False


def _require_deps() -> None:
    if not _HAS_BASE_DEPS:
        raise RuntimeError("verify_heatmap requires numpy and Pillow")


def _parse_bbox(text: str | None) -> tuple[int, int, int, int] | None:
    if text is None:
        return None
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be 'x,y,w,h'")
    x, y, w, h = [int(p) for p in parts]
    if w <= 0 or h <= 0:
        raise ValueError("bbox width/height must be > 0")
    return x, y, w, h


def _coerce_bbox_list(value: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x, y, w, h = [int(v) for v in value]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _load_rgb(image_path: str) -> "np.ndarray":
    _require_deps()
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise RuntimeError("Expected RGB image")
    return arr


def _rgb_to_hsv(rgb: "np.ndarray") -> "np.ndarray":
    if _HAS_CV2:
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    pil_hsv = Image.fromarray(rgb, mode="RGB").convert("HSV")
    return np.array(pil_hsv, dtype=np.uint8)


def _colorful_mask(hsv: "np.ndarray", sat_min: int = 38, val_min: int = 30) -> "np.ndarray":
    # PIL HSV is 0..255 for all channels. OpenCV hue can be 0..179; sat/val are 0..255.
    sat = hsv[..., 1]
    val = hsv[..., 2]
    return (sat >= sat_min) & (val >= val_min)


def _clip_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = bbox
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return x, y, w, h


def _tight_bbox_from_mask(mask: "np.ndarray", origin_x: int, origin_y: int) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    x0 = int(xs.min()) + origin_x
    x1 = int(xs.max()) + origin_x
    y0 = int(ys.min()) + origin_y
    y1 = int(ys.max()) + origin_y
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def _candidate_regions(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int], str, float]]:
    ew = max(10, int(width * 0.18))
    eh = max(10, int(height * 0.18))
    return [
        ("right", (width - ew, 0, ew, height), "vertical", 0.08),
        ("left", (0, 0, ew, height), "vertical", 0.02),
        ("bottom", (0, height - eh, width, eh), "horizontal", 0.08),
        ("top", (0, 0, width, eh), "horizontal", 0.02),
    ]


def _color_progression_score(
    crop_rgb: "np.ndarray",
    crop_mask: "np.ndarray",
    orientation: str,
) -> tuple[float, float, float, float]:
    if orientation == "vertical":
        length = crop_rgb.shape[0]
        vectors = []
        for i in range(length):
            line_mask = crop_mask[i, :]
            if line_mask.sum() < 2:
                continue
            vectors.append(np.median(crop_rgb[i, line_mask, :], axis=0))
    else:
        length = crop_rgb.shape[1]
        vectors = []
        for i in range(length):
            line_mask = crop_mask[:, i]
            if line_mask.sum() < 2:
                continue
            vectors.append(np.median(crop_rgb[line_mask, i, :], axis=0))

    if len(vectors) < 8:
        return -1.0, 0.0, 0.0, 1.0

    profile = np.array(vectors, dtype=float)
    diffs = np.linalg.norm(np.diff(profile, axis=0), axis=1)
    progression = float(np.mean(diffs) / 255.0)
    endpoint_delta = float(np.linalg.norm(profile[-1, :] - profile[0, :]) / 255.0)
    active_fraction = float((diffs > 1.0).mean())

    if orientation == "vertical":
        cross_std = np.std(crop_rgb, axis=1).mean()
    else:
        cross_std = np.std(crop_rgb, axis=0).mean()

    uniformity_penalty = float(cross_std / 255.0)
    return progression, endpoint_delta, active_fraction, uniformity_penalty


def _detect_legend(
    rgb: "np.ndarray",
    hsv: "np.ndarray",
    legend_bbox: tuple[int, int, int, int] | None,
) -> tuple[tuple[int, int, int, int], str, float]:
    h, w = rgb.shape[:2]

    if legend_bbox is not None:
        clipped = _clip_bbox(legend_bbox, w, h)
        orientation = "vertical" if clipped[3] >= clipped[2] else "horizontal"
        return clipped, orientation, 1.0

    mask_all = _colorful_mask(hsv)
    best_score = -1e9
    best_bbox: tuple[int, int, int, int] | None = None
    best_orientation = "vertical"

    for _, bbox, orientation, edge_bonus in _candidate_regions(w, h):
        x, y, bw, bh = _clip_bbox(bbox, w, h)
        crop_rgb = rgb[y : y + bh, x : x + bw, :]
        crop_mask = mask_all[y : y + bh, x : x + bw]

        colorful_fraction = float(crop_mask.mean())
        if colorful_fraction < 0.03:
            continue

        tight = _tight_bbox_from_mask(crop_mask, x, y)
        if tight is None:
            continue

        tx, ty, tw, th = tight
        if tw < 4 or th < 4:
            continue

        tight_rgb = rgb[ty : ty + th, tx : tx + tw, :]
        tight_mask = mask_all[ty : ty + th, tx : tx + tw]
        progression, endpoint_delta, active_fraction, uniformity_penalty = _color_progression_score(
            tight_rgb,
            tight_mask,
            orientation,
        )
        if progression < 0:
            continue
        if endpoint_delta < 0.2:
            continue
        if active_fraction < 0.25:
            continue
        geom_bonus = 0.1 if (orientation == "vertical" and th > tw * 2) or (orientation == "horizontal" and tw > th * 2) else 0.0

        score = (
            1.2 * endpoint_delta
            + 0.5 * active_fraction
            + 0.3 * progression
            - 0.25 * uniformity_penalty
            + 0.05 * colorful_fraction
            + edge_bonus
            + geom_bonus
        )
        if score > best_score:
            best_score = score
            best_bbox = (tx, ty, tw, th)
            best_orientation = orientation

    if best_bbox is None or best_score < 0.12:
        raise RuntimeError("legend_not_found")

    confidence = float(max(0.0, min(1.0, best_score)))
    return best_bbox, best_orientation, confidence


def _extract_legend_profile(
    rgb: "np.ndarray",
    bbox: tuple[int, int, int, int],
    orientation: str,
    bins: int = 256,
) -> "np.ndarray":
    x, y, w, h = bbox
    crop = rgb[y : y + h, x : x + w, :].astype(float)

    if orientation == "vertical":
        idx = np.linspace(0, h - 1, bins).astype(int)
        profile = np.array([np.median(crop[i, :, :], axis=0) for i in idx], dtype=float)
    else:
        idx = np.linspace(0, w - 1, bins).astype(int)
        profile = np.array([np.median(crop[:, i, :], axis=0) for i in idx], dtype=float)

    # Simple deterministic smoothing.
    smoothed = profile.copy()
    smoothed[1:-1] = 0.25 * profile[:-2] + 0.5 * profile[1:-1] + 0.25 * profile[2:]
    return smoothed


def _sample_heatmap_pixels(
    rgb: "np.ndarray",
    hsv: "np.ndarray",
    legend_bbox: tuple[int, int, int, int],
    heatmap_bbox: tuple[int, int, int, int] | None,
    max_samples: int = 7000,
) -> tuple["np.ndarray", int]:
    h, w = rgb.shape[:2]
    mask = _colorful_mask(hsv)

    lx, ly, lw, lh = _clip_bbox(legend_bbox, w, h)
    mask[ly : ly + lh, lx : lx + lw] = False

    if heatmap_bbox is not None:
        hx, hy, hw, hh = _clip_bbox(heatmap_bbox, w, h)
        hm = np.zeros_like(mask, dtype=bool)
        hm[hy : hy + hh, hx : hx + hw] = True
        mask = mask & hm

    coords = np.argwhere(mask)
    total_candidates = int(coords.shape[0])
    if total_candidates == 0:
        return np.empty((0, 3), dtype=float), 0

    if total_candidates > max_samples:
        idx = np.linspace(0, total_candidates - 1, max_samples).astype(int)
        coords = coords[idx]

    pixels = rgb[coords[:, 0], coords[:, 1], :].astype(float)
    return pixels, total_candidates


def _infer_r_values(
    sampled_pixels: "np.ndarray",
    legend_profile: "np.ndarray",
    r_min: float,
    r_max: float,
) -> tuple["np.ndarray", "np.ndarray"]:
    dists = ((sampled_pixels[:, None, :] - legend_profile[None, :, :]) ** 2).sum(axis=2)
    nearest_idx = np.argmin(dists, axis=1)
    bins = legend_profile.shape[0]
    norm = nearest_idx.astype(float) / max(1, bins - 1)

    r_forward = r_min + norm * (r_max - r_min)
    r_reverse = r_max - norm * (r_max - r_min)
    return r_forward, r_reverse


def _verification_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def verify_forest_plot_association(
    effect_size: float,
    ci_lower: float | None,
    ci_upper: float | None,
    effect_type: str = "odds_ratio",
    null_value: float | None = None,
) -> dict[str, Any]:
    """CI-based verification for forest plots.

    Verified when the confidence interval does not cross the null value:
    - OR / HR: null = 1.0
    - beta / correlation: null = 0.0
    """
    if null_value is None:
        null_value = 1.0 if effect_type in {"odds_ratio", "hazard_ratio"} else 0.0

    if ci_lower is None or ci_upper is None:
        return {
            "verified": False,
            "pass_fail": False,
            "proposed_r": float(effect_size),
            "reason": "missing_ci",
            "reason_code": "missing_ci",
            "observed_range": [0.0, 0.0],
            "distance_metric": None,
            "nearest_r": None,
            "min_abs_error": None,
            "support_pixels": 0,
            "required_support": 0,
            "support_fraction": 0.0,
            "legend_bbox": None,
            "orientation": None,
            "pixel_count": 0,
            "diagnostics": {"effect_type": effect_type, "null_value": null_value},
        }

    ci_crosses_null = ci_lower <= null_value <= ci_upper
    verified = not ci_crosses_null
    reason = "ci_excludes_null" if verified else "ci_crosses_null"

    return {
        "verified": bool(verified),
        "pass_fail": bool(verified),
        "proposed_r": float(effect_size),
        "reason": reason,
        "reason_code": reason,
        "observed_range": [float(ci_lower), float(ci_upper)],
        "distance_metric": None,
        "nearest_r": float(effect_size),
        "min_abs_error": abs(effect_size - null_value),
        "support_pixels": 0,
        "required_support": 0,
        "support_fraction": 0.0,
        "legend_bbox": None,
        "orientation": None,
        "pixel_count": 0,
        "diagnostics": {
            "effect_type": effect_type,
            "null_value": null_value,
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "ci_crosses_null": bool(ci_crosses_null),
        },
    }


def _failure_payload(
    *,
    proposed_r: float,
    reason_code: str,
    r_min: float,
    r_max: float,
    legend_bbox: list[int] | None = None,
    orientation: str | None = None,
    pixel_count: int = 0,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "verified": False,
        "pass_fail": False,
        "proposed_r": float(proposed_r),
        "reason": reason_code,
        "reason_code": reason_code,
        "observed_range": [float(r_min), float(r_max)],
        "distance_metric": None,
        "nearest_r": None,
        "min_abs_error": None,
        "support_pixels": 0,
        "required_support": 0,
        "support_fraction": 0.0,
        "legend_bbox": legend_bbox,
        "orientation": orientation,
        "pixel_count": int(pixel_count),
        "diagnostics": diagnostics or {},
    }


def verify_heatmap_r_value(
    proposed_r: float,
    image_path: str,
    tolerance: float = 0.05,
    r_min: float = -1.0,
    r_max: float = 1.0,
    min_support_pixels: int = 30,
    min_support_fraction: float = 0.0005,
    legend_bbox: tuple[int, int, int, int] | None = None,
    heatmap_bbox: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    if proposed_r < r_min or proposed_r > r_max:
        return _failure_payload(
            proposed_r=proposed_r,
            reason_code="r_out_of_range",
            r_min=r_min,
            r_max=r_max,
            diagnostics={"r_min": r_min, "r_max": r_max},
        )

    _require_deps()

    rgb = _load_rgb(image_path)
    hsv = _rgb_to_hsv(rgb)

    try:
        detected_legend, legend_orientation, legend_conf = _detect_legend(rgb, hsv, legend_bbox)
    except RuntimeError:
        return _failure_payload(
            proposed_r=proposed_r,
            reason_code="legend_not_found",
            r_min=r_min,
            r_max=r_max,
        )

    profile = _extract_legend_profile(rgb, detected_legend, legend_orientation)
    sampled_pixels, total_candidates = _sample_heatmap_pixels(
        rgb, hsv, detected_legend, heatmap_bbox
    )

    if total_candidates == 0 or sampled_pixels.shape[0] == 0:
        return _failure_payload(
            proposed_r=proposed_r,
            reason_code="insufficient_colored_pixels",
            r_min=r_min,
            r_max=r_max,
            legend_bbox=[int(v) for v in detected_legend],
            orientation=legend_orientation,
            diagnostics={"legend_confidence": legend_conf},
        )

    r_forward, r_reverse = _infer_r_values(sampled_pixels, profile, r_min, r_max)

    abs_f = np.abs(r_forward - proposed_r)
    abs_r = np.abs(r_reverse - proposed_r)

    support_f = int((abs_f <= tolerance).sum())
    support_r = int((abs_r <= tolerance).sum())

    if support_r > support_f:
        chosen_abs = abs_r
        support = support_r
        direction = "reversed"
    else:
        chosen_abs = abs_f
        support = support_f
        direction = "forward"

    sample_count = int(sampled_pixels.shape[0])
    support_fraction_sample = support / max(1, sample_count)
    estimated_support_pixels = int(round(support_fraction_sample * total_candidates))

    required_support = max(min_support_pixels, int(math.ceil(min_support_fraction * total_candidates)))
    verified = estimated_support_pixels >= required_support

    nearest_r = float(r_forward[np.argmin(abs_f)]) if direction == "forward" else float(r_reverse[np.argmin(abs_r)])
    min_abs_error = float(chosen_abs.min())

    reason = "verified" if verified else "insufficient_support"

    return {
        "verified": bool(verified),
        "pass_fail": bool(verified),
        "proposed_r": float(proposed_r),
        "reason": reason,
        "reason_code": reason,
        "observed_range": [float(r_min), float(r_max)],
        "distance_metric": min_abs_error,
        "nearest_r": nearest_r,
        "min_abs_error": min_abs_error,
        "support_pixels": int(estimated_support_pixels),
        "required_support": int(required_support),
        "support_fraction": float(estimated_support_pixels / max(1, total_candidates)),
        "legend_bbox": [int(v) for v in detected_legend],
        "orientation": direction,
        "pixel_count": int(total_candidates),
        "diagnostics": {
            "legend_orientation": legend_orientation,
            "legend_confidence": float(legend_conf),
            "sampled_pixels": sample_count,
            "tolerance": tolerance,
        },
    }


def _build_figure_lookup(figures_rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in figures_rows:
        figure_id = str(row.get("figure_id") or "")
        image_path = row.get("image_path")
        if figure_id and isinstance(image_path, str) and image_path.strip():
            lookup[figure_id] = image_path
    return lookup


def _verification_from_proposal(
    *,
    proposal: dict[str, Any],
    figure_lookup: dict[str, str],
    tolerance: float,
    r_min: float,
    r_max: float,
    min_support_pixels: int,
    min_support_fraction: float,
) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or "")
    pmid = str(proposal.get("pmid") or "")
    figure_id = str(proposal.get("figure_id") or "")

    candidate = proposal.get("candidate_r", proposal.get("proposed_r"))
    candidate_r = None
    try:
        if candidate is not None:
            candidate_r = float(candidate)
    except (TypeError, ValueError):
        candidate_r = None

    topology = str(proposal.get("topology") or "heatmap")

    if candidate_r is None:
        result = _failure_payload(
            proposed_r=0.0,
            reason_code="missing_candidate_r",
            r_min=r_min,
            r_max=r_max,
        )
    elif topology == "forest_plot":
        # CI-based verification — no pixel analysis needed
        effect_type = str(proposal.get("effect_type") or "odds_ratio")
        ci_lower_raw = proposal.get("ci_lower")
        ci_upper_raw = proposal.get("ci_upper")
        try:
            ci_lower = float(ci_lower_raw) if ci_lower_raw is not None else None
            ci_upper = float(ci_upper_raw) if ci_upper_raw is not None else None
        except (TypeError, ValueError):
            ci_lower = None
            ci_upper = None
        result = verify_forest_plot_association(
            effect_size=candidate_r,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            effect_type=effect_type,
        )
    else:
        image_path = proposal.get("image_path") or figure_lookup.get(figure_id)
        if not isinstance(image_path, str) or not image_path.strip():
            result = _failure_payload(
                proposed_r=candidate_r,
                reason_code="missing_image",
                r_min=r_min,
                r_max=r_max,
            )
        elif not Path(image_path).exists():
            result = _failure_payload(
                proposed_r=candidate_r,
                reason_code="image_not_found",
                r_min=r_min,
                r_max=r_max,
            )
        else:
            legend_bbox = _coerce_bbox_list(proposal.get("legend_bbox"))
            heatmap_bbox = _coerce_bbox_list(proposal.get("heatmap_bbox", proposal.get("bbox")))
            try:
                result = verify_heatmap_r_value(
                    proposed_r=candidate_r,
                    image_path=image_path,
                    tolerance=tolerance,
                    r_min=r_min,
                    r_max=r_max,
                    min_support_pixels=min_support_pixels,
                    min_support_fraction=min_support_fraction,
                    legend_bbox=legend_bbox,
                    heatmap_bbox=heatmap_bbox,
                )
            except Exception as exc:
                result = _failure_payload(
                    proposed_r=candidate_r,
                    reason_code="runtime_error",
                    r_min=r_min,
                    r_max=r_max,
                    diagnostics={"error": str(exc)},
                )

    verification_id = _verification_id(
        proposal_id or "na",
        pmid or "na",
        figure_id or "na",
        str(result.get("proposed_r")),
    )

    result["verification_id"] = verification_id
    result["proposal_id"] = proposal_id or None
    result["pmid"] = pmid or None
    result["figure_id"] = figure_id or None
    return result


def verify_proposals(
    *,
    proposals: list[dict[str, Any]],
    figure_lookup: dict[str, str],
    tolerance: float,
    r_min: float,
    r_max: float,
    min_support_pixels: int,
    min_support_fraction: float,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for proposal in proposals:
        output.append(
            _verification_from_proposal(
                proposal=proposal,
                figure_lookup=figure_lookup,
                tolerance=tolerance,
                r_min=r_min,
                r_max=r_max,
                min_support_pixels=min_support_pixels,
                min_support_fraction=min_support_fraction,
            )
        )
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministically verify an r-value against a heatmap legend."
    )
    parser.add_argument("--r", type=float, help="Proposed r-value for single-image mode.")
    parser.add_argument("--image", help="Path to heatmap image for single-image mode.")
    parser.add_argument("--proposals", default=None, help="Path to vision_proposals.jsonl for batch mode.")
    parser.add_argument("--figures", default="artifacts/figures.jsonl", help="Optional figures.jsonl for figure_id->image_path lookup.")
    parser.add_argument("--output", default="artifacts/verification_results.jsonl", help="Output path for batch mode.")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--r-min", type=float, default=-1.0)
    parser.add_argument("--r-max", type=float, default=1.0)
    parser.add_argument("--min-support-pixels", type=int, default=30)
    parser.add_argument("--min-support-fraction", type=float, default=0.0005)
    parser.add_argument("--legend-bbox", default=None, help="Optional x,y,w,h (single-image mode).")
    parser.add_argument("--heatmap-bbox", default=None, help="Optional x,y,w,h (single-image mode).")
    parser.add_argument("--validate-schema", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def _run_single(args: argparse.Namespace) -> int:
    if args.r is None or args.image is None:
        raise ValueError("Single mode requires both --r and --image")

    try:
        result = verify_heatmap_r_value(
            proposed_r=args.r,
            image_path=args.image,
            tolerance=args.tolerance,
            r_min=args.r_min,
            r_max=args.r_max,
            min_support_pixels=args.min_support_pixels,
            min_support_fraction=args.min_support_fraction,
            legend_bbox=_parse_bbox(args.legend_bbox),
            heatmap_bbox=_parse_bbox(args.heatmap_bbox),
        )
    except Exception as exc:
        payload = {
            "verified": False,
            "pass_fail": False,
            "reason": "runtime_error",
            "reason_code": "runtime_error",
            "error": str(exc),
        }
        print(json.dumps(payload, indent=2 if args.pretty else None))
        return 2

    print(json.dumps(result, indent=2 if args.pretty else None))
    return 0 if result.get("verified") else 1


def _run_batch(args: argparse.Namespace) -> int:
    proposals = read_jsonl(args.proposals)
    figures = read_jsonl(args.figures) if Path(args.figures).exists() else []
    figure_lookup = _build_figure_lookup(figures)

    results = verify_proposals(
        proposals=proposals,
        figure_lookup=figure_lookup,
        tolerance=args.tolerance,
        r_min=args.r_min,
        r_max=args.r_max,
        min_support_pixels=args.min_support_pixels,
        min_support_fraction=args.min_support_fraction,
    )

    if args.validate_schema:
        schema = load_schema("verification_results.schema.json")
        for idx, row in enumerate(results):
            try:
                validate_record(row, schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"verification_results[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, results)
    metrics = {
        "proposals_in": len(proposals),
        "results_out": count,
        "verified": sum(1 for r in results if bool(r.get("verified"))),
        "rejected": sum(1 for r in results if not bool(r.get("verified"))),
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="verify_heatmap",
        params={
            "proposals": args.proposals,
            "figures": args.figures,
            "tolerance": args.tolerance,
            "r_min": args.r_min,
            "r_max": args.r_max,
            "min_support_pixels": args.min_support_pixels,
            "min_support_fraction": args.min_support_fraction,
        },
        metrics=metrics,
        outputs={"verification_results": str(Path(args.output).resolve())},
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.proposals:
        return _run_batch(args)
    return _run_single(args)


if __name__ == "__main__":
    raise SystemExit(main())
