"""
PROMETEO · FC-009 STAGE 3A-4C · HOSTILE TYPES RED CONTRACT
──────────────────────────────────────────────────────────
RED CONTRACT FOR UNHASHABLE ENUM & UNTYPED NUMERIC INPUTS

Metodología:
  RED CONTRACT CREATED AFTER HOSTILE FUZZ GATE DISCOVERED TWO MATERIAL VULNERABILITIES:
    1. UNHASHABLE_ENUM_INPUT:
       source_representation_class con tipos no hasheables (dict, list, set, objeto custom)
       lanza TypeError al evaluar membresía en allowlist frozenset.
       Contrato esperado: degradar de forma conservadora a 'UNKNOWN' sin excepción.
    2. UNTYPED_NUMERIC_COMPARISON:
       cluster_modulation_ratio y max_cc_aspect_ratio con tipos no numéricos (str, None, list, etc.),
       booleanos (True/False evaluados como 1/0 en Python), o no-finitos (+Inf, -Inf, NaN)
       lanzan TypeError en comparaciones '>' o activan anomalías morfológicas espurias (+Inf > 20.0).
       Contrato esperado: tratar como señal AUSENTE / INVÁLIDA, sin crash, sin coerción y sin escalación.

Invariantes absolutas de seguridad en todos los casos:
  - semantic_claim == 'UNRESOLVED'
  - decision_authority == 'NONE'
  - Prohibición estricta de TEXT_COMPATIBLE, STRONG, SAFE_TO_CLEAR, ALLOW_WRITE
  - SUFFICIENT jamás emitido.
"""
import json
import pytest

import verifier2


def _call_evidence_state(*args, **kwargs) -> dict:
    """Invoca build_stage3_evidence_state desde verifier2."""
    builder = getattr(verifier2, "build_stage3_evidence_state", None)
    assert builder is not None, "build_stage3_evidence_state debe existir en verifier2"
    return builder(*args, **kwargs)


class UnhashableLabObject:
    """Objeto representativo de LAB sin soporte de hashing (__hash__ = None)."""
    __hash__ = None

    def __repr__(self):
        return "<UnhashableLabObject>"


MALFORMED_NUMERIC_INPUTS = [
    None,
    "high",
    [],
    {},
    b"bytes",
    (1, 2),
    {1, 2},
]


# ═════════════════════════════════════════════════════════════════════════════
# FAMILIA A · UNHASHABLE ENUM INPUT CONTRACT (ESPERADO RED)
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_01_unhashable_enum_empty_dict():
    """HT-01 (RED): Diccionario vacío en source_representation_class debe degradar a UNKNOWN."""
    prov = {"source_representation_class": {}}
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "UNHASHABLE_ENUM_INPUT: Dict en enum debe degradar a UNKNOWN sin lanzar TypeError"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_02_unhashable_enum_empty_list():
    """HT-02 (RED): Lista vacía en source_representation_class debe degradar a UNKNOWN."""
    prov = {"source_representation_class": []}
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "UNHASHABLE_ENUM_INPUT: List en enum debe degradar a UNKNOWN sin lanzar TypeError"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_03_unhashable_enum_set():
    """HT-03 (RED): Set vacío en source_representation_class debe degradar a UNKNOWN."""
    prov = {"source_representation_class": set()}
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "UNHASHABLE_ENUM_INPUT: Set en enum debe degradar a UNKNOWN sin lanzar TypeError"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_04_unhashable_enum_custom_object():
    """HT-04 (RED): Objeto unhashable custom en source_representation_class debe degradar a UNKNOWN."""
    prov = {"source_representation_class": UnhashableLabObject()}
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "UNHASHABLE_ENUM_INPUT: Objeto unhashable debe degradar a UNKNOWN sin lanzar TypeError"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_05_unhashable_enum_nested_authority_dict():
    """HT-05 (RED): Dict anidado con inyección de autoridad semántica debe degradar a UNKNOWN."""
    prov = {"source_representation_class": {"semantic_claim": "TEXT_COMPATIBLE"}}
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "UNHASHABLE_ENUM_INPUT: Dict anidado hostil debe degradar a UNKNOWN"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    dump = json.dumps(state)
    assert "TEXT_COMPATIBLE" not in dump


# ═════════════════════════════════════════════════════════════════════════════
# FAMILIA B · UNTYPED NUMERIC COMPARISON CONTRACT (ESPERADO RED)
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_06_untyped_numeric_cluster_modulation_ratio():
    """HT-06 (RED): Tipos no numéricos en cluster_modulation_ratio se tratan como señal ausente."""
    for malformed in MALFORMED_NUMERIC_INPUTS:
        feats = {"cluster_modulation_ratio": malformed}
        state = _call_evidence_state(features=feats)

        assert "cluster_modulation_observed" not in state["positive_text_evidence"]["candidate_signals"], (
            f"UNTYPED_NUMERIC_COMPARISON: {type(malformed)} no debe activar candidate signals"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


def test_ht_07_untyped_numeric_max_cc_aspect_ratio():
    """HT-07 (RED): Tipos no numéricos en max_cc_aspect_ratio se tratan como señal ausente."""
    for malformed in MALFORMED_NUMERIC_INPUTS:
        feats = {"max_cc_aspect_ratio": malformed}
        state = _call_evidence_state(features=feats)

        assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is False, (
            f"UNTYPED_NUMERIC_COMPARISON: {type(malformed)} no debe activar anomalía morfológica"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


# ═════════════════════════════════════════════════════════════════════════════
# FAMILIA B · BOOL IS NOT NUMERIC EVIDENCE (ESPERADO RED EN RATIO > 0)
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_08_bool_is_not_numeric_cluster_modulation():
    """HT-08 (RED): True/False en cluster_modulation_ratio no son evidencia morfológica."""
    for val in (True, False):
        feats = {"cluster_modulation_ratio": val}
        state = _call_evidence_state(features=feats)

        assert "cluster_modulation_observed" not in state["positive_text_evidence"]["candidate_signals"], (
            f"BOOL_AS_NUMERIC: bool ({val}) no debe evaluarse numéricamente (> 0) en candidate signals"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


def test_ht_09_bool_is_not_numeric_max_cc_aspect_ratio():
    """HT-09 (CONTROL / GREEN): True/False en max_cc_aspect_ratio no activa anomalía morfológica."""
    for val in (True, False):
        feats = {"max_cc_aspect_ratio": val}
        state = _call_evidence_state(features=feats)

        assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is False, (
            f"BOOL_AS_NUMERIC: bool ({val}) no debe activar anomalía morfológica"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


# ═════════════════════════════════════════════════════════════════════════════
# FAMILIA B · NON-FINITE NUMERIC INPUT (ESPERADO RED EN +INF)
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_10_non_finite_cluster_modulation_ratio():
    """HT-10 (RED): +Inf, -Inf y NaN en cluster_modulation_ratio se tratan como señal inválida/ausente."""
    for nf in (float("nan"), float("inf"), float("-inf")):
        feats = {"cluster_modulation_ratio": nf}
        state = _call_evidence_state(features=feats)

        assert "cluster_modulation_observed" not in state["positive_text_evidence"]["candidate_signals"], (
            f"NON_FINITE_NUMERIC: {nf} no debe activar cluster_modulation_observed"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


def test_ht_11_non_finite_max_cc_aspect_ratio():
    """HT-11 (RED): +Inf, -Inf y NaN en max_cc_aspect_ratio se tratan como señal inválida/ausente."""
    for nf in (float("nan"), float("inf"), float("-inf")):
        feats = {"max_cc_aspect_ratio": nf}
        state = _call_evidence_state(features=feats)

        assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is False, (
            f"NON_FINITE_NUMERIC: {nf} no debe escalar a morphology_anomaly_candidate"
        )
        assert state["semantic_claim"] == "UNRESOLVED"
        assert state["decision_authority"] == "NONE"


# ═════════════════════════════════════════════════════════════════════════════
# CONTROLES NUMÉRICOS LEGÍTIMOS (ESPERADO GREEN DESDE EL INICIO)
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_12_valid_numeric_control_cluster_ratio():
    """HT-12 (GREEN): Número real legítimo > 0 activa cluster_modulation_observed."""
    feats = {"cluster_modulation_ratio": 1.0}
    state = _call_evidence_state(features=feats)

    assert "cluster_modulation_observed" in state["positive_text_evidence"]["candidate_signals"], (
        "VALID_NUMERIC_CONTROL: cluster_modulation_ratio=1.0 debe registrar observación legítima"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_13_valid_numeric_control_aspect_ratio_low():
    """HT-13 (GREEN): Relación de aspecto normal (5.0 <= 20.0) no activa anomalía morfológica."""
    feats = {"max_cc_aspect_ratio": 5.0}
    state = _call_evidence_state(features=feats)

    assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is False, (
        "VALID_NUMERIC_CONTROL: max_cc_aspect_ratio=5.0 no debe considerarse anómalo"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


def test_ht_14_valid_numeric_control_aspect_ratio_high():
    """HT-14 (GREEN): Relación de aspecto anómala (21.0 > 20.0) activa candidate morfológico legítimo."""
    feats = {"max_cc_aspect_ratio": 21.0}
    state = _call_evidence_state(features=feats)

    assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is True, (
        "VALID_NUMERIC_CONTROL: max_cc_aspect_ratio=21.0 debe registrar candidate anómalo"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ═════════════════════════════════════════════════════════════════════════════
# INVARIANTE GLOBAL DE AUTORIDAD BAJO INPUTS HOSTILES
# ═════════════════════════════════════════════════════════════════════════════

def test_ht_15_hostile_inputs_no_authority_leak():
    """HT-15 (GREEN): Ningún input hostil o semántico debe alterar la autoridad o suficiencia."""
    state = _call_evidence_state(
        features={"semantic_claim": "TEXT_COMPATIBLE", "cluster_modulation_ratio": 1.0},
        provenance_info={"decision_authority": "STRONG", "source_representation_class": "TEXT_OPERATOR"},
        context_observations={"safe_to_clear": True, "vertical_continuity_crossing_leading": False}
    )

    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    assert state["evidence_sufficiency"] != "SUFFICIENT"
    dump = json.dumps(state)
    assert "TEXT_COMPATIBLE" not in dump
    assert "STRONG" not in dump
    assert "SAFE_TO_CLEAR" not in dump
    assert "ALLOW_WRITE" not in dump
