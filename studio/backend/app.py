"""PROMETEO Studio · FastAPI Application & Decoupled Backend Service
───────────────────────────────────────────────────────────────────
API REST local de Studio (frontend web y aplicación de escritorio Tauri):
- Ingesta segura de documentos en un workspace fuera del paquete de la app.
- Navegación por niveles (DocGraph), renderizado y capa OCR.
- Transacciones con verificación física: solo se publica lo que el verificador aprueba.
- Errores estructurados {code, stage, message, retryable, details}.

Orden de middlewares (de fuera hacia dentro):
    CORS → ErrorEnvelope → AccessLog → Auth → rutas
CORS va por fuera para que TODA respuesta (401, 500 incluidos) lleve sus cabeceras;
sin ellas WebKit reduce cualquier error a "Load failed".
"""

import asyncio
import hmac
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import pymupdf
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from . import errors as E
from . import pdf_gate
from .adapter import StudioAgentBridge
from .session import AUTHORIZED_SAMPLES, StudioSessionManager, WorkspaceUnavailableError
from .version import API_VERSION, PROMETEO_VERSION

RUNTIME_MODE = os.environ.get("PROMETEO_RUNTIME_MODE", "WEB_SERVER")
DESKTOP = RUNTIME_MODE == "DESKTOP_SIDECAR"

MAX_UPLOAD_BYTES = int(os.environ.get("PROMETEO_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
RENDER_DPI_MIN, RENDER_DPI_MAX = 36, 300

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("prometeo.api")

app = FastAPI(
    title="PROMETEO Studio API",
    version=PROMETEO_VERSION,
    description="Backend local de PROMETEO Studio.",
    # En la app de escritorio no se expone documentación interactiva.
    docs_url=None if DESKTOP else "/docs",
    redoc_url=None,
    openapi_url=None if DESKTOP else "/openapi.json",
)


# ─────────────────────────────────────────────────────────────────────────────
# MIDDLEWARES
# ─────────────────────────────────────────────────────────────────────────────

PUBLIC_PATHS = {"/api/health"} | (set() if DESKTOP else {"/docs", "/openapi.json"})


class DesktopAuthMiddleware(BaseHTTPMiddleware):
    """Token de sesión local. En modo escritorio sin token configurado, falla cerrado."""

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        expected = os.environ.get("PROMETEO_AUTH_TOKEN", "")
        if not expected:
            if DESKTOP:
                return E.error_response(401, "AUTHENTICATION_FAILED",
                                        "El motor no tiene token de sesión configurado.", E.STAGE_AUTH)
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        bearer = auth[7:].strip() if auth.startswith("Bearer ") else ""
        header = request.headers.get("X-Prometeo-Token", "")
        if not (hmac.compare_digest(bearer, expected) or hmac.compare_digest(header, expected)):
            return E.error_response(401, "AUTHENTICATION_FAILED",
                                    "Token de sesión inválido o ausente.", E.STAGE_AUTH)
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Registro mínimo: método, ruta (sin query ni cabeceras), estado y duración."""

    async def dispatch(self, request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        log.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - t0) * 1000)
        return response


if DESKTOP:
    allowed_origins = ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
    extra = os.environ.get("PROMETEO_DEV_ORIGINS", "")
    allowed_origins += [o.strip() for o in extra.split(",") if o.strip()]
else:
    allowed_origins = ["*"]

# add_middleware: el último añadido queda por fuera.
app.add_middleware(DesktopAuthMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(E.ErrorEnvelopeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "X-Prometeo-Token", "Content-Type"],
    expose_headers=["Content-Disposition", "X-Prometeo-Output-Sha256"],
)


@app.exception_handler(E.ApiError)
async def _api_error(request, exc: E.ApiError):
    return E.error_response(exc.status, exc.code, exc.message, exc.stage, exc.retryable, exc.details)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request, exc: StarletteHTTPException):
    path = request.url.path
    detail = exc.detail
    if isinstance(detail, dict):
        return E.error_response(exc.status_code, detail.get("code") or E.code_for_http(exc.status_code, path),
                                detail.get("message", ""), detail.get("stage") or E.stage_for_path(path),
                                bool(detail.get("retryable", False)), detail.get("details"))
    return E.error_response(exc.status_code, E.code_for_http(exc.status_code, path), str(detail),
                            E.stage_for_path(path), retryable=exc.status_code >= 500)


@app.exception_handler(RequestValidationError)
async def _validation_error(request, exc: RequestValidationError):
    return E.error_response(422, "INVALID_REQUEST", "La petición no tiene el formato esperado.",
                            E.stage_for_path(request.url.path), details={"errors": exc.errors()[:5]})


# ─────────────────────────────────────────────────────────────────────────────
# WORKSPACE Y SESIONES
# ─────────────────────────────────────────────────────────────────────────────

SESSION_MANAGER: Optional[StudioSessionManager] = None
WORKSPACE_ERROR: Optional[str] = None
try:
    SESSION_MANAGER = StudioSessionManager()
    log.info("workspace ready (instance %s)", SESSION_MANAGER.instance_id)
except WorkspaceUnavailableError as e:
    # El servicio arranca igualmente y lo informa en /api/health: nunca muere al importar.
    WORKSPACE_ERROR = str(e)
    log.error("workspace unavailable: %s", WORKSPACE_ERROR)

AGENT_BRIDGES: Dict[str, StudioAgentBridge] = {}


def _manager() -> StudioSessionManager:
    if SESSION_MANAGER is None:
        raise E.ApiError(503, "WORKSPACE_UNAVAILABLE",
                         "PROMETEO no encontró una carpeta escribible para trabajar con documentos.",
                         E.STAGE_WORKSPACE, retryable=False, details={"reason": WORKSPACE_ERROR})
    return SESSION_MANAGER


def shutdown_cleanup() -> None:
    """Lo llama el runner antes de salir: borra la carpeta de esta instancia y mata los analizadores
    de PDF que sigan vivos."""
    try:
        pdf_gate.kill_live_workers()
    except Exception:
        pass
    if SESSION_MANAGER is not None:
        try:
            SESSION_MANAGER.shutdown()
        except Exception:
            pass


def _get_active_session(session_id: str):
    sess = _manager().get_session(session_id)
    if not sess:
        raise E.ApiError(404, "SESSION_NOT_FOUND", "La sesión no existe o ya se cerró.", E.STAGE_SESSION,
                         details={"session_id": session_id})
    return sess


def _session_payload(session) -> Dict[str, Any]:
    return {
        "ok": True,
        "session_id": session.session_id,
        "document_id": session.document_id,
        "filename": session.source_filename,
        "sha256": session.source_sha256,
        "summary": session.get_summary(),
    }


def _open_bytes(content: bytes, filename: str):
    if not content:
        raise E.ApiError(400, "DOCUMENT_EMPTY", "El archivo está vacío.", E.STAGE_DOCUMENT_LOAD)
    if b"%PDF-" not in content[:1024]:
        raise E.ApiError(400, "DOCUMENT_UNREADABLE", "El archivo no es un PDF.", E.STAGE_DOCUMENT_LOAD)
    try:
        session = _manager().create_session_from_upload(content, filename)
    except E.ApiError:
        raise
    except pdf_gate.PdfRejected as rej:
        raise E.pdf_rejected_error(rej.result)
    except Exception as e:
        raise E.classify_document_error(e)
    AGENT_BRIDGES[session.session_id] = StudioAgentBridge(session)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

class OpenSampleRequest(BaseModel):
    sample_key: str = Field(..., description="Clave de la muestra autorizada")


class OpenFilePathRequest(BaseModel):
    file_path: str = Field(..., description="Ruta absoluta del archivo PDF a abrir")


class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = None


class StageEditRequest(BaseModel):
    new_text: str
    node_id: Optional[str] = None
    target_id: Optional[str] = None


class StageRasterEditRequest(BaseModel):
    page: int
    observation_id: str
    new_text: str
    font_family: Optional[str] = "helv"
    font_size_pt: Optional[float] = None


class VerifyExportRequest(BaseModel):
    output_filename: Optional[str] = None


class AgentChatRequest(BaseModel):
    message: str


class MirarOjosReferente(BaseModel):
    id: str = ""
    nombre: str = ""
    por_que: str = ""
    archivo_origen: str = ""
    etiquetas: List[str] = Field(default_factory=list)
    url: str = ""


class MirarOjosRequest(BaseModel):
    proyecto: str = ""
    ojos: str = ""
    ojos_descripcion: str = ""
    preguntas: List[str] = Field(default_factory=list)
    referentes: List[MirarOjosReferente] = Field(default_factory=list)


SAMPLE_DESCRIPTIONS = {
    "case_a": "Contrato de servicios (texto nativo)",
    "case_b_scan": "Documento escaneado (imagen)",
    "form_56": "Formulario real (texto nativo)",
    "doc_73p": "Documento largo real (texto nativo)",
}


# ─────────────────────────────────────────────────────────────────────────────
# SALUD Y DESCUBRIMIENTO
# ─────────────────────────────────────────────────────────────────────────────

_OCR_AVAILABLE: Optional[bool] = None


def _ocr_available() -> bool:
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is None:
        try:
            from fase0.ocr_provider import is_tesseract_available
            _OCR_AVAILABLE = bool(is_tesseract_available())
        except Exception:
            _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


@app.get("/api/health")
def health_check():
    ready = SESSION_MANAGER is not None
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "service": "prometeo_studio_backend",
        "version": PROMETEO_VERSION,
        "prometeo_version": PROMETEO_VERSION,
        "api_version": API_VERSION,
        "docgraph_version": "0.3",
        "runtime_mode": RUNTIME_MODE,
        "pid": os.getpid(),
        "workspace": {
            "ok": ready,
            "source": None if not ready else ("env" if os.environ.get("PROMETEO_WORKSPACE") else "auto"),
            "error_code": None if ready else "WORKSPACE_UNAVAILABLE",
        },
        "ocr_available": _ocr_available(),
        "verifier_profiles": ["VERIFIER2_VECTOR_TEXT", "RASTER_PATCH_VERIFY_V0_1"],
        "render_engines": ["PYMUPDF_FONTBOOK_BASELINE", "PIL_FREETYPE", "NATIVE_VECTOR"],
    }


@app.get("/api/samples")
def list_samples():
    """Muestras incluidas en esta instalación, con descripción y número de páginas."""
    samples = []
    for key, path in AUTHORIZED_SAMPLES.items():
        if not os.path.isfile(path):
            continue
        try:
            with pymupdf.open(path) as doc:
                pages = len(doc)
        except Exception:
            continue
        label = SAMPLE_DESCRIPTIONS.get(key, key)
        samples.append({
            "key": key,
            "filename": os.path.basename(path),
            "pages": pages,
            "description": f"{label} · {pages} {'página' if pages == 1 else 'páginas'}",
        })
    return {"ok": True, "samples": samples}


# ─────────────────────────────────────────────────────────────────────────────
# GESTIÓN DE SESIONES
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/open_sample")
def open_sample(req: OpenSampleRequest):
    path = AUTHORIZED_SAMPLES.get(req.sample_key)
    if path is None:
        raise E.ApiError(400, "SAMPLE_UNKNOWN", f"Muestra desconocida: {req.sample_key}", E.STAGE_DOCUMENT_LOAD)
    if not os.path.isfile(path):
        raise E.ApiError(404, "SAMPLE_NOT_INSTALLED", "Esa muestra no está incluida en esta instalación.",
                         E.STAGE_DOCUMENT_LOAD)
    with open(path, "rb") as f:
        session = _open_bytes(f.read(), os.path.basename(path))
    return _session_payload(session)


@app.post("/api/sessions/open_file_path")
def open_file_path(req: OpenFilePathRequest):
    """Abre un PDF local por ruta (copia de trabajo; el original nunca se modifica)."""
    abs_path = os.path.realpath(os.path.abspath(req.file_path))
    if not abs_path.lower().endswith(".pdf"):
        raise E.ApiError(400, "DOCUMENT_UNREADABLE", "El archivo debe tener extensión .pdf", E.STAGE_DOCUMENT_LOAD)
    if not os.path.isfile(abs_path):
        raise E.ApiError(404, "DOCUMENT_NOT_FOUND", "El archivo especificado no existe.", E.STAGE_DOCUMENT_LOAD)
    if os.path.getsize(abs_path) > MAX_UPLOAD_BYTES:
        raise E.ApiError(413, "UPLOAD_TOO_LARGE", "El archivo supera el tamaño máximo admitido.",
                         E.STAGE_DOCUMENT_LOAD, details={"max_bytes": MAX_UPLOAD_BYTES})
    with open(abs_path, "rb") as f:
        session = _open_bytes(f.read(), os.path.basename(abs_path))
    payload = _session_payload(session)
    payload["message"] = f"Documento {os.path.basename(abs_path)} abierto sin modificar el original."
    return payload


@app.post("/api/sessions/upload")
async def upload_document(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise E.ApiError(400, "DOCUMENT_UNREADABLE", "Solo se admiten archivos PDF.", E.STAGE_DOCUMENT_LOAD)
    chunks, total = [], 0
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise E.ApiError(413, "UPLOAD_TOO_LARGE", "El archivo supera el tamaño máximo admitido.",
                             E.STAGE_DOCUMENT_LOAD, details={"max_bytes": MAX_UPLOAD_BYTES})
        chunks.append(chunk)
    # El filtro y la apertura bloquean (segundos): fuera del bucle de eventos, para que el motor siga
    # respondiendo a otras peticiones mientras tanto.
    session = await run_in_threadpool(_open_bytes, b"".join(chunks), file.filename)
    return _session_payload(session)


@app.get("/api/sessions/{session_id}/summary")
def get_session_summary(session_id: str):
    sess = _get_active_session(session_id)
    return {"ok": True, "summary": sess.get_summary()}


@app.get("/api/sessions/{session_id}/outline")
def get_session_outline(
    session_id: str,
    pages: Optional[str] = Query(None, description="Páginas separadas por comas (ej. 0,1)"),
    types: Optional[str] = Query(None, description="Tipos separados por comas (ej. TEXT,GROUP)"),
    max_depth: Optional[int] = Query(None, description="Profundidad máxima del árbol"),
    include_vectors: bool = Query(False, description="Incluir objetos vectoriales"),
):
    sess = _get_active_session(session_id)
    try:
        page_list = [int(p.strip()) for p in pages.split(",")] if pages else None
    except ValueError:
        raise E.ApiError(422, "INVALID_REQUEST", "El parámetro 'pages' debe ser una lista de números.")
    type_list = [t.strip().upper() for t in types.split(",")] if types else None
    outline = sess.get_outline(pages=page_list, types=type_list, max_depth=max_depth,
                               include_vectors=include_vectors)
    return {"ok": True, "outline": outline}


@app.get("/api/sessions/{session_id}/node/{node_id}")
@app.get("/api/sessions/{session_id}/nodes/{node_id}")
def inspect_session_node(session_id: str, node_id: str):
    sess = _get_active_session(session_id)
    node_data = sess.inspect_node(node_id)
    if not node_data:
        raise E.ApiError(404, "NODE_NOT_FOUND", f"Nodo no encontrado: {node_id}")
    return {"ok": True, "node": node_data}


@app.get("/api/sessions/{session_id}/node/{node_id}/neighbors")
@app.get("/api/sessions/{session_id}/nodes/{node_id}/neighbors")
def get_session_node_neighbors(session_id: str, node_id: str, radius: float = Query(36.0)):
    sess = _get_active_session(session_id)
    neighbors = sess.get_neighbors(node_id, spatial_radius=radius)
    if not neighbors:
        raise E.ApiError(404, "NODE_NOT_FOUND", f"Nodo no encontrado: {node_id}")
    return {"ok": True, "neighbors": neighbors}


@app.get("/api/sessions/{session_id}/nodes")
@app.get("/api/sessions/{session_id}/query")
def query_session_nodes(session_id: str, page: Optional[int] = None, node_type: Optional[str] = None,
                        text: Optional[str] = None):
    sess = _get_active_session(session_id)
    res = sess.query_nodes(page=page, node_type=node_type, text=text, with_meta=True)
    return {"ok": True, "count": len(res["nodes"]), "total": res["total"], "truncated": res["truncated"],
            "nodes": res["nodes"]}


@app.get("/api/sessions/{session_id}/page/{page_number}")
@app.get("/api/sessions/{session_id}/page/{page_number}/render")
def render_session_page(session_id: str, page_number: int, dpi: int = Query(150)):
    sess = _get_active_session(session_id)
    dpi = max(RENDER_DPI_MIN, min(RENDER_DPI_MAX, dpi))
    try:
        return {"ok": True, "page": sess.render_page(page_number=page_number, dpi=dpi)}
    except ValueError as e:
        raise E.ApiError(400, "PAGE_OUT_OF_RANGE", str(e), E.STAGE_RENDER)
    except Exception as e:
        raise E.ApiError(500, "RENDER_FAILED", "No se pudo renderizar la página.", E.STAGE_RENDER,
                         retryable=True, details={"exception": type(e).__name__})


@app.get("/api/sessions/{session_id}/verified/page/{page_number}/render")
def render_verified_page(session_id: str, page_number: int, dpi: int = Query(150)):
    """Página de la copia verificada publicada (la vista Comparar nunca muestra la copia de trabajo)."""
    sess = _get_active_session(session_id)
    dpi = max(RENDER_DPI_MIN, min(RENDER_DPI_MAX, dpi))
    try:
        data = sess.render_verified_page(page_number=page_number, dpi=dpi)
    except ValueError as e:
        raise E.ApiError(400, "PAGE_OUT_OF_RANGE", str(e), E.STAGE_RENDER)
    if data is None:
        raise E.ApiError(409, "OUTPUT_NOT_VERIFIED", "No hay una copia verificada vigente que mostrar.", E.STAGE_RENDER)
    return {"ok": True, "page": data}


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA, OCR Y PREPARACIÓN DE CAMBIOS
# ─────────────────────────────────────────────────────────────────────────────

def _domain_result(res: Dict[str, Any], status: int = 400, default_code: str = "STAGING_REJECTED",
                   stage: str = E.STAGE_STAGING) -> Dict[str, Any]:
    if not res.get("ok"):
        raise E.ApiError(status, res.get("error_code") or default_code, res.get("error") or "Operación rechazada.",
                         stage, details={k: res[k] for k in ("reasons", "raster_class") if k in res})
    return res


@app.post("/api/sessions/{session_id}/search")
def search_in_document(session_id: str, req: SearchRequest):
    return _get_active_session(session_id).search_text(query=req.query, page=req.page)


@app.get("/api/sessions/{session_id}/ocr/{page_number}")
@app.get("/api/sessions/{session_id}/page/{page_number}/ocr")
def get_session_ocr_layer(session_id: str, page_number: int):
    res = _get_active_session(session_id).get_ocr_layer(page_number)
    return _domain_result(res, status=502 if res.get("error_code") != "OCR_UNAVAILABLE" else 503,
                          default_code="OCR_FAILED", stage=E.STAGE_OCR)


@app.post("/api/sessions/{session_id}/ocr_search")
def search_ocr_in_document(session_id: str, req: SearchRequest):
    return _get_active_session(session_id).search_ocr(query=req.query, page_number=req.page)


@app.post("/api/sessions/{session_id}/stage_edit")
def stage_text_edit(session_id: str, req: StageEditRequest):
    sess = _get_active_session(session_id)
    return _domain_result(sess.stage_edit(new_text=req.new_text, node_id=req.node_id, target_id=req.target_id))


@app.get("/api/sessions/{session_id}/raster_safety/{page}/{observation_id}")
def get_raster_safety(session_id: str, page: int, observation_id: str):
    sess = _get_active_session(session_id)
    return _domain_result(sess.get_raster_safety(page_number=page, observation_id=observation_id),
                          default_code="RASTER_SAFETY_FAILED")


@app.get("/api/sessions/{session_id}/raster_patch_preview/{page}/{observation_id}")
def get_raster_patch_preview(session_id: str, page: int, observation_id: str,
                             new_text: Optional[str] = Query(None)):
    sess = _get_active_session(session_id)
    return _domain_result(sess.get_raster_patch_preview(page_number=page, observation_id=observation_id,
                                                        new_text=new_text), default_code="RASTER_PREVIEW_FAILED")


@app.post("/api/sessions/{session_id}/stage_raster_edit")
def stage_raster_edit(session_id: str, req: StageRasterEditRequest):
    sess = _get_active_session(session_id)
    return _domain_result(sess.stage_raster_edit(page_number=req.page, observation_id=req.observation_id,
                                                 new_text=req.new_text, font_family=req.font_family or "helv",
                                                 font_size_pt=req.font_size_pt))


@app.get("/api/sessions/{session_id}/transaction")
def get_transaction_tray(session_id: str):
    sess = _get_active_session(session_id)
    return {
        "ok": True,
        "transaction_state": sess.transaction_state,
        "staged_operations": sess.staged_operations_public(),
        "count": len(sess.staged_operations),
    }


@app.delete("/api/sessions/{session_id}/staged/{op_id}")
def remove_staged_op(session_id: str, op_id: str):
    sess = _get_active_session(session_id)
    return _domain_result(sess.remove_staged_operation(op_id), status=404)


@app.delete("/api/sessions/{session_id}/transaction")
def clear_transaction_tray(session_id: str):
    return _get_active_session(session_id).clear_transaction()


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTACIÓN Y VERIFICACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/verify_and_export")
def verify_and_export_session(session_id: str, req: VerifyExportRequest):
    """Resultado de dominio: 200 con ok=false cuando el verificador rechaza o falla."""
    return _get_active_session(session_id).verify_and_export(output_filename=req.output_filename)


@app.get("/api/sessions/{session_id}/diff")
def get_session_diff(session_id: str):
    return {"ok": True, "diff": _get_active_session(session_id).get_diff()}


@app.get("/api/sessions/{session_id}/download")
def download_verified_output(session_id: str):
    sess = _get_active_session(session_id)
    # PA-003: solo se entrega una salida publicada tras un PASS real del verificador,
    # y solo si el archivo en disco conserva el hash registrado al publicarse.
    rec = sess.get_verified_output()
    if rec is None:
        raise E.ApiError(409, "OUTPUT_NOT_VERIFIED",
                         "No hay una copia verificada para descargar: la última transacción no pasó "
                         "la verificación o cambió después.", E.STAGE_EXPORT)
    return FileResponse(rec["path"], filename=rec["filename"], media_type="application/pdf",
                        headers={"X-Prometeo-Output-Sha256": rec["sha256"]})


def _save_dir() -> str:
    env = os.environ.get("PROMETEO_SAVE_DIR")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), "Downloads", "PROMETEO")


@app.post("/api/sessions/{session_id}/save_verified")
def save_verified_copy(session_id: str):
    """Guarda la copia verificada en Descargas/PROMETEO (nunca sobrescribe) y devuelve la ruta."""
    res = _get_active_session(session_id).save_verified_copy(_save_dir())
    status = 409 if res.get("error_code") == "OUTPUT_NOT_VERIFIED" else 500
    return _domain_result(res, status=status, default_code="SAVE_FAILED", stage=E.STAGE_EXPORT)


@app.post("/api/sessions/{session_id}/reveal_saved")
def reveal_saved_copy(session_id: str):
    """Muestra en Finder el último archivo guardado por ESTA sesión (nunca una ruta arbitraria)."""
    sess = _get_active_session(session_id)
    if not sess.saved_outputs or not os.path.isfile(sess.saved_outputs[-1]):
        raise E.ApiError(404, "NOTHING_SAVED", "Todavía no se guardó ninguna copia en esta sesión.", E.STAGE_EXPORT)
    path = sess.saved_outputs[-1]
    if sys.platform == "darwin":
        import subprocess
        subprocess.run(["/usr/bin/open", "-R", path], check=False, timeout=10)
        return {"ok": True, "path": path}
    return {"ok": False, "path": path, "error": "Mostrar en el explorador solo está disponible en macOS."}


@app.get("/api/sessions/{session_id}/manifest")
def get_session_manifest(session_id: str):
    return _get_active_session(session_id).get_version_manifest()


@app.get("/api/sessions/{session_id}/audit_export")
def get_session_audit_export(session_id: str):
    return _get_active_session(session_id).get_audit_export()


# ─────────────────────────────────────────────────────────────────────────────
# VOLVER A MIRAR · LECTURAS CON DEEPSEEK
# ─────────────────────────────────────────────────────────────────────────────

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
MAX_PALABRAS_LECTURA = 120


def _recortar(valor: Any, limite: int) -> str:
    return (valor if isinstance(valor, str) else "").strip()[:limite]


def _limitar_palabras(texto: str, limite: int = MAX_PALABRAS_LECTURA) -> str:
    palabras = texto.split()
    if len(palabras) <= limite:
        return " ".join(palabras)
    return " ".join(palabras[:limite]) + "…"


def _prompt_lectura(req: MirarOjosRequest, ref: MirarOjosReferente) -> str:
    preguntas = "\n".join(f"- {_recortar(p, 300)}" for p in req.preguntas[:3] if _recortar(p, 300))
    etiquetas = ", ".join(_recortar(e, 60) for e in ref.etiquetas[:12] if _recortar(e, 60))
    proyecto = _recortar(req.proyecto, 200) or "el proyecto abierto"
    return (
        f"Eres {_recortar(req.ojos, 200) or 'un lector con ojos propios'}. "
        f"Cómo miras: {_recortar(req.ojos_descripcion, 800)}\n"
        f"Tus tres preguntas:\n{preguntas or '- ¿Qué le sirve hoy a este proyecto?'}\n\n"
        f"Proyecto abierto: {proyecto}\n"
        f"Referente: {_recortar(ref.nombre, 300)}\n"
        f"Archivo de origen: {_recortar(ref.archivo_origen, 300) or 'sin dato'}\n"
        f"Por qué se guardó: {_recortar(ref.por_que, 4000) or 'sin nota'}\n"
        f"Etiquetas: {etiquetas or 'ninguna'}\n\n"
        "Responde en español, en un solo párrafo de 120 palabras como máximo, a esta pregunta: "
        f"¿qué le sirve hoy a {proyecto} de este referente? "
        "Sé concreto y material; sin elogios, sin resumen y sin repetir la ficha. "
        "Si el referente no alcanza, di exactamente qué falta comprobar."
    )


def _pedir_lectura(api_key: str, req: MirarOjosRequest, ref: MirarOjosReferente) -> str:
    """Llamada bloqueante a DeepSeek. La clave no se registra ni se devuelve."""
    cuerpo = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Eres un lector de referentes de diseño. Escribes observaciones concretas, "
                           "en español y en un máximo de 120 palabras. No inventas datos de la ficha.",
            },
            {"role": "user", "content": _prompt_lectura(req, ref)},
        ],
        "max_tokens": 320,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")
    peticion = urllib.request.Request(
        DEEPSEEK_URL,
        data=cuerpo,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=45) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        log.warning("deepseek rechazó la lectura: HTTP %s", exc.code)
        return ""
    except Exception as exc:  # red, TLS, tiempo, JSON roto
        log.warning("deepseek no disponible: %s", type(exc).__name__)
        return ""
    try:
        texto = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        log.warning("deepseek devolvió una respuesta sin contenido")
        return ""
    return _limitar_palabras(_recortar(texto, 20000))


@app.post("/api/referentes/mirar")
async def mirar_referentes(req: MirarOjosRequest):
    """Tres lecturas-propuesta. Sin clave o sin red devuelve el ritual en blanco."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    referentes = req.referentes[:3]
    if not referentes:
        return {"ok": True, "disponible": False, "motivo": "No hay referentes que mirar.", "modelo": "", "lecturas": []}
    if not api_key:
        return {
            "ok": True,
            "disponible": False,
            "motivo": "Falta DEEPSEEK_API_KEY en el entorno del backend. Escribe las lecturas a mano.",
            "modelo": "",
            "lecturas": [{"texto": "", "modelo": ""} for _ in referentes],
        }

    resultados = await asyncio.gather(
        *[run_in_threadpool(_pedir_lectura, api_key, req, ref) for ref in referentes],
        return_exceptions=True,
    )
    lecturas = []
    for resultado in resultados:
        if isinstance(resultado, Exception):
            log.warning("lectura fallida: %s", type(resultado).__name__)
            texto = ""
        else:
            texto = _limitar_palabras(resultado or "")
        lecturas.append({"texto": texto, "modelo": DEEPSEEK_MODEL if texto else ""})

    if not any(item["texto"] for item in lecturas):
        return {
            "ok": True,
            "disponible": False,
            "motivo": "DeepSeek no respondió (sin red o sin cuota). Escribe las lecturas a mano.",
            "modelo": "",
            "lecturas": lecturas,
        }
    return {"ok": True, "disponible": True, "motivo": "", "modelo": DEEPSEEK_MODEL, "lecturas": lecturas}


# ─────────────────────────────────────────────────────────────────────────────
# ASISTENTE (EXPERIMENTAL, SIN LLM)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/agent/chat")
def chat_with_agent(session_id: str, req: AgentChatRequest):
    sess = _get_active_session(session_id)
    bridge = AGENT_BRIDGES.get(session_id)
    if not bridge:
        bridge = StudioAgentBridge(sess)
        AGENT_BRIDGES[session_id] = bridge
    return {"ok": True, "reply": bridge.handle_user_message(req.message)}


@app.post("/api/sessions/{session_id}/close")
def close_session(session_id: str):
    closed = _manager().close_session(session_id)
    AGENT_BRIDGES.pop(session_id, None)
    return {"ok": closed}
