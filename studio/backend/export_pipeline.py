"""PROMETEO Studio · Export pipeline with verifier authority (CLAUDE-REMEDIATION-001)
────────────────────────────────────────────────────────────────────────────────
Flujo obligatorio de toda exportación de Studio:

    PREPARE → STAGING → VERIFY → PUBLISH (solo si PASS)

Reglas (invariantes del proyecto):
  - UNVERIFIED_PASS == 0: un veredicto PASS solo existe si un verificador real
    se ejecutó sobre el archivo resultante y devolvió PASS.
  - Un archivo que no pasó la verificación nunca se publica ni se descarga.
  - Si el verificador no está disponible o falla, el resultado es REJECT, nunca PASS.
  - Las transacciones mixtas (vectorial + raster) se rechazan explícitamente:
    no se descarta ninguna operación en silencio.
  - Una edición raster que perdería color o una capa de texto de la página se
    rechaza antes de aplicarse (el resultado raster es una página en escala de grises).
"""
from __future__ import annotations

import datetime
import hashlib
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pymupdf

# Vocabulario de veredictos y estados.
VERDICT_PASS = "PASS"
VERDICT_FAILED = "FAILED"
VERDICT_REJECT = "HONEST_REJECT"

STATE_READY = "READY"
STATE_STAGED = "STAGED"
STATE_VERIFIED = "VERIFIED"
STATE_FAILED = "FAILED"
STATE_REJECTED = "HONEST_REJECT"

OP_KIND_VECTOR = "VECTOR_REPLACE_TEXT"
OP_KIND_RASTER = "RASTER_REPLACE_TEXT"

RASTER_VERIFIER_PROFILE = "RASTER_PATCH_VERIFY_V0_1"

# Códigos de error estructurados (contrato con el frontend).
CODE_NO_STAGED = "NO_STAGED_OPERATIONS"
CODE_MIXED = "MIXED_TRANSACTION_UNSUPPORTED"
CODE_RASTER_PREFLIGHT = "RASTER_PREFLIGHT_REJECTED"
CODE_RASTER_COLOR = "RASTER_COLOR_PAGE_UNSUPPORTED"
CODE_RASTER_TEXT_LAYER = "RASTER_TEXT_LAYER_PRESENT"
CODE_RASTER_APPLY = "RASTER_APPLY_FAILED"
CODE_VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"
CODE_VERIFIER_ERROR = "VERIFIER_ERROR"
CODE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
CODE_UNTOUCHED_PAGE_CHANGED = "UNTOUCHED_PAGE_CHANGED"
CODE_EXPORT_FAILED = "EXPORT_FAILED"
CODE_CORE_REJECTED = "CORE_REJECTED"

# Umbrales de la comprobación de color (página RGB renderizada a baja resolución).
COLOR_CHECK_DPI = 50
COLOR_CHROMA_MIN = 24          # diferencia max(r,g,b)-min(r,g,b) que cuenta como color
COLOR_PIXEL_FRACTION_MAX = 0.005
UNTOUCHED_CHECK_DPI = 72


def op_kind(op: Dict[str, Any]) -> str:
    return OP_KIND_RASTER if op.get("type") == OP_KIND_RASTER else OP_KIND_VECTOR


def transaction_kinds(ops: Iterable[Dict[str, Any]]) -> set:
    return {op_kind(op) for op in ops}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def to_jsonable(value: Any) -> Any:
    """Convierte tipos de NumPy, tuplas y dataclasses en tipos JSON nativos."""
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "__dataclass_fields__"):
        import dataclasses
        return to_jsonable(dataclasses.asdict(value))
    return value


def outcome(
    *,
    ok: bool,
    state: str,
    verdict: str,
    code: Optional[str],
    reason: str,
    verifier_executed: bool,
    operations_verified: int = 0,
    details: Optional[List[Dict[str, Any]]] = None,
    verifier_profile: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construye el resultado de exportación con forma estable para la API."""
    verifier_result = {
        "ok": ok,
        "verdict": verdict,
        "status": verdict,
        "reason": reason,
        "code": code,
        "verifier_executed": verifier_executed,
        "verified_globally": ok and verdict == VERDICT_PASS and verifier_executed,
        "operations_verified": operations_verified,
        "verifier_profile": verifier_profile,
        "transaction_id": transaction_id,
        "details": to_jsonable(details or []),
    }
    result: Dict[str, Any] = {
        "ok": ok,
        "transaction_state": state,
        "verifier_result": verifier_result,
        "published": False,
    }
    if not ok:
        result["error"] = reason
        result["error_code"] = code
    return result


def reject(code: str, reason: str, **kw) -> Dict[str, Any]:
    return outcome(ok=False, state=STATE_REJECTED, verdict=VERDICT_REJECT, code=code,
                   reason=reason, verifier_executed=kw.pop("verifier_executed", False), **kw)


def failed(code: str, reason: str, **kw) -> Dict[str, Any]:
    return outcome(ok=False, state=STATE_FAILED, verdict=VERDICT_FAILED, code=code,
                   reason=reason, verifier_executed=kw.pop("verifier_executed", True), **kw)


# ─────────────────────────────────────────────────────────────────────────────
# Comprobaciones de fidelidad de página para la edición raster
# ─────────────────────────────────────────────────────────────────────────────

def page_fidelity_preflight(pdf_bytes: bytes, page_number: int) -> Dict[str, Any]:
    """Comprueba que reconstruir la página como imagen en gris no destruya información.

    La operación raster actual (fase0.raster_operations.apply_raster_transaction)
    reemplaza la página editada por una imagen en escala de grises. Eso es
    aceptable para un escaneo en gris sin capa de texto; no lo es si la página
    tiene color o texto extraíble, porque ambos se perderían sin que el
    verificador físico (que compara en gris) lo detecte.
    """
    reasons: List[str] = []
    metrics: Dict[str, Any] = {}
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_number < 0 or page_number >= len(doc):
            return {"eligible": False, "reasons": ["PAGE_OUT_OF_RANGE"], "metrics": metrics}
        page = doc[page_number]

        text = page.get_text("text").strip()
        metrics["text_layer_chars"] = len(text)
        if text:
            reasons.append(CODE_RASTER_TEXT_LAYER)

        pix = page.get_pixmap(dpi=COLOR_CHECK_DPI, colorspace=pymupdf.csRGB, alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        chroma = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
        fraction = float((chroma >= COLOR_CHROMA_MIN).mean()) if chroma.size else 0.0
        metrics["colored_pixel_fraction"] = round(fraction, 5)
        if fraction > COLOR_PIXEL_FRACTION_MAX:
            reasons.append(CODE_RASTER_COLOR)
    finally:
        doc.close()
    return {"eligible": not reasons, "reasons": reasons, "metrics": metrics}


def untouched_pages_identical(source: bytes, output: bytes, edited_pages: Sequence[int]) -> Dict[str, Any]:
    """Verifica que las páginas no editadas se rendericen idénticas al origen."""
    src = pymupdf.open(stream=source, filetype="pdf")
    out = pymupdf.open(stream=output, filetype="pdf")
    try:
        if len(src) != len(out):
            return {"pass": False, "reason": f"page_count {len(src)} != {len(out)}", "changed_pages": []}
        changed: List[int] = []
        edited = set(edited_pages)
        for idx in range(len(src)):
            if idx in edited:
                continue
            a = src[idx].get_pixmap(dpi=UNTOUCHED_CHECK_DPI, alpha=False)
            b = out[idx].get_pixmap(dpi=UNTOUCHED_CHECK_DPI, alpha=False)
            if (a.width, a.height) != (b.width, b.height) or a.samples != b.samples:
                changed.append(idx)
        return {"pass": not changed, "changed_pages": changed}
    finally:
        src.close()
        out.close()


# ─────────────────────────────────────────────────────────────────────────────
# Verificación raster
# ─────────────────────────────────────────────────────────────────────────────

def load_raster_verifier() -> Optional[Callable[..., Dict[str, Any]]]:
    """Devuelve verify_raster_patch, o None si el verificador no se puede cargar."""
    try:
        from raster_verifier import verify_raster_patch  # type: ignore
    except Exception:
        try:
            from fase0.raster_verifier import verify_raster_patch  # type: ignore
        except Exception:
            return None
    return verify_raster_patch


def semantic_authority_available() -> bool:
    """El verificador raster exige lectura OCR independiente (doble autoridad)."""
    try:
        from ocr_provider import is_tesseract_available  # type: ignore
    except Exception:
        try:
            from fase0.ocr_provider import is_tesseract_available  # type: ignore
        except Exception:
            return False
    try:
        return bool(is_tesseract_available())
    except Exception:
        return False


def run_raster_transaction(
    source_bytes: bytes,
    raster_ops: Sequence[Any],
    *,
    apply_fn: Callable[[bytes, list], Tuple[bytes, List[Dict[str, Any]]]],
    verify_fn: Optional[Callable[..., Dict[str, Any]]],
    semantic_available: bool,
) -> Tuple[Dict[str, Any], Optional[bytes]]:
    """Aplica y verifica cada parche raster en secuencia.

    Cada operación se aplica sobre la salida verificada de la anterior y se
    verifica contra ella con verify_raster_patch (contención física, anillo de
    borde, reconstrucción de fondo y lectura OCR independiente). Al final, las
    páginas no editadas deben renderizarse idénticas al origen.

    Devuelve (outcome, bytes_finales). bytes_finales solo es distinto de None
    cuando el resultado es PASS.
    """
    if verify_fn is None:
        return reject(CODE_VERIFIER_UNAVAILABLE,
                      "El verificador raster no está disponible: la edición se rechaza en lugar de aprobarse sin verificar.",
                      verifier_profile=RASTER_VERIFIER_PROFILE), None
    if not semantic_available:
        return reject(CODE_VERIFIER_UNAVAILABLE,
                      "La lectura OCR independiente que exige el verificador raster no está disponible (Tesseract).",
                      verifier_profile=RASTER_VERIFIER_PROFILE), None

    for op in raster_ops:
        fidelity = page_fidelity_preflight(source_bytes, op.page)
        if not fidelity["eligible"]:
            code = fidelity["reasons"][0]
            return reject(code,
                          "La página no admite edición raster sin perder información: "
                          + ", ".join(fidelity["reasons"]),
                          details=[{"page": op.page, **fidelity}],
                          verifier_profile=RASTER_VERIFIER_PROFILE), None

    current = source_bytes
    reports: List[Dict[str, Any]] = []
    for op in raster_ops:
        try:
            out_bytes, evidence = apply_fn(current, [op])
        except (ValueError, IndexError) as e:
            return reject(CODE_RASTER_PREFLIGHT, f"Preflight raster rechazado: {e}",
                          details=reports, verifier_profile=RASTER_VERIFIER_PROFILE), None
        except Exception as e:
            return reject(CODE_RASTER_APPLY, f"No se pudo aplicar el parche raster: {type(e).__name__}",
                          details=reports, verifier_profile=RASTER_VERIFIER_PROFILE), None

        try:
            report = verify_fn(current, out_bytes, op)
        except Exception as e:
            return reject(CODE_VERIFIER_ERROR,
                          f"El verificador raster falló durante la verificación ({type(e).__name__}); no se aprueba nada.",
                          details=reports, verifier_profile=RASTER_VERIFIER_PROFILE), None

        if not isinstance(report, dict) or report.get("status") not in (VERDICT_PASS, VERDICT_FAILED):
            return reject(CODE_VERIFIER_ERROR, "El verificador raster devolvió un resultado no interpretable.",
                          details=reports, verifier_profile=RASTER_VERIFIER_PROFILE), None

        reports.append({
            "observation_id": getattr(op, "observation_id", None),
            "page": op.page,
            "status": report["status"],
            "physical_pass": report.get("physical_pass"),
            "semantic_pass": report.get("semantic_pass"),
            "reasons": report.get("reasons", []),
            "metrics": report.get("metrics", {}),
            "evidence": report.get("evidence", {}),
            "patch_evidence": evidence,
        })
        if report["status"] != VERDICT_PASS:
            return failed(CODE_VERIFICATION_FAILED,
                          "El verificador raster no aprobó el parche: " + ", ".join(report.get("reasons", [])),
                          operations_verified=len(reports) - 1, details=reports,
                          verifier_profile=RASTER_VERIFIER_PROFILE), None
        current = out_bytes

    edited_pages = sorted({op.page for op in raster_ops})
    untouched = untouched_pages_identical(source_bytes, current, edited_pages)
    if not untouched["pass"]:
        return failed(CODE_UNTOUCHED_PAGE_CHANGED,
                      f"Páginas no editadas cambiaron: {untouched.get('changed_pages') or untouched.get('reason')}",
                      operations_verified=len(reports), details=reports + [{"untouched_pages": untouched}],
                      verifier_profile=RASTER_VERIFIER_PROFILE), None

    ok = outcome(ok=True, state=STATE_VERIFIED, verdict=VERDICT_PASS, code=None,
                 reason="Todos los parches pasaron el verificador raster y las páginas no editadas son idénticas.",
                 verifier_executed=True, operations_verified=len(reports),
                 details=reports + [{"untouched_pages": untouched}],
                 verifier_profile=RASTER_VERIFIER_PROFILE)
    return ok, current


# ─────────────────────────────────────────────────────────────────────────────
# Staging y publicación
# ─────────────────────────────────────────────────────────────────────────────

def publish(staging_path: str, verified_dir: str, filename: str) -> Dict[str, Any]:
    """Mueve atómicamente un archivo verificado del área de staging al área publicada."""
    os.makedirs(verified_dir, mode=0o700, exist_ok=True)
    digest_before = sha256_path(staging_path)
    final_path = os.path.join(verified_dir, filename)
    os.replace(staging_path, final_path)
    digest_after = sha256_path(final_path)
    if digest_before != digest_after:
        os.remove(final_path)
        raise RuntimeError("El archivo cambió durante la publicación.")
    return {"path": final_path, "filename": filename, "sha256": digest_after, "published_at": utc_now()}


def discard(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
