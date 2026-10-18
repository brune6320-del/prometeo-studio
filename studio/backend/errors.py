"""PROMETEO Studio · Errores estructurados de la API (CLAUDE-REMEDIATION-001 · PA-006/007)
──────────────────────────────────────────────────────────────────────────────────────
Toda respuesta de error tiene la misma forma:

    {"ok": false,
     "error": {"code", "stage", "message", "retryable", "details"},
     "detail": message}          # compatibilidad con clientes anteriores

`code` es estable y lo interpreta el frontend; `message` es texto para personas,
sin trazas internas ni secretos.
"""
from __future__ import annotations

import logging
import re
import traceback
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse

log = logging.getLogger("prometeo.api")

# Etapas del flujo documental.
STAGE_API = "API"
STAGE_AUTH = "AUTH"
STAGE_DOCUMENT_LOAD = "DOCUMENT_LOAD"
STAGE_RENDER = "RENDER"
STAGE_OCR = "OCR"
STAGE_STAGING = "STAGING"
STAGE_VERIFICATION = "VERIFICATION"
STAGE_EXPORT = "EXPORT"
STAGE_SESSION = "SESSION"
STAGE_WORKSPACE = "WORKSPACE"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, stage: str = STAGE_API,
                 retryable: bool = False, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.stage = stage
        self.retryable = retryable
        self.details = details or {}


def envelope(code: str, message: str, stage: str = STAGE_API, retryable: bool = False,
             details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "stage": stage, "message": message,
                  "retryable": retryable, "details": details or {}},
        "detail": message,
    }


def error_response(status: int, code: str, message: str, stage: str = STAGE_API,
                   retryable: bool = False, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=envelope(code, message, stage, retryable, details))


_STAGE_BY_PATH = [
    (re.compile(r"/api/sessions/(upload|open_sample|open_file_path)$"), STAGE_DOCUMENT_LOAD),
    (re.compile(r"/page/\d+(/render)?$"), STAGE_RENDER),
    (re.compile(r"/(ocr|ocr_search)(/\d+)?$|/page/\d+/ocr$"), STAGE_OCR),
    (re.compile(r"/(stage_edit|stage_raster_edit|staged/.+|transaction)$"), STAGE_STAGING),
    (re.compile(r"/verify_and_export$"), STAGE_VERIFICATION),
    (re.compile(r"/(download|manifest|audit_export)$"), STAGE_EXPORT),
]

_CODE_BY_STAGE = {
    STAGE_DOCUMENT_LOAD: "DOCUMENT_LOAD_FAILED",
    STAGE_RENDER: "RENDER_FAILED",
    STAGE_OCR: "OCR_FAILED",
    STAGE_STAGING: "STAGING_FAILED",
    STAGE_VERIFICATION: "VERIFICATION_FAILED",
    STAGE_EXPORT: "EXPORT_FAILED",
}


def stage_for_path(path: str) -> str:
    for rx, stage in _STAGE_BY_PATH:
        if rx.search(path):
            return stage
    return STAGE_API


def code_for_http(status: int, path: str) -> str:
    stage = stage_for_path(path)
    if status == 401:
        return "AUTHENTICATION_FAILED"
    if status == 404 and "/api/sessions/" in path:
        return "SESSION_NOT_FOUND" if stage in (STAGE_API, STAGE_SESSION) else _CODE_BY_STAGE.get(stage, "NOT_FOUND")
    if status == 409:
        return "OUTPUT_NOT_VERIFIED" if stage == STAGE_EXPORT else "CONFLICT"
    if status == 413:
        return "UPLOAD_TOO_LARGE"
    if status == 422:
        return "INVALID_REQUEST"
    if status == 503:
        return "SERVICE_UNAVAILABLE"
    return _CODE_BY_STAGE.get(stage, "REQUEST_FAILED" if status < 500 else "INTERNAL_ERROR")


_PDF_GATE_MESSAGES = {
    "DOCUMENT_UNREADABLE": "El archivo no es un PDF legible o está dañado.",
    "DOCUMENT_ENCRYPTED": "El PDF está protegido con contraseña o cifrado.",
    "PDF_PARSE_TIMEOUT": "El PDF tardó demasiado en analizarse y se descartó para no bloquear PROMETEO.",
    "PDF_TOO_COMPLEX": "El PDF supera los límites de análisis (páginas o memoria) y se descartó.",
    "PDF_REJECTED_UNSAFE": "El PDF hizo fallar el analizador y se descartó sin abrirlo en el motor.",
}


def pdf_rejected_error(result) -> ApiError:
    """Rechazo del filtro de PDFs (CAMP-002 · F5). El original de la persona no se modificó."""
    code = result.code or "DOCUMENT_UNREADABLE"
    # Mismo estado que el resto del motor para el mismo código: 400 para archivos ilegibles o
    # cifrados (igual que la comprobación previa y classify_document_error); 422 para lo que el
    # filtro descarta por sus límites. La interfaz se guía por el código, no por el estado.
    status = 400 if code in ("DOCUMENT_UNREADABLE", "DOCUMENT_ENCRYPTED") else 422
    details = {"reason": (result.reason or "")[:300], "gate_seconds": result.seconds, "peak_rss_mb": result.peak_rss_mb}
    for key in ("signal", "limit_s", "sandboxed"):
        if key in result.details:
            details[key] = result.details[key]
    return ApiError(status, code, _PDF_GATE_MESSAGES.get(code, "No se pudo abrir el documento."), STAGE_DOCUMENT_LOAD,
                    retryable=False, details=details)


def classify_document_error(exc: BaseException) -> ApiError:
    """Traduce errores al abrir un PDF a códigos comprensibles."""
    msg = str(exc)
    low = msg.lower()
    if "password" in low or "encrypt" in low or "needs_pass" in low:
        return ApiError(400, "DOCUMENT_ENCRYPTED", "El PDF está protegido con contraseña o cifrado.",
                        STAGE_DOCUMENT_LOAD)
    if any(k in low for k in ("cannot open", "broken", "damaged", "corrupt", "syntax", "not a pdf",
                              "failed to open", "filedataerror", "format error", "no objects")):
        return ApiError(400, "DOCUMENT_UNREADABLE", "El archivo no es un PDF legible o está dañado.",
                        STAGE_DOCUMENT_LOAD, details={"reason": msg[:300]})
    return ApiError(500, "DOCUMENT_LOAD_FAILED", "No se pudo abrir el documento.", STAGE_DOCUMENT_LOAD,
                    retryable=False, details={"reason": f"{type(exc).__name__}: {msg[:300]}"})


class ErrorEnvelopeMiddleware:
    """ASGI: convierte excepciones no controladas en un 500 estructurado.

    Se instala DENTRO de CORS para que la respuesta conserve las cabeceras CORS:
    sin ellas, WebKit oculta el error detrás de un genérico "Load failed".
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:  # noqa: BLE001
            path = scope.get("path", "")
            log.error("Unhandled error on %s %s: %s\n%s", scope.get("method"), path,
                      type(exc).__name__, traceback.format_exc())
            if started:
                raise
            stage = stage_for_path(path)
            response = error_response(500, _CODE_BY_STAGE.get(stage, "INTERNAL_ERROR"),
                                      "Error interno del motor de PROMETEO.", stage, retryable=True,
                                      details={"exception": type(exc).__name__})
            await response(scope, receive, send)
