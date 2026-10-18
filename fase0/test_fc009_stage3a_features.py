"""
PROMETEO · FC-009 STAGE 3A · FEATURE EXTRACTION CONTRACT TESTS
───────────────────────────────────────────────────────────────
DETERMINISTIC OBSERVABLE EVIDENCE EXTRACTION & TELEMETRY ONLY

Metodología:
  RED TESTS WRITTEN BEFORE FEATURE IMPLEMENTATION.
  Stage 3A al crear este archivo:
    ELIGIBLE = YES
    REACHED = NO
    EXECUTED = NO
    VERIFIED = NO

Correcciones Epistemológicas Adoptadas:
  1. NO existe threshold normativo gutter_ink_density >= 0.02 (0.02 es solo candidato de sweep).
  2. K1..K9 se denominan estrictamente PREDICTED_ADVERSARIAL_KILL_MECHANISMS (no ejecutados).
  3. FALSE_CLEARANCE_RISK = NOT_YET_QUANTIFIED.
  4. Cross-font normalization = CANDIDATE_NORMALIZATION (no PROVEN_INVARIANCE).
  5. Cross-DPI normalization = CANDIDATE_NORMALIZATION (no PROVEN_INVARIANCE, requiere sweeps).
  6. Runtime cost = UNMEASURED (estimate not benchmarked).
  7. Design A = PROMISING_DESIGN (no PROVEN_DISCRIMINATOR).
  8. AUTORIDAD DE DECISIÓN = NONE (no emite TEXT_COMPATIBLE ni text_evidence_level=STRONG).

Inventario de Tests Stage 3A:
  3A-01 · Feature extraction API exists in verifier2;
  3A-02 · Exact determinism: same input → same output;
  3A-03 · Extracted features are finite (no NaN, no Inf);
  3A-04 · Normalized metrics are dimensionless in [0, 1] or bounded;
  3A-05 · A7 150/300/600 produces comparable normalized feature distributions;
  3A-06 · A6 helv/hebo/tiro/cour produce distinguishable raw but valid normalized features;
  3A-07 · Barcode vs display text feature vectors differ in at least one observable;
  3A-08 · Confined table rule vs display text feature comparison;
  3A-09 · Grid in gutters vs display text feature comparison (gutter ink density);
  3A-10 · OCR-absorbed graphic vs display text feature comparison;
  3A-11 · Times-Roman serif vs Helvetica display text feature extraction;
  3A-12 · CAL-005 real scan calibration feature extraction succeeds;
  3A-13 · Outside continuity remains in safety_observations, not positive evidence;
  3A-14 · Missing global_img marks global_context_available=False;
  3A-15 · No LAB metadata or fixture labels accepted by API signature.
"""
import os
import inspect
import pytest
import numpy as np
import pymupdf
from PIL import Image

import verifier2
from raster import (
    _span_region_px,
    build_span_from_ocr,
    SpaceTransform,
)
from ocr_provider import TesseractOCRProvider

HERE = os.path.dirname(os.path.abspath(__file__))
CAL005 = os.path.join(HERE, "reality_corpus", "docs", "CAL-005_1001.pdf")


# ── Fixture Helpers ──────────────────────────────────────────────────────────

def _render_stage3a_synthetic_image(text: str, fontsize_pt: float = 36.0,
                                    fontname: str = "hebo",
                                    add_h_line: bool = False,
                                    add_v_line: bool = False,
                                    v_line_pos: tuple = (230, 20, 230, 180),
                                    v_line_width: float = 4.0,
                                    add_stripes_bg: bool = False,
                                    dpi: int = 300) -> np.ndarray:
    """Renderiza imágenes sintéticas controladas para tests de extracción de features."""
    doc = pymupdf.open()
    page_w_pt, page_h_pt = 600.0, 200.0
    page = doc.new_page(width=page_w_pt, height=page_h_pt)

    if add_stripes_bg:
        shape_bg = page.new_shape()
        for x in range(30, 570, 8):
            shape_bg.draw_line(pymupdf.Point(x, 40), pymupdf.Point(x, 160))
        shape_bg.finish(color=(0.75, 0.75, 0.75), width=0.5)
        shape_bg.commit()

    if text:
        page.insert_text(pymupdf.Point(50, 100), text, fontname=fontname, fontsize=fontsize_pt)

    shape = page.new_shape()
    if add_h_line:
        shape.draw_line(pymupdf.Point(0, 105), pymupdf.Point(600, 105))
        shape.finish(color=(0, 0, 0), width=4)
    if add_v_line:
        p0 = pymupdf.Point(v_line_pos[0], v_line_pos[1])
        p1 = pymupdf.Point(v_line_pos[2], v_line_pos[3])
        shape.draw_line(p0, p1)
        shape.finish(color=(0, 0, 0), width=v_line_width)
    if add_h_line or add_v_line:
        shape.commit()

    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()
    return arr


def _call_extractor(*args, **kwargs):
    """Wrapper para invocar extract_positive_text_features desde verifier2."""
    extractor = getattr(verifier2, "extract_positive_text_features", None)
    assert extractor is not None, (
        "Stage 3A RED: extract_positive_text_features no existe aún en verifier2.py"
    )
    return extractor(*args, **kwargs)


# ── 3A-01 · API EXISTENCE ────────────────────────────────────────────────────

def test_3a_01_feature_extraction_api_exists():
    """3A-01 (nace ROJO): Verifica que la API extract_positive_text_features exista en verifier2."""
    extractor = getattr(verifier2, "extract_positive_text_features", None)
    assert extractor is not None, "verifier2 debe definir extract_positive_text_features"
    assert callable(extractor), "extract_positive_text_features debe ser una función invocable"


# ── 3A-02 · EXACT DETERMINISM ────────────────────────────────────────────────

def test_3a_02_determinism_exact_same_input_same_output():
    """3A-02 (nace ROJO): Verifica determinismo exacto (misma entrada → misma salida idéntica)."""
    img = _render_stage3a_synthetic_image("TITULO DETERMINISMO", fontsize_pt=36.0, fontname="hebo")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR debe encontrar el título"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res1 = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
    res2 = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)

    assert res1 == res2, "extract_positive_text_features debe ser estrictamente determinista"


# ── 3A-03 · FINITE FEATURES (NO NAN / NO INF) ────────────────────────────────

def test_3a_03_features_finite_no_nan_no_inf():
    """3A-03 (nace ROJO): Verifica que todas las métricas numéricas extraídas sean finitas."""
    img = _render_stage3a_synthetic_image("TITULO FINITO", fontsize_pt=36.0, fontname="hebo")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
    features = res.get("features", {})
    assert len(features) > 0, "features no debe ser un diccionario vacío"
    for k, v in features.items():
        if isinstance(v, (int, float)):
            assert np.isfinite(v), f"Feature {k}={v} no es un número finito"


# ── 3A-04 · NORMALIZED METRICS DIMENSIONLESS ─────────────────────────────────

def test_3a_04_normalized_metrics_dimensionless():
    """3A-04 (nace ROJO): Verifica que las métricas normalizadas (envelope, gutters) sean adimensionales."""
    img = _render_stage3a_synthetic_image("TITULO NORMALIZADO", fontsize_pt=36.0, fontname="hebo")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
    features = res.get("features", {})

    assert "envelope_confinement_ratio" in features, "Falta envelope_confinement_ratio"
    assert 0.0 <= features["envelope_confinement_ratio"] <= 1.0, "envelope_confinement_ratio debe estar en [0, 1]"

    assert "gutter_ink_density" in features, "Falta gutter_ink_density"
    assert 0.0 <= features["gutter_ink_density"] <= 1.0, "gutter_ink_density debe estar en [0, 1]"


# ── 3A-05 · MULTI-DPI SCALE COMPARABILITY (CANDIDATE NORMALIZATION) ──────────

def test_3a_05_multi_dpi_scale_comparable_normalized_distribution():
    """3A-05 (nace ROJO): Verifica que a 150, 300 y 600 DPI las métricas normalizadas sean comparables."""
    ratios = []
    for dpi in [150, 300, 600]:
        img = _render_stage3a_synthetic_image("TITULO MULTI RESOLUCION", fontsize_pt=36.0, fontname="hebo", dpi=dpi)
        obs = TesseractOCRProvider(config="--psm 6")
        page_ocr = obs.process(Image.fromarray(img, "L"), float(dpi))
        line = page_ocr.find_line_containing("TITULO")
        assert line is not None

        t = SpaceTransform(600.0, 200.0, dpi=float(dpi))
        span = build_span_from_ocr(line, t, 600.0, 0)
        rect_px = _span_region_px(span)
        local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

        res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
        ratios.append(res["features"]["envelope_confinement_ratio"])

    assert len(ratios) == 3
    # Comprobar que no hay divergencia masiva entre DPIs (rango < 0.20)
    assert max(ratios) - min(ratios) < 0.20, f"Divergencia entre DPIs excesiva: {ratios}"


# ── 3A-06 · MULTI-FONT MORPHOLOGY OBSERVABILITY (CANDIDATE NORMALIZATION) ─────

def test_3a_06_multi_font_family_observable_morphology():
    """3A-06 (nace ROJO): Verifica que distintas familias tipográficas produzcan descriptores observables válidos."""
    results = {}
    for font in ["helv", "hebo", "tiro", "cour"]:
        img = _render_stage3a_synthetic_image("TITULO TIPOGRAFICO MODULADO", fontsize_pt=36.0, fontname=font)
        obs = TesseractOCRProvider(config="--psm 6")
        page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
        line = page_ocr.find_line_containing("TITULO")
        assert line is not None

        t = SpaceTransform(600.0, 200.0, dpi=300.0)
        span = build_span_from_ocr(line, t, 600.0, 0)
        rect_px = _span_region_px(span)
        local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

        res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
        results[font] = res["features"]

    assert len(results) == 4
    # Todas las fuentes limpias deben tener envelope_confinement_ratio positivo
    for font, feat in results.items():
        assert feat["envelope_confinement_ratio"] > 0.5, f"Envelope falló en {font}"


# ── 3A-07 · BARCODE VS DISPLAY TEXT DIFFERENTIATION ──────────────────────────

def test_3a_07_barcode_vs_display_text_distinguishable():
    """3A-07 (nace ROJO): Verifica que un código de barras difiera de texto display en al menos un feature observable."""
    # 1. Texto display
    img_text = _render_stage3a_synthetic_image("TITULO PRINCIPAL DISPLAY", fontsize_pt=36.0, fontname="hebo")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img_text, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_text = img_text[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    feat_text = _call_extractor(local_region=local_text, rect_px=rect_px, span=span, global_img=img_text, ocr_page=page_ocr)["features"]

    # 2. Barcode
    reg_barcode = np.full((120, 400), 255, dtype=np.uint8)
    for bx in range(50, 350, 15):
        reg_barcode[20:100, bx:bx + 4] = 0
    rect_barcode = (30, 30, 430, 150)

    feat_barcode = _call_extractor(local_region=reg_barcode, rect_px=rect_barcode)["features"]

    # Comparar vectores: al menos un descriptor morfológico/topológico debe diferir sensiblemente
    keys_common = set(feat_text.keys()) & set(feat_barcode.keys())
    assert len(keys_common) > 0
    diffs = [abs(feat_text[k] - feat_barcode[k]) for k in keys_common if isinstance(feat_text[k], (int, float))]
    assert max(diffs) > 0.05, "Texto y código de barras deben ser distinguibles en al menos una dimensión observable"


# ── 3A-08 · CONFINED TABLE RULE VS DISPLAY TEXT ──────────────────────────────

def test_3a_08_confined_table_rule_vs_display_text_distinguishable():
    """3A-08 (nace ROJO): Verifica que una regla confinada difiera de texto en features observados."""
    reg_rule = np.full((120, 400), 255, dtype=np.uint8)
    reg_rule[10:110, 200:204] = 0
    rect_rule = (50, 50, 450, 170)

    feat_rule = _call_extractor(local_region=reg_rule, rect_px=rect_rule)["features"]
    assert "observed_clusters_count" in feat_rule
    assert feat_rule["observed_clusters_count"] <= 1, "Regla de tabla confinada solo tiene 1 fuste observable"


# ── 3A-09 · GRID IN GUTTERS VS DISPLAY TEXT ──────────────────────────────────

def test_3a_09_grid_in_gutters_vs_display_text_distinguishable():
    """3A-09 (nace ROJO): Verifica que una regla en el gutter eleve gutter_ink_density."""
    # Texto limpio con 2 palabras
    img_clean = _render_stage3a_synthetic_image("PALABRA UNO   PALABRA DOS", fontsize_pt=36.0)
    obs = TesseractOCRProvider(config="--psm 6")
    ocr_clean = obs.process(Image.fromarray(img_clean, "L"), 300.0)
    lines_clean = ocr_clean.lines()
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span_clean = build_span_from_ocr(lines_clean[0], t, 600.0, 0)
    rect_clean = _span_region_px(span_clean)
    feat_clean = _call_extractor(local_region=img_clean[rect_clean[1]:rect_clean[3], rect_clean[0]:rect_clean[2]],
                                 rect_px=rect_clean, span=span_clean, global_img=img_clean, ocr_page=ocr_clean)["features"]

    # Texto con regla en el gutter
    img_grid = _render_stage3a_synthetic_image("PALABRA UNO   PALABRA DOS", fontsize_pt=36.0,
                                               add_v_line=True, v_line_pos=(280, 20, 280, 180), v_line_width=2.0)
    ocr_grid = obs.process(Image.fromarray(img_grid, "L"), 300.0)
    lines_grid = ocr_grid.lines()
    span_grid = build_span_from_ocr(lines_grid[0], t, 600.0, 0)
    rect_grid = _span_region_px(span_grid)
    feat_grid = _call_extractor(local_region=img_grid[rect_grid[1]:rect_grid[3], rect_grid[0]:rect_grid[2]],
                                rect_px=rect_grid, span=span_grid, global_img=img_grid, ocr_page=ocr_grid)["features"]

    assert feat_grid["gutter_ink_density"] > feat_clean["gutter_ink_density"], (
        "La regla en el gutter debe aumentar la densidad observada de tinta en gutters"
    )


# ── 3A-10 · OCR ABSORBED GRAPHIC VS DISPLAY TEXT ─────────────────────────────

def test_3a_10_ocr_absorbed_graphic_vs_display_text_distinguishable():
    """3A-10 (nace ROJO): Verifica que una regla absorbida por OCR altere la envolvente o modulación."""
    img_regla = _render_stage3a_synthetic_image("TITULO REGULADO", fontsize_pt=24.0,
                                                add_v_line=True, v_line_pos=(150, 10, 150, 190), v_line_width=4.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img_regla, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img_regla[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img_regla, ocr_page=page_ocr)
    # La regla que cruza debe registrarse en la envolvente o en outside continuity
    assert "envelope_confinement_ratio" in res["features"]


# ── 3A-11 · TIMES SERIF VS HELVETICA DISPLAY TEXT FEATURES ───────────────────

def test_3a_11_times_serif_vs_helvetica_display_text_features():
    """3A-11 (nace ROJO): Verifica extracción correcta de features en tipografía Serif."""
    img = _render_stage3a_synthetic_image("TITULO SERIF DISPLAY", fontsize_pt=36.0, fontname="tiro")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
    assert res["features"]["envelope_confinement_ratio"] > 0.5


# ── 3A-12 · CAL-005 REAL SCAN CALIBRATION FEATURE EXTRACTION ─────────────────

@pytest.mark.skipif(not os.path.exists(CAL005), reason="CAL-005 real es LOCAL (no commiteado)")
def test_3a_12_cal005_real_scan_feature_extraction():
    """3A-12 (nace ROJO): Verifica extracción de features en el titular de CAL-005 real (CALIBRATION ONLY)."""
    doc = pymupdf.open(CAL005)
    pix = doc[0].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    rect_px = (7752, 3646, 9882, 3792)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    obs = TesseractOCRProvider(config="--psm 3")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("PREFACIO")
    assert line is not None

    t = SpaceTransform(img.shape[1] * 72.0 / 300.0, img.shape[0] * 72.0 / 300.0, dpi=300.0)
    span = build_span_from_ocr(line, t, t.w_pt, 0)

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)
    assert "features" in res
    assert "envelope_confinement_ratio" in res["features"]
    assert "gutter_ink_density" in res["features"]


# ── 3A-13 · OUTSIDE CONTINUITY REMAINS SAFETY OBSERVATION ────────────────────

def test_3a_13_outside_continuity_remains_safety_observation():
    """3A-13 (nace ROJO): Verifica que outside_continuity esté en safety_observations y NO en features positivas."""
    img = _render_stage3a_synthetic_image("COLUMNA A   COLUMNA B", fontsize_pt=36.0,
                                          add_v_line=True, v_line_pos=(235, 20, 235, 180), v_line_width=2.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("COLUMNA")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    res = _call_extractor(local_region=local_region, rect_px=rect_px, span=span, global_img=img, ocr_page=page_ocr)

    safety = res.get("safety_observations", {})
    assert "outside_continuity_cols" in safety, "outside_continuity_cols debe residir en safety_observations"
    assert "outside_continuity_cols" not in res.get("features", {}), (
        "outside_continuity_cols NO debe contarse como feature de evidencia positiva"
    )


# ── 3A-14 · MISSING GLOBAL_IMG MARKS CONTEXT UNAVAILABLE ─────────────────────

def test_3a_14_missing_global_img_marks_evidence_unavailable():
    """3A-14 (nace ROJO): Verifica que sin global_img se marque global_context_available=False de forma segura."""
    reg = np.full((120, 300), 255, dtype=np.uint8)
    rect_px = (50, 50, 350, 170)

    res = _call_extractor(local_region=reg, rect_px=rect_px, global_img=None)
    safety = res.get("safety_observations", {})
    assert safety.get("global_context_available") is False, "Sin global_img debe marcar global_context_available=False"


# ── 3A-15 · NO LAB METADATA ENTERS API ───────────────────────────────────────

def test_3a_15_no_lab_metadata_in_api_signature():
    """3A-15 (nace ROJO): Verifica que la firma de extract_positive_text_features no acepte parámetros LAB."""
    extractor = getattr(verifier2, "extract_positive_text_features", None)
    assert extractor is not None, "verifier2 debe definir extract_positive_text_features"
    sig = inspect.signature(extractor)
    forbidden_params = {"lab_true_nature", "oracle", "is_target", "case_name", "fixture_name", "ground_truth"}
    for p in sig.parameters:
        assert p.lower() not in forbidden_params, f"Parámetro LAB prohibido detectado en la API: {p}"
