"""PROMETEO · FC-009 · STAGE 3B-2D1B2C13E
Assessor Environment Provisioning and Freeze Custody Test Suite.
"""

import json
import os
import pytest

PROV_MANIFEST_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_PROVISIONING_MANIFEST.json"
MODEL_MANIFEST_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_MODEL_MANIFEST.json"
OFFLINE_PROOF_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_OFFLINE_PROOF.json"
SYNTHETIC_CAPABILITY_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_SYNTHETIC_CAPABILITY.json"
ENV_FREEZE_PATH = "fase0/reality_corpus/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_ENVIRONMENT_FREEZE.json"
DOC_MD_PATH = "docs/FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_PROVISIONING_AND_FREEZE.md"

FROZEN_9_ROLES = {
    "LINEAR_DIVIDER_ROLE",
    "BACKGROUND_OR_HIGHLIGHT_ROLE",
    "CONTENT_ENCLOSURE_ROLE",
    "TABLE_GRID_ROLE",
    "TEXT_DECORATION_ROLE",
    "IMAGE_FRAMING_ROLE",
    "COMPOUND_GRAPHIC_ROLE",
    "NO_CLEAR_SEMANTIC_ROLE",
    "ROLE_AMBIGUOUS"
}


def test_provisioning_manifest_artifact_integrity():
    assert os.path.exists(PROV_MANIFEST_PATH), f"Missing {PROV_MANIFEST_PATH}"
    with open(PROV_MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_id"] == "FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_PROVISIONING_MANIFEST"
    env = data["environment"]
    assert env["python_version"].startswith("3.11")
    assert env["system"] == "Darwin"
    assert env["machine"] == "arm64"
    assert env["unified_ram_bytes"] == 8589934592
    assert env["backend_classification"] == "SAME_PROCESS_LIBRARY_BACKEND"
    assert env["candidate_architecture_class"] == "MLX_VLM_SAME_PROCESS"

    pkgs = data["key_packages"]
    assert pkgs["mlx"] != "NOT_INSTALLED"
    assert pkgs["mlx-vlm"] != "NOT_INSTALLED"
    assert pkgs["transformers"] != "NOT_INSTALLED"
    assert pkgs["safetensors"] != "NOT_INSTALLED"
    assert pkgs["pillow"] != "NOT_INSTALLED"
    assert pkgs["pymupdf"] != "NOT_INSTALLED"
    assert len(data["pip_freeze"]) > 10


def test_model_manifest_artifact_integrity():
    assert os.path.exists(MODEL_MANIFEST_PATH), f"Missing {MODEL_MANIFEST_PATH}"
    with open(MODEL_MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_id"] == "FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_MODEL_MANIFEST"
    assert data["assessor_id"] == "MLX_VLM_QWEN2_VL_2B_INSTRUCT_4BIT"
    assert data["model_architecture"] == "Qwen2-VL"
    assert data["parameter_count"] == "2.21B"
    assert data["quantization_format"] == "4-bit (mlx-q4)"
    assert data["total_files"] == 12
    assert data["total_size_bytes"] == 1261854392
    assert data["assessor_model_manifest_sha256"] == "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a"

    # Verify no private absolute home paths encoded in logical paths
    for art in data["artifacts"]:
        assert art["logical_path"].startswith("ASSESSOR_MODEL_ROOT/"), (
            f"Artifact logical path {art['logical_path']} leaks machine private path"
        )
        assert len(art["sha256"]) == 64
        assert art["size_bytes"] > 0


def test_offline_proof_artifact_integrity():
    assert os.path.exists(OFFLINE_PROOF_PATH), f"Missing {OFFLINE_PROOF_PATH}"
    with open(OFFLINE_PROOF_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["proof_id"] == "FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_OFFLINE_PROOF"
    assert data["execution_class"] == "SAME_PROCESS_LIBRARY_BACKEND"
    assert data["local_model_path_verified"] is True
    assert data["same_process_verified"] is True
    assert data["socket_firewall_active"] is True
    assert data["runtime_network_connection_attempts"] == 0
    assert data["runtime_network_requests"] == 0
    assert data["runtime_downloads"] == 0
    assert data["remote_model_calls"] == 0
    assert data["cold_load_duration_seconds"] > 0
    assert data["memory_profile_mb"]["loaded_model_rss"] > 0


def test_synthetic_capability_and_reproducibility():
    assert os.path.exists(SYNTHETIC_CAPABILITY_PATH), f"Missing {SYNTHETIC_CAPABILITY_PATH}"
    with open(SYNTHETIC_CAPABILITY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["capability_id"] == "FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_SYNTHETIC_CAPABILITY"

    # Synthetic fixture & overlay protocol
    fix = data["synthetic_fixture"]
    assert fix["fixture_type"] == "ABSTRACT_LAYOUT_PRIMITIVES_ONLY"
    assert os.path.exists(fix["base_image_relpath"])
    assert os.path.exists(fix["overlay_image_relpath"])
    assert fix["overlay_rendering_protocol"] == "EXACT_MEMBER_GEOMETRY_OVERLAY_RGB_150DPI"
    assert fix["overlay_data_firewall_verified"] is True

    # Prompt Preservation
    prompts = data["prompts"]
    assert prompts["canonical_semantic_prompt_sha256"] == "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
    assert prompts["backend_transport_wrapper_sha256"] == "221eaf2045c5f5771856b42e2eb4cc9a4f0f48c234fb14c336d450595588fb41"

    # Reproducibility
    repro = data["reproducibility"]
    assert repro["reproducibility_class"] == "BITWISE_DETERMINISTIC"
    assert repro["runs_executed"] == 3
    assert repro["bitwise_identical"] is True
    assert len(repro["runs"]) == 3

    # Output Validation
    val = data["structured_output_validation"]
    assert val["json_parse_success"] is True
    assert val["schema_conformance"] is True
    rec = val["validated_canonical_record"]
    assert rec["structural_context_id"] == "SYNTH_CTX_SECTION_DIVIDER_001"
    assert rec["assessment_target_type"] == "STRUCTURAL_CONTEXT"
    assert rec["context_role_evidence_state"] in FROZEN_9_ROLES
    assert rec["confidence"] in ["HIGH", "MODERATE", "LOW"]
    assert len(rec["context_role_rationale"]) > 0
    assert rec["technical_state"] == "PASS_B_ROLE_EVIDENCE_COMPLETE"
    assert rec["assessor_id"] == "MLX_VLM_QWEN2_VL_2B_INSTRUCT_4BIT"
    assert rec["assessor_manifest_digest"] == "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a"
    assert rec["prompt_sha256"] == "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
    assert rec["render_protocol_id"] == "EXACT_MEMBER_GEOMETRY_OVERLAY_RGB_150DPI"

    # Prohibited fields audit
    for prohibited in ["adjudicated_ontology_class", "m1_stratum", "detector_predictions", "is_long_rule"]:
        assert prohibited not in rec, f"Prohibited field {prohibited} present in PASS B record"


def test_environment_freeze_and_gate_v6():
    assert os.path.exists(ENV_FREEZE_PATH), f"Missing {ENV_FREEZE_PATH}"
    with open(ENV_FREEZE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["freeze_id"] == "FC009_STAGE3B2D1B2C13E_PASS_B_ASSESSOR_ENVIRONMENT_FREEZE"
    assert data["status"] == "LOCAL_ASSESSOR_ENVIRONMENT_PROVISIONED"

    gate = data["readiness_gate_v6"]
    assert gate["pass_b_execution_ready_v6"] == "YES"
    assert gate["ag273_authority_intact"] is True
    assert gate["ag274_contracts_intact"] is True
    assert gate["eligible_model_locally_frozen"] is True
    assert gate["same_process_backend_proven"] is True
    assert gate["runtime_zero_network_proven"] is True
    assert gate["model_manifest_digest_frozen"] is True
    assert gate["prompt_sha_preserved"] is True
    assert gate["decoding_frozen"] is True
    assert gate["exact_member_overlay_pipeline_proven_synthetically"] is True
    assert gate["structured_output_validated"] is True
    assert gate["anti_inheritance_preserved"] is True
    assert gate["lexical_firewall_preserved"] is True
    assert gate["one_unit_memory_feasibility_demonstrated"] is True
    assert gate["reproducibility_acceptable"] is True
    assert gate["failure_policy_frozen"] is True
    assert gate["corpus_semantic_observations_remain_zero"] is True

    # Absolute boundaries
    bounds = data["boundaries_guarantee"]
    assert bounds["runtime_network_requests"] == 0
    assert bounds["runtime_downloads"] == 0
    assert bounds["remote_model_calls"] == 0
    assert bounds["corpus_pdf_opens"] == 0
    assert bounds["corpus_page_renders"] == 0
    assert bounds["corpus_semantic_image_views"] == 0
    assert bounds["pass_b_semantic_observations"] == 0
    assert bounds["pass_b_executions"] == 0
    assert bounds["m1_executions"] == 0
    assert bounds["ontology_assignments"] == 0
    assert bounds["new_numeric_thresholds"] == 0

    # Authorities
    auth = data["authority_verdicts"]
    assert auth["authority_granted_for_dual_granularity_protocol"] == "YES"
    assert auth["authority_granted_for_assessor_environment"] == "YES"
    assert auth["authority_granted_for_pass_b_execution"] == "NO"
    assert auth["pass_b_executed"] == "NO"


def test_markdown_documentation_integrity():
    assert os.path.exists(DOC_MD_PATH), f"Missing {DOC_MD_PATH}"
    with open(DOC_MD_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "LOCAL_ASSESSOR_ENVIRONMENT_PROVISIONED" in content
    assert "PASS_B_EXECUTION_READY_V6: YES" in content
    assert "EXACT_MEMBER_GEOMETRY_OVERLAY_REQUIRED" in content
    assert "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a" in content
    assert "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b" in content
    assert "BITWISE_DETERMINISTIC" in content
    assert "RUNTIME NETWORK REQUESTS: 0" in content
    assert "AUTHORITY_GRANTED_FOR_ASSESSOR_ENVIRONMENT: YES" in content
    assert "AUTHORITY_GRANTED_FOR_PASS_B_EXECUTION: NO" in content
