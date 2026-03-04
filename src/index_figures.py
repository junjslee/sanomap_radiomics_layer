from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import FigureRecord, to_dict

try:
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    _HAS_IMAGE_DEPS = True
except ImportError:
    _HAS_IMAGE_DEPS = False


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

HEATMAP_KEYWORDS = {
    "heatmap",
    "heat map",
    "correlation matrix",
    "cluster map",
    "clustermap",
    "color map",
    "matrix",
}
FOREST_KEYWORDS = {
    "forest plot",
    "hazard ratio",
    "odds ratio",
    "confidence interval",
    "meta-analysis",
    "meta analysis",
    "ci",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _find_keyword_hits(text: str, keywords: set[str]) -> list[str]:
    norm = _normalize_text(text)
    hits = [kw for kw in sorted(keywords) if kw in norm]
    return hits


def _image_heuristics(image_path: Path) -> tuple[float, float, list[str]]:
    if not _HAS_IMAGE_DEPS:
        return 0.0, 0.0, []

    try:
        arr = np.array(Image.open(image_path).convert("L"), dtype=float)
    except Exception:
        return 0.0, 0.0, []

    if arr.ndim != 2 or arr.size == 0:
        return 0.0, 0.0, []

    gx = np.abs(np.diff(arr, axis=1))
    gy = np.abs(np.diff(arr, axis=0))

    col_strength = gx.mean(axis=0)
    row_strength = gy.mean(axis=1)

    col_threshold = np.percentile(col_strength, 85) if col_strength.size else 0.0
    row_threshold = np.percentile(row_strength, 85) if row_strength.size else 0.0

    strong_cols = int((col_strength >= col_threshold).sum()) if col_strength.size else 0
    strong_rows = int((row_strength >= row_threshold).sum()) if row_strength.size else 0

    matrix_score = min(1.0, (strong_cols + strong_rows) / 80.0)

    central_band = arr[:, arr.shape[1] // 3 : (arr.shape[1] * 2) // 3]
    central_var = float(np.std(central_band)) if central_band.size else 0.0
    side_var = float(np.std(np.hstack((arr[:, : arr.shape[1] // 6], arr[:, -arr.shape[1] // 6 :]))) if arr.shape[1] >= 12 else np.std(arr))
    forest_score = 0.0
    if side_var > 0:
        forest_score = min(1.0, max(0.0, (central_var - side_var) / (side_var + 1e-6)))

    hits: list[str] = []
    if matrix_score >= 0.30:
        hits.append("image_matrix_like")
    if forest_score >= 0.30:
        hits.append("image_forest_like")

    return matrix_score, forest_score, hits


def classify_figure(caption: str, image_path: Path | None = None) -> tuple[str, float, list[str]]:
    heat_hits = _find_keyword_hits(caption, HEATMAP_KEYWORDS)
    forest_hits = _find_keyword_hits(caption, FOREST_KEYWORDS)

    heat_score = min(1.0, 0.2 * len(heat_hits))
    forest_score = min(1.0, 0.2 * len(forest_hits))
    hits: list[str] = []
    hits.extend(f"kw:{h}" for h in heat_hits + forest_hits)

    if image_path is not None:
        matrix_score, image_forest_score, image_hits = _image_heuristics(image_path)
        heat_score = max(heat_score, matrix_score)
        forest_score = max(forest_score, image_forest_score)
        hits.extend(image_hits)

    if heat_score == 0.0 and forest_score == 0.0:
        return "unknown", 0.0, hits
    if heat_score >= forest_score:
        return "heatmap", round(heat_score, 3), hits
    return "forest_plot", round(forest_score, 3), hits


def _extract_pmid(text: str) -> str | None:
    match = re.search(r"\b\d{6,9}\b", text)
    return match.group(0) if match else None


def _figure_id(pmid: str | None, caption: str, image_path: str | None) -> str:
    base = f"{pmid or 'na'}|{caption}|{image_path or 'na'}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _from_paper_metadata(papers: list[dict[str, Any]]) -> list[FigureRecord]:
    figures: list[FigureRecord] = []
    for paper in papers:
        pmid = str(paper.get("pmid") or "") or None
        for fig in paper.get("figure_metadata", []) or []:
            caption = str(fig.get("caption") or "")
            image_path = fig.get("image_path")
            topology, confidence, hits = classify_figure(caption, Path(image_path) if image_path else None)
            rec = FigureRecord(
                figure_id=str(fig.get("figure_id") or _figure_id(pmid, caption, image_path)),
                pmid=pmid,
                image_path=image_path,
                caption=caption,
                topology=topology,
                topology_confidence=confidence,
                heuristic_hits=hits,
                source_context="paper_metadata",
            )
            figures.append(rec)
    return figures


def _from_images_dir(images_dir: Path) -> list[FigureRecord]:
    figures: list[FigureRecord] = []
    if not images_dir.exists():
        return figures

    for path in sorted(images_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        caption = path.stem.replace("_", " ").replace("-", " ")
        pmid = _extract_pmid(path.name) or _extract_pmid(str(path.parent))
        topology, confidence, hits = classify_figure(caption, path)

        rec = FigureRecord(
            figure_id=_figure_id(pmid, caption, str(path.resolve())),
            pmid=pmid,
            image_path=str(path.resolve()),
            caption=caption,
            topology=topology,
            topology_confidence=confidence,
            heuristic_hits=hits,
            source_context="images_dir",
        )
        figures.append(rec)
    return figures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index and classify figure topology deterministically.")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--images-dir", default="sample_papers_of_radiomics")
    parser.add_argument("--output", default="artifacts/figures.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    paper_rows: list[dict[str, Any]] = []
    papers_path = Path(args.papers)
    if papers_path.exists():
        paper_rows = read_jsonl(papers_path)

    figures = _from_paper_metadata(paper_rows)
    figures.extend(_from_images_dir(Path(args.images_dir)))

    # Dedupe by id while preferring higher confidence
    deduped: dict[str, FigureRecord] = {}
    for fig in figures:
        prev = deduped.get(fig.figure_id)
        if prev is None or fig.topology_confidence > prev.topology_confidence:
            deduped[fig.figure_id] = fig

    records = list(deduped.values())

    if args.validate_schema:
        schema = load_schema("figures.schema.json")
        for idx, rec in enumerate(records):
            try:
                validate_record(to_dict(rec), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"figures[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, records)
    metrics = {
        "figures_indexed": count,
        "heatmap": sum(1 for x in records if x.topology == "heatmap"),
        "forest_plot": sum(1 for x in records if x.topology == "forest_plot"),
        "unknown": sum(1 for x in records if x.topology == "unknown"),
        "image_deps": _HAS_IMAGE_DEPS,
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="index_figures",
        params={"papers": args.papers, "images_dir": args.images_dir},
        metrics=metrics,
        outputs={"figures": str(Path(args.output).resolve())},
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
