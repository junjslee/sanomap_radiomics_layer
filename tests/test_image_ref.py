"""Tests for ImageRef node collection and REPRESENTED_BY edge generation."""

from __future__ import annotations

from src.assemble_edges import build_image_ref_neo4j_rows, collect_image_ref_nodes
from src.schema_utils import load_schema, validate_record
from src.types import ImageRef, to_dict


def _proposal(
    proposal_id: str = "p1",
    pmid: str = "PMC12345",
    figure_id: str = "fig1",
    panel_id: str = "A",
    modality: str = "CT",
    image_path: str | None = "/tmp/fig.jpg",
) -> dict:
    return {
        "proposal_id": proposal_id,
        "pmid": pmid,
        "figure_id": figure_id,
        "panel_id": panel_id,
        "modality": modality,
        "image_path": image_path,
        "microbe": "Prevotella",
        "radiomic_feature": "GLCM_Correlation",
    }


def _verification(proposal_id: str = "p1", verified: bool = True) -> dict:
    return {
        "verification_id": "v1",
        "proposal_id": proposal_id,
        "verified": verified,
        "pass_fail": verified,
        "proposed_r": 0.95,
    }


class TestCollectImageRefNodes:
    def test_empty_input(self) -> None:
        assert collect_image_ref_nodes([], []) == []

    def test_no_verified_results(self) -> None:
        proposals = [_proposal()]
        verifications = [_verification(verified=False)]
        assert collect_image_ref_nodes(proposals, verifications) == []

    def test_extracts_verified_node(self) -> None:
        proposals = [_proposal(proposal_id="p1", pmid="PMC99", figure_id="fig1")]
        verifications = [_verification(proposal_id="p1", verified=True)]
        refs = collect_image_ref_nodes(proposals, verifications)
        assert len(refs) == 1
        assert refs[0].pmcid == "PMC99"
        assert refs[0].figure_id == "fig1"
        assert refs[0].node_id == "imageref:PMC99:fig1"
        assert refs[0].node_type == "ImageRef"
        assert refs[0].panel_id == "A"
        assert refs[0].modality == "CT"

    def test_deduplicates_same_figure(self) -> None:
        proposals = [
            _proposal(proposal_id="p1", figure_id="fig1"),
            _proposal(proposal_id="p2", figure_id="fig1"),
        ]
        verifications = [
            _verification(proposal_id="p1"),
            _verification(proposal_id="p2"),
        ]
        refs = collect_image_ref_nodes(proposals, verifications)
        assert len(refs) == 1

    def test_skips_empty_figure_id(self) -> None:
        proposals = [_proposal(proposal_id="p1", figure_id="", pmid="PMC1")]
        verifications = [_verification(proposal_id="p1")]
        refs = collect_image_ref_nodes(proposals, verifications)
        assert refs == []

    def test_uses_pass_fail_as_verified(self) -> None:
        proposals = [_proposal(proposal_id="p1")]
        verifications = [{"verification_id": "v1", "proposal_id": "p1", "verified": False, "pass_fail": True}]
        refs = collect_image_ref_nodes(proposals, verifications)
        assert len(refs) == 1


class TestBuildImageRefNeo4jRows:
    def test_empty_input(self) -> None:
        assert build_image_ref_neo4j_rows([], []) == []

    def test_generates_represented_by_row(self) -> None:
        ref = ImageRef(node_id="imageref:PMC99:fig1", pmcid="PMC99", figure_id="fig1", modality="CT")
        proposals = [_proposal(proposal_id="p1", pmid="PMC99", figure_id="fig1", modality="CT")]
        rows = build_image_ref_neo4j_rows([ref], proposals)
        assert len(rows) == 1
        assert rows[0]["source_node_type"] == "ImagingModality"
        assert rows[0]["source_node"] == "CT"
        assert rows[0]["target_node_type"] == "ImageRef"
        assert rows[0]["target_node"] == "imageref:PMC99:fig1"
        assert rows[0]["rel_type"] == "REPRESENTED_BY"

    def test_skips_proposal_without_modality(self) -> None:
        ref = ImageRef(node_id="imageref:PMC99:fig1", pmcid="PMC99", figure_id="fig1")
        proposals = [_proposal(proposal_id="p1", figure_id="fig1", modality="")]
        rows = build_image_ref_neo4j_rows([ref], proposals)
        assert rows == []

    def test_deduplicates_rows(self) -> None:
        ref = ImageRef(node_id="imageref:PMC99:fig1", pmcid="PMC99", figure_id="fig1")
        proposals = [
            _proposal(proposal_id="p1", figure_id="fig1", modality="CT"),
            _proposal(proposal_id="p2", figure_id="fig1", modality="CT"),
        ]
        rows = build_image_ref_neo4j_rows([ref], proposals)
        assert len(rows) == 1

    def test_normalises_modality_to_upper(self) -> None:
        ref = ImageRef(node_id="imageref:PMC99:fig1", pmcid="PMC99", figure_id="fig1")
        proposals = [_proposal(proposal_id="p1", figure_id="fig1", modality="ct")]
        rows = build_image_ref_neo4j_rows([ref], proposals)
        assert rows[0]["source_node"] == "CT"


class TestImageRefSchema:
    def test_valid_node_validates(self) -> None:
        node = ImageRef(
            node_id="imageref:PMC10605408:89b1e3b5e8a4e447",
            pmcid="PMC10605408",
            figure_id="89b1e3b5e8a4e447",
            panel_id="A",
            modality="CT",
        )
        schema = load_schema("image_ref_nodes.schema.json")
        validate_record(to_dict(node), schema)

    def test_minimal_node_validates(self) -> None:
        node = ImageRef(
            node_id="imageref:PMC1:fig1",
            pmcid="PMC1",
            figure_id="fig1",
        )
        schema = load_schema("image_ref_nodes.schema.json")
        validate_record(to_dict(node), schema)
