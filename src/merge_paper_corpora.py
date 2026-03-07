from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import PaperRecord, from_dict, to_dict


def _profile_label_from_path(path: Path) -> str:
    stem = path.stem
    if stem.startswith("papers_"):
        return stem[len("papers_") :]
    return stem


def _merge_optional_text(current: str | None, candidate: str | None) -> str | None:
    current_clean = str(current or "").strip()
    candidate_clean = str(candidate or "").strip()
    if current_clean:
        return current_clean
    return candidate_clean or None


def _merge_optional_number(current: int | float | None, candidate: int | float | None) -> int | float | None:
    if current is not None:
        return current
    return candidate


def merge_paper_corpora(paths: list[str | Path]) -> tuple[list[PaperRecord], list[dict[str, object]], dict[str, int]]:
    merged: dict[str, PaperRecord] = {}
    provenance: dict[str, dict[str, object]] = {}

    metrics = {
        "input_files": len(paths),
        "input_rows": 0,
        "unique_pmids": 0,
        "duplicate_rows_removed": 0,
    }

    for raw_path in paths:
        path = Path(raw_path)
        label = _profile_label_from_path(path)
        rows = [from_dict(PaperRecord, row) for row in read_jsonl(path)]
        for row in rows:
            metrics["input_rows"] += 1
            pmid = str(row.pmid or "").strip()
            if not pmid:
                continue

            if pmid not in merged:
                merged[pmid] = row
                provenance[pmid] = {
                    "pmid": pmid,
                    "source_profiles": [label],
                    "source_files": [str(path.resolve())],
                    "source_count": 1,
                }
                continue

            metrics["duplicate_rows_removed"] += 1
            current = merged[pmid]
            current.abstract = _merge_optional_text(current.abstract, row.abstract) or ""
            current.title = _merge_optional_text(current.title, row.title) or ""
            current.pmcid = _merge_optional_text(current.pmcid, row.pmcid)
            current.doi = _merge_optional_text(current.doi, row.doi)
            current.journal = _merge_optional_text(current.journal, row.journal)
            current.issn = _merge_optional_text(current.issn, row.issn)
            current.language = _merge_optional_text(current.language, row.language)
            current.quartile = _merge_optional_text(current.quartile, row.quartile)
            current.full_text_path = _merge_optional_text(current.full_text_path, row.full_text_path)
            current.year = _merge_optional_number(current.year, row.year)  # type: ignore[assignment]
            current.impact_factor = _merge_optional_number(current.impact_factor, row.impact_factor)  # type: ignore[assignment]
            if str(row.retrieval_date or "").strip() > str(current.retrieval_date or "").strip():
                current.retrieval_date = row.retrieval_date

            prov = provenance[pmid]
            profiles = list(prov["source_profiles"])
            files = list(prov["source_files"])
            if label not in profiles:
                profiles.append(label)
            resolved_path = str(path.resolve())
            if resolved_path not in files:
                files.append(resolved_path)
            prov["source_profiles"] = profiles
            prov["source_files"] = files
            prov["source_count"] = len(profiles)

    ordered_pmids: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        rows = read_jsonl(raw_path)
        for row in rows:
            pmid = str(row.get("pmid") or "").strip()
            if pmid and pmid not in seen:
                seen.add(pmid)
                ordered_pmids.append(pmid)

    merged_rows: list[PaperRecord] = []
    provenance_rows: list[dict[str, object]] = []
    for pmid in ordered_pmids:
        row = merged[pmid]
        prov = provenance[pmid]
        row.query = "merged:" + "|".join(prov["source_profiles"])  # type: ignore[index]
        merged_rows.append(row)
        provenance_rows.append(prov)

    metrics["unique_pmids"] = len(merged_rows)
    return merged_rows, provenance_rows, metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and deduplicate harvested paper corpora by PMID.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=[
            "artifacts/papers_microbe_radiomics_strict.jsonl",
            "artifacts/papers_microbe_imaging_adjacent.jsonl",
            "artifacts/papers_microbe_bodycomp.jsonl",
        ],
    )
    parser.add_argument("--output", default="artifacts/papers_microbe_merged_dedup.jsonl")
    parser.add_argument("--provenance-output", default="artifacts/papers_microbe_merged_provenance.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    merged_rows, provenance_rows, metrics = merge_paper_corpora(args.inputs)

    if args.validate_schema:
        paper_schema = load_schema("papers.schema.json")
        provenance_schema = load_schema("merged_paper_provenance.schema.json")
        for idx, row in enumerate(merged_rows):
            try:
                validate_record(to_dict(row), paper_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"papers[{idx}] invalid: {exc}") from exc
        for idx, row in enumerate(provenance_rows):
            try:
                validate_record(row, provenance_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"provenance[{idx}] invalid: {exc}") from exc

    merged_count = write_jsonl(args.output, merged_rows)
    provenance_count = write_jsonl(args.provenance_output, provenance_rows)
    stage_metrics = dict(metrics)
    stage_metrics["merged_written"] = merged_count
    stage_metrics["provenance_written"] = provenance_count

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="merge_paper_corpora",
        params={
            "inputs": [str(Path(path).resolve()) for path in args.inputs],
        },
        metrics=stage_metrics,
        outputs={
            "papers": str(Path(args.output).resolve()),
            "provenance": str(Path(args.provenance_output).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": stage_metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
