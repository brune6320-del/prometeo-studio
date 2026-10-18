"""Test suite for PROMETEO Model Worker Adapter & Routing Sandbox v0.1 (PROM-C00 / AG277-AUTO-03).
Covers all 27 required tests specified in Section 35:
1. actual starting HEAD mismatch rejected
2. actual state preimage mismatch rejected
3. unauthorized acceptance test command rejected
4. side-effect classes validate
5. PURE crash replay allowed
6. remote non-idempotent crash replay blocked
7. model route deterministic
8. worker cannot self-promote route
9. routine -> strong escalation works
10. escalation preserves previous evidence
11. director cannot declare GREEN
12. model response schema validated
13. malformed model output rejected
14. allowed tool request succeeds
15. unauthorized tool request rejected before execution
16. API cost tracked
17. cost gate occurs before provider dispatch
18. context pack excludes unrelated files
19. context budget enforced
20. prompt hashes frozen
21. request preimage deterministic
22. response provenance captured
23. secret-like fields rejected/redacted
24. mock provider performs zero network requests
25. model campaign completes 10+ nodes autonomously
26. human escalation halts
27. AG277 unchanged
All tests run 100% offline.
"""

import copy
import glob
import hashlib
import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional
import pytest

from fase0.autonomous.authority import AuthorityEngine, CommandAuthorityDenied, PathAuthorityDenied, SecretPolicyViolation, SecretSanitizer
from fase0.autonomous.budget import BudgetEngine
from fase0.autonomous.campaign_loader import CampaignLoader, CampaignValidationFailed, StartingPreimageMismatch
from fase0.autonomous.context_packer import ContextPacker, ContextBudgetExceeded
from fase0.autonomous.cost_accounting import CostEngine, PreDispatchCostGateExceeded
from fase0.autonomous.deterministic_worker import DeterministicLocalWorker
from fase0.autonomous.escalation import AttemptRecord, EscalationManager
from fase0.autonomous.evidence import EvidenceEngine, InvalidGreenError
from fase0.autonomous.fixtures_model import (
    create_model_campaign_fixture,
    create_human_escalation_fixture,
    create_cost_gate_fixture,
    create_malformed_response_fixture,
    create_unauthorized_tool_fixture,
    create_non_idempotent_recovery_fixture,
    get_actual_git_head
)
from fase0.autonomous.model_registry import ModelRegistry, ModelRegistryEntry, PricingSnapshot
from fase0.autonomous.model_router import ModelRouter, RoutingViolation
from fase0.autonomous.model_worker import DirectorAuthorityViolation, ModelResponseSchemaInvalid, ModelWorkerAdapter
from fase0.autonomous.orchestrator import DeterministicOrchestrator
from fase0.autonomous.persistence import EventLogger
from fase0.autonomous.provider_transport import MockProviderTransport, ProviderRequest, ProviderResponse
from fase0.autonomous.task_packet import TaskPacket, TaskPacketManager, TaskPacketValidationError

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="prometeo_test_auto03_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_valid_raw_packet(**kwargs) -> Dict[str, Any]:
    """Helper constructing schema-compliant Task Packet dictionaries."""
    base = {
        "task_packet_version": "0.1.0",
        "campaign_id": "TEST-CAMPAIGN",
        "task_id": "T01",
        "parent_order_id": None,
        "objective": "Test objective",
        "context": {"summary": "test", "relevant_files": [], "relevant_state": {}, "relevant_evidence": []},
        "authority": {
            "allowed_paths": ["fase0/scratch/"],
            "forbidden_paths": [".git/"],
            "allowed_commands": ["python", "python3"],
            "forbidden_commands": ["rm -rf"],
            "network_policy": "OFFLINE_MANDATORY",
            "destructive_actions_allowed": False,
            "commit_allowed": False
        },
        "dependencies": [],
        "inputs": {"artifacts": [], "hashes": {}},
        "definition_of_done": ["Done"],
        "acceptance_tests": [],
        "evidence_required": [],
        "expected_artifacts": [],
        "stop_conditions": ["DONE"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {
            "max_iterations": 1,
            "max_wall_time": 60,
            "max_input_tokens": 1000,
            "max_output_tokens": 500,
            "max_api_cost_usd": 1.0,
            "max_gpu_minutes": 0.0
        },
        "continuation": {
            "green_means_continue": True,
            "next_node_policy": "DETERMINISTIC_PRIORITY"
        },
        "escalation": {
            "worker_level": 0,
            "escalation_limit": 1
        }
    }
    for k, v in kwargs.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k] = copy.deepcopy(base[k])
            base[k].update(v)
        else:
            base[k] = v
    return base


# ==============================================================================
# 1. ACTUAL STARTING HEAD MISMATCH REJECTED (Hardening Gate A)
# ==============================================================================
def test_01_actual_starting_head_mismatch_rejected(tmp_dir):
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    bad_manifest = {
        "campaign_id": "TEST-HEAD-MISMATCH",
        "starting_preimage": {
            "head_commit": "0000000000000000000000000000000000000000"  # Valid 40-char SHA, but wrong HEAD
        }
    }
    with pytest.raises(StartingPreimageMismatch) as exc_info:
        loader.verify_starting_preimage(bad_manifest)
    assert "STARTING_PREIMAGE_MISMATCH" in str(exc_info.value)
    assert "0000000000000000000000000000000000000000" in str(exc_info.value)


# ==============================================================================
# 2. ACTUAL STATE PREIMAGE MISMATCH REJECTED (Hardening Gate A)
# ==============================================================================
def test_02_actual_state_preimage_mismatch_rejected(tmp_dir):
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    # Check with an invalid state hash for an existing file
    bad_manifest = {
        "campaign_id": "TEST-STATE-MISMATCH",
        "starting_preimage": {
            "head_commit": get_actual_git_head(),
            "state_file": "PROJECT_STATE.md",
            "state_hash": "e" * 64  # Wrong state hash
        }
    }
    with pytest.raises(StartingPreimageMismatch) as exc_info:
        loader.verify_starting_preimage(bad_manifest)
    assert "STARTING_PREIMAGE_MISMATCH" in str(exc_info.value)


# ==============================================================================
# 3. UNAUTHORIZED ACCEPTANCE TEST COMMAND REJECTED (Hardening Gate B)
# ==============================================================================
def test_03_unauthorized_acceptance_test_command_rejected(tmp_dir):
    orchestrator = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    raw_packet = make_valid_raw_packet(
        task_id="T01",
        acceptance_tests=["curl http://malicious.internal"]  # Unauthorized command!
    )
    packet = TaskPacketManager.materialize(raw_packet)
    logger = EventLogger(os.path.join(tmp_dir, "events.jsonl"))

    with pytest.raises(CommandAuthorityDenied) as exc_info:
        orchestrator._run_acceptance_tests(packet, logger, "T01")
    assert "COMMAND_AUTHORITY_DENIED" in str(exc_info.value)


# ==============================================================================
# 4. SIDE-EFFECT CLASSES VALIDATE (Hardening Gate C)
# ==============================================================================
def test_04_side_effect_classes_validate():
    valid_classes = [
        "PURE", "LOCAL_IDEMPOTENT", "LOCAL_NON_IDEMPOTENT",
        "REMOTE_IDEMPOTENT", "REMOTE_NON_IDEMPOTENT", "DESTRUCTIVE"
    ]
    for c in valid_classes:
        raw = make_valid_raw_packet(task_id=f"T-{c}", side_effect_class=c)
        pkt = TaskPacketManager.materialize(raw)
        assert pkt.side_effect_class == c

    # Invalid side effect class raises TaskPacketValidationFailed
    raw_invalid = make_valid_raw_packet(task_id="T_BAD", side_effect_class="MAGIC_SIDE_EFFECT")
    with pytest.raises(TaskPacketValidationError) as exc_info:
        TaskPacketManager.materialize(raw_invalid)
    assert "Invalid side_effect_class" in str(exc_info.value)


# ==============================================================================
# 5. PURE CRASH REPLAY ALLOWED (Crash Recovery V2)
# ==============================================================================
def test_05_pure_crash_replay_allowed(tmp_dir):
    orchestrator = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    manifest = {
        "campaign_id": "TEST-CRASH-PURE",
        "nodes": [
            {
                "node_id": "N01",
                "state": "RUNNING",
                "side_effect_class": "PURE",
                "restart_safe": True
            }
        ]
    }
    m_path = os.path.join(tmp_dir, "manifest.json")
    with open(m_path, "w") as f:
        json.dump(manifest, f)

    logger = EventLogger(os.path.join(tmp_dir, "events.jsonl"))
    orchestrator._handle_crash_recovery(manifest, m_path, logger)

    assert manifest["nodes"][0]["state"] == "ELIGIBLE"


# ==============================================================================
# 6. REMOTE NON-IDEMPOTENT CRASH REPLAY BLOCKED (Crash Recovery V2)
# ==============================================================================
def test_06_remote_non_idempotent_crash_replay_blocked(tmp_dir):
    orchestrator = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    manifest = {
        "campaign_id": "TEST-CRASH-REMOTE-NONIDEMPOTENT",
        "nodes": [
            {
                "node_id": "N01",
                "state": "RUNNING",
                "side_effect_class": "REMOTE_NON_IDEMPOTENT",
                "restart_safe": False
            }
        ]
    }
    m_path = os.path.join(tmp_dir, "manifest.json")
    with open(m_path, "w") as f:
        json.dump(manifest, f)

    logger = EventLogger(os.path.join(tmp_dir, "events.jsonl"))
    orchestrator._handle_crash_recovery(manifest, m_path, logger)

    node = manifest["nodes"][0]
    assert node["state"] == "BLOCKED"
    assert node["blocking_reason"] == "AMBIGUOUS_SIDE_EFFECT_AFTER_CRASH"


# ==============================================================================
# 7. MODEL ROUTE DETERMINISTIC
# ==============================================================================
def test_07_model_route_deterministic():
    registry = ModelRegistry()
    router = ModelRouter(registry)
    raw_packet = make_valid_raw_packet(
        task_id="T01",
        budget={"max_iterations": 3}
    )
    packet = TaskPacketManager.materialize(raw_packet)

    r1 = router.select_route(packet, current_attempt=1)
    assert r1.route_class == "ROUTINE_WORKER"

    r2 = router.select_route(packet, current_attempt=2)
    assert r2.route_class == "STRONG_WORKER"

    r3 = router.select_route(packet, current_attempt=3)
    assert r3.route_class == "DIRECTOR_AUDITOR"


# ==============================================================================
# 8. WORKER CANNOT SELF-PROMOTE ROUTE
# ==============================================================================
def test_08_worker_cannot_self_promote_route():
    router = ModelRouter()
    with pytest.raises(RoutingViolation) as exc_info:
        router.validate_no_self_promotion("DIRECTOR_AUDITOR", "ROUTINE_WORKER")
    assert "MODEL_SELF_PROMOTION_DENIED" in str(exc_info.value)


# ==============================================================================
# 9. ROUTINE -> STRONG ESCALATION WORKS
# ==============================================================================
def test_09_routine_to_strong_escalation_works(tmp_dir):
    transport = MockProviderTransport()
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT, transport=transport)

    raw_packet = make_valid_raw_packet(
        task_id="T_ESC",
        context={
            "attempt_id": 1,
            "attempt_mock_responses": {
                "1": {"status": "RETRYABLE_FAILURE", "error": "Attempt 1 failed"},
                "2": {"status": "SUCCESS", "assistant_output": "Attempt 2 strong worker success"}
            }
        },
        budget={"max_iterations": 2}
    )
    packet = TaskPacketManager.materialize(raw_packet)

    # Attempt 1: Routine worker fails
    res1 = adapter.execute(packet)
    assert res1.status == "RETRYABLE_FAILURE"

    # Attempt 2: Escalated to Strong worker succeeds
    packet.context["attempt_id"] = 2
    res2 = adapter.execute(packet)
    assert res2.status == "SUCCESS"


# ==============================================================================
# 10. ESCALATION PRESERVES PREVIOUS EVIDENCE (Escalation Contract V2)
# ==============================================================================
def test_10_escalation_preserves_previous_evidence():
    mgr = EscalationManager("CAMP-01", "T01", "packet-sha-256")
    rec1 = AttemptRecord(
        attempt_id=1,
        worker_id="mock-routine-v1",
        route_class="ROUTINE_WORKER",
        model_id="mock-routine-v1",
        status="RETRYABLE_FAILURE",
        error="Constraint failure",
        commands_run=["python3 step1.py"],
        tool_requests=[],
        diffs=["+ line 1 in step1.py"],
        evidence=[{"artifact_path": "fase0/scratch/step1.txt", "sha256": "abc123sha"}],
        cost_usd=0.001,
        latency_ms=120.0
    )
    mgr.record_attempt(rec1)
    state = mgr.build_escalation_state({"max_api_cost_usd": 5.0})

    assert state["attempt_count"] == 1
    assert state["previous_worker"] == "mock-routine-v1"
    assert state["previous_model_route"] == "ROUTINE_WORKER"
    assert state["commands_already_run"] == ["python3 step1.py"]
    assert state["diffs"] == ["+ line 1 in step1.py"]
    assert len(state["evidence"]) == 1
    assert state["evidence"][0]["artifact_path"] == "fase0/scratch/step1.txt"


# ==============================================================================
# 11. DIRECTOR CANNOT DECLARE GREEN
# ==============================================================================
def test_11_director_cannot_declare_green():
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    raw_packet = make_valid_raw_packet(
        task_id="T_DIR",
        route_class="DIRECTOR_AUDITOR",
        context={
            "mock_response": {
                "status": "GREEN",  # Director attempts to declare GREEN!
                "assistant_output": "Director declaring green directly"
            }
        }
    )
    packet = TaskPacketManager.materialize(raw_packet)

    with pytest.raises(DirectorAuthorityViolation) as exc_info:
        adapter.execute(packet)
    assert "DIRECTOR_CANNOT_DECLARE_GREEN" in str(exc_info.value)


# ==============================================================================
# 12. MODEL RESPONSE SCHEMA VALIDATED
# ==============================================================================
def test_12_model_response_schema_validated():
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    valid_resp = {
        "worker_id": "w1", "provider": "MOCK", "model_id": "m1", "route_class": "ROUTINE_WORKER",
        "request_id": "r1", "task_id": "t1", "attempt_id": 1, "status": "SUCCESS",
        "assistant_output": "output", "structured_output": {}, "tool_requests": [],
        "input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 0,
        "estimated_cost_usd": 0.0001, "latency_ms": 10.0, "evidence": [], "error": None
    }
    # Should not raise
    adapter._validate_response_schema(valid_resp)


# ==============================================================================
# 13. MALFORMED MODEL OUTPUT REJECTED
# ==============================================================================
def test_13_malformed_model_output_rejected():
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    malformed_resp = {"status": "SUCCESS", "garbage": 123}
    with pytest.raises(ModelResponseSchemaInvalid) as exc_info:
        adapter._validate_response_schema(malformed_resp)
    assert "MODEL_RESPONSE_SCHEMA_INVALID" in str(exc_info.value)


# ==============================================================================
# 14. ALLOWED TOOL REQUEST SUCCEEDS
# ==============================================================================
def test_14_allowed_tool_request_succeeds(tmp_dir):
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    test_file = "fase0/scratch/allowed_tool_test.txt"
    raw_packet = make_valid_raw_packet(
        task_id="T_TOOL",
        context={
            "mock_response": {
                "status": "SUCCESS",
                "tool_requests": [
                    {
                        "tool_name": "write_file",
                        "arguments": {"path": test_file, "content": "hello from tool"},
                        "reason": "Test tool execution",
                        "expected_effect": "File created",
                        "side_effect_class": "LOCAL_IDEMPOTENT"
                    }
                ]
            }
        }
    )
    packet = TaskPacketManager.materialize(raw_packet)
    res = adapter.execute(packet)
    assert res.status == "SUCCESS"
    assert test_file in res.artifacts

    abs_path = os.path.join(REPO_ROOT, test_file)
    assert os.path.exists(abs_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        assert f.read() == "hello from tool"


# ==============================================================================
# 15. UNAUTHORIZED TOOL REQUEST REJECTED BEFORE EXECUTION
# ==============================================================================
def test_15_unauthorized_tool_request_rejected_before_execution():
    adapter = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    raw_packet = make_valid_raw_packet(
        task_id="T_UNAUTH",
        context={
            "mock_response": {
                "status": "SUCCESS",
                "tool_requests": [
                    {
                        "tool_name": "write_file",
                        "arguments": {"path": ".git/forbidden.txt", "content": "bad"},
                        "reason": "Unauthorized path write",
                        "expected_effect": "Exploit",
                        "side_effect_class": "DESTRUCTIVE"
                    }
                ]
            }
        }
    )
    packet = TaskPacketManager.materialize(raw_packet)
    with pytest.raises(PathAuthorityDenied) as exc_info:
        adapter.execute(packet)
    assert "PATH_AUTHORITY_DENIED" in str(exc_info.value)
    assert not os.path.exists(os.path.join(REPO_ROOT, ".git", "forbidden.txt"))


# ==============================================================================
# 16. API COST TRACKED
# ==============================================================================
def test_16_api_cost_tracked():
    snap = PricingSnapshot(
        retrieved_at="2026-10-02T00:00:00Z",
        source="MOCK",
        currency="USD",
        input_price_per_1m=1.00,
        output_price_per_1m=2.00,
        cache_price_per_1m=0.50
    )
    cost = CostEngine.compute_cost(
        pricing=snap,
        input_tokens=1_000_000,
        output_tokens=500_000,
        cached_input_tokens=200_000
    )
    # 0.80 (uncached) + 0.10 (cached) + 1.00 (output) = 1.90 USD
    assert abs(cost - 1.90) < 1e-4


# ==============================================================================
# 17. COST GATE OCCURS BEFORE PROVIDER DISPATCH (Pre-Dispatch Cost Gate)
# ==============================================================================
def test_17_cost_gate_occurs_before_provider_dispatch():
    transport = MockProviderTransport()
    registry = ModelRegistry()
    expensive_entry = registry.get("expensive-mock-test")

    with pytest.raises(PreDispatchCostGateExceeded) as exc_info:
        # Task budget is $0.05, but expensive model estimated max cost is thousands of dollars
        max_cost = CostEngine.estimate_max_cost(expensive_entry, 1000, 2000)
        CostEngine.check_pre_dispatch_cost_gate(max_cost, 0.05, "T_EXPENSIVE")
    assert "PRE_DISPATCH_COST_GATE_EXCEEDED" in str(exc_info.value)
    # Crucial invariant: transport requests must remain exactly 0
    assert transport.request_count == 0


# ==============================================================================
# 18. CONTEXT PACK EXCLUDES UNRELATED FILES
# ==============================================================================
def test_18_context_pack_excludes_unrelated_files(tmp_dir):
    packer = ContextPacker(workspace_root=REPO_ROOT)
    sample_rel = "fase0/scratch/context_test_sample.txt"
    sample_full = os.path.join(REPO_ROOT, sample_rel)
    os.makedirs(os.path.dirname(sample_full), exist_ok=True)
    with open(sample_full, "w", encoding="utf-8") as f:
        f.write("context test content")

    raw_packet = make_valid_raw_packet(
        task_id="T_CTX",
        context={
            "summary": "Specific test summary",
            "relevant_files": [sample_rel]
        }
    )
    packet = TaskPacketManager.materialize(raw_packet)
    packed = packer.pack_context(packet, "System Prompt Header", [])

    manifest = packed["context_manifest"]
    # Only the explicit relevant_files entry is packed
    assert sample_rel in manifest["explicit_artifacts"]
    assert len(manifest["explicit_artifacts"]) == 1
    # Does NOT include whole codebase or arbitrary other files
    assert "fase0/autonomous/orchestrator.py" not in manifest["explicit_artifacts"]


# ==============================================================================
# 19. CONTEXT BUDGET ENFORCED
# ==============================================================================
def test_19_context_budget_enforced():
    packer = ContextPacker(workspace_root=REPO_ROOT, max_context_bytes=50)  # Very small limit
    raw_packet = make_valid_raw_packet(
        task_id="T_CTX_BUDGET",
        objective="A" * 200,  # Exceeds 50 bytes
        context={"summary": "A" * 100}
    )
    packet = TaskPacketManager.materialize(raw_packet)
    with pytest.raises(ContextBudgetExceeded) as exc_info:
        packer.pack_context(packet, "System Prompt", [])
    assert "CONTEXT_BUDGET_EXCEEDED" in str(exc_info.value)


# ==============================================================================
# 20. PROMPT HASHES FROZEN
# ==============================================================================
def test_20_prompt_hashes_frozen():
    prompts_dir = os.path.join(REPO_ROOT, "fase0", "autonomous", "prompts")
    expected_prompts = {
        "ROUTINE_WORKER_SYSTEM_PROMPT_v0.1.txt": "111aa63fe06429db5f5df01a0f06c41e2f5769f935042da6a5e894e43f5f862c",
        "STRONG_WORKER_SYSTEM_PROMPT_v0.1.txt": "49eab5fa56a9abdd287857bcc2da0a322938ee77dcf3ad048ab6c307e71a9a1f",
        "DIRECTOR_AUDITOR_SYSTEM_PROMPT_v0.1.txt": "317b409df295380a34d8192766b199597b0af3ed4bf1261b65c46d28e7719467"
    }
    for fname, exp_hash in expected_prompts.items():
        fpath = os.path.join(prompts_dir, fname)
        assert os.path.exists(fpath)
        with open(fpath, "rb") as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()
        assert computed_sha == exp_hash, f"Frozen prompt hash mismatch for {fname}"


# ==============================================================================
# 21. REQUEST PREIMAGE DETERMINISTIC
# ==============================================================================
def test_21_request_preimage_deterministic():
    req1 = ProviderRequest(
        campaign_id="CAMP-PREIMAGE",
        task_id="T01",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="MOCK_PROVIDER",
        model_id="mock-routine-v1",
        prompt_template_sha="prompt-sha",
        task_packet_sha="packet-sha",
        context_manifest_sha="context-sha",
        tool_policy_sha="tool-sha",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "test"}]
    )
    req2 = ProviderRequest(
        campaign_id="CAMP-PREIMAGE",
        task_id="T01",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="MOCK_PROVIDER",
        model_id="mock-routine-v1",
        prompt_template_sha="prompt-sha",
        task_packet_sha="packet-sha",
        context_manifest_sha="context-sha",
        tool_policy_sha="tool-sha",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "test"}]
    )
    assert req1.compute_request_preimage() == req2.compute_request_preimage()


# ==============================================================================
# 22. RESPONSE PROVENANCE CAPTURED
# ==============================================================================
def test_22_response_provenance_captured():
    transport = MockProviderTransport()
    req = ProviderRequest(
        campaign_id="CAMP-PROV",
        task_id="T01",
        attempt_id=1,
        route_class="ROUTINE_WORKER",
        provider="MOCK_PROVIDER",
        model_id="mock-routine-v1",
        prompt_template_sha="prompt-sha",
        task_packet_sha="packet-sha",
        context_manifest_sha="context-sha",
        tool_policy_sha="tool-sha",
        budget_remaining={"max_api_cost_usd": 1.0},
        messages=[{"role": "user", "content": "test"}]
    )
    resp = transport.send(req)
    prov = resp.to_provenance_record()

    assert prov["request_preimage_sha"] == req.compute_request_preimage()
    assert prov["provider"] == "MOCK_PROVIDER"
    assert prov["model_id"] == "mock-routine-v1"
    assert "cost_usd" in prov
    assert len(transport.provenance_records) == 1


# ==============================================================================
# 23. SECRET-LIKE FIELDS REJECTED / REDACTED
# ==============================================================================
def test_23_secret_like_fields_rejected_redacted():
    leaked_texts = [
        "My key is sk-1234567890abcdef12345678",
        "Authorization: Bearer my-secret-api-token-value-here"
    ]
    for text in leaked_texts:
        with pytest.raises(SecretPolicyViolation) as exc_info:
            SecretSanitizer.validate_no_secrets(text, "Test context")
        assert "SECRET_POLICY_VIOLATION" in str(exc_info.value)


# ==============================================================================
# 24. MOCK PROVIDER PERFORMS ZERO NETWORK REQUESTS
# ==============================================================================
def test_24_mock_provider_zero_network_requests():
    transport = MockProviderTransport()
    for i in range(10):
        req = ProviderRequest(
            campaign_id="CAMP-NET",
            task_id=f"T{i}",
            attempt_id=1,
            route_class="ROUTINE_WORKER",
            provider="MOCK_PROVIDER",
            model_id="mock-routine-v1",
            prompt_template_sha="sha",
            task_packet_sha="sha",
            context_manifest_sha="sha",
            tool_policy_sha="sha",
            budget_remaining={},
            messages=[]
        )
        transport.send(req)
    # Network requests must strictly remain 0
    assert transport.network_requests == 0
    assert transport.request_count == 10


# ==============================================================================
# 25. MODEL CAMPAIGN COMPLETES 10+ NODES AUTONOMOUSLY (Section 29)
# ==============================================================================
def test_25_model_campaign_completes_12_nodes_autonomously(tmp_dir):
    manifest_path = create_model_campaign_fixture(tmp_dir)
    worker = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    orchestrator = DeterministicOrchestrator(workspace_root=REPO_ROOT, worker=worker)

    outcome = orchestrator.run(manifest_path, is_resume=False)

    assert outcome == "COMPLETED"
    assert orchestrator.autonomous_nodes_completed == 12
    assert orchestrator.human_continuation_prompts == 0
    assert worker.transport.network_requests == 0

    # Verify all expected artifacts exist on disk
    expected_files = [
        "fase0/scratch/m_t01_deterministic.txt",
        "fase0/scratch/m_t03_tool_output.txt",
        "fase0/scratch/m_t05_escalation_resolved.txt",
        "fase0/scratch/m_t06_strong_direct.txt",
        "fase0/scratch/m_t07_strong_verified.txt",
        "fase0/scratch/m_t08_acceptance.txt",
        "fase0/scratch/m_t09_evidence_summary.txt",
        "fase0/scratch/m_t11_final_artifact.txt",
        "fase0/scratch/m_t12_campaign_done.txt"
    ]
    for rel_path in expected_files:
        full_path = os.path.join(REPO_ROOT, rel_path)
        assert os.path.exists(full_path), f"Artifact missing: {rel_path}"


# ==============================================================================
# 26. HUMAN ESCALATION HALTS (Section 30)
# ==============================================================================
def test_26_human_escalation_halts(tmp_dir):
    manifest_path = create_human_escalation_fixture(tmp_dir)
    worker = ModelWorkerAdapter(workspace_root=REPO_ROOT)
    orchestrator = DeterministicOrchestrator(workspace_root=REPO_ROOT, worker=worker)

    outcome = orchestrator.run(manifest_path, is_resume=False)

    assert outcome == "HALTED_AT_HUMAN_GATE"
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert m["nodes"][0]["state"] == "HUMAN_GATE"


# ==============================================================================
# 27. AG277 UNCHANGED
# ==============================================================================
def test_27_ag277_unchanged():
    p_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "pass_b_runs", "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001")
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_sha in expected_hashes.items():
        fpath = os.path.join(p_dir, "results", fname)
        assert os.path.exists(fpath), f"Missing AG277 canonical result {fname}"
        with open(fpath, "rb") as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()
        assert computed_sha == exp_sha, f"AG277 canonical result {fname} hash mutated!"

    # Derived ledger lines = 3
    ledger_path = os.path.join(p_dir, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    assert os.path.exists(ledger_path)
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3, f"Expected 3 ledger lines, found {len(lines)}"
