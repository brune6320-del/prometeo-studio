"""
PROMETEO · FC-009 STAGE 3A-4B · EVIDENCE STATE ADVERSARIAL HARDENING CONTRACT
─────────────────────────────────────────────────────────────────────────────
RED CONTRACT TESTING CONSERVATIVE DEGRADATION UNDER ADVERSARIAL & MALFORMED INPUTS

Metodología:
  RED ADVERSARIAL TESTS DEFINED BEFORE IMPLEMENTING HARDENING FIXES.
  Stage 3A-4B:
    Misión: Atacar la Evidence State API para demostrar si degrada
            de forma estrictamente conservadora o si presenta debilidades.
    Invariantes absolutas:
      - semantic_claim == 'UNRESOLVED' (siempre)
      - decision_authority == 'NONE' (siempre)
      - Prohibición estricta de TEXT_COMPATIBLE, STRONG, SAFE_TO_CLEAR, ALLOW_WRITE.

Familias Adversariales Evaluadas:
  ADV-01 · Empty/missing inputs degrade to INSUFFICIENT without crash;
  ADV-02 · Unknown representation enum must degrade to UNKNOWN (allowlist leak);
  ADV-03 · Semantic authority injection in inputs is completely ignored;
  ADV-04 · Truthy-string trap: strings 'false'/'0' must not activate counterevidence;
  ADV-05 · Conflict saturation: simultaneous contradictory signals mark CONFLICTED;
  ADV-06 · Raster contradiction: claiming text origin on raster remains UNAVAILABLE;
  ADV-07 · Vector + text signals never promote to semantic text claim;
  ADV-08 · Text operator + vertical continuity marks CONFLICTED without winner;
  ADV-09 · Repeated-X alone does not activate graphic counterevidence present;
  ADV-10 · Morphology anomaly alone does not activate semantic graphic claim;
  ADV-11 · Arbitrary extra kwargs do not leak into schema or alter authority;
  ADV-12 · Mutable input aliasing: caller inputs must not be mutated;
  ADV-13 · Order invariance: insertion order of input keys does not affect output;
  ADV-14 · Caution monotonicity A: adding conflict moves PARTIAL to CONFLICTED;
  ADV-15 · Caution monotonicity B: CONFLICTED cannot be diluted back to PARTIAL;
  ADV-16 · Serialization and determinism under adversarial inputs.
"""
import copy
import json
import pytest

import verifier2


def _call_evidence_state(*args, **kwargs) -> dict:
    """Invoca la función build_stage3_evidence_state desde verifier2."""
    builder = getattr(verifier2, "build_stage3_evidence_state", None)
    assert builder is not None, "build_stage3_evidence_state debe existir en verifier2"
    return builder(*args, **kwargs)


# ── ADV-01 · EMPTY / MISSING INPUTS ──────────────────────────────────────────

def test_adv_01_empty_missing_inputs():
    """ADV-01: Inputs None o vacíos deben degradar a INSUFFICIENT sin lanzar excepción."""
    state = _call_evidence_state(None, provenance_info=None, context_observations=None, span=None)

    assert state["evidence_sufficiency"] == "INSUFFICIENT"
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    assert state["graphic_counterevidence"]["present"] is False


# ── ADV-02 · UNKNOWN ENUM ALLOWLIST ──────────────────────────────────────────

def test_adv_02_unknown_enum_degrades_to_unknown():
    """ADV-02: Clases de representación desconocidas deben degradar a UNKNOWN, no pasar crudas."""
    prov = {
        "source_representation_class": "ALIEN_TEXT_SUPER_CERTAIN"
    }
    state = _call_evidence_state(provenance_info=prov)

    # Si pasa 'ALIEN_TEXT_SUPER_CERTAIN' sin validar contra allowlist, falla por ENUM_ALLOWLIST_LEAK
    assert state["representation_provenance"]["source_representation_class"] == "UNKNOWN", (
        "ENUM_ALLOWLIST_LEAK: Valores arbitrarios de representación deben degradar a UNKNOWN"
    )
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-03 · SEMANTIC AUTHORITY INJECTION ─────────────────────────────────────

def test_adv_03_semantic_authority_injection_ignored():
    """ADV-03: Intentos de inyectar veredictos o autoridad en diccionarios de entrada son ignorados."""
    hostile_prov = {
        "source_representation_class": "TEXT_OPERATOR",
        "semantic_claim": "TEXT_COMPATIBLE",
        "decision_authority": "STRONG",
        "safe_to_clear": True,
        "allow_write": True
    }
    state = _call_evidence_state(provenance_info=hostile_prov)

    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    dump = json.dumps(state)
    assert "TEXT_COMPATIBLE" not in dump
    assert "STRONG" not in dump
    assert "safe_to_clear" not in dump
    assert "allow_write" not in dump


# ── ADV-04 · TRUTHY-STRING TRAP ──────────────────────────────────────────────

def test_adv_04_truthy_string_trap_coercion():
    """ADV-04: Strings como 'false' o '0' no deben evaluarse como True por bool('false')."""
    malformed_obs = {
        "vertical_continuity_crossing_leading": "false",
        "orthogonal_grid_junction": "0",
        "repeated_x_alignment": "no"
    }
    state = _call_evidence_state(context_observations=malformed_obs)

    # En Python bool('false') == True. Si hay coerción ingenua, falla por TYPE_COERCION_LEAK.
    assert state["graphic_counterevidence"]["vertical_continuity_crossing_leading"] is False, (
        "TYPE_COERCION_LEAK: El string 'false' no debe evaluarse como booleano True"
    )
    assert state["graphic_counterevidence"]["orthogonal_grid_junction"] is False, (
        "TYPE_COERCION_LEAK: El string '0' no debe evaluarse como booleano True"
    )
    assert state["graphic_counterevidence"]["present"] is False


# ── ADV-05 · CONFLICT SATURATION ─────────────────────────────────────────────

def test_adv_05_conflict_saturation():
    """ADV-05: Coexistencia simultánea de todas las señales contradictorias satura en CONFLICTED."""
    feats = {
        "cluster_modulation_ratio": 3.5,
        "max_cc_aspect_ratio": 30.0,
        "connected_components_count": 5
    }
    prov = {
        "source_representation_class": "TEXT_OPERATOR",
        "has_invisible_text_layer": True,
        "has_underlying_image": True
    }
    obs = {
        "vertical_continuity_crossing_leading": True,
        "orthogonal_grid_junction": True,
        "repeated_x_alignment": True,
        "morphology_anomaly_observed": True,
        "language_context_candidate": "SPANISH_LEXICON"
    }
    state = _call_evidence_state(features=feats, provenance_info=prov, context_observations=obs)

    assert state["evidence_conflict"] is True
    assert state["evidence_sufficiency"] == "CONFLICTED"
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-06 · RASTER CONTRADICTION ────────────────────────────────────────────

def test_adv_06_raster_contradiction_authoring_origin():
    """ADV-06: Documento raster donde el caller intenta forzar authoring_origin=NATIVE_TEXT."""
    prov = {
        "source_representation_class": "IMAGE_RASTER",
        "authoring_origin": "NATIVE_TEXT"
    }
    state = _call_evidence_state(provenance_info=prov)

    # En raster el origen de autoría es físicamente inaccesible; debe quedar UNAVAILABLE
    assert state["representation_provenance"]["source_representation_class"] == "IMAGE_RASTER"
    assert state["representation_provenance"]["authoring_origin"] == "UNAVAILABLE"
    assert state["representation_provenance"]["is_raster_only"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-07 · VECTOR + TEXT SIGNALS ───────────────────────────────────────────

def test_adv_07_vector_plus_text_signals_remains_unresolved():
    """ADV-07: Trazos vectoriales acompañados de contexto léxico no promueven a texto semántico."""
    prov = {
        "source_representation_class": "VECTOR_PATH_OPERATOR",
        "vector_item_type": "path"
    }
    obs = {
        "language_context_candidate": "DICTIONARY_COHERENT"
    }
    state = _call_evidence_state(provenance_info=prov, context_observations=obs)

    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-08 · TEXT OPERATOR + GRAPHIC STRUCTURE ───────────────────────────────

def test_adv_08_text_operator_plus_graphic_structure():
    """ADV-08: TEXT_OPERATOR que intersecta regla continua marca CONFLICTED sin elegir ganador."""
    prov = {
        "source_representation_class": "TEXT_OPERATOR"
    }
    obs = {
        "vertical_continuity_crossing_leading": True
    }
    state = _call_evidence_state(provenance_info=prov, context_observations=obs)

    assert state["evidence_conflict"] is True
    assert state["evidence_sufficiency"] == "CONFLICTED"
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-09 · REPEATED-X ONLY ─────────────────────────────────────────────────

def test_adv_09_repeated_x_only_does_not_activate_present():
    """ADV-09: Alineación repetida en X sola no debe activar graphic_counterevidence.present."""
    obs = {
        "repeated_x_alignment": True,
        "vertical_continuity_crossing_leading": False,
        "orthogonal_grid_junction": False
    }
    state = _call_evidence_state(context_observations=obs)

    assert state["graphic_counterevidence"]["repeated_x_alignment"] is True
    assert state["graphic_counterevidence"]["present"] is False
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"


# ── ADV-10 · MORPHOLOGY ONLY ─────────────────────────────────────────────────

def test_adv_10_morphology_anomaly_only():
    """ADV-10: Alta relación de aspecto sola no activa veredicto gráfico ni thresholds."""
    obs = {
        "morphology_anomaly_observed": True
    }
    state = _call_evidence_state(context_observations=obs)

    assert state["graphic_counterevidence"]["morphology_anomaly_candidate"] is True
    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    assert "normative_threshold" not in state["graphic_counterevidence"]


# ── ADV-11 · UNKNOWN EXTRA KWARGS ────────────────────────────────────────────

def test_adv_11_unknown_extra_kwargs_ignored():
    """ADV-11: Argumentos adicionales desconocidos no deben alterar la estructura ni la autoridad."""
    state = _call_evidence_state(
        features={"cluster_modulation_ratio": 1.2},
        certainty=1.0,
        trusted=True,
        override="TEXT",
        force=True
    )

    assert state["semantic_claim"] == "UNRESOLVED"
    assert state["decision_authority"] == "NONE"
    assert "certainty" not in state
    assert "override" not in state


# ── ADV-12 · MUTABLE INPUT ALIASING ──────────────────────────────────────────

def test_adv_12_mutable_input_aliasing():
    """ADV-12: La función no debe mutar los diccionarios pasados por el llamador."""
    feats = {"max_cc_aspect_ratio": 15.0, "nested_list": [1, 2, 3]}
    prov = {"source_representation_class": "TEXT_OPERATOR", "tags": ["native"]}
    obs = {"vertical_continuity_crossing_leading": False}

    feats_copy = copy.deepcopy(feats)
    prov_copy = copy.deepcopy(prov)
    obs_copy = copy.deepcopy(obs)

    state = _call_evidence_state(features=feats, provenance_info=prov, context_observations=obs)

    assert feats == feats_copy, "INPUT_MUTATION: El diccionario features fue mutado"
    assert prov == prov_copy, "INPUT_MUTATION: El diccionario provenance_info fue mutado"
    assert obs == obs_copy, "INPUT_MUTATION: El diccionario context_observations fue mutado"


# ── ADV-13 · ORDER INVARIANCE ────────────────────────────────────────────────

def test_adv_13_order_invariance():
    """ADV-13: Diccionarios con distinto orden de inserción deben producir idéntica salida."""
    prov1 = {"source_representation_class": "TEXT_OPERATOR", "render_mode": 0}
    prov2 = {"render_mode": 0, "source_representation_class": "TEXT_OPERATOR"}

    obs1 = {"vertical_continuity_crossing_leading": True, "orthogonal_grid_junction": False}
    obs2 = {"orthogonal_grid_junction": False, "vertical_continuity_crossing_leading": True}

    state1 = _call_evidence_state(provenance_info=prov1, context_observations=obs1)
    state2 = _call_evidence_state(provenance_info=prov2, context_observations=obs2)

    assert state1 == state2, "La Evidence State API debe ser invariante al orden de inserción de claves"


# ── ADV-14 · CAUTION MONOTONICITY A (PARTIAL -> CONFLICTED) ──────────────────

def test_adv_14_caution_monotonicity_partial_to_conflicted():
    """ADV-14: Agregar contraevidencia incompatible a un estado PARTIAL debe transicionar a CONFLICTED."""
    # Estado inicial: TEXT_OPERATOR aislado -> PARTIAL
    state_a = _call_evidence_state(provenance_info={"source_representation_class": "TEXT_OPERATOR"})
    assert state_a["evidence_sufficiency"] == "PARTIAL"

    # Se agrega contraevidencia gráfica incompatible
    state_b = _call_evidence_state(
        provenance_info={"source_representation_class": "TEXT_OPERATOR"},
        context_observations={"vertical_continuity_crossing_leading": True}
    )

    # Debe ser CONFLICTED, nunca degradar a INSUFFICIENT ni escalar a SUFFICIENT
    assert state_b["evidence_sufficiency"] == "CONFLICTED", (
        "CONFLICT_MONOTONICITY_FAILURE: Agregar señal incompatible debe transicionar a CONFLICTED"
    )
    assert state_b["semantic_claim"] == "UNRESOLVED"
    assert state_b["decision_authority"] == "NONE"


# ── ADV-15 · CAUTION MONOTONICITY B (CONFLICTED CANNOT BE DILUTED) ───────────

def test_adv_15_caution_monotonicity_conflicted_cannot_be_diluted():
    """ADV-15: Un estado CONFLICTED no puede diluirse a PARTIAL añadiendo más señales favorables."""
    # Estado conflictivo base
    base_prov = {"source_representation_class": "TEXT_OPERATOR"}
    base_obs = {"vertical_continuity_crossing_leading": True}

    state_conflicted = _call_evidence_state(provenance_info=base_prov, context_observations=base_obs)
    assert state_conflicted["evidence_sufficiency"] == "CONFLICTED"

    # Se intentan agregar señales favorables adicionales (idioma, OCR)
    diluted_obs = {
        "vertical_continuity_crossing_leading": True,
        "language_context_candidate": "SPANISH_HIGH_CONFIDENCE",
        "repeated_x_alignment": False
    }
    state_diluted = _call_evidence_state(provenance_info=base_prov, context_observations=diluted_obs)

    # El conflicto no puede desaparecer por acumulación
    assert state_diluted["evidence_conflict"] is True
    assert state_diluted["evidence_sufficiency"] == "CONFLICTED", (
        "CONFLICT_MONOTONICITY_FAILURE: Un conflicto no debe diluirse a PARTIAL por añadir más señales"
    )


# ── ADV-16 · SERIALIZATION AND DETERMINISM UNDER ADVERSARIAL INPUTS ──────────

def test_adv_16_serialization_and_determinism_under_hostile_data():
    """ADV-16: Todos los outputs adversariales deben ser 100% JSON-safe y deterministas."""
    hostile_input = {
        "features": {"cluster_modulation_ratio": 0.0, "max_cc_aspect_ratio": 999.9},
        "provenance_info": {
            "source_representation_class": "MIXED",
            "has_invisible_text_layer": True,
            "has_underlying_image": True,
            "extra_junk": [None, 1, 2.5, "str"]
        },
        "context_observations": {
            "vertical_continuity_crossing_leading": True,
            "orthogonal_grid_junction": True,
            "repeated_x_alignment": True
        }
    }

    state1 = _call_evidence_state(**hostile_input)
    state2 = _call_evidence_state(**hostile_input)

    assert state1 == state2, "Determinismo violado en inputs adversariales"
    dumped = json.dumps(state1)
    loaded = json.loads(dumped)
    assert loaded == state1, "Roundtrip JSON falló en inputs adversariales"
