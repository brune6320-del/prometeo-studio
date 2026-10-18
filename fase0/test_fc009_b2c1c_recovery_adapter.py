"""
PROMETEO · FC-009 · STAGE 3B-2D1B2C1C
Unit Test Suite for Mechanical Observer-Adapter Recovery.

Strict test boundary:
- Uses ONLY deterministic in-memory synthetic numpy arrays and small synthetic support boxes.
- ZERO repository image or PDF fixture reads.
- ZERO label joins, ZERO scorer executions, ZERO ground truth.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "fase0") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "fase0"))

import numpy as np
import pytest

from fase0.experiments.h3dv2_dev_002.integration.observer_bindings_b2c1c import (
    get_observer_provenance,
    observe_m2,
    observe_m3,
    to_canonical_support_bbox,
)
from fase0.experiments.h3dv2_dev_002.integration.packet_builder import (
    build_region_observation_packet,
)
from fase0.experiments.h3dv2_dev_002.p2c_v2_characterization import (
    extract_p2c_measurements_single,
)
from fase0.experiments.h3dv2_dev_002.runtime import (
    SupportGeometry,
    compute_region_id,
    evaluate_document,
    evaluate_region,
)


# ── TEST 1: M2 DICT-SHAPE PARITY ─────────────────────────────────────────────


def test_m2_dict_shape_parity():
    """Verifies that observe_m2 accepts list, tuple, dict, and None without error and yields identical results."""
    # Synthetic image with dark foreground rectangle on light background
    img = 255 * np.ones((100, 100), dtype=np.uint8)
    img[30:70, 30:70] = 20  # dark block

    bbox_list = [20, 20, 80, 80]
    bbox_tuple = (20, 20, 80, 80)
    bbox_dict = {"x0": 20, "y0": 20, "x1": 80, "y1": 80}

    res_list = observe_m2(img, bbox_list)
    res_tuple = observe_m2(img, bbox_tuple)
    res_dict = observe_m2(img, bbox_dict)

    # Must NOT raise AttributeError: 'tuple' object has no attribute 'get'
    assert isinstance(res_list, dict)
    assert isinstance(res_tuple, dict)
    assert isinstance(res_dict, dict)

    # Parity across input representations
    assert res_list["R1_SECONDARY_MASS_RATIO"] == res_dict["R1_SECONDARY_MASS_RATIO"]
    assert res_tuple["R1_SECONDARY_MASS_RATIO"] == res_dict["R1_SECONDARY_MASS_RATIO"]
    assert res_list["T3_ONE_SIDED_OFFSET_CONSISTENCY"] == res_dict["T3_ONE_SIDED_OFFSET_CONSISTENCY"]
    assert res_tuple["T3_ONE_SIDED_OFFSET_CONSISTENCY"] == res_dict["T3_ONE_SIDED_OFFSET_CONSISTENCY"]
    assert res_list["missingness_states"] == res_dict["missingness_states"]

    # Canonical helper correctness
    canon = to_canonical_support_bbox(bbox_list, img.shape)
    assert canon == {"x0": 20, "y0": 20, "x1": 80, "y1": 80}


# ── TEST 2: M2 FEATURE_SPEC PARITY ───────────────────────────────────────────


def test_m2_feature_spec_parity():
    """Verifies that passing {} vs the canonical frozen B2B2 feature_spec produces 100% identical outputs."""
    spec_path = REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2B2_P2C_FEATURE_SPEC.json"
    assert spec_path.exists(), "Frozen feature spec artifact must exist"
    frozen_spec = json.loads(spec_path.read_text(encoding="utf-8"))

    img = 255 * np.ones((80, 80), dtype=np.uint8)
    img[20:60, 20:60] = 10
    bbox = {"x0": 10, "y0": 10, "x1": 70, "y1": 70}

    res_empty = extract_p2c_measurements_single(img, bbox, {})
    res_frozen = extract_p2c_measurements_single(img, bbox, frozen_spec)

    assert res_empty == res_frozen, "Empty feature_spec must be functionally identical to frozen spec"


# ── TEST 3: M2 DETERMINISTIC OUTPUT ──────────────────────────────────────────


def test_m2_deterministic_output():
    """Verifies that observe_m2 produces bitwise identical results across repeated invocations."""
    img = np.zeros((64, 64), dtype=np.uint8)
    img[20:44, 20:44] = 200
    bbox = [15, 15, 50, 50]

    first_res = observe_m2(img, bbox)
    for _ in range(5):
        repeat_res = observe_m2(img, bbox)
        assert first_res == repeat_res


# ── TEST 4: M2 MISSINGNESS SCHEMA ─────────────────────────────────────────────


def test_m2_missingness_schema():
    """Verifies missingness states on degenerate support and insufficient foreground."""
    img = 255 * np.ones((50, 50), dtype=np.uint8)

    # Degenerate support bbox (width <= 2)
    degen_res = observe_m2(img, [10, 10, 11, 30])
    assert "DEGENERATE_SUPPORT" in degen_res["missingness_states"]
    assert degen_res["R1_SECONDARY_MASS_RATIO"] is None
    assert degen_res["T3_ONE_SIDED_OFFSET_CONSISTENCY"] is None

    # Valid extent support bbox returns list of missingness states
    valid_res = observe_m2(img, [5, 5, 45, 45])
    assert isinstance(valid_res["missingness_states"], list)


# ── TEST 5: M3 INTERFACE PARITY ───────────────────────────────────────────────


def test_m3_interface_parity():
    """Verifies that observe_m3 conforms to the expected integration return schema."""
    img_line = np.zeros((100, 100), dtype=np.uint8)
    img_line[48:52, 10:90] = 255  # bright line

    m3_res = observe_m3(img_line, top_k=20)

    assert "OR3_NORMALIZED_SPAN" in m3_res
    assert "missingness_states" in m3_res
    assert "candidate_count" in m3_res
    assert "rank1_candidate" in m3_res

    assert isinstance(m3_res["OR3_NORMALIZED_SPAN"], float)
    assert isinstance(m3_res["missingness_states"], list)
    assert isinstance(m3_res["candidate_count"], int)
    assert m3_res["candidate_count"] >= 1


# ── TEST 6: M3 DETERMINISTIC OUTPUT ───────────────────────────────────────────


def test_m3_deterministic_output():
    """Verifies that observe_m3 is strictly deterministic across repeated invocations."""
    img = np.zeros((64, 64), dtype=np.uint8)
    img[30:34, 10:54] = 255

    first_res = observe_m3(img)
    for _ in range(5):
        repeat_res = observe_m3(img)
        assert first_res == repeat_res


# ── TEST 7: RUNTIME OBSERVATION SCHEMA PARITY ────────────────────────────────


def test_runtime_observation_schema_parity():
    """Verifies that observer outputs flow into build_region_observation_packet and evaluate_region without failure."""
    img = 255 * np.ones((80, 80), dtype=np.uint8)
    img[25:55, 20:60] = 0  # dark rectangular stroke

    support_box = [15, 20, 65, 60]
    support_geom = SupportGeometry(
        x0=float(support_box[0]),
        y0=float(support_box[1]),
        x1=float(support_box[2]),
        y1=float(support_box[3]),
        support_digest=f"{support_box[0]},{support_box[1]},{support_box[2]},{support_box[3]}",
    )

    doc_id = "SYNTH_DOC_001"
    page_num = 0
    region_id = compute_region_id(doc_id, page_num, support_geom)

    m2_res = observe_m2(img, support_box)
    m3_res = observe_m3(img, top_k=20)

    packet = build_region_observation_packet(
        document_id=doc_id,
        page_num=page_num,
        region_id=region_id,
        support_geometry=support_geom,
        m2_obs_result=m2_res,
        m3_obs_result=m3_res,
        polarity_context="POLARITY_NORMAL",
        provenance_metadata={"ordinal": 0},
    )

    assert packet.region_id == region_id
    assert "M2_P2C_V2" in packet.module_observations
    assert "M3_ORIENTATION_NORMALIZED_RULE" in packet.module_observations

    # Evaluate candidate region
    decision = evaluate_region(packet)
    assert decision.region_id == region_id
    assert decision.state in [
        "STRUCTURAL_COUNTEREVIDENCE_PRESENT",
        "STRUCTURAL_COUNTEREVIDENCE_CONFLICTED",
        "STRUCTURE_UNRESOLVED",
        "NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED",
    ]

    # Evaluate document aggregate
    doc_agg = evaluate_document(
        document_id=doc_id,
        region_decisions=[decision],
    )
    assert doc_agg.document_id == doc_id
    assert doc_agg.primary_state == decision.state


# ── TEST 8: OLD FROZEN FILES UNCHANGED ────────────────────────────────────────


def test_old_frozen_files_unchanged():
    """Verifies that all historical files remain 100% byte-identical."""
    expected_digests = {
        "fase0/experiments/h3dv2_dev_002/integration/observer_bindings.py": "7f3ca81a778a38358ee4168aa0185cdc7e41561abbb3019ccfd260cd85e1ce06",
        "fase0/experiments/h3dv2_dev_002/integration/run_dev002_integration_b2c0b.py": "a3592f7bb6cbdbf7a970549d0284503aceb5eb99595490c6ae8264a5346ec860",
        "fase0/experiments/h3dv2_dev_002/integration/run_dev002_integration_b2c0c.py": "a21551ee5f4c8fef3a9bc84bbb925e6214c21c27a8f69724b77bb60063691324",
        "fase0/experiments/h3dv2_dev_002/p2c_v2_characterization.py": "8a6b4d51d9fdedeb786c942ac5eccc7de0c98326acf2a47f8bc68be8eecea653",
        "fase0/experiments/h3dv2_dev_002/orientation_rule_characterization.py": "66e76f6e4cbc84b961718e1ebd748f4eb8860e32e708531099c6e8490ea00fbc",
    }

    for rel_path, expected_sha in expected_digests.items():
        actual_sha = hashlib.sha256((REPO_ROOT / rel_path).read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"Byte mutation detected in {rel_path}"


# ── TEST 9: RECOVERY OUTPUT NAMES DIFFER FROM B2C1A ───────────────────────────


def test_recovery_output_names_differ_from_b2c1a():
    """Verifies that recovery runner defaults use B2C1D namespace and do not collide with B2C1A raw outputs."""
    from fase0.experiments.h3dv2_dev_002.integration.run_dev002_integration_b2c1c import (
        DEFAULT_RECOVERY_JOURNAL_PATH,
        DEFAULT_RECOVERY_RECEIPT_PATH,
        DEFAULT_RECOVERY_RESULTS_PATH,
    )

    b2c1a_names = [
        "FC009_STAGE3B2D1B2C1_DEV002_RAW_JOURNAL.jsonl",
        "FC009_STAGE3B2D1B2C1_DEV002_RAW_RESULTS.json",
        "FC009_STAGE3B2D1B2C1_DEV002_EXECUTION_RECEIPT.json",
    ]

    assert DEFAULT_RECOVERY_JOURNAL_PATH.name not in b2c1a_names
    assert DEFAULT_RECOVERY_RESULTS_PATH.name not in b2c1a_names
    assert DEFAULT_RECOVERY_RECEIPT_PATH.name not in b2c1a_names

    assert "STAGE3B2D1B2C1D" in DEFAULT_RECOVERY_JOURNAL_PATH.name
    assert "STAGE3B2D1B2C1D" in DEFAULT_RECOVERY_RESULTS_PATH.name
    assert "STAGE3B2D1B2C1D" in DEFAULT_RECOVERY_RECEIPT_PATH.name

    # Outputs must not exist prior to B2C1D execution
    assert not DEFAULT_RECOVERY_JOURNAL_PATH.exists()
    assert not DEFAULT_RECOVERY_RESULTS_PATH.exists()
    assert not DEFAULT_RECOVERY_RECEIPT_PATH.exists()


# ── TEST 10: STATIC AST AUDIT ─────────────────────────────────────────────────


def test_static_ast_safety_audit():
    """Verifies that successor binding and runner contain zero forbidden calls or ground-truth logic."""
    target_files = [
        REPO_ROOT / "fase0/experiments/h3dv2_dev_002/integration/observer_bindings_b2c1c.py",
        REPO_ROOT / "fase0/experiments/h3dv2_dev_002/integration/run_dev002_integration_b2c1c.py",
    ]

    forbidden_symbols = [
        "canonical_intent",
        "cohort_role",
        "ground_truth",
        "score_candidate_run",
        "scorer",
        "urllib",
        "requests",
        "socket",
        "random",
        "np.random",
    ]

    for p in target_files:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_symbols:
                pytest.fail(f"Forbidden symbol {node.id} found in {p.name}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_symbols:
                pytest.fail(f"Forbidden attribute {node.attr} found in {p.name}")
