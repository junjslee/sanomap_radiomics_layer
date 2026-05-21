"""Tests for scripts/build_explorer_data.py.

Smoke + schema invariants. The post-audit emitted-row count must equal
manifest.json's post_total (the canonical source of truth from Stage A),
and the edge_id hash must be deterministic across runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_explorer_data as bxd  # noqa: E402


# --- Unit: edge_id determinism ----------------------------------------------

def test_edge_id_is_deterministic():
    a = bxd.edge_id("akkermansia", "obesity", "CORRELATES_WITH")
    b = bxd.edge_id("akkermansia", "obesity", "CORRELATES_WITH")
    assert a == b


def test_edge_id_distinguishes_direction():
    # If subject and object swap, the id must change. Direction matters for
    # asymmetric edges like ASSOCIATED_WITH (feature → disease, not the reverse).
    assert bxd.edge_id("a", "b", "X") != bxd.edge_id("b", "a", "X")


def test_edge_id_distinguishes_rel_type():
    assert bxd.edge_id("a", "b", "X") != bxd.edge_id("a", "b", "Y")


# --- Unit: safe coercion ----------------------------------------------------

def test_safe_float_handles_empty_and_invalid():
    assert bxd.safe_float("") is None
    assert bxd.safe_float(None) is None
    assert bxd.safe_float("xx") is None
    assert bxd.safe_float("0.85") == 0.85


def test_safe_int_handles_floats_in_strings():
    assert bxd.safe_int("2024") == 2024
    assert bxd.safe_int("2024.0") == 2024
    assert bxd.safe_int("") is None


def test_safe_bool_handles_common_truthy():
    assert bxd.safe_bool("True") is True
    assert bxd.safe_bool("true") is True
    assert bxd.safe_bool("1") is True
    assert bxd.safe_bool("False") is False
    assert bxd.safe_bool("") is None


# --- Unit: row_to_record ---------------------------------------------------

def test_row_to_record_microbe_disease_pos():
    row = {
        "source_node_type": "Microbe",
        "source_node": "akkermansia",
        "target_node_type": "Disease",
        "target_node": "obesity",
        "rel_type": "POSITIVELY_CORRELATED_WITH",
        "pmid": "12345",
        "pmcid": "PMC1",
        "journal": "Journal X",
        "title": "Title Y",
        "publication_year": "2024",
        "evidence": "sentence text",
        "confidence": "1.0",
        "verification_passed": "True",
        "microbe_cui": "C0001",
        "microbe_official_name": "Akkermansia muciniphila",
        "disease_cui": "C0028754",
        "disease_official_name": "Obesity",
        "issn": "1234-5678",
        "impact_factor": "",
        "quartile": "",
    }
    rec = bxd.row_to_record(row)
    assert rec["microbe"] == "akkermansia"
    assert rec["disease"] == "obesity"
    assert rec["radiomic_feature"] is None
    assert rec["feature_family"] is None
    assert rec["relation_type"] == "MICROBE_DISEASE_POS"
    assert rec["evidence_type"] == "text_signed_co_mention"
    assert rec["confidence"] == 1.0
    assert rec["verification_passed"] is True
    assert rec["publication_year"] == 2024
    assert rec["assertion_level"] == "direct_evidence"


def test_row_to_record_bodycomp_disease_associated_with():
    row = {
        "source_node_type": "BodyCompositionFeature",
        "source_node": "sarcopenia",
        "target_node_type": "Disease",
        "target_node": "cirrhosis",
        "rel_type": "ASSOCIATED_WITH",
        "pmid": "67890",
        "evidence": "PMID 67890 sentence 15",
        "confidence": "0.85",
        "verification_passed": "True",
        "pmcid": "", "journal": "", "title": "", "publication_year": "",
        "microbe_cui": "", "microbe_official_name": "",
        "disease_cui": "", "disease_official_name": "", "issn": "",
        "impact_factor": "", "quartile": "",
    }
    rec = bxd.row_to_record(row)
    assert rec["microbe"] is None
    assert rec["disease"] == "cirrhosis"
    assert rec["radiomic_feature"] == "sarcopenia"
    assert rec["feature_family"] == "body_composition"
    assert rec["relation_type"] == "TEXT_ASSOCIATION"
    assert rec["evidence_type"] == "text_rule_verified"


def test_row_to_record_vision_correlates_with():
    """The surviving vision edge: prevotella_nigrescens → GLCM_Correlation."""
    row = {
        "source_node_type": "Microbe",
        "source_node": "prevotella_nigrescens",
        "target_node_type": "RadiomicFeature",
        "target_node": "GLCM_Correlation",
        "rel_type": "CORRELATES_WITH",
        "pmid": "", "pmcid": "",
        "evidence": "Vision proposal 5549945ad4a32b2f; reason=verified; distance_metric=0.05",
        "confidence": "1.0",
        "verification_passed": "True",
        "journal": "", "title": "", "publication_year": "",
        "microbe_cui": "", "microbe_official_name": "",
        "disease_cui": "", "disease_official_name": "", "issn": "",
        "impact_factor": "", "quartile": "",
    }
    rec = bxd.row_to_record(row)
    assert rec["microbe"] == "prevotella_nigrescens"
    assert rec["radiomic_feature"] == "GLCM_Correlation"
    assert rec["disease"] is None
    assert rec["feature_family"] == "radiomic"
    assert rec["relation_type"] == "VISION_OR_TEXT_CORRELATION"
    assert rec["evidence_type"] == "quantitatively_verified"
    # r_value + figure_id reserved for v2 enrichment.
    assert rec["r_value"] is None
    assert rec["figure_id"] is None


def test_row_to_record_backbone_measured_at():
    row = {
        "source_node_type": "BodyCompositionFeature",
        "source_node": "skeletal_muscle_index",
        "target_node_type": "BodyLocation",
        "target_node": "abdomen",
        "rel_type": "MEASURED_AT",
        "pmid": "", "pmcid": "", "evidence": "",
        "confidence": "", "verification_passed": "True",
        "journal": "", "title": "", "publication_year": "",
        "microbe_cui": "", "microbe_official_name": "",
        "disease_cui": "", "disease_official_name": "", "issn": "",
        "impact_factor": "", "quartile": "",
    }
    rec = bxd.row_to_record(row)
    assert rec["radiomic_feature"] == "skeletal_muscle_index"
    assert rec["disease"] is None
    assert rec["relation_type"] == "BACKBONE_LOCATION"
    assert rec["evidence_type"] == "schema_backbone"


# --- Integration: real graph_export must match manifest --------------------

def test_real_export_matches_manifest_post_total():
    """Smoke against the live graph_export — the canonical invariant the main
    script enforces. If this fails, the canonical bundle drifted from itself
    and Stage A needs to re-run before the explorer rewire is meaningful."""
    rel_csv = REPO_ROOT / "artifacts" / "graph_export" / "relationships.csv"
    manifest = REPO_ROOT / "artifacts" / "graph_export" / "manifest.json"
    if not rel_csv.exists() or not manifest.exists():
        # Some CI/dev environments may not carry artifacts; skip silently.
        return
    records = bxd.build_records(rel_csv)
    post_total = json.loads(manifest.read_text())["counts"]["post_total"]
    assert len(records) == post_total
    by_rel = bxd.summarize_by_rel(records)
    # Concrete post-audit invariants from Stage A reconciliation (2026-05-19):
    # CORRELATES_WITH = 7 (1 vision + 6 text). This is the load-bearing
    # number the paper now cites.
    assert by_rel.get("CORRELATES_WITH") == 7


# --- Unit: extract_pmid_pmcid ----------------------------------------------

def test_extract_pmid_pmcid_from_figure_id_pmc_form():
    pmid, pmcid = bxd.extract_pmid_pmcid({"figure_id": "PMC10605408_g004"})
    assert pmcid == "PMC10605408"
    assert pmid is None


def test_extract_pmid_pmcid_from_image_path_pmid_prefix():
    pmid, pmcid = bxd.extract_pmid_pmcid({
        "image_path": "/tmp/figures/37894458_correlation_heatmap.jpg"
    })
    assert pmid == "37894458"
    assert pmcid is None


def test_extract_pmid_pmcid_from_image_path_pmcid_prefix():
    pmid, pmcid = bxd.extract_pmid_pmcid({
        "image_path": "artifacts/figures/PMC9466706_g004.jpg"
    })
    assert pmcid == "PMC9466706"


def test_extract_pmid_pmcid_prefers_existing_fields():
    pmid, pmcid = bxd.extract_pmid_pmcid({
        "pmid": "11111", "pmcid": "PMC22222",
        "figure_id": "PMC33333_g1",
    })
    assert pmid == "11111"
    assert pmcid == "PMC22222"


def test_extract_pmid_pmcid_handles_empty():
    pmid, pmcid = bxd.extract_pmid_pmcid({})
    assert pmid is None and pmcid is None


# --- Unit: backfill_vision_provenance -------------------------------------

def test_backfill_vision_provenance_chains_proposal_id_to_pmid():
    records = [
        {
            "graph_rel_type": "CORRELATES_WITH",
            "pmid": None,
            "pmcid": None,
            "title": None,
            "journal": None,
            "evidence": "Vision proposal abcdef0123456789; reason=verified; distance_metric=0.05",
        }
    ]
    proposal_index = {
        "abcdef0123456789": {"pmid": "37894458", "pmcid": "PMC10605408",
                             "image_path": "/tmp/37894458_x.jpg"}
    }
    papers_by_pmid = {"37894458": {"pmid": "37894458", "pmcid": "PMC10605408",
                                    "title": "CT-Based QTA + Microbiome in NSCLC",
                                    "journal": "Cancers"}}
    papers_by_pmcid = {"PMC10605408": papers_by_pmid["37894458"]}
    stats = bxd.backfill_vision_provenance(
        records, proposal_index, papers_by_pmid, papers_by_pmcid
    )
    assert stats["considered"] == 1
    assert stats["backfilled_pmid"] >= 1
    assert stats["backfilled_pmcid"] >= 1
    assert stats["backfilled_title"] >= 1
    r = records[0]
    assert r["pmid"] == "37894458"
    assert r["pmcid"] == "PMC10605408"
    assert r["title"] == "CT-Based QTA + Microbiome in NSCLC"
    assert r["journal"] == "Cancers"


def test_backfill_skips_non_correlates_with_rows():
    records = [
        {"graph_rel_type": "ASSOCIATED_WITH", "pmid": None, "evidence": "Vision proposal abcdef0123456789;"},
    ]
    stats = bxd.backfill_vision_provenance(records, {}, {}, {})
    assert stats["considered"] == 0
    # Row must NOT be mutated.
    assert records[0].get("pmid") is None


def test_backfill_skips_rows_with_existing_pmid():
    records = [
        {"graph_rel_type": "CORRELATES_WITH", "pmid": "99999",
         "evidence": "Vision proposal abcdef0123456789;"},
    ]
    stats = bxd.backfill_vision_provenance(
        records, {"abcdef0123456789": {"pmid": "11111", "pmcid": "PMC1"}}, {}, {}
    )
    assert stats["considered"] == 0
    assert records[0]["pmid"] == "99999"


def test_backfill_silent_when_proposal_id_not_in_index():
    records = [
        {"graph_rel_type": "CORRELATES_WITH", "pmid": None,
         "evidence": "Vision proposal deadbeefcafef00d; reason=verified;"},
    ]
    stats = bxd.backfill_vision_provenance(records, {}, {}, {})
    assert stats["considered"] == 1
    assert stats["backfilled_pmid"] == 0
    assert records[0].get("pmid") is None  # unchanged


# --- Integration: surviving vision edge gets backfilled at runtime --------

def test_real_run_backfills_the_surviving_vision_edge():
    """Against the live artifacts: the prevotella → GLCM_Correlation edge must
    end up with PMID 37894458 + PMCID PMC10605408 + a non-empty title after the
    backfill step runs. This is the load-bearing claim for Stage B item (c)
    evidence drill-down."""
    rel_csv = REPO_ROOT / "artifacts" / "graph_export" / "relationships.csv"
    artifacts = REPO_ROOT / "artifacts"
    if not rel_csv.exists() or not (artifacts / "vision_proposals_gemini_vision.jsonl").exists():
        return  # CI without artifacts
    records = bxd.build_records(rel_csv)
    proposal_index = bxd.load_vision_proposal_index(artifacts)
    audit_index = bxd.load_vision_audit_index(artifacts)
    by_pmid, by_pmcid = bxd.load_papers_corpus(artifacts)
    bxd.backfill_vision_provenance(
        records, proposal_index, by_pmid, by_pmcid,
        audit_by_pmcid=audit_index,
    )
    vision_edges = [
        r for r in records
        if r["graph_rel_type"] == "CORRELATES_WITH"
        and "Vision proposal" in (r.get("evidence") or "")
    ]
    assert len(vision_edges) == 1
    edge = vision_edges[0]
    assert edge["subject_node"] == "prevotella_nigrescens"
    assert edge["object_node"] == "GLCM_Correlation"
    assert edge["pmid"] == "37894458", f"vision-edge PMID not backfilled: {edge['pmid']}"
    assert edge["pmcid"] == "PMC10605408", f"vision-edge PMCID not backfilled: {edge['pmcid']}"
    assert edge.get("title"), "vision-edge title not backfilled from papers corpus"
    # Audit-side backfill: figure_id_pmc + r_value land too (Stage B c).
    assert edge["figure_id"] == "PMC10605408_g004", (
        f"vision-edge figure_id_pmc not backfilled: {edge.get('figure_id')}"
    )
    assert edge["r_value"] == 0.95, (
        f"vision-edge r_value not backfilled: {edge.get('r_value')}"
    )


# --- Unit: load_vision_audit_index -----------------------------------------

def test_load_vision_audit_index_indexes_by_pmcid_and_skips_rejects(tmp_path):
    audit = tmp_path / "vision_gated_audit.jsonl"
    audit.write_text(
        json.dumps({
            "provenance": "historical_graph_edge",
            "figure_id": "PMC10605408_g004",
            "candidate_r": 0.95,
            "image_path": "artifacts/figures/PMC10605408_g004.jpg",
            "final_verdict": "REVIEW",
        }) + "\n" +
        json.dumps({
            "provenance": "current_proposal",
            "figure_id": "PMC9466706_g004",
            "candidate_r": -0.46,
            "image_path": "artifacts/figures/PMC9466706_g004.jpg",
            "final_verdict": "ACCEPT",
        }) + "\n" +
        json.dumps({
            "provenance": "current_proposal",
            "figure_id": "PMC3111466_g006",
            "candidate_r": 0.4,
            "image_path": "artifacts/figures/PMC3111466_g006.jpg",
            "final_verdict": "REJECT_GATE",
        }) + "\n"
    )
    index = bxd.load_vision_audit_index(tmp_path)
    assert "PMC10605408" in index, "REVIEW-verdict row should be retained"
    assert "PMC9466706" in index, "ACCEPT-verdict row should be retained"
    assert "PMC3111466" not in index, "REJECT_GATE row must NOT be indexed"
    assert index["PMC10605408"]["figure_id_pmc"] == "PMC10605408_g004"
    assert index["PMC10605408"]["r_value"] == 0.95


def test_backfill_uses_audit_index_for_figure_id_and_r_value():
    """If audit_by_pmcid provides a matching PMCID, figure_id_pmc + r_value
    backfill onto the record after PMCID is established via the papers
    corpus."""
    records = [
        {
            "graph_rel_type": "CORRELATES_WITH",
            "pmid": None, "pmcid": None, "title": None, "journal": None,
            "figure_id": None, "r_value": None,
            "evidence": "Vision proposal abcdef0123456789;",
        }
    ]
    proposal_index = {
        "abcdef0123456789": {"pmid": "37894458", "pmcid": "PMC10605408",
                             "image_path": "/tmp/37894458_x.jpg"}
    }
    papers_by_pmcid = {
        "PMC10605408": {"pmid": "37894458", "pmcid": "PMC10605408",
                        "title": "QTA+MG NSCLC", "journal": "Cancers"}
    }
    audit_by_pmcid = {
        "PMC10605408": {"figure_id_pmc": "PMC10605408_g004", "r_value": 0.95,
                        "image_path": "artifacts/figures/PMC10605408_g004.jpg"}
    }
    stats = bxd.backfill_vision_provenance(
        records, proposal_index, papers_by_pmid={"37894458": papers_by_pmcid["PMC10605408"]},
        papers_by_pmcid=papers_by_pmcid, audit_by_pmcid=audit_by_pmcid,
    )
    assert stats["backfilled_figure_id"] == 1
    assert stats["backfilled_r_value"] == 1
    r = records[0]
    assert r["figure_id"] == "PMC10605408_g004"
    assert r["r_value"] == 0.95
