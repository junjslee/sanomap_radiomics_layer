"""Evaluation harness for the v1 gold-label benchmark.

Reads the labeled JSONL produced by hand-annotation against the schema
in ``docs/benchmark/annotation_schema.md`` and the pipeline's accepted
edges (``artifacts/microbe_feature_relations.jsonl``). Outputs:

  - binary precision / recall / F1
  - 2x2 confusion matrix
  - per-stratum accuracy
  - per-feature breakdown
  - per-evidence_type breakdown
  - gold class distribution
  - rows skipped due to ``unclear`` or missing label

The scorer treats ``associated_*`` (positive, negative, unsigned) as
gold=1 and {``no_association_explicit``, ``not_associated``} as gold=0.
Rows labeled ``unclear`` are excluded from P/R/F1 and reported in the
``unclear_rate`` field.

For multi-class scoring (signed direction error analysis), see the
``--multi-class`` flag.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# --------------------------------------------------------------------------- #
#  Label policy
# --------------------------------------------------------------------------- #
ASSOCIATED_LABELS: frozenset[str] = frozenset({
    "associated_positive",
    "associated_negative",
    "associated_unsigned",
})
NEGATIVE_LABELS: frozenset[str] = frozenset({
    "no_association_explicit",
    "not_associated",
})
EXCLUDED_LABELS: frozenset[str] = frozenset({"unclear"})
ALL_LABELS: frozenset[str] = (
    ASSOCIATED_LABELS | NEGATIVE_LABELS | EXCLUDED_LABELS
)


def gold_binary(label: str | None) -> int | None:
    """Return 1 / 0 / None (excluded). None means skip from P/R/F1."""
    if label is None:
        return None
    if label in EXCLUDED_LABELS:
        return None
    if label in ASSOCIATED_LABELS:
        return 1
    if label in NEGATIVE_LABELS:
        return 0
    raise ValueError(f"Unknown label: {label!r}. "
                     f"Allowed: {sorted(ALL_LABELS)}")


# --------------------------------------------------------------------------- #
#  Data shapes
# --------------------------------------------------------------------------- #
@dataclass
class GoldLabel:
    record_id: str
    pmid: str
    stratum: str
    microbe: str
    candidate_feature_canonical: str | None
    inferred_feature_canonical: str | None
    label: str | None
    evidence_type: str | None
    quantitative: str | None
    confidence: str | None

    @property
    def effective_feature(self) -> str | None:
        """The feature against which the pipeline prediction is checked.

        Use the candidate_feature_canonical when present (accepted_edge,
        gemini_rejected, vocab_excluded strata). Fall back to
        inferred_feature_canonical for null-feature strata
        (recall_probe, random_co_occurrence) — the annotator filled this
        in as part of labeling.
        """
        return self.candidate_feature_canonical or self.inferred_feature_canonical


@dataclass
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


# --------------------------------------------------------------------------- #
#  Loaders
# --------------------------------------------------------------------------- #
def load_gold(path: Path) -> list[GoldLabel]:
    rows: list[GoldLabel] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        rows.append(GoldLabel(
            record_id=str(rec.get("record_id", "")),
            pmid=str(rec.get("pmid", "")),
            stratum=str(rec.get("stratum", "")),
            microbe=str(rec.get("microbe", "")).strip().lower(),
            candidate_feature_canonical=(rec.get("candidate_feature_canonical")
                                         or None),
            inferred_feature_canonical=(rec.get("inferred_feature_canonical")
                                        or None),
            label=rec.get("label"),
            evidence_type=rec.get("evidence_type"),
            quantitative=rec.get("quantitative"),
            confidence=rec.get("confidence"),
        ))
    return rows


def load_accepted_edges(path: Path) -> set[tuple[str, str, str]]:
    """Return set of (pmid, microbe_lower, feature_canonical) from the
    pipeline's accepted CORRELATES_WITH artifact.
    """
    keys: set[tuple[str, str, str]] = set()
    if not path.exists():
        return keys
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        pmid = str(rec.get("pmid", ""))
        microbe = str(rec.get("source_node", "")).strip().lower()
        feature = str(rec.get("target_node", ""))
        if pmid and microbe and feature:
            keys.add((pmid, microbe, feature))
    return keys


# --------------------------------------------------------------------------- #
#  Predicate
# --------------------------------------------------------------------------- #
def pipeline_predict(gold: GoldLabel,
                     accepted_keys: set[tuple[str, str, str]]) -> int:
    """Return 1 if pipeline emitted this edge, else 0.

    Uses (pmid, microbe_lower, effective_feature). For rows where the
    annotator did not fill in inferred_feature_canonical, the prediction
    falls back to "no edge" (0) — i.e., the pipeline definitionally did
    not predict a feature it could not name.
    """
    feat = gold.effective_feature
    if not feat:
        return 0
    return int((gold.pmid, gold.microbe, feat) in accepted_keys)


# --------------------------------------------------------------------------- #
#  Scoring
# --------------------------------------------------------------------------- #
def score(
    gold: list[GoldLabel],
    accepted_keys: set[tuple[str, str, str]],
) -> dict[str, Any]:
    """Compute binary P/R/F1 + per-stratum accuracy + diagnostics."""
    overall = Confusion()
    by_stratum: dict[str, Confusion] = {}
    by_feature: dict[str, Confusion] = {}
    by_evidence_type: dict[str, Confusion] = {}
    label_dist: Counter[str] = Counter()
    skipped_unclear = 0
    skipped_no_label = 0
    n_total = len(gold)

    for row in gold:
        label_dist[str(row.label)] += 1
        if row.label is None:
            skipped_no_label += 1
            continue
        gb = gold_binary(row.label)
        if gb is None:
            skipped_unclear += 1
            continue
        pred = pipeline_predict(row, accepted_keys)
        c = _bucket(by_stratum, row.stratum)
        cf = _bucket(by_feature,
                     row.effective_feature or "_unspecified")
        ce = _bucket(by_evidence_type,
                     row.evidence_type or "_unspecified")
        for box in (overall, c, cf, ce):
            _tally(box, gb, pred)

    return {
        "n_total": n_total,
        "n_scored": (
            n_total - skipped_unclear - skipped_no_label
        ),
        "skipped_unclear": skipped_unclear,
        "skipped_no_label": skipped_no_label,
        "unclear_rate": (skipped_unclear / n_total) if n_total else 0.0,
        "label_distribution": dict(label_dist),
        "overall": overall.as_dict(),
        "by_stratum": {k: v.as_dict() for k, v in by_stratum.items()},
        "by_feature": {k: v.as_dict() for k, v in by_feature.items()},
        "by_evidence_type": {k: v.as_dict() for k, v in by_evidence_type.items()},
    }


def _bucket(d: dict[str, Confusion], key: str) -> Confusion:
    if key not in d:
        d[key] = Confusion()
    return d[key]


def _tally(c: Confusion, gold_y: int, pred_y: int) -> None:
    if gold_y == 1 and pred_y == 1:
        c.tp += 1
    elif gold_y == 0 and pred_y == 1:
        c.fp += 1
    elif gold_y == 1 and pred_y == 0:
        c.fn += 1
    else:
        c.tn += 1


# --------------------------------------------------------------------------- #
#  Multi-class diagnostic (direction errors)
# --------------------------------------------------------------------------- #
def multi_class_breakdown(gold: list[GoldLabel]) -> dict[str, Any]:
    """Distribution of associated_positive / negative / unsigned among
    rows the pipeline accepted, so direction errors are visible.
    """
    breakdown: Counter[str] = Counter()
    for row in gold:
        if row.label in ASSOCIATED_LABELS:
            breakdown[row.label] += 1
    return {
        "associated_positive": breakdown.get("associated_positive", 0),
        "associated_negative": breakdown.get("associated_negative", 0),
        "associated_unsigned": breakdown.get("associated_unsigned", 0),
    }


# --------------------------------------------------------------------------- #
#  Cohen's kappa for IAA
# --------------------------------------------------------------------------- #
def cohens_kappa(
    pass1: Iterable[GoldLabel],
    pass2: Iterable[GoldLabel],
    *,
    binary: bool = False,
) -> dict[str, Any]:
    """Cohen's κ across two passes joined by record_id.

    Args:
        pass1, pass2: gold rows from two independent annotation passes.
        binary: collapse 6-class labels to {associated, not} before κ.
    """
    by_id1 = {row.record_id: row.label for row in pass1 if row.label}
    by_id2 = {row.record_id: row.label for row in pass2 if row.label}
    common = sorted(set(by_id1) & set(by_id2))
    if not common:
        return {"n": 0, "kappa": float("nan"),
                "p_observed": 0.0, "p_expected": 0.0}

    def project(label: str) -> str:
        if not binary:
            return label
        if label in ASSOCIATED_LABELS:
            return "associated"
        return "not"

    a = [project(by_id1[i]) for i in common]
    b = [project(by_id2[i]) for i in common]

    classes = sorted(set(a) | set(b))
    n = len(common)
    p_observed = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = Counter(a)
    pb = Counter(b)
    p_expected = sum((pa[c] / n) * (pb[c] / n) for c in classes)
    kappa = (p_observed - p_expected) / (1 - p_expected) if p_expected < 1 else 1.0
    return {
        "n": n,
        "kappa": round(kappa, 4),
        "p_observed": round(p_observed, 4),
        "p_expected": round(p_expected, 4),
        "classes": classes,
        "binary": binary,
    }


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        default="artifacts/gold_set_v1_LABELED_pass1.jsonl",
        type=Path,
    )
    parser.add_argument(
        "--accepted",
        default="artifacts/microbe_feature_relations.jsonl",
        type=Path,
    )
    parser.add_argument(
        "--output",
        default="artifacts/gold_set_v1_metrics.json",
        type=Path,
    )
    parser.add_argument(
        "--iaa-pass2",
        type=Path,
        default=None,
        help="Optional second-pass JSONL — triggers Cohen's κ computation.",
    )
    parser.add_argument(
        "--multi-class",
        action="store_true",
        help="Print signed-association distribution alongside binary metrics.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.gold.exists():
        print(f"ERROR: gold set not found: {args.gold}", file=sys.stderr)
        return 1
    gold = load_gold(args.gold)
    accepted = load_accepted_edges(args.accepted)
    metrics = score(gold, accepted)
    if args.multi_class:
        metrics["multi_class_breakdown"] = multi_class_breakdown(gold)
    if args.iaa_pass2 and args.iaa_pass2.exists():
        pass2 = load_gold(args.iaa_pass2)
        metrics["iaa_6class"] = cohens_kappa(gold, pass2, binary=False)
        metrics["iaa_binary"] = cohens_kappa(gold, pass2, binary=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ASSOCIATED_LABELS",
    "NEGATIVE_LABELS",
    "EXCLUDED_LABELS",
    "GoldLabel",
    "Confusion",
    "gold_binary",
    "load_gold",
    "load_accepted_edges",
    "pipeline_predict",
    "score",
    "multi_class_breakdown",
    "cohens_kappa",
]
