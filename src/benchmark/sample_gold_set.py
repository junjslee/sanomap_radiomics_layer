"""Stratified sampling of the v1 gold-label benchmark.

Produces ``artifacts/gold_set_v1_UNLABELED.jsonl`` with five strata:

  1. accepted_edge       (target 15) — every accepted CORRELATES_WITH
                                       edge already in the production
                                       artifact, plus padding.
  2. gemini_rejected     (target 50) — substring-vocab candidates that
                                       did NOT make it into the accepted
                                       set (rejected by Gemini 7/7
                                       self-consistency).
  3. vocab_excluded      (target 35) — sentences containing a microbe
                                       AND a body-composition feature
                                       OUTSIDE the current
                                       _FEATURE_VOCAB. Probes recall
                                       ceiling of substring matching.
  4. recall_probe        (target 30) — sentences with a microbe AND
                                       generic body-region tokens
                                       (muscle/fat/bone/liver) but no
                                       specific feature mention. Probes
                                       whether embedding retrieval would
                                       catch what vocab missed.
  5. random_co_occurrence (target 20) — sentences with a microbe AND
                                       any body-related token, sampled
                                       uniformly. Sanity baseline.

Each row is self-contained for hand-labeling. See
``docs/benchmark/annotation_schema.md`` for the labeling protocol.

Sampling is deterministic given a fixed seed; reproducing the gold set
requires only the same input files and the same seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

# Allow importing from sibling scripts without packaging
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.extract_microbe_feature_relations import _extract_candidates


# --------------------------------------------------------------------------- #
#  Stratum keywords beyond the current _FEATURE_VOCAB
# --------------------------------------------------------------------------- #
# Body-composition / radiomic features the current vocab misses.
# Sentences containing these AND a microbe entity are vocab-excluded
# and are exactly the recall losses Task 2 (embedding retrieval) is
# meant to fix.
EXTENDED_FEATURE_KEYWORDS: dict[str, str] = {
    "psoas": "psoas_muscle_area",
    "psoas muscle": "psoas_muscle_area",
    "pmi": "psoas_muscle_index",
    "intermuscular adipose": "intermuscular_adipose_tissue",
    "imat": "intermuscular_adipose_tissue",
    "epicardial adipose": "epicardial_adipose_tissue",
    "epicardial fat": "epicardial_adipose_tissue",
    "eat": "epicardial_adipose_tissue",
    "pericardial fat": "pericardial_adipose_tissue",
    "pericardial adipose": "pericardial_adipose_tissue",
    "liver fat": "hepatic_steatosis",
    "hepatic fat": "hepatic_steatosis",
    "pdff": "hepatic_steatosis",
    "proton density fat fraction": "hepatic_steatosis",
    "pancreatic fat": "pancreatic_steatosis",
    "pancreatic steatosis": "pancreatic_steatosis",
    "bone marrow fat": "bone_marrow_adiposity",
    "bone marrow adiposity": "bone_marrow_adiposity",
    "t-score": "bone_mineral_density",
    "z-score": "bone_mineral_density",
    "cachexia": "cachexia",
    "frailty": "frailty",
    "asmm": "appendicular_skeletal_muscle_mass",
    "appendicular skeletal muscle": "appendicular_skeletal_muscle_mass",
    "ffmi": "fat_free_mass_index",
    "fat-free mass index": "fat_free_mass_index",
    "cross-sectional area": "muscle_cross_sectional_area",
    "csa at l3": "muscle_cross_sectional_area",
    "l3 muscle area": "muscle_cross_sectional_area",
    "myostatin": "myostatin_level",
    "fractal dimension": "glcm_fractal_dimension",
    "glcm": "glcm_texture_feature",
    "wavelet": "wavelet_texture_feature",
}

# Generic body-region / measurement tokens used for the recall_probe
# stratum. A sentence with a microbe + one of these but NO specific
# feature mention probes whether the embedding retriever would
# correctly identify body-comp context that the substring filter
# misses. Keep abbreviations word-bounded.
GENERIC_BODY_TOKENS: set[str] = {
    "muscle", "fat", "bone", "liver", "adipose",
    "skeletal", "lean", "obesity", "weight",
}
GENERIC_BODY_ABBREVS: frozenset[str] = frozenset({"bmi", "ct", "mri", "dxa"})

# Tokens that need word-boundary matching to avoid false positives.
# All EXTENDED_FEATURE_KEYWORDS that are 4 chars or shorter are
# considered abbreviations (pmi inside pmid, eat inside eating, etc.).
# Plus the generic abbreviations for the recall-probe path.
EXTENDED_KEYWORD_ABBREVS: frozenset[str] = frozenset({
    "pmi", "imat", "eat", "pdff", "asmm", "ffmi", "glcm",
})
WORD_BOUNDARY_TOKENS: frozenset[str] = (
    GENERIC_BODY_ABBREVS | EXTENDED_KEYWORD_ABBREVS
)

# Sampling defaults
DEFAULT_SEED = 42
DEFAULT_TARGETS = {
    "accepted_edge": 15,
    "gemini_rejected": 50,
    "vocab_excluded": 35,
    "recall_probe": 30,
    "random_co_occurrence": 20,
}


# --------------------------------------------------------------------------- #
#  Data shapes
# --------------------------------------------------------------------------- #
@dataclass
class GoldRow:
    record_id: str
    pmid: str
    stratum: str
    sentence: str
    microbe: str
    candidate_feature_canonical: str | None
    candidate_feature_node_type: str | None
    pipeline_state: str
    source_file: str

    def to_unlabeled_jsonl(self) -> str:
        # Field order is intentional — annotators read top-to-bottom.
        payload = {
            "record_id": self.record_id,
            "pmid": self.pmid,
            "stratum": self.stratum,
            "sentence": self.sentence,
            "microbe": self.microbe,
            "candidate_feature_canonical": self.candidate_feature_canonical,
            "candidate_feature_node_type": self.candidate_feature_node_type,
            "pipeline_state": self.pipeline_state,
            "source_file": self.source_file,
            # Annotator slots
            "label": None,
            "evidence_type": None,
            "quantitative": None,
            "confidence": None,
            "evidence_span": None,
            "inferred_feature_canonical": None,
            "inferred_node_type": None,
            "annotator_notes": "",
            "labeled_at": None,
            "label_pass": None,
        }
        return json.dumps(payload, ensure_ascii=False)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _record_id(*parts: str) -> str:
    base = "|".join(parts)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _has_extended_feature_keyword(text_lower: str) -> tuple[str, str] | None:
    """Returns (canonical, surface_keyword) if text contains an extended
    feature keyword that the current _FEATURE_VOCAB misses, else None.

    Sorted longest-first so multi-word matches win over single-word.
    """
    keys = sorted(EXTENDED_FEATURE_KEYWORDS.keys(), key=len, reverse=True)
    for kw in keys:
        if kw in WORD_BOUNDARY_TOKENS:
            if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                return EXTENDED_FEATURE_KEYWORDS[kw], kw
        else:
            if kw in text_lower:
                return EXTENDED_FEATURE_KEYWORDS[kw], kw
    return None


def _has_generic_body_token(text_lower: str) -> bool:
    for token in GENERIC_BODY_TOKENS:
        if token in text_lower:
            return True
    for abbrev in GENERIC_BODY_ABBREVS:
        if re.search(rf"\b{re.escape(abbrev)}\b", text_lower):
            return True
    return False


def _accepted_edge_set(accepted_records: Iterable[Mapping[str, Any]]) -> set[tuple[str, str, str]]:
    """Build (pmid, microbe_lower, feature_canonical) keys of accepted edges."""
    keys: set[tuple[str, str, str]] = set()
    for rec in accepted_records:
        pmid = str(rec.get("pmid", ""))
        microbe = str(rec.get("source_node", "")).strip().lower()
        feature = str(rec.get("target_node", "")).strip()
        if pmid and microbe and feature:
            keys.add((pmid, microbe, feature))
    return keys


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# --------------------------------------------------------------------------- #
#  Stratum samplers
# --------------------------------------------------------------------------- #
def _sample_accepted(
    accepted: list[dict[str, Any]],
    target: int,
    rng: random.Random,
) -> list[GoldRow]:
    rows: list[GoldRow] = []
    # Take every accepted edge first; if more than target, downsample.
    pool = list(accepted)
    if len(pool) > target:
        pool = rng.sample(pool, target)
    for rec in pool:
        pmid = str(rec.get("pmid", ""))
        microbe = str(rec.get("source_node", ""))
        feature = str(rec.get("target_node", ""))
        node_type = str(rec.get("target_node_type", "BodyCompositionFeature"))
        evidence = str(rec.get("evidence", ""))
        # Evidence string is "PMID xxx: <sentence...>" — strip the prefix.
        if evidence.startswith("PMID "):
            try:
                _, sentence = evidence.split(":", 1)
                sentence = sentence.strip()
            except ValueError:
                sentence = evidence
        else:
            sentence = evidence
        rows.append(GoldRow(
            record_id=_record_id("acc", pmid, microbe, feature),
            pmid=pmid,
            stratum="accepted_edge",
            sentence=sentence,
            microbe=microbe,
            candidate_feature_canonical=feature,
            candidate_feature_node_type=node_type,
            pipeline_state="accepted",
            source_file=str(rec.get("source_file", "microbe_feature_relations.jsonl")),
        ))
    return rows


def _sample_gemini_rejected(
    candidates: list[dict[str, Any]],
    accepted_keys: set[tuple[str, str, str]],
    target: int,
    rng: random.Random,
) -> list[GoldRow]:
    pool = []
    for cand in candidates:
        key = (str(cand["pmid"]), str(cand["microbe"]).strip().lower(),
               str(cand["feature_canonical"]))
        if key in accepted_keys:
            continue
        pool.append(cand)
    if len(pool) > target:
        pool = rng.sample(pool, target)
    rows: list[GoldRow] = []
    for cand in pool:
        rows.append(GoldRow(
            record_id=_record_id("rej", str(cand["pmid"]),
                                 str(cand["microbe"]),
                                 str(cand["feature_canonical"])),
            pmid=str(cand["pmid"]),
            stratum="gemini_rejected",
            sentence=str(cand["sentence"]),
            microbe=str(cand["microbe"]),
            candidate_feature_canonical=str(cand["feature_canonical"]),
            candidate_feature_node_type=str(cand["feature_node_type"]),
            pipeline_state="rejected_by_gemini",
            source_file=str(cand.get("source_file", "")),
        ))
    return rows


def _sample_vocab_excluded(
    entity_records: list[tuple[dict[str, Any], str]],
    accepted_keys: set[tuple[str, str, str]],
    target: int,
    rng: random.Random,
) -> list[GoldRow]:
    """Find sentences with microbe + extended-keyword feature."""
    pool: list[GoldRow] = []
    seen: set[str] = set()
    for rec, source_file in entity_records:
        sentence = str(rec.get("sentence", ""))
        if not sentence:
            continue
        text_lower = sentence.lower()
        match = _has_extended_feature_keyword(text_lower)
        if match is None:
            continue
        canonical = match[0]
        microbes = rec.get("microbes") or []
        for m in microbes:
            mtext = m["text"] if isinstance(m, dict) else str(m)
            mtext_clean = mtext.strip().lower()
            pmid = str(rec.get("pmid", ""))
            if not (pmid and mtext_clean):
                continue
            key = (pmid, mtext_clean, canonical)
            if key in accepted_keys:
                continue  # belongs to accepted stratum
            dedup = f"{pmid}|{mtext_clean}|{canonical}"
            if dedup in seen:
                continue
            seen.add(dedup)
            pool.append(GoldRow(
                record_id=_record_id("vex", pmid, mtext_clean, canonical),
                pmid=pmid,
                stratum="vocab_excluded",
                sentence=sentence,
                microbe=mtext_clean,
                candidate_feature_canonical=canonical,
                candidate_feature_node_type="BodyCompositionFeature",
                pipeline_state="not_seen_by_pipeline",
                source_file=source_file,
            ))
    if len(pool) > target:
        pool = rng.sample(pool, target)
    return pool


def _sample_recall_probe(
    entity_records: list[tuple[dict[str, Any], str]],
    accepted_keys: set[tuple[str, str, str]],
    used_pmid_microbe_sentence: set[tuple[str, str, str]],
    target: int,
    rng: random.Random,
) -> list[GoldRow]:
    """Sentences with microbe + generic body token, no specific feature.

    Excludes anything already used in the accepted or vocab_excluded
    strata via ``used_pmid_microbe_sentence``. Sentences whose
    (pmid, microbe) pair appears in any accepted edge are also skipped
    because the accepted stratum already covers them.
    """
    accepted_pm = {(p, m) for (p, m, _) in accepted_keys}
    pool: list[GoldRow] = []
    seen: set[str] = set()
    for rec, source_file in entity_records:
        sentence = str(rec.get("sentence", ""))
        if not sentence:
            continue
        text_lower = sentence.lower()
        if _has_extended_feature_keyword(text_lower) is not None:
            continue  # belongs to vocab_excluded
        if not _has_generic_body_token(text_lower):
            continue
        microbes = rec.get("microbes") or []
        pmid = str(rec.get("pmid", ""))
        for m in microbes:
            mtext = m["text"] if isinstance(m, dict) else str(m)
            mtext_clean = mtext.strip().lower()
            if not (pmid and mtext_clean):
                continue
            if (pmid, mtext_clean) in accepted_pm:
                continue
            sent_key = (pmid, mtext_clean, sentence[:80])
            if sent_key in used_pmid_microbe_sentence:
                continue
            dedup = f"{pmid}|{mtext_clean}|{sentence[:60]}"
            if dedup in seen:
                continue
            seen.add(dedup)
            pool.append(GoldRow(
                record_id=_record_id("rec", pmid, mtext_clean, sentence[:80]),
                pmid=pmid,
                stratum="recall_probe",
                sentence=sentence,
                microbe=mtext_clean,
                candidate_feature_canonical=None,
                candidate_feature_node_type=None,
                pipeline_state="not_seen_by_pipeline",
                source_file=source_file,
            ))
    if len(pool) > target:
        pool = rng.sample(pool, target)
    return pool


def _sample_random_co_occurrence(
    entity_records: list[tuple[dict[str, Any], str]],
    target: int,
    rng: random.Random,
) -> list[GoldRow]:
    """Random microbe-bearing sentences with any body-related token."""
    pool: list[GoldRow] = []
    seen: set[str] = set()
    for rec, source_file in entity_records:
        sentence = str(rec.get("sentence", ""))
        if not sentence:
            continue
        text_lower = sentence.lower()
        if not _has_generic_body_token(text_lower):
            continue
        microbes = rec.get("microbes") or []
        if not microbes:
            continue
        m = microbes[0]
        mtext = m["text"] if isinstance(m, dict) else str(m)
        mtext_clean = mtext.strip().lower()
        pmid = str(rec.get("pmid", ""))
        if not (pmid and mtext_clean):
            continue
        dedup = f"{pmid}|{mtext_clean}|{sentence[:60]}"
        if dedup in seen:
            continue
        seen.add(dedup)
        pool.append(GoldRow(
            record_id=_record_id("rnd", pmid, mtext_clean, sentence[:80]),
            pmid=pmid,
            stratum="random_co_occurrence",
            sentence=sentence,
            microbe=mtext_clean,
            candidate_feature_canonical=None,
            candidate_feature_node_type=None,
            pipeline_state="not_seen_by_pipeline",
            source_file=source_file,
        ))
    if len(pool) > target:
        pool = rng.sample(pool, target)
    return pool


# --------------------------------------------------------------------------- #
#  Top-level driver
# --------------------------------------------------------------------------- #
def build_gold_set(
    *,
    accepted_path: Path,
    entity_sentences_paths: list[Path],
    seed: int = DEFAULT_SEED,
    targets: Mapping[str, int] | None = None,
) -> tuple[list[GoldRow], dict[str, Any]]:
    targets = dict(targets or DEFAULT_TARGETS)
    rng = random.Random(seed)

    accepted = _read_jsonl(accepted_path)
    accepted_keys = _accepted_edge_set(accepted)

    candidates = _extract_candidates(entity_sentences_paths)

    entity_records: list[tuple[dict[str, Any], str]] = []
    for path in entity_sentences_paths:
        for rec in _read_jsonl(path):
            entity_records.append((rec, path.name))

    rows: list[GoldRow] = []
    rows.extend(_sample_accepted(accepted, targets["accepted_edge"], rng))
    rows.extend(_sample_gemini_rejected(candidates, accepted_keys,
                                        targets["gemini_rejected"], rng))
    vocab_rows = _sample_vocab_excluded(entity_records, accepted_keys,
                                        targets["vocab_excluded"], rng)
    rows.extend(vocab_rows)

    # Prevent recall_probe and random_co_occurrence from re-sampling
    # the same (pmid, microbe, sentence) combinations already used.
    used_psm: set[tuple[str, str, str]] = {
        (r.pmid, r.microbe, r.sentence[:80]) for r in rows
    }
    rows.extend(_sample_recall_probe(entity_records, accepted_keys,
                                     used_psm,
                                     targets["recall_probe"], rng))
    rows.extend(_sample_random_co_occurrence(entity_records,
                                             targets["random_co_occurrence"],
                                             rng))

    # Final dedup by record_id (defensive — strata generators already dedupe
    # internally, but cross-stratum overlap is theoretically possible).
    by_id: dict[str, GoldRow] = {}
    for r in rows:
        by_id.setdefault(r.record_id, r)
    rows = list(by_id.values())

    summary = {
        "n_total": len(rows),
        "by_stratum": dict(Counter(r.stratum for r in rows)),
        "n_accepted_input": len(accepted),
        "n_candidates_input": len(candidates),
        "n_entity_sentences_input": len(entity_records),
        "seed": seed,
    }
    return rows, summary


def write_gold_set(rows: list[GoldRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for row in rows:
            f.write(row.to_unlabeled_jsonl() + "\n")


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accepted",
        default="artifacts/microbe_feature_relations.jsonl",
        type=Path,
    )
    parser.add_argument(
        "--entity-sentences",
        nargs="+",
        default=[
            "artifacts/entity_sentences_microbe_expanded.jsonl",
            "artifacts/entity_sentences_new_lanes.jsonl",
        ],
        type=Path,
    )
    parser.add_argument(
        "--output",
        default="artifacts/gold_set_v1_UNLABELED.jsonl",
        type=Path,
    )
    parser.add_argument(
        "--summary",
        default="artifacts/gold_set_v1_summary.json",
        type=Path,
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # argparse `type=Path` is only applied to user-provided values, not
    # default lists. Coerce explicitly.
    entity_paths = [Path(p) for p in args.entity_sentences]
    accepted_path = Path(args.accepted)
    print(f"[1/3] Loading accepted edges from {accepted_path}", flush=True)
    print(f"[2/3] Loading entity sentences from {len(entity_paths)} files",
          flush=True)
    rows, summary = build_gold_set(
        accepted_path=accepted_path,
        entity_sentences_paths=entity_paths,
        seed=args.seed,
    )
    print(f"[3/3] Writing {len(rows)} unlabeled rows → {args.output}",
          flush=True)
    write_gold_set(rows, args.output)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_SEED",
    "DEFAULT_TARGETS",
    "EXTENDED_FEATURE_KEYWORDS",
    "GENERIC_BODY_TOKENS",
    "GoldRow",
    "build_gold_set",
    "write_gold_set",
]
