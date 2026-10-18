"""
PROMETEO · FASE 0 · RENDER (aplicación determinista de operaciones)
───────────────────────────────────────────────────────────────────
Aplica operaciones validadas sobre el PDF ORIGINAL (abierto en fresco
en cada exportación → reproducibilidad) usando PyMuPDF.

Cadena de fidelidad tipográfica (DAS §12):
  1. reutilizar la fuente embebida del propio documento (fontbuffer)
  2. alias base-14 por nombre (Helvetica, Times, Courier…)
  3. fallback helv, declarado como fallback (nunca silencioso)

La MISMA instancia de pymupdf.Font mide (validación) y escribe
(render): el preview y el export no pueden discrepar.

AVISO DE LICENCIA (auditoría §C): PyMuPDF es AGPL-3.0. Para Fase 0
(experimento interno) es válido; ANTES de productizar hay que decidir:
licencia comercial de Artifex, o reconstruir sobre pikepdf +
pdfminer.six + reportlab (permissivas). Esta decisión es una compuerta
de la Fase 1, no un detalle.
"""
from __future__ import annotations

from typing import Dict, Tuple

import pymupdf

# ── Alias base-14: nombre PDF → nombre interno PyMuPDF ──────────────
FONT_ALIASES: Dict[str, str] = {
    "Helvetica": "helv",
    "Helvetica-Bold": "hebo",
    "Helvetica-Oblique": "heit",
    "Helvetica-BoldOblique": "hebi",
    "Times-Roman": "tiro",
    "Times": "tiro",
    "times": "tiro",
    "Times-Bold": "tibo",
    "Times-Italic": "tiit",
    "Times-BoldItalic": "tibi",
    "Courier": "cour",
    "courier": "cour",
    "Courier-Bold": "cobo",
    "Courier-Oblique": "coit",
    "Courier-BoldOblique": "cobi",
    "Symbol": "symb",
    "ZapfDingbats": "zadb",
}


def color_int_to_rgb(c: int) -> Tuple[float, float, float]:
    return ((c >> 16 & 255) / 255.0, (c >> 8 & 255) / 255.0, (c & 255) / 255.0)


class FontBook:
    """Resuelve, mide y escribe fuentes para UN documento.

    La realidad de los PDF: el nombre que reporta la extracción de
    texto (p.ej. 'ArialMT') NO tiene por qué coincidir con el basefont
    del recurso ('Arial Regular'). Cadena de matching:
      1. exacto y sin prefijo de subset (+ABCDEF)
      2. tolerante a mayúsculas/espacios
      3. si la página tiene UNA sola fuente embebida, es esa
      4. alias base-14 por nombre
      5. fallback helv (declarado, nunca silencioso)
    """

    def __init__(self, doc: "pymupdf.Document", page: "pymupdf.Page") -> None:
        self._embedded: Dict[str, bytes] = {}
        self._fonts: Dict[str, "pymupdf.Font"] = {}      # interno → Font
        self._embedded_internal: Dict[str, str] = {}     # key → interno
        try:
            for xref, _ext, _type, basefont, _name, _enc in page.get_fonts():
                try:
                    _bname, _fext, _subtype, buffer = doc.extract_font(xref)
                    if buffer:
                        clean = basefont.split("+")[-1]
                        self._embedded.setdefault(clean, bytes(buffer))
                except Exception:
                    continue
        except Exception:
            pass
        self._next_id = 0

    # ── decisión (pura, para reportes) ─────────────────────────────
    def resolve(self, pdf_font_name: str) -> Tuple[str, bool]:
        """Cadena de matching (orden corregido tras hallazgo adversarial
        P1: la heurística de fuente única ROBABA la embebida cuando el
        span era base-14 con alias disponible):
          1. exacto / tolerante contra fuentes embebidas
          2. alias base-14                          ← antes de la heurística
          3. página con UNA sola embebida → es esa
          4. fallback helv (declarado, nunca silencioso)
        """
        clean = pdf_font_name.split("+")[-1]
        key = self._match_key(pdf_font_name)
        if key is not None:
            if key not in self._embedded_internal:
                self._embedded_internal[key] = f"PROMF{self._next_id}"
                self._next_id += 1
            return self._embedded_internal[key], False
        if pdf_font_name in FONT_ALIASES:
            return FONT_ALIASES[pdf_font_name], False
        if clean in FONT_ALIASES:
            return FONT_ALIASES[clean], False
        if len(self._embedded) == 1:
            k = next(iter(self._embedded))
            self._embedded_internal.setdefault(k, f"PROMF{self._next_id}")
            self._next_id += 1
            return self._embedded_internal[k], False
        return "helv", True

    def _match_key(self, pdf_font_name: str) -> str | None:
        clean = pdf_font_name.split("+")[-1]
        if clean in self._embedded:
            return clean
        squashed = {self._squash(k): k for k in self._embedded}
        key = self._squash(clean)
        if key in squashed:
            return squashed[key]
        return None

    @staticmethod
    def _squash(name: str) -> str:
        return "".join(ch.lower() for ch in name if ch.isalnum())

    # ── objeto tipográfico real (mide y escribe) ────────────────────
    def font_for(self, internal: str) -> "pymupdf.Font":
        resolved_name = FONT_ALIASES.get(internal, internal)
        font = self._fonts.get(resolved_name)
        if font is None:
            if resolved_name.startswith("PROMF"):
                buf = next(
                    v for k, v in self._embedded.items()
                    if self._embedded_internal.get(k) == resolved_name
                )
                font = pymupdf.Font(fontbuffer=buf)
            else:
                font = pymupdf.Font(resolved_name)
            self._fonts[resolved_name] = font
        return font

    # ── FC-007 · contrato de fuente antes de tocar nada ──────────────
    def check_font_for_edit(self, span: dict, new_text: str) -> dict:
        """Cadena REQUESTED → RESOLVED → USABLE, verificada ANTES de
        escribir. FC-007 (CAL-001, SILENT_FAILURE crítico): pymupdf no
        valida el programa de fuente al cargar un fontbuffer —
        subsets con mapa roto (name='(null)') o sin los glifos del
        texto nuevo hacen que MuPDF sustituya SILENCIOSAMENTE por Noto
        al escribir. Este método convierte esa trampa en rechazo
        honesto: jamás se escribe con una fuente que no podemos usar.

        usable=False ⇒ la edición NO puede preservar la identidad
        tipográfica ⇒ política superior: reject (engine decide)."""
        requested = span["font"]
        internal, fallback = self.resolve(requested)
        chars = set(span.get("text", "")) | set(new_text)
        missing = []
        try:
            font = self.font_for(internal)
        except Exception as e:
            return {"requested": requested, "resolved_internal": internal,
                    "resolved_name": None, "fallback": fallback,
                    "usable": False, "reason": "font_programa_ilegible",
                    "error": f"{type(e).__name__}: {e}", "missing_glyphs": []}
        name = getattr(font, "name", None)
        if not name or name == "(null)":
            return {"requested": requested, "resolved_internal": internal,
                    "resolved_name": name, "fallback": fallback,
                    "usable": False, "reason": "font_programa_ilegible",
                    "missing_glyphs": []}
        for c in sorted(chars):
            if c.strip() and not font.has_glyph(ord(c)):
                missing.append(c)
        if missing:
            return {"requested": requested, "resolved_internal": internal,
                    "resolved_name": name, "fallback": fallback,
                    "usable": False, "reason": "glifos_ausentes",
                    "missing_glyphs": missing}
        return {"requested": requested, "resolved_internal": internal,
                "resolved_name": name, "fallback": fallback,
                "usable": True, "reason": None, "missing_glyphs": []}

    def measure(self, text: str, size_pt: float, internal: str) -> float:
        """Única regla de medición del sistema: el editor y el worker
        deben medir con el mismo mecanismo, o el preview miente."""
        return float(self.font_for(internal).text_length(text, fontsize=size_pt))

    def write(
        self,
        page: "pymupdf.Page",
        origin: Tuple[float, float],
        text: str,
        internal: str,
        size_pt: float,
        color: int,
    ) -> None:
        """Escribe con TextWriter: la fuente viaja como objeto, no como
        registro de página (sobrevive a apply_redactions)."""
        tw = pymupdf.TextWriter(page.rect)
        tw.append(
            pymupdf.Point(origin[0], origin[1]),
            text,
            font=self.font_for(internal),
            fontsize=size_pt,
        )
        tw.write_text(page, color=color_int_to_rgb(color))


def _plan_patch(span: dict, verdict) -> tuple:
    """Decide el rect de redacción y el texto/posición de escritura.

    Estrategia SUFFIX (hallazgo P2): el prefijo no editado queda
    intacto — sus objetos y su kerning originales sobreviven. Solo se
    redacta desde el borde de tinta del primer carácter reemplazado.
    """
    if verdict.strategy == "suffix":
        redact = pymupdf.Rect(verdict.prefix_end_x_pt, span["bbox"][1],
                              span["bbox"][2], span["bbox"][3])
        return redact, verdict.insert_x_pt, verdict.tail_text
    redact = pymupdf.Rect(span["bbox"])
    return redact, span["origin"][0], verdict.span_text_after


def apply_replace(page: "pymupdf.Page", fontbook: FontBook, span: dict, verdict) -> None:
    """Ejecuta FÍSICAMENTE un replace validado sobre la página.

    1. redacta SOLO la región reemplazada (borra objetos de texto, no los tapa)
    2. escribe la cola nueva en la baseline original, con el tamaño
       final decidido por la política.
    """
    redact, insert_x, text = _plan_patch(span, verdict)
    page.add_redact_annot(redact, fill=False)
    page.apply_redactions()
    internal, _fallback = fontbook.resolve(span["font"])
    fontbook.write(page, (insert_x, span["origin"][1]), text,
                   internal, verdict.final_size_pt, span.get("color", 0))


def apply_replace_on_scan(page: "pymupdf.Page", fontbook: FontBook, span: dict, verdict) -> None:
    """Ruta experimental Clase B (raster): parche de fondo + texto nuevo.

    Fase 0 asume fondo uniforme (parche blanco). La reparación real de
    fondo (LaMa/OpenCV/PatchMatch) es el benchmark de la Fase 0.5.
    """
    redact, insert_x, text = _plan_patch(span, verdict)
    page.draw_rect(redact, color=None, fill=(1, 1, 1))
    internal, _fallback = fontbook.resolve(span["font"])
    fontbook.write(page, (insert_x, span["origin"][1]), text,
                   internal, verdict.final_size_pt, span.get("color", 0))
