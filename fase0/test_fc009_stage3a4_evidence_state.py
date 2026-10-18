"""
PROMETEO · FC-009 STAGE 3A-4 · EVIDENCE STATE CONTRACT TESTS
─────────────────────────────────────────────────────────────
RED CONTRACT FOR OBSERVATIONAL EVIDENCE STATE REPRESENTATION

Metodología:
  RED TESTS DEFINED BEFORE PRODUCTION IMPLEMENTATION.
  Stage 3A-4 al crear este archivo:
    ELIGIBLE = YES
    REACHED = IN_PROGRESS (RED CONTRACT)
    PRODUCTION IMPLEMENTATION = NOT_STARTED
    DECISION AUTHORITY = NONE (ALWAYS)

Principios Arquitectónicos Congelados:
  1. No colapsar OBSERVATION con SEMANTIC CLAIM ni con DECISION AUTHORITY.
  2. Cuatro dimensiones independientes:
     A. positive_text_evidence
     B. graphic_counterevidence
     C. representation_provenance
     D. evidence_sufficiency / ambiguity
  3. SEMANTIC_CLAIM = UNRESOLVED en todos los estados.
  4. DECISION_AUTHORITY = NONE en todos los estados.
  5. PROHIBICIÓN ESTRICTA:
     - NO TEXT_COMPATIBLE
     - NO STRONG
     - NO graphics_clearance mutation
     - NO runtime policy mutation
     - NO thresholds normativos
     - NO ML / probabilities / scores universales 0-1.

Inventario de Tests:
  ES-01 · API existence contract;
  ES-02 · Text operator representation does not imply semantic text;
  ES-03 · Vector path representation does not imply semantic graphic;
  ES-04 · Outlined text remains unresolved with authoring origin unavailable;
  ES-05 · OCR sandwich conflict represented explicitly;
  ES-06 · Raster representation marks authoring origin unavailable;
  ES-07 · Cross-line continuity registers graphic counterevidence only;
  ES-08 · Grid junction registers graphic counterevidence only;
  ES-09 · Repeated-X alone does not escalate to graphic counterevidence;
  ES-10 · Morphology anomaly alone does not escalate without normative threshold;
  ES-11 · Insufficient evidence preserves unresolved state and marks ambiguity;
  ES-12 · Conflicting evidence preserves unresolved state;
  ES-13 · decision_authority is unconditionally NONE across all inputs;
  ES-14 · TEXT_COMPATIBLE is strictly absent from all schema outputs;
  ES-15 · STRONG is strictly absent from all schema outputs;
  ES-16 · Exact determinism: identical inputs produce identical output;
  ES-17 · JSON serialization safety across all evidence state dictionaries.
"""
import json
import pytest

import verifier2


def _call_evidence_state(*args, **kwargs) -> dict:
    """Helper de invocación para el contrato Stage 3A-4.

    Falla como EXPECTED_CONTRACT_RED mientras build_stage3_evidence_state
    no esté implementada en verifier2.py.
    """
    builder = getattr(verifier2, "build_stage3_evidence_state", None)
    assert builder is not None, (
        "Stage 3A-4 RED: build_stage3_evidence_state no existe aún en verifier2.py"
    )
    assert callable(builder), "build_stage3_evidence_state debe ser invocable"
    return builder(*args, **kwargs)


# ── ES-01 · API EXISTENCE ────────────────────────────────────────────────────

def test_es_01_api_exists_in_verifier2():
    """ES-01: Verifica que verifier2 defina la función build_stage3_evidence_state."""
    builder = getattr(verifier2, "build_stage3_evidence_state", None)
    assert builder is not None, (
        "Stage 3A-4 RED: build_stage3_evidence_state debe estar definida en verifier2"
    )
    assert callable(builder), "build_stage3_evidence_state debe ser una función invocable"


# ── ES-02 · TEXT OPERATOR DOES NOT IMPLY SEMANTIC TEXT ───────────────────────

def test_es_02_text_operator_does_not_imply_semantic_text():
    """ES-02: La representación TEXT_OPERATOR no debe forzar semantic_claim=TEXT."""
    prov = {
        "source_representation_class": "TEXT_OPERATOR",
        "font_name": "Helvetica",
        "render_mode": 0
    }
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "TEXT_OPERATOR"
    assert state["semantic_claim"] == "UNRESOLVED", (
        "TEXT_OPERATOR no debe implicar semantic_claim=TEXT (falsificado por OCR sandwich)"
    )
    assert state["decision_authority"] == "NONE"


# ── ES-03 · VECTOR PATH DOES NOT IMPLY SEMANTIC GRAPHIC ──────────────────────

def test_es_03_vector_path_does_not_imply_semantic_graphic():
    """ES-03: La representación VECTOR_PATH_OPERATOR no debe forzar semantic_claim=GRAPHIC."""
    prov = {
        "source_representation_class": "VECTOR_PATH_OPERATOR",
        "operator": "re"
    }
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "VECTOR_PATH_OPERATOR"
    assert state["semantic_claim"] == "UNRESOLVED", (
        "VECTOR_PATH_OPERATOR no debe implicar semantic_claim=GRAPHIC (falsificado por outlined text)"
    )
    assert state["decision_authority"] == "NONE"


# ── ES-04 · OUTLINED TEXT REMAINS UNRESOLVED ─────────────────────────────────

def test_es_04_outlined_text_remains_unresolved():
    """ES-04: Texto convertido a curvas (outlines) debe permanecer unresolved sin inventar origen."""
    prov = {
        "source_representation_class": "VECTOR_PATH_OPERATOR",
        "vector_item_type": "curve_outline"
    }
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["authoring_origin"] in (
        "UNAVAILABLE", "OUTLINED_OR_UNKNOWN"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-05 · OCR SANDWICH CONFLICT REPRESENTED ────────────────────────────────

def test_es_05_ocr_sandwich_conflict_represented():
    """ES-05: PDF sandwich (capa OCR invisible sobre imagen) debe registrar conflicto de evidencia."""
    prov = {
        "source_representation_class": "MIXED",
        "has_invisible_text_layer": True,
        "has_underlying_image": True
    }
    state = _call_evidence_state(provenance_info=prov)

    assert state["evidence_conflict"] is True
    assert state["evidence_sufficiency"] in ("CONFLICTED", "PARTIAL")
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-06 · RASTER AUTHORING ORIGIN UNAVAILABLE ──────────────────────────────

def test_es_06_raster_authoring_origin_unavailable():
    """ES-06: Documento escaneado/raster debe reportar origen de autoría UNAVAILABLE."""
    prov = {
        "source_representation_class": "IMAGE_RASTER"
    }
    state = _call_evidence_state(provenance_info=prov)

    assert state["representation_provenance"]["source_representation_class"] == "IMAGE_RASTER"
    assert state["representation_provenance"]["authoring_origin"] == "UNAVAILABLE"
    assert state["representation_provenance"]["is_raster_only"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-07 · CROSS-LINE CONTINUITY REGISTERS COUNTEREVIDENCE ONLY ─────────────

def test_es_07_cross_line_continuity_registers_counterevidence_only():
    """ES-07: Continuidad vertical que cruza interlineado es counterevidence, no prueba semántica."""
    obs = {
        "vertical_continuity_crossing_leading": True
    }
    state = _call_evidence_state(context_observations=obs)

    assert state["graphic_counterevidence"]["present"] is True
    assert state["graphic_counterevidence"]["vertical_continuity_crossing_leading"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-08 · GRID JUNCTION REGISTERS COUNTEREVIDENCE ONLY ─────────────────────

def test_es_08_grid_junction_registers_counterevidence_only():
    """ES-08: Uniones ortogonales de cuadrícula registran counterevidence sin decisión semántica."""
    obs = {
        "orthogonal_grid_junction": True
    }
    state = _call_evidence_state(context_observations=obs)

    assert state["graphic_counterevidence"]["present"] is True
    assert state["graphic_counterevidence"]["orthogonal_grid_junction"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-09 · REPEATED-X ALONE DOES NOT ESCALATE ───────────────────────────────

def test_es_09_repeated_x_alone_does_not_escalate():
    """ES-09: Alineación repetida en X aislada no debe elevarse a counterevidence afirmativa."""
    obs = {
        "repeated_x_alignment": True,
        "vertical_continuity_crossing_leading": False
    }
    state = _call_evidence_state(context_observations=obs)

    assert state["graphic_counterevidence"]["repeated_x_alignment"] is True
    assert state["graphic_counterevidence"]["present"] is False
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-10 · MORPHOLOGY ANOMALY ALONE DOES NOT ESCALATE ───────────────────────

def test_es_10_morphology_anomaly_alone_does_not_escalate():
    """ES-10: Alto aspect ratio morfológico solo se registra como anomalía, sin umbral normativo."""
    feats = {
        "max_cc_aspect_ratio": 25.0
    }
    obs = {
        "morphology_anomaly_observed": True
    }
    state = _call_evidence_state(features=feats, context_observations=obs)

    assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    assert "normative_threshold" not in state["graphic_counterevidence"]


# ── ES-11 · INSUFFICIENT EVIDENCE PRESERVES UNRESOLVED ────────────────────────

def test_es_11_insufficient_evidence_preserves_unresolved():
    """ES-11: Elemento aislado sin contexto ni procedencia vectorial preserva ambigüedad."""
    prov = {
        "source_representation_class": "IMAGE_RASTER"
    }
    obs = {
        "vertical_continuity_crossing_leading": False,
        "orthogonal_grid_junction": False
    }
    state = _call_evidence_state(provenance_info=prov, context_observations=obs)

    assert state["evidence_sufficiency"] in ("INSUFFICIENT", "PARTIAL")
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-12 · CONFLICTING EVIDENCE PRESERVES UNRESOLVED ────────────────────────

def test_es_12_conflicting_evidence_preserves_unresolved():
    """ES-12: Coexistencia de TEXT_OPERATOR y continuidad gráfica preserva UNRESOLVED sin elegir."""
    prov = {
        "source_representation_class": "TEXT_OPERATOR"
    }
    obs = {
        "vertical_continuity_crossing_leading": True
    }
    state = _call_evidence_state(provenance_info=prov, context_observations=obs)

    assert state["evidence_conflict"] is True
    assert state["evidence_sufficiency"] in ("CONFLICTED", "PARTIAL")
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ES-13 · DECISION AUTHORITY ALWAYS NONE ───────────────────────────────────

def test_es_13_decision_authority_always_none():
    """ES-13: decision_authority debe ser estrictamente NONE en cualquier combinación de inputs."""
    scenarios = [
        {"provenance_info": {"source_representation_class": "TEXT_OPERATOR"}},
        {"provenance_info": {"source_representation_class": "VECTOR_PATH_OPERATOR"}},
        {"provenance_info": {"source_representation_class": "IMAGE_RASTER"}},
        {"context_observations": {"vertical_continuity_crossing_leading": True}},
        {"context_observations": {"orthogonal_grid_junction": True}},
        {}
    ]
    for sc in scenarios:
        state = _call_evidence_state(**sc)
        assert state["decision_authority"] == "NONE", (
            f"Fallo en escenario {sc}: decision_authority debe ser estrictamente NONE"
        )


# ── ES-14 · TEXT_COMPATIBLE ABSENT ───────────────────────────────────────────

def test_es_14_text_compatible_absent():
    """ES-14: TEXT_COMPATIBLE no debe figurar en ningún valor ni clave de la estructura."""
    scenarios = [
        {"provenance_info": {"source_representation_class": "TEXT_OPERATOR"}},
        {"context_observations": {"vertical_continuity_crossing_leading": False}},
        {}
    ]
    for sc in scenarios:
        state = _call_evidence_state(**sc)
        dump = json.dumps(state)
        assert "TEXT_COMPATIBLE" not in dump, (
            "TEXT_COMPATIBLE está estrictamente prohibido en Stage 3A-4"
        )


# ── ES-15 · STRONG ABSENT ────────────────────────────────────────────────────

def test_es_15_strong_absent():
    """ES-15: La etiqueta STRONG no debe figurar en ningún valor ni clave de la estructura."""
    scenarios = [
        {"provenance_info": {"source_representation_class": "TEXT_OPERATOR"}},
        {"context_observations": {"vertical_continuity_crossing_leading": True}},
        {}
    ]
    for sc in scenarios:
        state = _call_evidence_state(**sc)
        dump = json.dumps(state)
        assert "STRONG" not in dump, (
            "STRONG está estrictamente prohibido como etiqueta de autoridad en Stage 3A-4"
        )


# ── ES-16 · DETERMINISTIC REPEATED EXECUTION ─────────────────────────────────

def test_es_16_deterministic_repeated_execution():
    """ES-16: Ejecuciones sucesivas con idénticos parámetros deben producir exactamente el mismo dict."""
    kwargs = {
        "features": {"max_cc_aspect_ratio": 12.0, "connected_components_count": 2},
        "provenance_info": {"source_representation_class": "TEXT_OPERATOR"},
        "context_observations": {"vertical_continuity_crossing_leading": False}
    }
    state1 = _call_evidence_state(**kwargs)
    state2 = _call_evidence_state(**kwargs)

    assert state1 == state2, "build_stage3_evidence_state debe ser estrictamente determinista"


# ── ES-17 · JSON SERIALIZATION SAFETY ────────────────────────────────────────

def test_es_17_serialization_safety():
    """ES-17: La salida de build_stage3_evidence_state debe ser 100% serializable a JSON."""
    kwargs = {
        "features": {"mean_cc_aspect_ratio": 8.5, "clusters": 1},
        "provenance_info": {"source_representation_class": "IMAGE_RASTER"},
        "context_observations": {"orthogonal_grid_junction": False}
    }
    state = _call_evidence_state(**kwargs)

    dumped = json.dumps(state)
    loaded = json.loads(dumped)
    assert loaded == state, "El estado de evidencia debe soportar roundtrip JSON exacto"
