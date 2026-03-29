"""Tests for imaging backbone node collection and Neo4j row generation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.assemble_edges import (
    MODALITY_DICOM_CODES,
    build_imaging_backbone_neo4j_rows,
    collect_imaging_backbone_nodes,
)
from src.schema_utils import load_schema, validate_record
from src.types import BodyLocationNode, ImagingModalityNode, to_dict


def _mention(
    canonical_feature: str = "entropy",
    node_type: str = "RadiomicFeature",
    body_location: str | None = None,
    modality: str | None = None,
    pmid: str = "12345678",
) -> dict:
    return {
        "mention_id": "m1",
        "pmid": pmid,
        "sentence": "test",
        "span_start": 0,
        "span_end": 4,
        "raw_feature": canonical_feature,
        "canonical_feature": canonical_feature,
        "ibsi_id": "IBSI:test",
        "confidence": 0.9,
        "mapping_method": "exact",
        "evidence": "test sentence",
        "feature_family": "glcm",
        "node_type": node_type,
        "ontology_namespace": "IBSI",
        "body_location": body_location,
        "modality": modality,
    }


class TestCollectImagingBackboneNodes:
    def test_empty_input(self) -> None:
        bl, mod = collect_imaging_backbone_nodes([])
        assert bl == []
        assert mod == []

    def test_extracts_body_location(self) -> None:
        mentions = [_mention(body_location="liver")]
        bl, mod = collect_imaging_backbone_nodes(mentions)
        assert len(bl) == 1
        assert bl[0].name == "liver"
        assert bl[0].node_id == "body_location:liver"
        assert bl[0].node_type == "BodyLocation"
        assert mod == []

    def test_extracts_modality(self) -> None:
        mentions = [_mention(modality="CT")]
        bl, mod = collect_imaging_backbone_nodes(mentions)
        assert bl == []
        assert len(mod) == 1
        assert mod[0].name == "CT"
        assert mod[0].node_id == "modality:CT"
        assert mod[0].dicom_code == "CT"
        assert mod[0].node_type == "ImagingModality"

    def test_deduplicates_locations(self) -> None:
        mentions = [
            _mention(body_location="liver"),
            _mention(body_location="Liver"),
            _mention(body_location="liver"),
        ]
        bl, _ = collect_imaging_backbone_nodes(mentions)
        assert len(bl) == 1

    def test_deduplicates_modalities(self) -> None:
        mentions = [
            _mention(modality="MRI"),
            _mention(modality="mri"),
            _mention(modality="MRI"),
        ]
        _, mod = collect_imaging_backbone_nodes(mentions)
        assert len(mod) == 1

    def test_mri_dicom_code(self) -> None:
        mentions = [_mention(modality="MRI")]
        _, mod = collect_imaging_backbone_nodes(mentions)
        assert mod[0].dicom_code == "MR"

    def test_skips_none_and_empty(self) -> None:
        mentions = [
            _mention(body_location=None, modality=None),
            _mention(body_location="", modality=""),
        ]
        bl, mod = collect_imaging_backbone_nodes(mentions)
        assert bl == []
        assert mod == []

    def test_multiple_distinct(self) -> None:
        mentions = [
            _mention(body_location="liver", modality="CT"),
            _mention(body_location="lung", modality="MRI"),
            _mention(body_location="colon", modality="PET"),
        ]
        bl, mod = collect_imaging_backbone_nodes(mentions)
        assert len(bl) == 3
        assert len(mod) == 3
        bl_names = {b.name for b in bl}
        assert bl_names == {"liver", "lung", "colon"}


class TestBuildImagingBackboneNeo4jRows:
    def test_empty_input(self) -> None:
        assert build_imaging_backbone_neo4j_rows([]) == []

    def test_measured_at_row(self) -> None:
        mentions = [_mention(canonical_feature="entropy", body_location="liver")]
        rows = build_imaging_backbone_neo4j_rows(mentions)
        assert len(rows) == 1
        assert rows[0]["source_node_type"] == "RadiomicFeature"
        assert rows[0]["source_node"] == "entropy"
        assert rows[0]["target_node_type"] == "BodyLocation"
        assert rows[0]["target_node"] == "liver"
        assert rows[0]["rel_type"] == "MEASURED_AT"

    def test_acquired_via_row(self) -> None:
        mentions = [_mention(canonical_feature="entropy", modality="CT")]
        rows = build_imaging_backbone_neo4j_rows(mentions)
        assert len(rows) == 1
        assert rows[0]["rel_type"] == "ACQUIRED_VIA"
        assert rows[0]["target_node_type"] == "ImagingModality"
        assert rows[0]["target_node"] == "CT"

    def test_both_location_and_modality(self) -> None:
        mentions = [_mention(body_location="liver", modality="CT")]
        rows = build_imaging_backbone_neo4j_rows(mentions)
        assert len(rows) == 2
        rel_types = {r["rel_type"] for r in rows}
        assert rel_types == {"MEASURED_AT", "ACQUIRED_VIA"}

    def test_deduplicates_edges(self) -> None:
        mentions = [
            _mention(canonical_feature="entropy", body_location="liver", pmid="1"),
            _mention(canonical_feature="entropy", body_location="liver", pmid="2"),
        ]
        rows = build_imaging_backbone_neo4j_rows(mentions)
        assert len(rows) == 1

    def test_bodycomp_node_type(self) -> None:
        mentions = [
            _mention(
                canonical_feature="visceral_adipose_tissue",
                node_type="BodyCompositionFeature",
                body_location="abdomen",
            )
        ]
        rows = build_imaging_backbone_neo4j_rows(mentions)
        assert rows[0]["source_node_type"] == "BodyCompositionFeature"


class TestSchemaValidation:
    def test_body_location_node_validates(self) -> None:
        node = BodyLocationNode(node_id="body_location:liver", name="liver")
        schema = load_schema("body_location_nodes.schema.json")
        validate_record(to_dict(node), schema)

    def test_imaging_modality_node_validates(self) -> None:
        node = ImagingModalityNode(
            node_id="modality:CT", name="CT", dicom_code="CT"
        )
        schema = load_schema("imaging_modality_nodes.schema.json")
        validate_record(to_dict(node), schema)


class TestDicomCodeMapping:
    def test_known_codes(self) -> None:
        assert MODALITY_DICOM_CODES["CT"] == "CT"
        assert MODALITY_DICOM_CODES["MRI"] == "MR"
        assert MODALITY_DICOM_CODES["PET"] == "PT"
        assert MODALITY_DICOM_CODES["US"] == "US"
        assert MODALITY_DICOM_CODES["DXA"] == "DXA"

    def test_unknown_falls_through(self) -> None:
        assert MODALITY_DICOM_CODES.get("SPECT", "SPECT") == "SPECT"
