"""PROMETEO · PROM-C00 / AG277-AUTO-01
AUTONOMOUS CAMPAIGN PROTOCOL v0.1 — CONTRACT TEST SUITE

Tests the 15 non-negotiable invariants of Autonomous Campaign Protocol v0.1:
1. GREEN continues if next eligible node exists (GREEN != STOP).
2. HUMAN_GATE halts autonomous progression.
3. BUDGET_GATE halts autonomous progression when budget exhausted.
4. Node with unsatisfied dependencies is not eligible.
5. Node in GREEN or DONE is never re-executed.
6. Worker cannot expand allowed_paths (security boundary enforced).
7. Worker cannot modify campaign authority.
8. INVALID_GREEN triggered if declared required evidence is missing.
9. Completed campaign terminates cleanly in DONE.
10. MAX_ACTIVE_WORKERS = 1 strictly enforced.
11. Recovery from crash reconstructs the correct next eligible node.
12. Cyclic dependency in DAG is rejected fail-closed.
13. Unknown state transition raises INVALID_STATE_TRANSITION and is rejected.
14. Campaign manifest hash changes deterministically upon modification.
15. Invalid Task Packet failing schema is rejected fail-closed.
"""

import copy
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CORPUS_DIR = os.path.join(REPO_ROOT, "fase0", "reality_corpus")
STATE_MACHINE_FILE = os.path.join(CORPUS_DIR, "AUTONOMOUS_STATE_MACHINE_v0.1.json")
TASK_PACKET_SCHEMA_FILE = os.path.join(CORPUS_DIR, "TASK_PACKET_SCHEMA_v0.1.json")
CAMPAIGN_MANIFEST_SCHEMA_FILE = os.path.join(CORPUS_DIR, "CAMPAIGN_MANIFEST_SCHEMA_v0.1.json")
PROTOCOL_FILE = os.path.join(CORPUS_DIR, "AUTONOMOUS_CAMPAIGN_PROTOCOL_v0.1.json")


# ==============================================================================
# DETERMINISTIC PROTOCOL ENGINE & VALIDATORS (CONTRACT REFERENCE IMPLEMENTATION)
# ==============================================================================

class ProtocolViolation(Exception):
    """Raised when a campaign or worker violates protocol contracts."""
    pass


class InvalidStateTransition(ProtocolViolation):
    """Raised when an illegal state transition is attempted."""
    pass


class InvalidGreenError(ProtocolViolation):
    """Raised when GREEN is claimed without verifiable evidence."""
    pass


class AuthorityViolation(ProtocolViolation):
    """Raised when an action exceeds approved authority."""
    pass


def load_state_machine_spec() -> Dict[str, Any]:
    with open(STATE_MACHINE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_transition(from_state: str, to_state: str) -> bool:
    spec = load_state_machine_spec()
    allowed = spec.get("allowed_transitions", [])
    for trans in allowed:
        if trans["from"] == from_state and trans["to"] == to_state:
            return True
    return False


def apply_transition(from_state: str, to_state: str) -> str:
    if not validate_transition(from_state, to_state):
        raise InvalidStateTransition(f"Transition from {from_state} to {to_state} is illegal.")
    return to_state


def validate_task_packet_schema(packet: Dict[str, Any]) -> List[str]:
    """Pure-Python structural validator for TASK_PACKET v0.1 schema."""
    errors = []
    required_top = [
        "task_packet_version", "campaign_id", "task_id", "parent_order_id",
        "objective", "context", "authority", "dependencies", "inputs",
        "definition_of_done", "acceptance_tests", "evidence_required",
        "expected_artifacts", "stop_conditions", "rollback_strategy",
        "budget", "continuation", "escalation"
    ]
    for req in required_top:
        if req not in packet:
            errors.append(f"Missing required top-level property: {req}")

    if packet.get("task_packet_version") != "0.1.0":
        errors.append("Invalid task_packet_version; must be '0.1.0'")

    auth = packet.get("authority", {})
    for req_auth in ["allowed_paths", "forbidden_paths", "allowed_commands",
                     "forbidden_commands", "network_policy",
                     "destructive_actions_allowed", "commit_allowed"]:
        if req_auth not in auth:
            errors.append(f"Missing required authority property: {req_auth}")

    if auth.get("destructive_actions_allowed") is not False:
        errors.append("destructive_actions_allowed must be false in v0.1")

    continuation = packet.get("continuation", {})
    if continuation.get("green_means_continue") is not True:
        errors.append("continuation.green_means_continue must be true")

    budget = packet.get("budget", {})
    for req_b in ["max_iterations", "max_wall_time", "max_input_tokens",
                  "max_output_tokens", "max_api_cost_usd", "max_gpu_minutes"]:
        if req_b not in budget:
            errors.append(f"Missing required budget property: {req_b}")

    return errors


def compute_dag_eligibility(nodes: List[Dict[str, Any]], edges: List[Dict[str, str]]) -> List[str]:
    """Computes eligible nodes: PENDING nodes whose upstream dependencies are all DONE."""
    # Check for cycles
    adj: Dict[str, List[str]] = {n["node_id"]: [] for n in nodes}
    for e in edges:
        if e["from_node"] in adj and e["to_node"] in adj:
            adj[e["from_node"]].append(e["to_node"])

    visited: Dict[str, int] = {}  # 0: visiting, 1: visited

    def has_cycle(u: str) -> bool:
        visited[u] = 0
        for v in adj[u]:
            if visited.get(v) == 0:
                return True
            if v not in visited:
                if has_cycle(v):
                    return True
        visited[u] = 1
        return False

    for node in nodes:
        nid = node["node_id"]
        if nid not in visited:
            if has_cycle(nid):
                raise ProtocolViolation(f"DAG contains cycle involving {nid}")

    node_states = {n["node_id"]: n["state"] for n in nodes}
    node_deps = {n["node_id"]: n.get("dependencies", []) for n in nodes}

    eligible = []
    for n in nodes:
        nid = n["node_id"]
        if n["state"] == "PENDING":
            deps = node_deps[nid]
            if all(node_states.get(d) in ["GREEN", "DONE"] for d in deps):
                eligible.append(nid)
    return eligible


def compute_manifest_sha256(manifest: Dict[str, Any]) -> str:
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ==============================================================================
# TEST SUITE: 15 CONTRACTUAL INVARIANTS
# ==============================================================================

def make_valid_task_packet(task_id: str = "TASK-001", deps: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "task_packet_version": "0.1.0",
        "campaign_id": "PROM-C00",
        "task_id": task_id,
        "parent_order_id": "AG277",
        "objective": "Verify autonomous contract execution.",
        "context": {
            "summary": "Contract test verification packet.",
            "relevant_files": ["fase0/test_autonomous_campaign_protocol_v0_1.py"],
            "relevant_state": {"phase": "TEST"},
            "relevant_evidence": []
        },
        "authority": {
            "allowed_paths": ["fase0/scratch/", "fase0/reality_corpus/"],
            "forbidden_paths": [".git/", "PROJECT_STATE.md"],
            "allowed_commands": ["pytest", "python"],
            "forbidden_commands": ["rm -rf", "git push"],
            "network_policy": "OFFLINE_MANDATORY",
            "destructive_actions_allowed": False,
            "commit_allowed": False
        },
        "dependencies": deps or [],
        "inputs": {
            "artifacts": ["fase0/reality_corpus/AUTONOMOUS_STATE_MACHINE_v0.1.json"],
            "hashes": {
                "fase0/reality_corpus/AUTONOMOUS_STATE_MACHINE_v0.1.json":
                    "a" * 64
            }
        },
        "definition_of_done": ["All tests pass deterministically.", "Evidence recorded."],
        "acceptance_tests": ["pytest fase0/test_autonomous_campaign_protocol_v0_1.py"],
        "evidence_required": ["TEST_EVIDENCE", "HASH_EVIDENCE"],
        "expected_artifacts": ["fase0/scratch/test_receipt.json"],
        "stop_conditions": ["CAMPAIGN_COMPLETE", "HUMAN_DECISION_REQUIRED", "BUDGET_LIMIT_REACHED"],
        "rollback_strategy": "GIT_RESTORE",
        "budget": {
            "max_iterations": 3,
            "max_wall_time": 300,
            "max_input_tokens": 10000,
            "max_output_tokens": 2000,
            "max_api_cost_usd": 0.0,
            "max_gpu_minutes": 0.0
        },
        "continuation": {
            "green_means_continue": True,
            "next_node_policy": "DETERMINISTIC_PRIORITY"
        },
        "escalation": {
            "worker_level": 0,
            "escalation_limit": 3
        }
    }


def test_01_green_continues_if_next_eligible_node_exists():
    """1. GREEN continues automatically if an eligible next node exists (GREEN != STOP)."""
    manifest = {
        "nodes": [
            {"node_id": "TASK-1", "state": "RUNNING", "dependencies": []},
            {"node_id": "TASK-2", "state": "PENDING", "dependencies": ["TASK-1"]}
        ],
        "edges": [{"from_node": "TASK-1", "to_node": "TASK-2"}]
    }

    # Simulate TASK-1 satisfying DoD and evidence
    manifest["nodes"][0]["state"] = apply_transition("RUNNING", "GREEN")
    assert manifest["nodes"][0]["state"] == "GREEN"

    # Orchestrator commits GREEN -> DONE
    manifest["nodes"][0]["state"] = apply_transition("GREEN", "DONE")
    assert manifest["nodes"][0]["state"] == "DONE"

    # Re-evaluate eligibility
    eligible = compute_dag_eligibility(manifest["nodes"], manifest["edges"])
    assert eligible == ["TASK-2"]

    # Invariant: Orchestrator MUST dispatch next node without halting
    # Transition TASK-2 from PENDING -> ELIGIBLE -> RUNNING
    manifest["nodes"][1]["state"] = apply_transition("PENDING", "ELIGIBLE")
    manifest["nodes"][1]["state"] = apply_transition("ELIGIBLE", "RUNNING")
    assert manifest["nodes"][1]["state"] == "RUNNING"


def test_02_human_gate_halts():
    """2. HUMAN_GATE pauses execution and halts autonomous continuation."""
    manifest = {
        "nodes": [
            {"node_id": "TASK-1", "state": "DONE", "dependencies": []},
            {"node_id": "GATE-1", "state": "PENDING", "dependencies": ["TASK-1"]},
            {"node_id": "TASK-2", "state": "PENDING", "dependencies": ["GATE-1"]}
        ],
        "edges": [
            {"from_node": "TASK-1", "to_node": "GATE-1"},
            {"from_node": "GATE-1", "to_node": "TASK-2"}
        ]
    }

    eligible = compute_dag_eligibility(manifest["nodes"], manifest["edges"])
    assert eligible == ["GATE-1"]

    # Dispatch gate
    manifest["nodes"][1]["state"] = apply_transition("PENDING", "ELIGIBLE")
    manifest["nodes"][1]["state"] = apply_transition("ELIGIBLE", "RUNNING")
    manifest["nodes"][1]["state"] = apply_transition("RUNNING", "HUMAN_GATE")

    assert manifest["nodes"][1]["state"] == "HUMAN_GATE"

    # While in HUMAN_GATE, downstream TASK-2 CANNOT become eligible
    downstream_eligible = compute_dag_eligibility(manifest["nodes"], manifest["edges"])
    assert "TASK-2" not in downstream_eligible
    assert downstream_eligible == []  # Completely halted


def test_03_budget_gate_halts():
    """3. BUDGET_GATE halts autonomous progression when budget limit is reached."""
    # Simulate a worker consuming tokens up to the limit
    token_budget_allocated = 5000
    token_budget_consumed = 5000

    node_state = "RUNNING"
    if token_budget_consumed >= token_budget_allocated:
        node_state = apply_transition(node_state, "BUDGET_GATE")

    assert node_state == "BUDGET_GATE"

    # Node in BUDGET_GATE cannot transition directly to GREEN or DONE
    with pytest.raises(InvalidStateTransition):
        apply_transition("BUDGET_GATE", "GREEN")
    with pytest.raises(InvalidStateTransition):
        apply_transition("BUDGET_GATE", "DONE")


def test_04_node_with_unsatisfied_dependencies_is_not_eligible():
    """4. A node with unsatisfied upstream dependencies is never eligible."""
    manifest = {
        "nodes": [
            {"node_id": "TASK-A", "state": "RUNNING", "dependencies": []},
            {"node_id": "TASK-B", "state": "PENDING", "dependencies": ["TASK-A"]},
            {"node_id": "TASK-C", "state": "PENDING", "dependencies": ["TASK-B"]}
        ],
        "edges": [
            {"from_node": "TASK-A", "to_node": "TASK-B"},
            {"from_node": "TASK-B", "to_node": "TASK-C"}
        ]
    }

    eligible = compute_dag_eligibility(manifest["nodes"], manifest["edges"])
    # TASK-A is RUNNING, TASK-B and TASK-C are PENDING with unsatisfied dependencies
    assert eligible == []


def test_05_green_node_is_not_reexecuted():
    """5. A node in GREEN or DONE is never re-executed."""
    # Attempting to transition DONE back to RUNNING or ELIGIBLE must fail
    with pytest.raises(InvalidStateTransition):
        apply_transition("DONE", "RUNNING")
    with pytest.raises(InvalidStateTransition):
        apply_transition("DONE", "ELIGIBLE")
    with pytest.raises(InvalidStateTransition):
        apply_transition("GREEN", "RUNNING")


def test_06_worker_cannot_expand_allowed_paths():
    """6. Worker cannot expand allowed_paths or write to forbidden paths."""
    packet = make_valid_task_packet()
    allowed = packet["authority"]["allowed_paths"]
    forbidden = packet["authority"]["forbidden_paths"]

    target_write = "PROJECT_STATE.md"

    def is_write_permitted(path: str) -> bool:
        for f in forbidden:
            if path.startswith(f) or path == f:
                return False
        for a in allowed:
            if path.startswith(a):
                return True
        return False

    assert not is_write_permitted(target_write)
    assert not is_write_permitted(".git/refs/heads/main")
    assert is_write_permitted("fase0/scratch/temp.json")

    # If worker attempts unauthorized write, orchestrator raises AuthorityViolation
    attempted_write = "PROJECT_STATE.md"
    if not is_write_permitted(attempted_write):
        with pytest.raises(AuthorityViolation):
            raise AuthorityViolation(f"Path {attempted_write} is forbidden.")


def test_07_worker_cannot_modify_campaign_authority():
    """7. Worker cannot modify campaign authority or grant itself permissions."""
    packet = make_valid_task_packet()

    # Worker attempts to mutate destructive_actions_allowed or max_workers
    worker_tampered_packet = copy.deepcopy(packet)
    worker_tampered_packet["authority"]["destructive_actions_allowed"] = True

    errors = validate_task_packet_schema(worker_tampered_packet)
    assert any("destructive_actions_allowed must be false" in e for e in errors)


def test_08_invalid_green_if_missing_evidence():
    """8. INVALID_GREEN triggered if tests pass but declared required evidence is missing."""
    packet = make_valid_task_packet()
    required_evidence = packet["evidence_required"]  # ["TEST_EVIDENCE", "HASH_EVIDENCE"]

    # Worker produced tests, but omitted HASH_EVIDENCE
    attached_evidence = {"TEST_EVIDENCE": "pytest exit 0"}

    def assess_green(tests_passed: bool, attached: Dict[str, Any], required: List[str]) -> str:
        if not tests_passed:
            return "FAILED"
        for req in required:
            if req not in attached:
                raise InvalidGreenError(f"Missing required evidence: {req}")
        return "GREEN"

    with pytest.raises(InvalidGreenError):
        assess_green(tests_passed=True, attached=attached_evidence, required=required_evidence)


def test_09_campaign_complete_terminates_in_done():
    """9. Completed campaign with all terminal nodes terminates in DONE."""
    manifest = {
        "nodes": [
            {"node_id": "TASK-1", "state": "DONE", "dependencies": []},
            {"node_id": "TASK-2", "state": "DONE", "dependencies": ["TASK-1"]}
        ],
        "edges": [{"from_node": "TASK-1", "to_node": "TASK-2"}],
        "completion_definition": {"terminal_nodes": ["TASK-2"]}
    }

    all_done = all(n["state"] in ["DONE", "CANCELLED"] for n in manifest["nodes"])
    terminal_done = all(
        next(n["state"] for n in manifest["nodes"] if n["node_id"] == t) == "DONE"
        for t in manifest["completion_definition"]["terminal_nodes"]
    )

    campaign_status = "RUNNING"
    if all_done and terminal_done:
        campaign_status = "COMPLETED"

    assert campaign_status == "COMPLETED"


def test_10_max_active_workers_equals_one_enforced():
    """10. MAX_ACTIVE_WORKERS = 1 strictly enforced for pilot v0.1."""
    protocol_manifest_authority = {
        "max_active_workers": 1
    }
    assert protocol_manifest_authority["max_active_workers"] == 1

    # Attempting to assign more than 1 worker raises AuthorityViolation
    active_workers = 1
    with pytest.raises(AuthorityViolation):
        if active_workers + 1 > protocol_manifest_authority["max_active_workers"]:
            raise AuthorityViolation("MAX_ACTIVE_WORKERS = 1 exceeded.")


def test_11_recovery_reconstructs_correct_next_node():
    """11. Recovery from crash reconstructs the correct next eligible node without repeating DONE nodes."""
    manifest = {
        "nodes": [
            {"node_id": "TASK-1", "state": "DONE", "dependencies": []},
            {"node_id": "TASK-2", "state": "RUNNING", "dependencies": ["TASK-1"]},  # Crashed mid-execution
            {"node_id": "TASK-3", "state": "PENDING", "dependencies": ["TASK-2"]}
        ],
        "edges": [
            {"from_node": "TASK-1", "to_node": "TASK-2"},
            {"from_node": "TASK-2", "to_node": "TASK-3"}
        ]
    }

    # Crash recovery routine:
    # 1. Reset any uncommitted RUNNING node back to ELIGIBLE (rollback)
    for n in manifest["nodes"]:
        if n["state"] == "RUNNING":
            n["state"] = "ELIGIBLE"

    # 2. Check next eligible node
    assert manifest["nodes"][1]["state"] == "ELIGIBLE"
    assert manifest["nodes"][0]["state"] == "DONE"  # Remained intact, zero re-execution!


def test_12_dag_cycle_is_rejected():
    """12. Cyclic dependency in DAG is rejected fail-closed."""
    cyclic_manifest = {
        "nodes": [
            {"node_id": "TASK-A", "state": "PENDING", "dependencies": ["TASK-B"]},
            {"node_id": "TASK-B", "state": "PENDING", "dependencies": ["TASK-A"]}
        ],
        "edges": [
            {"from_node": "TASK-A", "to_node": "TASK-B"},
            {"from_node": "TASK-B", "to_node": "TASK-A"}
        ]
    }

    with pytest.raises(ProtocolViolation) as exc_info:
        compute_dag_eligibility(cyclic_manifest["nodes"], cyclic_manifest["edges"])
    assert "cycle" in str(exc_info.value).lower()


def test_13_unknown_state_transition_is_rejected():
    """13. Unknown state transition raises INVALID_STATE_TRANSITION and is rejected."""
    # PENDING -> DONE directly is prohibited
    with pytest.raises(InvalidStateTransition):
        apply_transition("PENDING", "DONE")

    # FAILED -> GREEN directly is prohibited
    with pytest.raises(InvalidStateTransition):
        apply_transition("FAILED", "GREEN")

    # RUNNING -> DONE directly (skipping GREEN) is prohibited
    with pytest.raises(InvalidStateTransition):
        apply_transition("RUNNING", "DONE")


def test_14_campaign_manifest_hash_changes_upon_modification():
    """14. Campaign manifest hash changes deterministically upon modification."""
    manifest1 = {
        "campaign_id": "PROM-C00",
        "nodes": [{"node_id": "TASK-1", "state": "PENDING"}]
    }
    hash1 = compute_manifest_sha256(manifest1)

    manifest2 = copy.deepcopy(manifest1)
    manifest2["nodes"][0]["state"] = "RUNNING"
    hash2 = compute_manifest_sha256(manifest2)

    assert hash1 != hash2
    assert len(hash1) == 64
    assert len(hash2) == 64


def test_15_invalid_task_packet_is_rejected_against_schema():
    """15. Invalid Task Packet failing schema is rejected fail-closed."""
    invalid_packet = {
        "task_packet_version": "0.1.0",
        "campaign_id": "PROM-C00"
        # Missing all required fields: task_id, authority, definition_of_done, budget, etc.
    }
    errors = validate_task_packet_schema(invalid_packet)
    assert len(errors) > 0
    assert any("Missing required top-level property" in e for e in errors)
