from __future__ import annotations

import argparse
import json
import math
from typing import Any

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
) -> float:
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
        return -1.0

    profile = np.array(vectors, dtype=float)
    diffs = np.linalg.norm(np.diff(profile, axis=0), axis=1)
    progression = float(np.mean(diffs) / 255.0)

    if orientation == "vertical":
        cross_std = np.std(crop_rgb, axis=1).mean()
    else:
        cross_std = np.std(crop_rgb, axis=0).mean()

    uniformity_penalty = float(cross_std / 255.0)
    return progression - 0.15 * uniformity_penalty


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
        progression = _color_progression_score(tight_rgb, tight_mask, orientation)
        geom_bonus = 0.1 if (orientation == "vertical" and th > tw * 2) or (orientation == "horizontal" and tw > th * 2) else 0.0

        score = progression + colorful_fraction + edge_bonus + geom_bonus
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
    _require_deps()

    if proposed_r < r_min or proposed_r > r_max:
        return {
            "verified": False,
            "proposed_r": proposed_r,
            "reason": "r_out_of_range",
            "nearest_r": None,
            "min_abs_error": None,
            "support_pixels": 0,
            "required_support": 0,
            "support_fraction": 0.0,
            "legend_bbox": None,
            "orientation": None,
            "pixel_count": 0,
            "diagnostics": {"r_min": r_min, "r_max": r_max},
        }

    rgb = _load_rgb(image_path)
    hsv = _rgb_to_hsv(rgb)

    try:
        detected_legend, legend_orientation, legend_conf = _detect_legend(rgb, hsv, legend_bbox)
    except RuntimeError:
        return {
            "verified": False,
            "proposed_r": proposed_r,
            "reason": "legend_not_found",
            "nearest_r": None,
            "min_abs_error": None,
            "support_pixels": 0,
            "required_support": 0,
            "support_fraction": 0.0,
            "legend_bbox": None,
            "orientation": None,
            "pixel_count": 0,
            "diagnostics": {},
        }

    profile = _extract_legend_profile(rgb, detected_legend, legend_orientation)
    sampled_pixels, total_candidates = _sample_heatmap_pixels(
        rgb, hsv, detected_legend, heatmap_bbox
    )

    if total_candidates == 0 or sampled_pixels.shape[0] == 0:
        return {
            "verified": False,
            "proposed_r": proposed_r,
            "reason": "insufficient_colored_pixels",
            "nearest_r": None,
            "min_abs_error": None,
            "support_pixels": 0,
            "required_support": 0,
            "support_fraction": 0.0,
            "legend_bbox": list(detected_legend),
            "orientation": legend_orientation,
            "pixel_count": 0,
            "diagnostics": {"legend_confidence": legend_conf},
        }

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
        "proposed_r": float(proposed_r),
        "reason": reason,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministically verify an r-value against a heatmap legend."
    )
    parser.add_argument("--r", type=float, required=True, help="Proposed r-value.")
    parser.add_argument("--image", required=True, help="Path to heatmap image.")
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--r-min", type=float, default=-1.0)
    parser.add_argument("--r-max", type=float, default=1.0)
    parser.add_argument("--min-support-pixels", type=int, default=30)
    parser.add_argument("--min-support-fraction", type=float, default=0.0005)
    parser.add_argument("--legend-bbox", default=None, help="Optional x,y,w,h")
    parser.add_argument("--heatmap-bbox", default=None, help="Optional x,y,w,h")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
        payload = {"verified": False, "error": str(exc), "reason": "runtime_error"}
        print(json.dumps(payload, indent=2 if args.pretty else None))
        return 2

    print(json.dumps(result, indent=2 if args.pretty else None))
    return 0 if result.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
