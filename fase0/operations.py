"""
PROMETEO · FASE 0 · OPERACIONES COMO DATOS + VALIDADOR DE POLÍTICAS
───────────────────────────────────────────────────────────────────
Aquí vive la decisión arquitectónica central de PROMETEO: editar un
documento es REGISTRAR una operación declarativa, nunca tocar píxeles.

Este módulo es puro: no importa PyMuPDF, no hace I/O. La medición de
anchos se inyecta como función, para que validador (aquí), editor
(navegador) y renderer (worker) usen LA MISMA regla de medición.

POLÍTICAS GEOMÉTRICAS (DAS §41). El sistema nunca deforma
silenciosamente: toda decisión de política queda registrada en el
veredicto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

# Orden de intento por defecto. EXPAND/REFLOW/WRAP quedan documentados
# pero no implementados en Fase 0 (no son necesarios para falsificar
# la hipótesis central).
DEFAULT_POLICY_ORDER: Tuple[str, ...] = ("fit", "shrink", "ask_user", "reject")


@dataclass(frozen=True)
class ReplaceText:
    """Reemplaza `old_text` por `new_text` DENTRO del texto del span objetivo.

    old_text puede ser el texto completo del span o un subtexto:
    lo que se re-renderiza es el span completo ya modificado, en su
    baseline original.
    """
    target_span_id: str
    old_text: str
    new_text: str
    policy_preference: Sequence[str] = DEFAULT_POLICY_ORDER
    min_scale: float = 0.55   # mínimo encogimiento tipográfico aceptado

    def as_dict(self) -> Dict:
        return {
            "type": "replace_text",
            "target": self.target_span_id,
            "from": self.old_text,
            "to": self.new_text,
        }


@dataclass
class Verdict:
    ok: bool
    policy: str                      # decisión FINAL tomada
    reason: str
    strategy: str = "full"           # full | suffix (hallazgo P2)
    span_text_after: str = ""        # texto completo del span tras la operación
    tail_text: str = ""              # lo que se re-renderiza (strategy=suffix)
    prefix_end_x_pt: float = 0.0     # borde INK donde empieza lo reemplazado
    insert_x_pt: float = 0.0         # origen de escritura (baseline x)
    requested_size_pt: float = 0.0
    final_size_pt: float = 0.0
    needed_width_pt: float = 0.0
    available_width_pt: float = 0.0
    font_requested: str = ""
    font_used: Optional[str] = None
    font_fallback: bool = False      # True si no se pudo reutilizar/nombrar la fuente

    def as_dict(self) -> Dict:
        return {
            "ok": self.ok,
            "policy": self.policy,
            "reason": self.reason,
            "strategy": self.strategy,
            "spanTextAfter": self.span_text_after,
            "tailText": self.tail_text,
            "prefixEndXPt": round(self.prefix_end_x_pt, 3),
            "insertXPt": round(self.insert_x_pt, 3),
            "requestedSizePt": round(self.requested_size_pt, 3),
            "finalSizePt": round(self.final_size_pt, 3),
            "neededWidthPt": round(self.needed_width_pt, 3),
            "availableWidthPt": round(self.available_width_pt, 3),
            "fontRequested": self.font_requested,
            "fontUsed": self.font_used,
            "fontFallback": self.font_fallback,
        }


# (texto, tamaño_pt, fuente_interna) → ancho en pt. Inyectada por el host.
MeasureFn = Callable[[str, float, str], float]
# nombre de fuente del PDF → (fuente_interna, es_fallback)
ResolveFn = Callable[[str], Tuple[str, bool]]


def _char_boundary(span: Mapping, old_text: str) -> Optional[dict]:
    """Localiza el índice de carácter donde empieza `old_text` usando la
    geometría POR CARÁCTER del span (kerning real incluido).

    Devuelve {"index", "bbox_x0", "origin_x"} o None si no hay datos de
    caracteres, si el límite cae dentro de una ligadura, o si el
    reemplazo empieza en el carácter 0 (equivalente a full)."""
    chars = span.get("chars")
    if not chars:
        return None
    text = span["text"]
    start = text.find(old_text)
    if start <= 0:
        return None
    acc = ""
    for i, ch in enumerate(chars):
        if len(acc) == start:
            return {"index": i, "bbox_x0": ch["bbox_x0"], "origin_x": ch["origin_x"]}
        acc += ch["c"]
    return None   # una ligadura se tragó el límite


def validate_replace(
    op: ReplaceText,
    span: Mapping,
    measure: MeasureFn,
    resolve: ResolveFn,
) -> Verdict:
    """Valida una operación ReplaceText contra el estado ACTUAL del span.

    ESTRATEGIA SUFIJO (hallazgo adversarial P2): el prefijo NO editado
    nunca se re-renderiza — sus objetos originales quedan intactos y su
    kerning sobrevive. Solo se redacta y re-escribe desde el borde de
    tinta del primer carácter reemplazado. Si el límite cae dentro de
    una ligadura, se degrada a estrategia full (re-render completo).
    """
    base = dict(
        font_requested=span.get("font", ""),
        requested_size_pt=float(span.get("size", 0.0)),
    )

    if op.old_text not in span["text"]:
        return Verdict(
            ok=False, policy="reject", reason="target_text_mismatch",
            **base,
        )

    internal, fallback = resolve(span.get("font", ""))
    base["font_used"] = internal
    base["font_fallback"] = fallback

    new_span_text = span["text"].replace(op.old_text, op.new_text, 1)
    size = float(span["size"])
    origin_x = float(span["origin"][0])
    available_full = float(span["clearance_pt"])
    base["span_text_after"] = new_span_text

    boundary = _char_boundary(span, op.old_text)
    if boundary is not None and boundary["index"] > 0:
        insert_x = boundary["origin_x"]
        prefix_end = boundary["bbox_x0"]
        tail = new_span_text[boundary["index"]:]
        needed = measure(tail, size, internal)
        available = available_full - (insert_x - origin_x)
        base.update(strategy="suffix", tail_text=tail,
                    prefix_end_x_pt=prefix_end, insert_x_pt=insert_x,
                    needed_width_pt=needed,
                    available_width_pt=max(available, 0.0))
        if needed <= available:
            return Verdict(
                ok=True, policy="fit", reason="cabe_en_hueco",
                final_size_pt=size, **base,
            )

    # estrategia full: re-render completo del span (necesario si hay que
    # encoger — la cola no puede encogerse sola sin romper la línea —
    # o si el límite cayó dentro de una ligadura)
    insert_x = origin_x
    prefix_end = origin_x
    tail = new_span_text
    needed = measure(tail, size, internal)
    available = available_full
    base.update(strategy="full", tail_text=tail,
                prefix_end_x_pt=prefix_end, insert_x_pt=insert_x)

    base["needed_width_pt"] = needed
    base["available_width_pt"] = max(available, 0.0)

    if needed <= available:
        return Verdict(
            ok=True, policy="fit", reason="cabe_en_hueco",
            final_size_pt=size, **base,
        )

    prefs = op.policy_preference
    if "shrink" in prefs:
        scale = available / needed if needed > 0 else 0.0
        if scale >= op.min_scale:
            return Verdict(
                ok=True, policy="shrink", reason="encogido_para_caber",
                final_size_pt=round(size * scale, 4), **base,
            )
    if "ask_user" in prefs:
        return Verdict(
            ok=False, policy="ask_user", reason="excede_hueco_requiere_decision",
            final_size_pt=size, **base,
        )
    return Verdict(
        ok=False, policy="reject", reason="excede_hueco_y_minimo_de_escala",
        final_size_pt=size, **base,
    )
