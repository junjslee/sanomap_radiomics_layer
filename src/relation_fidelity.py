from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log10
from typing import Any

from src.model_backends import NEGATIVE, POSITIVE, UNRELATED, BaseRelationBackend


@dataclass
class SelfConsistencyResult:
    final_label: str
    sample_labels: list[str]
    vote_counts: dict[str, int]
    full_consistency: bool
    label_entropy: float
    zero_entropy: bool
    accepted: bool


def _shannon_entropy_from_counts(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        entropy -= p * log10(p)
    return float(entropy)


def self_consistency_predict(
    *,
    backend: BaseRelationBackend,
    sentence: str,
    subject: str,
    disease: str,
    temperatures: list[float],
    max_new_tokens: int = 16,
    require_complete_consistency: bool = True,
) -> SelfConsistencyResult:
    sample_labels: list[str] = []
    for t in temperatures:
        label = backend.predict_relation(
            sentence=sentence,
            microbe=subject,
            disease=disease,
            temperature=t,
            max_new_tokens=max_new_tokens,
        )
        sample_labels.append(label)

    vote = Counter(sample_labels)
    top_label, top_count = vote.most_common(1)[0]
    full_consistency = top_count == len(sample_labels)
    label_entropy = _shannon_entropy_from_counts(list(vote.values()))
    zero_entropy = label_entropy <= 1e-12

    if require_complete_consistency and not zero_entropy:
        final_label = UNRELATED
    else:
        final_label = top_label

    accepted = final_label in {POSITIVE, NEGATIVE}
    return SelfConsistencyResult(
        final_label=final_label,
        sample_labels=sample_labels,
        vote_counts={k: int(v) for k, v in vote.items()},
        full_consistency=full_consistency,
        label_entropy=label_entropy,
        zero_entropy=zero_entropy,
        accepted=accepted,
    )


def _majority_label(labels: list[str]) -> str:
    if not labels:
        return UNRELATED
    counter = Counter(labels)
    most = counter.most_common()
    if len(most) > 1 and most[0][1] == most[1][1]:
        return UNRELATED
    return most[0][0]


def aggregate_within_paper(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        subject_node_type = str(row.get("subject_node_type") or "Microbe")
        subject_node = str(row.get("subject_node") or row.get("microbe") or "")
        key = (
            str(row.get("pmid") or ""),
            subject_node_type,
            subject_node,
            str(row.get("disease") or ""),
        )
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for (pmid, subject_node_type, subject_node, disease), rows in grouped.items():
        labels = [str(r.get("final_label") or UNRELATED) for r in rows]
        final_label = _majority_label(labels)

        winning_rows = [r for r in rows if str(r.get("final_label") or UNRELATED) == final_label]
        evidences = [str(r.get("sentence") or "") for r in winning_rows if str(r.get("sentence") or "")]
        evidence_text = " ||| ".join(sorted(set(evidences)))

        vote_counts = Counter(labels)
        out = {
            "pmid": pmid,
            "microbe": rows[0].get("microbe", subject_node),
            "disease": disease,
            "subject_node_type": subject_node_type,
            "subject_node": subject_node,
            "final_label": final_label,
            "accepted": final_label in {POSITIVE, NEGATIVE},
            "evidence": evidence_text,
            "sentence_count": len(rows),
            "vote_counts": {k: int(v) for k, v in vote_counts.items()},
            "impact_factor": rows[0].get("impact_factor", "NA"),
            "quartile": rows[0].get("quartile", "NA"),
        }
        output.append(out)
    return output


def _parse_impact_factor(value: Any, default_impact: float) -> float:
    if value in (None, "", "NA"):
        return default_impact
    try:
        f = float(value)
    except Exception:
        return default_impact
    return f if f > 0 else default_impact


def _parse_quartile(value: Any, default_quartile: int) -> int:
    if value in (None, "", "NA"):
        return default_quartile
    if isinstance(value, int):
        return value if value > 0 else default_quartile
    text = str(value).strip().upper()
    if text.startswith("Q") and text[1:].isdigit():
        q = int(text[1:])
        return q if q > 0 else default_quartile
    if text.isdigit():
        q = int(text)
        return q if q > 0 else default_quartile
    return default_quartile


def compute_strength_scores(
    aggregated_relations: list[dict[str, Any]],
    *,
    default_impact: float = 3.5,
    default_quartile: int = 2,
    group_fields: tuple[str, ...] = ("subject_node_type", "subject_node", "disease"),
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in aggregated_relations:
        if not bool(row.get("accepted")):
            continue
        key = tuple(str(row.get(field) or "") for field in group_fields)
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        signs = [1 if str(r.get("final_label")) == POSITIVE else -1 for r in rows]
        impact_factors = [_parse_impact_factor(r.get("impact_factor"), default_impact) for r in rows]
        quartiles = [_parse_quartile(r.get("quartile"), default_quartile) for r in rows]

        total_strength_raw = sum(signs)
        total_strength_if = round(sum(signs[i] * log10(impact_factors[i]) for i in range(len(rows))), 3)
        total_strength_ifq = round(
            sum(signs[i] * log10(impact_factors[i] / quartiles[i]) for i in range(len(rows))),
            3,
        )

        data = {
            "group_key": {group_fields[i]: key[i] for i in range(len(group_fields))},
            "support_count": len(rows),
            "total_strength_raw": total_strength_raw,
            "total_strength_if": total_strength_if,
            "total_strength_ifq": total_strength_ifq,
        }
        output.append(data)
    return output


__all__ = [
    "SelfConsistencyResult",
    "self_consistency_predict",
    "aggregate_within_paper",
    "compute_strength_scores",
]
