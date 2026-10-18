"""
PROMETEO · FASE 0B · REGRESIÓN DEL PIPELINE RASTER
──────────────────────────────────────────────────
El OCR es REAL (Tesseract). El ground truth SOLO mide error.
La suite completa de benchmark vive en benchmark_raster.py; aquí la
huella mínima de regresión (rápida, <30 s).
"""
import os

import pytest

import fixtures_raster
from ocr_provider import JitterOCRProvider, TesseractOCRProvider
from raster import raster_edit

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "raster")


@pytest.fixture(scope="session", autouse=True)
def dataset():
    return fixtures_raster.build_all()


def _run(data, case, old, new, provider=None, strategy="mean"):
    paths = data[case]
    out = os.path.join(OUT, f"reg_{case}.pdf")
    return raster_edit(paths["pdf"], old, new, out,
                       provider=provider, strategy=strategy,
                       gt_pdf=paths["gt_pdf"])


def test_A_scan_limpio_end_to_end(dataset):
    rep = _run(dataset, "A_scan_limpio", "Perez", "Garcia")
    assert rep["ok"], rep
    v = rep["verify"]
    assert v["readback"]["found"] and v["readback"]["best"]["cer"] == 0.0
    assert v["contamination"]["fraction_outside"] <= 0.002
    assert rep["gt_error"]["size_err_pt"] <= 1.0


def test_B_scan_degradado(dataset):
    rep = _run(dataset, "B_scan_degradado", "Perez", "Garcia")
    assert rep["ok"], rep


def test_K_corto_a_largo(dataset):
    rep = _run(dataset, "A_scan_limpio", "Perez",
               "Alejandro Martinez de los Rios")
    assert rep["ok"], rep
    assert rep["verify"]["readback"]["best"]["cer"] <= 0.1


def test_L_largo_a_corto(dataset):
    rep = _run(dataset, "A_scan_limpio", "1.250,00", "OK")
    assert rep["ok"], rep


def test_J_bbox_con_jitter_realdataset(dataset):
    rep = _run(dataset, "J_bbox_imperfecta", "Perez", "Garcia",
               provider=JitterOCRProvider(TesseractOCRProvider(), sigma_px=3.0))
    assert rep["ok"], rep


def test_F_perspectiva_SE_NIEGA_LIMPIAMENTE(dataset):
    """FC-001: la perspectiva fuerte rompe el OCR. El sistema NO debe
    producir nada: se rehúsa con la causa registrada. Ese rechazo
    limpio ES el comportamiento correcto hasta que exista rectificación."""
    rep = _run(dataset, "F_perspectiva", "Perez", "Garcia")
    assert not rep["ok"]
    assert rep["stages"]["ocr"]["reason"] == "texto_no_encontrado_por_ocr"
