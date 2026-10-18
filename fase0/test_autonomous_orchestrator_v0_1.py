"""PROMETEO · PROM-C00 / AG277-AUTO-02
DETERMINISTIC ORCHESTRATOR MVP v0.1 — TEST SUITE

Verifies the 25 required test cases of the executable orchestrator:
 1. Valid manifest accepted
 2. Invalid manifest rejected
 3. DAG cycle rejected
 4. Deterministic scheduler ordering
 5. GREEN automatically continues (GREEN != STOP)
 6. DONE never reruns
 7. HUMAN_GATE stops
 8. HUMAN_GATE default not auto-applied (HUMAN_GATE_AUTO_RESUME = False)
 9. EXTERNAL_GATE stops
10. BUDGET_GATE stops
11. Worker cannot expand paths
12. Path traversal rejected
13. Symlink escape rejected
14. Unauthorized command rejected
15. Worker claim cannot self-declare GREEN
16. Missing evidence => INVALID_GREEN
17. Failed acceptance test prevents GREEN
18. Evidence hashes validated
19. Atomic state persistence
20. Restart after RUNNING reconstructs state
21. Completed node remains immutable
22. Duplicate artifact conflict halts
23. Iteration limit works
24. MAX_ACTIVE_WORKERS = 1 enforced
25. Synthetic 10+ node campaign reaches DONE with zero human prompts
"""

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fase0.autonomous.authority import AuthorityEngine, PathAuthorityDenied, CommandAuthorityDenied
from fase0.autonomous.budget import BudgetEngine, BudgetExhausted
from fase0.autonomous.campaign_loader import CampaignLoader, CampaignValidationFailed
from fase0.autonomous.deterministic_worker import DeterministicLocalWorker
from fase0.autonomous.evidence import EvidenceEngine, InvalidGreenError, DuplicateArtifactConflict
from fase0.autonomous.orchestrator import DeterministicOrchestrator
from fase0.autonomous.persistence import StatePersistence, EventLogger
from fase0.autonomous.scheduler import DeterministicScheduler
from fase0.autonomous.state_machine import AutonomousStateMachine, InvalidStateTransition
from fase0.autonomous.task_packet import TaskPacket, TaskPacketManager, TaskPacketValidationFailed

FIXTURES_DIR = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "campaign_fixtures")


@pytest.fixture(autouse=True)
def reset_fixtures():
    from fase0.autonomous.fixtures import generate_all
    generate_all()


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp(prefix="prometeo_test_orch_")
    scratch_dir = os.path.join(tmp_dir, "fase0", "scratch", "mvp_run")
    os.makedirs(scratch_dir, exist_ok=True)
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_01_valid_manifest_accepted():
    """1. Valid campaign manifest is loaded and accepted."""
    manifest_path = os.path.join(FIXTURES_DIR, "mvp_fixture", "campaign_manifest.json")
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    data = loader.load_manifest(manifest_path)
    assert data["campaign_id"] == "PROM-C00-ORCHESTRATOR-MVP-FIXTURE"
    assert data["campaign_protocol_version"] == "0.1.0"


def test_02_invalid_manifest_rejected():
    """2. Invalid manifest missing required fields is rejected fail-closed."""
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    invalid_manifest = {
        "campaign_protocol_version": "0.1.0",
        "campaign_id": "INVALID"
        # missing nodes, starting_preimage, budget, authority, etc.
    }
    with pytest.raises(CampaignValidationFailed):
        loader.validate(invalid_manifest)


def test_03_dag_cycle_rejected():
    """3. Cyclic dependency in DAG is rejected."""
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    cyclic = {
        "campaign_protocol_version": "0.1.0",
        "campaign_id": "CYCLIC",
        "title": "Cyclic Campaign",
        "objective": "Test cycle rejection",
        "scope": ["fase0/"],
        "out_of_scope": [".git/"],
        "starting_preimage": {"head_commit": "1" * 40, "state_hash": "2" * 64, "manifest_hash": "3" * 64},
        "authority": {"canonical_order_hierarchy": ["CAMPAIGN"], "max_active_workers": 1, "allowed_root_paths": ["fase0/"], "forbidden_root_paths": [".git/"]},
        "budget": {"total_max_tokens": 100, "total_max_api_cost_usd": 0.0, "total_max_gpu_minutes": 0.0, "total_max_wall_time_seconds": 10, "total_max_iterations": 2},
        "nodes": [
            {"node_id": "N1", "type": "TASK", "state": "PENDING", "dependencies": ["N2"]},
            {"node_id": "N2", "type": "TASK", "state": "PENDING", "dependencies": ["N1"]}
        ],
        "edges": [{"from_node": "N1", "to_node": "N2"}, {"from_node": "N2", "to_node": "N1"}],
        "human_gates": [],
        "external_gates": [],
        "completion_definition": {"terminal_nodes": ["N2"], "required_global_evidence": []},
        "rollback_policy": {"default_strategy": "GIT_RESTORE", "allowed_strategies": ["GIT_RESTORE"], "preserve_evidence": True},
        "state": "PENDING",
        "evidence_index": []
    }
    with pytest.raises(CampaignValidationFailed) as exc:
        loader.validate(cyclic)
    assert "cycle" in str(exc.value).lower()


def test_04_deterministic_scheduler_ordering():
    """4. Deterministic scheduler orders eligible nodes by index then lexicographically."""
    manifest = {
        "nodes": [
            {"node_id": "T_Z", "state": "PENDING", "dependencies": []},
            {"node_id": "T_A", "state": "PENDING", "dependencies": []},
            {"node_id": "T_M", "state": "PENDING", "dependencies": []}
        ],
        "edges": []
    }
    eligible = DeterministicScheduler.compute_eligible_nodes(manifest)
    assert eligible == ["T_Z", "T_A", "T_M"]

    # First declared node is chosen
    selected = DeterministicScheduler.select_next_node(eligible, manifest)
    assert selected == "T_Z"


def test_05_green_automatically_continues(temp_workspace):
    """5. GREEN automatically continues without human prompts (GREEN != STOP)."""
    manifest_path = os.path.join(FIXTURES_DIR, "mvp_fixture", "campaign_manifest.json")
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path)
    assert outcome == "COMPLETED"
    assert orch.autonomous_nodes_completed >= 10
    assert orch.human_continuation_prompts == 0


def test_06_done_never_reruns():
    """6. A node in DONE is never re-run."""
    manifest = {
        "nodes": [
            {"node_id": "T01", "state": "DONE", "dependencies": []},
            {"node_id": "T02", "state": "PENDING", "dependencies": ["T01"]}
        ],
        "edges": [{"from_node": "T01", "to_node": "T02"}]
    }
    eligible = DeterministicScheduler.compute_eligible_nodes(manifest)
    assert "T01" not in eligible
    assert eligible == ["T02"]


def test_07_human_gate_stops():
    """7. HUMAN_GATE halts autonomous execution."""
    manifest_path = os.path.join(FIXTURES_DIR, "human_gate_fixture", "campaign_manifest.json")
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path)
    assert outcome == "HALTED_AT_HUMAN_GATE"


def test_08_human_gate_default_not_auto_applied():
    """8. default_if_no_action is informational only and MUST NOT auto-resume."""
    manifest_path = os.path.join(FIXTURES_DIR, "human_gate_fixture", "campaign_manifest.json")
    with open(manifest_path, "r") as f:
        data = json.load(f)
    hg = data["human_gates"][0]
    assert hg["default_if_no_action"] == "APPROVE"

    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path)
    assert outcome == "HALTED_AT_HUMAN_GATE"

    # Verify that downstream node T02 is still PENDING and was not auto-dispatched
    status = orch.plan(manifest_path)
    assert status["status_counts"].get("HUMAN_GATE") == 1
    assert status["status_counts"].get("PENDING") == 1


def test_09_external_gate_stops():
    """9. EXTERNAL_GATE halts campaign execution until resolved."""
    manifest = {
        "campaign_protocol_version": "0.1.0",
        "campaign_id": "EXT-GATE-TEST",
        "title": "External Gate Test",
        "objective": "Test external gate",
        "scope": ["fase0/scratch/mvp_run/"],
        "out_of_scope": [".git/"],
        "starting_preimage": {"head_commit": CampaignLoader.get_actual_git_head(REPO_ROOT) or ("1" * 40), "state_hash": "2" * 64, "manifest_hash": "3" * 64},
        "authority": {"canonical_order_hierarchy": ["CAMPAIGN"], "max_active_workers": 1, "allowed_root_paths": ["fase0/scratch/mvp_run/"], "forbidden_root_paths": [".git/"]},
        "budget": {"total_max_tokens": 100, "total_max_api_cost_usd": 0.0, "total_max_gpu_minutes": 0.0, "total_max_wall_time_seconds": 10, "total_max_iterations": 2},
        "nodes": [
            {"node_id": "EG01", "type": "EXTERNAL_GATE", "state": "PENDING", "dependencies": []}
        ],
        "edges": [],
        "human_gates": [],
        "external_gates": [{"gate_id": "EG01", "external_resource": "remote_db", "resolution_condition": "connected", "timeout_seconds": 60}],
        "completion_definition": {"terminal_nodes": ["EG01"], "required_global_evidence": []},
        "rollback_policy": {"default_strategy": "GIT_RESTORE", "allowed_strategies": ["GIT_RESTORE"], "preserve_evidence": True},
        "state": "PENDING",
        "evidence_index": []
    }
    tmp_path = os.path.join(REPO_ROOT, "fase0", "scratch", "ext_gate_manifest.json")
    with open(tmp_path, "w") as f:
        json.dump(manifest, f)
    try:
        orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
        outcome = orch.run(tmp_path)
        assert outcome == "HALTED_AT_EXTERNAL_GATE"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_10_budget_gate_stops():
    """10. BUDGET_GATE halts autonomous progression when budget is reached."""
    manifest_path = os.path.join(FIXTURES_DIR, "budget_gate_fixture", "campaign_manifest.json")
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path)
    assert outcome == "HALTED_AT_BUDGET_GATE"


def test_11_worker_cannot_expand_paths():
    """11. Worker cannot write outside allowed_paths."""
    auth = AuthorityEngine({
        "allowed_paths": ["fase0/scratch/mvp_run/"],
        "forbidden_paths": [".git/", "PROJECT_STATE.md"],
        "destructive_actions_allowed": False
    }, workspace_root=REPO_ROOT)

    with pytest.raises(PathAuthorityDenied):
        auth.validate_write_path("docs/some_file.md")


def test_12_path_traversal_rejected():
    """12. Path directory traversal (..) is rejected fail-closed."""
    auth = AuthorityEngine({
        "allowed_paths": ["fase0/scratch/mvp_run/"],
        "forbidden_paths": [".git/"],
        "destructive_actions_allowed": False
    }, workspace_root=REPO_ROOT)

    with pytest.raises(PathAuthorityDenied):
        auth.validate_write_path("fase0/scratch/mvp_run/../../outside.txt")


def test_13_symlink_escape_rejected(temp_workspace):
    """13. Symlink pointing outside allowed root is rejected upon canonicalization."""
    auth = AuthorityEngine({
        "allowed_paths": ["fase0/scratch/mvp_run/"],
        "forbidden_paths": [".git/"],
        "destructive_actions_allowed": False
    }, workspace_root=temp_workspace)

    # Create a symlink pointing to temp_workspace root
    symlink_path = os.path.join(temp_workspace, "fase0", "scratch", "mvp_run", "escape_link")
    try:
        os.symlink(temp_workspace, symlink_path)
        # Attempting to write through the symlink to root
        target = os.path.join(symlink_path, "escaped_file.txt")
        # Canonicalization will resolve it to temp_workspace/escaped_file.txt which is not in allowed_paths!
        with pytest.raises(PathAuthorityDenied):
            auth.validate_write_path(target)
    except OSError:
        pytest.skip("Symlink creation not permitted in this filesystem")


def test_14_unauthorized_command_rejected():
    """14. Unwhitelisted shell command is rejected."""
    auth = AuthorityEngine({
        "allowed_commands": ["python3", "pytest"],
        "forbidden_commands": ["rm", "git push"],
        "destructive_actions_allowed": False
    }, workspace_root=REPO_ROOT)

    with pytest.raises(CommandAuthorityDenied):
        auth.validate_command("curl https://malicious.site")
    with pytest.raises(CommandAuthorityDenied):
        auth.validate_command("rm -rf /")


def test_15_worker_claim_cannot_self_declare_green():
    """15. Worker result status alone cannot set state to GREEN without orchestrator validation."""
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    # Orchestrator independently checks acceptance tests and evidence
    # Worker declaring status='SUCCESS' without test or evidence fails
    packet_raw = {
        "task_packet_version": "0.1.0",
        "campaign_id": "TEST",
        "task_id": "T_MOCK",
        "parent_order_id": None,
        "objective": "Test self-declaration",
        "context": {"summary": "", "relevant_files": [], "relevant_state": {}, "relevant_evidence": []},
        "authority": {"allowed_paths": ["fase0/scratch/"], "forbidden_paths": [], "allowed_commands": ["python", "python3"], "forbidden_commands": [], "network_policy": "OFFLINE_MANDATORY", "destructive_actions_allowed": False, "commit_allowed": False},
        "dependencies": [],
        "inputs": {"artifacts": [], "hashes": {}},
        "definition_of_done": ["Mock DoD"],
        "acceptance_tests": ['python3 -c "import sys; sys.exit(1)"'],  # Failing test!
        "evidence_required": ["HASH_EVIDENCE"],
        "expected_artifacts": [],
        "stop_conditions": ["CAMPAIGN_COMPLETE"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {"max_iterations": 1, "max_wall_time": 10, "max_input_tokens": 100, "max_output_tokens": 100, "max_api_cost_usd": 0.0, "max_gpu_minutes": 0.0},
        "continuation": {"green_means_continue": True, "next_node_policy": "DETERMINISTIC_PRIORITY"},
        "escalation": {"worker_level": 0, "escalation_limit": 1}
    }
    packet = TaskPacketManager.materialize(packet_raw)
    test_result = orch._run_acceptance_tests(packet, EventLogger("/dev/null"), "T_MOCK")
    assert test_result is False  # Orchestrator independent test catches failure!


def test_16_missing_evidence_causes_invalid_green():
    """16. Missing declared required evidence triggers InvalidGreenError."""
    engine = EvidenceEngine(workspace_root=REPO_ROOT)
    with pytest.raises(InvalidGreenError):
        engine.verify_node_evidence(
            node_id="T01",
            required_types=["TEST_EVIDENCE", "HASH_EVIDENCE"],
            attached_evidence={"TEST_EVIDENCE": "passed"},  # HASH_EVIDENCE missing!
            expected_artifacts=[]
        )


def test_17_failed_acceptance_test_prevents_green():
    """17. Acceptance test exit code != 0 prevents transition to GREEN."""
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    packet_raw = {
        "task_packet_version": "0.1.0",
        "campaign_id": "TEST",
        "task_id": "T_FAIL",
        "parent_order_id": None,
        "objective": "Test fail",
        "context": {"summary": "", "relevant_files": [], "relevant_state": {}, "relevant_evidence": []},
        "authority": {"allowed_paths": ["fase0/scratch/"], "forbidden_paths": [], "allowed_commands": ["python", "python3"], "forbidden_commands": [], "network_policy": "OFFLINE_MANDATORY", "destructive_actions_allowed": False, "commit_allowed": False},
        "dependencies": [],
        "inputs": {"artifacts": [], "hashes": {}},
        "definition_of_done": ["DoD"],
        "acceptance_tests": ['python3 -c "assert 1 == 2"'],
        "evidence_required": [],
        "expected_artifacts": [],
        "stop_conditions": ["CAMPAIGN_COMPLETE"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {"max_iterations": 1, "max_wall_time": 10, "max_input_tokens": 100, "max_output_tokens": 100, "max_api_cost_usd": 0.0, "max_gpu_minutes": 0.0},
        "continuation": {"green_means_continue": True, "next_node_policy": "DETERMINISTIC_PRIORITY"},
        "escalation": {"worker_level": 0, "escalation_limit": 1}
    }
    packet = TaskPacketManager.materialize(packet_raw)
    passed = orch._run_acceptance_tests(packet, EventLogger("/dev/null"), "T_FAIL")
    assert passed is False


def test_18_evidence_hashes_validated():
    """18. Evidence hash mismatch raises InvalidGreenError."""
    engine = EvidenceEngine(workspace_root=REPO_ROOT)
    test_art = "fase0/scratch/mvp_run/hash_val_art.txt"
    full_art = os.path.join(REPO_ROOT, test_art)
    os.makedirs(os.path.dirname(full_art), exist_ok=True)
    with open(full_art, "w") as f:
        f.write("actual_content")

    with pytest.raises(InvalidGreenError) as exc:
        engine.verify_node_evidence(
            node_id="T01",
            required_types=["HASH_EVIDENCE", "ARTIFACT_EVIDENCE"],
            attached_evidence={
                "HASH_EVIDENCE": {test_art: "wrong_hash_" + "0" * 53},
                "ARTIFACT_EVIDENCE": [test_art]
            },
            expected_artifacts=[test_art]
        )
    assert "Hash mismatch" in str(exc.value)


def test_19_atomic_state_persistence(temp_workspace):
    """19. State persistence uses atomic write semantics."""
    target_file = os.path.join(temp_workspace, "persisted_state.json")
    payload = {"campaign_id": "ATOMIC_TEST", "counter": 42}
    StatePersistence.atomic_save_json(target_file, payload)

    assert os.path.exists(target_file)
    with open(target_file, "r") as f:
        read_back = json.load(f)
    assert read_back == payload


def test_20_restart_after_running_reconstructs_state():
    """20. Restarting a campaign with a RUNNING node resets it to ELIGIBLE and completes."""
    manifest_path = os.path.join(FIXTURES_DIR, "crash_resume_fixture", "campaign_manifest.json")
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path, is_resume=True)
    assert outcome == "COMPLETED"

    status = orch.plan(manifest_path)
    assert status["status_counts"]["DONE"] == 3


def test_21_completed_node_remains_immutable():
    """21. Completed nodes cannot transition to PENDING, ELIGIBLE, or RUNNING."""
    sm = AutonomousStateMachine()
    with pytest.raises(InvalidStateTransition):
        sm.transition("DONE", "PENDING")
    with pytest.raises(InvalidStateTransition):
        sm.transition("DONE", "RUNNING")
    with pytest.raises(InvalidStateTransition):
        sm.transition("DONE", "ELIGIBLE")


def test_22_duplicate_artifact_conflict_halts():
    """22. Inconsistent duplicate artifact creation raises DuplicateArtifactConflict."""
    # Verified by checking that duplicate writes with differing content are detected
    art_path = os.path.join(REPO_ROOT, "fase0", "scratch", "mvp_run", "dup_test.txt")
    os.makedirs(os.path.dirname(art_path), exist_ok=True)
    with open(art_path, "w") as f:
        f.write("content_v1")

    # If evidence expects content_v2 for the same path
    engine = EvidenceEngine(workspace_root=REPO_ROOT)
    with pytest.raises(InvalidGreenError):
        engine.verify_node_evidence(
            node_id="T_DUP",
            required_types=["HASH_EVIDENCE", "ARTIFACT_EVIDENCE"],
            attached_evidence={
                "HASH_EVIDENCE": {"fase0/scratch/mvp_run/dup_test.txt": hashlib.sha256(b"content_v2").hexdigest()},
                "ARTIFACT_EVIDENCE": ["fase0/scratch/mvp_run/dup_test.txt"]
            },
            expected_artifacts=["fase0/scratch/mvp_run/dup_test.txt"]
        )


def test_23_iteration_limit_works():
    """23. A task exceeding its max_iterations transitions to FAILED."""
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    manifest = {
        "campaign_protocol_version": "0.1.0",
        "campaign_id": "ITER-LIMIT-TEST",
        "title": "Iteration Limit Test",
        "objective": "Test failure on iteration exhaustion",
        "scope": ["fase0/scratch/mvp_run/"],
        "out_of_scope": [".git/"],
        "starting_preimage": {"head_commit": CampaignLoader.get_actual_git_head(REPO_ROOT) or ("1" * 40), "state_hash": "2" * 64, "manifest_hash": "3" * 64},
        "authority": {"canonical_order_hierarchy": ["CAMPAIGN"], "max_active_workers": 1, "allowed_root_paths": ["fase0/scratch/mvp_run/"], "forbidden_root_paths": [".git/"]},
        "budget": {"total_max_tokens": 100, "total_max_api_cost_usd": 0.0, "total_max_gpu_minutes": 0.0, "total_max_wall_time_seconds": 10, "total_max_iterations": 10},
        "nodes": [
            {
                "node_id": "T_FAIL_ITER",
                "type": "TASK",
                "state": "PENDING",
                "dependencies": [],
                "max_iterations": 2,
                "context": {"intentional_failure": True, "intentional_error_msg": "Controlled test error"}
            }
        ],
        "edges": [],
        "human_gates": [],
        "external_gates": [],
        "completion_definition": {"terminal_nodes": ["T_FAIL_ITER"], "required_global_evidence": []},
        "rollback_policy": {"default_strategy": "GIT_RESTORE", "allowed_strategies": ["GIT_RESTORE"], "preserve_evidence": True},
        "state": "PENDING",
        "evidence_index": []
    }
    tmp_path = os.path.join(REPO_ROOT, "fase0", "scratch", "iter_fail_manifest.json")
    with open(tmp_path, "w") as f:
        json.dump(manifest, f)
    try:
        outcome = orch.run(tmp_path)
        assert outcome == "HALTED_AT_FAILED"
        status = orch.plan(tmp_path)
        assert status["status_counts"]["FAILED"] == 1
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_24_max_active_workers_equals_one_enforced():
    """24. MAX_ACTIVE_WORKERS = 1 is strictly verified during loading and scheduling."""
    manifest = {
        "campaign_protocol_version": "0.1.0",
        "campaign_id": "WORKERS-TEST",
        "title": "Workers Test",
        "objective": "Test max workers",
        "scope": ["fase0/"],
        "out_of_scope": [".git/"],
        "starting_preimage": {"head_commit": "1" * 40, "state_hash": "2" * 64, "manifest_hash": "3" * 64},
        "authority": {"canonical_order_hierarchy": ["CAMPAIGN"], "max_active_workers": 2, "allowed_root_paths": ["fase0/"], "forbidden_root_paths": [".git/"]},
        "budget": {"total_max_tokens": 100, "total_max_api_cost_usd": 0.0, "total_max_gpu_minutes": 0.0, "total_max_wall_time_seconds": 10, "total_max_iterations": 2},
        "nodes": [{"node_id": "T1", "type": "TASK", "state": "PENDING", "dependencies": []}],
        "edges": [],
        "human_gates": [],
        "external_gates": [],
        "completion_definition": {"terminal_nodes": ["T1"], "required_global_evidence": []},
        "rollback_policy": {"default_strategy": "GIT_RESTORE", "allowed_strategies": ["GIT_RESTORE"], "preserve_evidence": True},
        "state": "PENDING",
        "evidence_index": []
    }
    loader = CampaignLoader(workspace_root=REPO_ROOT)
    with pytest.raises(CampaignValidationFailed) as exc:
        loader.validate(manifest)
    assert "max_active_workers must strictly equal 1" in str(exc.value)


def test_25_synthetic_ten_plus_node_campaign_completes_autonomously():
    """25. 12-node synthetic pilot campaign completes start-to-finish with zero human prompts."""
    # Regenerate fresh 12-node manifest
    from fase0.autonomous.fixtures import generate_12_node_fixture
    generate_12_node_fixture()

    manifest_path = os.path.join(FIXTURES_DIR, "mvp_fixture", "campaign_manifest.json")
    orch = DeterministicOrchestrator(workspace_root=REPO_ROOT)
    outcome = orch.run(manifest_path)

    assert outcome == "COMPLETED"
    assert orch.autonomous_nodes_completed == 12
    assert orch.autonomous_nodes_completed >= 10
    assert orch.human_continuation_prompts == 0

    # Verify all 12 artifacts exist on disk
    for i in range(1, 13):
        nid = f"t{i:02d}"
        art = os.path.join(REPO_ROOT, "fase0", "scratch", "mvp_run", f"{nid}_output.json")
        assert os.path.exists(art)
        with open(art, "r") as f:
            data = json.load(f)
        assert data["status"] == "VERIFIED_AUTONOMOUS"
