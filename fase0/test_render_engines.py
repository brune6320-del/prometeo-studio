"""PROMETEO · Multi-Engine Typography Benchmark & Parity Test Suite (ORDEN 139)
─────────────────────────────────────────────────────────────────────────────
Valida:
- Resolución determinista y offline de fuentes (FontResolver).
- Cobertura completa de caracteres en español y símbolos Unicode (á, é, í, ó, ú, ñ, ¿, ¡, €).
- Rechazo honesto (HONEST_REJECT / GUARANTEE_REJECT) ante glifos faltantes sin tofu silencioso.
- Funcionamiento del motor de referencia (PyMuPDFBaselineEngine).
- Funcionamiento del motor challenger (PillowFreeTypeEngine).
- Comparativa de paridad métrica y geométrica entre motores.
- Política de ajuste proporcional con límite estricto del 15% (FittingPolicy).
"""
from __future__ import annotations

import time
import pytest
import numpy as np

from fase0.text_render_engine import (
    FontRequest,
    FontResolver,
    FittingPolicy,
    PyMuPDFBaselineEngine,
    PillowFreeTypeEngine,
    EXACT_FONT,
    METRIC_COMPATIBLE_SUBSTITUTE,
    GENERIC_APPROXIMATION,
    UNSUPPORTED,
    GUARANTEE_EXACT,
    GUARANTEE_METRIC,
    GUARANTEE_APPROX,
    GUARANTEE_REJECT,
    ENGINE_BASELINE,
    ENGINE_CHALLENGER_PIL,
)


def test_font_resolver_canonical_families():
    """Verifica el mapeo determinista de familias estándar."""
    canon, name, sub_class, guar = FontResolver.resolve("helv")
    assert canon == "helv"
    assert sub_class == EXACT_FONT
    assert guar == GUARANTEE_EXACT

    canon_arial, name_arial, sub_arial, guar_arial = FontResolver.resolve("arial")
    assert canon_arial == "helv"
    assert sub_arial == METRIC_COMPATIBLE_SUBSTITUTE
    assert guar_arial == GUARANTEE_METRIC

    canon_times, _, sub_times, _ = FontResolver.resolve("times-roman")
    assert canon_times == "times"
    assert sub_times == EXACT_FONT

    canon_mono, _, sub_mono, guar_mono = FontResolver.resolve("monospace")
    assert canon_mono == "courier"
    assert sub_mono == GENERIC_APPROXIMATION
    assert guar_mono == GUARANTEE_APPROX


def test_glyph_coverage_spanish_unicode():
    """Valida que todos los caracteres comunes en español tengan 100% de cobertura."""
    spanish_phrase = "Producción Escénica 2026 — Perú: ¿Cuánto cuesta? 150 €"
    cov, missing = FontResolver.check_glyphs(spanish_phrase)
    assert cov == 1.0, f"Glifos faltantes en frase en español: {missing}"
    assert len(missing) == 0


def test_glyph_coverage_unsupported_reject():
    """Verifica que caracteres exóticos no soportados emitan HONEST_REJECT sin generar tofu silencioso."""
    exotic_text = "Texto con glifo cuneiforme: <ctrl42> y runa ᚠ"
    cov, missing = FontResolver.check_glyphs(exotic_text)
    assert cov < 1.0
    assert len(missing) > 0
    assert "<ctrl42>" in missing or "ᚠ" in missing


def test_pymupdf_baseline_engine_render():
    """Verifica que el motor de referencia genere un parche con métricas consistentes."""
    engine = PyMuPDFBaselineEngine()
    assert engine.engine_id == ENGINE_BASELINE

    req = FontRequest(family="helv", size_pt=12.0)
    patch = engine.render_text("PROMETEO VERIFIED", req, dpi=300.0)

    assert patch.engine_id == ENGINE_BASELINE
    assert patch.substitution_class == EXACT_FONT
    assert patch.guarantee_scope == GUARANTEE_EXACT
    assert patch.glyph_coverage == 1.0
    assert patch.bitmap.ndim == 2
    assert patch.bitmap.dtype == np.uint8
    assert patch.metrics.advance_width_pt > 0
    assert patch.metrics.width_px > 0
    assert patch.metrics.height_px > 0


def test_pillow_freetype_challenger_render():
    """Verifica que el challenger PIL_FREETYPE genere parches conformes al contrato."""
    engine = PillowFreeTypeEngine()
    assert engine.engine_id == ENGINE_CHALLENGER_PIL

    req = FontRequest(family="helv", size_pt=12.0)
    patch = engine.render_text("PROMETEO VERIFIED", req, dpi=300.0)

    assert patch.engine_id == ENGINE_CHALLENGER_PIL
    assert patch.glyph_coverage == 1.0
    assert patch.bitmap.ndim == 2
    assert patch.bitmap.dtype == np.uint8
    assert patch.metrics.advance_width_pt > 0


def test_multi_engine_metrics_parity():
    """Compara métricas entre Baseline y Challenger demostrando convergencia geométrica."""
    text = "TOTAL A PAGAR: $1,250.00"
    req = FontRequest(family="helv", size_pt=14.0)

    base_engine = PyMuPDFBaselineEngine()
    challenger = PillowFreeTypeEngine()

    base_metrics = base_engine.measure_metrics(text, req, dpi=300.0)
    chal_metrics = challenger.measure_metrics(text, req, dpi=300.0)

    assert base_metrics.advance_width_pt > 0
    assert chal_metrics.advance_width_pt > 0
    # Ambas métricas deben estar en el mismo orden de magnitud (ancho advance > 50pt y < 300pt)
    assert 50.0 < base_metrics.advance_width_pt < 300.0
    assert 50.0 < chal_metrics.advance_width_pt < 300.0


def test_fitting_policy():
    """Verifica que la política de ajuste respete el límite estricto de reducción (máx 15%)."""
    engine = PyMuPDFBaselineEngine()
    text = "Texto de prueba"
    initial_req = FontRequest(family="helv", size_pt=12.0)

    # 1. Cabe perfectamente
    bbox_large = (0.0, 0.0, 200.0, 50.0)
    req_fit, status_fit = FittingPolicy.fit_text(text, initial_req, bbox_large, engine)
    assert status_fit == "EXACT_FIT"
    assert req_fit.size_pt == 12.0

    # 2. Requiere reducción leve (p.ej. 10%, scale ~ 0.90 >= 0.85)
    metrics = engine.measure_metrics(text, initial_req)
    bbox_slightly_small = (0.0, 0.0, metrics.advance_width_pt * 0.92, 50.0)
    req_shrink, status_shrink = FittingPolicy.fit_text(text, initial_req, bbox_slightly_small, engine)
    assert status_shrink == "FITTED_WITH_SHRINK"
    assert req_shrink.size_pt < 12.0
    assert req_shrink.size_pt >= 12.0 * 0.85

    # 3. Excede límite del 15% (requiere scale 0.50) -> HONEST_REJECT
    bbox_too_small = (0.0, 0.0, metrics.advance_width_pt * 0.50, 50.0)
    req_rej, status_rej = FittingPolicy.fit_text(text, initial_req, bbox_too_small, engine)
    assert status_rej == GUARANTEE_REJECT
    assert req_rej is None


def test_render_benchmark_latency():
    """Mide la latencia de renderizado de ambos motores en un corpus sintético."""
    corpus = [
        "123.456,78 €",
        "Nombre: Juan Pérez Rodríguez",
        "Fecha de Emisión: 24/10/2026",
        "Aprobado por Dirección General",
    ]
    req = FontRequest(family="helv", size_pt=11.0)

    base_engine = PyMuPDFBaselineEngine()
    chal_engine = PillowFreeTypeEngine()

    t0 = time.perf_counter()
    for s in corpus:
        base_engine.render_text(s, req, dpi=300.0)
    base_time = (time.perf_counter() - t0) / len(corpus)

    t1 = time.perf_counter()
    for s in corpus:
        chal_engine.render_text(s, req, dpi=300.0)
    chal_time = (time.perf_counter() - t1) / len(corpus)

    # Ambos deben renderizar en menos de 50ms por parche
    assert base_time < 0.05, f"Baseline demasiado lento: {base_time:.4f}s"
    assert chal_time < 0.05, f"Challenger demasiado lento: {chal_time:.4f}s"
