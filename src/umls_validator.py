"""UMLS Semantic-Type (TUI) entity grounding gate.

Rejects NER-extracted entities that fail to ground to a permitted UMLS
Semantic Type at sufficient similarity. Used downstream of biomedical
NER (d4data/biomedical-ner-all and successors) to remove gene-function,
phenotype, and host-organism noise that NER mislabels as Microbe.

This module is a thin policy layer on top of the existing
``UMLSNormalizer`` in ``src/text_ner_minerva.py``. The ``UMLSNormalizer``
provides scispacy + UMLS linker access; this module decides which
groundings are admissible for each entity class.

Reference precedent for TUI-based filtering:
    - Sun et al. 2024 (BERN2) — UMLS TUI restriction in disambiguation step
    - Kraljevic et al. 2021 (MedCAT) — semantic-type filtering in linking
    - scispacy 0.6.x ``UmlsEntityLinker`` — TUI is a first-class field
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable


@runtime_checkable
class _Normalizer(Protocol):
    """Structural type for any UMLS normalizer with the project contract."""

    def normalize(self, text: str, allowed_tuis: set[str] | None = None) -> dict[str, Any] | None:
        ...


# --------------------------------------------------------------------------- #
#  TUI accept sets, by entity class
# --------------------------------------------------------------------------- #
# UMLS Semantic Network reference: https://www.nlm.nih.gov/research/umls/META3_current_semantic_types.html
#
# Microbe class: Bacterium, Archaeon, Eukaryote, Virus.
#   T204 (Eukaryote) is intentionally broad — it admits fungi/protozoa for
#   mycobiome and parasite work, but it also admits humans and lab model
#   organisms. The non-microbe deny-list below is the targeted mitigation.
#   T005 (Virus) is included for virome future-proofing per operator decision
#   2026-05-04 — admits viral taxa (e.g. crAssphage, Caudovirales) that appear
#   in gut-virome literature.
MICROBE_TUIS_ACCEPT: frozenset[str] = frozenset({
    "T005",  # Virus
    "T007",  # Bacterium
    "T194",  # Archaeon
    "T204",  # Eukaryote
})

# Disease class: same set used in ``scripts/apply_umls_to_entity_sentences.py``.
DISEASE_TUIS_ACCEPT: frozenset[str] = frozenset({
    "T047",  # Disease or Syndrome
    "T191",  # Neoplastic Process
    "T048",  # Mental or Behavioral Dysfunction
    "T046",  # Pathologic Function
    "T019",  # Congenital Abnormality
})

# Body composition / radiomic feature class: there is no clean UMLS TUI
# dedicated to imaging-derived phenotype features. T201 (Clinical Attribute)
# and T033 (Finding) cover most cases. Use cautiously — this set is wider
# than the microbe set and admits more noise.
FEATURE_TUIS_ACCEPT: frozenset[str] = frozenset({
    "T201",  # Clinical Attribute
    "T033",  # Finding
    "T034",  # Laboratory or Test Result
    "T184",  # Sign or Symptom
})

# Non-microbe eukaryote CUIs that T204 would otherwise admit.
# This is a small, hand-curated deny list. Add to it if audit surfaces
# new false-positives. Each entry: CUI -> human-readable name.
NON_MICROBE_EUKARYOTE_DENY: Mapping[str, str] = {
    "C0086418": "Homo sapiens",
    "C0025929": "Mus musculus",
    "C0034693": "Rattus norvegicus",
    "C0010076": "Cells (generic)",
    "C0007634": "Cells (generic)",
    "C0021359": "Infant",
    "C0030705": "Patients",
    "C0683329": "Donors",
}

# Default similarity floor for accepting a UMLS grounding.
# Empirically chosen at 0.85 against scispacy 0.6.x linker behaviour;
# scispacy reports normalized cosine in [0, 1] and >= 0.85 corresponds
# roughly to "strong match" in linker output. Recalibrate via the audit
# script if drop rate on accepted edges is unreasonable.
MIN_GROUNDING_SIMILARITY: float = 0.85


# --------------------------------------------------------------------------- #
#  Data shapes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GroundedEntity:
    """Result of evaluating a single entity surface form against UMLS."""

    surface: str
    cui: str
    tui: str
    similarity: float
    official_name: str
    accepted: bool
    drop_reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "cui": self.cui,
            "tui": self.tui,
            "similarity": self.similarity,
            "official_name": self.official_name,
            "accepted": self.accepted,
            "drop_reason": self.drop_reason,
        }


# --------------------------------------------------------------------------- #
#  Gate
# --------------------------------------------------------------------------- #
class EntityGate:
    """TUI-based admissibility gate for a single entity class."""

    def __init__(
        self,
        normalizer: _Normalizer,
        accepted_tuis: frozenset[str],
        *,
        min_similarity: float = MIN_GROUNDING_SIMILARITY,
        deny_cuis: Mapping[str, str] | None = None,
    ) -> None:
        if not hasattr(normalizer, "normalize"):
            raise TypeError("normalizer must expose a .normalize(text, allowed_tuis) method")
        self.normalizer: _Normalizer = normalizer
        self.accepted_tuis = accepted_tuis
        self.min_similarity = float(min_similarity)
        self.deny_cuis: Mapping[str, str] = dict(deny_cuis or {})

    def evaluate(self, surface: str) -> GroundedEntity:
        """Resolve `surface` against UMLS and decide admissibility.

        Returns a GroundedEntity with `accepted=True` only if all of:
          - UMLS normalizer returns a candidate
          - Candidate TUI is in `accepted_tuis`
          - Candidate similarity >= `min_similarity`
          - Candidate CUI is not in `deny_cuis`
        """
        text = (surface or "").strip()
        if not text:
            return GroundedEntity("", "", "", 0.0, "", False, "empty_surface")

        result = self.normalizer.normalize(text, allowed_tuis=set(self.accepted_tuis))
        if result is None:
            # Retry without TUI restriction so we can record what UMLS thought
            # the surface was — informative when the normalizer rejected it
            # because of TUI mismatch rather than missing match.
            result = self.normalizer.normalize(text, allowed_tuis=None)
            if result is None:
                return GroundedEntity(text, "", "", 0.0, "", False, "no_umls_match")
            return GroundedEntity(
                surface=text,
                cui=str(result.get("cui") or ""),
                tui=str(result.get("tui") or ""),
                similarity=float(result.get("similarity") or 0.0),
                official_name=str(result.get("official_name") or ""),
                accepted=False,
                drop_reason="tui_not_in_accept_set",
            )

        cui = str(result.get("cui") or "")
        tui = str(result.get("tui") or "")
        sim = float(result.get("similarity") or 0.0)
        official = str(result.get("official_name") or "")

        if cui in self.deny_cuis:
            return GroundedEntity(
                surface=text, cui=cui, tui=tui, similarity=sim,
                official_name=official, accepted=False,
                drop_reason=f"deny_cui:{self.deny_cuis[cui]}",
            )
        if sim < self.min_similarity:
            return GroundedEntity(
                surface=text, cui=cui, tui=tui, similarity=sim,
                official_name=official, accepted=False,
                drop_reason=f"low_similarity:{sim:.3f}<{self.min_similarity:.3f}",
            )
        return GroundedEntity(
            surface=text, cui=cui, tui=tui, similarity=sim,
            official_name=official, accepted=True, drop_reason="",
        )

    def filter_entity_dicts(
        self,
        entities: Iterable[Mapping[str, object]],
        *,
        text_field: str = "text",
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Split a list of NER-style entity dicts into (kept, dropped).

        Each input dict must contain `text_field` (default "text").
        Kept dicts are augmented with `cui`, `tui`, `umls_official_name`,
        `umls_similarity`. Dropped dicts gain `drop_reason` and `grounding`.
        """
        kept: list[dict[str, object]] = []
        dropped: list[dict[str, object]] = []
        for entity in entities:
            surface_raw = entity.get(text_field) if isinstance(entity, Mapping) else None
            surface = str(surface_raw or "")
            grounded = self.evaluate(surface)
            base = dict(entity)
            if grounded.accepted:
                base.update({
                    "cui": grounded.cui,
                    "tui": grounded.tui,
                    "umls_official_name": grounded.official_name,
                    "umls_similarity": grounded.similarity,
                })
                kept.append(base)
            else:
                base.update({
                    "drop_reason": grounded.drop_reason,
                    "grounding": grounded.as_dict(),
                })
                dropped.append(base)
        return kept, dropped


def make_microbe_gate(
    normalizer: _Normalizer,
    *,
    min_similarity: float = MIN_GROUNDING_SIMILARITY,
) -> EntityGate:
    """Convenience constructor with the project-default microbe policy."""
    return EntityGate(
        normalizer=normalizer,
        accepted_tuis=MICROBE_TUIS_ACCEPT,
        min_similarity=min_similarity,
        deny_cuis=NON_MICROBE_EUKARYOTE_DENY,
    )


def make_disease_gate(
    normalizer: _Normalizer,
    *,
    min_similarity: float = MIN_GROUNDING_SIMILARITY,
) -> EntityGate:
    """Convenience constructor with the project-default disease policy."""
    return EntityGate(
        normalizer=normalizer,
        accepted_tuis=DISEASE_TUIS_ACCEPT,
        min_similarity=min_similarity,
    )


__all__ = [
    "MICROBE_TUIS_ACCEPT",
    "DISEASE_TUIS_ACCEPT",
    "FEATURE_TUIS_ACCEPT",
    "NON_MICROBE_EUKARYOTE_DENY",
    "MIN_GROUNDING_SIMILARITY",
    "GroundedEntity",
    "EntityGate",
    "make_microbe_gate",
    "make_disease_gate",
]
