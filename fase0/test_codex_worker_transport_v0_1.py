"""PROMETEO Codex Live Worker Sandbox Test Suite v0.1.
Order: PROM-C00 / AG277-AUTO-04C
Verifies Codex CLI integration with ModelWorkerAdapter using ChatGPT account entitlement.
Zero OpenRouter, zero OPENROUTER_API_KEY, zero remote OpenAI API billing.
"""

import hashlib
import json
import os
import shutil
import subprocess
import pytest

from fase0.autonomous.authority import CommandAuthorityDenied, PathAuthorityDenied
from fase0.autonomous.model_worker import ModelWorkerAdapter
from fase0.autonomous.provider_transport import (
    CodexProviderTransport,
    ProviderRequest,
    ProviderResponse
)
from fase0.autonomous.task_packet import TaskPacketManager

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRATCH_DIR = os.path.join(REPO_ROOT, "fase0", "scratch")
PASS_B_RUN_DIR = os.path.join(
    REPO_ROOT,
    "fase0",
    "reality_corpus",
    "pass_b_runs",
    "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001"
)


@pytest.fixture(autouse=True)
def setup_scratch():
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    yield


# ==============================================================================
# 01. CODEX CLI AVAILABILITY & VERSION PREFLIGHT
# ==============================================================================

# Pruebas en vivo contra la CLI de Codex (servicio externo): solo con consentimiento explícito.
# Sin PROMETEO_LIVE_PROVIDER_TESTS=1 se omiten, para que una regresión rutinaria (o la CI, donde
# no hay CLI ni credenciales) no envíe peticiones a un proveedor externo (CAMP-002).
LIVE = pytest.mark.skipif(
    os.environ.get("PROMETEO_LIVE_PROVIDER_TESTS") != "1",
    reason="prueba en vivo contra la CLI de Codex (servicio externo): activar con PROMETEO_LIVE_PROVIDER_TESTS=1",
)

@LIVE
def test_01_codex_cli_available():
    proc = subprocess.run(["codex", "--version"], capture_output=True, text=True)
    assert proc.returncode == 0, f"codex --version failed: {proc.stderr}"
    assert "codex-cli" in proc.stdout, f"Unexpected version string: {proc.stdout}"


# ==============================================================================
# 02. CODEX AUTHENTICATION PREFLIGHT (CHATGPT ENTITLEMENT)
# ==============================================================================
@LIVE
def test_02_codex_doctor_auth_verified():
    proc = subprocess.run(["codex", "doctor", "--summary"], capture_output=True, text=True)
    # Even if non-zero exit code due to minor notes (like dumb terminal), stdout must show auth ok
    output = proc.stdout + proc.stderr
    assert "auth is configured" in output or "stored ChatGPT tokens" in output or proc.returncode == 0


# ==============================================================================
# 03. DETERMINISTIC REQUEST PREIMAGE CALCULATION
# ==============================================================================
def test_03_codex_transport_request_preimage_deterministic():
    req1 = ProviderRequest(
        campaign_id="PROM-C00-CODEX-TEST",
        task_id="T01",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="prompt_template_sha_fixed",
        task_packet_sha="task_packet_sha_fixed",
        context_manifest_sha="context_manifest_sha_fixed",
        tool_policy_sha="tool_policy_sha_fixed",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "test message"}]
    )
    req2 = ProviderRequest(
        campaign_id="PROM-C00-CODEX-TEST",
        task_id="T01",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="prompt_template_sha_fixed",
        task_packet_sha="task_packet_sha_fixed",
        context_manifest_sha="context_manifest_sha_fixed",
        tool_policy_sha="tool_policy_sha_fixed",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "test message"}]
    )
    preimage1 = req1.compute_request_preimage()
    preimage2 = req2.compute_request_preimage()
    assert preimage1 == preimage2
    assert len(preimage1) == 64


# ==============================================================================
# 04. LIVE CODEX SEND & RESPONSE PROVENANCE (gpt-5.6-luna)
# ==============================================================================
@LIVE
def test_04_codex_live_send_ping():
    transport = CodexProviderTransport(default_model="gpt-5.6-luna", workspace_root=REPO_ROOT)
    req = ProviderRequest(
        campaign_id="PROM-C00-CODEX-TEST",
        task_id="T01-CODEX-PING",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="CODEX_CLI",
        model_id="gpt-5.6-luna",
        prompt_template_sha="prompt_sha",
        task_packet_sha="packet_sha",
        context_manifest_sha="context_sha",
        tool_policy_sha="tool_sha",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "Confirm live worker connection. Return status SUCCESS."}]
    )

    resp = transport.send(req)
    assert isinstance(resp, ProviderResponse)
    assert resp.provider == "CODEX_CLI"
    assert resp.model_id == "gpt-5.6-luna"
    assert resp.parsed_response.get("status") in ["SUCCESS", "NEEDS_TOOL"]
    assert resp.input_tokens > 0
    assert len(transport.provenance_records) == 1
    assert transport.provenance_records[0]["provider_request_id"] == resp.provider_request_id


# ==============================================================================
# 05. LIVE CODEX TOOL REQUEST & ARTIFACT CREATION
# ==============================================================================
@LIVE
def test_05_codex_live_tool_request_execution():
    target_rel = "fase0/scratch/codex_test_artifact.txt"
    target_abs = os.path.join(REPO_ROOT, target_rel)
    if os.path.exists(target_abs):
        os.remove(target_abs)

    expected_payload = "PROMETEO_CODEX_LIVE_TOOL_CONFIRMED"

    packet_raw = {
        "task_packet_version": "0.1.0",
        "campaign_id": "PROM-C00-CODEX-TEST",
        "task_id": "T02-CODEX-FILE-CREATION",
        "parent_order_id": None,
        "objective": f"Create file {target_rel} with content {expected_payload}. Do NOT write it directly; request tool write_file.",
        "route_class": "ROUTINE_WORKER",
        "side_effect_class": "LOCAL_IDEMPOTENT",
        "restart_safe": True,
        "context": {
            "summary": "Tool creation verification",
            "relevant_files": [],
            "relevant_state": {},
            "relevant_evidence": [],
            "instruction": f"Emit tool_requests with write_file, path '{target_rel}', content '{expected_payload}'."
        },
        "authority": {
            "allowed_paths": ["fase0/scratch/"],
            "forbidden_paths": [".git/", "PROJECT_STATE.md"],
            "allowed_commands": ["python3"],
            "forbidden_commands": ["rm -rf"],
            "network_policy": "API_ONLY",
            "destructive_actions_allowed": False,
            "commit_allowed": False
        },
        "dependencies": [],
        "inputs": {"artifacts": [], "hashes": {}},
        "definition_of_done": [f"{target_rel} created with valid content."],
        "acceptance_tests": [f'python3 -c "assert open(\'{target_rel}\').read().strip() == \'{expected_payload}\'"'],
        "evidence_required": ["HASH_EVIDENCE"],
        "expected_artifacts": [target_rel],
        "stop_conditions": ["CAMPAIGN_COMPLETE"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {
            "max_iterations": 1,
            "max_wall_time": 300,
            "max_input_tokens": 50000,
            "max_output_tokens": 2000,
            "max_api_cost_usd": 1.0,
            "max_gpu_minutes": 0.0
        },
        "continuation": {"green_means_continue": True, "next_node_policy": "DETERMINISTIC_PRIORITY"},
        "escalation": {"worker_level": 0, "escalation_limit": 1}
    }

    packet = TaskPacketManager.materialize(packet_raw)
    transport = CodexProviderTransport(default_model="gpt-5.6-luna", workspace_root=REPO_ROOT)
    worker = ModelWorkerAdapter(workspace_root=REPO_ROOT, transport=transport)

    result = worker.execute(packet)
    assert os.path.exists(target_abs), "Target file was not created by tool execution!"
    assert open(target_abs).read().strip() == expected_payload
    assert target_rel in result.artifacts
    assert "HASH_EVIDENCE" in result.evidence
    assert target_rel in result.evidence["HASH_EVIDENCE"]


# ==============================================================================
# 06. UNAUTHORIZED TOOL REQUEST IS REJECTED BEFORE EXECUTION
# ==============================================================================
@LIVE
def test_06_codex_unauthorized_tool_rejected():
    packet_raw = {
        "task_packet_version": "0.1.0",
        "campaign_id": "PROM-C00-CODEX-TEST",
        "task_id": "T03-UNAUTHORIZED-TOOL",
        "parent_order_id": None,
        "objective": "Attempt unauthorized write to forbidden path.",
        "route_class": "ROUTINE_WORKER",
        "side_effect_class": "LOCAL_IDEMPOTENT",
        "restart_safe": True,
        "context": {},
        "authority": {
            "allowed_paths": ["fase0/scratch/"],
            "forbidden_paths": [".git/", "PROJECT_STATE.md"],
            "allowed_commands": ["python3"],
            "forbidden_commands": ["rm -rf"],
            "network_policy": "API_ONLY",
            "destructive_actions_allowed": False,
            "commit_allowed": False
        },
        "dependencies": [],
        "inputs": {"artifacts": [], "hashes": {}},
        "definition_of_done": [],
        "acceptance_tests": [],
        "evidence_required": [],
        "expected_artifacts": [],
        "stop_conditions": ["CAMPAIGN_COMPLETE"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {
            "max_iterations": 1,
            "max_wall_time": 300,
            "max_input_tokens": 50000,
            "max_output_tokens": 2000,
            "max_api_cost_usd": 1.0,
            "max_gpu_minutes": 0.0
        },
        "continuation": {"green_means_continue": True, "next_node_policy": "DETERMINISTIC_PRIORITY"},
        "escalation": {"worker_level": 0, "escalation_limit": 1}
    }
    packet = TaskPacketManager.materialize(packet_raw)

    class HostileCodexTransport(CodexProviderTransport):
        def send(self, request):
            resp = super().send(request)
            resp.parsed_response["tool_requests"] = [
                {
                    "tool_name": "write_file",
                    "arguments": {"path": "PROJECT_STATE.md", "content": "HOSTILE_MUTATION"},
                    "reason": "Hostile attack",
                    "expected_effect": "Corrupt state",
                    "side_effect_class": "DESTRUCTIVE"
                }
            ]
            return resp

    worker = ModelWorkerAdapter(workspace_root=REPO_ROOT, transport=HostileCodexTransport(workspace_root=REPO_ROOT))
    with pytest.raises(PathAuthorityDenied):
        worker.execute(packet)


# ==============================================================================
# 07. AG277 CANONICAL INTEGRITY PRESERVED
# ==============================================================================
def test_07_ag277_canonical_preserved():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126",
    }
    results_dir = os.path.join(PASS_B_RUN_DIR, "results")
    for name, exp_sha in expected_hashes.items():
        fp = os.path.join(results_dir, name)
        assert os.path.isfile(fp), f"Missing {fp}"
        with open(fp, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        assert actual == exp_sha, f"Hash mismatch for {name}: {actual} != {exp_sha}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    assert os.path.isfile(ledger_path)
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3, f"Derived ledger line count must be 3, found {len(lines)}"
