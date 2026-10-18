"""
Test suite for PROMETEO AG276 / Stage3B-2D1B2C13F
PASS B Final Execution Preregistration, Resumability Contract and Dry-Run Invariant Audit.
"""

import os
import json
import hashlib
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FINAL_CONTRACT_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F_PASS_B_FINAL_EXECUTION_CONTRACT.json")
CONTEXT_MANIFEST_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F_PASS_B_CONTEXT_EXECUTION_MANIFEST.json")
SOURCE_DOC_MANIFEST_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F_PASS_B_SOURCE_DOCUMENT_MANIFEST.json")
CHECKPOINT_CONTRACT_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F_PASS_B_CHECKPOINT_AND_RESUME_CONTRACT.json")
DRY_RUN_AUDIT_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F_PASS_B_DRY_RUN_INVARIANT_AUDIT.json")


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_b2c13f_artifacts_exist():
    assert os.path.exists(FINAL_CONTRACT_PATH), "Missing FINAL_EXECUTION_CONTRACT"
    assert os.path.exists(CONTEXT_MANIFEST_PATH), "Missing CONTEXT_EXECUTION_MANIFEST"
    assert os.path.exists(SOURCE_DOC_MANIFEST_PATH), "Missing SOURCE_DOCUMENT_MANIFEST"
    assert os.path.exists(CHECKPOINT_CONTRACT_PATH), "Missing CHECKPOINT_AND_RESUME_CONTRACT"
    assert os.path.exists(DRY_RUN_AUDIT_PATH), "Missing DRY_RUN_INVARIANT_AUDIT"


def test_b2c13f_source_document_manifest():
    with open(SOURCE_DOC_MANIFEST_PATH, "r") as f:
        data = json.load(f)

    assert data["manifest_id"] == "FC009_STAGE3B2D1B2C13F_PASS_B_SOURCE_DOCUMENT_MANIFEST"
    assert data["document_count"] == 10
    assert data["total_page_count"] == 331
    assert data["immutable_preimages_verified"] is True
    assert len(data["documents"]) == 10

    total_pages = sum(d["page_count"] for d in data["documents"])
    assert total_pages == 331


def test_b2c13f_context_execution_manifest():
    with open(CONTEXT_MANIFEST_PATH, "r") as f:
        data = json.load(f)

    assert data["manifest_id"] == "FC009_STAGE3B2D1B2C13F_PASS_B_CONTEXT_EXECUTION_MANIFEST"
    assert data["total_contexts"] == 33516
    assert data["singleton_contexts"] == 29794
    assert data["non_singleton_contexts"] == 3722
    assert data["total_member_objects_sum"] == 118812
    assert data["structural_partition_digest"] == "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059"

    contexts = data["contexts"]
    assert len(contexts) == 33516

    # Verify execution ordinals
    ordinals = [c["execution_ordinal"] for c in contexts]
    assert ordinals[0] == 1
    assert ordinals[-1] == 33516
    assert len(set(ordinals)) == 33516
    assert ordinals == list(range(1, 33517))

    # Verify unique IDs
    context_ids = [c["structural_context_id"] for c in contexts]
    assert len(set(context_ids)) == 33516

    # Verify target types and fields
    for c in contexts[:100]:
        assert "execution_ordinal" in c
        assert "structural_context_id" in c
        assert "document_id" in c
        assert "page_index" in c
        assert "component_cardinality" in c
        assert "context_bbox" in c
        assert "member_identity_digest" in c
        assert "assessment_target_type" in c
        if c["component_cardinality"] == 1:
            assert c["assessment_target_type"] == "ATOMIC_CANDIDATE"
        else:
            assert c["assessment_target_type"] == "STRUCTURAL_CONTEXT"


def test_b2c13f_checkpoint_and_resume_contract():
    with open(CHECKPOINT_CONTRACT_PATH, "r") as f:
        data = json.load(f)

    assert data["contract_id"] == "FC009_STAGE3B2D1B2C13F_PASS_B_CHECKPOINT_AND_RESUME_CONTRACT"
    assert data["canonical_run_id"] == "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
    assert data["execution_class"] == "SAME_PROCESS_LIBRARY_BACKEND"
    assert data["execution_semantics_amendment"]["authorized_resumability"] is True
    assert data["checkpoint_ledger_schema"]["format"] == "JSONL_APPEND_ONLY"
    assert data["technical_failure_policy"]["mode"] == "FAIL_CLOSED"
    assert data["retry_policy"]["mode"] == "NO_AUTOMATIC_RETRY"
    assert data["concurrency_policy"]["model_inference_concurrency"] == 1


def test_b2c13f_dry_run_invariant_audit():
    with open(DRY_RUN_AUDIT_PATH, "r") as f:
        data = json.load(f)

    assert data["audit_id"] == "FC009_STAGE3B2D1B2C13F_PASS_B_DRY_RUN_INVARIANT_AUDIT"
    assert data["continuous_vs_resumed_result_equivalence"] == "YES"
    assert data["duplicate_detection_invariant"] == "PASSED_WITH_DUPLICATE_CANONICAL_RESULT_CONFLICT"
    assert data["prohibited_field_firewall_invariant"] == "PASSED_WITH_STRICT_REJECTION"
    assert data["corpus_semantic_observations_count"] == 0
    assert data["corpus_pdf_opens_count"] == 0
    assert data["corpus_page_renders_count"] == 0


def test_b2c13f_final_execution_contract_and_gate_v7():
    with open(FINAL_CONTRACT_PATH, "r") as f:
        data = json.load(f)

    assert data["contract_id"] == "FC009_STAGE3B2D1B2C13F_PASS_B_FINAL_EXECUTION_CONTRACT"
    assert data["canonical_run_id"] == "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
    assert data["primary_verdict"] == "PASS_B_FINAL_EXECUTION_PREREGISTRATION_CLOSED"
    assert data["successor_stage"] == "AG277 — CANONICAL PASS B EXECUTION"

    # Digests
    digests = data["bound_component_digests"]
    assert digests["canonical_topology_sha256"] == "cbee24b5fd5ef8aa4823b563b9a62242349693a7063e0da994b34b74a6fc86f7"
    assert digests["structural_partition_digest"] == "24ae541c60ffe4cc09f50215f3c562310aff3577b3c3c72a4afc46e68c781059"
    assert digests["assessor_model_manifest_sha256"] == "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a"
    assert digests["canonical_prompt_sha256"] == "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
    assert digests["backend_wrapper_sha256"] == "221eaf2045c5f5771856b42e2eb4cc9a4f0f48c234fb14c336d450595588fb41"

    # Gate V7
    gate = data["execution_readiness_gate_v7"]
    assert gate["pass_b_execution_ready_v7"] == "YES"
    assert gate["membership_accounting_exact"] is True
    assert gate["exact_geometry_reconstructable_for_all_contexts"] is True
    assert gate["continuous_vs_resumed_synthetic_equivalence_proven"] is True
    assert gate["corpus_semantic_observations_remain_zero"] is True

    # Authorities
    auth = data["authority_verdicts"]
    assert auth["authority_granted_for_dual_granularity_protocol"] == "YES"
    assert auth["authority_granted_for_assessor_environment"] == "YES"
    assert auth["authority_granted_for_pass_b_execution"] == "YES"
    assert auth["pass_b_executed"] == "NO"
    assert auth["fresh_validation"] == "NO"
    assert auth["generalization_evidence"] == "NO"


def test_b2c13f_reproducibility_hashes_match_files():
    source_sha = compute_file_sha256(SOURCE_DOC_MANIFEST_PATH)
    context_sha = compute_file_sha256(CONTEXT_MANIFEST_PATH)
    checkpoint_sha = compute_file_sha256(CHECKPOINT_CONTRACT_PATH)

    with open(FINAL_CONTRACT_PATH, "r") as f:
        data = json.load(f)

    assert data["bound_component_digests"]["source_document_manifest_sha256"] == source_sha
    assert data["bound_component_digests"]["context_execution_manifest_sha256"] == context_sha
    assert data["bound_component_digests"]["checkpoint_and_resume_contract_sha256"] == checkpoint_sha
