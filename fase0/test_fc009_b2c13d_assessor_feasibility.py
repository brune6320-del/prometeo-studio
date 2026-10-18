"""PROMETEO · FC-009 · STAGE 3B-2D1B2C13D
Successor Assessor Feasibility & Inventory Custody Test Suite.
"""

import json
import os
import pytest

INVENTORY_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13D_PASS_B_ASSESSOR_LOCAL_INVENTORY.json"
FEASIBILITY_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13D_PASS_B_SUCCESSOR_ASSESSOR_FEASIBILITY.json"
PREREGISTRATION_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13D_PASS_B_SUCCESSOR_ASSESSOR_PREREGISTRATION.json"
DOC_MD_PATH = "docs/FC009_STAGE3B2D1B2C13D_PASS_B_SUCCESSOR_ASSESSOR_FEASIBILITY.md"


def test_inventory_artifact_integrity():
    assert os.path.exists(INVENTORY_PATH), f"Missing {INVENTORY_PATH}"
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["inventory_id"] == "FC009_STAGE3B2D1B2C13D_PASS_B_ASSESSOR_LOCAL_INVENTORY"
    assert data["eligible_candidates_count"] == 0
    assert data["total_candidates_evaluated"] >= 7

    # Check key packages reported as NOT_INSTALLED
    pkgs = data["key_packages_status"]
    assert pkgs["torch"] == "NOT_INSTALLED"
    assert pkgs["transformers"] == "NOT_INSTALLED"
    assert pkgs["mlx"] == "NOT_INSTALLED"
    assert pkgs["llama_cpp"] == "NOT_INSTALLED"


def test_feasibility_artifact_integrity():
    assert os.path.exists(FEASIBILITY_PATH), f"Missing {FEASIBILITY_PATH}"
    with open(FEASIBILITY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["feasibility_id"] == "FC009_STAGE3B2D1B2C13D_PASS_B_SUCCESSOR_ASSESSOR_FEASIBILITY"
    assert data["primary_verdict"] == "NO_ELIGIBLE_LOCAL_ASSESSOR"
    assert data["assessor_selection_status"]["status"] == "NO_ELIGIBLE_LOCAL_ASSESSOR"
    assert data["assessor_selection_status"]["selected_assessor"] is None

    # Preimage verification
    assert data["preimage_verification"]["canonical_topology_sha256"] == "cbee24b5fd5ef8aa4823b563b9a62242349693a7063e0da994b34b74a6fc86f7"
    assert data["preimage_verification"]["ag272_partition_digest"] == "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059"

    # Absolute boundaries
    bounds = data["boundaries_guarantee"]
    assert bounds["network_requests"] == 0
    assert bounds["downloads"] == 0
    assert bounds["remote_model_calls"] == 0
    assert bounds["pdf_content_opens"] == 0
    assert bounds["corpus_page_renders"] == 0
    assert bounds["corpus_semantic_image_views"] == 0
    assert bounds["pass_b_semantic_observations"] == 0
    assert bounds["pass_b_executions"] == 0
    assert bounds["m1_executions"] == 0
    assert bounds["ontology_assignments"] == 0
    assert bounds["new_numeric_thresholds"] == 0

    # Preregistration specs
    specs = data["frozen_preregistration_specifications"]
    assert specs["canonical_prompt_sha256"] == "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
    assert specs["context_overlay_architecture"]["verdict"] == "EXACT_MEMBER_GEOMETRY_OVERLAY_REQUIRED"
    assert specs["failure_policy"]["principle"] == "FAIL_CLOSED"

    # Gate V5
    assert data["readiness_gate_v5"]["pass_b_execution_ready_v5"] == "NO"


def test_preregistration_artifact_not_created():
    # Section 24.B: "If and only if an eligible assessor exists"
    assert not os.path.exists(PREREGISTRATION_PATH), (
        "Preregistration artifact must not exist when NO_ELIGIBLE_LOCAL_ASSESSOR is established"
    )


def test_markdown_documentation_integrity():
    assert os.path.exists(DOC_MD_PATH), f"Missing {DOC_MD_PATH}"
    with open(DOC_MD_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "NO_ELIGIBLE_LOCAL_ASSESSOR" in content
    assert "PASS_B_EXECUTION_READY_V5: NO" in content
    assert "EXACT_MEMBER_GEOMETRY_OVERLAY_REQUIRED" in content
    assert "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b" in content
    assert "NETWORK_REQUESTS: 0" in content
