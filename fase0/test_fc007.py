"""
PROMETEO · FC-007 · REGRESIÓN: sustitución silenciosa de fuente subset
──────────────────────────────────────────────────────────────────────
Origen: Calibration Reality Set · CAL-001-T1 (documento real, SILENT_FAILURE
CRITICAL confirmado por revisión humana). Causa raíz demostrada en
reality_corpus/evidence/CAL-001/probe_rootcause.txt:

  (a) buffer subset con programa ilegible → pymupdf.Font(fontbuffer=)
      da name='(null)' y has_glyph=False para TODO → TextWriter
      sustituye silenciosamente por Noto Serif;
  (b) subset válida pero SIN los glifos del texto nuevo → misma
      sustitución silenciosa.

Este test NACIÓ ROJO contra PROMETEO_PRE_GATE_0B (0b4f52c): el motor
informaba fontFallback=false y ok=true con la fuente sustituida.
Contrato nuevo exigido (§7 del mandato):
  REQUESTED → RESOLVED → WRITING → OUTPUT FONT → POST-EXPORT VERIFIED
  UNKNOWN nunca puede terminar en PASS.
"""
import os

import pytest

import pymupdf

import engine
from render import FontBook

HERE = os.path.dirname(os.path.abspath(__file__))
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia.ttf"


def _fixture_subset_pdf(path: str) -> str:
    """PDF con fuente COMPLETA embebida y LUEGO subseteada (subset_fonts)
    por el propio pymupdf: la subset carece del glifo 'f' (el texto
    original 'Alonso Alegría' no lo usa). Reproduce el mecanismo (b)
    del probe de FC-007 de forma determinista y commiteable."""
    if os.path.exists(path):
        return path
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=120)
    page.insert_font(fontname="FGe", fontfile=GEORGIA)
    page.insert_text(pymupdf.Point(30, 60), "Firma: Alonso Alegría",
                     fontname="FGe", fontsize=14)
    doc.subset_fonts()
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    return path


@pytest.fixture(scope="module")
def subset_pdf(tmp_path_factory):
    return _fixture_subset_pdf(
        str(tmp_path_factory.mktemp("fc007") / "fixture_subset_font.pdf"))


# ── 1 · END-TO-END: la sustitución silenciosa no puede ser PASS ──────

def test_subset_sin_glifo_no_puede_ser_PASS_silencioso(subset_pdf, tmp_path):
    """FC-007 mecanismo (b): 'Alonso'→'Alfonso' necesita 'f', la subset
    no lo tiene. El motor debe rechazar HONESTAMENTE (nada escrito) —
    jamás producir output con fuente sustituida y ok=true."""
    out = str(tmp_path / "out_fc007.pdf")
    rep = engine.replace_flow(subset_pdf, "Alonso", "Alfonso", out)
    if rep.get("ok"):
        # si algún día la política permite continuar, la identidad de
        # fuente del output DEBE estar verificada, no asumida
        check = rep["verify"]["checks"][0]
        assert check.get("font_identity_ok") is True, (
            f"PASS con identidad de fuente no verificada: {check}")
        assert check.get("font_verification") == "verified"
    else:
        reason = rep["results"][0].get("reason") or ""
        assert rep["results"][0]["ok"] is False
        assert any(k in reason for k in
                   ("glifo", "font_programa", "ilegible", "no_preservable")), (
            f"rechazo sin causa tipográfica clara: {reason}")
        assert not os.path.exists(out), (
            "un rechazo por fuente no debe escribir output")


def test_report_fontFallback_false_exige_identidad_post_export(subset_pdf, tmp_path):
    """§10 del mandato: fontFallback=false sin demostración post-export
    NO puede ser PASS. En el fixture la fuente es inservible para el
    texto nuevo: o se rechaza, o el reporte lleva font_identity_ok
    verdadero con evidencia. Jamás el estado antiguo
    (fontFallback=false + sustitución silenciosa + ok=true)."""
    out = str(tmp_path / "out_fc007b.pdf")
    rep = engine.replace_flow(subset_pdf, "Alonso", "Alfonso", out)
    r = rep["results"][0]
    if rep.get("ok"):
        assert r.get("font_fallback") is False
        assert rep["verify"]["checks"][0].get("font_identity_ok") is True
    else:
        # rechazó: el motivo tiene que ser la fuente, y declararlo
        assert not r.get("ok", True)
        assert (r.get("font_usable") is False
                or "glifo" in (r.get("font_reason") or "")
                or "ilegible" in (r.get("font_reason") or "")), (
            f"rechazo sin diagnóstico de fuente: {r}")


# ── 2 · UNITARIOS del contrato FontBook.check_font_for_edit ──────────

def test_check_font_detecta_glifos_ausentes(subset_pdf, tmp_path):
    """Mecanismo (b): la subset de Georgia no tiene 'f' → check debe
    reportar usable=False con los glifos que faltan."""
    doc = pymupdf.open(subset_pdf)
    fb = FontBook(doc, doc[0])
    span = next(s for p in engine.extract(subset_pdf)["pages"]
                for s in p["spans"] if "Alonso" in s["text"])
    chk = fb.check_font_for_edit(span, "Alfonso")
    doc.close()
    assert chk["usable"] is False
    assert "f" in chk["missing_glyphs"]
    assert chk["requested"] == span["font"]


def test_check_font_detecta_programa_ilegible(tmp_path):
    """Mecanismo (a) de CAL-001: buffer ilegible → Font con name nulo
    → usable=False ANTES de intentar escribir (hoy FontBook cree que
    la tiene buena y MuPDF sustituye por Noto en silencio)."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=100)
    page.insert_text(pymupdf.Point(20, 50), "Base", fontname="helv")
    fb = FontBook(doc, page)
    # inyectar un 'buffer extraído' corrupto como haría un pypdf roto
    fb._embedded["FuenteRota"] = b"\x00\x01no-es-una-fuente" * 8
    span = {"font": "FuenteRota", "text": "Algo", "size": 10}
    chk = fb.check_font_for_edit(span, "Algo")
    doc.close()
    assert chk["usable"] is False
    assert chk["reason"] == "font_programa_ilegible"


def test_fuente_completa_embebida_SIGUE_FUNCIONANDO(tmp_path):
    """Guardián anti-regresión del fix: una fuente embebida COMPLETA y
    con todos los glifos (caso F de Fase 0A) debe seguir siendo usable
    y verificar identidad — el fix no puede romper el camino bueno."""
    path = str(tmp_path / "full_embedded.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=120)
    page.insert_font(fontname="FGe", fontfile=GEORGIA)
    page.insert_text(pymupdf.Point(30, 60), "Firma: Alonso Alegría",
                     fontname="FGe", fontsize=14)
    doc.save(path, garbage=3, deflate=True)   # SIN subset_fonts
    doc.close()
    out = str(tmp_path / "out_full.pdf")
    rep = engine.replace_flow(path, "Alonso", "Alfonso", out)
    assert rep["ok"], rep
    check = rep["verify"]["checks"][0]
    assert check.get("font_identity_ok") is True
    assert check.get("font_verification") == "verified"
