"""PROMETEO Codex Worker Trust-Boundary & Context-Isolation Test Suite v0.1.
Order: PROM-C00 / AG277-AUTO-04C1
Validates task workspace isolation, trusted provenance separation,
strict native output schema enforcement, non-USD entitlement budget accounting,
and adversarial context-escape & spoofing rejection.
"""

import hashlib
import json
import os
import shutil
class raises:
    """Standalone context manager for exception assertion compatible with pytest.raises."""
    def __init__(self, expected_exc):
        self.expected_exc = expected_exc
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected {self.expected_exc.__name__} but no exception was raised.")
        if not issubclass(exc_type, self.expected_exc):
            return False
        self.value = exc_val
        return True


try:
    import pytest
except ImportError:
    pytest = None

from fase0.autonomous.authority import AuthorityEngine, PathAuthorityDenied
from fase0.autonomous.cost_accounting import (
    CodexEntitlementBudget,
    CodexEntitlementBudgetExceeded
)
from fase0.autonomous.provider_transport import (
    CodexProviderTransport,
    ModelRouteUnavailable,
    ProviderRequest,
    ProviderResponse
)
from fase0.autonomous.task_workspace import (
    StagedWorkspace,
    TaskWorkspaceEscapeError,
    TaskWorkspaceManager
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRATCH_DIR = os.path.join(REPO_ROOT, "fase0", "scratch")
PASS_B_RUN_DIR = os.path.join(
    REPO_ROOT,
    "fase0",
    "reality_corpus",
    "pass_b_runs",
    "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
)


if pytest is not None:
    @pytest.fixture(autouse=True)
    def setup_scratch():
        os.makedirs(SCRATCH_DIR, exist_ok=True)
        yield



# ==============================================================================
# TEST A: CODEX WORKING DIRECTORY IS ISOLATED FROM REPO ROOT
# ==============================================================================
def test_a_codex_working_directory_isolated():
    mgr = TaskWorkspaceManager(SCRATCH_DIR, REPO_ROOT)
    staged = mgr.stage_workspace(
        request_id="TEST_ISO_01",
        task_packet_dict={"task_id": "T01", "campaign_id": "TEST_CAMP"}
    )
    assert os.path.exists(staged.workspace_dir)
    assert staged.workspace_dir != REPO_ROOT
    assert staged.workspace_dir.startswith(os.path.join(SCRATCH_DIR, "codex_worker_runs"))
    assert os.path.isdir(staged.input_dir)
    assert os.path.isdir(staged.authorized_artifacts_dir)
    assert os.path.isdir(staged.output_dir)
    assert os.path.isfile(staged.packet_path)
    assert os.path.isfile(staged.manifest_path)
    assert os.path.isfile(staged.schema_path)


# ==============================================================================
# TEST B: UNAUTHORIZED CANARY FILE IS NOT PART OF CONTEXT MANIFEST
# ==============================================================================
def test_b_unauthorized_canary_not_in_context_manifest():
    mgr = TaskWorkspaceManager(SCRATCH_DIR, REPO_ROOT)
    canary_path = os.path.join(SCRATCH_DIR, "codex_isolation_secret_canary.txt")
    with open(canary_path, "w", encoding="utf-8") as f:
        f.write("CANARY_TOKEN_9999_FORBIDDEN_LEAK")

    auth_file = os.path.join(SCRATCH_DIR, "auth_allowed.txt")
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write("AUTHORIZED_DATA_ONLY")

    staged = mgr.stage_workspace(
        request_id="TEST_CANARY_02",
        task_packet_dict={"task_id": "T02"},
        authorized_files=[auth_file]
    )

    with open(staged.manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Manifest must contain auth file but NOT canary
    assert "auth_allowed.txt" in manifest["authorized_files"]
    assert "codex_isolation_secret_canary.txt" not in manifest["authorized_files"]
    assert "CANARY_TOKEN_9999_FORBIDDEN_LEAK" not in json.dumps(manifest)

    # Canary file must NOT be present in staged input dir or workspace
    assert not os.path.exists(os.path.join(staged.input_dir, "codex_isolation_secret_canary.txt"))
    assert not os.path.exists(os.path.join(staged.workspace_dir, "codex_isolation_secret_canary.txt"))


# ==============================================================================
# TEST C: SYMLINK-BASED CONTEXT ESCAPE REJECTED
# ==============================================================================
def test_c_symlink_context_escape_rejected():
    mgr = TaskWorkspaceManager(SCRATCH_DIR, REPO_ROOT)
    target_file = os.path.join(SCRATCH_DIR, "sensitive_target.txt")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("HIGHLY_SENSITIVE")

    symlink_path = os.path.join(SCRATCH_DIR, "malicious_symlink.txt")
    if os.path.islink(symlink_path) or os.path.exists(symlink_path):
        os.remove(symlink_path)
    os.symlink(target_file, symlink_path)

    with raises(TaskWorkspaceEscapeError) as exc_info:
        mgr.stage_workspace(
            request_id="TEST_SYMLINK_03",
            task_packet_dict={"task_id": "T03"},
            authorized_files=[symlink_path]
        )
    assert "SYMLINK_ESCAPE_REJECTED" in str(exc_info.value)


# ==============================================================================
# TEST D: SEMANTIC PROVIDER SPOOF IGNORED
# ==============================================================================
def test_d_semantic_provider_spoof_ignored():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T04",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    # In transport.send, even if the model semantic JSON returns "provider": "ROGUE_PROVIDER",
    # the normalized ProviderResponse and parsed_response must strictly remain "CODEX_CLI".
    # We verify this via mock stdout simulation of Codex JSON stream:
    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-123"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"provider\\": \\"ROGUE_PROVIDER\\", \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 0}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.provider == "CODEX_CLI"
        assert resp.parsed_response["provider"] == "CODEX_CLI"
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST E: SEMANTIC MODEL_ID SPOOF IGNORED
# ==============================================================================
def test_e_semantic_model_id_spoof_ignored():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T05",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-456"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"model_id\\": \\"gpt-4-hyper-spoofed\\", \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 0}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.model_id == "gpt-5.6-luna"
        assert resp.parsed_response["model_id"] == "gpt-5.6-luna"
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST F: SEMANTIC REQUEST_ID SPOOF IGNORED
# ==============================================================================
def test_f_semantic_request_id_spoof_ignored():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T06",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-real-789"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"request_id\\": \\"FORGED_REQ_111\\", \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 0}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.provider_request_id == "thread-real-789"
        assert resp.parsed_response["request_id"] == "thread-real-789"
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST G: SEMANTIC TOKEN-COUNT SPOOF IGNORED
# ==============================================================================
def test_g_semantic_token_count_spoof_ignored():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T07",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-tok-01"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"input_tokens\\": 1, \\"output_tokens\\": 1, \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 9999, "output_tokens": 4444, "cached_input_tokens": 120}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.input_tokens == 9999
        assert resp.output_tokens == 4444
        assert resp.cached_input_tokens == 120
        assert resp.parsed_response["input_tokens"] == 9999
        assert resp.parsed_response["output_tokens"] == 4444
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST H: TRUSTED USAGE COMES FROM TURN.COMPLETED
# ==============================================================================
def test_h_trusted_usage_from_turn_completed():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T08",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-h"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"assistant_output\\": \\"done\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 3500, "output_tokens": 820, "cached_input_tokens": 500}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.input_tokens == 3500
        assert resp.output_tokens == 820
        assert resp.cached_input_tokens == 500
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST I: MALFORMED SEMANTIC PAYLOAD FAILS CLOSED
# ==============================================================================
def test_i_malformed_semantic_payload_fails_closed():
    budget = CodexEntitlementBudget()
    transport = CodexProviderTransport(entitlement_budget=budget)

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T09",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    # Malformed non-JSON output
    fake_stream = (
        '{"type": "thread.started", "thread_id": "thread-mal"}\n'
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "INVALID NOT JSON AT ALL <<>>"}}\n'
        '{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 0}}\n'
    )

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=fake_stream, stderr="")
        resp = transport.send(req)
        assert resp.parsed_response["status"] == "UNRESOLVED"
        assert resp.parsed_response["error"] is not None
        assert "Malformed model JSON" in resp.parsed_response["error"]
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST J: NATIVE OUTPUT SCHEMA USED WHEN SUPPORTED
# ==============================================================================
def test_j_native_output_schema_used_when_supported():
    transport = CodexProviderTransport(native_output_schema="YES")
    assert transport.native_output_schema == "YES"

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T10",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    captured_cmd = []

    def mock_run(cmd, *args, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='{"type": "thread.started", "thread_id": "t1"}\n{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n{"type": "turn.completed", "usage": {}}\n', stderr="")

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = mock_run
        transport.send(req)
        assert "--output-schema" in captured_cmd
        idx = captured_cmd.index("--output-schema")
        assert captured_cmd[idx + 1].endswith("schema.json")
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST K: STRICT FALLBACK VALIDATED WHEN NATIVE SCHEMA UNAVAILABLE
# ==============================================================================
def test_k_strict_fallback_when_native_schema_unavailable():
    transport = CodexProviderTransport(native_output_schema="NO_WITH_STRICT_FALLBACK")
    assert transport.native_output_schema == "NO_WITH_STRICT_FALLBACK"

    req = ProviderRequest(
        campaign_id="CAMP01",
        task_id="T11",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="sha_p",
        task_packet_sha="sha_t",
        context_manifest_sha="sha_m",
        tool_policy_sha="sha_pol",
        budget_remaining={},
        messages=[{"role": "user", "content": "test"}]
    )

    captured_cmd = []

    def mock_run(cmd, *args, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='{"type": "thread.started", "thread_id": "t1"}\n{"type": "item.completed", "item": {"type": "agent_message", "text": "{\\"status\\": \\"SUCCESS\\", \\"assistant_output\\": \\"ok\\", \\"structured_output\\": null, \\"tool_requests\\": [], \\"evidence_summary\\": []}"}}\n{"type": "turn.completed", "usage": {}}\n', stderr="")

    import subprocess
    orig_run = subprocess.run
    try:
        subprocess.run = mock_run
        transport.send(req)
        # --output-schema must NOT be present when native schema is set to fallback
        assert "--output-schema" not in captured_cmd
    finally:
        subprocess.run = orig_run


# ==============================================================================
# TEST L: SUBSCRIPTION TOKEN/REQUEST BUDGET INCREMENTS & BLOCKS
# ==============================================================================
def test_l_subscription_budget_increments():
    budget = CodexEntitlementBudget(max_requests=2, max_input_tokens=5000, max_output_tokens=1000, max_wall_time_seconds=30.0)

    # First request
    budget.check_pre_dispatch(estimated_input_tokens=1000)
    budget.record_usage(input_tokens=2000, output_tokens=400, wall_time_seconds=5.0)

    stats = budget.to_dict()
    assert stats["CODEX_REQUEST_BUDGET"]["used"] == 1
    assert stats["CODEX_REQUEST_BUDGET"]["remaining"] == 1
    assert stats["CODEX_INPUT_TOKEN_BUDGET"]["used"] == 2000
    assert stats["CODEX_INPUT_TOKEN_BUDGET"]["remaining"] == 3000
    assert stats["CODEX_OUTPUT_TOKEN_BUDGET"]["used"] == 400
    assert stats["CODEX_OUTPUT_TOKEN_BUDGET"]["remaining"] == 600
    assert stats["API_COST_USD"] == 0.0

    # Second request
    budget.check_pre_dispatch(estimated_input_tokens=1000)
    budget.record_usage(input_tokens=2500, output_tokens=500, wall_time_seconds=6.0)

    # Third request must breach request ceiling
    with raises(CodexEntitlementBudgetExceeded) as exc_info:
        budget.check_pre_dispatch(estimated_input_tokens=500)
    assert "CODEX_REQUEST_BUDGET_EXCEEDED" in str(exc_info.value)


# ==============================================================================
# TEST M: MODEL ROUTE UNAVAILABLE DOES NOT SILENTLY SUBSTITUTE
# ==============================================================================
def test_m_model_route_unavailable_no_silent_substitute():
    transport = CodexProviderTransport()

    # Verified routes succeed
    assert transport.resolve_model_route("gpt-5.6-luna") == "gpt-5.6-luna"
    assert transport.resolve_model_route("gpt-5.6-terra") == "gpt-5.6-terra"
    assert transport.resolve_model_route("gpt-5.6-sol") == "gpt-5.6-sol"
    assert transport.resolve_model_route("ROUTINE_WORKER") == "gpt-5.6-luna"

    # Unauthorized model must raise ModelRouteUnavailable and NOT silently fallback
    with raises(ModelRouteUnavailable) as exc_info:
        transport.resolve_model_route("gpt-4o-unknown")
    assert "MODEL_ROUTE_UNAVAILABLE" in str(exc_info.value)
    assert "Silent substitution is prohibited" in str(exc_info.value)


# ==============================================================================
# TEST N: TOOL REQUEST PASSES THROUGH AUTHORITY ENGINE
# ==============================================================================
def test_n_tool_request_passes_through_authority_engine():
    authority = {
        "allowed_paths": ["fase0/scratch"],
        "forbidden_paths": ["docs", ".git", "secrets"],
        "allowed_commands": []
    }
    auth_engine = AuthorityEngine(authority, workspace_root=REPO_ROOT)

    # Valid write inside allowed boundary
    valid_path = auth_engine.validate_write_path("fase0/scratch/output/report.txt")
    assert valid_path.endswith("fase0/scratch/output/report.txt")

    # Unauthorized write targeting sensitive directory
    with raises(PathAuthorityDenied) as exc_info:
        auth_engine.validate_write_path("docs/CANONICAL.md")
    assert "PATH_AUTHORITY_DENIED" in str(exc_info.value)

    # Unauthorized write with path traversal
    with raises(PathAuthorityDenied):
        auth_engine.validate_write_path("../../../etc/passwd")


# ==============================================================================
# TEST O: AG277 CANONICAL INTEGRITY PRESERVED
# ==============================================================================
def test_o_ag277_unchanged():
    results_dir = os.path.join(PASS_B_RUN_DIR, "results")
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126",
    }

    for fname, exp_hash in expected_hashes.items():
        fpath = os.path.join(results_dir, fname)
        assert os.path.exists(fpath), f"AG277 canonical result {fname} missing!"
        with open(fpath, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert actual_hash == exp_hash, f"AG277 canonical result {fname} corrupted! Hash mismatch."

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    assert os.path.exists(ledger_path)
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3, f"Expected 3 ledger lines, found {len(lines)}"


if __name__ == "__main__":
    tests = [
        test_a_codex_working_directory_isolated,
        test_b_unauthorized_canary_not_in_context_manifest,
        test_c_symlink_context_escape_rejected,
        test_d_semantic_provider_spoof_ignored,
        test_e_semantic_model_id_spoof_ignored,
        test_f_semantic_request_id_spoof_ignored,
        test_g_semantic_token_count_spoof_ignored,
        test_h_trusted_usage_from_turn_completed,
        test_i_malformed_semantic_payload_fails_closed,
        test_j_native_output_schema_used_when_supported,
        test_k_strict_fallback_when_native_schema_unavailable,
        test_l_subscription_budget_increments,
        test_m_model_route_unavailable_no_silent_substitute,
        test_n_tool_request_passes_through_authority_engine,
        test_o_ag277_unchanged
    ]
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    passed = 0
    for t in tests:
        print(f"RUNNING {t.__name__}...")
        t()
        passed += 1
        print(f"PASSED {t.__name__} [{passed}/{len(tests)}]")
    print(f"\nALL {passed}/{len(tests)} ADVERSARIAL TESTS A-O PASSED CONSERVATIVELY AND DETERMINISTICALLY!")
