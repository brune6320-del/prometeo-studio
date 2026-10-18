"""
Test suite for PROMETEO AG276A / Stage3B-2D1B2C13F1
PASS B Final Execution Contract Errata and Durability Hardening.
"""

import os
import json
import hashlib
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FINAL_CONTRACT_V2_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F1_PASS_B_FINAL_EXECUTION_CONTRACT_V2.json")
DURABLE_COMMIT_CONTRACT_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F1_PASS_B_DURABLE_COMMIT_CONTRACT.json")
RESUME_EQUIV_V2_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F1_PASS_B_RESUME_EQUIVALENCE_V2_AUDIT.json")
SCHEMA_ERRATA_AUDIT_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F1_PASS_B_SCHEMA_ERRATA_AUDIT.json")


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_b2c13f1_artifacts_exist():
    assert os.path.exists(FINAL_CONTRACT_V2_PATH), "Missing FINAL_EXECUTION_CONTRACT_V2"
    assert os.path.exists(DURABLE_COMMIT_CONTRACT_PATH), "Missing DURABLE_COMMIT_CONTRACT"
    assert os.path.exists(RESUME_EQUIV_V2_PATH), "Missing RESUME_EQUIVALENCE_V2_AUDIT"
    assert os.path.exists(SCHEMA_ERRATA_AUDIT_PATH), "Missing SCHEMA_ERRATA_AUDIT"


def test_b2c13f1_contract_v2_supersession_and_preimages():
    with open(FINAL_CONTRACT_V2_PATH, "r") as f:
        data = json.load(f)

    assert data["contract_id"] == "FC009_STAGE3B2D1B2C13F1_PASS_B_FINAL_EXECUTION_CONTRACT_V2"
    assert data["canonical_run_id"] == "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
    assert data["supersedes"] == "FC009_STAGE3B2D1B2C13F_PASS_B_FINAL_EXECUTION_CONTRACT"
    assert data["superseded_contract_sha256"] == "56d5a04cdb64894e27e75f1b3f2d5c2ae2aa20760c0f83ef2b29f2d20bb33fa9"

    # Verify unchanged scientific preimages
    digests = data["bound_component_digests"]
    assert digests["canonical_topology_sha256"] == "cbee24b5fd5ef8aa4823b563b9a62242349693a7063e0da994b34b74a6fc86f7"
    assert digests["structural_partition_digest"] == "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059"
    assert digests["source_document_manifest_sha256"] == "b7aefc5c80e6f66957b92e5ff0bb60d89c5ee3fbab94ec307db2ec6c0baba6eb"
    assert digests["context_execution_manifest_sha256"] == "f77f1db50a136152e9a6ac9122ad130e49fd74c35385663990787807190bf736"
    assert digests["assessor_model_manifest_sha256"] == "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a"
    assert digests["canonical_prompt_sha256"] == "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
    assert digests["backend_wrapper_sha256"] == "221eaf2045c5f5771856b42e2eb4cc9a4f0f48c234fb14c336d450595588fb41"


def test_b2c13f1_schema_errata_and_domain_separation():
    with open(SCHEMA_ERRATA_AUDIT_PATH, "r") as f:
        data = json.load(f)

    assert data["audit_id"] == "FC009_STAGE3B2D1B2C13F1_PASS_B_SCHEMA_ERRATA_AUDIT"
    assert data["erratum_a_confirmation"]["technical_state_contradiction_confirmed"] == "YES"

    tech_states = data["canonical_technical_states_restored"]["vocabulary"]
    assert "PASS_B_ROLE_EVIDENCE_COMPLETE" in tech_states
    assert "PASS_B_NO_CLEAR_ROLE" in tech_states
    assert "PASS_B_ROLE_AMBIGUOUS" in tech_states
    assert "PASS_B_TECHNICAL_FAILURE" in tech_states
    assert "COMPLETED" not in tech_states

    exec_statuses = data["execution_status_field_definition"]["vocabulary"]
    assert "COMMITTED" in exec_statuses
    assert "VALIDATED" in exec_statuses
    assert "STAGED" in exec_statuses

    sep = data["state_domain_separation"]["rule"]
    assert "context_role_evidence_state != technical_state != execution_status" in sep


def test_b2c13f1_durable_commit_contract():
    with open(DURABLE_COMMIT_CONTRACT_PATH, "r") as f:
        data = json.load(f)

    assert data["contract_id"] == "FC009_STAGE3B2D1B2C13F1_PASS_B_DURABLE_COMMIT_CONTRACT"
    assert data["jsonl_append_crash_atomic_audit"]["jsonl_append_crash_atomic"] == "NO"

    arch = data["canonical_commit_architecture"]
    assert arch["name"] == "IMMUTABLE_PER_CONTEXT_ATOMIC_COMMIT_V1"
    assert arch["canonical_completion_authority"] == "IMMUTABLE_CONTEXT_RESULT_FILES"
    assert arch["jsonl_ledger_authority"] == "DERIVED_INDEX_ONLY"

    input_spec = data["input_preimage_digest_specification"]
    assert input_spec["name"] == "PASS_B_CONTEXT_INPUT_PREIMAGE_SHA256"

    result_set_spec = data["result_set_digest_specification"]
    assert result_set_spec["name"] == "PASS_B_CANONICAL_RESULT_SET_SHA256"


def test_b2c13f1_resume_equivalence_v2_and_crash_cases():
    with open(RESUME_EQUIV_V2_PATH, "r") as f:
        data = json.load(f)

    assert data["audit_id"] == "FC009_STAGE3B2D1B2C13F1_PASS_B_RESUME_EQUIVALENCE_V2_AUDIT"
    assert data["continuous_vs_resumed_result_equivalence_v2"] == "YES"

    crash_cases = data["crash_cases_tested"]
    assert crash_cases["case_a_crash_before_temp_write"] == "PASSED_CONTEXT_RERUNS"
    assert crash_cases["case_b_crash_after_temp_write_before_fsync"] == "PASSED_TEMP_IGNORED_CONTEXT_RERUNS"
    assert crash_cases["case_c_crash_after_temp_fsync_before_atomic_rename"] == "PASSED_TEMP_IGNORED_CONTEXT_RERUNS"
    assert crash_cases["case_d_crash_immediately_after_atomic_rename"] == "PASSED_RESULT_RECOGNIZED_NO_RERUN"
    assert crash_cases["case_e_crash_during_rebuilding_derived_jsonl_ledger"] == "PASSED_DERIVED_LEDGER_RECONSTRUCTED"
    assert crash_cases["case_f_existing_conflicting_committed_result"] == "PASSED_DUPLICATE_CANONICAL_RESULT_CONFLICT"

    assert data["derived_jsonl_reconstruction_verified"] is True
    assert len(data["canonical_synthetic_result_set_sha256"]) == 64


def test_b2c13f1_gate_v7_1_and_authority():
    with open(FINAL_CONTRACT_V2_PATH, "r") as f:
        data = json.load(f)

    gate = data["execution_readiness_gate_v7_1"]
    assert gate["pass_b_execution_ready_v7_1"] == "YES"
    assert gate["ag276_scientific_preimages_unchanged"] is True
    assert gate["schema_conflation_repaired"] is True
    assert gate["execution_status_separated"] is True
    assert gate["true_atomic_commit_demonstrated"] is True
    assert gate["crash_cases_a_through_f_passed"] is True
    assert gate["resumability_equivalence_v2_passed"] is True
    assert gate["derived_jsonl_reconstruction_passed"] is True
    assert gate["corpus_semantic_observations_remain_zero"] is True

    auth = data["authority_verdicts"]
    assert auth["authority_granted_for_pass_b_execution"] == "YES"
    assert auth["pass_b_executed"] == "NO"
    assert auth["fresh_validation"] == "NO"
    assert auth["generalization_evidence"] == "NO"

    assert data["primary_verdict"] == "PASS_B_EXECUTION_ERRATA_CLOSED"
    assert data["successor_stage"] == "AG277 — CANONICAL PASS B EXECUTION"
