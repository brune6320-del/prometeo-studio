"""FASE 0 · Tests del vertical slice (DAS §19–§20 y §55)."""
import os

import pymupdf
import pytest

import make_fixtures
from engine import (
    all_spans, build_replace_op, export_version, extract, replace_flow,
    sha256_file, span_by_id,
)
from operations import ReplaceText
from render import FontBook


@pytest.fixture(scope="session", autouse=True)
def assets():
    return make_fixtures.ensure_assets()


# ── CASO A · born-digital: el corazón ───────────────────────────────
def test_caso_a_reemplazo_cabe_y_verifica(tmp_path, assets):
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_a"], "Perez", "Garcia", out)
    assert rep["ok"], rep
    v = rep["verify"]["checks"][0]
    assert v["policy"] == "fit"
    assert v["dx_pt"] <= 1.5 and v["dy_pt"] <= 1.5
    assert v["font_used"] == "helv" and v["font_fallback"] is False
    # el texto viejo desapareció y el nuevo está (la banda de línea lo
    # verifica con precisión geométrica; el volcado plano puede meter
    # un salto entre prefijo original y cola insertada — artifacto de
    # copy/paste conocido, ver PROJECT_STATE hallazgos)
    doc = pymupdf.open(out)
    assert "Juan Perez" not in doc[0].get_text()
    assert "Garcia" in doc[0].get_text()
    doc.close()


def test_caso_a_original_intacto_y_reproducible(tmp_path, assets):
    before = sha256_file(assets["case_a"])
    out1, out2 = str(tmp_path / "v1.pdf"), str(tmp_path / "v2.pdf")
    r1 = replace_flow(assets["case_a"], "Perez", "Garcia", out1)
    r2 = replace_flow(assets["case_a"], "Perez", "Garcia", out2)
    assert r1["ok"] and r2["ok"]
    assert r1["output_sha256"] == r2["output_sha256"]   # TEST 4 DAS §55
    assert sha256_file(assets["case_a"]) == before      # el original no cambia
    assert r1["original_sha256"] == before


def test_caso_e_texto_pequeno(tmp_path, assets):
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_a"], "AB-2025-0042", "AB-2026-0077", out)
    assert rep["ok"]
    v = rep["verify"]["checks"][0]
    assert v["dx_pt"] <= 1.5 and v["dy_pt"] <= 1.5


def test_caso_g_corto_a_largo_que_cabe(tmp_path, assets):
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_a"], "10 de agosto de 2025",
                       "18 de septiembre de 2026", out)
    assert rep["ok"]
    v = rep["verify"]["checks"][0]
    assert v["width_pt"] <= v["clearance_pt"] + 0.5


# ── CASO D · página rotada ──────────────────────────────────────────
def test_caso_d_pagina_rotada(tmp_path, assets):
    model = extract(assets["case_d_rotated"])
    assert model["pages"][0]["rotation"] == 90
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_d_rotated"], "Perez", "Garcia", out)
    assert rep["ok"], rep
    v = rep["verify"]["checks"][0]
    assert v["dx_pt"] <= 1.5 and v["dy_pt"] <= 1.5


# ── CASO H · desbordes → políticas explícitas, jamás silenciosas ───
def _doc_con_span_cerca_del_margen(tmp_path, x=430.0):
    path = str(tmp_path / "f.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_text(pymupdf.Point(x, 100), "Monto total", fontname="helv",
                     fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    return path


def _texto_de_ancho(target_min, target_max, size=11.0):
    """Genera un texto cuyo ancho tipográfico cae en [target_min, target_max)."""
    base = "monto acordado "
    font = pymupdf.Font("helv")
    s = base
    while font.text_length(s, fontsize=size) < target_min:
        s += "x"
    assert font.text_length(s, fontsize=size) <= target_max
    return s


def test_caso_h_shrink_cuando_puede(tmp_path):
    path = _doc_con_span_cerca_del_margen(tmp_path)
    model = extract(path)
    span = next(s for s in all_spans(model) if s["text"] == "Monto total")
    # hueco real ≈ 595-36-430 ≈ 129 pt; pedimos algo que exija encoger ≥ 0.55
    largo = _texto_de_ancho(span["clearance_pt"] + 5,
                            span["clearance_pt"] / 0.55 - 5)
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "Monto total", "Monto total " + largo, out)
    assert rep["ok"]
    v = rep["verify"]["checks"][0]
    assert v["policy"] == "shrink"
    assert v["final_size_pt"] < 11.0
    assert v["width_pt"] <= v["clearance_pt"] + 0.5


def test_caso_h_desborde_pide_decision_o_rechaza(tmp_path):
    """Cuando ni encogiendo cabe: por defecto el sistema pide decisión al
    usuario (ASK_USER); con orden explícito sin ask_user, REJECT. Nunca
    deforma ni escribe nada en silencio."""
    path = _doc_con_span_cerca_del_margen(tmp_path)
    model = extract(path)
    span = next(s for s in all_spans(model) if s["text"] == "Monto total")
    larguisimo = _texto_de_ancho(span["clearance_pt"] / 0.5, 1e9) + "x" * 80
    out = str(tmp_path / "out.pdf")

    rep = replace_flow(path, "Monto total", "Monto total " + larguisimo, out)
    assert not rep["ok"]
    assert rep["results"][0]["policy"] == "ask_user"
    assert not os.path.exists(out)

    op_duro = ReplaceText(
        target_span_id=span["id"], old_text="Monto total",
        new_text="Monto total " + larguisimo,
        policy_preference=("fit", "shrink", "reject"),
    )
    rep2 = export_version(path, [op_duro], str(tmp_path / "out2.pdf"))
    assert not rep2["ok"]
    assert rep2["results"][0]["policy"] == "reject"


def test_politica_ask_user_como_rechazo_consciente(tmp_path):
    path = _doc_con_span_cerca_del_margen(tmp_path)
    model = extract(path)
    span = next(s for s in all_spans(model) if s["text"] == "Monto total")
    largo = _texto_de_ancho(span["clearance_pt"] + 5, 1e9)
    op = ReplaceText(target_span_id=span["id"], old_text="Monto total",
                     new_text="Monto total " + largo,
                     policy_preference=("fit", "ask_user"))
    out = str(tmp_path / "out.pdf")
    rep = export_version(path, [op], out)
    assert not rep["ok"]
    assert rep["results"][0]["policy"] == "ask_user"


# ── OPERACIONES COMO DATOS (DAS §36, §55) ──────────────────────────
def test_dos_operaciones_y_deshacer(tmp_path, assets):
    out12 = str(tmp_path / "v12.pdf")
    out1 = str(tmp_path / "v1.pdf")
    model = extract(assets["case_a"])
    op1 = build_replace_op(model, "Perez", "Garcia")
    op2 = build_replace_op(model, "10 de agosto de 2025", "18 de agosto de 2025")
    r12 = export_version(assets["case_a"], [op1, op2], out12)
    r1 = export_version(assets["case_a"], [op1], out1)
    assert r12["ok"] and r1["ok"]
    # la versión con 2 ops contiene ambos cambios
    doc = pymupdf.open(out12)
    text = doc[0].get_text()
    doc.close()
    assert "Garcia" in text and "18 de agosto" in text
    # "deshacer" = re-exportar desde el original con solo op1 (TEST 3/4)
    doc = pymupdf.open(out1)
    text1 = doc[0].get_text()
    doc.close()
    assert "Garcia" in text1 and "18 de agosto" not in text1


def test_operacion_invalida_no_modifica_nada(tmp_path):
    path = _doc_con_span_cerca_del_margen(tmp_path)
    op = ReplaceText(target_span_id="p0s999", old_text="x", new_text="y")
    out = str(tmp_path / "out.pdf")
    rep = export_version(path, [op], out)
    assert not rep["ok"]
    assert rep["results"][0]["reason"] == "target_not_found"
    assert not os.path.exists(out)


def test_idempotencia_guardada_target_text_mismatch(tmp_path, assets):
    """Aplicar la MISMA op sobre la salida ya editada debe rehusarse:
    el texto objetivo ya no coincide (TEST 2 DAS §55)."""
    out = str(tmp_path / "v1.pdf")
    model = extract(assets["case_a"])
    op = build_replace_op(model, "Perez", "Garcia")
    assert export_version(assets["case_a"], [op], out)["ok"]
    # re-aplicar sobre la SALIDA: el span ya dice "Garcia"
    rep2 = export_version(out, [op], str(tmp_path / "v2.pdf"))
    assert not rep2["ok"]
    assert rep2["results"][0]["reason"] == "target_text_mismatch"


def test_dos_ops_sobre_el_mismo_span_se_rechazan(tmp_path, assets):
    model = extract(assets["case_a"])
    op1 = build_replace_op(model, "Perez", "Garcia")
    op2 = build_replace_op(model, "Garcia", "Lopez")
    op2 = ReplaceText(target_span_id=op1.target_span_id,
                      old_text="Garcia", new_text="Lopez")
    out = str(tmp_path / "out.pdf")
    rep = export_version(assets["case_a"], [op1, op2], out)
    assert not rep["ok"]
    assert rep["results"][1]["reason"] == "target_already_modified"


def test_trazabilidad_completa_del_reporte(tmp_path, assets):
    out = str(tmp_path / "out.pdf")
    rep = replace_flow(assets["case_a"], "Perez", "Garcia", out)
    for key in ("timestamp", "original_sha256", "operations",
                "results", "output_sha256", "verify"):
        assert key in rep
    assert rep["operations"][0]["type"] == "replace_text"
    assert rep["operations"][0]["from"] == "Perez"


# ── CASO F · fuente embebida no base-14, reutilizada del propio PDF ─
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"

@pytest.mark.skipif(not os.path.exists(ARIAL), reason="Arial.ttf no disponible")
def test_caso_f_fuente_embebida_reutilizada(tmp_path):
    path = str(tmp_path / "f_embedded.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595.276, height=841.890)
    page.insert_font(fontname="ARL0", fontfile=ARIAL)
    page.insert_text(pymupdf.Point(72, 120), "Contratado: Juan Perez",
                     fontname="ARL0", fontsize=11)
    doc.save(path, garbage=3, deflate=True)
    doc.close()

    model = extract(path)
    span = next(s for s in all_spans(model) if "Perez" in s["text"])
    assert span["font"] != "Helvetica"        # es la embebida (ARL0/Arial)

    out = str(tmp_path / "out.pdf")
    rep = replace_flow(path, "Perez", "Garcia", out)
    assert rep["ok"], rep
    v = rep["verify"]["checks"][0]
    assert v["font_used"] and v["font_used"].startswith("PROMF")  # reutilizada
    assert v["font_fallback"] is False
    assert v["dx_pt"] <= 1.5 and v["dy_pt"] <= 1.5


# ── CASO B · scan (ruta experimental) ──────────────────────────────
def test_caso_b_scan_parche_blanco_experimental(tmp_path, assets):
    """Clase B sin proveedor de OCR: el ground truth vectorial de case_a
    hace de 'OCR perfecto'. El parche blanco + re-tipografiado debe caer
    en la geometría correcta del documento rasterizado."""
    out = str(tmp_path / "out.pdf")
    model_gt = extract(assets["case_a"])          # simula la salida del OCR
    op = build_replace_op(model_gt, "Perez", "Garcia")
    rep = export_version(assets["case_b_scan"], [op], out,
                         scan_mode=True, model_override=model_gt)
    assert rep["ok"], rep
    doc = pymupdf.open(out)
    text = doc[0].get_text()
    doc.close()
    assert "Garcia" in text and "Juan Perez" not in text
