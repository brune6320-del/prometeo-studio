"""PROMETEO · FC-009 · STAGE 3B-2D1B2C13C
Dual-Granularity Authority Amendment Custody Test Suite.
"""

import json
import os
import pytest

AMENDMENT_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13C_PASS_B_DUAL_GRANULARITY_AUTHORITY_AMENDMENT.json"
AUDIT_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13C_PASS_B_DUAL_GRANULARITY_AUTHORITY_AUDIT.json"
PAGE_LOAD_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13C_PASS_B_CONTEXT_PAGE_LOAD_AUDIT.json"
DOC_MD_PATH = "docs/FC009_STAGE3B2D1B2C13C_PASS_B_DUAL_GRANULARITY_AUTHORITY_AMENDMENT.md"


def test_amendment_artifact_integrity():
    assert os.path.exists(AMENDMENT_PATH), f"Missing {AMENDMENT_PATH}"
    with open(AMENDMENT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["authority_id"] == "FC009_STAGE3B2D1B2C13C_PASS_B_DUAL_GRANULARITY_AUTHORITY_AMENDMENT"
    assert data["canonical_topology_hash"] == "cbee24b5fd5ef8aa4823b563b9a62242349693a7063e0da994b34b74a6fc86f7"
    assert data["ag272_structural_partition_digest"] == "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059"
    assert data["atomic_candidate_count"] == 118812
    assert data["structural_context_count"] == 33516
    assert data["singleton_context_count"] == 29794
    assert data["non_singleton_context_count"] == 3722
    assert data["singleton_context_count"] + data["non_singleton_context_count"] == 33516

    # Schemas
    assert "required_fields" in data["context_evidence_schema"]
    assert "required_fields" in data["atomic_lineage_schema"]

    # Rules
    assert "STRICT_PROHIBITION_OF_AUTOMATIC_SEMANTIC_ROLE_INHERITANCE" in data["anti_semantic_inheritance_rule"]["rule_statement"]
    assert data["network_policy"]["network_requests"] == 0
    assert data["assessor_status"]["compatibility_verdict"] == "CURRENT_RULE_ENGINE_REQUIRES_SUCCESSOR_ASSESSOR"
    assert data["execution_authority"]["pass_b_execution_ready_v4"] == "NO"
    assert data["verdict"] == "DUAL_GRANULARITY_AUTHORITY_AMENDMENT_VALID"


def test_audit_artifact_integrity():
    assert os.path.exists(AUDIT_PATH), f"Missing {AUDIT_PATH}"
    with open(AUDIT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    pres = data["candidate_universe_preservation_audit"]
    assert pres["canonical_candidates_count"] == 118812
    assert pres["preserved_count"] == 118812
    assert pres["dropped_count"] == 0
    assert pres["merged_count"] == 0
    assert pres["atomic_identity_loss"] is False

    obs = data["observational_and_boundary_audit"]
    assert obs["pdf_content_opens"] == 0
    assert obs["page_renders"] == 0
    assert obs["visual_inspections"] == 0
    assert obs["pass_b_executions"] == 0
    assert obs["pass_b_semantic_observations"] == 0
    assert obs["ontology_assignments"] == 0
    assert obs["m1_executions"] == 0
    assert obs["new_numeric_thresholds_introduced"] == 0

    assert data["readiness_gate_v4"]["pass_b_execution_ready_v4"] == "NO"
    assert data["primary_verdict"] == "DUAL_GRANULARITY_AUTHORITY_AMENDMENT_VALID"


def test_page_load_audit_statistics():
    assert os.path.exists(PAGE_LOAD_PATH), f"Missing {PAGE_LOAD_PATH}"
    with open(PAGE_LOAD_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    p331 = data["page_level_context_distribution_all_331_pages"]
    assert p331["total_pages_evaluated"] == 331
    assert p331["minimum"] == 0
    assert p331["median"] == 7.0
    assert p331["pages_with_0_contexts_count"] == 44
    assert p331["pages_with_exactly_1_context_count"] == 18
    assert p331["pages_with_gt_1_context_count"] == 269
    assert p331["maximum"] == 2127
    assert p331["max_page"]["page_label"] == "E2M1_DOC_0007_P030"

    p287 = data["page_level_context_distribution_287_drawing_pages"]
    assert p287["total_pages_evaluated"] == 287
    assert p287["minimum"] == 1
    assert p287["median"] == 8.0

    ext = data["extreme_pages_batching_audit"]
    assert ext["E2M1_DOC_0002_P011"]["total_candidates"] == 24358
    assert ext["E2M1_DOC_0002_P011"]["total_contexts"] == 1
    assert ext["E2M1_DOC_0002_P013"]["total_candidates"] == 15914
    assert ext["E2M1_DOC_0002_P013"]["total_contexts"] == 1
    assert ext["E2M1_DOC_0009_P019"]["total_candidates"] == 8332
    assert ext["E2M1_DOC_0009_P019"]["total_contexts"] == 5


def test_markdown_documentation_exists():
    assert os.path.exists(DOC_MD_PATH), f"Missing {DOC_MD_PATH}"
    with open(DOC_MD_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "DUAL_GRANULARITY_AUTHORITY_AMENDMENT_VALID" in content
    assert "PASS_B_EXECUTION_READY_V4: NO" in content
    assert "CANONICAL CANDIDATES: 118,812" in content
    assert "PRESEMANTIC STRUCTURAL CONTEXTS: 33,516" in content
    assert "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059" in content
