from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.model_backends import (
    GEMINI_OPENAI_BASE_URL,
    MODEL_FAMILY_MAP,
    build_backend,
    is_gemini_model_id,
)
from src.relation_fidelity import (
    aggregate_within_paper,
    compute_strength_scores,
    self_consistency_predict,
)
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.span_cleanup import clean_relation_pair


def _prediction_id(
    pmid: str,
    subject_node_type: str,
    subject_node: str,
    disease: str,
    sentence: str,
) -> str:
    base = f"{pmid}|{subject_node_type}|{subject_node}|{disease}|{sentence}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _default_temperatures(num_samples: int) -> list[float]:
    if num_samples <= 1:
        return [0.7]
    start = 0.45
    stop = 0.85
    step = (stop - start) / (num_samples - 1)
    return [round(start + i * step, 3) for i in range(num_samples)]


def resolve_api_settings(
    *,
    model_id: str | None,
    cli_api_base_url: str | None,
    cli_api_key: str | None,
    environ: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    env = environ if environ is not None else os.environ

    if is_gemini_model_id(model_id):
        api_base_url = (cli_api_base_url or env.get("GEMINI_API_BASE_URL") or GEMINI_OPENAI_BASE_URL).strip()
        api_key = (
            cli_api_key
            or env.get("GEMINI_API_KEY")
            or env.get("RELATION_API_KEY")
            or env.get("OPENAI_API_KEY")
            or ""
        ).strip()
        return api_base_url or None, api_key or None

    api_base_url = (
        cli_api_base_url
        or env.get("RELATION_API_BASE_URL")
        or env.get("OPENAI_BASE_URL")
        or ""
    ).strip()
    api_key = (
        cli_api_key
        or env.get("RELATION_API_KEY")
        or env.get("HUGGINGFACE_API_KEY")
        or env.get("HF_TOKEN")
        or env.get("OPENAI_API_KEY")
        or ""
    ).strip()
    return api_base_url or None, api_key or None


def _clean_relation_input_row(
    row: dict[str, Any],
    *,
    max_evidence_words: int,
    max_evidence_chars: int,
) -> tuple[dict[str, Any] | None, str | None]:
    sentence = str(row.get("sentence") or "").strip()
    subject_node_type = str(row.get("subject_node_type") or "Microbe").strip()
    subject_node = str(row.get("subject_node") or row.get("microbe") or "")
    disease = str(row.get("disease") or "")

    cleaned_subject, cleaned_disease, reason = clean_relation_pair(
        sentence=sentence,
        subject_node_type=subject_node_type or "Microbe",
        subject_node=subject_node,
        disease=disease,
        max_evidence_words=max_evidence_words,
        max_evidence_chars=max_evidence_chars,
    )
    if reason is not None:
        return None, reason
    if cleaned_subject is None or cleaned_disease is None:
        return None, "missing_cleaned_spans"

    cleaned_row = dict(row)
    cleaned_row["sentence"] = sentence
    cleaned_row["subject_node_type"] = subject_node_type or "Microbe"
    cleaned_row["subject_node"] = cleaned_subject.canonical
    cleaned_row["disease"] = cleaned_disease.canonical
    if cleaned_row.get("microbe") or cleaned_row["subject_node_type"] == "Microbe":
        cleaned_row["microbe"] = cleaned_subject.canonical
    return cleaned_row, None


def filter_relation_input_rows(
    rows: list[dict[str, Any]],
    *,
    max_evidence_words: int = 500,
    max_evidence_chars: int = 5000,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    reason_counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for row in rows:
        cleaned_row, reason = _clean_relation_input_row(
            row,
            max_evidence_words=max_evidence_words,
            max_evidence_chars=max_evidence_chars,
        )
        if reason is not None:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            continue
        if cleaned_row is None:
            continue
        kept.append(cleaned_row)
    return kept, reason_counts


def run_relation_extraction(
    *,
    input_rows: list[dict[str, Any]],
    backend_name: str,
    model_family: str,
    model_id: str | None,
    device: str,
    temperatures: list[float],
    max_new_tokens: int,
    require_complete_consistency: bool,
    apply_upstream_filters: bool = True,
    max_evidence_words: int = 500,
    max_evidence_chars: int = 5000,
    filtered_reason_counts: dict[str, int] | None = None,
    api_base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    backend = build_backend(
        backend=backend_name,
        model_family=model_family,
        model_id=model_id,
        device=device,
        api_base_url=api_base_url,
        api_key=api_key,
    )

    rows = input_rows
    local_filter_counts: dict[str, int] = {}
    if apply_upstream_filters:
        rows, local_filter_counts = filter_relation_input_rows(
            input_rows,
            max_evidence_words=max_evidence_words,
            max_evidence_chars=max_evidence_chars,
        )
    if filtered_reason_counts is not None:
        filtered_reason_counts.clear()
        filtered_reason_counts.update(local_filter_counts)

    predictions: list[dict[str, Any]] = []
    for row in rows:
        pmid = str(row.get("pmid") or "")
        microbe = str(row.get("microbe") or "")
        subject_node_type = str(row.get("subject_node_type") or "Microbe")
        subject_node = str(row.get("subject_node") or microbe)
        disease = str(row.get("disease") or "")
        sentence = str(row.get("sentence") or "")
        impact_factor = row.get("impact_factor", "NA")
        quartile = row.get("quartile", "NA")

        result = self_consistency_predict(
            backend=backend,
            sentence=sentence,
            subject=subject_node or microbe,
            disease=disease,
            temperatures=temperatures,
            max_new_tokens=max_new_tokens,
            require_complete_consistency=require_complete_consistency,
        )

        prediction = {
            "prediction_id": _prediction_id(pmid, subject_node_type, subject_node or microbe, disease, sentence),
            "pmid": pmid,
            "microbe": microbe,
            "subject_node_type": subject_node_type,
            "subject_node": subject_node or microbe,
            "disease": disease,
            "sentence": sentence,
            "final_label": result.final_label,
            "accepted": result.accepted,
            "full_consistency": result.full_consistency,
            "label_entropy": result.label_entropy,
            "zero_entropy": result.zero_entropy,
            "sample_labels": result.sample_labels,
            "vote_counts": result.vote_counts,
            "model_backend": backend_name,
            "model_family": model_family,
            "model_id": model_id or MODEL_FAMILY_MAP.get(model_family, model_family),
            "temperatures": temperatures,
            "impact_factor": impact_factor,
            "quartile": quartile,
        }
        predictions.append(prediction)

    aggregated = aggregate_within_paper(predictions)
    strengths = compute_strength_scores(aggregated)
    return predictions, aggregated, strengths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MINERVA-like relation extraction stage with configurable backends and fidelity gates."
    )
    parser.add_argument("--input", default="artifacts/relation_input.jsonl")
    parser.add_argument("--output-predictions", default="artifacts/relation_predictions.jsonl")
    parser.add_argument("--output-aggregated", default="artifacts/relation_aggregated.jsonl")
    parser.add_argument("--output-strengths", default="artifacts/relation_strengths.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")

    parser.add_argument("--backend", default="hf_textgen", choices=["heuristic", "hf_textgen", "openai_compatible"])
    parser.add_argument("--model-family", default="biomistral_7b")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument("--api-key", default=None)

    parser.add_argument("--num-samples", type=int, default=7)
    parser.add_argument("--temperatures", default=None, help="Comma-separated temperatures.")
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--allow-majority-consistency", action="store_true")
    parser.add_argument("--disable-upstream-filters", action="store_true")
    parser.add_argument("--max-evidence-words", type=int, default=500)
    parser.add_argument("--max-evidence-chars", type=int, default=5000)
    parser.add_argument("--validate-schema", action="store_true")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_rows = read_jsonl(args.input) if Path(args.input).exists() else []
    api_base_url, api_key = resolve_api_settings(
        model_id=args.model_id,
        cli_api_base_url=args.api_base_url,
        cli_api_key=args.api_key,
    )

    if args.temperatures:
        temperatures = [float(x.strip()) for x in args.temperatures.split(",") if x.strip()]
    else:
        temperatures = _default_temperatures(args.num_samples)

    filtered_reason_counts: dict[str, int] = {}
    predictions, aggregated, strengths = run_relation_extraction(
        input_rows=input_rows,
        backend_name=args.backend,
        model_family=args.model_family,
        model_id=args.model_id,
        device=args.device,
        api_base_url=api_base_url,
        api_key=api_key,
        temperatures=temperatures,
        max_new_tokens=args.max_new_tokens,
        require_complete_consistency=not args.allow_majority_consistency,
        apply_upstream_filters=not args.disable_upstream_filters,
        max_evidence_words=args.max_evidence_words,
        max_evidence_chars=args.max_evidence_chars,
        filtered_reason_counts=filtered_reason_counts,
    )

    if args.validate_schema:
        prediction_schema = load_schema("relation_predictions.schema.json")
        aggregated_schema = load_schema("relation_aggregated.schema.json")
        strengths_schema = load_schema("relation_strengths.schema.json")
        for idx, row in enumerate(predictions):
            try:
                validate_record(row, prediction_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_predictions[{idx}] invalid: {exc}") from exc
        for idx, row in enumerate(aggregated):
            try:
                validate_record(row, aggregated_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_aggregated[{idx}] invalid: {exc}") from exc
        for idx, row in enumerate(strengths):
            try:
                validate_record(row, strengths_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_strengths[{idx}] invalid: {exc}") from exc

    write_jsonl(args.output_predictions, predictions)
    write_jsonl(args.output_aggregated, aggregated)
    write_jsonl(args.output_strengths, strengths)

    metrics = {
        "input_rows": len(input_rows),
        "rows_after_filters": len(predictions),
        "filtered_out_rows": len(input_rows) - len(predictions),
        "filtered_reason_counts": filtered_reason_counts,
        "predictions_out": len(predictions),
        "full_consistency_rate": round(
            sum(1 for p in predictions if bool(p.get("full_consistency"))) / max(1, len(predictions)),
            4,
        ),
        "zero_entropy_rate": round(
            sum(1 for p in predictions if bool(p.get("zero_entropy"))) / max(1, len(predictions)),
            4,
        ),
        "accepted_sentence_relations": sum(1 for p in predictions if bool(p.get("accepted"))),
        "aggregated_relations": len(aggregated),
        "accepted_aggregated_relations": sum(1 for r in aggregated if bool(r.get("accepted"))),
        "strength_groups": len(strengths),
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="relation_extract_stage",
        params={
            "backend": args.backend,
            "model_family": args.model_family,
            "model_id": args.model_id,
            "device": args.device,
            "api_base_url": api_base_url,
            "api_key_used": bool(api_key),
            "temperatures": temperatures,
            "max_new_tokens": args.max_new_tokens,
            "require_complete_consistency": not args.allow_majority_consistency,
            "apply_upstream_filters": not args.disable_upstream_filters,
            "max_evidence_words": args.max_evidence_words,
            "max_evidence_chars": args.max_evidence_chars,
        },
        metrics=metrics,
        outputs={
            "predictions": str(Path(args.output_predictions).resolve()),
            "aggregated": str(Path(args.output_aggregated).resolve()),
            "strengths": str(Path(args.output_strengths).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
