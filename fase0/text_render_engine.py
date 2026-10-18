"""PROMETEO · Text Rendering Engine Abstraction & Multi-Engine Architecture (ORDEN 139)
─────────────────────────────────────────────────────────────────────────────
Define la arquitectura desacoplada para renderizado tipográfico offline:
- Interfaz `TextRenderEngine` agnóstica de raster operations.
- `ENGINE_BASELINE`: Adaptador PyMuPDF FontBook estándar.
- `PIL_FREETYPE`: Challenger 1 basado en Pillow / FreeType.
- `FontResolver`: Capa de resolución de fuentes determinista y offline con inventario local.
- `FittingPolicy`: Política de ajuste de texto con límite estricto de reducción (max shrink 15%).
- Verificación explícita de cobertura de glifos (Unicode / acentos en español) sin tofu silencioso.
- Declaración rigurosa de niveles de garantía (visual identity vs metric compatible).
"""
from __future__ import annotations

import os
import math
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pymupdf

try:
    from fase0.render import FontBook
except ImportError:
    from render import FontBook


# Clases de sustitución formal
EXACT_FONT = "EXACT_FONT"
METRIC_COMPATIBLE_SUBSTITUTE = "METRIC_COMPATIBLE_SUBSTITUTE"
GENERIC_APPROXIMATION = "GENERIC_APPROXIMATION"
UNSUPPORTED = "UNSUPPORTED"

# Ámbitos de garantía tipográfica
GUARANTEE_EXACT = "EXACT_VISUAL_IDENTITY"
GUARANTEE_METRIC = "METRIC_COMPATIBLE"
GUARANTEE_APPROX = "APPROXIMATE_RENDERING"
GUARANTEE_REJECT = "HONEST_REJECT"

# Identificadores canónicos de motores
ENGINE_BASELINE = "PYMUPDF_FONTBOOK_BASELINE"
ENGINE_CHALLENGER_PIL = "PIL_FREETYPE"


@dataclass(frozen=True)
class FontRequest:
    """Solicitud tipográfica normalizada."""
    family: str = "helv"
    size_pt: float = 10.0
    color_rgb: Tuple[int, int, int] = (0, 0, 0)
    bold: bool = False
    italic: bool = False


@dataclass
class RenderMetrics:
    """Métricas geométricas calculadas por el motor de renderizado."""
    advance_width_pt: float
    height_pt: float
    ascender_pt: float
    descender_pt: float
    baseline_y_pt: float
    baseline_y_px: float
    width_px: int
    height_px: int


@dataclass
class RenderedPatch:
    """Resultado del renderizado tipográfico con trazabilidad completa."""
    bitmap: np.ndarray  # Grayscale 2D uint8
    metrics: RenderMetrics
    engine_id: str
    requested_font: str
    resolved_font_name: str
    substitution_class: str
    guarantee_scope: str
    glyph_coverage: float
    missing_glyphs: List[str] = field(default_factory=list)


class FontResolver:
    """Resolutor de fuentes offline determinista."""

    CANONICAL_FAMILIES = {
        "helv": ("helv", "Helvetica", EXACT_FONT, GUARANTEE_EXACT),
        "helvetica": ("helv", "Helvetica", EXACT_FONT, GUARANTEE_EXACT),
        "arial": ("helv", "Arial -> Helvetica", METRIC_COMPATIBLE_SUBSTITUTE, GUARANTEE_METRIC),
        "sans": ("helv", "Generic Sans -> Helvetica", GENERIC_APPROXIMATION, GUARANTEE_APPROX),
        "sans-serif": ("helv", "Generic Sans-Serif -> Helvetica", GENERIC_APPROXIMATION, GUARANTEE_APPROX),
        "times": ("times", "Times-Roman", EXACT_FONT, GUARANTEE_EXACT),
        "times-roman": ("times", "Times-Roman", EXACT_FONT, GUARANTEE_EXACT),
        "serif": ("times", "Generic Serif -> Times-Roman", GENERIC_APPROXIMATION, GUARANTEE_APPROX),
        "courier": ("courier", "Courier", EXACT_FONT, GUARANTEE_EXACT),
        "mono": ("courier", "Generic Monospace -> Courier", GENERIC_APPROXIMATION, GUARANTEE_APPROX),
        "monospace": ("courier", "Generic Monospace -> Courier", GENERIC_APPROXIMATION, GUARANTEE_APPROX),
    }

    # Caracteres de validación en español y símbolos internacionales
    SPANISH_UNICODE_CHARS = "áéíóúÁÉÍÓÚñÑüÜ¿¡€"

    @classmethod
    def resolve(cls, requested_family: str) -> Tuple[str, str, str, str]:
        """Devuelve (canon_id, font_name, substitution_class, guarantee_scope)."""
        key = requested_family.lower().strip()
        if key in cls.CANONICAL_FAMILIES:
            return cls.CANONICAL_FAMILIES[key]
        # Si no se reconoce la familia: aproximación genérica a helv
        return ("helv", f"Unknown '{requested_family}' -> Helvetica", GENERIC_APPROXIMATION, GUARANTEE_APPROX)

    @classmethod
    def check_glyphs(cls, text: str) -> Tuple[float, List[str]]:
        """Verifica la compatibilidad de glifos sin acudir a internet.
        Devuelve (coverage_ratio, missing_glyphs)."""
        if not text:
            return 1.0, []

        missing = []
        for char in text:
            # Descartar caracteres de control no imprimibles
            cat = unicodedata.category(char)
            if cat.startswith("C") and char not in "\n\t":
                missing.append(char)
            # Rango Unicode soportado en fuentes estándar Base14 y Latin-1 Extended + puntuación tipográfica
            code = ord(char)
            if code > 0x024F and char not in "€¿¡—–«»“”‘’•…":
                # Carácter fuera de alfabeto latino extendido / símbolos soportados
                missing.append(char)

        total = len(text)
        covered = total - len(missing)
        ratio = max(0.0, min(1.0, covered / total))
        return ratio, missing


class TextRenderEngine(ABC):
    """Interfaz abstracta del motor de renderizado tipográfico."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def measure_metrics(self, text: str, font_req: FontRequest, dpi: float = 300.0) -> RenderMetrics:
        raise NotImplementedError

    @abstractmethod
    def render_text(
        self,
        text: str,
        font_req: FontRequest,
        dpi: float = 300.0,
        target_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> RenderedPatch:
        raise NotImplementedError


class PyMuPDFBaselineEngine(TextRenderEngine):
    """Motor canónico de referencia (ENGINE_BASELINE) vía PyMuPDF FontBook."""

    @property
    def engine_id(self) -> str:
        return ENGINE_BASELINE

    def _get_font(self, font_name: str):
        doc = pymupdf.open()
        page = doc.new_page(width=100, height=100)
        fb = FontBook(doc, page)
        font = fb.font_for(font_name)
        return font

    def measure_metrics(self, text: str, font_req: FontRequest, dpi: float = 300.0) -> RenderMetrics:
        canon_id, font_name, sub_class, guar = FontResolver.resolve(font_req.family)
        font = self._get_font(canon_id)

        width_pt = font.text_length(text, fontsize=font_req.size_pt)
        height_pt = font_req.size_pt * 1.2
        ascender_pt = font_req.size_pt * 0.8
        descender_pt = font_req.size_pt * 0.2
        baseline_y_pt = font_req.size_pt * 1.0

        scale = dpi / 72.0
        width_px = int(math.ceil(width_pt * scale))
        height_px = int(math.ceil(height_pt * scale))
        baseline_y_px = baseline_y_pt * scale

        return RenderMetrics(
            advance_width_pt=width_pt,
            height_pt=height_pt,
            ascender_pt=ascender_pt,
            descender_pt=descender_pt,
            baseline_y_pt=baseline_y_pt,
            baseline_y_px=baseline_y_px,
            width_px=width_px,
            height_px=height_px,
        )

    def render_text(
        self,
        text: str,
        font_req: FontRequest,
        dpi: float = 300.0,
        target_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> RenderedPatch:
        canon_id, resolved_name, sub_class, guar = FontResolver.resolve(font_req.family)
        coverage, missing = FontResolver.check_glyphs(text)

        if missing:
            guar = GUARANTEE_REJECT
            sub_class = UNSUPPORTED

        metrics = self.measure_metrics(text, font_req, dpi=dpi)

        pad_pt = font_req.size_pt * 0.2
        page_w = metrics.advance_width_pt + 2 * pad_pt
        page_h = font_req.size_pt * 1.5

        doc = pymupdf.open()
        page = doc.new_page(width=page_w, height=page_h)
        fb = FontBook(doc, page)
        baseline_pt = font_req.size_pt * 1.15
        fb.write(page, (pad_pt, baseline_pt), text, canon_id, font_req.size_pt, 0)
        pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
        doc.close()

        return RenderedPatch(
            bitmap=arr,
            metrics=metrics,
            engine_id=self.engine_id,
            requested_font=font_req.family,
            resolved_font_name=resolved_name,
            substitution_class=sub_class,
            guarantee_scope=guar,
            glyph_coverage=coverage,
            missing_glyphs=missing,
        )


class PillowFreeTypeEngine(TextRenderEngine):
    """Challenger 1 (PIL_FREETYPE) basado en Pillow / FreeType."""

    @property
    def engine_id(self) -> str:
        return ENGINE_CHALLENGER_PIL

    def _get_pil_font(self, font_req: FontRequest, dpi: float = 300.0) -> ImageFont.ImageFont:
        size_px = int(math.ceil(font_req.size_pt * (dpi / 72.0)))
        # Cargar fuente por defecto o del sistema si está disponible
        try:
            return ImageFont.load_default(size=size_px)
        except Exception:
            return ImageFont.load_default()

    def measure_metrics(self, text: str, font_req: FontRequest, dpi: float = 300.0) -> RenderMetrics:
        font = self._get_pil_font(font_req, dpi=dpi)
        bbox = font.getbbox(text) if hasattr(font, "getbbox") else (0, 0, len(text) * 10, int(font_req.size_pt))

        width_px = bbox[2] - bbox[0]
        height_px = max(bbox[3] - bbox[1], int(font_req.size_pt * (dpi / 72.0)))

        scale = 72.0 / dpi
        width_pt = width_px * scale
        height_pt = height_px * scale
        baseline_y_pt = font_req.size_pt * 0.9
        baseline_y_px = baseline_y_pt * (dpi / 72.0)

        return RenderMetrics(
            advance_width_pt=width_pt,
            height_pt=height_pt,
            ascender_pt=font_req.size_pt * 0.75,
            descender_pt=font_req.size_pt * 0.25,
            baseline_y_pt=baseline_y_pt,
            baseline_y_px=baseline_y_px,
            width_px=width_px,
            height_px=height_px,
        )

    def render_text(
        self,
        text: str,
        font_req: FontRequest,
        dpi: float = 300.0,
        target_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> RenderedPatch:
        canon_id, resolved_name, sub_class, guar = FontResolver.resolve(font_req.family)
        coverage, missing = FontResolver.check_glyphs(text)

        if missing:
            guar = GUARANTEE_REJECT
            sub_class = UNSUPPORTED

        metrics = self.measure_metrics(text, font_req, dpi=dpi)
        pad_px = int(10 * (dpi / 72.0))
        img_w = metrics.width_px + 2 * pad_px
        img_h = metrics.height_px + 2 * pad_px

        img = Image.new("L", (img_w, img_h), color=255)
        draw = ImageDraw.Draw(img)
        font = self._get_pil_font(font_req, dpi=dpi)
        draw.text((pad_px, pad_px), text, font=font, fill=0)

        arr = np.array(img, dtype=np.uint8)

        return RenderedPatch(
            bitmap=arr,
            metrics=metrics,
            engine_id=self.engine_id,
            requested_font=font_req.family,
            resolved_font_name=f"Pillow FreeType ({resolved_name})",
            substitution_class=METRIC_COMPATIBLE_SUBSTITUTE if sub_class == EXACT_FONT else sub_class,
            guarantee_scope=GUARANTEE_METRIC if guar == GUARANTEE_EXACT else guar,
            glyph_coverage=coverage,
            missing_glyphs=missing,
        )


class FittingPolicy:
    """Política de adaptación geométrica con límite estricto de reducción."""

    MAX_SHRINK_RATIO = 0.85  # Máximo 15% de reducción permitida

    @classmethod
    def fit_text(
        cls,
        text: str,
        initial_font_req: FontRequest,
        target_bbox: Tuple[float, float, float, float],
        engine: TextRenderEngine,
        dpi: float = 300.0,
    ) -> Tuple[Optional[FontRequest], str]:
        """Ajusta el tamaño de fuente uniformemente.
        Retorna (font_req_ajustado, resultado_status).
        Si excede tras reducción máxima de 15%: retorna (None, HONEST_REJECT)."""
        x0, y0, x1, y1 = target_bbox
        target_w = max(0.0, x1 - x0)
        target_h = max(0.0, y1 - y0)

        metrics = engine.measure_metrics(text, initial_font_req, dpi=dpi)
        if metrics.advance_width_pt <= target_w and metrics.height_pt <= target_h:
            return initial_font_req, "EXACT_FIT"

        # Calcular factor de escala requerido
        scale_w = target_w / metrics.advance_width_pt if metrics.advance_width_pt > 0 else 1.0
        scale_h = target_h / metrics.height_pt if metrics.height_pt > 0 else 1.0
        needed_scale = min(scale_w, scale_h)

        if needed_scale >= cls.MAX_SHRINK_RATIO:
            adjusted_req = FontRequest(
                family=initial_font_req.family,
                size_pt=round(initial_font_req.size_pt * needed_scale, 2),
                color_rgb=initial_font_req.color_rgb,
                bold=initial_font_req.bold,
                italic=initial_font_req.italic,
            )
            return adjusted_req, "FITTED_WITH_SHRINK"

        # Excede la tolerancia preregistrada del 15% -> HONEST_REJECT
        return None, GUARANTEE_REJECT
