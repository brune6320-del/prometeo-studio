"""
PROMETEO · ADVERSARIAL_SUITE
═════════════════════════════
Ataques diseñados para ROMPER la implementación de Fase 0A.
Los inputs NO se diseñan para encajar con el código: se diseñan para
encontrar dónde falla (directriz §6). Las 22 pruebas originales viven
intactas en test_geometry.py + test_fase0.py como REGRESSION_SUITE.

Predicciones P1–P8 en docs/02-auditoria-adversarial.md.
"""
import os

import numpy as np
import pymupdf
import pytest

import make_fixtures
from engine import all_spans, extract, replace_flow, sha256_file
from operations import ReplaceText
from render import FontBook

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"


@pytest.fixture(scope="session", autouse=True)
def assets():
    return make_fixtures.ensure_assets()


# ── helpers ─────────────────────────────────────────────────────────
def render_gray(path, page=0, dpi=150):
    doc = pymupdf.open(path)
    pix = doc[page].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    doc.close()
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return a, pix.width, pix.height, dpi / 72.0


def ink_bbox(gray, rect_pt, scale, dark=128):
    """bbox de tinta (px) dentro de una región en pt."""
    x0 = max(int(rect_pt[0] * scale) - 2, 0)
    y0 = max(int(rect_pt[1] * scale) - 2, 0)
    x1 = min(int(rect_pt[2] * scale) + 2, gray.shape[1])
    y1 = min(int(rect_pt[3] * scale) + 2, gray.shape[0])
    region = gray[y0:y1, x0:x1] < dark
    if not region.any():
        return None
    ys, xs = np.where(region)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max(), y0 + ys.max())


def build_raw_pdf(path, content_stream, page_w=612, page_h=792):
    """Construye un PDF crudo con contenido EXACTO (independiente del
    generador del sistema). Para documentos con kerning real (TJ)."""
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    page_dict = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
                 f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    objs.append(page_dict.encode())
    stream = b"BT /F1 12 Tf 72 720 Td " + content_stream + b" ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode()
            + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode()
            + b"\n%%EOF\n")
    with open(path, "wb") as f:
        f.write(bytes(out))
    return path


# ── P1 · robo de fuente: embebida + base-14 en la misma página ──────
def test_P1_no_robar_fuente_embebida_cuando_hay_alias(tmp_path):
    path = str(tmp_path / "mix.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_font(fontname="ARL0", fontfile=ARIAL)          # embebida
    page.insert_text(pymupdf.Point(72, 100), "Titulo en Arial", fontname="ARL0", fontsize=12)
    page.insert_text(pymupdf.Point(72, 130), "Texto comun en Helvetica", fontname="helv", fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()

    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "comun", "corriente", out)
    assert rep["ok"], rep
    v = rep["verify"]["checks"][0]
    # DESEO: el span Helvetica debe re-renderizarse con helv, no con la Arial embebida
    assert v["font_used"] == "helv", (
        f"P1 CONFIRMADO: se reutilizó {v['font_used']} (Arial) para texto Helvetica")


# ── P2 · kerning real (TJ) perdido al re-renderizar el span ─────────
def test_P2_prefijo_no_editado_no_se_desplaza_con_kerning(tmp_path):
    # PDF crudo con kerning real (valores de tipografía display):
    # el prefijo "Valor " acumula ~+300/1000 em ≈ 3.6 pt a 12 pt
    path = build_raw_pdf(
        str(tmp_path / "kerned.pdf"),
        b"[(V)-120(a)180(l)-90(o)150(r)180( t)60(o)120(t)-40(a)150(l)] TJ")
    model = extract(path)
    spans = list(all_spans(model))
    assert spans and spans[0]["text"] == "Valor total"

    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "total", "gran total", out)
    assert rep["ok"], rep

    # medir tinta del prefijo "Valor " antes y después (300 dpi)
    span = spans[0]
    scale = 300 / 72.0
    g_before, *_ = render_gray(path, dpi=300)
    g_after, *_ = render_gray(out, dpi=300)
    prefix_w = pymupdf.Font("helv").text_length("Valor ", fontsize=12) * scale
    band = (span["bbox"][0], span["bbox"][1], span["bbox"][0 + 2], span["bbox"][3])
    x1 = span["bbox"][0] * scale + prefix_w
    y0, y1 = span["bbox"][1] * scale - 2, span["bbox"][3] * scale + 2
    def rightmost_ink(g):
        region = g[int(y0):int(y1), int(span["bbox"][0] * scale) - 2:int(x1)] < 128
        if not region.any():
            return None
        return int(np.where(region.any(axis=0))[0].max())
    rb, ra = rightmost_ink(g_before), rightmost_ink(g_after)
    shift_px = abs(ra - rb)
    shift_pt = shift_px / scale
    assert shift_pt <= 0.5, (
        f"P2 CONFIRMADO: el prefijo no editado se desplazó {shift_pt:.2f} pt "
        f"(kerning original perdido en el re-render)")


# ── P3 · acentos y unicode latino ────────────────────────────────────
def test_P3_acentos_latinos(tmp_path):
    path = str(tmp_path / "acr.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_text(pymupdf.Point(72, 120), "Contratado: José Muñoz Pérez",
                     fontname="helv", fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "Pérez", "García", out)
    assert rep["ok"], rep
    doc = pymupdf.open(out)
    text = doc[0].get_text()
    doc.close()
    assert "García" in text and "Pérez" not in text


# ── P4 · CropBox desplazado respecto a MediaBox ──────────────────────
def test_P4_cropbox_desplazado(tmp_path):
    path = str(tmp_path / "crop.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(72, 120), "Contratado: Juan Perez",
                     fontname="helv", fontsize=11)
    # recortar: el área visible empieza en (20,20) del MediaBox
    page.set_cropbox(pymupdf.Rect(20, 20, 500, 772))
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "Perez", "Garcia", out)
    assert rep["ok"], rep
    v = rep["verify"]["checks"][0]
    assert v["dx_pt"] <= 1.5 and v["dy_pt"] <= 1.5


# ── P5 · texto sobre gráficos (borde de tabla) ───────────────────────
@pytest.mark.xfail(strict=False, reason=(
    "LIMITACIÓN DOCUMENTADA: clearance solo considera spans, no capas "
    "gráficas — el texto nuevo puede pisar líneas de tabla. "
    "Ver failure_corpus/FC-002."))
def test_P5_no_pintar_sobre_linea_de_tabla(tmp_path):
    path = str(tmp_path / "tabla.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.draw_line(pymupdf.Point(300, 105), pymupdf.Point(300, 135))  # borde
    page.insert_text(pymupdf.Point(72, 120), "Total: 1200",
                     fontname="helv", fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "1200", "1200 euros netos anuales", out)
    assert rep["ok"], rep
    # la tinta nueva no debe invadir la columna de la línea (x≈300)
    g, w, h, scale = render_gray(out, dpi=150)
    line_col = int(300 * scale)
    band = g[int(105 * scale):int(135 * scale), line_col - 3:line_col + 3]
    # si el texto cruzó la línea, la columna tendrá mucha más tinta que un trazo de 1pt
    dark_ratio = (band < 128).mean()
    assert dark_ratio < 0.25, "P5 CONFIRMADO: el texto nuevo pisa el borde de tabla"


# ── P6 · determinismo con fuente embebida ────────────────────────────
@pytest.mark.skipif(not os.path.exists(ARIAL), reason="Arial.ttf no disponible")
def test_P6_determinismo_con_fuente_embebida(tmp_path):
    path = str(tmp_path / "emb.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_font(fontname="ARL0", fontfile=ARIAL)
    page.insert_text(pymupdf.Point(72, 120), "Contratado: Juan Perez",
                     fontname="ARL0", fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    r1 = replace_flow(path, "Perez", "Garcia", str(tmp_path / "o1.pdf"))
    r2 = replace_flow(path, "Perez", "Garcia", str(tmp_path / "o2.pdf"))
    assert r1["ok"] and r2["ok"]
    assert r1["output_sha256"] == r2["output_sha256"]


# ── P7 · preservación de color ───────────────────────────────────────
def test_P7_color_preservado(tmp_path):
    path = str(tmp_path / "col.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_text(pymupdf.Point(72, 120), "Estado: PENDIENTE",
                     fontname="helv", fontsize=11, color=(0.1, 0.2, 0.8))
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "PENDIENTE", "APROBADO", out)
    assert rep["ok"], rep
    doc = pymupdf.open(out)
    span = None
    for b in doc[0].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if "APROBADO" in s["text"]:
                    span = s
    doc.close()
    assert span is not None
    c = span["color"]
    rgb = ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)
    assert abs(rgb[0] - 0.1) < 0.02 and abs(rgb[1] - 0.2) < 0.02 and abs(rgb[2] - 0.8) < 0.02


# ── P8 · ancla posicional por TINTA (verificación externa) ───────────
def test_P8_posicion_de_tinta_verificacion_externa(tmp_path, assets):
    """Verificación POSICIONAL independiente del motor de texto: la
    tinta del texto nuevo debe caer sobre la banda del span editado,
    con origen horizontal donde el modelo dice."""
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_a"], "Perez", "Garcia", out)
    assert rep["ok"]
    model = extract(assets["case_a"])
    span = next(s for s in all_spans(model) if "Contratado" in s["text"])
    g, w, h, scale = render_gray(out, dpi=150)
    # banda vertical del span + margen
    band_pt = (span["bbox"][0] - 2, span["bbox"][1] - 3, span["bbox"][2] + 60, span["bbox"][3] + 3)
    ib = ink_bbox(g, band_pt, scale)
    assert ib is not None, "no se encontró tinta en la banda editada"
    ink_x0_pt = ib[0] / scale
    assert abs(ink_x0_pt - span["bbox"][0]) <= 1.5, (
        f"la tinta empieza en {ink_x0_pt:.2f}pt pero el span está en {span['bbox'][0]:.2f}pt")
