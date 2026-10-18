"""
PROMETEO · FASE 0 · NÚCLEO GEOMÉTRICO
──────────────────────────────────────
El archivo más importante del repositorio.

REGLA DE PROYECTO: ninguna conversión de coordenadas ocurre fuera de
este módulo. Multiplicar por dpi/72, invertir el eje Y, aplicar dpr o
normalizar fuera de aquí es un error de arquitectura, no un atajo.

Espacios definidos (todos comparten Y hacia abajo, origen arriba-izquierda):

  PDF     — puntos (1/72"), área visible de la página (CropBox ya resuelta
            por PyMuPDF en page.rect). Espacio canónico del modelo.
  NORM    — normalizado [0,1] respecto al área visible. Para persistir
            geometría independiente del viewport.
  RASTER  — píxeles de un render a `dpi` dado (salida de OCR, pixmaps).
  CANVAS  — píxeles CSS del canvas del editor (RASTER × devicePixelRatio).

La cadena completa del sistema:

  PDF  ↕  NORM  ↕  VIEWPORT/RASTER  ↕  CANVAS  ↕  EXPORT(=PDF)

El espacio de exportación ES el espacio PDF: exportamos sobre el
original, no sobre un render.
"""
from __future__ import annotations

from dataclasses import dataclass

PT_PER_INCH = 72.0


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def inset(self, d: float) -> "Rect":
        return Rect(self.x0 + d, self.y0 + d, self.x1 - d, self.y1 - d)


class SpaceTransform:
    """Transformación única entre espacios para UNA página y UN viewport."""

    def __init__(
        self,
        page_width_pt: float,
        page_height_pt: float,
        dpi: float = 72.0,
        dpr: float = 1.0,
    ) -> None:
        self.w_pt = float(page_width_pt)
        self.h_pt = float(page_height_pt)
        self.dpi = float(dpi)
        self.dpr = float(dpr)
        self._raster = self.dpi / PT_PER_INCH        # pt → px de render
        self._canvas = self._raster * self.dpr       # pt → px CSS del editor

    # ── tamaños derivados ──────────────────────────────────────────
    @property
    def raster_width(self) -> int:
        return int(round(self.w_pt * self._raster))

    @property
    def raster_height(self) -> int:
        return int(round(self.h_pt * self._raster))

    @property
    def canvas_width(self) -> float:
        return self.w_pt * self._canvas

    @property
    def canvas_height(self) -> float:
        return self.h_pt * self._canvas

    # ── PDF(pt) ↔ RASTER(px de render / coordenadas de OCR) ────────
    def pdf_to_raster(self, p: Point) -> Point:
        return Point(p.x * self._raster, p.y * self._raster)

    def raster_to_pdf(self, p: Point) -> Point:
        return Point(p.x / self._raster, p.y / self._raster)

    def rect_pdf_to_raster(self, r: Rect) -> Rect:
        a, b = self.pdf_to_raster(Point(r.x0, r.y0)), self.pdf_to_raster(Point(r.x1, r.y1))
        return Rect(a.x, a.y, b.x, b.y)

    def rect_raster_to_pdf(self, r: Rect) -> Rect:
        a, b = self.raster_to_pdf(Point(r.x0, r.y0)), self.raster_to_pdf(Point(r.x1, r.y1))
        return Rect(a.x, a.y, b.x, b.y)

    # ── PDF ↔ NORMALIZED [0,1] ─────────────────────────────────────
    def pdf_to_norm(self, p: Point) -> Point:
        return Point(p.x / self.w_pt, p.y / self.h_pt)

    def norm_to_pdf(self, p: Point) -> Point:
        return Point(p.x * self.w_pt, p.y * self.h_pt)

    # ── PDF ↔ CANVAS(px CSS del editor, con dpr aplicado) ──────────
    def pdf_to_canvas(self, p: Point) -> Point:
        return Point(p.x * self._canvas, p.y * self._canvas)

    def canvas_to_pdf(self, p: Point) -> Point:
        return Point(p.x / self._canvas, p.y / self._canvas)
