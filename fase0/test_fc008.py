"""
PROMETEO · FC-008 · REGRESIÓN: inestabilidad de percepción OCR
────────────────────────────────────────────────────────────────
Origen: CAL-005 (raster real, HONEST_REJECT confirmado). Fenómeno:
la localización del target depende materialmente del MODO de
segmentación usado a la escala operativa del pipeline — psm6 (config
congelada) pierde un target perfectamente legible que psm3/psm11
encuentran con conf 90+ SOBRE LA MISMA IMAGEN (matriz de
falsificación: evidence/CAL-005/fc008_matrix.txt).

Clasificación del fenómeno: SAFE FALSE NEGATIVE (no silent failure).

Este archivo contiene:
  1) reproducción sintética commiteable del MECANISMO (firma exacta
     del doc real: psm6 FALLA ∧ psm3 OK ∧ psm11 OK a escala pipeline);
  2) CONTRATO nacido ROJO: un target legible no puede perderse por
     depender de un único modo de observación;
  3) regresión sobre CAL-005 real (solo si el archivo LOCAL existe).

Anti-tuning (mandato): PROHIBIDO resolver con 300→150 dpi. El fix
deberá surgir de la evidencia (p.ej. consenso/localización multi-modo
con registro de evidencia) y pasar por falsificación.
"""
import os

import pytest

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from raster import raster_edit

HERE = os.path.dirname(os.path.abspath(__file__))
CAL005 = os.path.join(HERE, "reality_corpus", "docs", "CAL-005_1001.pdf")
REPRO_PARAMS = dict(seed=23, text_pt=30, n_snippets=380, n_lines=250)


def _build_repro_image(seed=23, text_pt=30, n_snippets=380, n_lines=250):
    """Reproducción mínima commiteable del mecanismo FC-008: lienzo
    enorme (2450×1600 pt → 10209 px a 300 dpi) + una línea limpia +
    marginalia dispersa tipo texto + trazos — psm6 pierde la línea,
    psm3/psm11 la encuentran. Firma calibrada contra el documento real."""
    rng = np.random.default_rng(seed)
    W_pt, H_pt, dpi_img = 2450.0, 1600.0, 150
    tmp = pymupdf.open()
    pg = tmp.new_page(width=W_pt, height=H_pt)
    pg.insert_text(pymupdf.Point(W_pt * 0.35, H_pt * 0.55),
                   "PREFACIO DE MICHAEL LYDON", fontname="hebo",
                   fontsize=text_pt)
    pix = pg.get_pixmap(dpi=dpi_img, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples).copy()
    W, H = img.size
    d = ImageDraw.Draw(img)
    chars = "aeioustnrmdyYSS|/.,;'`~"
    for _ in range(n_snippets):
        x, y = int(rng.integers(0, W - 400)), int(rng.integers(0, H - 80))
        s = "".join(rng.choice(list(chars), size=int(rng.integers(2, 14))))
        fs = int(rng.integers(24, 70))
        try:
            f = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Courier New.ttf", fs)
        except Exception:
            f = ImageFont.load_default()
        d.text((x, y), s, fill=int(rng.integers(40, 150)), font=f)
    for _ in range(n_lines):
        x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
        wl, hl = int(rng.integers(60, 500)), int(rng.integers(4, 30))
        d.line([(x, y), (x + wl, y + hl)], fill=int(rng.integers(50, 190)),
               width=int(rng.integers(2, 8)))
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    a = np.asarray(img).astype(np.float32)
    a += rng.normal(0, 9, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _img_to_pdf(img, path, W_pt=2450.0, H_pt=1600.0):
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=W_pt, height=H_pt)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def _ocr_has_target(img, config):
    data = pytesseract.image_to_data(
        img, config=config, output_type=pytesseract.Output.DICT)
    for i in range(len(data["text"])):
        t = (data["text"][i] or "").strip().upper()
        try:
            c = float(data["conf"][i])
        except (ValueError, TypeError):
            c = -1.0
        if "PREFACIO" in t and c >= 30:
            return True
    return False


@pytest.fixture(scope="module")
def repro_pdf(tmp_path_factory):
    img = _build_repro_image(**REPRO_PARAMS)
    path = str(tmp_path_factory.mktemp("fc008") / "fc008_repro.pdf")
    _img_to_pdf(img, path)
    return path


# ── 1 · Documentación ejecutable del fenómeno (PASA hoy: es el hecho) ──

def test_mecanismo_documentado_psm6_pierde_alternativa_recupera(repro_pdf):
    """FC-008: sobre la MISMA rasterización a escala de pipeline,
    psm6 no localiza el target y al menos un modo alternativo sí.
    Firma exacta del documento real (psm6 FALLA ∧ psm3 OK ∧ psm11 OK,
    conf 90+): matriz evidence/CAL-005/fc008_matrix.txt. El fixture
    sintético reproduce la CLASE del mecanismo a través del camino real
    de render (MuPDF): qué modo alternativo recupera es sensible a la
    densidad — más evidencia de la inestabilidad (ver FC-008)."""
    doc = pymupdf.open(repro_pdf)
    pix = doc[0].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    doc.close()
    assert not _ocr_has_target(img, "--psm 6"), (
        "el fixture dejó de reproducir el mecanismo (psm6 ahora encuentra)"
    )
    assert (_ocr_has_target(img, "--psm 3")
            or _ocr_has_target(img, "--psm 11")), (
        "ningún modo alternativo recupera: la clase del mecanismo no "
        "está reproducida")


# ── 2 · CONTRATO (nació ROJO) ──────────────────────────────────────────

def test_target_legible_no_puede_perderse_por_modo_unico(repro_pdf, tmp_path):
    """CONTRATO FC-008: un target legible (demostrable por modos
    alternativos sobre la misma evidencia) no puede perderse con
    'texto_no_encontrado_por_ocr' por depender de un único modo de
    observación. El pipeline puede terminar en PASS o en HONEST_REJECT
    por OTRAS causas honestas — pero no por esta."""
    out = str(tmp_path / "out_fc008.pdf")
    rep = raster_edit(repro_pdf, "PREFACIO", "PROLOGO", out)
    assert rep.get("reject_reason") != "texto_no_encontrado_por_ocr", (
        "FC-008 activo: el pipeline perdió un target legible por "
        "depender de un solo modo de observación OCR")


# ── 3 · T4 AMBIGÜEDAD: candidatos incompatibles → HONEST_REJECT ────────

def test_t4_ambiguedad_candidatos_incompatibles_rechazo_explicito():
    """T4 (mandate §5): si dos observadores localizan candidatos
    materialmente INCOMPATIBLES y no hay evidencia suficiente para
    resolver, la política debe decretar ambigüedad → HONEST_REJECT
    'ocr_localization_ambiguous'. Nunca elección silenciosa."""
    from raster import _resolve_localization          # política pura
    c1 = {"config": "--psm 6", "text": "PREFACIO ... LYDON",
          "bbox_px": (100, 1000, 3000, 1120), "conf": 91.0}
    c2 = {"config": "--psm 3", "text": "PREFACIO ... LYDON",
          "bbox_px": (7000, 5000, 9800, 5120), "conf": 94.0}
    res = _resolve_localization([c1, c2])
    assert res["status"] == "ambiguous"
    assert res["reason"] == "ocr_localization_ambiguous"
    assert res["chosen"] is None


def test_t4_candidatos_compatibles_eligen_por_orden_congelado():
    """Candidatos compatibles (misma zona) → se elige el primero en el
    orden de modos congelado, NO por confidence (conf es auxiliar)."""
    from raster import _resolve_localization
    c_psm3 = {"config": "--psm 3", "text": "PREFACIO ...",
              "bbox_px": (1000, 1800, 4200, 1920), "conf": 96.0}
    c_psm11 = {"config": "--psm 11", "text": "PREFACIO ...",
               "bbox_px": (1010, 1810, 4190, 1915), "conf": 90.0}
    res = _resolve_localization([c_psm3, c_psm11])
    assert res["status"] == "localized"
    assert res["chosen"]["config"] == "--psm 3"
    assert res["reason"] == "orden_congelado"


def test_t4_sin_candidatos_es_no_encontrado():
    from raster import _resolve_localization
    res = _resolve_localization([])
    assert res["status"] == "not_found"


# ── 4 · T5 camino normal: psm6 encuentra → nada cambia ────────────────

def test_t5_psm6_encuentra_comportamiento_inalterado(tmp_path):
    """T5: cuando el modo primario localiza, el pipeline se comporta
    como antes: localizer psm6, verifier psm3 (WEAK), PASS intacto y
    provenance completa en el reporte."""
    import fixtures_raster
    data = fixtures_raster.build_all()
    out = str(tmp_path / "out_t5.pdf")
    rep = raster_edit(data["A_scan_limpio"]["pdf"], "Perez", "Garcia", out)
    assert rep["ok"] and rep["classification"] == "PASS"
    prov = rep["ocr_provenance"]
    assert prov["localizer_config"] == "--psm 6"
    assert prov["modes_attempted"] == ["--psm 6"]      # lazy: no innecesario
    assert prov["independence"]["verifier_config"] == "--psm 3"
    assert prov["independence"]["independence_level"] == "WEAK"
    assert prov["per_mode"]["--psm 6"]["found"] is True


# ── 5 · T3 CAL-005 regression LOCAL ────────────────────────────────────

@pytest.mark.skipif(not os.path.exists(CAL005),
                    reason="CAL-005 real es LOCAL (no commiteado)")
def test_t3_cal005_real_como_regresion(tmp_path):
    """T3: el target real de CAL-005 deja de morir EXCLUSIVAMENTE por
    depender del modo único. El pipeline puede terminar legítimamente
    en cualquier veredicto posterior (gates/render/verifier) — pero no
    en texto_no_encontrado_por_ocr."""
    out = str(tmp_path / "out_cal005_reg.pdf")
    rep = raster_edit(CAL005, "PREFACIO", "PROLOGO", out)
    assert rep.get("reject_reason") != "texto_no_encontrado_por_ocr", (
        "FC-008 sigue activo sobre CAL-005 real")
    prov = rep.get("ocr_provenance", {})
    assert prov.get("modes_attempted"), "provenance ausente"
