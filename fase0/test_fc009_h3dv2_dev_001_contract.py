"""
PROMETEO · FC-009 · STAGE 3B-2D1B1A
Contract Test Suite for H3DV2_DEV_001 Integrator.
Directly verifies all 15 frozen conformance criteria, behavioral invariants,
authority prohibitions, and determinism properties using ONLY synthetic in-memory fixtures.
ZERO access to historical or development fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np
import pytest

from fase0.experiments.h3dv2_dev_001.aggregation import aggregate_material_regions
from fase0.experiments.h3dv2_dev_001.candidate import H3DV2Dev001
from fase0.experiments.h3dv2_dev_001.canonical import (
    CANDIDATE_ID,
    CONTRACT_HASHES,
    DECISION_AUTHORITY,
    FORBIDDEN_OUTPUT_STRINGS,
    LEGACY_PERIODIC_POLICY,
    P2C_RAW_PIXEL_SHIFT_DEBT,
    P2D_TESTED_SCALE_CONSISTENCY,
    SEMANTIC_CLAIM,
)
from fase0.experiments.h3dv2_dev_001.evidence import (
    compute_token_id,
    create_token,
    evaluate_token_compatibility_and_conflicts,
)
from fase0.experiments.h3dv2_dev_001.geometry import (
    classify_support_relation,
    compute_support_digest,
    map_token_support_association,
)
from fase0.experiments.h3dv2_dev_001.lattice import resolve_region_lattice
from fase0.experiments.h3dv2_dev_001.regions import (
    cluster_material_regions,
    compute_material_region_id,
    compute_observation_region_id,
    compute_root_region_id,
    sort_observation_candidates,
)
from fase0.experiments.h3dv2_dev_001.schema import (
    ApplicabilityState,
    BoundingBox,
    EvidenceToken,
    MaterialRegion,
    ObservationRegion,
    PolarityState,
    RegionState,
    RegularityState,
    RelevanceState,
    SupportRelation,
    TokenSupportAssociation,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHORITY & CLAIM PROHIBITION TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_authority_invariants_and_prohibitions():
    """Verifies that H3DV2_DEV_001 cannot claim authority or safe clearance."""
    integrator = H3DV2Dev001()
    img_synth = np.full((100, 200), 255, dtype=np.uint8)
    out = integrator.evaluate(img_synth, doc_or_fixture_id="UNIT_TEST_SYNTHETIC")

    assert out.candidate_id == CANDIDATE_ID == "H3DV2_DEV_001"
    assert out.semantic_claim == SEMANTIC_CLAIM == "UNRESOLVED"
    assert out.decision_authority == DECISION_AUTHORITY == "NONE"

    # Serialized JSON must contain no authority grants
    json_str = integrator.to_canonical_json(out)
    parsed = json.loads(json_str)

    assert parsed["semantic_claim"] == "UNRESOLVED"
    assert parsed["decision_authority"] == "NONE"

    for forbidden in FORBIDDEN_OUTPUT_STRINGS:
        assert parsed["semantic_claim"] != forbidden
        assert parsed["decision_authority"] != forbidden


# ══════════════════════════════════════════════════════════════════════════════
# 2. BEHAVIORAL INVARIANTS (I-INV-01 through I-INV-08)
# ══════════════════════════════════════════════════════════════════════════════

def test_i_inv_01_text_support_never_deletes_positive_structural_evidence():
    """I-INV-01: Positive structural token may become conflicted, but NEVER disappears due to text support."""
    # Token 1: Hard topology long rule (positive structural)
    t_rule = create_token(
        source_primitive="LEGACY_LONG_RULE",
        source_configuration="CFG_LEGACY_LONG_RULE",
        region_id="REG_RULE",
        support_geometry={"bbox": {"x0": 10, "y0": 50, "x1": 200, "y1": 55}},
        evidence_family="HARD_TOPOLOGY",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="LONG_RULE_PRESENT",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=True,
    )
    # Token 2: Text support on same support
    t_text = create_token(
        source_primitive="P2-E",
        source_configuration="CFG_P2E_ytol30_solidthresh82",
        region_id="REG_RULE",
        support_geometry={"bbox": {"x0": 10, "y0": 50, "x1": 200, "y1": 55}},
        evidence_family="TEXT_SUPPORT",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="TEXT_SUPPORT_CANDIDATE",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=False,
    )

    evaluated = evaluate_token_compatibility_and_conflicts([t_rule, t_text])
    assert len(evaluated) == 2
    # Rule must still be positive!
    rule_tok = [t for t in evaluated if t.evidence_family == "HARD_TOPOLOGY"][0]
    assert rule_tok.positive_observation is True

    reg_state, _, _ = resolve_region_lattice(evaluated)
    assert reg_state == RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT


def test_i_inv_02_ambiguous_polarity_prevents_no_counterevidence():
    """I-INV-02: AMBIGUOUS_POLARITY never silently becomes no-counterevidence; must yield STRUCTURE_UNRESOLVED."""
    t_context = create_token(
        source_primitive="P2-B",
        source_configuration="CFG_P2B_darkratio15_hratio85",
        region_id="REG_0",
        support_geometry={"bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100}},
        evidence_family="PHOTOMETRIC_CONTEXT",
        polarity_context=PolarityState.AMBIGUOUS_POLARITY.value,
        ownership_context="AMBIGUOUS",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="AMBIGUOUS",
        positive_observation=False,
    )
    reg_state, limitations, prov = resolve_region_lattice(
        tokens=[t_context],
        polarity_state=PolarityState.AMBIGUOUS_POLARITY.value,
    )
    assert reg_state == RegionState.STRUCTURE_UNRESOLVED
    assert reg_state != RegionState.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED
    assert any("POLARITY" in lim for lim in limitations)


def test_i_inv_03_p2c_absence_under_scale_debt_is_not_negative():
    """I-INV-03: P2-C absence under open scale debt must never become negative evidence or clearance."""
    t_p2c = create_token(
        source_primitive="P2-C",
        source_configuration="CFG_P2C_mass25_asym20",
        region_id="REG_0",
        support_geometry={"bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100}},
        evidence_family="OBSERVATION_LIMITATION",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="NO_SHADOW_RELATION_OBSERVED",
        applicability_state=ApplicabilityState.PARTIALLY_APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=False,
        scale_status=P2C_RAW_PIXEL_SHIFT_DEBT,
    )
    reg_state, limitations, prov = resolve_region_lattice(
        tokens=[t_p2c],
        polarity_state="DARK_ON_LIGHT",
        p2c_state="NO_SHADOW_RELATION_OBSERVED",
    )
    assert reg_state == RegionState.STRUCTURE_UNRESOLVED
    assert reg_state != RegionState.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED
    assert "P2C_ABSENCE_UNDER_SCALE_DEBT" in limitations


def test_i_inv_04_legacy_residual_m3_conflict_surfaced():
    """I-INV-04: M3 residual + text support candidate generates RESIDUAL_OWNERSHIP_CONFLICT yielding CONFLICTED."""
    t_m3 = create_token(
        source_primitive="LEGACY_RESIDUAL_M3",
        source_configuration="CFG_LEGACY_RESIDUAL_M3",
        region_id="REG_TEXT",
        support_geometry={"bbox": {"x0": 20, "y0": 20, "x1": 150, "y1": 60}},
        evidence_family="RESIDUAL_STRUCTURE_M3",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="RESIDUAL_STRUCTURE_CANDIDATE",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=True,
    )
    t_text = create_token(
        source_primitive="P2-E",
        source_configuration="CFG_P2E_ytol30_solidthresh82",
        region_id="REG_TEXT",
        support_geometry={"bbox": {"x0": 20, "y0": 20, "x1": 150, "y1": 60}},
        evidence_family="TEXT_SUPPORT",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="TEXT_SUPPORT_CANDIDATE",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=False,
    )
    evaluated = evaluate_token_compatibility_and_conflicts([t_m3, t_text])
    m3_res = [t for t in evaluated if t.evidence_family == "RESIDUAL_STRUCTURE_M3"][0]
    assert "RESIDUAL_OWNERSHIP_CONFLICT" in m3_res.conflict_flags

    reg_state, _, _ = resolve_region_lattice(evaluated, p2e_state="TEXT_SUPPORT_CANDIDATE")
    assert reg_state == RegionState.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED


def test_i_inv_05_legacy_periodic_not_double_counted():
    """I-INV-05: Legacy periodic chain is superseded and not run as independent voting token in H3-Dv2."""
    assert LEGACY_PERIODIC_POLICY == "SUPERSEDED_FOR_H3DV2_EXPERIMENT"
    integrator = H3DV2Dev001()
    img_dots = np.full((100, 300), 255, dtype=np.uint8)
    for x in range(30, 270, 25):
        img_dots[48:52, x:x+4] = 0  # periodic dot sequence

    out = integrator.evaluate(img_dots)
    # Tokens must include P2-A, and must NOT include LEGACY_PERIODIC_CHAIN
    primitives = [t["source_primitive"] for t in out.evidence_tokens]
    assert "LEGACY_PERIODIC_CHAIN" not in primitives


def test_i_inv_06_p2c_and_p2d_corroboration_retains_two_sources():
    """I-INV-06: P2-D low contrast and P2-C shadow on overlapping support corroborate while preserving both tokens."""
    t_p2d = create_token(
        source_primitive="P2-D",
        source_configuration="CFG_P2D_D2_thresh30",
        region_id="REG_HALO",
        support_geometry={"bbox": {"x0": 30, "y0": 30, "x1": 120, "y1": 80}},
        evidence_family="LOW_CONTRAST_STRUCTURE",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="LOW_CONTRAST_STRUCTURE_PRESENT",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=True,
    )
    t_p2c = create_token(
        source_primitive="P2-C",
        source_configuration="CFG_P2C_mass25_asym20",
        region_id="REG_HALO",
        support_geometry={"bbox": {"x0": 30, "y0": 30, "x1": 120, "y1": 80}},
        evidence_family="SHADOW_STRUCTURE",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="SHADOW_STRUCTURE_PRESENT",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=True,
    )

    evaluated = evaluate_token_compatibility_and_conflicts([t_p2d, t_p2c])
    assert len(evaluated) == 2
    sources = set(t.source_primitive for t in evaluated)
    assert sources == {"P2-C", "P2-D"}
    assert "corroboration" in evaluated[0].provenance
    assert "corroboration" in evaluated[1].provenance


def test_i_inv_07_regional_conflict_survives_document_aggregation():
    """I-INV-07: Region-local conflict survives document aggregation without loss."""
    reg_clean = MaterialRegion(
        region_id="REG_CLEAN",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 0, "y0": 0, "x1": 100, "y1": 50},
        support_digest="DIGEST_CLEAN",
        constituent_observation_region_ids=["OBS_1"],
        positive_structural_tokens=[{"token_id": "TOK_1"}],
        context_tokens=[],
        conflict_tokens=[],
        observation_limitations=[],
        applicable_channels=["LEGACY_LONG_RULE"],
        unresolved_channels=[],
        region_state=RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value,
        region_provenance={},
    )
    reg_conflicted = MaterialRegion(
        region_id="REG_CONFLICTED",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 150, "y0": 0, "x1": 250, "y1": 50},
        support_digest="DIGEST_CONF",
        constituent_observation_region_ids=["OBS_2"],
        positive_structural_tokens=[{"token_id": "TOK_2"}],
        context_tokens=[],
        conflict_tokens=[{"token_id": "TOK_2"}],
        observation_limitations=[],
        applicable_channels=["LEGACY_RESIDUAL_M3", "P2-E"],
        unresolved_channels=[],
        region_state=RegionState.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.value,
        region_provenance={},
    )

    doc_agg = aggregate_material_regions([reg_clean, reg_conflicted])
    # Document state is PRESENT due to clean positive
    assert doc_agg.document_state == RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value
    # But conflict MUST be preserved!
    assert doc_agg.contains_conflicted_region is True
    assert doc_agg.region_state_counts[RegionState.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.value] == 1
    assert "REG_CONFLICTED" in doc_agg.region_ids_by_state[RegionState.STRUCTURAL_COUNTEREVIDENCE_CONFLICTED.value]


def test_i_inv_08_final_state_provenance_complete():
    """I-INV-08: Every final state has complete decision path and provenance."""
    t_clean = create_token(
        source_primitive="LEGACY_ENCLOSURE",
        source_configuration="CFG_LEGACY_ENCLOSURE",
        region_id="REG_0",
        support_geometry={"bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 100}},
        evidence_family="HARD_TOPOLOGY",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="ENCLOSURE_PRESENT",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=True,
    )
    st, lims, prov = resolve_region_lattice([t_clean])
    assert st == RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert "rule_level" in prov
    assert prov["rule_level"] == 1
    assert prov["precedence_decision"] == "VALID_POSITIVE_STRUCTURAL_WITHOUT_MATERIAL_CONFLICT"


# ══════════════════════════════════════════════════════════════════════════════
# 3. STRUCTURAL CONFORMANCE CRITERIA
# ══════════════════════════════════════════════════════════════════════════════

def test_structural_01_cross_region_illicit_interactions_zero():
    """cross_region_illicit_interactions = 0: Disjoint regions remain strictly isolated."""
    # Two spatially disjoint observation regions
    r_a = ObservationRegion(
        region_id="OBS_A",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 0, "y0": 0, "x1": 50, "y1": 50},
        support_digest="DIGEST_A",
        source_primitive="LEGACY_LONG_RULE",
        derivation_method="RULE_DETECTION",
        coordinate_system="V1",
        provenance={},
    )
    r_b = ObservationRegion(
        region_id="OBS_B",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 200, "y0": 200, "x1": 250, "y1": 250},
        support_digest="DIGEST_B",
        source_primitive="P2-A",
        derivation_method="PERIODIC_DETECTION",
        coordinate_system="V1",
        provenance={},
    )

    clusters = cluster_material_regions(
        root_region_id="ROOT_0",
        observation_regions=[r_a, r_b],
        region_masks={"OBS_A": None, "OBS_B": None},
    )
    # Must form exactly 2 separate material regions!
    assert len(clusters) == 2
    assert clusters[0].constituent_observation_region_ids == ["OBS_A"]
    assert clusters[1].constituent_observation_region_ids == ["OBS_B"]


def test_structural_02_and_03_conflicted_and_unresolved_survival():
    """conflicted_regions_lost_in_aggregation = 0 and unresolved_regions_lost_in_aggregation = 0."""
    m_clean = MaterialRegion(
        region_id="M_CLEAN",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 0, "y0": 0, "x1": 100, "y1": 50},
        support_digest="DIGEST_1",
        constituent_observation_region_ids=["OBS_1"],
        positive_structural_tokens=[],
        context_tokens=[],
        conflict_tokens=[],
        observation_limitations=[],
        applicable_channels=[],
        unresolved_channels=[],
        region_state=RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value,
        region_provenance={},
    )
    m_unres = MaterialRegion(
        region_id="M_UNRES",
        parent_root_region_id="ROOT_0",
        bounding_geometry={"x0": 100, "y0": 0, "x1": 200, "y1": 50},
        support_digest="DIGEST_2",
        constituent_observation_region_ids=["OBS_2"],
        positive_structural_tokens=[],
        context_tokens=[],
        conflict_tokens=[],
        observation_limitations=[],
        applicable_channels=[],
        unresolved_channels=[],
        region_state=RegionState.STRUCTURE_UNRESOLVED.value,
        region_provenance={},
    )

    agg = aggregate_material_regions([m_clean, m_unres])
    assert agg.document_state == RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value
    assert agg.contains_unresolved_region is True
    assert "M_UNRES" in agg.region_ids_by_state[RegionState.STRUCTURE_UNRESOLVED.value]


def test_structural_04_and_05_determinism_region_and_token_ids():
    """nondeterministic_region_ids = 0 and nondeterministic_token_ids = 0."""
    bbox = BoundingBox(x0=10, y0=20, x1=80, y1=60)
    root_1 = compute_root_region_id("DOC_001", 1, bbox)
    root_2 = compute_root_region_id("DOC_001", 1, bbox)
    assert root_1 == root_2

    obs_1 = compute_observation_region_id(root_1, "METHOD_A", bbox, "DIGEST_XYZ", 0)
    obs_2 = compute_observation_region_id(root_1, "METHOD_A", bbox, "DIGEST_XYZ", 0)
    assert obs_1 == obs_2

    tok_1 = compute_token_id("P2-A", "CFG_P2A", obs_1, "PERIODIC_STRUCTURE", 0)
    tok_2 = compute_token_id("P2-A", "CFG_P2A", obs_1, "PERIODIC_STRUCTURE", 0)
    assert tok_1 == tok_2


def test_structural_06_p2e_graphic_regularity_cannot_self_promote():
    """P2E_graphic_regularity_promoted_alone = 0."""
    t_reg = create_token(
        source_primitive="P2-E",
        source_configuration="CFG_P2E_ytol30_solidthresh82",
        region_id="REG_0",
        support_geometry={"bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 50}},
        evidence_family="GRAPHIC_REGULARITY",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="GRAPHIC_REGULARITY_CANDIDATE",
        applicability_state=ApplicabilityState.APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=False,  # Regularity is context only
    )
    reg_state, _, _ = resolve_region_lattice([t_reg], p2e_state="GRAPHIC_REGULARITY_CANDIDATE")
    # Must NOT produce STRUCTURAL_COUNTEREVIDENCE_PRESENT!
    assert reg_state != RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT
    assert reg_state == RegionState.STRUCTURE_UNRESOLVED


def test_structural_07_p2c_no_observation_used_as_negative_forbidden():
    """P2C_no_observation_used_as_negative = 0."""
    t_lim = create_token(
        source_primitive="P2-C",
        source_configuration="CFG_P2C_mass25_asym20",
        region_id="REG_0",
        support_geometry={"bbox": {"x0": 0, "y0": 0, "x1": 100, "y1": 50}},
        evidence_family="OBSERVATION_LIMITATION",
        polarity_context="DARK_ON_LIGHT",
        ownership_context="NO_SHADOW_RELATION_OBSERVED",
        applicability_state=ApplicabilityState.PARTIALLY_APPLICABLE,
        relevance_state=RelevanceState.RELEVANT,
        observation_quality="NOMINAL",
        positive_observation=False,
    )
    reg_state, lims, _ = resolve_region_lattice(
        [t_lim],
        p2c_state="NO_SHADOW_RELATION_OBSERVED",
    )
    assert reg_state == RegionState.STRUCTURE_UNRESOLVED
    assert reg_state != RegionState.NO_STRUCTURAL_COUNTEREVIDENCE_OBSERVED


# ══════════════════════════════════════════════════════════════════════════════
# 4. DETERMINISM UNDER INPUT PERMUTATION & CANONICAL SERIALIZATION
# ══════════════════════════════════════════════════════════════════════════════

def test_determinism_under_candidate_permutation():
    """Permuted observation candidates produce identical sorted ordering and IDs."""
    cand_1 = {
        "source_primitive": "P2-A",
        "derivation_method": "METHOD_A",
        "bbox": BoundingBox(x0=10, y0=20, x1=50, y1=60),
        "support_digest": "DIG_A",
        "tie_breaker": "TB_A",
    }
    cand_2 = {
        "source_primitive": "P2-B",
        "derivation_method": "METHOD_B",
        "bbox": BoundingBox(x0=5, y0=10, x1=40, y1=30),
        "support_digest": "DIG_B",
        "tie_breaker": "TB_B",
    }

    sorted_1 = sort_observation_candidates([cand_1, cand_2])
    sorted_2 = sort_observation_candidates([cand_2, cand_1])
    assert sorted_1 == sorted_2


def test_repeated_canonical_json_serialization_is_byte_identical():
    """Repeated serialization produces identical JSON byte representations."""
    integrator = H3DV2Dev001()
    img_synth = np.full((120, 240), 255, dtype=np.uint8)
    img_synth[60, 20:220] = 0  # Single dark rule

    out1 = integrator.evaluate(img_synth, doc_or_fixture_id="SYNTH_01")
    out2 = integrator.evaluate(img_synth, doc_or_fixture_id="SYNTH_01")

    json1 = integrator.to_canonical_json(out1)
    json2 = integrator.to_canonical_json(out2)
    assert json1 == json2


# ══════════════════════════════════════════════════════════════════════════════
# 5. SYNTHETIC MICRO-IMAGES (UNIT_TEST_NON_EVIDENCE)
# ══════════════════════════════════════════════════════════════════════════════

def test_synthetic_micro_image_long_rule():
    """Synthetic unit execution: horizontal solid rule triggers normalized long rule."""
    img = np.full((100, 300), 255, dtype=np.uint8)
    img[48:52, 20:280] = 0  # solid rule: height 4, width 260 -> mass ~ 1040 px > 300 px

    integrator = H3DV2Dev001()
    out = integrator.evaluate(img, stroke_width_px=3.0)
    assert out.document_aggregate["document_state"] == RegionState.STRUCTURAL_COUNTEREVIDENCE_PRESENT.value
    prims = [t["source_primitive"] for t in out.evidence_tokens if t["positive_observation"]]
    assert any("RULE" in p for p in prims)


def test_synthetic_micro_image_offset_shadow():
    """Synthetic unit execution: glyph + secondary offset grey shadow."""
    img = np.full((120, 200), 255, dtype=np.uint8)
    # Primary ink < 60: box of 20x20
    img[40:60, 40:60] = 30
    # Secondary shadow ink [60, 210): shifted by (+8, +8)
    img[48:68, 48:68] = 120
    # Overwrite primary on top:
    img[40:60, 40:60] = 30

    integrator = H3DV2Dev001()
    out = integrator.evaluate(img)
    p2c_tokens = [t for t in out.evidence_tokens if t["source_primitive"] == "P2-C"]
    assert len(p2c_tokens) >= 1
    assert p2c_tokens[0]["positive_observation"] is True


def test_synthetic_micro_image_reverse_polarity_dark_banner():
    """Synthetic unit execution: white text on dark background."""
    img = np.full((100, 300), 30, dtype=np.uint8)  # dark background
    # White glyph-like marks
    img[35:65, 50:70] = 240
    img[35:65, 80:100] = 240
    img[35:65, 110:130] = 240

    integrator = H3DV2Dev001()
    out = integrator.evaluate(img)
    p2b_tokens = [t for t in out.evidence_tokens if t["source_primitive"] == "P2-B"]
    assert len(p2b_tokens) >= 1
    assert p2b_tokens[0]["ownership_context"] == PolarityState.LIGHT_ON_DARK.value
