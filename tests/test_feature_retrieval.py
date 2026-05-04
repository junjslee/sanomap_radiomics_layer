"""Unit tests for src/feature_retrieval.py.

These tests use a stub encoder that returns hand-crafted embeddings so
the test suite does not download 600MB of ModernBERT weights or require
MPS at test time. The math (mean pooling, L2 normalization, top-k
search, threshold calibration) is the same regardless of how vectors
were produced.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pytest

from src.feature_retrieval import (
    DEFAULT_THRESHOLD,
    FeatureCandidateRetriever,
    FeatureConcept,
    RetrievedCandidate,
    calibrate_threshold,
    default_feature_concepts,
)


class StubEncoder:
    """Encoder stub that returns deterministic L2-normalized vectors.

    Each input string is hashed-ish into a 4-dim unit vector. Substring
    overlap between query and corpus produces higher similarity, mimicking
    the structural property the real encoder provides.
    """

    embed_dim = 4

    def encode(self, texts: Sequence[str], batch_size: int = 16) -> np.ndarray:
        rows: list[np.ndarray] = []
        for t in texts:
            tl = t.lower()
            v = np.array([
                1.0 if "muscle" in tl else 0.0,
                1.0 if "fat" in tl or "adipose" in tl else 0.0,
                1.0 if "bone" in tl else 0.0,
                1.0 if "liver" in tl or "hepatic" in tl else 0.0,
            ], dtype=np.float32)
            if v.sum() == 0:
                # Off-axis residual so empty queries are not identically zero
                v = np.array([0.05, 0.05, 0.05, 0.05], dtype=np.float32)
            v /= np.linalg.norm(v)
            rows.append(v)
        return np.vstack(rows).astype(np.float32)


# --------------------------------------------------------------------------- #
#  FeatureConcept
# --------------------------------------------------------------------------- #
def test_concept_document_combines_canonical_and_synonyms():
    c = FeatureConcept(
        canonical="skeletal_muscle_index",
        node_type="BodyCompositionFeature",
        synonyms=["SMI", "L3 muscle area"],
        umls_preferred="Skeletal Muscle Index",
    )
    doc = c.concept_document()
    assert "skeletal muscle index" in doc.lower()
    assert "SMI" in doc
    assert "L3 muscle area" in doc
    assert "Skeletal Muscle Index" in doc


def test_concept_document_handles_no_synonyms():
    c = FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature")
    assert c.concept_document() == "sarcopenia"


def test_default_concepts_include_core_features():
    canonicals = {c.canonical for c in default_feature_concepts()}
    for required in {
        "sarcopenia",
        "skeletal_muscle_index",
        "visceral_adipose_tissue",
        "subcutaneous_adipose_tissue",
        "myosteatosis",
        "body_fat",
        "bone_mineral_density",
    }:
        assert required in canonicals


def test_default_threshold_is_set():
    for c in default_feature_concepts():
        assert c.threshold == DEFAULT_THRESHOLD


# --------------------------------------------------------------------------- #
#  Retriever — indexing
# --------------------------------------------------------------------------- #
def _records():
    return [
        {"pmid": "P1", "sentence": "muscle wasting was severe", "microbes": [{"text": "Akkermansia"}]},
        {"pmid": "P2", "sentence": "visceral fat increased",  "microbes": [{"text": "Bacteroides"}]},
        {"pmid": "P3", "sentence": "bone density decreased",  "microbes": [{"text": "Bifidobacterium"}]},
        {"pmid": "P4", "sentence": "hepatic steatosis observed", "microbes": [{"text": "Faecalibacterium"}]},
        {"pmid": "P5", "sentence": "no relevant phenotype here", "microbes": [{"text": "Eubacterium"}]},
        {"pmid": "P6", "sentence": "muscle fat infiltration", "microbes": []},  # no microbe
    ]


def test_build_corpus_index_populates_state():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature",
                        synonyms=["muscle wasting"])],
    )
    retriever.build_corpus_index(_records())
    assert retriever.sentence_emb is not None
    assert retriever.sentence_emb.shape == (6, 4)
    assert len(retriever.sentence_records) == 6


def test_retrieval_returns_microbe_bearing_sentences_only():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature",
                        synonyms=["muscle wasting"], threshold=0.5)],
    )
    retriever.build_corpus_index(_records())
    cands = retriever.candidates_for_concept(0, top_k=10)
    pmids = {c.pmid for c in cands}
    assert "P1" in pmids                  # muscle-positive sentence
    assert "P6" not in pmids              # microbe-absent sentence rejected
    for c in cands:
        assert c.feature_canonical == "sarcopenia"
        assert c.retrieval_similarity >= 0.5


def test_retrieval_threshold_filters_low_similarity():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature",
                        synonyms=["muscle wasting"], threshold=0.99)],
    )
    retriever.build_corpus_index(_records())
    cands = retriever.candidates_for_concept(0, top_k=10)
    # With τ=0.99, only sentences whose embeddings exactly align with the
    # muscle axis qualify. The stub maps "muscle wasting" → [1,0,0,0] and
    # "muscle fat infiltration" → [1,1,0,0]/√2 ≈ 0.707 — under 0.99.
    assert {c.pmid for c in cands} == {"P1"}


def test_retrieval_threshold_override_at_call_time():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature",
                        synonyms=["muscle wasting"], threshold=0.99)],
    )
    retriever.build_corpus_index(_records())
    cands = retriever.candidates_for_concept(0, top_k=10, threshold=0.0)
    assert len(cands) == 5  # all microbe-bearing records pass τ=0


def test_retrieval_can_disable_microbe_requirement():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="myosteatosis", node_type="BodyCompositionFeature",
                        synonyms=["muscle fat infiltration"], threshold=0.5)],
    )
    retriever.build_corpus_index(_records())
    no_microbe = retriever.candidates_for_concept(0, top_k=10, require_microbe=False)
    assert any(c.pmid == "P6" for c in no_microbe)


def test_retrieval_results_sorted_descending_by_similarity():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="body_fat", node_type="BodyCompositionFeature",
                        synonyms=["fat", "adipose"], threshold=0.0)],
    )
    retriever.build_corpus_index(_records())
    cands = retriever.candidates_for_concept(0, top_k=10)
    sims = [c.retrieval_similarity for c in cands]
    assert sims == sorted(sims, reverse=True)


def test_retrieval_concept_lookup_by_object():
    encoder = StubEncoder()
    concept = FeatureConcept(canonical="bone_mineral_density",
                             node_type="BodyCompositionFeature",
                             synonyms=["bone"], threshold=0.5)
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [concept],
    )
    retriever.build_corpus_index(_records())
    cands = retriever.candidates_for_concept(concept, top_k=10)
    assert any(c.pmid == "P3" for c in cands)


def test_retrieval_unknown_concept_raises():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature")],
    )
    retriever.build_corpus_index(_records())
    other = FeatureConcept(canonical="other", node_type="BodyCompositionFeature")
    with pytest.raises(KeyError):
        retriever.candidates_for_concept(other)


def test_retrieval_requires_index_built():
    encoder = StubEncoder()
    retriever = FeatureCandidateRetriever(
        encoder,  # type: ignore[arg-type]
        [FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature")],
    )
    with pytest.raises(RuntimeError):
        retriever.candidates_for_concept(0)


def test_retrieved_candidate_as_dict():
    rc = RetrievedCandidate(
        pmid="P1", sentence="muscle wasting", microbes=[{"text": "Akk"}],
        feature_canonical="sarcopenia",
        feature_node_type="BodyCompositionFeature",
        feature_cui=None, retrieval_similarity=0.91,
        source_record={"pmid": "P1"},
    )
    d = rc.as_dict()
    assert d["pmid"] == "P1"
    assert d["retrieval_similarity"] == pytest.approx(0.91)
    assert "source_record" not in d  # not part of public payload


# --------------------------------------------------------------------------- #
#  Calibration
# --------------------------------------------------------------------------- #
def test_calibrate_picks_tau_above_precision_floor():
    encoder = StubEncoder()
    concept = FeatureConcept(canonical="sarcopenia",
                             node_type="BodyCompositionFeature",
                             synonyms=["muscle wasting"])
    dev = [
        ("muscle wasting was severe", True),
        ("muscle fat infiltration", True),     # ambiguous: positive but lower sim
        ("hepatic steatosis observed", False),
        ("visceral fat increased", False),
        ("bone density decreased", False),
    ]
    result = calibrate_threshold(encoder, concept, dev,  # type: ignore[arg-type]
                                 target_precision=0.99, min_recall=0.0)
    assert result["concept"] == "sarcopenia"
    assert result["precision"] >= 0.99
    assert result["tp"] >= 1


def test_calibrate_handles_empty_dev_set():
    encoder = StubEncoder()
    concept = FeatureConcept(canonical="sarcopenia", node_type="BodyCompositionFeature")
    result = calibrate_threshold(encoder, concept, [])  # type: ignore[arg-type]
    assert result["n_dev"] == 0
    assert np.isnan(result["tau"])


def test_calibrate_respects_min_recall():
    """If min_recall is too high, no τ qualifies and result keeps default τ=inf."""
    encoder = StubEncoder()
    concept = FeatureConcept(canonical="sarcopenia",
                             node_type="BodyCompositionFeature",
                             synonyms=["muscle wasting"])
    dev = [
        ("muscle wasting", True),
        ("hepatic steatosis", False),
    ]
    # Only one positive; recall is binary 0 or 1. Demand >100% — impossible.
    result = calibrate_threshold(encoder, concept, dev,  # type: ignore[arg-type]
                                 target_precision=0.5, min_recall=2.0)
    assert result["tau"] == float("inf")
