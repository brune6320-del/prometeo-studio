"""
PROMETEO · FC-009 STAGE 3 · RED CONTRACT TESTS
───────────────────────────────────────────────
POSITIVE TEXT ATTRIBUTION & OBSERVED GLYPH MODULATION COMPATIBILITY

Metodología:
  RED TESTS WRITTEN BEFORE IMPLEMENTATION.
  Stage 3 al crear este archivo:
    ELIGIBLE = YES
    REACHED = NO
    EXECUTED = NO
    VERIFIED = NO

Correcciones Contractuales Obligatorias:
  1. H9 es etiquetada como PROMISING_COMPOSITE_HYPOTHESIS (no PROVEN_DISCRIMINATOR).
  2. STEM BUDGET NO depende de diccionarios fijos por letra (M=2, I=1). Utiliza
     OBSERVED_GLYPH_MODULATION_COMPATIBILITY como señal observable y falsable.
  3. CAL-005 es CALIBRATION_CASE / TARGET (no HOLDOUT). Nace RED esperando implementación.
  4. Política de decisiones: NON_TARGET_CASES idénticos (invariante), AUTHORIZED_TARGET_CASES
     declarados explícitamente, UNPLANNED_DECISION_DELTA = FAILURE.
  5. Jerarquía de Seguridad:
       IF protection_counterevidence:
           PROTECTED_STRUCTURE
       ELIF positive_text_evidence == STRONG:
           TEXT_COMPATIBLE
       ELSE:
           AMBIGUOUS
  6. outside_continuity == 0 es únicamente una guardia negativa (SAFETY_GUARD), NO evidencia positiva.
  7. Métricas normalizadas a escala de glifo/span height/DPI; thresholds normativos no congelados.

Inventario de Tests:
  S3-01 · [NON_TARGET / GUARD] Ordinary text outside Stage 3 decision boundary (legacy pass);
  S3-02 · [TARGET / RED] Synthetic display text 36 pt positive attribution;
  S3-03 · [NON_TARGET / GUARD] Single glyph 'I' isolated → AMBIGUOUS (fail-closed);
  S3-04 · [NON_TARGET / GUARD] Graphic 1px lookalike → AMBIGUOUS / PROTECTED;
  S3-05 · [NON_TARGET / GUARD] Confined table rule without outside continuity → AMBIGUOUS;
  S3-06 · [NON_TARGET / GUARD] Text + vertical rule crossing word → AMBIGUOUS / PROTECTED;
  S3-07 · [NON_TARGET / GUARD] Text + horizontal underline → rejected by horizontal gate;
  S3-08 · [NON_TARGET / GUARD] Nearby outer border does not intersect target → preserved PASS;
  S3-09 · [NON_TARGET / GUARD] OCR absorbs rule into bbox → AMBIGUOUS / PROTECTED;
  S3-10 · [TARGET / RED] CAL-005 real scan page 0 title positive attribution;
  S3-11 · [NON_TARGET / GUARD] S2-03 corrected table geometry → PROTECTED_STRUCTURE;
  S3-12 · [NON_TARGET / GUARD] Scanner scratch / vertical dust artifact → AMBIGUOUS / PROTECTED;
  S3-13 · [NON_TARGET / GUARD] Multi-PSM correlated error alone does not grant STRONG;
  S3-14 · [NON_TARGET / GUARD] Protection dominance over positive text evidence;
  S3-15 · [NON_TARGET / GUARD] Decision delta accounting baseline preservation;
  S3-A1 · [NON_TARGET / GUARD] Adversarial: Barcode matching cluster count → AMBIGUOUS;
  S3-A2 · [NON_TARGET / GUARD] Adversarial: Confined solid bar in exact envelope → AMBIGUOUS;
  S3-A3 · [NON_TARGET / GUARD] Adversarial: Grid aligned with word gutters → AMBIGUOUS / PROTECTED;
  S3-A4 · [NON_TARGET / GUARD] Adversarial: Faint vertical stripes behind display text → AMBIGUOUS;
  S3-A5 · [TARGET / RED] Adversarial: Times/serif display text positive attribution;
  S3-A6 · [TARGET / RED] Adversarial: Multi-font rhythm invariance (Helv, Hebo, Times, Cour);
  S3-A7 · [TARGET / RED] Adversarial: Multi-DPI scale invariance (150, 300, 600 DPI).
"""
import os
import pytest
import numpy as np
import pymupdf
from PIL import Image

import fixtures_raster
import verifier2
from raster import (
    raster_edit,
    _span_region_px,
    build_span_from_ocr,
    SpaceTransform,
)
from ocr_provider import TesseractOCRProvider

HERE = os.path.dirname(os.path.abspath(__file__))
CAL005 = os.path.join(HERE, "reality_corpus", "docs", "CAL-005_1001.pdf")


# ── Fixture Helpers ──────────────────────────────────────────────────────────

def _render_stage3_synthetic_image(text: str, fontsize_pt: float = 36.0,
                                   fontname: str = "hebo",
                                   add_h_line: bool = False,
                                   add_v_line: bool = False,
                                   v_line_pos: tuple = (230, 20, 230, 180),
                                   v_line_width: float = 4.0,
                                   add_stripes_bg: bool = False,
                                   dpi: int = 300) -> np.ndarray:
    """Renderiza imágenes sintéticas con control geométrico preciso para Stage 3."""
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


def _create_stage3_synthetic_pdf(path: str, text: str = "TITULO PRINCIPAL DISPLAY",
                                 fontsize_pt: float = 36.0,
                                 fontname: str = "hebo",
                                 add_h_line: bool = False,
                                 add_v_line: bool = False,
                                 v_line_pos: tuple = (230, 20, 230, 180),
                                 v_line_width: float = 4.0,
                                 add_border_nearby: bool = False,
                                 dpi: int = 300) -> None:
    """Genera PDFs sintéticos para tests de integración Runtime en raster_edit."""
    doc = pymupdf.open()
    page_w_pt, page_h_pt = 600.0, 200.0
    page = doc.new_page(width=page_w_pt, height=page_h_pt)
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
    if add_border_nearby:
        shape.draw_rect(pymupdf.Rect(30, 20, 570, 180))
        shape.finish(color=(0, 0, 0), width=1.5)
    if add_h_line or add_v_line or add_border_nearby:
        shape.commit()
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    doc_out = pymupdf.open()
    page_out = doc_out.new_page(width=page_w_pt, height=page_h_pt)
    page_out.insert_image(page_out.rect, pixmap=pix)
    doc_out.save(path)
    doc_out.close()
    doc.close()


@pytest.fixture(scope="session")
def dataset():
    return fixtures_raster.build_all()


# ── S3-01 · ORDINARY TEXT OUTSIDE STAGE 3 BOUNDARY ───────────────────────────

def test_s3_01_ordinary_text_outside_stage3_boundary():
    """
    LAB_TRUE_NATURE: Texto ordinario de cuerpo (11 pt Helvetica limpio).
    RUNTIME_ALLOWED_EVIDENCE: local_region, span, line_structure_in_region.
    EXPECTED_RUNTIME_STATUS: OUTSIDE_STAGE3_DECISION_BOUNDARY (local_v_cols == 0).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es texto ordinario; Runtime lo sabe porque las astas
                     no superan el umbral legacy lv=20 px y local_v_cols == 0.
    WHY_RED: GREEN GUARDRAIL (demuestra que el texto ordinario conserva liveness sin Stage 3).
    """
    img = _render_stage3_synthetic_image("Texto ordinario de cuerpo editorial.", fontsize_pt=11.0, fontname="helv")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("ordinario")
    assert line is not None, "OCR no detectó texto ordinario"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)

    res = verifier2.line_structure_in_region(img, rect_px)
    assert not res["has_structure"], "Texto ordinario 11 pt no debe activar gate de gráficos"
    assert res["v_line_cols"] == 0, "Texto ordinario debe quedar fuera de la frontera de decisión Stage 3"


# ── S3-02 · DISPLAY TEXT POSITIVE ATTRIBUTION (TARGET) ───────────────────────

def test_s3_02_display_text_positive_attribution():
    """
    LAB_TRUE_NATURE: Texto display limpio grande (36 pt Helvetica-Bold).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: TEXT_COMPATIBLE con text_evidence_level == 'STRONG'.
    TARGET_CLASS: TARGET.
    ORACLE_BOUNDARY: LAB sabe que es texto limpio sin tablas; Runtime debe derivar
                     POSITIVE_TEXT_ATTRIBUTION mediante envelope, gutters y ritmo observable.
    WHY_RED: NACE ROJO porque vertical_structure_assessment devuelve actualmente AMBIGUOUS
             y no existe implementación de atribución positiva en Runtime.
    """
    img = _render_stage3_synthetic_image("TITULO PRINCIPAL DISPLAY", fontsize_pt=36.0, fontname="hebo")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR no encontró título display"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )

    # Contrato Stage 3: Debe promover a TEXT_COMPATIBLE al demostrar evidencia fuerte
    assert v_assessment.get("status") == "TEXT_COMPATIBLE", (
        f"Stage 3 Target RED: Se esperaba TEXT_COMPATIBLE pero se obtuvo: {v_assessment.get('status')}"
    )
    assert v_assessment.get("text_evidence_level") == "STRONG", (
        f"Stage 3 Target RED: text_evidence_level debe ser STRONG, obtenido: {v_assessment.get('text_evidence_level')}"
    )
    assert not v_assessment.get("has_structure"), "TEXT_COMPATIBLE no debe ser clasificado como estructura protegida"


# ── S3-03 · SINGLE GLYPH 'I' ISOLATED → AMBIGUOUS (FAIL-CLOSED) ─────────────

def test_s3_03_single_glyph_I_ambiguous_fail_closed():
    """
    LAB_TRUE_NATURE: Glifo aislado 'I' sans-serif (48 pt).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (Fail-Closed).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es la letra 'I'; Runtime no puede diferenciar un fuste
                     vertical aislado de 1 carácter de una regla gráfica corta sin contexto.
    WHY_RED: GREEN GUARDRAIL (Stage 1 ya emite AMBIGUOUS ante fustes aislados).
    """
    img = _render_stage3_synthetic_image("I", fontsize_pt=48.0, fontname="hebo")
    rect_px = (88, 53, 112, 112)
    local_region = img[53:112, 88:112]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span={"text": "I", "id": "r0"},
        global_img=img,
    )
    assert v_assessment["status"] == "AMBIGUOUS", (
        f"Glifo 'I' aislado no debe promoverse a TEXT_COMPATIBLE: {v_assessment}"
    )
    assert v_assessment["has_structure"] is True, "AMBIGUOUS debe mantener has_structure=True (fail-closed)"


# ── S3-04 · GRAPHIC 1PX LOOKALIKE → AMBIGUOUS / PROTECTED ────────────────────

def test_s3_04_graphic_1px_lookalike_ambiguous_or_protected():
    """
    LAB_TRUE_NATURE: Regla gráfica vertical de 1 px aislada en fondo blanco.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS o PROTECTED_STRUCTURE (nunca TEXT_COMPATIBLE).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es un trazo gráfico; Runtime debe abstenerse de declarar
                     TEXT_COMPATIBLE por el principio ONE_PIXEL_IDENTITY = AMBIGUOUS.
    WHY_RED: GREEN GUARDRAIL.
    """
    reg = np.full((120, 200), 255, dtype=np.uint8)
    reg[:, 100] = 0  # 1 columna oscura
    rect_px = (50, 50, 250, 170)

    v_assessment = verifier2.vertical_structure_assessment(reg, rect_px)
    assert v_assessment["status"] in ("AMBIGUOUS", "PROTECTED_STRUCTURE"), (
        f"Regla de 1 px nunca debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


# ── S3-05 · CONFINED TABLE RULE WITHOUT OUTSIDE CONTINUITY ───────────────────

def test_s3_05_confined_table_rule_never_text_compatible():
    """
    LAB_TRUE_NATURE: Regla vertical de tabla (ancho 4 px) confinada a la altura del span
                     dentro de una celda, sin penetración exterior (outside_continuity == 0).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, global_img.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (nunca TEXT_COMPATIBLE).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es una regla de tabla; este test demuestra que
                     outside_continuity == 0 NO es evidencia positiva de texto.
    WHY_RED: GREEN GUARDRAIL (falsifica la vía negativa).
    """
    reg = np.full((120, 400), 255, dtype=np.uint8)
    reg[10:110, 200:204] = 0  # Regla confinada de 4 px
    rect_px = (50, 50, 450, 170)

    v_assessment = verifier2.vertical_structure_assessment(reg, rect_px)
    assert v_assessment["status"] != "TEXT_COMPATIBLE", (
        f"Regla confinada sin continuidad exterior no debe ser TEXT_COMPATIBLE: {v_assessment}"
    )
    assert v_assessment["status"] == "AMBIGUOUS"


# ── S3-06 · TEXT PLUS VERTICAL RULE CROSSING WORD ────────────────────────────

def test_s3_06_text_plus_vertical_rule_crosses_word():
    """
    LAB_TRUE_NATURE: Texto display ("TITULO") intersectado por una regla vertical gráfica.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS o PROTECTED_STRUCTURE (nunca TEXT_COMPATIBLE).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que una regla contamina el texto; Runtime debe detectar
                     la contra-evidencia geométrica y no otorgar clearance aunque OCR lea el texto.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("TITULO REGULADO", fontsize_pt=36.0,
                                         add_v_line=True, v_line_pos=(120, 10, 120, 190), v_line_width=4.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    lines = page_ocr.lines()
    assert len(lines) > 0, "OCR no encontró líneas"
    span = build_span_from_ocr(lines[0], t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] in ("PROTECTED_STRUCTURE", "AMBIGUOUS"), (
        f"Texto con regla atravesando nunca debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


# ── S3-07 · UNDERLINE HORIZONTAL STRUCTURE REJECTION PRESERVED ───────────────

def test_s3_07_underline_horizontal_structure_rejection_preserved(tmp_path):
    """
    LAB_TRUE_NATURE: Texto display con subrayado horizontal grueso (4 pt).
    RUNTIME_ALLOWED_EVIDENCE: pipeline raster_edit completo.
    EXPECTED_RUNTIME_STATUS: HONEST_REJECT con razon 'grafico_en_region'.
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que hay un subrayado; la evidencia vertical de Stage 3
                     NO puede sobrepasar la detección del gate horizontal legacy.
    WHY_RED: GREEN GUARDRAIL.
    """
    pdf_in = str(tmp_path / "s3_07_in.pdf")
    pdf_out = str(tmp_path / "s3_07_out.pdf")
    _create_stage3_synthetic_pdf(pdf_in, text="TITULO SUBRAYADO", fontsize_pt=36.0, add_h_line=True)

    rep = raster_edit(pdf_in, "TITULO", "NUEVO", pdf_out)
    assert rep["classification"] == "HONEST_REJECT"
    assert rep["reject_reason"] == "grafico_en_region"
    assert rep["gates"]["structure"]["h_line_rows"] > 0, "Gate horizontal debe detectar el subrayado"


# ── S3-08 · NEARBY OUTER BORDER PRESERVES LIVENESS ───────────────────────────

def test_s3_08_nearby_border_preserves_liveness(tmp_path):
    """
    LAB_TRUE_NATURE: Texto ordinario con un borde gráfico exterior cercano que no intersecta el span.
    RUNTIME_ALLOWED_EVIDENCE: pipeline raster_edit completo.
    EXPECTED_RUNTIME_STATUS: PASS (liveness preservada).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que el borde está fuera de la caja de edición; Stage 3 no debe
                     introducir falsos rechazos colaterales.
    WHY_RED: GREEN GUARDRAIL.
    """
    pdf_in = str(tmp_path / "s3_08_in.pdf")
    pdf_out = str(tmp_path / "s3_08_out.pdf")
    _create_stage3_synthetic_pdf(pdf_in, text="TEXTO CON BORDE LEJANO", fontsize_pt=14.0, fontname="helv",
                                 add_border_nearby=True)

    rep = raster_edit(pdf_in, "TEXTO", "NUEVO", pdf_out)
    assert rep["classification"] == "PASS"
    assert rep["dimensions"]["graphics_clearance_ok"] is True


# ── S3-09 · OCR ABSORBS GRAPHIC INTO BBOX → NOT TEXT COMPATIBLE ──────────────

def test_s3_09_ocr_absorbs_graphic_into_bbox_not_text_compatible():
    """
    LAB_TRUE_NATURE: Regla vertical de 4 pt cruzando texto donde Tesseract infla el bbox
                     (reproducción deliberada del fallo de precondición de S2-03 original).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS o PROTECTED_STRUCTURE (nunca TEXT_COMPATIBLE).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que el bbox está inflado por una regla; Runtime no debe confiar
                     en la mera pertenencia al bbox OCR como prueba de texto.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("TITULO REGULADO", fontsize_pt=24.0,
                                         add_v_line=True, v_line_pos=(150, 10, 150, 190), v_line_width=4.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR debe encontrar la línea con la regla absorbida"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] != "TEXT_COMPATIBLE", (
        f"Regla absorbida por OCR no debe ser promovida a TEXT_COMPATIBLE: {v_assessment}"
    )


# ── S3-10 · CAL-005 REAL SCAN CALIBRATION TARGET ─────────────────────────────

@pytest.mark.skipif(not os.path.exists(CAL005), reason="CAL-005 real es LOCAL (no commiteado)")
def test_s3_10_cal005_real_local_target_positive_attribution():
    """
    LAB_TRUE_NATURE: CAL-005 escaneo real, titular 'PREFACIO DE MICHAEL LYDON' (38.2 pt).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: TEXT_COMPATIBLE con text_evidence_level == 'STRONG'.
    TARGET_CLASS: TARGET (CALIBRATION_CASE).
    ORACLE_BOUNDARY: LAB sabe que CAL-005 es un libro biográfico sin tablas ni arte en el titular;
                     Runtime debe computar afirmativamente la correspondencia de fustes y envelope.
    WHY_RED: NACE ROJO porque Stage 3 no está implementado y actualmente reporta AMBIGUOUS.
    """
    doc = pymupdf.open(CAL005)
    pix = doc[0].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    rect_px = (7752, 3646, 9882, 3792)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    obs = TesseractOCRProvider(config="--psm 3")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("PREFACIO")
    assert line is not None, "OCR psm3 debe localizar PREFACIO en CAL-005"

    t = SpaceTransform(img.shape[1] * 72.0 / 300.0, img.shape[0] * 72.0 / 300.0, dpi=300.0)
    span = build_span_from_ocr(line, t, t.width_pt, 0)

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )

    assert v_assessment.get("status") == "TEXT_COMPATIBLE", (
        f"CAL-005 Target RED: Se esperaba TEXT_COMPATIBLE, obtenido: {v_assessment.get('status')}"
    )
    assert v_assessment.get("text_evidence_level") == "STRONG", (
        f"CAL-005 Target RED: Se esperaba text_evidence_level STRONG, obtenido: {v_assessment.get('text_evidence_level')}"
    )


# ── S3-11 · S2-03 CORRECTED TABLE GEOMETRY → PROTECTED_STRUCTURE ─────────────

def test_s3_11_s2_03_corrected_table_geometry_protected_structure():
    """
    LAB_TRUE_NATURE: Texto en columnas con regla vertical de 2 pt entre columnas penetrando afuera.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, global_img.
    EXPECTED_RUNTIME_STATUS: PROTECTED_STRUCTURE (prioridad absoluta de protección).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es una tabla con regla real; Runtime detecta outside continuity.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("COLUMNA A   COLUMNA B", fontsize_pt=36.0,
                                         add_v_line=True, v_line_pos=(235, 20, 235, 180), v_line_width=2.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("COLUMNA")
    assert line is not None, "OCR debe encontrar las columnas"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] == "PROTECTED_STRUCTURE", (
        f"Regla de tabla entre columnas debe ser PROTECTED_STRUCTURE: {v_assessment}"
    )
    assert v_assessment["evidence_trace"]["outside_continuity_cols"] >= 1


# ── S3-12 · SCANNER ARTIFACT VERTICAL NEVER TEXT COMPATIBLE ──────────────────

def test_s3_12_scanner_artifact_vertical_never_text_compatible():
    """
    LAB_TRUE_NATURE: Mancha / raya vertical de escáner en región sin texto.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS o PROTECTED_STRUCTURE (nunca TEXT_COMPATIBLE).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es suciedad de escaneo; Runtime no debe atribuir texto a ruido.
    WHY_RED: GREEN GUARDRAIL.
    """
    reg = np.full((120, 300), 255, dtype=np.uint8)
    reg[10:110, 50] = 0
    reg[15:105, 52] = 80
    rect_px = (30, 30, 330, 150)

    v_assessment = verifier2.vertical_structure_assessment(reg, rect_px)
    assert v_assessment["status"] != "TEXT_COMPATIBLE"


# ── S3-13 · MULTI-PSM CORRELATED ERROR ALONE DOES NOT GRANT STRONG ───────────

def test_s3_13_multimode_ocr_correlated_error_fails_closed():
    """
    LAB_TRUE_NATURE: Artefacto gráfico que Tesseract confunde correlacionadamente con caracteres.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, ocr_provenance.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (el consenso multi-PSM por sí solo no otorga STRONG).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es un artefacto gráfico; Runtime no debe tratar el consenso
                     de OCR como prueba afirmativa suficiente.
    WHY_RED: GREEN GUARDRAIL.
    """
    reg = np.full((120, 300), 255, dtype=np.uint8)
    reg[:, 150:156] = 0  # Barra vertical gráfica
    rect_px = (50, 50, 350, 170)
    fake_provenance = {
        "modes_attempted": ["--psm 6", "--psm 3", "--psm 11"],
        "per_mode": {
            "--psm 6": {"line_text": "I", "conf": 90.0},
            "--psm 3": {"line_text": "I", "conf": 92.0},
            "--psm 11": {"line_text": "I", "conf": 89.0},
        },
        "selection_reason": "consensus"
    }
    v_assessment = verifier2.vertical_structure_assessment(
        reg, rect_px, ocr_provenance=fake_provenance
    )
    assert v_assessment["status"] != "TEXT_COMPATIBLE", (
        f"Consenso OCR sobre regla gráfica no debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


# ── S3-14 · PROTECTION DOMINANCE OVER POSITIVE TEXT EVIDENCE ─────────────────

def test_s3_14_protection_dominance_over_positive_text_evidence():
    """
    LAB_TRUE_NATURE: Texto display en columnas que toca una regla gráfica exterior.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, global_img, span.
    EXPECTED_RUNTIME_STATUS: PROTECTED_STRUCTURE (la protección domina sobre la atribución textual).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que hay texto pero también una regla real; el sistema debe
                     priorizar la protección del documento ante cualquier duda.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("COLUMNA A   COLUMNA B", fontsize_pt=36.0,
                                         add_v_line=True, v_line_pos=(235, 20, 235, 180), v_line_width=2.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("COLUMNA")
    assert line is not None, "OCR debe encontrar la línea"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] == "PROTECTED_STRUCTURE", (
        f"Dominancia de protección violada: {v_assessment}"
    )


# ── S3-15 · DECISION DELTA ACCOUNTING BASELINE PRESERVATION ──────────────────

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


@pytest.mark.parametrize("case_id", list(OBSERVED_LEGACY_BASELINES.keys()))
def test_s3_15_decision_delta_accounting_baseline_preservation(dataset, case_id, tmp_path):
    """
    LAB_TRUE_NATURE: 5 casos del fingerprint legacy.
    RUNTIME_ALLOWED_EVIDENCE: pipeline raster_edit completo.
    EXPECTED_RUNTIME_STATUS: NON_TARGET_DECISIONS_IDENTICAL.
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB conoce los fingerprints congelados; Stage 3 no debe provocar deltas
                     no planificados en ningún caso no-target.
    WHY_RED: GREEN GUARDRAIL.
    """
    base = OBSERVED_LEGACY_BASELINES[case_id]
    pdf_in = dataset[case_id]["pdf"]
    pdf_out = str(tmp_path / f"s3_15_{case_id}_out.pdf")

    rep = raster_edit(pdf_in, base["old"], base["new"], pdf_out, strategy=base["strat"])
    assert rep["classification"] == base["classification"], f"Delta no planificado en {case_id}: class"
    assert rep.get("reject_reason") == base["reject_reason"], f"Delta no planificado en {case_id}: reason"
    dims = rep.get("dimensions", {})
    assert dims.get("graphics_clearance_ok") == base["graphics_clearance_ok"], f"Delta no planificado en {case_id}: gfx"
    assert dims.get("geometry_ok") == base["geometry_ok"], f"Delta no planificado en {case_id}: geo"
    assert dims.get("typography_ok") == base["typography_ok"], f"Delta no planificado en {case_id}: typo"
    if base["background_ok"] is not None:
        assert dims.get("background_ok") == base["background_ok"], f"Delta no planificado en {case_id}: bg"
    assert (os.path.exists(pdf_out) and os.path.getsize(pdf_out) > 0) == base["output_written"], (
        f"Delta no planificado en {case_id}: out_written"
    )


# ── ADVERSARIAL TESTS S3-A1 .. S3-A7 ─────────────────────────────────────────

def test_s3_a1_barcode_glyph_cluster_lookalike_fails_closed():
    """
    LAB_TRUE_NATURE: Código de barras sintético con N barras verticales equidistantes.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (falla por ausencia de ramas horizontales/curvas).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es un código de barras; falsifica el conteo ciego de clusters.
    WHY_RED: GREEN GUARDRAIL.
    """
    reg = np.full((120, 400), 255, dtype=np.uint8)
    for bx in range(50, 350, 15):
        reg[20:100, bx:bx + 4] = 0
    rect_px = (30, 30, 430, 150)

    v_assessment = verifier2.vertical_structure_assessment(reg, rect_px)
    assert v_assessment["status"] != "TEXT_COMPATIBLE", (
        f"Código de barras nunca debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


def test_s3_a2_confined_solid_bar_exact_envelope_fails_closed():
    """
    LAB_TRUE_NATURE: Barra vertical sólida de 10 px de ancho confinada exactamente al envelope ycap..ybase.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (falla por longitud L=1 < 3 y falta de ritmo multi-glifo).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que es una barra gráfica corta; falsifica el envelope como condición única.
    WHY_RED: GREEN GUARDRAIL.
    """
    reg = np.full((120, 300), 255, dtype=np.uint8)
    reg[25:95, 145:155] = 0  # Barra sólida confinada
    rect_px = (50, 50, 350, 170)

    v_assessment = verifier2.vertical_structure_assessment(reg, rect_px)
    assert v_assessment["status"] != "TEXT_COMPATIBLE"


def test_s3_a3_grid_aligned_with_gutters_detected_as_structure():
    """
    LAB_TRUE_NATURE: Texto con una regla vertical ubicada exactamente en el gutter inter-palabra.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS o PROTECTED_STRUCTURE (falla gutter cleanliness).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que una regla contamina el espacio entre palabras.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("PALABRA UNO   PALABRA DOS", fontsize_pt=36.0,
                                         add_v_line=True, v_line_pos=(280, 20, 280, 180), v_line_width=2.0)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    lines = page_ocr.lines()
    assert len(lines) > 0, "OCR debe encontrar texto"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(lines[0], t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] in ("PROTECTED_STRUCTURE", "AMBIGUOUS"), (
        f"Regla en gutter no debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


def test_s3_a4_faint_vertical_stripes_background_fails_closed():
    """
    LAB_TRUE_NATURE: Texto display sobre fondo con textura de líneas verticales tenues.
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span.
    EXPECTED_RUNTIME_STATUS: AMBIGUOUS (la densidad en gutters supera la tolerancia de fondo limpio).
    TARGET_CLASS: NON_TARGET.
    ORACLE_BOUNDARY: LAB sabe que hay un fondo con textura gráfica no uniforme.
    WHY_RED: GREEN GUARDRAIL.
    """
    img = _render_stage3_synthetic_image("TITULO RAYAS FONDO", fontsize_pt=36.0, add_stripes_bg=True)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR debe encontrar el título"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment["status"] != "TEXT_COMPATIBLE", (
        f"Texto sobre fondo de rayas verticales no debe ser TEXT_COMPATIBLE: {v_assessment}"
    )


def test_s3_a5_times_serif_display_text_positive_attribution():
    """
    LAB_TRUE_NATURE: Texto display en tipografía Serif (Times-Roman 36 pt).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: TEXT_COMPATIBLE con STRONG.
    TARGET_CLASS: TARGET.
    ORACLE_BOUNDARY: LAB sabe que es texto serif limpio; falsifica sensibilidad excesiva a serifas.
    WHY_RED: NACE ROJO porque Stage 3 no está implementado aún.
    """
    img = _render_stage3_synthetic_image("TITULO SERIF DISPLAY", fontsize_pt=36.0, fontname="tiro")
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, "OCR debe encontrar texto Times"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment.get("status") == "TEXT_COMPATIBLE", (
        f"Serif Display Target RED: Se esperaba TEXT_COMPATIBLE, obtenido: {v_assessment.get('status')}"
    )


@pytest.mark.parametrize("fontname", ["helv", "hebo", "tiro", "cour"])
def test_s3_a6_multi_font_family_rhythm_invariance(fontname):
    """
    LAB_TRUE_NATURE: Mismo texto display renderizado en 4 familias tipográficas (Sans, Bold, Serif, Mono).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: TEXT_COMPATIBLE con STRONG.
    TARGET_CLASS: TARGET.
    ORACLE_BOUNDARY: LAB sabe que son textos limpios de distintas fuentes; demuestra invarianza de ritmo.
    WHY_RED: NACE ROJO (4 items) porque Stage 3 no está implementado aún.
    """
    img = _render_stage3_synthetic_image("TITULO TIPOGRAFICO MODULADO", fontsize_pt=36.0, fontname=fontname)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), 300.0)
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, f"OCR debe encontrar texto en {fontname}"

    t = SpaceTransform(600.0, 200.0, dpi=300.0)
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment.get("status") == "TEXT_COMPATIBLE", (
        f"Multi-font Target RED ({fontname}): Se esperaba TEXT_COMPATIBLE, obtenido: {v_assessment.get('status')}"
    )


@pytest.mark.parametrize("dpi", [150, 300, 600])
def test_s3_a7_multi_dpi_scale_invariance_normalized_metrics(dpi):
    """
    LAB_TRUE_NATURE: Mismo texto display renderizado a múltiples resoluciones (150, 300, 600 DPI).
    RUNTIME_ALLOWED_EVIDENCE: local_region, rect_px, span, global_img, ocr_page.
    EXPECTED_RUNTIME_STATUS: TEXT_COMPATIBLE con STRONG.
    TARGET_CLASS: TARGET.
    ORACLE_BOUNDARY: LAB sabe que es el mismo texto a distintas escalas; demuestra que las métricas
                     deben normalizarse respecto a DPI y span height, no a píxeles fijos.
    WHY_RED: NACE ROJO (3 items) porque Stage 3 no está implementado aún.
    """
    img = _render_stage3_synthetic_image("TITULO MULTI RESOLUCION", fontsize_pt=36.0, fontname="hebo", dpi=dpi)
    obs = TesseractOCRProvider(config="--psm 6")
    page_ocr = obs.process(Image.fromarray(img, "L"), float(dpi))
    line = page_ocr.find_line_containing("TITULO")
    assert line is not None, f"OCR debe encontrar texto a {dpi} DPI"

    t = SpaceTransform(600.0, 200.0, dpi=float(dpi))
    span = build_span_from_ocr(line, t, 600.0, 0)
    rect_px = _span_region_px(span)
    local_region = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]]

    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=img,
        ocr_page=page_ocr,
    )
    assert v_assessment.get("status") == "TEXT_COMPATIBLE", (
        f"Multi-DPI Target RED ({dpi} DPI): Se esperaba TEXT_COMPATIBLE, obtenido: {v_assessment.get('status')}"
    )
