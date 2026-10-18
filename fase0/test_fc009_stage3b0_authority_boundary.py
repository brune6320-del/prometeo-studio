"""
PROMETEO · FC-009 STAGE 3B-0 · DECISION AUTHORITY BOUNDARY CONTRACT
───────────────────────────────────────────────────────────────────
RED CONTRACT FOR AUTHORITY PRECONDITIONS (DENY BY DEFAULT)

Metodología:
  RED CONTRACT CREATED BEFORE STAGE 3B PRODUCTION IMPLEMENTATION.
  Stage 3B-0:
    ELIGIBLE = YES
    REACHED = IN_PROGRESS (RED CONTRACT)
    PRODUCTION IMPLEMENTATION = NOT_STARTED
    DECISION AUTHORITY = NONE (ALWAYS)

Principios Arquitectónicos Congelados:
  1. Separación de niveles:
     EVIDENCE (Stage 3A-4)
       ↓
     AUTHORITY PRECONDITIONS (Stage 3B-0)
       ↓
     AUTHORITY DECISION (Future Stage 3B)
       ↓
     RUNTIME ACTION (Future Stage 3B)
  2. Deny by default:
     NO_EVIDENCE / INSUFFICIENT / PARTIAL / CONFLICTED / UNKNOWN => NONE.
     El estado por defecto siempre es decision_authority = 'NONE'.
  3. Lo que ya sabemos que no basta (no autoriza por sí solo):
     - TEXT_OPERATOR provenance alone
     - VECTOR_PATH absence
     - clean OCR token
     - dictionary / lexical coherence
     - font metric consistency
     - repeated-X alignment
     - local raster morphology
     - absence of graphic continuity
  4. UNIVERSAL_POSITIVE_TEXT_EVIDENCE_VALIDATED = NO.
     Conclusión actual: NO_AUTHORIZED_POSITIVE_RULE_AVAILABLE_YET = YES.
  5. PROHIBICIÓN ESTRICTA:
     - NO TEXT_COMPATIBLE
     - NO STRONG
     - NO SAFE_TO_CLEAR
     - NO ALLOW_WRITE
     - NO scores / probabilities / confidence 0-1
     - NO runtime integration.

Inventario de Tests (AB-01 a AB-20):
  AB-01 · API existence contract;
  AB-02 · Insufficient evidence denies authority;
  AB-03 · Partial evidence denies authority;
  AB-04 · Conflicted evidence denies authority;
  AB-05 · TEXT_OPERATOR alone denies authority;
  AB-06 · Clean OCR alone denies authority;
  AB-07 · Lexical coherence alone denies authority;
  AB-08 · Font metrics alone denies authority;
  AB-09 · Absence of graphic counterevidence does not confer authority;
  AB-10 · Graphic counterevidence present denies authority;
  AB-11 · UNKNOWN provenance denies authority;
  AB-12 · IMAGE_RASTER ambiguous denies authority;
  AB-13 · semantic_claim UNRESOLVED blocks authority;
  AB-14 · NO_VALIDATED_POSITIVE_TEXT_SIGNAL blocker;
  AB-15 · Current-evidence saturation test (all available signals => NONE);
  AB-16 · Deterministic output;
  AB-17 · JSON-safe serialization;
  AB-18 · TEXT_COMPATIBLE strictly not emitted;
  AB-19 · STRONG strictly not emitted;
  AB-20 · Runtime authority absent.
"""
import json
import pytest

import verifier2


def _call_authority_preconditions(*args, **kwargs) -> dict:
    """Invoca evaluate_stage3_authority_preconditions desde verifier2.

    Falla como EXPECTED_AUTHORITY_BOUNDARY_RED mientras la función
    no esté implementada en verifier2.py.
    """
    evaluator = getattr(verifier2, "evaluate_stage3_authority_preconditions", None)
    assert evaluator is not None, (
        "Stage 3B-0 RED: evaluate_stage3_authority_preconditions debe existir en verifier2"
    )
    assert callable(evaluator), "evaluate_stage3_authority_preconditions debe ser invocable"
    return evaluator(*args, **kwargs)


def _call_evidence_state(*args, **kwargs) -> dict:
    """Helper para construir el evidence state desde verifier2."""
    builder = getattr(verifier2, "build_stage3_evidence_state", None)
    assert builder is not None, "build_stage3_evidence_state debe existir en verifier2"
    return builder(*args, **kwargs)


# ── AB-01 · API EXISTENCE ────────────────────────────────────────────────────

def test_ab_01_api_existence():
    """AB-01 (RED): evaluate_stage3_authority_preconditions debe existir en verifier2."""
    evaluator = getattr(verifier2, "evaluate_stage3_authority_preconditions", None)
    assert evaluator is not None, (
        "Stage 3B-0 RED: evaluate_stage3_authority_preconditions no existe aún en verifier2"
    )
    assert callable(evaluator)


# ── AB-02 · INSUFFICIENT EVIDENCE DENIES AUTHORITY ───────────────────────────

def test_ab_02_insufficient_evidence_denies_authority():
    """AB-02 (RED): Evidencia INSUFFICIENT debe producir authority_candidate=False y decision_authority=NONE."""
    ev = _call_evidence_state(None)
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert res["authority_level"] == "NONE"
    assert "EVIDENCE_INSUFFICIENT" in res["blocking_reasons"]


# ── AB-03 · PARTIAL EVIDENCE DENIES AUTHORITY ────────────────────────────────

def test_ab_03_partial_evidence_denies_authority():
    """AB-03 (RED): Evidencia PARTIAL aislada no alcanza autoridad."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "TEXT_OPERATOR"})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["blocking_reasons"]


# ── AB-04 · CONFLICTED EVIDENCE DENIES AUTHORITY ─────────────────────────────

def test_ab_04_conflicted_evidence_denies_authority():
    """AB-04 (RED): Evidencia CONFLICTED bloquea incondicionalmente la autoridad."""
    ev = _call_evidence_state(
        provenance_info={"source_representation_class": "TEXT_OPERATOR"},
        context_observations={"vertical_continuity_crossing_leading": True}
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert res["conflict_present"] is True
    assert "EVIDENCE_CONFLICTED" in res["blocking_reasons"]


# ── AB-05 · TEXT_OPERATOR ALONE DENIES AUTHORITY ─────────────────────────────

def test_ab_05_text_operator_alone_denies_authority():
    """AB-05 (RED): Provenance TEXT_OPERATOR sola no otorga autoridad."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "TEXT_OPERATOR"})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert (
        "REPRESENTATION_ONLY" in res["blocking_reasons"]
        or "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["blocking_reasons"]
    )


# ── AB-06 · CLEAN OCR ALONE DENIES AUTHORITY ─────────────────────────────────

def test_ab_06_clean_ocr_alone_denies_authority():
    """AB-06 (RED): Lectura limpia OCR aislada no otorga autoridad."""
    ev = _call_evidence_state(
        provenance_info={"source_representation_class": "IMAGE_RASTER"},
        context_observations={"language_context_candidate": "TITULO"}
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"


# ── AB-07 · LEXICAL COHERENCE ALONE DENIES AUTHORITY ─────────────────────────

def test_ab_07_lexical_coherence_alone_denies_authority():
    """AB-07 (RED): Coherencia léxica / diccionario aislada no otorga autoridad."""
    ev = _call_evidence_state(
        context_observations={"language_context_candidate": "DICTIONARY_COHERENT_SPANISH"}
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"


# ── AB-08 · FONT METRICS ALONE DENIES AUTHORITY ──────────────────────────────

def test_ab_08_font_metrics_alone_denies_authority():
    """AB-08 (RED): Modulación de clusters / métricas de fuente solas no otorgan autoridad."""
    ev = _call_evidence_state(features={"cluster_modulation_ratio": 1.5})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"


# ── AB-09 · ABSENCE OF GRAPHIC COUNTEREVIDENCE != POSITIVE AUTHORITY ─────────

def test_ab_09_absence_of_graphic_counterevidence_not_positive_authority():
    """AB-09 (RED): Ausencia de contraevidencia gráfica no equivale a autoridad positiva."""
    ev = _call_evidence_state(
        context_observations={
            "vertical_continuity_crossing_leading": False,
            "orthogonal_grid_junction": False
        }
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert (
        res["ambiguity_present"] is True
        or "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["blocking_reasons"]
    )


# ── AB-10 · GRAPHIC COUNTEREVIDENCE PRESENT DENIES AUTHORITY ─────────────────

def test_ab_10_graphic_counterevidence_present_denies_authority():
    """AB-10 (RED): Presencia de contraevidencia gráfica bloquea autoridad."""
    ev = _call_evidence_state(
        context_observations={"vertical_continuity_crossing_leading": True}
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert "GRAPHIC_COUNTEREVIDENCE_PRESENT" in res["blocking_reasons"]


# ── AB-11 · UNKNOWN PROVENANCE DENIES AUTHORITY ──────────────────────────────

def test_ab_11_unknown_provenance_denies_authority():
    """AB-11 (RED): Procedencia UNKNOWN deniega autoridad."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "UNKNOWN"})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"


# ── AB-12 · IMAGE_RASTER AMBIGUOUS DENIES AUTHORITY ──────────────────────────

def test_ab_12_image_raster_ambiguous_denies_authority():
    """AB-12 (RED): Raster ambiguo deniega autoridad por origen de autoría inaccesible."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "IMAGE_RASTER"})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert "AUTHORING_ORIGIN_UNAVAILABLE" in res["blocking_reasons"]


# ── AB-13 · SEMANTIC_CLAIM UNRESOLVED BLOCKS AUTHORITY ───────────────────────

def test_ab_13_semantic_claim_unresolved_blocks_authority():
    """AB-13 (RED): semantic_claim=UNRESOLVED bloquea la concesión de autoridad."""
    ev = _call_evidence_state(features={"cluster_modulation_ratio": 2.0})
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert "SEMANTIC_CLAIM_UNRESOLVED" in res["blocking_reasons"]


# ── AB-14 · NO_VALIDATED_POSITIVE_TEXT_SIGNAL BLOCKER ────────────────────────

def test_ab_14_no_validated_positive_text_signal_blocker():
    """AB-14 (RED): Ausencia de regla positiva validada debe registrarse en blocking_reasons."""
    ev = _call_evidence_state(
        features={"cluster_modulation_ratio": 2.0},
        provenance_info={"source_representation_class": "TEXT_OPERATOR"}
    )
    res = _call_authority_preconditions(ev)

    assert "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["blocking_reasons"]
    assert "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["positive_requirements_missing"]


# ── AB-15 · CURRENT-EVIDENCE SATURATION TEST ─────────────────────────────────

def test_ab_15_current_evidence_saturation_test():
    """AB-15 (RED): Saturación con todas las señales favorables disponibles aún deniega autoridad.

    Este test es crucial: demuestra que ni siquiera acumulando TEXT_OPERATOR,
    OCR limpio, modulación de clusters y ausencia de gráfico se puede conceder
    autoridad mientras NO_VALIDATED_POSITIVE_TEXT_SIGNAL siga vigente.
    """
    ev = _call_evidence_state(
        features={
            "cluster_modulation_ratio": 2.0,
            "max_cc_aspect_ratio": 5.0
        },
        provenance_info={
            "source_representation_class": "TEXT_OPERATOR",
            "render_mode": 0
        },
        context_observations={
            "vertical_continuity_crossing_leading": False,
            "orthogonal_grid_junction": False,
            "repeated_x_alignment": False,
            "language_context_candidate": "SPANISH_LEXICON"
        }
    )
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert "NO_VALIDATED_POSITIVE_TEXT_SIGNAL" in res["blocking_reasons"]


# ── AB-16 · DETERMINISTIC OUTPUT ─────────────────────────────────────────────

def test_ab_16_deterministic_output():
    """AB-16 (RED): Invocaciones sucesivas con idéntico evidence state producen idéntica salida."""
    ev = _call_evidence_state(features={"cluster_modulation_ratio": 1.0})
    res1 = _call_authority_preconditions(ev)
    res2 = _call_authority_preconditions(ev)

    assert res1 == res2


# ── AB-17 · JSON-SAFE SERIALIZATION ──────────────────────────────────────────

def test_ab_17_json_safe_serialization():
    """AB-17 (RED): El output de preconditions debe ser estrictamente serializable a JSON."""
    ev = _call_evidence_state(features={"cluster_modulation_ratio": 1.0})
    res = _call_authority_preconditions(ev)

    dumped = json.dumps(res, allow_nan=False)
    loaded = json.loads(dumped)
    assert loaded == res


# ── AB-18 · TEXT_COMPATIBLE NOT EMITTED ──────────────────────────────────────

def test_ab_18_text_compatible_not_emitted():
    """AB-18 (RED): El término TEXT_COMPATIBLE está estrictamente ausente del resultado."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "TEXT_OPERATOR"})
    res = _call_authority_preconditions(ev)

    dumped = json.dumps(res)
    assert "TEXT_COMPATIBLE" not in dumped


# ── AB-19 · STRONG NOT EMITTED ───────────────────────────────────────────────

def test_ab_19_strong_not_emitted():
    """AB-19 (RED): El término STRONG está estrictamente ausente del resultado."""
    ev = _call_evidence_state(provenance_info={"source_representation_class": "TEXT_OPERATOR"})
    res = _call_authority_preconditions(ev)

    dumped = json.dumps(res)
    assert "STRONG" not in dumped


# ── AB-20 · RUNTIME AUTHORITY ABSENT ─────────────────────────────────────────

def test_ab_20_runtime_authority_absent():
    """AB-20 (RED): La evaluación de precondiciones no confiere autoridad de ejecución runtime."""
    ev = _call_evidence_state()
    res = _call_authority_preconditions(ev)

    assert res["authority_candidate"] is False
    assert res["decision_authority"] == "NONE"
    assert res["authority_level"] == "NONE"
    assert (
        "RUNTIME_INTEGRATION_FORBIDDEN" in res["blocking_reasons"]
        or res["decision_authority"] == "NONE"
    )
