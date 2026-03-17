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
from src.paper_text_utils import paper_text
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.span_cleanup import GENERIC_MICROBE_TERMS, clean_disease_span, clean_subject_span
from src.types import EntitySentenceRecord, RelationInputRecord, to_dict

NON_MICROBE_FIRST_TOKENS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "in",
    "on",
    "of",
    "for",
    "to",
    "from",
    "with",
    "without",
    "at",
    "by",
    "we",
    "our",
    "their",
    "its",
    "study",
    "analysis",
    "prediction",
    "development",
    "evaluation",
    "assessment",
    "patients",
    "model",
    "models",
    "radiomics",
}
COMMON_MICROBE_GENERA = {
    "escherichia",
    "fusobacterium",
    "clostridium",
    "bacteroides",
    "prevotella",
    "streptococcus",
    "staphylococcus",
    "lactobacillus",
    "bifidobacterium",
    "ruminococcus",
    "akkermansia",
    "faecalibacterium",
    "enterococcus",
    "anaerostipes",
    "blautia",
    "alistipes",
    "roseburia",
    "parabacteroides",
    "desulfovibrio",
    "coprococcus",
}
DISEASE_TUIS = {
    "T019",
    "T020",
    "T033",
    "T037",
    "T046",
    "T047",
    "T048",
    "T049",
    "T184",
    "T190",
    "T191",
}

# Conservative fallback patterns used when model dependencies are unavailable.
DISEASE_PATTERN = re.compile(
    r"\b([a-z][a-z\- ]{2,60}(?:cancer|carcinoma|tumou?r|disease|syndrome|lesion|fibrosis|diabetes|obesity|cirrhosis|adenocarcinoma|inflammation|colitis|arthritis|infection))\b",
    re.IGNORECASE,
)
MICROBE_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s[a-z]{2,})?|[A-Z][a-z]+\s[a-z]+|[a-z]+\s[a-z]+\s(?:sp\.|spp\.)|[A-Z][a-z]+\s(?:sp\.|spp\.))\b"
)


def split_sentences(text: str) -> list[str]:
    chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]

    expanded: list[str] = []
    for sentence in chunks:
        expanded.extend(_chunk_long_sentence(sentence))
    return expanded


def _chunk_long_sentence(sentence: str, max_words: int = 100, stride: int = 70) -> list[str]:
    words = sentence.split()
    if len(words) <= max_words:
        return [sentence]

    chunks: list[str] = []
    start = 0
    total = len(words)
    while start < total:
        chunk = " ".join(words[start : start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_words >= total:
            break
        start += stride
    return chunks or [sentence]


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _is_microbe_like(text: str) -> bool:
    term = text.strip()
    if not term:
        return False
    lower = term.lower()
    if lower in GENERIC_MICROBE_TERMS:
        return False
    tokens = lower.split()
    if tokens and tokens[0] in NON_MICROBE_FIRST_TOKENS:
        return False

    microbes_suffix = (
        "bacter",
        "coccus",
        "bacillus",
        "bacteria",
        "bacterium",
        "microbe",
        "staphyl",
        "strept",
        "lactobac",
        "bifido",
        "escherich",
        "clostrid",
        "fusobacter",
        "ruminococcus",
    )
    if any(x in lower for x in microbes_suffix):
        return True

    # Keep genus/species style only when genus is plausible microbiology.
    genus_species = re.search(r"^([A-Z][a-z]+)\s([a-z]{2,})$", term)
    if genus_species and genus_species.group(1).lower() in COMMON_MICROBE_GENERA:
        return True

    # Support abbreviated genus notation, e.g. "E. coli".
    if re.search(r"^[A-Z]\.\s?[a-z]{2,}$", term):
        return True
    return False


class UMLSNormalizer:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self._nlp = None
        self._linker = None
        self.available = False
        if not enabled:
            return

        try:
            import spacy  # type: ignore
            from scispacy.linking import EntityLinker  # type: ignore
        except Exception:
            return

        try:
            nlp = spacy.load("en_core_sci_lg")
            if "ner" in nlp.pipe_names:
                nlp.remove_pipe("ner")
            linker = EntityLinker(nlp=nlp, resolve_abbreviations=True, linker_name="umls")
        except Exception:
            return

        self._nlp = nlp
        self._linker = linker
        self.available = True

    def normalize(self, text: str, allowed_tuis: set[str] | None = None) -> dict[str, Any] | None:
        if not self.available or not self._nlp or not self._linker:
            return None

        try:
            doc = self._nlp(text)
            doc = self._linker(doc)
        except Exception:
            return None

        best: dict[str, Any] | None = None
        for ent in doc.ents:
            kb_ents = getattr(ent._, "kb_ents", [])
            if not kb_ents:
                continue
            cui, sim = kb_ents[0]
            info = self._linker.kb.cui_to_entity.get(cui)
            if info is None:
                continue
            tuis = info[3] if len(info) > 3 else []
            tui = tuis[0] if tuis else None
            if allowed_tuis and tui not in allowed_tuis:
                continue
            candidate = {
                "text": ent.text,
                "cui": str(cui),
                "tui": str(tui) if tui else None,
                "similarity": float(sim),
                "official_name": info[1] if len(info) > 1 else None,
            }
            if best is None or float(candidate["similarity"]) > float(best["similarity"]):
                best = candidate
        return best


class DiseaseExtractor:
    def __init__(
        self,
        mode: str,
        base_model: str,
        checkpoint: str | None,
        batch_size: int = 4,
    ) -> None:
        self.mode = mode
        self.base_model = base_model
        self.checkpoint = checkpoint
        self.batch_size = max(1, int(batch_size))
        self.effective_mode = mode
        self._adapter_pipe = None
        self._bc5cdr_nlp = None

        if mode == "scibert_adapter":
            self._adapter_pipe = self._load_adapter_pipe()
            if self._adapter_pipe is not None:
                return
            # Mandatory fallback path.
            self.effective_mode = "bc5cdr"

        if self.effective_mode == "bc5cdr":
            self._bc5cdr_nlp = self._load_bc5cdr()

    def _load_adapter_pipe(self) -> Any:
        if not self.checkpoint:
            return None
        try:
            from transformers import pipeline  # type: ignore
        except Exception:
            return None

        model_ref = self.checkpoint
        try:
            return pipeline(
                "token-classification",
                model=model_ref,
                tokenizer=model_ref,
                aggregation_strategy="simple",
            )
        except Exception:
            try:
                return pipeline(
                    "token-classification",
                    model=model_ref,
                    tokenizer=self.base_model,
                    aggregation_strategy="simple",
                )
            except Exception:
                return None

    def _load_bc5cdr(self) -> Any:
        try:
            import spacy  # type: ignore
        except Exception:
            return None

        try:
            return spacy.load("en_ner_bc5cdr_md")
        except Exception:
            return None

    def extract(self, sentence: str) -> list[dict[str, Any]]:
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]) -> list[list[dict[str, Any]]]:
        if not sentences:
            return []

        if self._adapter_pipe is not None:
            try:
                raw = self._adapter_pipe(sentences, batch_size=self.batch_size)
            except Exception:
                raw = []
            return [self._rows_from_adapter_output(rows) for rows in _normalize_batch_output(raw, len(sentences))]

        if self._bc5cdr_nlp is not None:
            try:
                docs = list(self._bc5cdr_nlp.pipe(sentences, batch_size=self.batch_size))
            except Exception:
                docs = []
            if docs:
                return [self._rows_from_bc5cdr_doc(doc) for doc in docs]

        return [self._regex_extract(sentence) for sentence in sentences]

    def _rows_from_adapter_output(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in raw:
            text = _normalize_text(str(row.get("word") or ""))
            if not text:
                continue
            start = int(row.get("start") or -1)
            end = int(row.get("end") or -1)
            score = float(row.get("score") or 0.0)
            results.append(
                {
                    "text": text,
                    "start": start,
                    "end": end,
                    "score": score,
                    "label": str(row.get("entity_group") or row.get("entity") or "DISEASE"),
                    "extractor": "scibert_adapter",
                }
            )
        return _dedupe_span_results(results)

    def _rows_from_bc5cdr_doc(self, doc: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for ent in doc.ents:
            if str(ent.label_).upper() != "DISEASE":
                continue
            results.append(
                {
                    "text": ent.text,
                    "start": int(ent.start_char),
                    "end": int(ent.end_char),
                    "score": 1.0,
                    "label": "DISEASE",
                    "extractor": "bc5cdr",
                }
            )
        return _dedupe_span_results(results)

    def _regex_extract(self, sentence: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for match in DISEASE_PATTERN.finditer(sentence):
            results.append(
                {
                    "text": match.group(1),
                    "start": int(match.start(1)),
                    "end": int(match.end(1)),
                    "score": 0.45,
                    "label": "DISEASE",
                    "extractor": "regex_fallback",
                }
            )
        return _dedupe_span_results(results)


class MicrobeExtractor:
    def __init__(self, model_id: str, batch_size: int = 4) -> None:
        self.model_id = model_id
        self.batch_size = max(1, int(batch_size))
        self._pipe = None
        self.available = False

        try:
            from transformers import pipeline  # type: ignore

            self._pipe = pipeline(
                "token-classification",
                model=model_id,
                aggregation_strategy="simple",
            )
            self.available = True
        except Exception:
            self._pipe = None
            self.available = False

    def extract(self, sentence: str) -> list[dict[str, Any]]:
        return self.extract_many([sentence])[0]

    def extract_many(self, sentences: list[str]) -> list[list[dict[str, Any]]]:
        if not sentences:
            return []

        if self._pipe is None:
            return [self._regex_extract(sentence) for sentence in sentences]

        try:
            raw = self._pipe(sentences, batch_size=self.batch_size)
        except Exception:
            return [self._regex_extract(sentence) for sentence in sentences]

        out_batches = [self._rows_from_pipeline_output(rows) for rows in _normalize_batch_output(raw, len(sentences))]
        return [rows if rows else self._regex_extract(sentence) for sentence, rows in zip(sentences, out_batches)]

    def _rows_from_pipeline_output(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in raw:
            text = _normalize_text(str(row.get("word") or ""))
            if not text:
                continue
            out.append(
                {
                    "text": text,
                    "start": int(row.get("start") or -1),
                    "end": int(row.get("end") or -1),
                    "score": float(row.get("score") or 0.0),
                    "label": str(row.get("entity_group") or row.get("entity") or "ENTITY"),
                    "extractor": "distilbert_biomedical",
                }
            )
        return _dedupe_span_results(out)

    def _regex_extract(self, sentence: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for match in MICROBE_PATTERN.finditer(sentence):
            term = match.group(1)
            if not _is_microbe_like(term):
                continue
            out.append(
                {
                    "text": term,
                    "start": int(match.start(1)),
                    "end": int(match.end(1)),
                    "score": 0.4,
                    "label": "MICROBE",
                    "extractor": "regex_fallback",
                }
            )
        return _dedupe_span_results(out)


def _dedupe_span_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[tuple[int, int, str], dict[str, Any]] = {}
    for row in rows:
        text = _normalize_text(str(row.get("text") or ""))
        if not text:
            continue
        key = (int(row.get("start") or -1), int(row.get("end") or -1), text.lower())
        prev = dedup.get(key)
        if prev is None or float(row.get("score") or 0.0) > float(prev.get("score") or 0.0):
            row = dict(row)
            row["text"] = text
            dedup[key] = row
    return list(dedup.values())


def _normalize_batch_output(raw: Any, expected_len: int) -> list[list[dict[str, Any]]]:
    if expected_len <= 0:
        return []
    if raw is None:
        return [[] for _ in range(expected_len)]
    if expected_len == 1 and isinstance(raw, list) and (not raw or isinstance(raw[0], dict)):
        return [raw]
    if isinstance(raw, list) and len(raw) == expected_len and all(
        isinstance(item, list) or item is None for item in raw
    ):
        return [list(item or []) for item in raw]
    return [[] for _ in range(expected_len)]


def _extract_many(extractor: Any, sentences: list[str]) -> list[list[dict[str, Any]]]:
    if hasattr(extractor, "extract_many"):
        try:
            out = extractor.extract_many(sentences)
            if len(out) == len(sentences):
                return out
        except Exception:
            pass
    return [extractor.extract(sentence) for sentence in sentences]


def _apply_umls_and_filters(
    rows: list[dict[str, Any]],
    *,
    normalizer: UMLSNormalizer,
    allowed_tuis: set[str] | None,
    entity_type: str,
) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        text = _normalize_text(str(row.get("text") or ""))
        if not text:
            continue

        normalized = normalizer.normalize(text, allowed_tuis=allowed_tuis)
        payload = dict(row)
        payload["text"] = text

        if normalized is not None:
            payload["cui"] = normalized.get("cui")
            payload["tui"] = normalized.get("tui")
            payload["umls_similarity"] = normalized.get("similarity")
            payload["official_name"] = normalized.get("official_name")

        if entity_type == "microbe":
            if normalized is None and not _is_microbe_like(text):
                continue
            cleaned_span, reason = clean_subject_span(payload["text"], subject_node_type="Microbe")
        elif entity_type == "disease":
            cleaned_span, reason = clean_disease_span(payload["text"])
        else:
            continue

        if reason is not None or cleaned_span is None:
            continue

        payload["text"] = cleaned_span.canonical
        key = cleaned_span.canonical
        prev = dedup.get(key)
        if prev is None or float(payload.get("score") or 0.0) > float(prev.get("score") or 0.0):
            dedup[key] = payload

    return list(dedup.values())


def _paper_text(paper: dict[str, Any]) -> tuple[str, str]:
    return paper_text(paper)


def build_entity_and_relation_rows(
    *,
    papers: list[dict[str, Any]],
    disease_extractor: DiseaseExtractor,
    microbe_extractor: MicrobeExtractor,
    normalizer: UMLSNormalizer,
    ner_batch_size: int = 4,
) -> tuple[list[EntitySentenceRecord], list[RelationInputRecord], dict[str, int]]:
    entity_rows: list[EntitySentenceRecord] = []
    relation_rows: list[RelationInputRecord] = []

    metrics = {
        "papers_processed": 0,
        "sentences_processed": 0,
        "sentences_with_pairs": 0,
        "disease_mentions": 0,
        "microbe_mentions": 0,
        "relation_rows": 0,
        "microbe_sentences_evaluated": 0,
        "microbe_sentences_skipped_no_disease": 0,
    }

    for paper in papers:
        metrics["papers_processed"] += 1
        pmid = str(paper.get("pmid") or "")
        paper_text, source_text = _paper_text(paper)
        if not pmid or not paper_text:
            continue

        impact_factor = paper.get("impact_factor")
        quartile = paper.get("quartile")

        sentences = split_sentences(paper_text)
        metrics["sentences_processed"] += len(sentences)

        for batch_start in range(0, len(sentences), max(1, ner_batch_size)):
            batch_sentences = sentences[batch_start : batch_start + max(1, ner_batch_size)]
            diseases_raw_batch = _extract_many(disease_extractor, batch_sentences)

            microbes_raw_batch: list[list[dict[str, Any]]] = [[] for _ in batch_sentences]
            candidate_indices = [idx for idx, rows in enumerate(diseases_raw_batch) if rows]
            metrics["microbe_sentences_skipped_no_disease"] += len(batch_sentences) - len(candidate_indices)
            if candidate_indices:
                candidate_sentences = [batch_sentences[idx] for idx in candidate_indices]
                candidate_microbes = _extract_many(microbe_extractor, candidate_sentences)
                metrics["microbe_sentences_evaluated"] += len(candidate_sentences)
                for idx, microbes_raw in zip(candidate_indices, candidate_microbes):
                    microbes_raw_batch[idx] = microbes_raw

            for local_idx, sentence in enumerate(batch_sentences):
                sent_idx = batch_start + local_idx
                diseases_raw = diseases_raw_batch[local_idx]
                microbes_raw = microbes_raw_batch[local_idx]

                diseases = _apply_umls_and_filters(
                    diseases_raw,
                    normalizer=normalizer,
                    allowed_tuis=DISEASE_TUIS,
                    entity_type="disease",
                )
                microbes = _apply_umls_and_filters(
                    microbes_raw,
                    normalizer=normalizer,
                    allowed_tuis={"T007"},
                    entity_type="microbe",
                )

                if not diseases or not microbes:
                    continue

                metrics["disease_mentions"] += len(diseases)
                metrics["microbe_mentions"] += len(microbes)
                metrics["sentences_with_pairs"] += 1

                record_id = _stable_id(pmid, str(sent_idx), sentence)
                entity_rows.append(
                    EntitySentenceRecord(
                        record_id=record_id,
                        pmid=pmid,
                        sentence=sentence,
                        sentence_index=sent_idx,
                        diseases=diseases,
                        microbes=microbes,
                        source_text=source_text,
                        extraction_meta={
                            "disease_mode": disease_extractor.effective_mode,
                            "microbe_model": microbe_extractor.model_id,
                            "umls_linker": normalizer.available,
                        },
                        paper_title=str(paper.get("title") or "") or None,
                    )
                )

                for disease in diseases:
                    disease_text = str(disease.get("text") or "")
                    for microbe in microbes:
                        microbe_text = str(microbe.get("text") or "")

                        row_id = _stable_id(record_id, disease_text, microbe_text)
                        relation_rows.append(
                            RelationInputRecord(
                                row_id=row_id,
                                pmid=pmid,
                                sentence=sentence,
                                microbe=microbe_text,
                                disease=disease_text,
                                subject_node_type="Microbe",
                                subject_node=microbe_text,
                                impact_factor=float(impact_factor) if isinstance(impact_factor, (int, float)) else None,
                                quartile=str(quartile) if quartile not in (None, "", "NA") else None,
                                entity_sentence_id=record_id,
                                disease_cui=(str(disease.get("cui")) if disease.get("cui") else None),
                                microbe_cui=(str(microbe.get("cui")) if microbe.get("cui") else None),
                                source="text_ner_minerva",
                            )
                        )
                        metrics["relation_rows"] += 1

    return entity_rows, relation_rows, metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MINERVA-style text NER stage for disease/microbe extraction.")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--entity-output", default="artifacts/entity_sentences.jsonl")
    parser.add_argument("--relation-output", default="artifacts/relation_input.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")

    parser.add_argument("--disease-ner-mode", choices=["scibert_adapter", "bc5cdr"], default="scibert_adapter")
    parser.add_argument("--disease-ner-base-model", default="allenai/scibert_scivocab_uncased")
    parser.add_argument("--disease-ner-checkpoint", default="")
    parser.add_argument("--microbe-ner-model-id", default="d4data/biomedical-ner-all")
    parser.add_argument("--ner-batch-size", type=int, default=4)
    parser.add_argument("--umls-linker", choices=["on", "off"], default="on")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    papers = read_jsonl(args.papers) if Path(args.papers).exists() else []

    disease_extractor = DiseaseExtractor(
        mode=args.disease_ner_mode,
        base_model=args.disease_ner_base_model,
        checkpoint=(args.disease_ner_checkpoint or None),
        batch_size=args.ner_batch_size,
    )
    microbe_extractor = MicrobeExtractor(model_id=args.microbe_ner_model_id, batch_size=args.ner_batch_size)
    normalizer = UMLSNormalizer(enabled=args.umls_linker == "on")

    entity_rows, relation_rows, metrics = build_entity_and_relation_rows(
        papers=papers,
        disease_extractor=disease_extractor,
        microbe_extractor=microbe_extractor,
        normalizer=normalizer,
        ner_batch_size=args.ner_batch_size,
    )

    if args.validate_schema:
        entity_schema = load_schema("entity_sentences.schema.json")
        relation_schema = load_schema("relation_input.schema.json")
        for idx, row in enumerate(entity_rows):
            try:
                validate_record(to_dict(row), entity_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"entity_sentences[{idx}] invalid: {exc}") from exc
        for idx, row in enumerate(relation_rows):
            try:
                validate_record(to_dict(row), relation_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_input[{idx}] invalid: {exc}") from exc

    entity_count = write_jsonl(args.entity_output, entity_rows)
    relation_count = write_jsonl(args.relation_output, relation_rows)

    stage_metrics = {
        **metrics,
        "entity_sentences_out": entity_count,
        "relation_rows_out": relation_count,
        "disease_mode_requested": args.disease_ner_mode,
        "disease_mode_effective": disease_extractor.effective_mode,
        "microbe_model_id": args.microbe_ner_model_id,
        "microbe_model_available": microbe_extractor.available,
        "ner_batch_size": args.ner_batch_size,
        "umls_linker_enabled": args.umls_linker == "on",
        "umls_linker_available": normalizer.available,
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="text_ner_minerva",
        params={
            "papers": args.papers,
            "disease_ner_mode": args.disease_ner_mode,
            "disease_ner_base_model": args.disease_ner_base_model,
            "disease_ner_checkpoint": args.disease_ner_checkpoint or None,
            "microbe_ner_model_id": args.microbe_ner_model_id,
            "umls_linker": args.umls_linker,
        },
        metrics=stage_metrics,
        outputs={
            "entity_sentences": str(Path(args.entity_output).resolve()),
            "relation_input": str(Path(args.relation_output).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"metrics": stage_metrics, "entity_output": args.entity_output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
