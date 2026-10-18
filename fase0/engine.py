"""
PROMETEO · FASE 0 · MOTOR (orquestador del vertical slice)
─────────────────────────────────────────────────────────
Ciclo completo que puede matar o coronar el proyecto:

  PDF → extraer modelo espacial → validar operación (política)
      → aplicar (redact + re-tipografiar) → exportar
      → VERIFICAR (re-extraer y medir el error geométrico)
      → reporte de trazabilidad (hashes, operaciones, veredicto)

El original jamás se modifica. Una versión = original + operaciones.
Si ALGUNA operación no valida, NO se escribe nada (DAS §55, TEST 5).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Dict, List, Optional

import pymupdf

from operations import ReplaceText, Verdict, validate_replace
from render import FontBook, apply_replace, apply_replace_on_scan

RIGHT_MARGIN_PT = 36.0
ORIGIN_TOLERANCE_PT = 1.5   # tolerancia Fase 0: ≈ 0.53 mm

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")

# Clones canónicos de las base-14: MuPDF implementa Helvetica/Times/Courier
# con las URW Nimbus (idénticas métricas/glyphs — SON las base-14 de facto).
# El texto nuevo escrito con "helv" extrae como "NimbusSans-Regular": misma
# identidad tipográfica, distinto rótulo. Arial-BoldMT ↔ NotoSerif-Regular
# NO canoniza: esa sustitución sigue siendo mismatch (FC-007).
_BASE14_CLONES = (
    ("nimbussans", "helvetica"),
    ("nimbusroman", "times"),
    ("nimbusmono", "courier"),
)


def _squash(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _canon_font(name: str) -> str:
    s = _squash(_SUBSET_PREFIX.sub("", name or ""))
    for clone, canon in _BASE14_CLONES:
        if s.startswith(clone):
            return canon + s[len(clone):]
    return s


def _font_identity_match(requested: str, observed: str) -> bool:
    """Identidad tipográfica tolerante (FC-007 §9: el nombre NO es prueba
    única — se combina con extracción post-export y el pre-check de
    glifos; aquí solo la comparación). Prefijos de subset ignorados y
    clones base-14 canonizados (Nimbus = implementación de Helvetica)."""
    a = _canon_font(requested)
    b = _canon_font(observed)
    if not a or not b:
        return False
    return a in b or b in a


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_ID_RE = re.compile(rb"/ID\[<([0-9A-Fa-f]{32})><([0-9A-Fa-f]{32})>\]")


def _deterministic_id(data: bytes) -> bytes:
    """MuPDF regenera el segundo /ID del trailer con el reloj en cada save,
    rompiendo la reproducibilidad byte a byte. Lo sustituimos por un valor
    derivado del propio contenido: misma entrada → mismos bytes, para
    siempre. (En producción: normalizar con qpdf/pikepdf.)"""
    m = _ID_RE.search(data)
    if not m:
        return data
    # 1) cegar el ID volátil, 2) digerir la forma normalizada, 3) sellar
    blinded = _ID_RE.sub(rb"/ID[<\1><" + b"0" * 32 + rb">]", data, count=1)
    digest = hashlib.sha256(blinded).hexdigest()[:32].upper().encode()
    return _ID_RE.sub(rb"/ID[<\1><" + digest + rb">]", blinded, count=1)


def _norm_text(s: str) -> str:
    """Normalización para comparar extracciones: algunos ToUnicode mapean
    el espacio como \xa0; el contenido semántico es el mismo."""
    return " ".join(s.replace("\xa0", " ").split())


# ── EXTRACCIÓN: PDF → MODELO ESPACIAL ──────────────────────────────
def extract(path: str) -> Dict:
    doc = pymupdf.open(path)
    model = {
        "source": path,
        "source_sha256": sha256_file(path),
        "pages": [],
    }
    for pno, page in enumerate(doc):
        spans: List[dict] = []
        idx = 0
        for block in page.get_text("rawdict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                line_spans = sorted(line["spans"], key=lambda s: s["bbox"][0])
                for i, s in enumerate(line_spans):
                    origin_x = s["origin"][0]
                    if i + 1 < len(line_spans):
                        available = line_spans[i + 1]["bbox"][0] - origin_x
                    else:
                        available = page.rect.width - RIGHT_MARGIN_PT - origin_x
                    chars = [
                        {"c": ch["c"], "origin_x": ch["origin"][0],
                         "bbox_x0": ch["bbox"][0]}
                        for ch in s.get("chars", [])
                    ]
                    # rawdict no trae "text": se reconstruye desde los chars
                    text = "".join(ch["c"] for ch in s.get("chars", []))
                    spans.append({
                        "id": f"p{pno}s{idx}",
                        "page": pno,
                        "text": text,
                        "bbox": tuple(s["bbox"]),
                        "origin": tuple(s["origin"]),   # baseline start
                        "size": s["size"],
                        "font": s["font"],
                        "color": s["color"],
                        "clearance_pt": max(available, 1.0),
                        "chars": chars,   # geometría por carácter (kerning real)
                    })
                    idx += 1
        model["pages"].append({
            "number": pno,
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "rotation": page.rotation,
            "spans": spans,
        })
    doc.close()
    return model


def all_spans(model: Dict):
    for page in model["pages"]:
        for span in page["spans"]:
            yield span


def span_by_id(model: Dict, span_id: str) -> Optional[dict]:
    for s in all_spans(model):
        if s["id"] == span_id:
            return s
    return None


def find_span_containing(model: Dict, substring: str) -> Optional[dict]:
    for s in all_spans(model):
        if substring in s["text"]:
            return s
    return None


def build_replace_op(model: Dict, old: str, new: str) -> Optional[ReplaceText]:
    span = find_span_containing(model, old)
    if span is None:
        return None
    return ReplaceText(target_span_id=span["id"], old_text=old, new_text=new)


# ── EXPORTACIÓN: ORIGINAL + OPERACIONES = VERSIÓN ──────────────────
def export_version(
    src_path: str,
    ops: List[ReplaceText],
    out_path: str,
    scan_mode: bool = False,
    model_override: Optional[Dict] = None,
) -> Dict:
    """Ejecuta validate → apply → save → verify y devuelve el reporte.

    Reproducible por construcción: siempre abre el original en fresco.
    `model_override` permite inyectar un modelo espacial externo (p.ej.
    el ground truth vectorial simulando un OCR perfecto para Clase B).
    """
    model = model_override if model_override is not None else extract(src_path)
    report = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "original_sha256": sha256_file(src_path),
        "operations": [op.as_dict() for op in ops],
        "results": [],
        "ok": False,
        "output_sha256": None,
        "verify": None,
    }

    # 1 · VALIDAR todo antes de tocar nada
    verdicts: List[tuple] = []
    used_targets: set = set()
    doc = pymupdf.open(src_path)
    fontbooks: Dict[int, FontBook] = {}

    def fontbook_for(pno: int) -> FontBook:
        if pno not in fontbooks:
            fontbooks[pno] = FontBook(doc, doc[pno])
        return fontbooks[pno]

    for op in ops:
        span = span_by_id(model, op.target_span_id) if op.target_span_id else None
        if span is None:
            report["results"].append({"ok": False, "policy": "reject",
                                      "reason": "target_not_found"})
            continue
        if op.target_span_id in used_targets:
            report["results"].append({"ok": False, "policy": "reject",
                                      "reason": "target_already_modified"})
            continue
        fb = fontbook_for(span["page"])
        # FC-007 · contrato de fuente ANTES de medir/escribir: una subset
        # ilegible o sin los glifos del texto nuevo hace que MuPDF
        # sustituya SILENCIOSAMENTE al escribir (Noto Serif en CAL-001).
        # Si la fuente no es utilizable, la identidad tipográfica no es
        # preservable → rechazo honesto, cero bytes escritos.
        fchk = fb.check_font_for_edit(span, op.new_text)
        if not fchk["usable"]:
            report["results"].append({
                "ok": False, "policy": "reject",
                "reason": "font_no_preservable",
                "font_usable": False,
                "font_reason": fchk["reason"],
                "font_missing_glyphs": fchk["missing_glyphs"],
                "font_chain": fchk,
            })
            continue
        verdict = validate_replace(
            op, span, measure=fb.measure, resolve=fb.resolve
        )
        verdicts.append((op, span, verdict))
        vdict = verdict.as_dict()
        vdict["font_usable"] = True
        vdict["font_requested"] = fchk["requested"]
        vdict["font_resolved_name"] = fchk["resolved_name"]
        report["results"].append(vdict)
        if verdict.ok:
            used_targets.add(op.target_span_id)

    if not all(r.get("ok") for r in report["results"]) or not verdicts:
        doc.close()
        return report   # nada se escribe; el original queda intacto

    # 2 · APLICAR (determinista)
    apply_fn = apply_replace_on_scan if scan_mode else apply_replace
    for _op, span, verdict in verdicts:
        page = doc[span["page"]]
        apply_fn(page, fontbooks[span["page"]], span, verdict)

    # 3 · EXPORTAR (determinista: /ID normalizado)
    data = _deterministic_id(doc.tobytes(garbage=3, deflate=True))
    doc.close()
    with open(out_path, "wb") as f:
        f.write(data)
    report["output_sha256"] = sha256_bytes(data)
    report["ok"] = True

    # 4 · VERIFICAR: re-extraer la salida y medir error geométrico
    report["verify"] = verify_output(out_path, model, verdicts,
                                     scan_mode=scan_mode)
    report["ok"] = report["verify"]["ok"]
    return report


def verify_output(out_path: str, original_model: Dict, verdicts,
                  scan_mode: bool = False) -> Dict:
    """El sistema se examina a sí misma: re-abre el PDF exportado,
    localiza la LÍNEA editada y mide desviación real.

    Verificación a nivel de línea (más fuerte que la de span):
      · el contenido concatenado de la línea debe ser EXACTO
        (prefijo intacto + cola nueva);
      · el primer span de la línea debe conservar el origen original
        (el prefijo no se movió — garantía contra la pérdida de kerning);
      · el ancho total debe caber en el hueco.
    """
    out = pymupdf.open(out_path)
    checks = []
    for _op, span, verdict in verdicts:
        page = out[span["page"]]
        expected_text = verdict.span_text_after
        expected_origin = span["origin"]
        expected_x = span["origin"][0]
        if scan_mode:
            # en ruta raster el prefijo son píxeles de la imagen: la banda
            # de texto solo contiene la cola insertada
            expected_text = verdict.tail_text
            expected_x = verdict.insert_x_pt
        # banda de línea: todo span cuya baseline coincida (±2 pt) y que
        # empiece en o después del origen esperado — el extractor puede
        # agrupar prefijo original y cola insertada en "líneas" distintas
        band = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for s in line["spans"]:
                    if (abs(s["origin"][1] - expected_origin[1]) <= 2
                            and s["origin"][0] >= expected_x - 1.0):
                        band.append(s)
        band.sort(key=lambda s: s["origin"][0])
        concat = "".join(s["text"] for s in band)
        if _norm_text(concat) != _norm_text(expected_text) or not band:
            checks.append({
                "span": span["id"], "ok": False,
                "reason": "linea_esperada_no_encontrada",
                "found": _norm_text(concat)[:80],
            })
            continue
        first, last = band[0], band[-1]
        dx = abs(first["origin"][0] - expected_x)
        dy = abs(first["origin"][1] - expected_origin[1])
        width = last["bbox"][2] - first["origin"][0]
        # FC-007 · identidad tipográfica POST-EXPORT: los spans que
        # cubren la región editada deben usar la fuente pedida. PyMuPDF
        # puede FUSIONAR prefijo+cola en un solo span (misma fuente
        # adyacente), así que el criterio es solape con la ventana x del
        # span original — no "span que empieza en insert_x". La
        # sustitución silenciosa de MuPDF (Noto Serif en CAL-001) se
        # detecta AQUÍ aunque todo lo demás pase. UNKNOWN jamás PASS.
        win_x0, win_x1 = expected_x - 1.0, span["bbox"][2] + 0.5
        covered = [s for s in band
                   if min(s["bbox"][2], win_x1) - max(s["bbox"][0], win_x0) > 1.0]
        fonts_observed = sorted({s["font"] for s in covered})
        font_requested = span["font"]
        if not covered:
            font_verification, font_identity_ok = "unknown", False
        elif all(_font_identity_match(font_requested, f) for f in fonts_observed):
            font_verification, font_identity_ok = "verified", True
        else:
            font_verification, font_identity_ok = "mismatch", False
        checks.append({
            "span": span["id"],
            "ok": (dx <= ORIGIN_TOLERANCE_PT and dy <= ORIGIN_TOLERANCE_PT
                   and width <= span["clearance_pt"] + 0.5
                   and font_identity_ok),
            "dx_pt": round(dx, 4),
            "dy_pt": round(dy, 4),
            "width_pt": round(width, 3),
            "clearance_pt": round(span["clearance_pt"], 3),
            "strategy": verdict.strategy,
            "policy": verdict.policy,
            "final_size_pt": round(verdict.final_size_pt, 3),
            "font_used": verdict.font_used,
            "font_fallback": verdict.font_fallback,
            # contrato FC-007: REQUESTED → OUTPUT observado → veredicto
            "font_requested": font_requested,
            "font_identity_ok": font_identity_ok,
            "font_verification": font_verification,
            "fonts_observed_in_output": fonts_observed,
        })
    out.close()
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def replace_flow(src: str, old: str, new: str, out: str, scan_mode: bool = False) -> Dict:
    """Helper de demo/CLI: una operación de reemplazo de principio a fin."""
    model = extract(src)
    op = build_replace_op(model, old, new)
    if op is None:
        return {"ok": False, "error": f"texto no encontrado: {old!r}"}
    return export_version(src, [op], out, scan_mode=scan_mode)
