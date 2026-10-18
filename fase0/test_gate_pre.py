"""
PROMETEO · PRE-GATE · REGRESIONES ADVERSARIALES DE LA AUDITORÍA
────────────────────────────────────────────────────────────────
Cada test nace de un hallazgo real de la auditoría de repositorio
(commit 0a09226). Escritos ANTES del fix: se demuestran rojos y
luego el fix los pone verdes. Ningún ok=true puede volver a
esconder una geometría inaceptable, un gráfico tapado, un fondo
malo o una autoverificación.

SILENT FAILURE = 0.
"""
import os

import pytest

import fixtures_raster
from ocr_provider import (JitterOCRProvider, TesseractOCRProvider,
                          independence_level)
from raster import raster_edit

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "raster")


@pytest.fixture(scope="session", autouse=True)
def dataset():
    return fixtures_raster.build_all()


def _run(data, case, old, new, **kw):
    paths = data[case]
    out = os.path.join(OUT, f"pregate_{case}.pdf")
    if os.path.exists(out):
        os.remove(out)
    rep = raster_edit(paths["pdf"], old, new, out,
                      gt_pdf=paths["gt_pdf"], **kw)
    return rep, out


# ── Hallazgo 1: el gate ok no media geometría ────────────────────────

def test_M_rotacion_NO_puede_ser_ok_con_esas_geometrias(dataset):
    """FC-004 · M_rotacion_4 salía ok=true con size_err 10.79 pt
    (benchmark 0B). Sin ground truth que lo salve: el skew de página
    es evidencia del propio documento y debe producir rechazo."""
    rep, _ = _run(dataset, "M_rotacion_4", "Perez", "Garcia")
    assert rep["gt_error"]["size_err_pt"] > 5.0     # la geometría ES mala
    assert not rep["ok"]
    assert rep["classification"] == "HONEST_REJECT"
    assert rep["dimensions"]["geometry_ok"] is False
    assert rep["reject_reason"] == "page_skew"


def test_C_rotacion_25_tambien_se_niega(dataset):
    """C (2.5°) pasaba con size_err 3.84 pt. Mismo criterio que M."""
    rep, _ = _run(dataset, "C_caso_DAS", "Perez", "Garcia")
    assert not rep["ok"]
    assert rep["classification"] == "HONEST_REJECT"
    assert rep["dimensions"]["geometry_ok"] is False


# ── Hallazgo 5: el fixture G no ejercitaba FC-002 ────────────────────

def test_G2_linea_cruza_region_se_niega_antes_de_escribir(dataset):
    """FC-002 (raster) · G2: una línea de tabla/subrayado cruza la
    región que sería reparada. Reparación rectangular la BORRARÍA.
    El pipeline debe detectar la estructura y rechazar ANTES de
    escribir un solo byte."""
    rep, out = _run(dataset, "G2_linea_cruza", "Perez", "Garcia")
    assert rep["classification"] == "HONEST_REJECT"
    assert rep["dimensions"]["graphics_clearance_ok"] is False
    assert rep["reject_reason"] == "grafico_en_region"
    assert not rep["ok"]
    assert not os.path.exists(out), (
        "un rechazo por clearance de gráficos no debe producir archivo")


def test_G2_borde_cercano_pero_fuera_NO_dispara_falso_positivo(dataset):
    """El control de especificidad: G2 también tiene un borde de tabla
    CERCANO pero fuera de la región. Ese caso debe seguir siendo
    editable (si no, el gate rechazaría cualquier factura con tabla)."""
    rep, out = _run(dataset, "G2_borde_cercano", "Fecha", "Dia")
    assert rep["ok"], rep
    assert rep["classification"] == "PASS"


# ── Hallazgo 4: gate de fondo flojo (bg 0.50 aceptado) ───────────────

def test_N_fondo_debil_debe_decidir_rechazar(dataset):
    """FC-005 · N_fondo_gradiente + white daba bg_score 0.50 y
    ok=true. La política debe rechazarlo explícitamente; y la DECISIÓN
    es sobre la evidencia: la misma página con mean pasa."""
    rep_w, _ = _run(dataset, "N_fondo_gradiente", "Perez", "Garcia",
                    strategy="white")
    assert not rep_w["ok"]
    assert rep_w["classification"] == "HONEST_REJECT"
    assert rep_w["dimensions"]["background_ok"] is False
    assert rep_w["reject_reason"] == "background"
    rep_m, _ = _run(dataset, "N_fondo_gradiente", "Perez", "Garcia",
                    strategy="mean")
    assert rep_m["ok"] and rep_m["classification"] == "PASS"


# ── Hallazgo 3: readback no independiente ────────────────────────────

def test_readback_no_puede_reusar_el_mismo_camino(dataset):
    """Si el verificador ES el detector (misma instancia), la
    independencia es NONE y readback_ok DEBE ser false: un error
    sistemático de lectura se autoconfirmaría."""
    prim = TesseractOCRProvider()          # psm 6, el camino de detección
    rep_same, _ = _run(dataset, "A_scan_limpio", "Perez", "Garcia",
                       provider=prim, verifier_provider=prim)
    assert rep_same["verify"]["readback"]["independence_level"] == "NONE"
    assert rep_same["dimensions"]["readback_ok"] is False
    assert not rep_same["ok"]


def test_readback_por_defecto_es_al_menos_WEAK(dataset):
    rep, _ = _run(dataset, "A_scan_limpio", "Perez", "Garcia")
    lvl = rep["verify"]["readback"]["independence_level"]
    assert lvl in ("WEAK", "STRONG"), (
        f"independencia por defecto insuficiente: {lvl}")
    assert rep["dimensions"]["readback_ok"] is True


def test_niveles_de_independencia():
    t6 = TesseractOCRProvider()
    t3 = TesseractOCRProvider(config="--psm 3")
    assert independence_level(t6, t6) == "NONE"
    assert independence_level(t6, t3) == "WEAK"
    # jitter envuelve tesseract: mismo motor → nunca STRONG por decorar
    assert independence_level(JitterOCRProvider(t6), t3) == "WEAK"

    class OtroMotor(TesseractOCRProvider):
        name = "otro_motor"

    assert independence_level(t6, OtroMotor()) == "STRONG"


# ── Modo experimental: nunca confundible con producción ──────────────

def test_modo_experimental_nunca_es_ok_de_produccion(dataset):
    """El único escape permitido a geometry_ok=false es el modo
    experimental: ok_experimental=true, ok=false, mode=EXPERIMENTAL."""
    rep, _ = _run(dataset, "M_rotacion_4", "Perez", "Garcia",
                  mode="experimental")
    assert rep["mode"] == "EXPERIMENTAL"
    assert rep.get("ok_experimental") is True
    assert rep["ok"] is False          # producción jamás lo aprueba
