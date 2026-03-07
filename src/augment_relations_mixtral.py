from __future__ import annotations

import argparse
import csv
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
from src.types import AugmentedRelationRecord, to_dict

DEFAULT_MODEL_ID = "mistralai/Mixtral-8x7B-v0.1"
DEFAULT_PROMPT_ID = "mixtral_relation_aug_v1"


class MixtralAugmenter:
    def __init__(self, model_id: str, backend: str, temperature: float, max_new_tokens: int) -> None:
        self.model_id = model_id
        self.backend = backend
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self._pipe = None
        self.available = False

        if backend in {"auto", "hf_textgen"}:
            self._pipe = self._load_pipeline(model_id)
            self.available = self._pipe is not None

    def _load_pipeline(self, model_id: str) -> Any:
        try:
            from transformers import pipeline  # type: ignore

            return pipeline("text-generation", model=model_id, device=-1)
        except Exception:
            return None

    def _prompt(self, sentence: str, microbe: str, disease: str, label: str) -> str:
        return (
            "Rewrite the sentence while preserving biomedical meaning and relation label. "
            "Return only one sentence.\n"
            f"Label: {label}\n"
            f"Microbe: {microbe}\n"
            f"Disease: {disease}\n"
            f"Sentence: {sentence}\n"
            "Rewrite:"
        )

    def paraphrase(self, sentence: str, microbe: str, disease: str, label: str) -> tuple[str, str]:
        if self._pipe is None:
            return self._template_paraphrase(sentence, microbe, disease), "fallback_template"

        prompt = self._prompt(sentence, microbe, disease, label)
        try:
            out = self._pipe(
                prompt,
                do_sample=True,
                temperature=self.temperature,
                max_new_tokens=self.max_new_tokens,
                return_full_text=False,
            )
            text = str(out[0].get("generated_text", "")).strip()
            text = text.splitlines()[0].strip() if text else ""
            if not text:
                raise RuntimeError("empty_generation")
            return text, "hf_textgen"
        except Exception:
            return self._template_paraphrase(sentence, microbe, disease), "fallback_template"

    def _template_paraphrase(self, sentence: str, microbe: str, disease: str) -> str:
        sentence = sentence.strip().rstrip(".")
        return f"Evidence indicates that {microbe} is discussed in relation to {disease}: {sentence}."


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _load_rows(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return read_jsonl(path)

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    return rows


def _extract_seed_fields(row: dict[str, Any], index: int) -> dict[str, str]:
    sentence = str(row.get("sentence") or row.get("evidence") or "").strip()
    microbe = str(row.get("microbe") or row.get("bacteria") or "").strip()
    disease = str(row.get("disease") or "").strip()
    label = str(row.get("label") or row.get("relation") or row.get("final_label") or "na").strip().lower()
    pmid = str(row.get("pmid") or row.get("pubmed_id") or "")
    seed_id = str(row.get("seed_id") or _stable_id(str(index), pmid, sentence, microbe, disease, label))
    return {
        "seed_id": seed_id,
        "pmid": pmid,
        "sentence": sentence,
        "microbe": microbe,
        "disease": disease,
        "label": label,
    }


def _replace_term(text: str, old: str, new: str) -> str:
    if not old:
        return text
    pattern = re.compile(re.escape(old), flags=re.IGNORECASE)
    return pattern.sub(new, text)


def build_augmented_rows(
    *,
    seeds: list[dict[str, Any]],
    augmenter: MixtralAugmenter,
    prompt_id: str,
) -> list[AugmentedRelationRecord]:
    if not seeds:
        return []

    microbe_pool = [s["microbe"] for s in seeds if s["microbe"]]
    disease_pool = [s["disease"] for s in seeds if s["disease"]]

    output: list[AugmentedRelationRecord] = []

    for idx, seed in enumerate(seeds):
        sentence = seed["sentence"]
        microbe = seed["microbe"]
        disease = seed["disease"]
        label = seed["label"] or "na"
        seed_id = seed["seed_id"]

        if not sentence or not microbe or not disease:
            continue

        for n in range(2):
            paraphrased, method = augmenter.paraphrase(sentence, microbe, disease, label)
            aug_id = _stable_id(seed_id, f"paraphrase_{n + 1}", paraphrased)
            output.append(
                AugmentedRelationRecord(
                    aug_id=aug_id,
                    seed_id=seed_id,
                    pmid=seed["pmid"] or None,
                    sentence=paraphrased,
                    microbe=microbe,
                    disease=disease,
                    label=label,
                    augmentation_type=f"paraphrase_{n + 1}",
                    model_id=augmenter.model_id,
                    prompt_id=prompt_id,
                    status="ok",
                    source_sentence=sentence,
                    metadata={"method": method},
                )
            )

        replacement_microbe = microbe_pool[(idx + 1) % len(microbe_pool)] if microbe_pool else microbe
        replacement_disease = disease_pool[(idx + 2) % len(disease_pool)] if disease_pool else disease

        swapped = _replace_term(sentence, microbe, replacement_microbe)
        swapped = _replace_term(swapped, disease, replacement_disease)
        if swapped == sentence:
            swapped = f"{replacement_microbe} was evaluated in the context of {replacement_disease}."

        aug_id = _stable_id(seed_id, "entity_swap_template", swapped)
        output.append(
            AugmentedRelationRecord(
                aug_id=aug_id,
                seed_id=seed_id,
                pmid=seed["pmid"] or None,
                sentence=swapped,
                microbe=replacement_microbe,
                disease=replacement_disease,
                label=label,
                augmentation_type="entity_swap_template",
                model_id=augmenter.model_id,
                prompt_id=prompt_id,
                status="ok",
                source_sentence=sentence,
                metadata={
                    "method": "template_swap",
                    "source_microbe": microbe,
                    "source_disease": disease,
                },
            )
        )

    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate relation augmentation dataset with Mixtral.")
    parser.add_argument("--input", default="artifacts/relation_input.jsonl")
    parser.add_argument("--output", default="artifacts/relation_augmented.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    parser.add_argument("--backend", choices=["auto", "hf_textgen", "template"], default="auto")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    raw_rows = _load_rows(args.input)
    seeds = [_extract_seed_fields(row, idx) for idx, row in enumerate(raw_rows)]

    augmenter = MixtralAugmenter(
        model_id=args.model_id,
        backend=args.backend,
        temperature=args.temperature,
        max_new_tokens=args.max_new_tokens,
    )

    if args.backend == "template":
        augmenter._pipe = None
        augmenter.available = False

    rows = build_augmented_rows(seeds=seeds, augmenter=augmenter, prompt_id=args.prompt_id)

    if args.validate_schema:
        schema = load_schema("relation_augmented.schema.json")
        for idx, row in enumerate(rows):
            try:
                validate_record(to_dict(row), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_augmented[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, rows)

    metrics = {
        "seed_rows_in": len(raw_rows),
        "seed_rows_usable": len([x for x in seeds if x.get("sentence") and x.get("microbe") and x.get("disease")]),
        "augmented_rows_out": count,
        "backend_requested": args.backend,
        "backend_effective": "hf_textgen" if augmenter.available and args.backend != "template" else "template",
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="augment_relations_mixtral",
        params={
            "input": args.input,
            "model_id": args.model_id,
            "prompt_id": args.prompt_id,
            "backend": args.backend,
            "temperature": args.temperature,
            "max_new_tokens": args.max_new_tokens,
        },
        metrics=metrics,
        outputs={"relation_augmented": str(Path(args.output).resolve())},
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
