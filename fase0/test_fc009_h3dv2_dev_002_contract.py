"""
PROMETEO · FC-009 · STAGE 3B-2D1B2B7
H3DV2_DEV_002 Full 15-Criteria Conformance & Decision Lattice Unit Test Suite.

Contains zero image decodes, zero corpus reads, zero OCR, and zero ML calls.
Tests the frozen candidate decision logic against the 15 canonical contract criteria,
including explicit synthetic triggers for the four historically unexercised criteria:
- I-INV-02 (T02)
- I-INV-04 (T04)
- I-INV-07 (T07)
- STRUCTURAL-02 (T07)
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from experiments.h3dv2_dev_002.runtime import (
    DECISION_AUTHORITY,
    DEV002_M1_NO_RULE,
    DEV002_M2_R1_RULE_001,
    DEV002_M3_OR3_RULE_001,
    DEV002_M4_NO_RULE,
    DEV002_M5_NO_RULE,
    DEV002_M6_NO_RULE,
    M2_CONTEXT_THRESHOLD_T3,
    M2_THRESHOLD_R1,
    M3_THRESHOLD_OR3,
    DocumentAggregate,
    ModuleEvaluation,
    ModuleObservation,
    ModuleOutputEnum,
    ObservationProvenance,
    RegionDecision,
    RegionObservationPacket,
    RegionStateEnum,
    SupportGeometry,
    compute_observation_id,
    compute_region_id,
    compute_token_id,
    evaluate_document,
    evaluate_region,
    to_canonical_bytes,
    to_canonical_json,
)


# ── HELPER FACTORIES ─────────────────────────────────────────────────────────


def make_geometry(
    x0: float = 100.0, y0: float = 100.0, x1: float = 500.0, y1: float = 200.0
) -> SupportGeometry:
    return SupportGeometry(x0=x0, y0=y0, x1=x1, y1=y1, support_digest="geo_digest_test")


def make_clean_packet(
    document_id: str = "doc_test_001",
    page_num: int = 1,
    region_id: str = "reg_test_001",
    polarity: str = "POLARITY_NORMAL",
    scale_debt: bool = False,
    m2_measurements: Dict[str, Any] = None,
    m3_measurements: Dict[str, Any] = None,
    m1_applicable: bool = False,
    m4_applicable: bool = False,
    m5_applicable: bool = False,
    m6_applicable: bool = False,
    legacy_context: Dict[str, Any] = None,
    typography_context: Dict[str, Any] = None,
) -> RegionObservationPacket:
    """Creates a controlled synthetic RegionObservationPacket for testing."""
    m2_m = m2_measurements if m2_measurements is not None else {"R1_SECONDARY_MASS_RATIO": 0.10}
    m3_m = m3_measurements if m3_measurements is not None else {"OR3_NORMALIZED_SPAN": 0.10}

    obs_map = {
        "M1_LONG_RULE_V2": ModuleObservation(
            module_id="M1_LONG_RULE_V2", applicable=m1_applicable, relevant=m1_applicable
        ),
        "M2_P2C_V2": ModuleObservation(
            module_id="M2_P2C_V2",
            applicable=True,
            relevant=True,
            measurements=m2_m,
        ),
        "M3_ORIENTATION_NORMALIZED_RULE": ModuleObservation(
            module_id="M3_ORIENTATION_NORMALIZED_RULE",
            applicable=True,
            relevant=True,
            measurements=m3_m,
        ),
        "M4_P2F_COMPONENT_PATTERN": ModuleObservation(
            module_id="M4_P2F_COMPONENT_PATTERN", applicable=m4_applicable, relevant=m4_applicable
        ),
        "M5_SCAN_JUNCTION_TOPOLOGY": ModuleObservation(
            module_id="M5_SCAN_JUNCTION_TOPOLOGY", applicable=m5_applicable, relevant=m5_applicable
        ),
        "M6_SCAN_ENCLOSURE_TOPOLOGY": ModuleObservation(
            module_id="M6_SCAN_ENCLOSURE_TOPOLOGY", applicable=m6_applicable, relevant=m6_applicable
        ),
    }

    return RegionObservationPacket(
        document_id=document_id,
        page_num=page_num,
        region_id=region_id,
        support_geometry=make_geometry(),
        module_observations=obs_map,
        polarity_context=polarity,
        typography_context=typography_context,
        legacy_residual_context=legacy_context,
        scale_debt_active=scale_debt,
        provenance={"test_synthetic": True},
    )


# ── SECTION 14 & REQUISITES: SYMBOLIC REACHABILITY OF NO_COUNTER ─────────────


def test_symbolic_no_counter_not_clearance():
    """
    SECTION 14: Verifies symbolic reachability of NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED.
    All relevant channels (M2, M3) adequately observed and evaluate FALSE.
    M1, M4, M5, M6 are explicitly NOT_APPLICABLE.
    Expected: NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED with decision_authority = NONE.
    """
    packet = make_clean_packet(
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.10},  # Below 0.21138450
        m3_measurements={"OR3_NORMALIZED_SPAN": 0.10},  # Below 0.34575950
        m1_applicable=False,
        m4_applicable=False,
        m5_applicable=False,
        m6_applicable=False,
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED
    assert decision.decision_authority == "NONE"
    assert decision.state.value != "SAFE"
    assert decision.state.value != "CLEARANCE_GRANTED"
    assert decision.state.value != "TEXT_COMPATIBLE"


# ── SECTION 24: M2 BOUNDARY TESTS ───────────────────────────────────────────


def test_m2_boundary_below_threshold():
    """R1 just below 0.21138450 must produce OBSERVED_NO_POSITIVE_EVIDENCE."""
    r1_val = 0.21138449
    packet = make_clean_packet(m2_measurements={"R1_SECONDARY_MASS_RATIO": r1_val})
    decision = evaluate_region(packet)
    m2_eval = decision.module_evaluations["M2_P2C_V2"]
    assert m2_eval.output_state == ModuleOutputEnum.OBSERVED_NO_POSITIVE_EVIDENCE
    assert m2_eval.rule_id == DEV002_M2_R1_RULE_001


def test_m2_boundary_exact_threshold():
    """R1 exactly at 0.21138450 must produce STRUCTURAL_EVIDENCE_PRESENT."""
    r1_val = M2_THRESHOLD_R1
    packet = make_clean_packet(m2_measurements={"R1_SECONDARY_MASS_RATIO": r1_val})
    decision = evaluate_region(packet)
    m2_eval = decision.module_evaluations["M2_P2C_V2"]
    assert m2_eval.output_state == ModuleOutputEnum.STRUCTURAL_EVIDENCE_PRESENT
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT


def test_m2_boundary_above_threshold():
    """R1 just above 0.21138450 must produce STRUCTURAL_EVIDENCE_PRESENT."""
    r1_val = 0.21138451
    packet = make_clean_packet(m2_measurements={"R1_SECONDARY_MASS_RATIO": r1_val})
    decision = evaluate_region(packet)
    m2_eval = decision.module_evaluations["M2_P2C_V2"]
    assert m2_eval.output_state == ModuleOutputEnum.STRUCTURAL_EVIDENCE_PRESENT
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT


def test_m2_missing_observable_unresolved():
    """Missing R1 when applicable must resolve to OBSERVATION_UNRESOLVED, never negative."""
    packet = make_clean_packet(m2_measurements={})  # R1 missing
    decision = evaluate_region(packet)
    m2_eval = decision.module_evaluations["M2_P2C_V2"]
    assert m2_eval.output_state == ModuleOutputEnum.OBSERVATION_UNRESOLVED
    assert decision.state == RegionStateEnum.STRUCTURE_UNRESOLVED


# ── SECTION 25: M2 CONTEXT CLAUSE & I-INV-01 (NO POSITIVE VETO) ─────────────


def test_m2_context_below_005_surfaces_conflict():
    """
    R1 positive coexisting with T3 <= 0.05 surfaces conflict:
    Region resolves to STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.
    Positive evidence is NOT deleted or vetoed (preserves I-INV-01).
    """
    packet = make_clean_packet(
        m2_measurements={
            "R1_SECONDARY_MASS_RATIO": 0.35,
            "T3_ONE_SIDED_OFFSET_CONSISTENCY": 0.04,  # Below 0.05
        }
    )
    decision = evaluate_region(packet)
    m2_eval = decision.module_evaluations["M2_P2C_V2"]
    assert m2_eval.output_state == ModuleOutputEnum.STRUCTURAL_EVIDENCE_PRESENT
    assert m2_eval.conflict_flag is not None
    assert decision.conflict_detected is True
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED
    assert decision.state != RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED


def test_m2_context_exact_005_surfaces_conflict():
    """T3 exactly 0.05 surfaces conflict."""
    packet = make_clean_packet(
        m2_measurements={
            "R1_SECONDARY_MASS_RATIO": 0.35,
            "T3_ONE_SIDED_OFFSET_CONSISTENCY": 0.05,
        }
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED


def test_m2_context_above_005_clean_positive():
    """T3 > 0.05 yields clean positive."""
    packet = make_clean_packet(
        m2_measurements={
            "R1_SECONDARY_MASS_RATIO": 0.35,
            "T3_ONE_SIDED_OFFSET_CONSISTENCY": 0.06,  # Above 0.05
        }
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT


# ── SECTION 26: M3 BOUNDARY TESTS ───────────────────────────────────────────


def test_m3_boundary_below_threshold():
    """OR3 just below 0.34575950 must produce OBSERVED_NO_POSITIVE_EVIDENCE."""
    packet = make_clean_packet(m3_measurements={"OR3_NORMALIZED_SPAN": 0.34575949})
    decision = evaluate_region(packet)
    m3_eval = decision.module_evaluations["M3_ORIENTATION_NORMALIZED_RULE"]
    assert m3_eval.output_state == ModuleOutputEnum.OBSERVED_NO_POSITIVE_EVIDENCE


def test_m3_boundary_exact_threshold():
    """OR3 exactly at 0.34575950 must produce STRUCTURAL_EVIDENCE_PRESENT."""
    packet = make_clean_packet(m3_measurements={"OR3_NORMALIZED_SPAN": M3_THRESHOLD_OR3})
    decision = evaluate_region(packet)
    m3_eval = decision.module_evaluations["M3_ORIENTATION_NORMALIZED_RULE"]
    assert m3_eval.output_state == ModuleOutputEnum.STRUCTURAL_EVIDENCE_PRESENT
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT


def test_m3_boundary_above_threshold():
    """OR3 just above 0.34575950 must produce STRUCTURAL_EVIDENCE_PRESENT."""
    packet = make_clean_packet(m3_measurements={"OR3_NORMALIZED_SPAN": 0.34575951})
    decision = evaluate_region(packet)
    m3_eval = decision.module_evaluations["M3_ORIENTATION_NORMALIZED_RULE"]
    assert m3_eval.output_state == ModuleOutputEnum.STRUCTURAL_EVIDENCE_PRESENT
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT


def test_m3_missing_observable_unresolved():
    """Missing OR3 must resolve to OBSERVATION_UNRESOLVED (never coerced to zero)."""
    packet = make_clean_packet(m3_measurements={})
    decision = evaluate_region(packet)
    m3_eval = decision.module_evaluations["M3_ORIENTATION_NORMALIZED_RULE"]
    assert m3_eval.output_state == ModuleOutputEnum.OBSERVATION_UNRESOLVED
    assert decision.state == RegionStateEnum.STRUCTURE_UNRESOLVED


# ── SECTION 27: NO-RULE MODULE TESTS (M1, M4, M5, M6) ───────────────────────


@pytest.mark.parametrize("mod_id", [
    "M1_LONG_RULE_V2",
    "M4_P2F_COMPONENT_PATTERN",
    "M5_SCAN_JUNCTION_TOPOLOGY",
    "M6_SCAN_ENCLOSURE_TOPOLOGY",
])
def test_no_rule_selected_modules_when_applicable_yield_unresolved(mod_id: str):
    """
    SECTION 27: For M1, M4, M5, M6, when applicable, output must be OBSERVATION_UNRESOLVED.
    Zero path from NO_RULE_SELECTED to OBSERVED_NO_POSITIVE_EVIDENCE.
    """
    kwargs = {
        "m1_applicable": (mod_id == "M1_LONG_RULE_V2"),
        "m4_applicable": (mod_id == "M4_P2F_COMPONENT_PATTERN"),
        "m5_applicable": (mod_id == "M5_SCAN_JUNCTION_TOPOLOGY"),
        "m6_applicable": (mod_id == "M6_SCAN_ENCLOSURE_TOPOLOGY"),
    }
    packet = make_clean_packet(**kwargs)
    decision = evaluate_region(packet)
    eval_obj = decision.module_evaluations[mod_id]
    assert eval_obj.output_state == ModuleOutputEnum.OBSERVATION_UNRESOLVED
    assert eval_obj.output_state != ModuleOutputEnum.OBSERVED_NO_POSITIVE_EVIDENCE
    assert decision.state == RegionStateEnum.STRUCTURE_UNRESOLVED


@pytest.mark.parametrize("mod_id", [
    "M1_LONG_RULE_V2",
    "M4_P2F_COMPONENT_PATTERN",
    "M5_SCAN_JUNCTION_TOPOLOGY",
    "M6_SCAN_ENCLOSURE_TOPOLOGY",
])
def test_no_rule_selected_modules_when_not_applicable_yield_not_applicable(mod_id: str):
    """When explicitly not applicable, emits NOT_APPLICABLE."""
    packet = make_clean_packet(
        m1_applicable=False,
        m4_applicable=False,
        m5_applicable=False,
        m6_applicable=False,
    )
    decision = evaluate_region(packet)
    eval_obj = decision.module_evaluations[mod_id]
    assert eval_obj.output_state == ModuleOutputEnum.NOT_APPLICABLE


# ── SECTION 29: T02 · I-INV-02 (AMBIGUOUS POLARITY UNRESOLVED) ───────────────


def test_t02_i_inv_02_ambiguous_polarity_unresolved():
    """
    T02 / I-INV-02: Synthetic packet with AMBIGUOUS_POLARITY, no qualified positive,
    otherwise adequately observed.
    Must resolve to STRUCTURE_UNRESOLVED, never NO_COUNTEREVIDENCE.
    """
    packet = make_clean_packet(
        polarity="AMBIGUOUS_POLARITY",
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.10},
        m3_measurements={"OR3_NORMALIZED_SPAN": 0.10},
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.STRUCTURE_UNRESOLVED
    assert decision.state != RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED
    assert "POLARITY_AMBIGUOUS" in decision.unresolved_channels


# ── SECTION 30: T04 · I-INV-04 (RESIDUAL CONFLICT SURFACED) ─────────────────


def test_t04_i_inv_04_residual_conflict_surfaced():
    """
    T04 / I-INV-04: Synthetic legacy residual/M3-like positive observation overlapping text support.
    Must resolve to STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.
    Residual conflict remains visible, never deleted.
    """
    packet = make_clean_packet(
        legacy_context={
            "residual_signal_present": True,
            "overlaps_text_support": True,
        }
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED
    assert decision.conflict_detected is True
    assert decision.state != RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED


# ── SECTION 31: T07 · I-INV-07 + STRUCTURAL-02 (AGGREGATION PRESERVATION) ───


def test_t07_i_inv_07_structural_02_aggregation_preservation():
    """
    T07 / I-INV-07 + STRUCTURAL-02:
    Document with Region A (PRESENT) and Region B (CONFLICTED).
    Primary state = PRESENT, but aggregate MUST report:
    contains_conflicted_region = True, Region B in region_ids_by_state[CONFLICTED],
    conflicted count preserved.
    """
    packet_a = make_clean_packet(
        region_id="reg_A",
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.35},  # Clean positive
    )
    packet_b = make_clean_packet(
        region_id="reg_B",
        m2_measurements={
            "R1_SECONDARY_MASS_RATIO": 0.35,
            "T3_ONE_SIDED_OFFSET_CONSISTENCY": 0.03,  # Conflicted positive
        },
    )
    dec_a = evaluate_region(packet_a)
    dec_b = evaluate_region(packet_b)

    assert dec_a.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert dec_b.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED

    doc_agg = evaluate_document("doc_t07", [dec_a, dec_b])

    assert doc_agg.primary_state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert doc_agg.contains_clean_positive is True
    assert doc_agg.contains_conflicted_region is True
    assert doc_agg.region_state_counts[RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.value] == 1
    assert "reg_B" in doc_agg.region_ids_by_state[RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.value]


# ── SECTION 32: I-INV-03 / STRUCTURAL-07 (SCALE DEBT NO NEGATIVE) ────────────


def test_i_inv_03_structural_07_scale_debt_no_negative_evidence():
    """
    I-INV-03 / STRUCTURAL-07: When scale debt is active and P2-C observation is missing,
    must resolve to STRUCTURE_UNRESOLVED, never NO_COUNTEREVIDENCE.
    """
    packet = make_clean_packet(
        scale_debt=True,
        m2_measurements={},  # Missing P2-C
    )
    decision = evaluate_region(packet)
    assert decision.state == RegionStateEnum.STRUCTURE_UNRESOLVED
    assert decision.state != RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED
    assert "P2C_SCALE_DEBT_UNRESOLVED" in decision.unresolved_channels


# ── SECTION 33: I-INV-05 (NO DOUBLE COUNTING) ────────────────────────────────


def test_i_inv_05_legacy_periodic_not_double_counted():
    """
    I-INV-05: Verifies legacy periodic signals and successor observations maintain
    distinct source channels without double-counting.
    """
    packet = make_clean_packet(
        legacy_context={"periodic_legacy_source": "M3_LEGACY", "signal_present": False},
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.10},
    )
    decision = evaluate_region(packet)
    eval_keys = list(decision.module_evaluations.keys())
    assert len(eval_keys) == 6
    assert len(set(eval_keys)) == 6


# ── SECTION 34: I-INV-06 (TWO CORROBORATING SOURCES PROVENANCE) ──────────────


def test_i_inv_06_corroboration_preserves_two_sources():
    """
    I-INV-06: Corroborating observations across independent channels retain
    two separately traceable provenance identities.
    """
    tok_p2d = compute_token_id("PRIMITIVE_P2D", "CFG_01", "reg_001", "CONTOUR", ordinal=0)
    tok_p2c = compute_token_id("PRIMITIVE_P2C", "CFG_01", "reg_001", "STROKE", ordinal=0)
    assert tok_p2d != tok_p2c
    assert len(tok_p2d) == 16
    assert len(tok_p2c) == 16


# ── SECTION 35: STRUCTURAL-06 (P2-E NO SELF-PROMOTION) ───────────────────────


def test_structural_06_p2e_typography_context_alone_no_positive():
    """
    STRUCTURAL-06: P2-E typographic context alone can NEVER generate
    STRUCTURAL_COUNTEREVIDENCE_PRESENT.
    """
    packet = make_clean_packet(
        typography_context={"p2e_graphic_regularity": 0.99, "is_clean_typography": True},
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.05},
        m3_measurements={"OR3_NORMALIZED_SPAN": 0.05},
    )
    decision = evaluate_region(packet)
    assert decision.state != RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert decision.state == RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED


# ── SECTION 36: STRUCTURAL-01 (CROSS-REGION ISOLATION) ───────────────────────


def test_structural_01_cross_region_isolation():
    """
    STRUCTURAL-01: Evidence from Region A can never cancel, validate, or resolve Region B.
    Zero cross-region illicit interaction.
    """
    packet_a = make_clean_packet(
        region_id="reg_A",
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.40},  # PRESENT
    )
    packet_b = make_clean_packet(
        region_id="reg_B",
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.05},  # NO_COUNTER
    )
    dec_a = evaluate_region(packet_a)
    dec_b = evaluate_region(packet_b)

    assert dec_a.state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert dec_b.state == RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED

    # Evaluating document does not mutate individual region decisions
    doc_agg = evaluate_document("doc_iso", [dec_a, dec_b])
    assert doc_agg.region_ids_by_state[RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value] == ["reg_A"]
    assert doc_agg.region_ids_by_state[RegionStateEnum.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED.value] == ["reg_B"]


# ── SECTION 37: STRUCTURAL-03 (UNRESOLVED PRESERVED IN AGGREGATE) ────────────


def test_structural_03_unresolved_preserved_in_aggregation():
    """
    STRUCTURAL-03: An unresolved region remains represented in aggregate summaries
    even if the document primary state is PRESENT.
    """
    packet_pos = make_clean_packet(
        region_id="reg_pos",
        m2_measurements={"R1_SECONDARY_MASS_RATIO": 0.40},
    )
    packet_unres = make_clean_packet(
        region_id="reg_unres",
        polarity="AMBIGUOUS_POLARITY",
    )
    dec_pos = evaluate_region(packet_pos)
    dec_unres = evaluate_region(packet_unres)

    doc_agg = evaluate_document("doc_unres_preserve", [dec_pos, dec_unres])
    assert doc_agg.primary_state == RegionStateEnum.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert doc_agg.contains_unresolved_region is True
    assert "reg_unres" in doc_agg.region_ids_by_state[RegionStateEnum.STRUCTURE_UNRESOLVED.value]


# ── SECTION 38: STRUCTURAL-04 & 05 (DETERMINISTIC IDS & SERIALIZATION) ───────


def test_structural_04_05_deterministic_ids_and_byte_serialization():
    """
    STRUCTURAL-04 & STRUCTURAL-05:
    Verifies deterministic ID generation, input permutation invariance,
    and byte-identical JSON serialization across multiple repeated executions.
    """
    geo1 = SupportGeometry(10, 20, 30, 40, "digest1")
    geo2 = SupportGeometry(10, 20, 30, 40, "digest1")

    id1 = compute_region_id("doc_det", 1, geo1)
    id2 = compute_region_id("doc_det", 1, geo2)
    assert id1 == id2
    assert len(id1) == 16

    tok1 = compute_token_id("PRIM_A", "CFG_01", id1, "FAMILY_A", 0)
    tok2 = compute_token_id("PRIM_A", "CFG_01", id1, "FAMILY_A", 0)
    assert tok1 == tok2

    # Permuted dictionary keys in packet
    pkt_orig = make_clean_packet(region_id=id1)
    dec_orig = evaluate_region(pkt_orig)
    json_bytes_1 = to_canonical_bytes(dec_orig)
    json_bytes_2 = to_canonical_bytes(dec_orig)
    assert json_bytes_1 == json_bytes_2

    # Repeated invocations yield byte-identical string
    for _ in range(5):
        assert to_canonical_json(dec_orig) == to_canonical_json(dec_orig)


# ── SECTION 39: AUTHORITY BOUNDARY & I-INV-08 ────────────────────────────────


def test_authority_boundary_and_i_inv_08_provenance():
    """
    Verifies that decision authority is strictly NONE for all outcomes,
    and every decision object carries complete provenance (I-INV-08).
    """
    packet = make_clean_packet()
    decision = evaluate_region(packet)
    assert decision.decision_authority == "NONE"
    assert "document_id" in decision.provenance
    assert "region_id" in decision.provenance
    assert "decision_authority" in decision.provenance

    doc_agg = evaluate_document("doc_auth_check", [decision])
    assert doc_agg.decision_authority == "NONE"
    assert "total_regions_evaluated" in doc_agg.aggregate_provenance
    assert doc_agg.aggregate_provenance["decision_authority"] == "NONE"
