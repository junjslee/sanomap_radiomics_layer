from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SURROUNDING_STRIP_CHARS = "\"'`[]{}()"

GENERIC_MICROBE_TERMS = {
    "bacteria",
    "bacterias",
    "bacterial",
    "bacterial abundance",
    "bacterial communities",
    "bacterial community",
    "bacterial density",
    "bacterial load",
    "bacterial presence",
    "bacterial species",
    "microbe",
    "microbes",
    "microbial",
    "microbial abundance",
    "microbial communities",
    "microbial community",
    "microbial density",
    "microbial load",
    "microbial presence",
    "microbiome",
    "microbiota",
    "organism",
    "organisms",
    "probiotic",
    "probiotics",
}

GENERIC_DISEASE_TERMS = {
    "disease",
    "diseases",
}

MICROBE_TRAILING_CONTEXT_TOKENS = {
    "abundance",
    "count",
    "counts",
    "density",
    "level",
    "levels",
    "load",
    "loads",
    "presence",
}

DISEASE_TRAILING_CONTEXT_TOKENS = {
    "analysis",
    "case",
    "cases",
    "cohort",
    "cohorts",
    "control",
    "controls",
    "group",
    "groups",
    "marker",
    "markers",
    "model",
    "models",
    "patient",
    "patients",
    "risk",
    "risks",
    "score",
    "scores",
    "study",
    "studies",
    "subject",
    "subjects",
}

TRAILING_STOP_TOKENS = {
    "a",
    "an",
    "the",
    "this",
    "these",
    "those",
    "in",
    "of",
    "among",
    "within",
    "during",
    "across",
}

SUBJECT_TRAILING_FRAGMENT_TOKENS = {
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
}

DISEASE_RELATION_LANGUAGE_TOKENS = {
    "associated",
    "association",
    "abundant",
    "correlated",
    "correlation",
    "decrease",
    "decreased",
    "elevated",
    "higher",
    "improved",
    "improvement",
    "increase",
    "increased",
    "link",
    "linked",
    "lower",
    "predictive",
    "prognostic",
    "reduced",
    "reduction",
    "related",
    "relationship",
    "relationships",
    "worsened",
    "worsening",
}

DISEASE_CONTEXT_TOKENS = DISEASE_TRAILING_CONTEXT_TOKENS | {
    "abundance",
    "density",
    "feature",
    "features",
    "indicator",
    "indicators",
    "level",
    "levels",
    "manifestation",
    "manifestations",
    "presence",
    "signature",
    "signatures",
}

CLAUSE_PRONOUN_TOKENS = {
    "current",
    "our",
    "their",
    "this",
    "these",
    "those",
}

CLAUSE_VERB_TOKENS = SUBJECT_TRAILING_FRAGMENT_TOKENS | {
    "has",
    "have",
    "had",
    "more",
    "less",
}

LEADING_DISEASE_CONTEXT_TOKENS = {
    "among",
    "during",
    "for",
    "in",
    "of",
    "within",
    "with",
}

LEADING_DISEASE_PREFIX_PATTERNS = (
    re.compile(
        r"^(?:in|among|within)\s+"
        r"(?:adult|adults|child|children|individual|individuals|patient|patients|people|"
        r"participant|participants|subject|subjects|women|men)\s+with\s+"
    ),
    re.compile(r"^one of the (?:main )?manifestations of\s+"),
    re.compile(r"^(?:main )?manifestations of\s+"),
    re.compile(
        r"^of\s+.+?\b(?:in|among|within)\s+"
        r"(?:adult|adults|child|children|individual|individuals|patient|patients|people|"
        r"participant|participants|subject|subjects|women|men)\s+with\s+"
    ),
)


@dataclass(frozen=True)
class CleanedSpan:
    text: str
    canonical: str


def normalize_span_text(text: Any) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    cleaned = cleaned.strip(SURROUNDING_STRIP_CHARS)
    cleaned = cleaned.strip(" ,;:.")
    return re.sub(r"\s+", " ", cleaned).strip()


def _strip_trailing_tokens(tokens: list[str], removable: set[str]) -> list[str]:
    trimmed = list(tokens)
    while trimmed and trimmed[-1] in removable:
        trimmed.pop()
    return trimmed


def _trim_disease_prefixes(text: str) -> str:
    trimmed = text
    for pattern in LEADING_DISEASE_PREFIX_PATTERNS:
        trimmed = pattern.sub("", trimmed)
    return trimmed.strip()


def _is_generic_microbe_term(text: str) -> bool:
    if text in GENERIC_MICROBE_TERMS:
        return True

    tokens = text.split()
    if not tokens:
        return True
    if tokens[0] in {"bacterial", "microbial"}:
        return True
    if len(tokens) <= 3 and tokens[-1] in {"bacteria", "microbes", "microbiome", "microbiota"}:
        return True
    return False


def clean_subject_span(text: Any, *, subject_node_type: str = "Microbe") -> tuple[CleanedSpan | None, str | None]:
    normalized = normalize_span_text(text)
    if not normalized:
        return None, "missing_subject_node"

    canonical = normalized.lower()
    if subject_node_type == "Microbe":
        tokens = canonical.split()
        tokens = _strip_trailing_tokens(
            tokens,
            MICROBE_TRAILING_CONTEXT_TOKENS | TRAILING_STOP_TOKENS | SUBJECT_TRAILING_FRAGMENT_TOKENS,
        )
        canonical = " ".join(tokens).strip()

    if not canonical:
        return None, "missing_subject_node"
    if "##" in canonical:
        return None, "subject_wordpiece_fragment"
    if subject_node_type == "Microbe" and _is_generic_microbe_term(canonical):
        return None, "generic_microbe_term"

    return CleanedSpan(text=canonical, canonical=canonical), None


def clean_disease_span(text: Any) -> tuple[CleanedSpan | None, str | None]:
    normalized = normalize_span_text(text)
    if not normalized:
        return None, "missing_disease"

    canonical = _trim_disease_prefixes(normalized.lower())
    tokens = canonical.split()
    tokens = _strip_trailing_tokens(tokens, DISEASE_TRAILING_CONTEXT_TOKENS)
    tokens = _strip_trailing_tokens(tokens, TRAILING_STOP_TOKENS)
    canonical = " ".join(tokens).strip()

    if not canonical:
        return None, "missing_disease"
    if "##" in canonical:
        return None, "disease_wordpiece_fragment"
    if canonical in GENERIC_DISEASE_TERMS:
        return None, "generic_disease_term"

    tokens = canonical.split()
    token_set = set(tokens)
    if tokens and tokens[0] in LEADING_DISEASE_CONTEXT_TOKENS and len(tokens) > 2:
        return None, "disease_clause_like"
    if token_set & DISEASE_RELATION_LANGUAGE_TOKENS:
        return None, "disease_relation_language"
    if len(token_set) > 4 and token_set & CLAUSE_PRONOUN_TOKENS:
        return None, "disease_clause_like"
    if len(tokens) > 4 and token_set & CLAUSE_VERB_TOKENS:
        return None, "disease_clause_like"
    if len(tokens) > 5 and token_set & DISEASE_CONTEXT_TOKENS:
        return None, "disease_clause_like"
    if len(tokens) > 8:
        return None, "disease_clause_like"

    return CleanedSpan(text=canonical, canonical=canonical), None


def clean_relation_pair(
    *,
    sentence: Any,
    subject_node_type: str,
    subject_node: Any,
    disease: Any,
    max_evidence_words: int | None = None,
    max_evidence_chars: int | None = None,
) -> tuple[CleanedSpan | None, CleanedSpan | None, str | None]:
    sentence_text = re.sub(r"\s+", " ", str(sentence or "").strip())
    if not sentence_text:
        return None, None, "missing_sentence"
    if max_evidence_words is not None and len(sentence_text.split()) >= max_evidence_words:
        return None, None, "evidence_too_long_words"
    if max_evidence_chars is not None and len(sentence_text) >= max_evidence_chars:
        return None, None, "evidence_too_long_chars"

    subject_span, subject_reason = clean_subject_span(subject_node, subject_node_type=subject_node_type)
    if subject_reason is not None:
        return None, None, subject_reason

    disease_span, disease_reason = clean_disease_span(disease)
    if disease_reason is not None:
        return None, None, disease_reason

    return subject_span, disease_span, None


__all__ = [
    "CleanedSpan",
    "GENERIC_DISEASE_TERMS",
    "GENERIC_MICROBE_TERMS",
    "clean_disease_span",
    "clean_relation_pair",
    "clean_subject_span",
    "normalize_span_text",
]
