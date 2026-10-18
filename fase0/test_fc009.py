"""
PROMETEO · FC-009 · REGRESIÓN: Falso positivo del gate de gráficos en tipografía display
──────────────────────────────────────────────────────────────────────────────────────────
Origen: CAL-005 post-FC008 (raster real).
Mecanismo profundo: LOCAL VERTICAL GEOMETRY DOES NOT IDENTIFY TYPOGRAPHIC STROKES
VS SHORT GRAPHIC RULES (insuficiencia intrínseca de la geometría binaria local).

Este archivo contiene el contrato histórico y el contrato triestado ampliado:

Contrato histórico de falso positivo (pre-gates binarios):
  T1 · [FAILED / RED] Texto display grande limpio clasificado como estructura por gate binario antiguo;
  T2 · [PASSED / GREEN] Control positivo: Línea horizontal gráfica pura se detecta como estructura 'h';
  T3 · [PASSED / GREEN] Control positivo: Texto + línea horizontal gráfica real se rechaza como estructura 'h';
  T4 · [PASSED / GREEN] Fixtures históricos del graphics gate (G2_linea_cruza / G2_borde_cercano) preservados;
  T5 · [FAILED / RED] Regresión CAL-005 real LOCAL falla por gate binario antiguo (276 columnas);
  T6 · [PASSED / GREEN] Control positivo: Regla vertical pura se detecta como estructura 'v';
  T7 · [PASSED / GREEN] Control positivo: Texto + regla vertical real se rechaza como estructura 'v'.

Contrato triestado Stage 1 (vertical_structure_assessment aislado):
  T8   · [PASSED / GREEN] Outside continuity real en imagen global → PROTECTED_STRUCTURE;
  T9a  · [PASSED / GREEN] LAB ORACLE: Validación de provenance y ausencia de trazos gráficos en fixture;
  T9b  · [PASSED / GREEN] RUNTIME CONTRACT: Sin mecanismo demostrado de atribución positiva → AMBIGUOUS;
  T10  · [PASSED / GREEN] Regla corta interna aislada → AMBIGUOUS (honest reject conservador);
  T11  · [PASSED / GREEN] Texto + regla corta interna absorbible por OCR → AMBIGUOUS;
  T12  · [PASSED / GREEN] Glifo I/l aislado sin evidencia independiente adicional → AMBIGUOUS;
  T13  · [PASSED / GREEN] Consenso multimodo (psm6/psm3/psm11) sobre I/| → sigue AMBIGUOUS (error correlacionado);
  T14  · [PASSED / GREEN] Componente tipográfico complejo conectado (H/E/M) sin estructuras externas → AMBIGUOUS;
  T15  · [PASSED / GREEN] CAL-005 real LOCAL → AMBIGUOUS (sin continuidad exterior; no forzar TEXT_COMPATIBLE).

Controles adversariales y caracterización de OUTSIDE_CONTINUITY (T16–T21 y sweeps):
  T16  · [PASSED / GREEN] Caracterización: 1 columna oscura conectada >=15 px → PROTECTED_STRUCTURE (V1);
  T17  · [PASSED / GREEN] Control positivo: regla gráfica 4 px conectada >=15 px → PROTECTED_STRUCTURE;
  T18  · [PASSED / GREEN] Control adversarial: misma X con gap blanco de 1 px en borde → AMBIGUOUS;
  T19  · [PASSED / GREEN] Control adversarial: misma X con gap blanco de 2–3 px → AMBIGUOUS;
  T20  · [PASSED / GREEN] Control adversarial: ruido aleatorio exterior sin conexión material → AMBIGUOUS;
  T21  · [PASSED / GREEN] Caracterización: regla con grises bajo dark=128 (gris 100 vs gris 160);
  Sweep Width · [PASSED / GREEN] Anchos 1, 2, 3, 4, 8 px reflejan exactamente outside_continuity_cols;
  Sweep Gap   · [PASSED / GREEN] Gaps 0, 1, 2, 3 px demuestran necesidad de conexión material estricta.

Stage 1 implementado en verifier2.py como evaluador triestado aislado; NO integrado en raster.py aún.
"""
import os
import pytest
import numpy as np
import pymupdf
from PIL import Image

import fixtures_raster
import verifier2
from raster import raster_edit, _span_region_px, build_span_from_ocr, SpaceTransform, FC008_MODES
from ocr_provider import TesseractOCRProvider

HERE = os.path.dirname(os.path.abspath(__file__))
CAL005 = os.path.join(HERE, "reality_corpus", "docs", "CAL-005_1001.pdf")


def _render_synthetic_text_image(text: str, fontsize_pt: float = 36.0,
                                 add_h_line: bool = False,
                                 add_v_line: bool = False,
                                 dpi: int = 300) -> np.ndarray:
    """Renderiza una imagen sintética limpia de texto display a 300 DPI con o sin reglas."""
    doc = pymupdf.open()
    page_w_pt, page_h_pt = 600.0, 200.0
    page = doc.new_page(width=page_w_pt, height=page_h_pt)
    # Insertar texto display
    page.insert_text(pymupdf.Point(50, 100), text, fontname="hebo", fontsize=fontsize_pt)
    shape = page.new_shape()
    if add_h_line:
        # Dibujar una regla horizontal (subrayado/filete de tabla) que cruza la página
        shape.draw_line(pymupdf.Point(0, 105), pymupdf.Point(600, 105))
        shape.finish(color=(0, 0, 0), width=4)
    if add_v_line:
        # Dibujar una regla vertical de tabla que cruza de borde a borde la región del texto
        shape.draw_line(pymupdf.Point(230, 20), pymupdf.Point(230, 180))
        shape.finish(color=(0, 0, 0), width=4)
    if add_h_line or add_v_line:
        shape.commit()
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()
    return arr


@pytest.fixture(scope="session")
def dataset():
    return fixtures_raster.build_all()


# ── T1 · CONTRATO: Texto display limpio no es estructura gráfica (ROJO) ──────

def test_t1_display_text_limpio_no_es_estructura_protegida():
    """T1 (nace ROJO): Un texto en tipografía display (36 pt) sobre fondo limpio
    posee astas verticales mayores a 60 px a 300 DPI, pero NO contiene estructuras
    gráficas ni líneas de tabla. El gate no debe clasificarlo como estructura."""
    img = _render_synthetic_text_image("TITULO PRINCIPAL DISPLAY", fontsize_pt=36.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR no encontró la línea sintética"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = verifier2.line_structure_in_region(img, rect_px)
    assert not res["has_structure"], (
        f"FC-009 activo: texto display limpio clasificado como estructura protegida: {res}"
    )


# ── T2 · Control Positivo: Línea horizontal gráfica pura se detecta (VERDE) ──

def test_t2_linea_grafica_real_debe_continuar_detectandose():
    """T2 (VERDE): Una línea horizontal real continua que cruza una
    región vacía debe continuar siendo detectada como estructura."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    # Dibujar línea horizontal continua de 400 px
    img[150:153, 100:500] = 0
    res = verifier2.line_structure_in_region(img, (50, 100, 550, 200))
    assert res["has_structure"] is True
    assert "h" in (res["kind"] or "")


# ── T3 · Control Positivo: Texto + línea horizontal gráfica real (VERDE) ─────

def test_t3_texto_mas_linea_grafica_real_debe_ser_rechazado():
    """T3 (VERDE): Si existe texto Y una línea horizontal real cruzando la región,
    la estructura gráfica debe ser detectada y rechazada para protegerla."""
    img = _render_synthetic_text_image("TITULO SUBRAYADO", fontsize_pt=36.0, add_h_line=True)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = verifier2.line_structure_in_region(img, rect_px)
    assert res["has_structure"] is True, "Línea gráfica real no detectada"
    assert "h" in (res["kind"] or "")


# ── T4 · Regresiones Históricas G2 preservadas (VERDE) ────────────────────────

def test_t4_fixtures_historicos_graphics_gate_preservados(dataset, tmp_path):
    """T4 (VERDE): G2_linea_cruza debe seguir siendo HONEST_REJECT (clearance_ok=False)
    y G2_borde_cercano debe seguir siendo PASS (clearance_ok=True)."""
    # G2_linea_cruza
    out1 = str(tmp_path / "out_g2_cruza.pdf")
    rep1 = raster_edit(dataset["G2_linea_cruza"]["pdf"], "Perez", "Garcia", out1)
    assert rep1["dimensions"]["graphics_clearance_ok"] is False
    assert rep1["classification"] == "HONEST_REJECT"

    # G2_borde_cercano
    out2 = str(tmp_path / "out_g2_borde.pdf")
    rep2 = raster_edit(dataset["G2_borde_cercano"]["pdf"], "Fecha", "Dia", out2)
    assert rep2["dimensions"]["graphics_clearance_ok"] is True


# ── T5 · Regresión CAL-005 real LOCAL (ROJO) ──────────────────────────────────

@pytest.mark.skipif(not os.path.exists(CAL005),
                    reason="CAL-005 real es LOCAL (no commiteado)")
def test_t5_cal005_real_local_deja_de_fallar_por_falso_positivo_gfx():
    """T5 (nace ROJO): En CAL-005 real, el gate de gráficos en la región de
    'PREFACIO DE MICHAEL LYDON' debe dejar de arrojar falso positivo por las
    276 columnas de astas de caracteres."""
    doc = pymupdf.open(CAL005)
    pix = doc[0].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    # Región exacta auditada de CAL-005 (span +-3pt)
    rect_px = (7752, 3646, 9882, 3792)
    res = verifier2.line_structure_in_region(img, rect_px)
    assert not res["has_structure"], (
        f"FC-009 activo en CAL-005 real: {res}"
    )


# ── T6 · Control Positivo: Regla vertical pura se detecta (VERDE) ────────────

def test_t6_linea_grafica_vertical_pura_debe_detectarse():
    """T6 (VERDE): Una regla vertical real que atraviesa la región sin texto
    debe ser clasificada como estructura protegida vertical (kind='v')."""
    img_v = np.full((300, 600), 255, dtype=np.uint8)
    # Regla vertical de 200 px de alto (y=50..250) y 4 px de ancho
    img_v[50:250, 298:302] = 0
    res = verifier2.line_structure_in_region(img_v, (50, 80, 550, 220))
    assert res["has_structure"] is True
    assert "v" in (res["kind"] or "")


# ── T7 · Control Positivo: Texto display + regla vertical real (VERDE) ────────

def test_t7_display_text_mas_linea_grafica_vertical_debe_rechazarse():
    """T7 (VERDE): Si existe texto display Y una regla vertical real que cruza
    la región de parte a parte, la estructura vertical debe detectarse y protegerse."""
    img = _render_synthetic_text_image("TITULO COLUMNA", fontsize_pt=36.0, add_v_line=True)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = verifier2.line_structure_in_region(img, rect_px)
    assert res["has_structure"] is True, "Regla vertical real no detectada"
    assert "v" in (res["kind"] or "")


def _render_elements(text_list=None, line_list=None, page_w_pt=600.0, page_h_pt=200.0, dpi=300) -> np.ndarray:
    """Renderiza elementos arbitrarios (textos y líneas) deterministamente a 300 DPI."""
    doc = pymupdf.open()
    page = doc.new_page(width=page_w_pt, height=page_h_pt)
    if text_list:
        for txt, font, sz, pos in text_list:
            page.insert_text(pymupdf.Point(*pos), txt, fontname=font, fontsize=sz)
    if line_list:
        shape = page.new_shape()
        for p0, p1, w in line_list:
            shape.draw_line(pymupdf.Point(*p0), pymupdf.Point(*p1))
            shape.finish(color=(0, 0, 0), width=w)
        shape.commit()
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()
    return arr


# ══════════════════════════════════════════════════════════════════════════════
# CONTRATO TRIESTADO: PROTECTED_STRUCTURE / TEXT_COMPATIBLE / AMBIGUOUS (T8–T15)
# ══════════════════════════════════════════════════════════════════════════════

def _call_tri_state(img: np.ndarray, rect_px: tuple, span: dict = None,
                    global_img: np.ndarray = None, ocr_page = None,
                    ocr_provenance: dict = None) -> dict:
    """Invocador contractual del evaluador triestado en verifier2.
    Nace ROJO si el evaluador triestado aún no está implementado en el motor."""
    assessment_fn = getattr(verifier2, "vertical_structure_assessment", None)
    if assessment_fn is None:
        pytest.fail(
            "CONTRATO TRIESTADO FC-009 ROJO: verifier2.vertical_structure_assessment "
            "no está implementado en el motor aún."
        )
    return assessment_fn(img, rect_px, span=span, global_img=global_img,
                          ocr_page=ocr_page, ocr_provenance=ocr_provenance)


# ── T8 · Contrato Triestado: Outside continuity real → PROTECTED_STRUCTURE ───

def test_t8_outside_continuity_real_es_protected_structure():
    """T8 (nace ROJO): Una regla vertical que cruza la página de parte a parte
    y atraviesa el span del texto posee continuidad exterior real en la imagen global.
    Debe clasificarse inequívocamente como PROTECTED_STRUCTURE."""
    img = _render_elements(
        text_list=[("COLUMNA A   COLUMNA B", "hebo", 36.0, (50, 100))],
        line_list=[((235, 20), (235, 180), 2.0)]
    )
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("COLUMNA")
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = _call_tri_state(img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]],
                          rect_px, span=span, global_img=img, ocr_page=page_ocr)
    assert res["status"] == "PROTECTED_STRUCTURE"
    assert res["has_structure"] is True


# ── T9a · LAB ORACLE: Validación de provenance y ausencia de gráficos en fixture (VERDE) ──

def test_t9a_lab_oracle_fixture_provenance():
    """T9a (VERDE / LAB ORACLE): Valida que el fixture sintético 'TITULO PRINCIPAL DISPLAY'
    fue construido exclusivamente con inserción de texto tipográfico y cero operaciones
    gráficas de línea/dibujo. El LAB ORACLE verifica la verdad fundamental del fixture,
    pero este conocimiento ground-truth NO está disponible como evidencia Runtime."""
    # Verificar provenance de renderizado del fixture
    doc = pymupdf.open()
    page = doc.new_page(width=600.0, height=200.0)
    page.insert_text(pymupdf.Point(50, 100), "TITULO PRINCIPAL DISPLAY", fontname="hebo", fontsize=36.0)

    # Inspección LAB: no hay operaciones de dibujo en el PDF
    drawings = page.get_drawings()
    assert len(drawings) == 0, "LAB ORACLE: El fixture no debe contener elementos de dibujo"

    # Rasterizar y verificar presencia de tinta
    pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    dark_px = np.sum(arr < 128)
    assert dark_px > 500, "LAB ORACLE: El fixture debe contener tinta tipográfica"


# ── T9b · RUNTIME CONTRACT: Sin mecanismo demostrado de atribución positiva (ROJO) ──────

def test_t9b_runtime_assessment_evidence():
    """T9b (nace ROJO / RUNTIME CONTRACT): Evalúa vertical_structure_assessment usando
    ÚNICAMENTE las señales disponibles en Runtime. Como la simple ausencia de evidencia
    gráfica NO basta para declarar positiva la tipografía sin un mecanismo demostrado de
    atribución textual, en Runtime este caso debe nacer esperando AMBIGUOUS hasta que
    dicho mecanismo positivo de atribución sea establecido formalmente."""
    img = _render_elements(
        text_list=[("TITULO PRINCIPAL DISPLAY", "hebo", 36.0, (50, 100))],
        line_list=None
    )
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = _call_tri_state(img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]],
                          rect_px, span=span, global_img=img, ocr_page=page_ocr)
    # Contrato Runtime estricto: sin mecanismo de atribución positiva demostrado,
    # el caso es AMBIGUOUS; no forzar TEXT_COMPATIBLE por conocimiento del test
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True


# ── T10 · Contrato Triestado: Regla corta interna aislada → AMBIGUOUS ─────────

def test_t10_regla_corta_interna_aislada_es_ambiguous():
    """T10 (nace ROJO): Una regla vertical corta interna aislada (sin texto,
    sin continuidad exterior fuera del renglón) no puede atribuirse a tipografía.
    Por seguridad (SILENT_FAILURE=0), debe clasificarse como AMBIGUOUS (honest reject)."""
    img = np.full((200, 600), 255, dtype=np.uint8)
    img[45:154, 93:107] = 0
    rect_px = (80, 35, 120, 165)

    res = _call_tri_state(img[35:165, 80:120], rect_px, global_img=img)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True


# ── T11 · Contrato Triestado: Texto + regla corta absorbible → AMBIGUOUS ─────

def test_t11_texto_mas_regla_corta_interna_absorbible_es_ambiguous():
    """T11 (nace ROJO): Un texto con una regla vertical corta entre palabras que
    puede ser absorbida por Tesseract en un word box (ej. 'COLUMNAIA'). Al no haber
    evidencia independiente suficiente de atribución tipográfica positiva, debe ser AMBIGUOUS."""
    img = _render_elements(
        text_list=[("COLUMNA A   COLUMNA B", "helv", 36.0, (50, 100))],
        line_list=[((235, 74), (235, 100), 2.0)]
    )
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("COLUMNA")
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = _call_tri_state(img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]],
                          rect_px, span=span, global_img=img, ocr_page=page_ocr)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True


# ── T12 · Contrato Triestado: Glifo I/l aislado sin contexto → AMBIGUOUS ──────

def test_t12_glifo_I_aislado_sin_contexto_es_ambiguous():
    """T12 (nace ROJO): Un glifo 'I' sans-serif aislado sin palabras circundantes
    ni evidencia contextual independiente es materialmente colisionante con una regla.
    Debe clasificarse como AMBIGUOUS."""
    img = _render_elements(
        text_list=[("I", "helv", 48.0, (100, 100))],
        line_list=None
    )
    rect_px = (88, 53, 112, 112)
    res = _call_tri_state(img[53:112, 88:112], rect_px, global_img=img)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True


# ── T13 · Contrato Triestado: Consenso multimodo real sobre I/| → AMBIGUOUS ───

def test_t13_consenso_multimodo_real_ejecutado_no_resuelve_ambiguous():
    """T13 (nace ROJO): Ejecuta explícitamente los tres modos congelados (--psm 6,
    --psm 3, --psm 11). Comprueba que, aunque los tres modos lean unánimemente '|' o 'I'
    por correlación del clasificador subyacente, dicho acuerdo correlacionado NO basta
    para promover el trazo a TEXT_COMPATIBLE. El resultado debe seguir siendo AMBIGUOUS."""
    img = _render_elements(
        text_list=[("CAPITULO", "helv", 36.0, (50, 100))],
        line_list=[((260, 74), (260, 100), 3.0)]
    )
    pil_img = Image.fromarray(img, "L")

    # Ejecución explícita y real de los 3 modos congelados
    ocr_results = {}
    for mode in FC008_MODES:
        provider = TesseractOCRProvider(config=mode)
        page_mode = provider.process(pil_img, 300.0)
        ocr_results[mode] = [(w.text, w.conf, w.bbox_px) for w in page_mode.words]

    # Demostrar que los tres modos produjeron lecturas correlacionadas (ambos leen '|' o 'I')
    for mode, words in ocr_results.items():
        assert len(words) >= 2, f"Modo {mode} no encontró palabras esperadas: {words}"
        read_texts = [w[0] for w in words]
        assert any(t in ("|", "I", "l", "1", "II!") for t in read_texts), (
            f"Modo {mode} no leyó carácter correlacionado: {read_texts}"
        )

    # Preparar span desde el localizador primario
    obs_prim = TesseractOCRProvider(config="--psm 6")
    page_prim = obs_prim.process(pil_img, 300.0)
    line = page_prim.find_line_containing("CAPITULO")
    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    provenance = {"modes_attempted": list(FC008_MODES), "per_mode": ocr_results}
    res = _call_tri_state(img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]],
                          rect_px, span=span, global_img=img, ocr_page=page_prim,
                          ocr_provenance=provenance)
    assert res["status"] == "AMBIGUOUS", (
        f"Consenso correlacionado de Tesseract promovió incorrectamente a {res['status']}"
    )
    assert res["has_structure"] is True


# ── T14 · Contrato Triestado: Componente complejo aislado en Runtime → AMBIGUOUS

def test_t14_componente_complejo_aislado_en_runtime_es_ambiguous():
    """T14 (nace ROJO): Un componente aislado complejo (ej. glifo 'H') posee ramas y
    travesaños (morfología rica), pero en Runtime, sin provenance positiva del target
    ni contexto de renglón completo, NO puede asumirse automáticamente TEXT_COMPATIBLE.
    Esperado en Runtime: AMBIGUOUS (no forzar)."""
    img = _render_elements(
        text_list=[("H", "helv", 48.0, (100, 100))],
        line_list=None
    )
    rect_px = (88, 53, 212, 112)
    res = _call_tri_state(img[53:112, 88:212], rect_px, global_img=img)
    # Contrato estricto: en Runtime sin contexto completo, debe ser AMBIGUOUS
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True


# ── T15 · Contrato Triestado: CAL-005 real LOCAL → AMBIGUOUS ─────────────────

@pytest.mark.skipif(not os.path.exists(CAL005),
                    reason="CAL-005 real es LOCAL (no commiteado)")
def test_t15_cal005_real_local_es_ambiguous():
    """T15 (nace ROJO): En CAL-005 real, el titular 'PREFACIO DE MICHAEL LYDON'
    NO tiene continuidad exterior (no es PROTECTED_STRUCTURE), pero tampoco
    debe forzarse a TEXT_COMPATIBLE sin atribución formal independiente.
    Estado Runtime esperado: AMBIGUOUS.
    Epistemológicamente el caso permanece unresolved
    con las señales actuales."""
    doc = pymupdf.open(CAL005)
    pix = doc[0].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    rect_px = (7752, 3646, 9882, 3792)
    res = _call_tri_state(img[3646:3792, 7752:9882], rect_px, global_img=img)
    assert res["status"] != "PROTECTED_STRUCTURE", "CAL-005 no tiene continuidad exterior"
    assert res["status"] == "AMBIGUOUS"


# ══════════════════════════════════════════════════════════════════════════════
# CONTROLES ADVERSARIALES Y DE CARACTERIZACIÓN OUTSIDE_CONTINUITY (T16–T21)
# ══════════════════════════════════════════════════════════════════════════════

# ── T16 · Caracterización: Raya/Columna oscura de 1 px con continuidad exterior ──

def test_t16_columna_oscura_1px_con_continuidad_exterior():
    """T16 (Caracterización): Evalúa el comportamiento material de V1 ante una
    sola columna oscura de 1 px con continuidad exterior >= 15 px.
    Registra el estado observado sin presuponer normativamente si constituye
    estructura legítima o ruido."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    img[50:250, 300] = 0
    rect_px = (200, 100, 400, 200)
    local = img[100:200, 200:400]

    res = _call_tri_state(local, rect_px, global_img=img)
    assert res["status"] in ("PROTECTED_STRUCTURE", "AMBIGUOUS")
    assert res["evidence_trace"]["outside_continuity_cols"] == 1
    assert res["evidence_trace"]["max_outside_run_px"] >= 15


# ── T17 · Control Positivo: Regla vertical gráfica real de 4 px ───────────────

def test_t17_regla_grafica_real_ancho_4px_con_continuidad():
    """T17 (Control Positivo): Una regla gráfica vertical real de ancho 4 px con
    continuidad exterior >= 15 px debe ser clasificada inequívocamente como PROTECTED_STRUCTURE."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    img[50:250, 300:304] = 0
    rect_px = (200, 100, 400, 200)
    local = img[100:200, 200:400]

    res = _call_tri_state(local, rect_px, global_img=img)
    assert res["status"] == "PROTECTED_STRUCTURE"
    assert res["has_structure"] is True
    assert res["evidence_trace"]["outside_continuity_cols"] == 4
    assert res["evidence_trace"]["max_outside_run_px"] >= 15


# ── T18 · Control Adversarial: Misma X con gap blanco exacto de 1 px en borde ─

def test_t18_estructura_alineada_con_gap_blanco_1px_es_ambiguous():
    """T18 (Control Adversarial): Estructura vertical en la misma coordenada X, pero
    separada por un gap blanco de exactamente 1 px en el borde del span (y=99 blanco).
    NO existe continuidad material conectada → debe ser clasificado como AMBIGUOUS."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    # Tinta dentro del span: y=100..200
    img[100:200, 300:304] = 0
    # Tinta fuera pero con gap de 1 px en y=99: y=50..99
    img[50:99, 300:304] = 0
    rect_px = (200, 100, 400, 200)
    local = img[100:200, 200:400]

    res = _call_tri_state(local, rect_px, global_img=img)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True
    assert res["evidence_trace"]["outside_continuity_cols"] == 0
    assert res["evidence_trace"]["max_outside_run_px"] == 0


# ── T19 · Control Adversarial: Misma X con gap blanco de 2–3 px ───────────────

def test_t19_estructura_alineada_con_gap_blanco_2_3px_es_ambiguous():
    """T19 (Control Adversarial): Estructura vertical en la misma coordenada X, pero
    separada por un gap blanco de 3 px en el borde del span (y=97..99 blanco).
    NO existe continuidad material conectada → debe ser clasificado como AMBIGUOUS."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    img[100:200, 300:304] = 0
    img[50:97, 300:304] = 0
    rect_px = (200, 100, 400, 200)
    local = img[100:200, 200:400]

    res = _call_tri_state(local, rect_px, global_img=img)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True
    assert res["evidence_trace"]["outside_continuity_cols"] == 0
    assert res["evidence_trace"]["max_outside_run_px"] == 0


# ── T20 · Control Adversarial: Ruido aleatorio exterior sin conexión material ──

def test_t20_ruido_aleatorio_exterior_sin_conexion_material_es_ambiguous():
    """T20 (Control Adversarial): Ruido aleatorio seeded fuera del span, sin
    conexión material con la tinta interior. NO debe generar falso PROTECTED_STRUCTURE."""
    np.random.seed(42)
    img = np.full((300, 600), 255, dtype=np.uint8)
    # Tinta dentro del span sin tocar los bordes (y=120..180)
    img[120:180, 300:304] = 0
    # Ruido exterior al 5%
    noise_mask = np.random.rand(300, 600) < 0.05
    noise_mask[100:200, :] = False
    img[noise_mask] = 0
    rect_px = (200, 100, 400, 200)
    local = img[100:200, 200:400]

    res = _call_tri_state(local, rect_px, global_img=img)
    assert res["status"] == "AMBIGUOUS"
    assert res["has_structure"] is True
    assert res["evidence_trace"]["outside_continuity_cols"] == 0


# ── T21 · Caracterización: Regla vertical anti-aliased / grises con dark=128 ──

def test_t21_regla_vertical_antialiased_grises_medicion():
    """T21 (Caracterización / Medición): Mide el comportamiento de V1 bajo dark=128.
    Registra empíricamente:
      - OBSERVED UNDER dark=128:
        * Gris oscuro (val=100 <= 127) → status='PROTECTED_STRUCTURE'
        * Gris claro (val=160 >= 128)  → status='AMBIGUOUS' (outside_cols=0)
    Ambos estados mantienen has_structure=True sin presuposición de suficiencia."""
    # Medición 1: Gris oscuro (100)
    img_dark = np.full((300, 600), 255, dtype=np.uint8)
    img_dark[50:250, 300:304] = 100
    rect_px = (200, 100, 400, 200)
    res_dark = _call_tri_state(img_dark[100:200, 200:400], rect_px, global_img=img_dark)
    assert res_dark["status"] == "PROTECTED_STRUCTURE"
    assert res_dark["has_structure"] is True
    assert res_dark["evidence_trace"]["outside_continuity_cols"] == 4

    # Medición 2: Gris claro (160)
    img_light = np.full((300, 600), 255, dtype=np.uint8)
    img_light[50:250, 300:304] = 160
    rect_px = (200, 100, 400, 200)
    res_light = _call_tri_state(img_light[100:200, 200:400], rect_px, global_img=img_light)
    assert res_light["status"] == "AMBIGUOUS"
    assert res_light["has_structure"] is True
    assert res_light["evidence_trace"]["outside_continuity_cols"] == 0


# ── Diagnóstico: Sweep de Anchuras (1, 2, 3, 4, 8 px) ─────────────────────────

def test_diagnostico_sweep_anchuras_conectadas():
    """Diagnóstico de Caracterización (WIDTH): Mide el comportamiento material de V1
    frente a trazos continuos de diferentes anchuras (1, 2, 3, 4, 8 px) con continuidad
    exterior >= 15 px.
    Registra empíricamente: width_px, status, outside_continuity_cols, max_outside_run_px.
    NO introduce ningún threshold normativo de anchura mínima."""
    records = []
    for w in [1, 2, 3, 4, 8]:
        img = np.full((300, 600), 255, dtype=np.uint8)
        img[50:250, 300:300+w] = 0
        rect_px = (200, 100, 400, 200)
        res = _call_tri_state(img[100:200, 200:400], rect_px, global_img=img)

        trace = res["evidence_trace"]
        rec = {
            "width_px": w,
            "status": res["status"],
            "outside_continuity_cols": trace["outside_continuity_cols"],
            "max_outside_run_px": trace["max_outside_run_px"],
        }
        records.append(rec)

        # Registro observable: fuera continuo detecta exactamente las w columnas
        assert trace["outside_continuity_cols"] == w
        assert trace["max_outside_run_px"] >= 15
        assert res["status"] in ("PROTECTED_STRUCTURE", "AMBIGUOUS")

    assert len(records) == 5


# ── Diagnóstico: Sweep de Gaps en el Borde (0, 1, 2, 3 px) ─────────────────────

def test_diagnostico_sweep_gaps_en_borde():
    """Diagnóstico de Caracterización (GAP): Mide el comportamiento material de V1
    cuando existe tinta alineada en la misma X pero separada por un gap blanco en el
    borde del span (0, 1, 2, 3 px).
    Registra empíricamente: gap_px, status, outside_continuity_cols, max_outside_run_px.
    Verifica que la continuidad requiere conexión material estricta (gap=0 vs gap>=1)."""
    records = []
    for gap in [0, 1, 2, 3]:
        img = np.full((300, 600), 255, dtype=np.uint8)
        img[100:200, 300:304] = 0
        if 100 - gap > 50:
            img[50:100-gap, 300:304] = 0
        rect_px = (200, 100, 400, 200)
        res = _call_tri_state(img[100:200, 200:400], rect_px, global_img=img)

        trace = res["evidence_trace"]
        rec = {
            "gap_px": gap,
            "status": res["status"],
            "outside_continuity_cols": trace["outside_continuity_cols"],
            "max_outside_run_px": trace["max_outside_run_px"],
        }
        records.append(rec)

        if gap == 0:
            assert trace["outside_continuity_cols"] == 4
            assert trace["max_outside_run_px"] >= 15
            assert res["status"] == "PROTECTED_STRUCTURE"
        else:
            assert trace["outside_continuity_cols"] == 0
            assert trace["max_outside_run_px"] == 0
            assert res["status"] == "AMBIGUOUS"

    assert len(records) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# FC-009 STAGE 2 · RUNTIME OBSERVABILITY CONTRACT (TESTS NACEN ROJOS)
# ═══════════════════════════════════════════════════════════════════════════════
# Principios de Stage 2:
# 1. INTEGRATION-ONLY / Telemetría Runtime: raster_edit invoca vertical_structure_assessment
#    y registra la evidencia en report["gates"]["vertical_structure_assessment"].
# 2. SEPARACIÓN OBSERVACIÓN vs DECISIÓN: La telemetría Stage 1 (PROTECTED/AMBIGUOUS)
#    convive con el gate legacy sin alterar la política de decisión de seguridad.
# 3. T1 y T5 permanecen HISTORICAL_RED (FC-009 continúa OPEN hasta Stage 3).
# 4. Los siguientes tests nacen ROJOS porque raster.py aún no invoca Stage 1 en Runtime.


def _create_synthetic_raster_pdf(path: str, text: str = "PREFACIO DE MICHAEL LYDON",
                                  fontsize_pt: float = 36.0, fontname: str = "hebo",
                                  add_h_line: bool = False, add_v_line: bool = False,
                                  add_outside_v_rule: bool = False,
                                  dpi: int = 300) -> str:
    """Helper de prueba: Genera un PDF puramente raster a 300 DPI con o sin trazos gráficos."""
    page_w_pt, page_h_pt = 600.0, 200.0
    doc_txt = pymupdf.open()
    page = doc_txt.new_page(width=page_w_pt, height=page_h_pt)
    page.insert_text(pymupdf.Point(50, 100), text, fontname=fontname, fontsize=fontsize_pt)
    shape = page.new_shape()
    if add_h_line:
        shape.draw_line(pymupdf.Point(0, 105), pymupdf.Point(600, 105))
        shape.finish(color=(0, 0, 0), width=4)
    if add_v_line:
        shape.draw_line(pymupdf.Point(230, 20), pymupdf.Point(230, 180))
        shape.finish(color=(0, 0, 0), width=4)
    if add_outside_v_rule:
        # Regla vertical de tabla (como en T8) que cruza entre columnas y penetra fuera del span
        shape.draw_line(pymupdf.Point(235, 20), pymupdf.Point(235, 180))
        shape.finish(color=(0, 0, 0), width=2.0)
    if add_h_line or add_v_line or add_outside_v_rule:
        shape.commit()
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    img_bytes = pix.tobytes("png")
    doc_txt.close()

    doc_pdf = pymupdf.open()
    npage = doc_pdf.new_page(width=page_w_pt, height=page_h_pt)
    npage.insert_image(npage.rect, stream=img_bytes)
    doc_pdf.save(path)
    doc_pdf.close()
    return path


# ── S2-01 · ROUTE REACHED: raster_edit alcanza vertical_structure_assessment ──

def test_stage2_raster_edit_reaches_vertical_assessment(tmp_path):
    """S2-01 (nace ROJO): Demuestra que raster_edit alcanza el evaluador de Stage 1.
    Contrato: report['gates'] debe contener la clave 'vertical_structure_assessment'."""
    pdf_in = str(tmp_path / "s2_01_in.pdf")
    pdf_out = str(tmp_path / "s2_01_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TITULO PRINCIPAL", fontsize_pt=36.0)

    rep = raster_edit(pdf_in, "TITULO", "NUEVO", pdf_out)
    assert "gates" in rep, "report no contiene sección gates"
    assert "vertical_structure_assessment" in rep["gates"], (
        "Stage 2 NOT REACHED: raster_edit no incluyó vertical_structure_assessment en gates"
    )


# ── S2-02 · ROUTE EXECUTED: raster_edit ejecuta y reporta evidencia real ──────

def test_stage2_raster_edit_executes_vertical_assessment(tmp_path):
    """S2-02 (nace ROJO): Demuestra que vertical_structure_assessment fue realmente
    ejecutado con contexto global y traza de evidencia material completa."""
    pdf_in = str(tmp_path / "s2_02_in.pdf")
    pdf_out = str(tmp_path / "s2_02_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TITULO PRINCIPAL", fontsize_pt=36.0)

    rep = raster_edit(pdf_in, "TITULO", "NUEVO", pdf_out)
    v_info = rep.get("gates", {}).get("vertical_structure_assessment")
    assert v_info is not None, "vertical_structure_assessment no ejecutado en gates"
    assert "evidence_trace" in v_info, "Falta evidence_trace en la telemetría"
    trace = v_info["evidence_trace"]
    assert "outside_continuity_cols" in trace, "Falta outside_continuity_cols en trace"
    assert "max_outside_run_px" in trace, "Falta max_outside_run_px en trace"
    assert trace["global_context_available"] is True, "global_img no estuvo disponible en Runtime"


# ── S2-03 · Telemetría PROTECTED_STRUCTURE ante regla vertical exterior ───────

def test_stage2_protected_structure_telemetry(tmp_path):
    """S2-03 (corregido): Una regla gráfica vertical (como la de T8 entre columnas)
    que penetra fuera del span debe ser reportada como PROTECTED_STRUCTURE y
    rechazada con grafico_en_region."""
    pdf_in = str(tmp_path / "s2_03_in.pdf")
    pdf_out = str(tmp_path / "s2_03_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="COLUMNA A   COLUMNA B", fontsize_pt=36.0,
                                 add_outside_v_rule=True)

    rep = raster_edit(pdf_in, "COLUMNA", "NUEVO", pdf_out)
    v_info = rep.get("gates", {}).get("vertical_structure_assessment")
    assert v_info is not None, "Telemetría Stage 1 ausente en gates"
    assert v_info["status"] == "PROTECTED_STRUCTURE"
    assert v_info["evidence_trace"]["outside_continuity_cols"] >= 1
    assert rep["dimensions"]["graphics_clearance_ok"] is False
    assert rep["reject_reason"] == "grafico_en_region"


# ── S2-04 · Telemetría AMBIGUOUS no altera decisión de clearance ──────────────

def test_stage2_ambiguous_telemetry_does_not_override_legacy(tmp_path):
    """S2-04 (nace ROJO): En tipografía display sin continuidad exterior ni oráculo,
    la telemetría reporta AMBIGUOUS, y la decisión final corresponde estrictamente al
    pipeline pre-gate legacy."""
    pdf_in = str(tmp_path / "s2_04_in.pdf")
    pdf_out = str(tmp_path / "s2_04_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TITULO AISLADO", fontsize_pt=36.0)

    rep = raster_edit(pdf_in, "TITULO", "NUEVO", pdf_out)
    v_info = rep.get("gates", {}).get("vertical_structure_assessment")
    assert v_info is not None, "Telemetría Stage 1 ausente en gates"
    assert v_info["status"] == "AMBIGUOUS"
    # Preservación de decisión legacy
    legacy_struct = rep["gates"].get("structure", {})
    assert rep["dimensions"]["graphics_clearance_ok"] == (not legacy_struct.get("has_structure", True))


# ── S2-05 · Estructuras horizontales continúan rechazándose ───────────────────

def test_stage2_horizontal_structure_behavior_unchanged(tmp_path):
    """S2-05 (nace ROJO): Una regla horizontal gráfica real debe seguir siendo detectada
    por el evaluador horizontal y rechazada con grafico_en_region."""
    pdf_in = str(tmp_path / "s2_05_in.pdf")
    pdf_out = str(tmp_path / "s2_05_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TEXTO CON SUBRAYADO", fontsize_pt=18.0,
                                 add_h_line=True)

    rep = raster_edit(pdf_in, "TEXTO", "NUEVO", pdf_out)
    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["gates"]["structure"]["h_line_rows"] >= 2
    assert rep["dimensions"]["graphics_clearance_ok"] is False
    assert rep["reject_reason"] == "grafico_en_region"


# ── S2-06 · Regresión G2_linea_cruza preservada ───────────────────────────────

def test_stage2_g2_linea_cruza_behavior_unchanged(dataset, tmp_path):
    """S2-06 (nace ROJO): El fixture histórico G2_linea_cruza debe mantener su
    clasificación HONEST_REJECT por grafico_en_region al incorporar telemetría Stage 1."""
    pdf_out = str(tmp_path / "s2_06_out.pdf")
    rep = raster_edit(dataset["G2_linea_cruza"]["pdf"], "Perez", "Garcia", pdf_out)

    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["classification"] == "HONEST_REJECT"
    assert rep["reject_reason"] == "grafico_en_region"


# ── S2-07 · Regresión G2_borde_cercano preservada ──────────────────────────────

def test_stage2_g2_borde_cercano_behavior_unchanged(dataset, tmp_path):
    """S2-07 (nace ROJO): El fixture histórico G2_borde_cercano debe mantener su
    clearance graphics_clearance_ok=True al incorporar telemetría Stage 1."""
    pdf_out = str(tmp_path / "s2_07_out.pdf")
    rep = raster_edit(dataset["G2_borde_cercano"]["pdf"], "Fecha", "Dia", pdf_out)

    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["dimensions"]["graphics_clearance_ok"] is True


# ── S2-08 · Liveness de texto normal (8–18 pt) no sufre regresión ─────────────

@pytest.mark.parametrize("font,size_pt", [
    ("helv", 11.0),
    ("hebo", 11.0),
    ("cour", 11.0),
])
def test_stage2_normal_text_liveness_unchanged(font, size_pt, tmp_path):
    """S2-08 (nace ROJO): El texto ordinario (11 pt) debe conservar graphics_clearance_ok=True
    sin sufrir falsos rechazos, mientras reporta telemetría AMBIGUOUS."""
    pdf_in = str(tmp_path / f"s2_08_{font}_{int(size_pt)}.pdf")
    pdf_out = str(tmp_path / f"s2_08_{font}_{int(size_pt)}_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="Texto Ordinario de Parrafo",
                                 fontsize_pt=size_pt, fontname=font)

    rep = raster_edit(pdf_in, "Texto", "Parrafo", pdf_out)
    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["dimensions"]["graphics_clearance_ok"] is True
    assert rep["gates"]["vertical_structure_assessment"]["status"] == "AMBIGUOUS"


# ── S2-09 · Observational Equivalence: Telemetría es neutral en decisiones ────

OBSERVED_LEGACY_BASELINES = {
    "A_scan_limpio": {
        "old": "Perez", "new": "Garcia", "strat": "mean",
        "classification": "PASS", "reject_reason": None,
        "graphics_clearance_ok": True, "geometry_ok": True, "typography_ok": True,
        "background_ok": True, "output_written": True, "policy": "fit",
    },
    "G2_linea_cruza": {
        "old": "Perez", "new": "Garcia", "strat": "mean",
        "classification": "HONEST_REJECT", "reject_reason": "grafico_en_region",
        "graphics_clearance_ok": False, "geometry_ok": True, "typography_ok": True,
        "background_ok": None, "output_written": False, "policy": None,
    },
    "G2_borde_cercano": {
        "old": "Fecha", "new": "Dia", "strat": "mean",
        "classification": "PASS", "reject_reason": None,
        "graphics_clearance_ok": True, "geometry_ok": True, "typography_ok": True,
        "background_ok": True, "output_written": True, "policy": "fit",
    },
    "M_rotacion_4": {
        "old": "Perez", "new": "Garcia", "strat": "white",
        "classification": "HONEST_REJECT", "reject_reason": "page_skew",
        "graphics_clearance_ok": True, "geometry_ok": False, "typography_ok": True,
        "background_ok": None, "output_written": False, "policy": None,
    },
    "N_fondo_gradiente": {
        "old": "Perez", "new": "Garcia", "strat": "white",
        "classification": "HONEST_REJECT", "reject_reason": "background",
        "graphics_clearance_ok": True, "geometry_ok": True, "typography_ok": True,
        "background_ok": False, "output_written": True, "policy": "fit",
    },
}


@pytest.mark.parametrize("case_name", list(OBSERVED_LEGACY_BASELINES.keys()))
def test_stage2_telemetry_preserves_legacy_decision_fingerprint(case_name, dataset, tmp_path):
    """S2-09 (nace ROJO): Demuestra que Stage 2 es neutral en decisiones para un conjunto
    representativo de casos (OBSERVED_LEGACY_BASELINES).
    Exige que los campos de decisión sean idénticos al baseline legacy y que además
    el reporte incluya la telemetría 'vertical_structure_assessment' en gates."""
    base = OBSERVED_LEGACY_BASELINES[case_name]
    pdf_in = dataset[case_name]["pdf"]
    pdf_out = str(tmp_path / f"s2_09_{case_name}_out.pdf")

    rep = raster_edit(pdf_in, base["old"], base["new"], pdf_out, strategy=base["strat"])
    out_exists = os.path.exists(pdf_out) and os.path.getsize(pdf_out) > 0

    # 1. Telemetría requerida (Stage 2 contract) -> Nace ROJO por ausencia de la key
    assert "vertical_structure_assessment" in rep.get("gates", {}), (
        f"Stage 2 telemetría ausente en gates para {case_name}"
    )

    # 2. Equivalencia estricta de campos de decisión
    assert rep["classification"] == base["classification"]
    assert rep["reject_reason"] == base["reject_reason"]
    assert rep["dimensions"].get("graphics_clearance_ok") == base["graphics_clearance_ok"]
    assert rep["dimensions"].get("geometry_ok") == base["geometry_ok"]
    assert rep["dimensions"].get("typography_ok") == base["typography_ok"]
    assert rep["dimensions"].get("background_ok") == base["background_ok"]
    assert rep.get("stages", {}).get("validate", {}).get("policy") == base["policy"]
    assert out_exists == base["output_written"]


# ── S2-10 · Invariante de Reparación: Rechazo de gráficos previene repair ──────

def test_stage2_graphics_reject_still_prevents_repair(tmp_path):
    """S2-10 (nace ROJO): Cuando el gate de gráficos rechaza, repair_region y render
    NO son ejecutados (report['stages'].get('render') es None)."""
    pdf_in = str(tmp_path / "s2_10_in.pdf")
    pdf_out = str(tmp_path / "s2_10_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TEXTO CON REGLA", fontsize_pt=24.0,
                                 add_h_line=True)

    rep = raster_edit(pdf_in, "TEXTO", "NUEVO", pdf_out)
    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["dimensions"]["graphics_clearance_ok"] is False
    assert "render" not in rep["stages"], "Invariante violado: render fue ejecutado tras rechazo"


# ── S2-11 · Invariante de Escritura: Rechazo pre-gate previene salida PDF ──────

def test_stage2_graphics_reject_still_prevents_write(tmp_path):
    """S2-11 (nace ROJO): Cuando ocurre un rechazo pre-gate por gráficos,
    no se escribe ningún byte en el archivo de salida."""
    pdf_in = str(tmp_path / "s2_11_in.pdf")
    pdf_out = str(tmp_path / "s2_11_out.pdf")
    _create_synthetic_raster_pdf(pdf_in, text="TEXTO CON REGLA", fontsize_pt=24.0,
                                 add_h_line=True)

    rep = raster_edit(pdf_in, "TEXTO", "NUEVO", pdf_out)
    assert "vertical_structure_assessment" in rep.get("gates", {}), "Telemetría Stage 1 ausente"
    assert rep["reject_reason"] == "grafico_en_region"
    assert not os.path.exists(pdf_out) or os.path.getsize(pdf_out) == 0, (
        "Invariante violado: archivo PDF de salida fue generado tras rechazo pre-gate"
    )
