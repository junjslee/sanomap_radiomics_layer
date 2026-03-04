from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.model_backends import MODEL_FAMILY_MAP, build_backend
from src.relation_fidelity import (
    aggregate_within_paper,
    compute_strength_scores,
    self_consistency_predict,
)
from src.schema_utils import SchemaValidationError, load_schema, validate_record


def _prediction_id(pmid: str, microbe: str, disease: str, sentence: str) -> str:
    base = f"{pmid}|{microbe}|{disease}|{sentence}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _default_temperatures(num_samples: int) -> list[float]:
    if num_samples <= 1:
        return [0.7]
    start = 0.45
    stop = 0.85
    step = (stop - start) / (num_samples - 1)
    return [round(start + i * step, 3) for i in range(num_samples)]


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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    backend = build_backend(
        backend=backend_name,
        model_family=model_family,
        model_id=model_id,
        device=device,
    )

    predictions: list[dict[str, Any]] = []
    for row in input_rows:
        pmid = str(row.get("pmid") or "")
        microbe = str(row.get("microbe") or "")
        disease = str(row.get("disease") or "")
        sentence = str(row.get("sentence") or "")
        impact_factor = row.get("impact_factor", "NA")
        quartile = row.get("quartile", "NA")

        result = self_consistency_predict(
            backend=backend,
            sentence=sentence,
            microbe=microbe,
            disease=disease,
            temperatures=temperatures,
            max_new_tokens=max_new_tokens,
            require_complete_consistency=require_complete_consistency,
        )

        prediction = {
            "prediction_id": _prediction_id(pmid, microbe, disease, sentence),
            "pmid": pmid,
            "microbe": microbe,
            "disease": disease,
            "sentence": sentence,
            "final_label": result.final_label,
            "accepted": result.accepted,
            "full_consistency": result.full_consistency,
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

    parser.add_argument("--backend", default="heuristic", choices=["heuristic", "hf_textgen"])
    parser.add_argument("--model-family", default="biomistral_7b")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--device", default="cpu")

    parser.add_argument("--num-samples", type=int, default=7)
    parser.add_argument("--temperatures", default=None, help="Comma-separated temperatures.")
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--allow-majority-consistency", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_rows = read_jsonl(args.input) if Path(args.input).exists() else []

    if args.temperatures:
        temperatures = [float(x.strip()) for x in args.temperatures.split(",") if x.strip()]
    else:
        temperatures = _default_temperatures(args.num_samples)

    predictions, aggregated, strengths = run_relation_extraction(
        input_rows=input_rows,
        backend_name=args.backend,
        model_family=args.model_family,
        model_id=args.model_id,
        device=args.device,
        temperatures=temperatures,
        max_new_tokens=args.max_new_tokens,
        require_complete_consistency=not args.allow_majority_consistency,
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
        "predictions_out": len(predictions),
        "full_consistency_rate": round(
            sum(1 for p in predictions if bool(p.get("full_consistency"))) / max(1, len(predictions)),
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
            "temperatures": temperatures,
            "max_new_tokens": args.max_new_tokens,
            "require_complete_consistency": not args.allow_majority_consistency,
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
