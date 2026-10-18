"""PROMETEO · FC-009 · STAGE 3B-2D1B2C13G
Canonical PASS B Execution & Durable Result Custody Test Suite.
"""

import hashlib
import json
import os
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUN_ID = "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
RUN_DIR = os.path.join(REPO_ROOT, "fase0/reality_corpus/pass_b_runs", RUN_ID)
RESULTS_DIR = os.path.join(RUN_DIR, "results")
FAILURES_DIR = os.path.join(RUN_DIR, "failures")
LEDGER_PATH = os.path.join(RUN_DIR, f"{RUN_ID}_DERIVED_LEDGER.jsonl")

CONTRACT_V2_PATH = os.path.join(REPO_ROOT, "fase0/reality_corpus/FC009_STAGE3B2D1B2C13F1_PASS_B_FINAL_EXECUTION_CONTRACT_V2.json")
EXPECTED_CONTRACT_V2_SHA = "826254732db43a2c213485d911980958e39d4d31ad6f2d1d7f446ec636fc1726"

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

POSITIVE_7_ROLES = {
    "LINEAR_DIVIDER_ROLE",
    "BACKGROUND_OR_HIGHLIGHT_ROLE",
    "CONTENT_ENCLOSURE_ROLE",
    "TABLE_GRID_ROLE",
    "TEXT_DECORATION_ROLE",
    "IMAGE_FRAMING_ROLE",
    "COMPOUND_GRAPHIC_ROLE"
}

EXPECTED_PROMPT_SHA = "c70b89244760860479881561327a26eef30a86c79d865a9be1f7d452e739f62b"
EXPECTED_WRAPPER_SHA = "221eaf2045c5f5771856b42e2eb4cc9a4f0f48c234fb14c336d450595588fb41"
EXPECTED_MODEL_MANIFEST_SHA = "fe74b8a1f004d500b04e462e9dff8460bb9a5be82ec07d306f7f62c63d1f067a"
DECODING_CONTRACT_DIGEST = "2d504331fe5964d5369547d8bbd9c67a2a41c4e19d1023b6a742d9d6776a127a"


def test_b2c13g_execution_environment_and_preflights():
    """Verify execution engine preflights and frozen cryptographic bounds."""
    assert os.path.exists(CONTRACT_V2_PATH), f"Missing {CONTRACT_V2_PATH}"
    with open(CONTRACT_V2_PATH, "rb") as f:
        contract_sha = hashlib.sha256(f.read()).hexdigest()
    assert contract_sha == EXPECTED_CONTRACT_V2_SHA

    engine_path = os.path.join(REPO_ROOT, "fase0/experiments/h3dv3_dev_003/m1/execute_pass_b_canonical_b2c13g.py")
    assert os.path.exists(engine_path), "Missing execution engine script"


def test_b2c13g_immutable_result_format_and_errata_compliance():
    """Verify committed result records adhere to Erratum A, schema, and hashes."""
    if not os.path.exists(RESULTS_DIR):
        pytest.skip("Results directory does not exist yet")

    committed_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.endswith(".json") and not f.endswith(".tmp")])
    if not committed_files:
        pytest.skip("Zero committed results yet")

    required_fields = [
        "canonical_run_id",
        "execution_ordinal",
        "structural_context_id",
        "assessment_target_type",
        "context_role_evidence_state",
        "confidence",
        "context_role_rationale",
        "technical_state",
        "execution_status",
        "atomic_semantic_assessment_status",
        "assessor_id",
        "assessor_manifest_digest",
        "prompt_sha256",
        "backend_wrapper_sha256",
        "render_protocol_id",
        "source_document_sha256",
        "base_page_render_sha256",
        "overlay_render_sha256",
        "member_identity_digest",
        "input_preimage_sha256",
        "raw_assessor_output",
        "raw_output_sha256",
        "parsed_output_sha256",
        "parser_version",
        "completed_at"
    ]

    prohibited_fields = [
        "adjudicated_ontology_class",
        "m1_stratum",
        "detector_predictions",
        "is_long_rule",
        "target",
        "adjudicated_class",
        "phase_d_decision"
    ]

    for fname in committed_files:
        fpath = os.path.join(RESULTS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            rec = json.load(f)

        # 1. Required fields
        for rf in required_fields:
            assert rf in rec, f"Missing {rf} in {fname}"

        # 2. Prohibited fields
        for pf in prohibited_fields:
            assert pf not in rec, f"Prohibited field {pf} found in {fname}"

        # 3. Filename matches ordinal
        expected_name = f"{rec['execution_ordinal']:05d}.json"
        assert fname == expected_name, f"Filename {fname} != expected {expected_name}"

        # 4. Canonical identifiers
        assert rec["canonical_run_id"] == RUN_ID
        assert rec["assessor_id"] == "MLX_VLM_QWEN2_VL_2B_INSTRUCT_4BIT"
        assert rec["assessor_manifest_digest"] == EXPECTED_MODEL_MANIFEST_SHA
        assert rec["prompt_sha256"] == EXPECTED_PROMPT_SHA
        assert rec["backend_wrapper_sha256"] == EXPECTED_WRAPPER_SHA
        assert rec["render_protocol_id"] == "EXACT_MEMBER_GEOMETRY_OVERLAY_RGB_150DPI"
        assert rec["execution_status"] == "COMMITTED"
        assert rec["parser_version"] == "STRICT_PASS_B_V2"

        # 5. Role & Technical state Erratum A mapping
        role = rec["context_role_evidence_state"]
        assert role in FROZEN_9_ROLES, f"Invalid role {role} in {fname}"
        assert rec["confidence"] in {"HIGH", "MODERATE", "LOW"}

        tech_state = rec["technical_state"]
        if role in POSITIVE_7_ROLES:
            assert tech_state == "PASS_B_ROLE_EVIDENCE_COMPLETE", f"Mismatch in {fname}"
        elif role == "NO_CLEAR_SEMANTIC_ROLE":
            assert tech_state == "PASS_B_NO_CLEAR_ROLE", f"Mismatch in {fname}"
        elif role == "ROLE_AMBIGUOUS":
            assert tech_state == "PASS_B_ROLE_AMBIGUOUS", f"Mismatch in {fname}"

        # Never accept COMPLETED as technical state
        assert tech_state != "COMPLETED", f"Conflated technical_state = COMPLETED in {fname}"

        # 6. Raw output hash integrity
        expected_raw_sha = hashlib.sha256(rec["raw_assessor_output"].encode("utf-8")).hexdigest()
        assert rec["raw_output_sha256"] == expected_raw_sha, f"Raw output hash mismatch in {fname}"

        # 7. Input preimage hash recomputation
        token_str = (
            f"{rec['canonical_run_id']}|"
            f"{rec['execution_ordinal']}|"
            f"{rec['structural_context_id']}|"
            f"{rec['source_document_sha256']}|"
            f"{int(rec['structural_context_id'].split('_P')[1].split('_')[0])}|"
            f"{rec['base_page_render_sha256']}|"
            f"{rec['overlay_render_sha256']}|"
            f"{rec['member_identity_digest']}|"
            f"{rec['assessor_manifest_digest']}|"
            f"{rec['prompt_sha256']}|"
            f"{rec['backend_wrapper_sha256']}|"
            f"{rec['render_protocol_id']}|"
            f"{DECODING_CONTRACT_DIGEST}"
        )
        expected_input_sha = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
        assert rec["input_preimage_sha256"] == expected_input_sha, f"Input preimage hash mismatch in {fname}"


def test_b2c13g_ledger_and_result_set_reproducibility():
    """Verify derived JSONL ledger matches committed result files."""
    if not os.path.exists(RESULTS_DIR):
        pytest.skip("Results directory does not exist yet")

    committed_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.endswith(".json") and not f.endswith(".tmp")])
    if not committed_files:
        pytest.skip("Zero committed results yet")

    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            ledger_lines = [json.loads(line) for line in f if line.strip()]
        assert len(ledger_lines) == len(committed_files)
        for i, rec in enumerate(ledger_lines):
            assert rec["execution_ordinal"] == i + 1
