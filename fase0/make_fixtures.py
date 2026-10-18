"""
PROMETEO · FASE 0 · FIXTURES DETERMINISTAS
──────────────────────────────────────────
Genera los PDFs de prueba del DAS §19. Misma entrada → mismos bytes
→ mismos tests para siempre.

  case_a.pdf        Caso A · born-digital (incluye Caso E: texto pequeño)
  case_d_rotated    Caso D · página con /Rotate 90
  case_b_scan.pdf   Caso B · simulación de escaneo (imagen a 200 dpi)
"""
from __future__ import annotations

import os

import pymupdf

A4_W, A4_H = 595.276, 841.890
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")


def _content(page: pymupdf.Page) -> None:
    page.insert_text(pymupdf.Point(72, 72), "CONTRATO DE SERVICIOS",
                     fontname="hebo", fontsize=14)
    page.insert_text(pymupdf.Point(72, 120), "Contratado: Juan Perez",
                     fontname="helv", fontsize=11)
    page.insert_text(pymupdf.Point(72, 140), "Fecha de inicio: 10 de agosto de 2025",
                     fontname="helv", fontsize=11)
    page.insert_text(pymupdf.Point(72, 170),
                     "El presente documento acuerda los terminos del servicio "
                     "prestado entre las partes, conforme a lo dispuesto.",
                     fontname="helv", fontsize=9.5)
    # Caso E · texto pequeño (6.5 pt)
    page.insert_text(pymupdf.Point(72, 750), "Referencia interna: AB-2025-0042",
                     fontname="helv", fontsize=6.5)


def make_case_a(path: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=A4_W, height=A4_H)
    _content(page)
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def make_case_d_rotated(path: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=A4_W, height=A4_H)
    page.set_rotation(90)          # el espacio visible pasa a 842×595
    _content(page)
    doc.save(path, garbage=3, deflate=True)
    doc.close()


def make_case_b_scan(path: str, dpi: int = 200) -> None:
    src = os.path.join(ASSETS, "case_a.pdf")
    src_doc = pymupdf.open(src)
    pix = src_doc[0].get_pixmap(dpi=dpi)
    out = pymupdf.open()
    page = out.new_page(width=A4_W, height=A4_H)
    page.insert_image(page.rect, pixmap=pix)
    out.save(path, garbage=3, deflate=True)
    out.close()
    src_doc.close()


def ensure_assets() -> dict:
    os.makedirs(ASSETS, exist_ok=True)
    paths = {
        "case_a": os.path.join(ASSETS, "case_a.pdf"),
        "case_d_rotated": os.path.join(ASSETS, "case_d_rotated.pdf"),
        "case_b_scan": os.path.join(ASSETS, "case_b_scan.pdf"),
    }
    if not all(os.path.exists(p) for p in paths.values()):
        make_case_a(paths["case_a"])
        make_case_d_rotated(paths["case_d_rotated"])
        make_case_b_scan(paths["case_b_scan"])
    return paths


if __name__ == "__main__":
    for name, p in ensure_assets().items():
        print(f"{name:16s} → {p}")
