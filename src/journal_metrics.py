from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class JournalMetrics:
    impact_factor: float | None
    quartile: str | None
    source: str


def normalize_quartile(value: Any) -> str | None:
    if value in (None, "", "NA"):
        return None
    text = str(value).strip().upper()
    if text.startswith("Q") and text[1:].isdigit():
        return f"Q{int(text[1:])}"
    if text.isdigit():
        return f"Q{int(text)}"
    return None


def normalize_impact_factor(value: Any) -> float | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


class ImpactFactorResolver:
    def __init__(self) -> None:
        self._factor = None
        self._init_error: str | None = None
        try:
            from impact_factor.core import Factor  # type: ignore

            self._factor = Factor()
        except Exception as exc:
            self._factor = None
            self._init_error = str(exc)

    @property
    def available(self) -> bool:
        return self._factor is not None

    @property
    def init_error(self) -> str | None:
        return self._init_error

    def resolve_by_issn(self, issn: str) -> JournalMetrics:
        if not issn or not issn.strip():
            return JournalMetrics(impact_factor=None, quartile=None, source="missing_issn")

        if not self.available:
            return JournalMetrics(impact_factor=None, quartile=None, source="resolver_unavailable")

        try:
            rows = self._factor.search(issn.strip())  # type: ignore[union-attr]
        except Exception:
            return JournalMetrics(impact_factor=None, quartile=None, source="lookup_error")

        if not rows:
            return JournalMetrics(impact_factor=None, quartile=None, source="not_found")

        first = rows[0]
        impact = normalize_impact_factor(first.get("factor"))
        quartile = normalize_quartile(first.get("jcr"))
        return JournalMetrics(impact_factor=impact, quartile=quartile, source="impact_factor_core")


def resolve_paper_metrics(
    paper: dict[str, Any],
    resolver: ImpactFactorResolver | None = None,
) -> JournalMetrics:
    inline_impact = normalize_impact_factor(paper.get("impact_factor"))
    inline_quartile = normalize_quartile(paper.get("quartile"))
    if inline_impact is not None or inline_quartile is not None:
        return JournalMetrics(
            impact_factor=inline_impact,
            quartile=inline_quartile,
            source="paper_record",
        )

    if resolver is None:
        return JournalMetrics(impact_factor=None, quartile=None, source="resolver_not_provided")

    issn = str(paper.get("issn") or "").strip()
    return resolver.resolve_by_issn(issn)


__all__ = [
    "JournalMetrics",
    "normalize_quartile",
    "normalize_impact_factor",
    "ImpactFactorResolver",
    "resolve_paper_metrics",
]
