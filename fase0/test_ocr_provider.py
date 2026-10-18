"""PROMETEO · Unit Tests for OCR Provider & Degraded Runtime Mode (ORDEN 139)
─────────────────────────────────────────────────────────────────────────────
Valida:
- Descubrimiento de binario Tesseract y directorio tessdata.
- Detección de disponibilidad del motor OCR.
- Modo degradado honesto (OCRUnavailableError) sin caída fatal del sistema.
- Extracción OCR real sobre imagen sintética si el binario está disponible.
"""
from __future__ import annotations

import os
import pytest
from PIL import Image, ImageDraw

from fase0.ocr_provider import (
    TesseractOCRProvider,
    OCRUnavailableError,
    find_tesseract_binary,
    find_tessdata_dir,
    is_tesseract_available,
)


def test_tesseract_discovery():
    """Verifica que el descubrimiento de Tesseract y tessdata funcione de forma determinista."""
    bin_path = find_tesseract_binary()
    assert bin_path is not None, "El binario de tesseract debería ser descubierto en el host de desarrollo"
    assert os.path.isfile(bin_path)

    tessdata = find_tessdata_dir()
    assert tessdata is not None, "El directorio tessdata debería ser descubierto"
    assert os.path.isdir(tessdata)


def test_tesseract_env_override(monkeypatch):
    """Verifica que PROMETEO_TESSERACT_PATH tenga precedencia."""
    fake_path = "/nonexistent/bin/tesseract"
    monkeypatch.setenv("PROMETEO_TESSERACT_PATH", fake_path)
    # No es archivo ejecutable real, por lo que find_tesseract_binary no lo retorna como válido
    assert find_tesseract_binary() != fake_path


def test_is_tesseract_available_probe():
    """Verifica que is_tesseract_available reporte un booleano sin lanzar excepción."""
    avail = is_tesseract_available()
    assert isinstance(avail, bool)


def test_tesseract_degraded_mode_on_missing_binary(monkeypatch):
    """Simula ausencia de binario y verifica que process() lance OCRUnavailableError."""
    monkeypatch.setattr("fase0.ocr_provider.is_tesseract_available", lambda: False)
    provider = TesseractOCRProvider()
    img = Image.new("RGB", (200, 50), color=(255, 255, 255))
    with pytest.raises(OCRUnavailableError) as exc_info:
        provider.process(img, dpi=300.0)
    assert "not available" in str(exc_info.value)


def test_tesseract_real_execution():
    """Ejecuta OCR sobre una imagen sintética limpia y verifica que reconozca el texto."""
    if not is_tesseract_available():
        pytest.skip("Tesseract no disponible en este entorno")

    provider = TesseractOCRProvider(lang="eng")
    img = Image.new("RGB", (300, 80), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 25), "PROMETEO 2026", fill=(0, 0, 0))

    page = provider.process(img, dpi=300.0)
    assert len(page.words) > 0
    joined = " ".join(w.text for w in page.words)
    assert "PROMETEO" in joined or "2026" in joined
