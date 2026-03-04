from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Type, TypeVar


@dataclass
class PaperRecord:
    pmid: str
    title: str
    abstract: str
    query: str
    retrieval_date: str
    source: str = "pubmed"
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    language: Optional[str] = None
    full_text_path: Optional[str] = None


@dataclass
class FigureRecord:
    figure_id: str
    topology: str
    topology_confidence: float
    heuristic_hits: list[str]
    caption: str = ""
    pmid: Optional[str] = None
    image_path: Optional[str] = None
    source_context: Optional[str] = None


@dataclass
class RadiomicMention:
    mention_id: str
    pmid: str
    sentence: str
    span_start: int
    span_end: int
    raw_feature: str
    canonical_feature: str
    ibsi_id: str
    confidence: float
    mapping_method: str
    evidence: str
    modality: Optional[str] = None
    body_location: Optional[str] = None
    disease: Optional[str] = None


@dataclass
class VisionProposal:
    proposal_id: str
    pmid: str
    figure_id: str
    proposed_r: float
    verification: Dict[str, Any]
    microbe: Optional[str] = None
    radiomic_feature: Optional[str] = None
    disease: Optional[str] = None
    model_name: Optional[str] = None
    legend_bbox: Optional[list[int]] = None
    heatmap_bbox: Optional[list[int]] = None


@dataclass
class VerificationResult:
    verification_id: str
    proposed_r: float
    verified: bool
    reason: str
    support_pixels: int
    required_support: int
    support_fraction: float
    diagnostics: Dict[str, Any]
    proposal_id: Optional[str] = None
    pmid: Optional[str] = None
    figure_id: Optional[str] = None
    nearest_r: Optional[float] = None
    min_abs_error: Optional[float] = None


@dataclass
class EdgeCandidate:
    edge_id: str
    pmid: str
    radiomic_feature: str
    relation_type: str
    evidence_type: str
    confidence: float
    evidence: str
    verification_passed: bool
    microbe: Optional[str] = None
    disease: Optional[str] = None
    r_value: Optional[float] = None
    figure_id: Optional[str] = None


RECORD_TYPES: dict[str, Type[Any]] = {
    "paper": PaperRecord,
    "figure": FigureRecord,
    "radiomic_mention": RadiomicMention,
    "vision_proposal": VisionProposal,
    "verification_result": VerificationResult,
    "edge_candidate": EdgeCandidate,
}

T = TypeVar("T")


def to_dict(record: Any) -> Dict[str, Any]:
    if hasattr(record, "__dataclass_fields__"):
        return asdict(record)
    if isinstance(record, dict):
        return record
    raise TypeError(f"Unsupported record type: {type(record)!r}")


def from_dict(record_cls: Type[T], payload: Dict[str, Any]) -> T:
    if not hasattr(record_cls, "__dataclass_fields__"):
        raise TypeError(f"Expected dataclass type, got: {record_cls!r}")
    fields = record_cls.__dataclass_fields__  # type: ignore[attr-defined]
    filtered = {k: v for k, v in payload.items() if k in fields}
    return record_cls(**filtered)  # type: ignore[misc]


__all__ = [
    "PaperRecord",
    "FigureRecord",
    "RadiomicMention",
    "VisionProposal",
    "VerificationResult",
    "EdgeCandidate",
    "RECORD_TYPES",
    "to_dict",
    "from_dict",
]
