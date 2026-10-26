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
import base64
import hashlib
import hmac
import html as html_lib
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
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


class TypographyRequest(BaseModel):
    node_id: str
    new_text: Optional[str] = None
    font_size_pt: Optional[float] = Field(default=None, ge=4, le=300)
    color: Any = None
    font_family: Optional[str] = None


class AnnotationRequest(BaseModel):
    page: int
    kind: str
    text: Optional[str] = None
    image_data_url: Optional[str] = None
    x: float = 72
    y: float = 72
    width: float = 240
    height: Optional[float] = None
    font_size_pt: float = 12
    color: Any = None


class OrganizePagesRequest(BaseModel):
    order: Optional[List[int]] = None
    rotate: Optional[List[Dict[str, Any]]] = None
    delete: Optional[List[int]] = None
    merge: Optional[List[str]] = None
    filename: Optional[str] = None


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


class ManifiestoRequest(BaseModel):
    proyecto: str = ""
    collages: List[str] = Field(default_factory=list)
    lecturas: List[str] = Field(default_factory=list)
    pesos: List[str] = Field(default_factory=list)


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


URL_PREVIEW_TIMEOUT = 6.0
URL_PREVIEW_MAX_BYTES = 512 * 1024


class _UrlPreviewParser(HTMLParser):
    """Extrae solo título, descripción e imagen sociales. Nada de scripts ni cuerpo."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self.meta: Dict[str, str] = {}
        self._in_title = False
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        attributes = {str(key).lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "body":
            self._in_body = True
        elif tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").strip().lower()
            content = attributes.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "body":
            self._in_body = True

    def handle_data(self, data):
        if self._in_title and not self._in_body:
            self.title_parts.append(data)


def _public_url_host(hostname: str) -> bool:
    """Rechaza destinos locales, privados o reservados (SSRF) antes de abrir el socket."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def _validar_url_vista_previa(raw: str) -> str:
    value = (raw or "").strip()
    if not value or len(value) > 2048:
        raise E.ApiError(400, "URL_INVALID", "La dirección está vacía o es demasiado larga.", E.STAGE_API)
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        raise E.ApiError(400, "URL_INVALID", "La dirección no es válida.", E.STAGE_API) from exc
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise E.ApiError(400, "URL_INVALID", "Solo se admiten direcciones http:// o https://.", E.STAGE_API)
    if parsed.username or parsed.password:
        raise E.ApiError(400, "URL_INVALID", "La dirección no puede llevar credenciales.", E.STAGE_API)
    if not _public_url_host(parsed.hostname):
        raise E.ApiError(400, "URL_NOT_PUBLIC", "Esa dirección apunta a la red local o a un host no público.", E.STAGE_API)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _descargar_vista_previa(url: str) -> Dict[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Prometeo-Studio-LinkPreview/1.0 (+local)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es,en;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=URL_PREVIEW_TIMEOUT) as response:
            final_url = response.geturl()
            final_host = urllib.parse.urlsplit(final_url).hostname or ""
            # Una redirección no puede saltarse la comprobación de red local.
            if not final_host or not _public_url_host(final_host):
                raise E.ApiError(400, "URL_NOT_PUBLIC", "La redirección apunta a la red local.", E.STAGE_API)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "xml" not in content_type:
                raise E.ApiError(415, "URL_NOT_HTML", "Esa dirección no devuelve una página HTML.", E.STAGE_API)
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(URL_PREVIEW_MAX_BYTES + 1)
            if len(body) > URL_PREVIEW_MAX_BYTES:
                body = body[:URL_PREVIEW_MAX_BYTES]
    except E.ApiError:
        raise
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise E.ApiError(502, "URL_UNREACHABLE", "No se pudo abrir la dirección.", E.STAGE_API, retryable=True,
                         details={"reason": type(exc).__name__}) from exc

    try:
        text = body.decode(charset, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    parser = _UrlPreviewParser()
    try:
        parser.feed(text)
    except Exception:
        # Un HTML roto no debe romper el pegado: se devuelve lo que se haya leído.
        pass

    def clean(value: str, limit: int) -> str:
        return re.sub(r"\s+", " ", html_lib.unescape(value or "")).strip()[:limit]

    title = clean(parser.meta.get("og:title") or parser.meta.get("twitter:title") or "".join(parser.title_parts), 300)
    description = clean(parser.meta.get("og:description") or parser.meta.get("description") or parser.meta.get("twitter:description"), 600)
    image = clean(parser.meta.get("og:image") or parser.meta.get("og:image:url") or parser.meta.get("twitter:image"), 2048)
    if image:
        image = urllib.parse.urljoin(final_url, image)
        if urllib.parse.urlsplit(image).scheme not in ("http", "https"):
            image = ""
    return {"url": final_url, "titulo": title, "descripcion": description, "imagen": image}


@app.get("/api/url-preview")
def url_preview(url: str = Query(..., max_length=2048)):
    """Vista previa de una URL pegada: solo og:/title/description, con timeout y sin claves."""
    safe_url = _validar_url_vista_previa(url)
    data = _descargar_vista_previa(safe_url)
    return {"ok": True, **data}


# ─────────────────────────────────────────────────────────────────────────────
# REFERENTES: DESARMAR UNA PÁGINA EN PIEZAS DE COLLAGE (SUPER-4 · I7)
# ─────────────────────────────────────────────────────────────────────────────

DESARMAR_TIMEOUT = 10.0
DESARMAR_MAX_HTML = 2 * 1024 * 1024
DESARMAR_MAX_IMAGES = 6
DESARMAR_MAX_IMAGE_BYTES = 2 * 1024 * 1024
DESARMAR_UA = "Prometeo-Studio-Referentes/1.0 (+uso personal de estudio)"


class _DesarmarParser(HTMLParser):
    """Lee titulares, textos, imágenes, estilos y fuentes. No ejecuta nada de la página."""

    CAPTURAS = {"title", "h1", "h2", "h3", "p", "blockquote", "figcaption", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: Dict[str, str] = {}
        self.headings: List[Dict[str, str]] = []
        self.paragraphs: List[str] = []
        self.images: List[Dict[str, str]] = []
        self.styles: List[str] = []
        self._captura: Optional[str] = None
        self._profundidad = 0
        self._buffer: List[str] = []
        self._en_style = False
        self._style_buffer: List[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = {str(key).lower(): (value or "") for key, value in attrs}
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").strip().lower()
            content = attributes.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
            return
        if tag == "img":
            src = (attributes.get("src") or "").strip()
            srcset = (attributes.get("srcset") or "").strip()
            if not src and srcset:
                src = srcset.split(",")[0].strip().split(" ")[0]
            if src:
                self.images.append({"src": src, "alt": (attributes.get("alt") or "").strip()[:300]})
            return
        if tag == "link":
            href = attributes.get("href", "").strip()
            if href and ("font" in (attributes.get("rel") or "").lower() or "fonts." in href):
                self.styles.append(f"url({href})")
            return
        if tag == "style":
            self._en_style = True
            self._style_buffer = []
            return
        if tag in self.CAPTURAS:
            if self._captura is None:
                self._captura = tag
                self._profundidad = 0
                self._buffer = []
            self._profundidad += 1
        style = attributes.get("style", "")
        if style:
            self.styles.append(style)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "style" and self._en_style:
            self._en_style = False
            self.styles.append(" ".join(self._style_buffer))
            self._style_buffer = []
            return
        if self._captura is None or tag != self._captura:
            return
        self._profundidad -= 1
        if self._profundidad > 0:
            return
        text = re.sub(r"\s+", " ", html_lib.unescape("".join(self._buffer))).strip()[:800]
        if self._captura == "title":
            self.title = text
        elif self._captura in ("h1", "h2", "h3"):
            if text:
                self.headings.append({"rol": self._captura, "text": text})
        elif text and len(text) >= 3:
            self.paragraphs.append(text)
        self._captura = None
        self._buffer = []

    def handle_data(self, data):
        if self._en_style:
            self._style_buffer.append(data)
        elif self._captura is not None:
            self._buffer.append(data)

    def handle_entityref(self, name):
        if self._captura is not None:
            self._buffer.append(f"&{name};")


def _robots_permite(url: str) -> bool:
    """Consulta robots.txt con el mismo guardia SSRF; si no se puede leer, no bloquea."""
    parts = urllib.parse.urlsplit(url)
    robots_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": DESARMAR_UA}, method="GET")
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read(128 * 1024).decode("utf-8", errors="replace")
    except Exception:
        return True
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    return parser.can_fetch(DESARMAR_UA, url)


def _descargar_html(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": DESARMAR_UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es,en;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=DESARMAR_TIMEOUT) as response:
            final_url = response.geturl()
            final_host = urllib.parse.urlsplit(final_url).hostname or ""
            if not final_host or not _public_url_host(final_host):
                raise E.ApiError(400, "URL_NOT_PUBLIC", "La redirección apunta a la red local.", E.STAGE_API)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "xml" not in content_type:
                raise E.ApiError(415, "URL_NOT_HTML", "Esa dirección no devuelve una página HTML.", E.STAGE_API)
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(DESARMAR_MAX_HTML + 1)
            if len(body) > DESARMAR_MAX_HTML:
                body = body[:DESARMAR_MAX_HTML]
    except E.ApiError:
        raise
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise E.ApiError(502, "URL_UNREACHABLE", "No se pudo abrir la dirección.", E.STAGE_API,
                         retryable=True, details={"reason": type(exc).__name__}) from exc
    try:
        text = body.decode(charset, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    return {"url": final_url, "html": text}


def _descargar_imagen_pagina(src: str, base_url: str) -> Optional[Dict[str, Any]]:
    try:
        absolute = urllib.parse.urljoin(base_url, src)
        parts = urllib.parse.urlsplit(absolute)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname or not _public_url_host(parts.hostname):
        return None
    request = urllib.request.Request(
        absolute,
        headers={"User-Agent": DESARMAR_UA, "Accept": "image/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            final_host = urllib.parse.urlsplit(response.geturl()).hostname or ""
            if not final_host or not _public_url_host(final_host):
                return None
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                return None
            body = response.read(DESARMAR_MAX_IMAGE_BYTES + 1)
            if len(body) > DESARMAR_MAX_IMAGE_BYTES or not body:
                return None
    except Exception:
        return None
    return {"url": absolute, "mime": content_type, "bytes": body}


def _extension_imagen(mime: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/avif": ".avif",
    }.get(mime, ".img")


def _data_url(mime: str, body: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(body).decode('ascii')}"


def _captura_svg(titulo: str, host: str) -> str:
    """La captura mínima cuando la página no ofrece og:image: su título y su dominio, no una foto inventada."""
    safe_title = html_lib.escape((titulo or host or "Página")[:120])
    safe_host = html_lib.escape((host or "")[:80])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450">'
        '<rect width="100%" height="100%" fill="#1b1511"/>'
        '<rect x="48" y="48" width="704" height="354" fill="none" stroke="#4a3a2d"/>'
        f'<text x="80" y="210" fill="#f2e8dc" font-family="Georgia, serif" font-size="34">{safe_title}</text>'
        f'<text x="80" y="270" fill="#c9a27a" font-family="Menlo, monospace" font-size="16">{safe_host}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _colores_de_estilos(estilos: List[str]) -> List[str]:
    vistos: List[str] = []
    for bloque in estilos:
        for match in re.finditer(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", bloque):
            valor = match.group(1).lower()
            if len(valor) == 3:
                valor = "".join(ch * 2 for ch in valor)
            hex_value = f"#{valor}"
            if hex_value not in vistos:
                vistos.append(hex_value)
    return vistos[:8]


def _fuentes_de_estilos(estilos: List[str]) -> List[str]:
    vistos: List[str] = []
    for bloque in estilos:
        for match in re.finditer(r"font-family\s*:\s*([^;}{]+)", bloque, flags=re.IGNORECASE):
            valor = re.sub(r"\s+", " ", match.group(1)).strip().strip("\"'")[:120]
            if not valor or valor in vistos:
                continue
            if valor.startswith(("url(", "var(", "calc(")) or "var(--" in valor:
                continue
            vistos.append(valor)
    return vistos[:6]


class DesarmarRequest(BaseModel):
    url: str = Field(..., max_length=2048, description="Página que se desarma en piezas")


@app.post("/api/referentes/desarmar")
def desarmar_referente(req: DesarmarRequest):
    """Descarga una página (sin JS), la parte en piezas y guarda sus imágenes en el proyecto.

    Uso personal de estudio: no se republica nada. Se respeta robots.txt y, si bloquea,
    se avisa sin descargar el cuerpo.
    """
    safe_url = _validar_url_vista_previa(req.url)
    if not _robots_permite(safe_url):
        return {
            "ok": False,
            "code": "ROBOTS_DISALLOW",
            "message": "La página pide en robots.txt no ser descargada. No se desarmó nada.",
            "url": safe_url,
        }
    fetched = _descargar_html(safe_url)
    final_url = fetched["url"]
    parser = _DesarmarParser()
    try:
        parser.feed(fetched["html"])
    except Exception:
        pass
    host = urllib.parse.urlsplit(final_url).netloc or final_url
    titulo = re.sub(r"\s+", " ", parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title).strip()[:300]
    descripcion = re.sub(r"\s+", " ", parser.meta.get("og:description") or parser.meta.get("description") or "").strip()[:600]

    # Imágenes: solo http(s), máximo 6, cada una guardada en la carpeta del proyecto.
    carpeta = ""
    if SESSION_MANAGER is not None:
        marca = hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:12]
        carpeta = os.path.join(SESSION_MANAGER.instance_root, "referentes", marca)
        os.makedirs(carpeta, mode=0o700, exist_ok=True)

    urls_vistas: set = set()
    imagenes: List[Dict[str, Any]] = []
    archivos: List[str] = []
    for entrada in parser.images:
        src = urllib.parse.urljoin(final_url, entrada["src"])
        if src in urls_vistas:
            continue
        urls_vistas.add(src)
        if len(imagenes) >= DESARMAR_MAX_IMAGES:
            break
        descargada = _descargar_imagen_pagina(src, final_url)
        if not descargada:
            continue
        indice = len(imagenes) + 1
        nombre = f"img-{indice:02d}{_extension_imagen(descargada['mime'])}"
        if carpeta:
            try:
                destino = os.path.join(carpeta, nombre)
                with open(destino, "wb") as handle:
                    handle.write(descargada["bytes"])
                archivos.append(os.path.relpath(destino, SESSION_MANAGER.instance_root))
            except OSError:
                pass
        imagenes.append({
            "kind": "image",
            "name": nombre,
            "mime": descargada["mime"],
            "src": _data_url(descargada["mime"], descargada["bytes"]),
            "alt": entrada.get("alt") or "",
            "fuente": final_url,
        })

    captura_src = parser.meta.get("og:image") or parser.meta.get("twitter:image") or ""
    captura = ""
    if captura_src:
        descargada = _descargar_imagen_pagina(captura_src, final_url)
        if descargada:
            captura = _data_url(descargada["mime"], descargada["bytes"])
    if not captura:
        captura = _captura_svg(titulo, host)

    piezas: List[Dict[str, Any]] = []
    piezas.extend(imagenes)
    vistos_texto: set = set()
    for titular in parser.headings:
        texto = titular["text"].strip()
        clave = texto.lower()
        if not texto or clave in vistos_texto:
            continue
        vistos_texto.add(clave)
        piezas.append({"kind": "text", "rol": "titular", "text": texto, "fuente": final_url})
        if len([p for p in piezas if p["kind"] == "text"]) >= 6:
            break
    for parrafo in parser.paragraphs:
        clave = parrafo.lower()
        if clave in vistos_texto:
            continue
        vistos_texto.add(clave)
        piezas.append({"kind": "text", "rol": "texto", "text": parrafo, "fuente": final_url})
        if len([p for p in piezas if p["kind"] == "text"]) >= 12:
            break
    paleta = _colores_de_estilos(parser.styles)
    for color in paleta:
        piezas.append({"kind": "color", "color": color, "fuente": final_url})
    tipografias = _fuentes_de_estilos(parser.styles)
    for fuente in tipografias:
        piezas.append({"kind": "font", "font": fuente, "fuente": final_url})

    return {
        "ok": True,
        "url": final_url,
        "titulo": titulo or host,
        "descripcion": descripcion,
        "host": host,
        "captura": captura,
        "paleta": paleta,
        "tipografias": tipografias,
        "piezas": piezas,
        "archivos": archivos,
        "robots": "permitido",
    }


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
# HERRAMIENTAS DE DOCUMENTO (H8): archivos nuevos, original intacto
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/typography")
def edit_typography(session_id: str, req: TypographyRequest):
    sess = _get_active_session(session_id)
    return sess.typography_edit(
        node_id=req.node_id,
        new_text=req.new_text,
        font_size_pt=req.font_size_pt,
        color=req.color,
        font_family=req.font_family,
    )


@app.post("/api/sessions/{session_id}/annotate")
def annotate_document(session_id: str, req: AnnotationRequest):
    sess = _get_active_session(session_id)
    return sess.annotate_document(
        page_number=req.page,
        kind=req.kind,
        text=req.text,
        image_data_url=req.image_data_url,
        x=req.x,
        y=req.y,
        width=req.width,
        height=req.height,
        font_size_pt=req.font_size_pt,
        color=req.color,
    )


@app.post("/api/sessions/{session_id}/organize_pages")
def organize_document_pages(session_id: str, req: OrganizePagesRequest):
    sess = _get_active_session(session_id)
    return sess.organize_pages(
        order=req.order,
        rotate=req.rotate,
        delete=req.delete,
        merge=req.merge,
        filename=req.filename,
    )


@app.get("/api/sessions/{session_id}/advanced/{token}")
def download_advanced_output(session_id: str, token: str):
    sess = _get_active_session(session_id)
    rec = sess.get_advanced_output(token)
    if rec is None:
        raise E.ApiError(404, "ADVANCED_OUTPUT_NOT_FOUND", "Esa copia ya no existe en la sesión.", E.STAGE_EXPORT)
    return FileResponse(rec["path"], filename=rec["filename"], media_type="application/pdf",
                        headers={"X-Prometeo-Output-Sha256": rec["sha256"]})


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTACIÓN Y VERIFICACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/verify_and_export")
def verify_and_export_session(session_id: str, req: VerifyExportRequest):
    """Resultado de dominio: 200 con ok=false cuando el verificador rechaza o falla."""
    return _get_active_session(session_id).verify_and_export(output_filename=req.output_filename)


@app.post("/api/sessions/{session_id}/preflight")
def preflight_session(session_id: str):
    """Comprobación en segundo plano: misma verificación física, sin archivo publicado."""
    return _get_active_session(session_id).preflight()


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
# MANIFIESTO SEMANAL · DEEPSEEK
# ─────────────────────────────────────────────────────────────────────────────

MAX_LINEAS_MANIFIESTO = 12


def _limpiar_linea_manifiesto(valor: str) -> str:
    linea = valor.strip()
    linea = re.sub(r"^#{1,6}\s*", "", linea)
    linea = re.sub(r"\*\*(.+?)\*\*", r"\1", linea)
    linea = re.sub(r"__(.+?)__", r"\1", linea)
    linea = re.sub(r"^(?:\d+[.)]|[-*•])\s*", "", linea)
    linea = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[clave oculta]", linea)
    linea = re.sub(r"Bearer\s+\S+", "Bearer [oculto]", linea, flags=re.IGNORECASE)
    return linea.strip()


def _lineas_manifiesto(texto: str) -> List[str]:
    limpio = (texto or "").replace("\r\n", "\n").strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", limpio)
        limpio = re.sub(r"\n?```$", "", limpio)
    crudas = [_limpiar_linea_manifiesto(linea) for linea in limpio.split("\n")]
    lineas = [linea for linea in crudas if linea]
    if len(lineas) <= 1 and lineas:
        lineas = [_limpiar_linea_manifiesto(parte) for parte in re.split(r"(?<=[.!?…])\s+", lineas[0])]
        lineas = [linea for linea in lineas if linea]
    lineas = lineas[:MAX_LINEAS_MANIFIESTO]
    return [f"{indice}. {linea}" for indice, linea in enumerate(lineas, start=1)]


def _prompt_manifiesto(req: ManifiestoRequest) -> str:
    proyecto = _recortar(req.proyecto, 200) or "el proyecto abierto"
    collages = "\n".join(f"- {_recortar(item, 400)}" for item in req.collages[:9] if _recortar(item, 400))
    lecturas = "\n".join(f"- {_recortar(item, 1200)}" for item in req.lecturas[:12] if _recortar(item, 1200))
    pesos = "\n".join(f"- {_recortar(item, 200)}" for item in req.pesos[:5] if _recortar(item, 200))
    return (
        f"Proyecto: {proyecto}\n\n"
        f"Collages con ♥ de los últimos siete días:\n{collages or '- ninguno'}\n\n"
        f"Lecturas aceptadas de la semana (palabras de Bruno):\n{lecturas or '- ninguna'}\n\n"
        f"Pesos de gusto que más subieron:\n{pesos or '- ninguno'}\n\n"
        "Escribe un manifiesto de vanguardia para esta semana, en español, de como máximo "
        f"{MAX_LINEAS_MANIFIESTO} líneas numeradas. Cada línea es una sola idea corta y material. "
        "Usa palabras de las lecturas; no inventes citas ni datos. "
        "No uses Markdown, ni títulos, ni explicaciones antes o después. "
        "Devuelve solo las líneas numeradas."
    )


def _pedir_manifiesto(api_key: str, req: ManifiestoRequest) -> List[str]:
    """Llamada bloqueante a DeepSeek. La clave no se registra ni se devuelve."""
    cuerpo = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Eres un editor de manifiestos de vanguardia. Escribes en español, "
                           f"en líneas numeradas y con un máximo de {MAX_LINEAS_MANIFIESTO} líneas. "
                           "No inventas datos ni citas.",
            },
            {"role": "user", "content": _prompt_manifiesto(req)},
        ],
        "max_tokens": 700,
        "temperature": 0.85,
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
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        log.warning("deepseek rechazó el manifiesto: HTTP %s", exc.code)
        return []
    except Exception as exc:  # red, TLS, tiempo, JSON roto
        log.warning("deepseek no disponible para el manifiesto: %s", type(exc).__name__)
        return []
    try:
        texto = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        log.warning("deepseek devolvió un manifiesto sin contenido")
        return []
    return _lineas_manifiesto(_recortar(texto, 20000))


@app.post("/api/manifiesto/escribir")
async def escribir_manifiesto(req: ManifiestoRequest):
    """Manifiesto de ≤12 líneas. Sin clave o sin red devuelve la plantilla vacía."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": True,
            "disponible": False,
            "motivo": "Falta DEEPSEEK_API_KEY en el entorno del backend. Escribe el manifiesto a mano.",
            "modelo": "",
            "lineas": [],
        }

    lineas = await run_in_threadpool(_pedir_manifiesto, api_key, req)
    if not lineas:
        return {
            "ok": True,
            "disponible": False,
            "motivo": "DeepSeek no respondió (sin red o sin cuota). Escribe el manifiesto a mano.",
            "modelo": "",
            "lineas": [],
        }
    return {"ok": True, "disponible": True, "motivo": "", "modelo": DEEPSEEK_MODEL, "lineas": lineas}


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
