"""Dense-retrieval candidate generation for body-composition feature mentions.

Replaces the hand-curated ``_FEATURE_VOCAB`` substring filter in
``scripts/extract_microbe_feature_relations.py`` with FAISS-indexed (or
numpy-fallback) cosine retrieval over BioClinical-ModernBERT embeddings.

Design rationale (for the methods section of the paper):
    - Substring matching has zero generalization to paraphrastic mentions
      ("loss of muscle mass at L3" → sarcopenia is invisible to the
      vocabulary). Recall ceiling = union of enumerated aliases.
    - Domain-pretrained transformer (BioClinical-ModernBERT-base, 53.5B
      tokens of PubMed/PMC + clinical notes; Sounack et al. 2025) places
      paraphrastic mentions within cosine ε of canonical centroids.
    - 8K context window encodes paragraph-level passages so definitions
      that span multiple sentences are not truncated.
    - Per-concept threshold τ_C is calibratable from a held-out labeled
      development set (precision-floor optimization).

The retrieval module is the FIRST gate in the pipeline. Its output feeds
into the UMLS TUI gate (Task 1) and then the relation classification
step.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

try:  # FAISS is optional — numpy fallback works for current corpus size
    import faiss  # type: ignore

    _HAS_FAISS = True
except ImportError:
    faiss = None  # type: ignore
    _HAS_FAISS = False

try:  # transformers + torch are required
    import torch
    from transformers import AutoModel, AutoTokenizer  # type: ignore

    _HAS_TRANSFORMERS = True
except ImportError:
    torch = None  # type: ignore
    AutoModel = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    _HAS_TRANSFORMERS = False


# --------------------------------------------------------------------------- #
#  Defaults
# --------------------------------------------------------------------------- #
DEFAULT_MODEL_ID = "thomas-sounack/BioClinical-ModernBERT-base"
DEFAULT_MAX_LEN = 1024  # paragraph-level encoding; ModernBERT supports up to 8192
DEFAULT_THRESHOLD = 0.62  # uncalibrated default; calibrate per-concept


# --------------------------------------------------------------------------- #
#  Concepts
# --------------------------------------------------------------------------- #
@dataclass
class FeatureConcept:
    """A canonical body-composition / radiomic feature with synonyms.

    The ``concept_document`` rendering is what gets embedded as the
    centroid for retrieval. Richer documents (canonical + synonyms +
    UMLS preferred term) produce more robust centroids than the
    canonical name alone.
    """

    canonical: str  # graph node name, e.g. "skeletal_muscle_index"
    node_type: str  # "BodyCompositionFeature" | "RadiomicFeature"
    synonyms: list[str] = field(default_factory=list)
    umls_preferred: str | None = None
    cui: str | None = None
    threshold: float = DEFAULT_THRESHOLD  # per-concept τ, calibrated externally

    def concept_document(self) -> str:
        """Rich text representation embedded as the concept centroid."""
        parts = [self.canonical.replace("_", " ")] + list(self.synonyms)
        if self.umls_preferred:
            parts.append(self.umls_preferred)
        # Pipe-separator gives the encoder a natural delimiter.
        return " | ".join(p for p in parts if p)


def default_feature_concepts() -> list[FeatureConcept]:
    """Project-default concept set, mirroring the prior ``_FEATURE_VOCAB``.

    Synonyms are deliberately broad — embedding retrieval performs best
    when the centroid is built from many surface forms. Add CUIs once
    UMLS lookups are run.
    """
    return [
        FeatureConcept(
            canonical="sarcopenia",
            node_type="BodyCompositionFeature",
            synonyms=[
                "sarcopenic",
                "muscle wasting",
                "low skeletal muscle",
                "muscle depletion",
                "age-related muscle loss",
            ],
        ),
        FeatureConcept(
            canonical="skeletal_muscle_index",
            node_type="BodyCompositionFeature",
            synonyms=[
                "SMI",
                "skeletal muscle index",
                "L3 muscle area",
                "cross-sectional muscle area at L3",
                "lumbar muscle area",
            ],
        ),
        FeatureConcept(
            canonical="visceral_adipose_tissue",
            node_type="BodyCompositionFeature",
            synonyms=[
                "VAT",
                "visceral adipose tissue",
                "visceral adiposity",
                "visceral fat",
                "intra-abdominal fat",
            ],
        ),
        FeatureConcept(
            canonical="subcutaneous_adipose_tissue",
            node_type="BodyCompositionFeature",
            synonyms=[
                "SAT",
                "subcutaneous adipose tissue",
                "subcutaneous fat",
                "abdominal subcutaneous fat",
            ],
        ),
        FeatureConcept(
            canonical="myosteatosis",
            node_type="BodyCompositionFeature",
            synonyms=[
                "muscle fat infiltration",
                "intramuscular fat",
                "low muscle attenuation",
                "fatty infiltration of muscle",
            ],
        ),
        FeatureConcept(
            canonical="body_fat",
            node_type="BodyCompositionFeature",
            synonyms=[
                "fat mass",
                "total body fat",
                "body fat percentage",
                "adiposity",
            ],
        ),
        FeatureConcept(
            canonical="bone_mineral_density",
            node_type="BodyCompositionFeature",
            synonyms=[
                "BMD",
                "bone mineral density",
                "DXA bone density",
                "T-score",
            ],
        ),
        FeatureConcept(
            canonical="hepatic_steatosis",
            node_type="BodyCompositionFeature",
            synonyms=[
                "liver fat",
                "fatty liver",
                "liver attenuation",
                "PDFF",
                "proton density fat fraction",
            ],
        ),
        FeatureConcept(
            canonical="muscle_attenuation",
            node_type="BodyCompositionFeature",
            synonyms=[
                "muscle radiation attenuation",
                "muscle Hounsfield units",
                "MRA",
            ],
        ),
    ]


# --------------------------------------------------------------------------- #
#  Encoder
# --------------------------------------------------------------------------- #
class BiomedEncoder:
    """Wraps BioClinical-ModernBERT for sentence/concept embedding."""

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        device: str | None = None,
        max_length: int = DEFAULT_MAX_LEN,
    ) -> None:
        if not _HAS_TRANSFORMERS:
            raise RuntimeError(
                "transformers + torch are required for BiomedEncoder. "
                "Install: `pip install transformers torch`."
            )
        # Auto-pick MPS on Apple Silicon, CUDA where available, else CPU.
        if device is None:
            if torch.backends.mps.is_available():  # type: ignore[union-attr]
                device = "mps"
            elif torch.cuda.is_available():  # type: ignore[union-attr]
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        self.max_length = int(max_length)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)  # type: ignore[union-attr]
        self.model = AutoModel.from_pretrained(model_id).to(device).eval()  # type: ignore[union-attr]
        self.embed_dim: int = int(self.model.config.hidden_size)

    @torch.inference_mode()  # type: ignore[misc]
    def encode(
        self,
        texts: Sequence[str],
        batch_size: int = 16,
    ) -> np.ndarray:
        """Mean-pooled, attention-masked, L2-normalized embeddings.

        Returns float32 array of shape (len(texts), embed_dim).
        Inner product over these vectors equals cosine similarity.
        """
        if not texts:
            return np.zeros((0, self.embed_dim), dtype=np.float32)
        outputs: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            enc = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            hidden = self.model(**enc).last_hidden_state  # (B, L, H)
            mask = enc.attention_mask.unsqueeze(-1).float()
            summed = (hidden * mask).sum(dim=1)
            denom = mask.sum(dim=1).clamp(min=1.0)
            pooled = summed / denom
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=-1)  # type: ignore[union-attr]
            outputs.append(pooled.cpu().numpy().astype(np.float32))
        return np.vstack(outputs)


# --------------------------------------------------------------------------- #
#  Retriever
# --------------------------------------------------------------------------- #
@dataclass
class RetrievedCandidate:
    pmid: str
    sentence: str
    microbes: list[Any]
    feature_canonical: str
    feature_node_type: str
    feature_cui: str | None
    retrieval_similarity: float
    source_record: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "sentence": self.sentence,
            "microbes": self.microbes,
            "feature_canonical": self.feature_canonical,
            "feature_node_type": self.feature_node_type,
            "feature_cui": self.feature_cui,
            "retrieval_similarity": self.retrieval_similarity,
        }


class FeatureCandidateRetriever:
    """Two-tower dense retrieval over corpus sentences vs feature centroids."""

    def __init__(
        self,
        encoder: BiomedEncoder,
        concepts: Sequence[FeatureConcept],
    ) -> None:
        self.encoder = encoder
        self.concepts: list[FeatureConcept] = list(concepts)
        self.concept_emb: np.ndarray = encoder.encode(
            [c.concept_document() for c in self.concepts]
        )
        # Corpus state populated by ``build_corpus_index``.
        self.sentence_records: list[dict[str, Any]] = []
        self.sentence_emb: np.ndarray | None = None
        self._faiss_index: Any | None = None

    # ------------------------------------------------------------------ #
    #  Indexing
    # ------------------------------------------------------------------ #
    def build_corpus_index(
        self,
        sentence_records: Sequence[dict[str, Any]],
        *,
        sentence_field: str = "sentence",
        batch_size: int = 32,
    ) -> None:
        """Encode and index a corpus of sentence records.

        sentence_records: each dict carries at minimum:
            ``pmid`` (str), ``sentence`` (str), ``microbes`` (list).
        """
        sentences = [str(r.get(sentence_field) or "") for r in sentence_records]
        emb = self.encoder.encode(sentences, batch_size=batch_size)
        self.sentence_records = list(sentence_records)
        self.sentence_emb = emb
        if _HAS_FAISS and emb.shape[0] > 0:
            index = faiss.IndexFlatIP(self.encoder.embed_dim)  # type: ignore[union-attr]
            index.add(emb)
            self._faiss_index = index
        else:
            self._faiss_index = None

    # ------------------------------------------------------------------ #
    #  Retrieval
    # ------------------------------------------------------------------ #
    def candidates_for_concept(
        self,
        concept: FeatureConcept | int,
        *,
        top_k: int = 200,
        threshold: float | None = None,
        require_microbe: bool = True,
    ) -> list[RetrievedCandidate]:
        """Return top-k sentences whose embedding similarity > threshold.

        ``concept`` is either a FeatureConcept (matched by canonical) or
        the integer index into ``self.concepts``.
        """
        if self.sentence_emb is None:
            raise RuntimeError("Call build_corpus_index() before retrieval.")
        idx = self._concept_index(concept)
        c = self.concepts[idx]
        tau = float(threshold if threshold is not None else c.threshold)
        query = self.concept_emb[idx : idx + 1]

        if self._faiss_index is not None:
            scores, ids = self._faiss_index.search(query, top_k)
            score_arr = scores[0]
            id_arr = ids[0]
        else:
            # Numpy fallback: cosine = inner product on L2-normalized vectors
            sims = (self.sentence_emb @ query.T).reshape(-1)  # (N,)
            top_k_eff = min(top_k, sims.shape[0])
            id_arr = np.argpartition(-sims, kth=top_k_eff - 1)[:top_k_eff]
            id_arr = id_arr[np.argsort(-sims[id_arr])]
            score_arr = sims[id_arr]

        results: list[RetrievedCandidate] = []
        for score, sid in zip(score_arr, id_arr):
            if sid < 0:
                continue
            score_f = float(score)
            if score_f < tau:
                continue
            rec = self.sentence_records[int(sid)]
            microbes = rec.get("microbes") or []
            if require_microbe and not microbes:
                continue
            results.append(
                RetrievedCandidate(
                    pmid=str(rec.get("pmid", "")),
                    sentence=str(rec.get("sentence", "")),
                    microbes=list(microbes),
                    feature_canonical=c.canonical,
                    feature_node_type=c.node_type,
                    feature_cui=c.cui,
                    retrieval_similarity=score_f,
                    source_record=rec,
                )
            )
        return results

    def _concept_index(self, concept: FeatureConcept | int) -> int:
        if isinstance(concept, int):
            if not 0 <= concept < len(self.concepts):
                raise IndexError(f"concept index {concept} out of range")
            return concept
        for i, c in enumerate(self.concepts):
            if c.canonical == concept.canonical:
                return i
        raise KeyError(f"concept {concept.canonical!r} not in retriever")


# --------------------------------------------------------------------------- #
#  Threshold calibration
# --------------------------------------------------------------------------- #
def calibrate_threshold(
    encoder: BiomedEncoder,
    concept: FeatureConcept,
    labeled_dev_set: Iterable[tuple[str, bool]],
    *,
    target_precision: float = 0.85,
    min_recall: float = 0.05,
) -> dict[str, Any]:
    """Find τ that maximizes recall subject to precision >= target.

    labeled_dev_set: iterable of (sentence, is_positive_for_this_concept).
    Returns a dict with chosen τ and operating-point statistics.
    """
    pairs = list(labeled_dev_set)
    if not pairs:
        return {
            "concept": concept.canonical,
            "tau": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "n_dev": 0,
        }
    sentences = [s for s, _ in pairs]
    labels = np.array([1 if y else 0 for _, y in pairs], dtype=np.int64)
    sent_emb = encoder.encode(sentences)
    concept_emb = encoder.encode([concept.concept_document()])
    scores = (sent_emb @ concept_emb.T).reshape(-1)

    # Sweep τ over observed score values; pick lowest τ satisfying precision
    candidates = sorted(set(np.round(scores, 4)), reverse=True)
    best: dict[str, Any] = {
        "concept": concept.canonical,
        "tau": float("inf"),
        "precision": 0.0,
        "recall": 0.0,
        "n_dev": len(pairs),
    }
    for tau in candidates:
        predicted = (scores >= tau).astype(np.int64)
        if predicted.sum() == 0:
            continue
        tp = int(((predicted == 1) & (labels == 1)).sum())
        fp = int(((predicted == 1) & (labels == 0)).sum())
        fn = int(((predicted == 0) & (labels == 1)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        if precision < target_precision:
            continue
        if recall < min_recall:
            continue
        if recall > best["recall"] or (
            recall == best["recall"] and float(tau) < best["tau"]
        ):
            best = {
                "concept": concept.canonical,
                "tau": float(tau),
                "precision": float(precision),
                "recall": float(recall),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "n_dev": len(pairs),
            }
    return best


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def _cmd_calibrate(args: argparse.Namespace) -> int:
    """Run threshold calibration on a labeled dev set."""
    concepts = {c.canonical: c for c in default_feature_concepts()}
    if args.concept not in concepts:
        print(f"ERROR: unknown concept '{args.concept}'. "
              f"Choices: {sorted(concepts)}", file=sys.stderr)
        return 1
    pairs: list[tuple[str, bool]] = []
    for line in Path(args.dev_set).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        pairs.append((str(rec["sentence"]), bool(rec["is_positive"])))

    encoder = BiomedEncoder(model_id=args.model_id)
    result = calibrate_threshold(
        encoder,
        concepts[args.concept],
        pairs,
        target_precision=args.target_precision,
        min_recall=args.min_recall,
    )
    print(json.dumps(result, indent=2))
    return 0


def _cmd_retrieve(args: argparse.Namespace) -> int:
    """Smoke-test retrieval on a small JSONL corpus."""
    encoder = BiomedEncoder(model_id=args.model_id)
    retriever = FeatureCandidateRetriever(encoder, default_feature_concepts())
    records: list[dict[str, Any]] = []
    for line in Path(args.corpus).read_text().splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    retriever.build_corpus_index(records)
    out_lines: list[str] = []
    for c in retriever.concepts:
        cands = retriever.candidates_for_concept(c, top_k=args.top_k,
                                                 threshold=args.threshold)
        for cand in cands:
            out_lines.append(json.dumps(cand.as_dict()))
    output = Path(args.output)
    output.write_text("\n".join(out_lines) + ("\n" if out_lines else ""))
    print(f"Wrote {len(out_lines)} candidates → {output}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cal = sub.add_parser("calibrate", help="Calibrate τ for one concept")
    p_cal.add_argument("--concept", required=True)
    p_cal.add_argument("--dev-set", required=True,
                       help="JSONL with {sentence, is_positive} rows")
    p_cal.add_argument("--target-precision", type=float, default=0.85)
    p_cal.add_argument("--min-recall", type=float, default=0.05)
    p_cal.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    p_cal.set_defaults(func=_cmd_calibrate)

    p_ret = sub.add_parser("retrieve", help="Run retrieval over a corpus JSONL")
    p_ret.add_argument("--corpus", required=True)
    p_ret.add_argument("--output", required=True)
    p_ret.add_argument("--top-k", type=int, default=200)
    p_ret.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p_ret.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    p_ret.set_defaults(func=_cmd_retrieve)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_MODEL_ID",
    "DEFAULT_MAX_LEN",
    "DEFAULT_THRESHOLD",
    "FeatureConcept",
    "default_feature_concepts",
    "BiomedEncoder",
    "RetrievedCandidate",
    "FeatureCandidateRetriever",
    "calibrate_threshold",
]
