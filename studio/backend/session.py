"""PROMETEO Studio · Document Session Model & Manager (ORDEN 133)
─────────────────────────────────────────────────────────────
Gestiona el ciclo de vida de sesiones de edición visual y de agente:
- Ingesta segura y copia de trabajo aislada.
- Preservación estricta de la inmutabilidad del original.
- Navegación multinivel por DocGraph v0.3.
- Preparación y ejecución de transacciones atómicas con verificación física.
- Comparación DocGraphDiff de resultados verificados.
"""

from studio.backend import pdf_gate
import os
import sys

# Ensure fase0 and repo root are in sys.path for engine/operations imports
HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(STUDIO_ROOT)
FASE0_DIR = os.path.join(REPO_ROOT, "fase0")
if FASE0_DIR not in sys.path:
    sys.path.insert(0, FASE0_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import shutil
import uuid
import base64
import hashlib
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

from docgraph import (
    DocGraph,
    build_docgraph,
    get_document_summary,
    get_document_outline_context,
    get_node_window,
    get_node_neighbors,
    docgraph_diff,
    NodeType,
    RelationType,
)
from docgraph.cache import GLOBAL_DOCGRAPH_CACHE
from fase0 import tools
from fase0.tools import PrometeoTools, ResultState, sha256_file
from raster_classifier import (
    classify_raster_target,
    RASTER_CLASS_A,
    RASTER_CLASS_B,
    RASTER_CLASS_C,
    SAFETY_SAFE,
    SAFETY_UNCERTAIN,
    SAFETY_UNSAFE,
)
from raster_operations import (
    RasterReplaceText,
    reconstruct_class_a_background,
    render_approximated_text_patch,
    apply_raster_patch,
    apply_raster_transaction,
)
import numpy as np
from .security import sanitize_filename, assert_safe_path
from . import export_pipeline as xp
from .version import PROMETEO_VERSION
from . import workspace as ws


# Tope de píxeles por render (como `maxCanvasPixels` de pdf.js): una página legal de 14 400 × 14 400 pt
# a 150 ppp serían ~900 Mpx (~2,7 GB). Por encima del tope se baja la resolución; la respuesta
# declara la resolución real (`dpi`, `scale`), así que la interfaz sigue alineada.
MAX_RENDER_PIXELS = 1 << 25  # ~33,5 Mpx (A0 a 150 ppp cabe)
# La edición raster trabaja a 300 ppp en gris; por encima de este tope se rechaza con un motivo.
MAX_RASTER_PIXELS = 1 << 26  # ~67 Mpx (A1 a 300 ppp cabe)
RASTER_PAGE_TOO_LARGE_MSG = "La página es demasiado grande para la edición raster (supera el tope de memoria)."


def fit_render_dpi(rect, dpi: int) -> int:
    """La resolución pedida, o la mayor que no supere MAX_RENDER_PIXELS para esta página."""
    w_in, h_in = max(float(rect.width), 1.0) / 72.0, max(float(rect.height), 1.0) / 72.0
    max_dpi = int((MAX_RENDER_PIXELS / (w_in * h_in)) ** 0.5)
    return max(1, min(int(dpi), max_dpi))


def raster_page_within_budget(rect) -> bool:
    return (float(rect.width) / 72.0 * 300.0) * (float(rect.height) / 72.0 * 300.0) <= MAX_RASTER_PIXELS


class WorkspaceUnavailableError(RuntimeError):
    """No hay ninguna carpeta escribible fuera del paquete para los datos de sesión."""

    def __init__(self, info):
        super().__init__("; ".join(info.errors) or "workspace no disponible")
        self.info = info
STUDIO_ROOT = os.path.dirname(HERE)

# Rutas de muestras pre-autorizadas del repositorio
AUTHORIZED_SAMPLES = {
    "case_a": os.path.abspath(os.path.join(STUDIO_ROOT, "..", "fase0", "assets", "case_a.pdf")),
    "case_b_scan": os.path.abspath(os.path.join(STUDIO_ROOT, "..", "fase0", "assets", "case_b_scan.pdf")),
    "form_56": os.path.abspath(os.path.join(STUDIO_ROOT, "..", "fase0", "experiments", "h3dv3_dev_003", "m1", "external_dev_natural_b2c7", "accepted", "EXTM1_CAND_0010.pdf")),
    "doc_73p": os.path.abspath(os.path.join(STUDIO_ROOT, "..", "fase0", "experiments", "h3dv3_dev_003", "m1", "external_dev_natural_b2c7", "accepted", "EXTM1_CAND_0002.pdf")),
}


class StudioDocumentSession:
    """Representa una sesión interactiva de un documento cargado en Studio."""

    def __init__(
        self,
        session_id: str,
        source_filename: str,
        source_path: str,
        working_copy_path: str,
        source_sha256: str,
        session_dir: str,
    ):
        self.session_id = session_id
        self.source_filename = source_filename
        self.source_path = source_path
        self.working_copy_path = working_copy_path
        self.source_sha256 = source_sha256
        self.session_dir = session_dir
        self.docgraph_version = "0.3"

        # Inicializar motor de herramientas de Prometeo
        self.tools = PrometeoTools()
        # Misma versión que la sesión: un único DocGraph en la caché (antes se construían dos).
        res_open = self.tools.open_document(self.working_copy_path, docgraph_version=self.docgraph_version)
        if not res_open.get("ok"):
            raise RuntimeError(f"Error al inicializar PrometeoTools: {res_open.get('error')}")

        self.document_id = res_open["document_id"]
        # Obtener grafo mediante caché
        self.graph, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(self.working_copy_path, version=self.docgraph_version)

        # Estado transaccional y de verificación
        self.active_transaction_id: Optional[str] = None
        self.transaction_state: str = xp.STATE_READY
        self.staged_operations: List[Dict[str, Any]] = []
        # Solo una salida que pasó la verificación se registra aquí (PA-003).
        self.published_output: Optional[Dict[str, Any]] = None
        self.saved_outputs: List[str] = []
        self.last_exported_path: Optional[str] = None
        self.last_exported_filename: Optional[str] = None
        self.last_verifier_result: Optional[Dict[str, Any]] = None
        self.last_diff: Optional[Dict[str, Any]] = None
        # Salidas de las herramientas de documento (tipografía, anotaciones, páginas):
        # siempre archivos nuevos, nunca el original ni la copia de trabajo.
        self.advanced_outputs: Dict[str, str] = {}
        # Ganchos sustituibles en pruebas: aplicación raster y verificador.
        self._raster_apply_fn = apply_raster_transaction
        self._raster_verify_loader = xp.load_raster_verifier
        self._semantic_authority_check = xp.semantic_authority_available

        self.is_active = True

    def _assert_original_unmodified(self):
        """Invariante epistemológico: el archivo original subido nunca cambia su digest."""
        current_sha = sha256_file(self.source_path)
        if current_sha != self.source_sha256:
            raise RuntimeError("CRITICAL INVARIANT VIOLATION: el archivo original ha sido modificado.")

    def get_summary(self) -> Dict[str, Any]:
        """LEVEL 0: Resumen ultracompacto del documento."""
        summary = get_document_summary(self.graph)
        summary["filename"] = self.source_filename
        summary["pages_count"] = summary.get("page_count", len(summary.get("pages", [])))
        summary["page_count"] = summary["pages_count"]
        summary["session_id"] = self.session_id
        summary["transaction_state"] = self.transaction_state
        summary["staged_count"] = len(self.staged_operations)
        summary["capabilities"] = self.get_capabilities()
        return summary

    def get_capabilities(self) -> Dict[str, Any]:
        """Descubrimiento de capacidades observables según la naturaleza del documento."""
        has_text = any(n.node_type == NodeType.TEXT.value for n in self.graph.nodes.values())
        has_images = any(n.node_type == NodeType.IMAGE.value for n in self.graph.nodes.values())

        is_born_digital = has_text
        is_raster_dominant = has_images and not has_text

        return {
            "is_born_digital": is_born_digital,
            "is_raster_dominant": is_raster_dominant,
            "can_select": True,
            "can_search": has_text,
            "can_ocr_search": True,
            "can_edit_text": True,
            "can_edit_raster": bool(is_raster_dominant),
            "can_stage_transaction": True,
            "can_verify": True,
            "has_ocr_layer": True,
            "raster_state": "CONDITIONAL_VERIFIED" if is_raster_dominant else "NATIVE_VECTOR_TEXT",
            "capability_badge": "RASTER_CONDITIONAL" if is_raster_dominant else "BORN_DIGITAL",
            "raster_verifier_profile": "RASTER_PATCH_VERIFY_V0_1" if is_raster_dominant else None,
            "warning": (
                "Documento escaneado / raster dominante. PROMETEO proporciona capa de observación OCR probabilística. "
                "La edición raster física está habilitada condicionalmente para parches verificables (RASTER_CLASS_A, RASTER_PATCH_VERIFY_V0_1)."
            ) if is_raster_dominant else None,
        }

    def as_dict(self) -> Dict[str, Any]:
        """Representación serializable de la sesión para clientes de Studio."""
        return {
            "session_id": self.session_id,
            "document_id": self.document_id,
            "filename": self.source_filename,
            "source_path": self.source_path,
            "working_copy_path": self.working_copy_path,
            "source_sha256": self.source_sha256,
            "transaction_state": self.transaction_state,
            "doc_summary": self.get_summary(),
            "capabilities": self.get_capabilities(),
        }

    def get_ocr_layer(self, page_number: int = 0) -> Dict[str, Any]:
        """Extrae capa de observación OCR probabilística para una página escaneada/raster."""
        if not hasattr(self, "_ocr_cache"):
            self._ocr_cache = {}

        if page_number in self._ocr_cache:
            return self._ocr_cache[page_number]

        dpi = 150
        doc = pymupdf.open(self.working_copy_path)
        if page_number < 0 or page_number >= len(doc):
            doc.close()
            return {"ok": False, "error": f"Página {page_number} fuera de rango"}

        page = doc[page_number]
        dpi = fit_render_dpi(page.rect, dpi)
        pix = page.get_pixmap(dpi=dpi)
        doc.close()

        # Guardar en workspace seguro de la sesión con sufijo único anti-colisión
        tmp_dir = os.path.join(self.session_dir, "ocr_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        unique_token = uuid.uuid4().hex[:8]
        img_path = os.path.realpath(os.path.abspath(os.path.join(tmp_dir, f"page_{page_number}_{unique_token}.png")))
        tsv_base = os.path.realpath(os.path.abspath(os.path.join(tmp_dir, f"page_{page_number}_{unique_token}_out")))
        tsv_file = f"{tsv_base}.tsv"

        pix.save(img_path)
        observations = []
        ocr_error = None  # (code, message): un fallo de OCR nunca se presenta como "sin texto"

        try:
            try:
                from ocr_provider import find_tesseract_binary
            except ImportError:
                from fase0.ocr_provider import find_tesseract_binary
            tess_bin = find_tesseract_binary() or shutil.which("tesseract")
            if not tess_bin:
                ocr_error = ("OCR_UNAVAILABLE", "El motor OCR (Tesseract) no está disponible.")
            else:
                cmd = [tess_bin, img_path, tsv_base, "tsv"]
                proc = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=45,
                )
                if proc.returncode != 0:
                    tail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
                    ocr_error = ("OCR_FAILED", f"Tesseract terminó con código {proc.returncode}: {tail[0][:200]}")
                elif not os.path.exists(tsv_file):
                    ocr_error = ("OCR_FAILED", "Tesseract no produjo resultado.")
                scale = 72.0 / float(dpi)
                if os.path.exists(tsv_file):
                    with open(tsv_file, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                        for idx, line in enumerate(lines[1:]):
                            parts = line.strip().split("\t")
                            if len(parts) >= 12 and parts[0] == "5":
                                text = parts[11].strip()
                                if text:
                                    try:
                                        conf = float(parts[10])
                                    except ValueError:
                                        conf = -1.0
                                    if conf >= 25.0:
                                        left = float(parts[6])
                                        top = float(parts[7])
                                        w = float(parts[8])
                                        h = float(parts[9])
                                        obs_id = f"ocr_p{page_number}_w{idx}"
                                        observations.append({
                                            "id": obs_id,
                                            "observation_id": obs_id,
                                            "page": page_number,
                                            "text": text,
                                            "bbox": [
                                                round(left * scale, 2),
                                                round(top * scale, 2),
                                                round((left + w) * scale, 2),
                                                round((top + h) * scale, 2),
                                            ],
                                            "confidence": round(conf, 1),
                                            "engine": "tesseract-5.5.3",
                                            "config": "--psm 3",
                                            "provenance": "PROBABILISTIC_OBSERVATION",
                                            "is_native_entity": False,
                                            "capability_state": "RASTER_INSPECTION_READY",
                                            "editing_state": "RASTER_EDITING_NOT_VERIFIABLE",
                                        })
        except subprocess.TimeoutExpired:
            ocr_error = ("OCR_TIMEOUT", "El OCR superó el límite de 45 s para esta página.")
        except Exception as e:
            ocr_error = ("OCR_FAILED", f"Error del OCR: {type(e).__name__}")
        finally:
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass
            if os.path.exists(tsv_file):
                try:
                    os.remove(tsv_file)
                except OSError:
                    pass

        if ocr_error is not None:
            # No se cachea: el siguiente intento vuelve a ejecutar el OCR.
            return {
                "ok": False,
                "page": page_number,
                "observations_count": 0,
                "observations": [],
                "error_code": ocr_error[0],
                "error": ocr_error[1],
                "status": "OCR_FAILED",
            }

        res = {
            "ok": True,
            "page": page_number,
            "observations_count": len(observations),
            "observations": observations,
            "status": "RASTER_INSPECTION_READY",
            "editing_status": "RASTER_EDITING_NOT_VERIFIABLE",
            "epistemic_disclaimer": "OCR_TEXT != SOURCE_TEXT: Estas regiones son hipótesis probabilísticas generadas por OCR, no entidades tipográficas nativas verificables.",
        }
        self._ocr_cache[page_number] = res
        return res

    def search_ocr(self, query: str, page_number: Optional[int] = None) -> Dict[str, Any]:
        """Busca texto dentro de la capa OCR observada preservando distinción epistemológica."""
        doc = pymupdf.open(self.working_copy_path)
        total_pages = len(doc)
        doc.close()

        pages_to_search = [page_number] if page_number is not None else range(total_pages)
        candidates = []
        q_lower = query.lower()

        for p in pages_to_search:
            layer = self.get_ocr_layer(p)
            for obs in layer.get("observations", []):
                if q_lower in obs["text"].lower():
                    candidates.append({
                        "candidate_id": obs["id"],
                        "observation_id": obs["id"],
                        "page": p,
                        "span_id": obs["id"],
                        "node_id": obs["id"],
                        "text": obs["text"],
                        "matched_query": query,
                        "bbox": obs["bbox"],
                        "confidence": obs["confidence"],
                        "origin": [obs["bbox"][0], obs["bbox"][1]],
                        "is_ocr_result": True,
                        "provenance": "PROBABILISTIC_OBSERVATION",
                        "engine": obs["engine"],
                    })

        status = "FOUND" if len(candidates) == 1 else ("AMBIGUOUS" if len(candidates) > 1 else "NOT_FOUND")
        return {
            "ok": True,
            "status": status,
            "query": query,
            "candidates_count": len(candidates),
            "candidates": candidates,
            "is_ocr_result": True,
            "epistemic_tag": "OCR_RESULT",
        }

    def get_outline(
        self,
        pages: Optional[List[int]] = None,
        types: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
        include_vectors: bool = False,
    ) -> Dict[str, Any]:
        """LEVEL 1: Árbol jerárquico compacto para el Outliner."""
        return get_document_outline_context(
            self.graph,
            pages=pages,
            types=types,
            max_depth=max_depth,
            include_vectors=include_vectors,
            show_ids=True,
            show_bbox=True,
        )

    def inspect_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """LEVEL 2: Inspección detallada de un nodo."""
        node = self.graph.get_node(node_id)
        if not node:
            return None
        win = get_node_window(self.graph, node_id)
        if win:
            win["relations"] = [
                r.to_dict() for r in self.graph.relations_of(node_id, include_derived=True)
            ]
            tn = win.get("target_node", {})
            if "id" not in tn and "node_id" in tn:
                tn["id"] = tn["node_id"]
            if "type" not in tn and "node_type" in tn:
                tn["type"] = tn["node_type"]
            win["id"] = node_id
            win["type"] = tn.get("type", "TEXT")
            win["text"] = tn.get("text")
            win["page"] = tn.get("page")
            win["bbox"] = tn.get("bbox")
            win["font"] = tn.get("font")
            win["size"] = tn.get("size")
        return win

    def get_neighbors(self, node_id: str, spatial_radius: float = 36.0) -> Optional[Dict[str, Any]]:
        """LEVEL 3: Vecindad local espacial y relacional."""
        return get_node_neighbors(self.graph, node_id, spatial_radius=spatial_radius)

    # Límite solo para peticiones de documento completo; por página no se recorta nada.
    WHOLE_DOCUMENT_NODE_LIMIT = 5000

    def query_nodes(
        self,
        page: Optional[int] = None,
        node_type: Optional[str] = None,
        rect: Optional[List[float]] = None,
        text: Optional[str] = None,
        with_meta: bool = False,
    ):
        """Nodos del grafo para la interfaz, consultados directamente (sin el recorte a 50 de
        las herramientas para agentes, que dejaba sin nodos las páginas siguientes de un
        documento largo). Si se pide el documento completo y supera el límite, se informa
        `truncated` en lugar de recortar en silencio."""
        g = self.graph
        nodes = g.nodes_on_page(page) if page is not None else list(g.nodes.values())
        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type.upper()]
        if text:
            low = text.lower()
            nodes = [n for n in nodes if getattr(n, "text", None) and low in n.text.lower()]
        if rect is not None and len(rect) == 4 and page is not None:
            ids = {n.node_id for n in g.nodes_in_rect(page=page, rect=rect, contain_mode="intersects")}
            nodes = [n for n in nodes if n.node_id in ids]
        total = len(nodes)
        if page is None and total > self.WHOLE_DOCUMENT_NODE_LIMIT:
            nodes = nodes[: self.WHOLE_DOCUMENT_NODE_LIMIT]
        out = []
        for n in nodes:
            d = n.to_dict()
            d.setdefault("id", d.get("node_id"))
            d.setdefault("type", d.get("node_type"))
            out.append(d)
        if with_meta:
            return {"nodes": out, "total": total, "truncated": len(out) < total}
        return out

    def render_verified_page(self, page_number: int, dpi: int = 150) -> Optional[Dict[str, Any]]:
        """Renderiza una página de la copia verificada publicada (None si no hay PASS vigente)."""
        rec = self.get_verified_output()
        if rec is None:
            return None
        data = self.render_page(page_number, dpi, path=rec["path"])
        data["source"] = "verified"
        data["output_sha256"] = rec["sha256"]
        return data

    def render_page(self, page_number: int, dpi: int = 150, path: Optional[str] = None) -> Dict[str, Any]:
        """Renderiza una página a imagen PNG en base64 para el viewport."""
        doc = pymupdf.open(path or self.working_copy_path)
        if page_number < 0 or page_number >= len(doc):
            doc.close()
            raise ValueError(f"Número de página inválido: {page_number}")

        page = doc[page_number]
        dpi = fit_render_dpi(page.rect, dpi)
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("ascii")

        rect = page.rect
        width_pt = float(rect.width)
        height_pt = float(rect.height)
        rotation = page.rotation

        doc.close()
        return {
            "page_number": page_number,
            "width_pt": width_pt,
            "height_pt": height_pt,
            "pixel_width": pix.width,
            "pixel_height": pix.height,
            "dpi": dpi,
            "scale": dpi / 72.0,
            "rotation": rotation,
            "image_data_url": f"data:image/png;base64,{b64}",
        }

    def search_text(self, query: str, page: Optional[int] = None) -> Dict[str, Any]:
        """Busca texto en el documento y detecta posibles ambigüedades."""
        res = self.tools.find_text(
            document_id=self.document_id,
            query=query,
            page=page,
        )
        res["is_ambiguous"] = (res.get("result_state") == ResultState.AMBIGUOUS.value)
        return res

    def stage_edit(
        self,
        new_text: str,
        node_id: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepara una operación de edición manual dentro de la transacción activa."""
        if not self.is_active:
            return {"ok": False, "error": "Sesión cerrada.", "error_code": "SESSION_CLOSED"}

        if xp.OP_KIND_RASTER in xp.transaction_kinds(self.staged_operations):
            return {
                "ok": False,
                "error_code": xp.CODE_MIXED,
                "error": (
                    "La transacción ya contiene ediciones raster. Combinar ediciones raster y de texto "
                    "nativo en una misma exportación no está soportado de forma verificable: verifique "
                    "o descarte primero los cambios preparados."
                ),
            }

        target_resolved = target_id
        node_resolved = node_id

        # Si se proporcionó node_id, localizar target correspondiente
        if node_id and not target_id:
            node = self.graph.get_node(node_id)
            if not node or node.node_type != NodeType.TEXT.value:
                return {"ok": False, "error": f"Nodo {node_id} no es un TextNode válido."}

            # Buscar texto del nodo
            f_res = self.tools.find_text(self.document_id, node.text, page=node.page)
            if f_res.get("ok") and f_res.get("candidates"):
                # Encontrar candidato que coincide con este node_id
                for c in f_res["candidates"]:
                    if c.get("node_id") == node_id:
                        s_res = self.tools.select_target(self.document_id, c["candidate_id"])
                        if s_res.get("ok"):
                            target_resolved = s_res["target_id"]
                            break

        if not target_resolved and not node_resolved:
            return {"ok": False, "error": "No se pudo resolver el target para edición."}

        # Reintentar el mismo cambio actualiza la operación preparada en vez de fallar:
        # el cambio sigue siendo uno y se vuelve a verificar desde cero.
        for op in self.staged_operations:
            same_target = bool(target_resolved) and op.get("target_id") == target_resolved
            same_node = bool(node_resolved) and op.get("node_id") == node_resolved
            if same_target or same_node:
                op["new_text"] = new_text
                op["status"] = "STAGED"
                self._on_transaction_changed()
                return {
                    "ok": True,
                    "operation": op,
                    "staged": op,
                    "reused": True,
                    "staged_total": len(self.staged_operations),
                    "transaction_state": self.transaction_state,
                }

        # Inspeccionar valor anterior
        old_val = ""
        if node_resolved:
            n = self.graph.get_node(node_resolved)
            if n:
                old_val = getattr(n, "text", "")

        op_entry = {
            "op_id": f"op_{uuid.uuid4().hex[:10]}",
            "type": xp.OP_KIND_VECTOR,
            "target_id": target_resolved,
            "node_id": node_resolved,
            "old_text": old_val,
            "original_text": old_val,
            "new_text": new_text,
            "status": "STAGED",
        }
        self.staged_operations.append(op_entry)
        self._on_transaction_changed()

        return {
            "ok": True,
            "operation": op_entry,
            "staged": op_entry,
            "staged_total": len(self.staged_operations),
            "transaction_state": self.transaction_state,
        }

    def _on_transaction_changed(self) -> None:
        """Cualquier cambio en la cesta invalida la salida verificada anterior."""
        self.published_output = None
        self.last_exported_path = None
        self.last_exported_filename = None
        self.transaction_state = xp.STATE_STAGED if self.staged_operations else xp.STATE_READY

    def staged_operations_public(self) -> List[Dict[str, Any]]:
        """Operaciones preparadas sin objetos internos (raster_op) para la API."""
        return [{k: v for k, v in op.items() if k != "raster_op"} for op in self.staged_operations]

    def remove_staged_operation(self, op_id: str) -> Dict[str, Any]:
        """Elimina una operación individual del lote staged."""
        before = len(self.staged_operations)
        self.staged_operations = [op for op in self.staged_operations if op["op_id"] != op_id]
        if len(self.staged_operations) == before:
            return {"ok": False, "error_code": "OPERATION_NOT_FOUND",
                    "error": f"La operación {op_id} no está en la cesta."}
        self._on_transaction_changed()
        return {
            "ok": True,
            "staged_total": len(self.staged_operations),
            "staged_operations": self.staged_operations_public(),
            "transaction_state": self.transaction_state,
        }

    def clear_transaction(self) -> Dict[str, Any]:
        """Limpia todas las operaciones preparadas."""
        self.staged_operations.clear()
        self._on_transaction_changed()
        return {"ok": True, "transaction_state": self.transaction_state, "staged_operations": [], "count": 0}

    def get_raster_safety(self, page_number: int, observation_id: str) -> Dict[str, Any]:
        """Evalúa deterministamente la seguridad física de una observación OCR específica."""
        ocr_layer = self.get_ocr_layer(page_number)
        if not ocr_layer.get("ok"):
            return {"ok": False, "error": ocr_layer.get("error", "Error al obtener capa OCR")}

        target_obs = None
        for obs in ocr_layer.get("observations", []):
            if obs.get("id") == observation_id or obs.get("observation_id") == observation_id:
                target_obs = obs
                break

        if not target_obs:
            return {"ok": False, "error": f"Observación OCR {observation_id} no encontrada en la página {page_number}"}

        doc = pymupdf.open(self.working_copy_path)
        if page_number < 0 or page_number >= len(doc):
            doc.close()
            return {"ok": False, "error": f"Página {page_number} fuera de rango"}

        page = doc[page_number]
        if not raster_page_within_budget(page.rect):
            doc.close()
            return {"ok": False, "error": RASTER_PAGE_TOO_LARGE_MSG}
        pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        img_gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
        doc.close()

        bbox_pt = tuple(target_obs["bbox"])
        conf = float(target_obs.get("confidence", 85.0))

        safety_res = classify_raster_target(
            image=img_gray,
            target_bbox_pt=bbox_pt,
            ocr_confidence=conf,
            dpi=300.0,
        )

        # La operación raster convierte la página en una imagen en gris: si la
        # página tiene color o texto extraíble, se perdería información.
        with open(self.working_copy_path, "rb") as f:
            fidelity = xp.page_fidelity_preflight(f.read(), page_number)
        edit_eligible = bool(safety_res["edit_eligible"]) and fidelity["eligible"]
        reasons = list(safety_res["reasons"]) + list(fidelity["reasons"])

        return {
            "ok": True,
            "observation_id": observation_id,
            "page": page_number,
            "observation": target_obs,
            "safety": safety_res,
            "page_fidelity": fidelity,
            "raster_class": safety_res["raster_class"],
            "safety_classification": safety_res["safety_classification"],
            "edit_eligible": edit_eligible,
            "reasons": reasons,
            "metrics": safety_res["metrics"],
            "thresholds": safety_res["thresholds"],
            "allowed_patch_bbox_pt": safety_res["allowed_patch_bbox_pt"],
            "profile_name": safety_res["profile_name"],
        }

    def get_raster_patch_preview(
        self,
        page_number: int,
        observation_id: str,
        new_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Genera una vista previa del parche raster reconstruido para inspección humana."""
        safety_data = self.get_raster_safety(page_number, observation_id)
        if not safety_data.get("ok"):
            return safety_data

        obs = safety_data["observation"]
        safety_info = safety_data["safety"]
        target_text = new_text if new_text is not None else obs["text"]

        doc = pymupdf.open(self.working_copy_path)
        page = doc[page_number]
        pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        img_gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
        doc.close()

        allowed_patch_px = safety_info["allowed_patch_bbox_px"]
        x0, y0, x1, y1 = allowed_patch_px
        h, w = img_gray.shape
        x0 = max(0, min(x0, w))
        y0 = max(0, min(y0, h))
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))

        before_crop = img_gray[y0:y1, x0:x1]

        import io
        from PIL import Image

        pil_before = Image.fromarray(before_crop)
        buf_b = io.BytesIO()
        pil_before.save(buf_b, format="PNG")
        b64_before = base64.b64encode(buf_b.getvalue()).decode("ascii")

        if not safety_info["edit_eligible"]:
            return {
                "ok": True,
                "edit_eligible": False,
                "raster_class": safety_info["raster_class"],
                "reasons": safety_info["reasons"],
                "before_data_url": f"data:image/png;base64,{b64_before}",
                "preview_data_url": f"data:image/png;base64,{b64_before}",
                "message": f"Previsualización informativa: región no editable ({safety_info['raster_class']})",
            }

        op = RasterReplaceText(
            document_id=self.document_id,
            page=page_number,
            observation_id=observation_id,
            old_observed_text=obs["text"],
            new_text=target_text,
            target_bbox=tuple(obs["bbox"]),
            allowed_patch_bbox=tuple(safety_info["allowed_patch_bbox_pt"]),
            background_class=safety_info["raster_class"],
            provenance={"confidence": obs.get("confidence", 85.0)},
        )

        after_img, patch_meta = apply_raster_patch(img_gray, op, dpi=300.0)
        after_crop = after_img[y0:y1, x0:x1]

        pil_after = Image.fromarray(after_crop)
        buf_a = io.BytesIO()
        pil_after.save(buf_a, format="PNG")
        b64_after = base64.b64encode(buf_a.getvalue()).decode("ascii")

        return {
            "ok": True,
            "edit_eligible": True,
            "raster_class": safety_info["raster_class"],
            "safety_classification": safety_info["safety_classification"],
            "before_data_url": f"data:image/png;base64,{b64_before}",
            "preview_data_url": f"data:image/png;base64,{b64_after}",
            "allowed_patch_bbox_pt": safety_info["allowed_patch_bbox_pt"],
            "target_bbox_pt": obs["bbox"],
            "metrics": safety_info["metrics"],
        }

    def stage_raster_edit(
        self,
        page_number: int,
        observation_id: str,
        new_text: str,
        font_family: str = "helv",
        font_size_pt: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Prepara una operación RasterReplaceText tras verificar elegibilidad de seguridad."""
        if not self.is_active:
            return {"ok": False, "error": "Sesión cerrada.", "error_code": "SESSION_CLOSED"}

        if xp.OP_KIND_VECTOR in xp.transaction_kinds(self.staged_operations):
            return {
                "ok": False,
                "error_code": xp.CODE_MIXED,
                "error": (
                    "La transacción ya contiene ediciones de texto nativo. Combinar ediciones raster y de "
                    "texto nativo en una misma exportación no está soportado de forma verificable: verifique "
                    "o descarte primero los cambios preparados."
                ),
            }

        safety_data = self.get_raster_safety(page_number, observation_id)
        if not safety_data.get("ok"):
            return safety_data

        if not safety_data.get("edit_eligible"):
            return {
                "ok": False,
                "error_code": xp.CODE_RASTER_PREFLIGHT,
                "error": (
                    f"Rechazo honesto (ORDEN 137): La región observada pertenece a {safety_data.get('raster_class')} "
                    f"y no es elegible para edición verificable. Razones: {', '.join(safety_data.get('reasons', []))}"
                ),
                "raster_class": safety_data.get("raster_class"),
                "reasons": safety_data.get("reasons"),
            }

        obs = safety_data["observation"]
        safety_info = safety_data["safety"]

        # Reintentar la misma observación reutiliza su parche y actualiza el texto.
        # Así «Preparar parche» es idempotente y no obliga a descartar el cambio primero.
        for op in self.staged_operations:
            if op.get("target_id") == observation_id or op.get("observation_id") == observation_id:
                op["new_text"] = new_text
                op["status"] = "STAGED"
                raster_op = op.get("raster_op")
                if raster_op is not None:
                    raster_op.new_text = new_text
                    raster_op.font_family = font_family
                    raster_op.font_size_pt = font_size_pt
                self._on_transaction_changed()
                public = {k: v for k, v in op.items() if k != "raster_op"}
                return {
                    "ok": True,
                    "operation": public,
                    "staged": public,
                    "reused": True,
                    "staged_total": len(self.staged_operations),
                    "transaction_state": self.transaction_state,
                }

        raster_op = RasterReplaceText(
            document_id=self.document_id,
            page=page_number,
            observation_id=observation_id,
            old_observed_text=obs["text"],
            new_text=new_text,
            target_bbox=tuple(obs["bbox"]),
            allowed_patch_bbox=tuple(safety_info["allowed_patch_bbox_pt"]),
            background_class=safety_info["raster_class"],
            font_family=font_family,
            font_size_pt=font_size_pt,
            provenance={"confidence": obs.get("confidence", 85.0), "engine": obs.get("engine", "tesseract")},
        )

        op_entry = {
            "op_id": f"op_{uuid.uuid4().hex[:10]}",
            "type": xp.OP_KIND_RASTER,
            "node_id": observation_id,
            "target_id": observation_id,
            "observation_id": observation_id,
            "page": page_number,
            "old_text": obs["text"],
            "original_text": obs["text"],
            "new_text": new_text,
            "status": "STAGED",
            "raster_op": raster_op,
            "safety": safety_info,
        }

        self.staged_operations.append(op_entry)
        self._on_transaction_changed()

        public = {k: v for k, v in op_entry.items() if k != "raster_op"}
        return {
            "ok": True,
            "operation": public,
            "staged": public,
            "staged_total": len(self.staged_operations),
            "transaction_state": self.transaction_state,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HERRAMIENTAS DE DOCUMENTO (H8): tipografía, anotaciones y páginas
    # Todas producen un archivo NUEVO con su SHA-256; el original nunca se toca.
    # ─────────────────────────────────────────────────────────────────────────

    def _save_advanced(self, doc: "pymupdf.Document", prefix: str, filename: Optional[str] = None) -> Dict[str, Any]:
        folder = os.path.join(self.session_dir, "advanced")
        os.makedirs(folder, exist_ok=True)
        token = f"{prefix}_{uuid.uuid4().hex[:12]}.pdf"
        path = os.path.join(folder, token)
        doc.save(path, garbage=3, deflate=True)
        doc.close()
        digest = sha256_file(path)
        self.advanced_outputs[token] = path
        return {
            "ok": True,
            "filename": sanitize_filename(filename or token),
            "token": token,
            "sha256": digest,
            "download_url": f"/api/sessions/{self.session_id}/advanced/{token}",
        }

    def get_advanced_output(self, token: str) -> Optional[Dict[str, Any]]:
        if not re.fullmatch(r"[a-z]+_[0-9a-f]{12}\.pdf", token):
            return None
        path = self.advanced_outputs.get(token)
        if not path or not os.path.isfile(path):
            return None
        return {"path": path, "filename": os.path.basename(path), "sha256": sha256_file(path)}

    @staticmethod
    def _span_signature(span: Dict[str, Any]) -> Tuple[Any, ...]:
        bbox = tuple(round(float(value), 2) for value in span.get("bbox", (0, 0, 0, 0)))
        return (
            bbox,
            str(span.get("text", "")),
            str(span.get("font", "")),
            round(float(span.get("size", 0)), 2),
            int(span.get("color", 0)),
        )

    @staticmethod
    def _spans(page: "pymupdf.Page") -> List[Dict[str, Any]]:
        spans: List[Dict[str, Any]] = []
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if str(span.get("text", "")).strip():
                        spans.append(span)
        return spans

    @staticmethod
    def _font_name(requested: Optional[str], original: str) -> str:
        candidato = (requested or "").strip().lower()
        if candidato in {"helv", "hebo", "heit", "hebi", "times", "tibo", "tito", "tibi", "cour", "cobo", "coit", "cobi"}:
            return candidato
        if "mono" in candidato or "courier" in candidato:
            return "cour"
        if "times" in candidato or "serif" in candidato:
            return "times"
        if "bold" in candidato and "italic" in candidato:
            return "hebi"
        if "bold" in candidato:
            return "hebo"
        if "italic" in candidato:
            return "heit"
        if "times" in original.lower() or "serif" in original.lower():
            return "times"
        if "courier" in original.lower() or "mono" in original.lower():
            return "cour"
        return "helv"

    @staticmethod
    def _color_rgb(value: Any) -> Optional[Tuple[float, float, float]]:
        if isinstance(value, str):
            limpio = value.strip().lstrip("#")
            if re.fullmatch(r"[0-9a-fA-F]{6}", limpio):
                return tuple(int(limpio[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
            return None
        if isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(item, (int, float)) for item in value):
            return tuple(max(0.0, min(1.0, float(item))) for item in value)
        return None

    def typography_edit(
        self,
        node_id: str,
        new_text: Optional[str] = None,
        font_size_pt: Optional[float] = None,
        color: Any = None,
        font_family: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cambia texto/tamaño/color/fuente de un span solo si otro texto queda intacto y cabe.

        Es una edición verificada de ida: se aplica en memoria, se compara cada span
        restante de la página y, solo si todos son idénticos, se escribe un PDF nuevo.
        """
        self._assert_original_unmodified()
        node = self.graph.get_node(node_id)
        if node is None or node.node_type != NodeType.TEXT.value:
            return {"ok": False, "code": "NOT_TEXT", "reason": "El nodo no es un texto editable."}
        if node.page is None or node.bbox is None:
            return {"ok": False, "code": "NO_GEOMETRY", "reason": "El texto no tiene página o caja."}
        doc = pymupdf.open(self.working_copy_path)
        try:
            page = doc[node.page]
            spans = self._spans(page)
            objetivo = None
            mejor_distancia = None
            for span in spans:
                bbox = span.get("bbox") or (0, 0, 0, 0)
                if str(span.get("text", "")) != node.text:
                    continue
                centro = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                nodo_centro = ((node.bbox[0] + node.bbox[2]) / 2, (node.bbox[1] + node.bbox[3]) / 2)
                distancia = abs(centro[0] - nodo_centro[0]) + abs(centro[1] - nodo_centro[1])
                if mejor_distancia is None or distancia < mejor_distancia:
                    objetivo = span
                    mejor_distancia = distancia
            if objetivo is None:
                return {"ok": False, "code": "SPAN_NOT_FOUND", "reason": "No se encontró el span exacto en el archivo de trabajo."}
            bbox = tuple(float(value) for value in objetivo["bbox"])
            texto = (new_text if new_text is not None else str(objetivo.get("text", ""))).strip()
            if not texto:
                return {"ok": False, "code": "EMPTY_TEXT", "reason": "El texto nuevo no puede quedar vacío."}
            tamano = float(font_size_pt) if font_size_pt is not None else float(objetivo.get("size", 11))
            if tamano < 4 or tamano > 300:
                return {"ok": False, "code": "SIZE_OUT_OF_RANGE", "reason": "El tamaño debe estar entre 4 y 300 pt."}
            fuente = self._font_name(font_family, str(objetivo.get("font", "")))
            color_rgb = self._color_rgb(color)
            ancho_disponible = max(0.0, bbox[2] - bbox[0])
            alto_disponible = max(0.0, bbox[3] - bbox[1])
            try:
                ancho_texto = pymupdf.Font(fontname=fuente).text_length(texto, tamano)
            except Exception:
                ancho_texto = pymupdf.get_text_length(texto, fontname=fuente, fontsize=tamano)
            if ancho_texto > ancho_disponible + 0.75:
                sugerido = max(4.0, min(tamano, tamano * (ancho_disponible / max(ancho_texto, 0.1))))
                return {
                    "ok": False,
                    "code": "TYPOGRAPHY_DOES_NOT_FIT",
                    "reason": f"El texto no cabe: necesita {ancho_texto:.1f} pt y hay {ancho_disponible:.1f} pt.",
                    "measured_width_pt": round(ancho_texto, 2),
                    "available_width_pt": round(ancho_disponible, 2),
                    "suggested_size_pt": round(sugerido, 1),
                }
            if tamano > alto_disponible * 1.45:
                return {
                    "ok": False,
                    "code": "TYPOGRAPHY_TOO_TALL",
                    "reason": f"El tamaño {tamano:.1f} pt no cabe en una caja de {alto_disponible:.1f} pt de alto.",
                    "available_height_pt": round(alto_disponible, 2),
                }
            antes = [self._span_signature(span) for span in spans if span is not objetivo]
            rect = pymupdf.Rect(bbox[0] - 0.4, bbox[1] - 0.4, bbox[2] + 0.4, bbox[3] + 0.4)
            page.add_redact_annot(rect, fill=False)
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
            origen = objetivo.get("origin") or (bbox[0], bbox[3] - max(1.0, (bbox[3] - bbox[1]) * 0.2))
            page.insert_text(
                (float(origen[0]), float(origen[1])),
                texto,
                fontname=fuente,
                fontsize=tamano,
                color=color_rgb or pymupdf.sRGB_to_pdf(int(objetivo.get("color", 0))),
                overlay=True,
            )
            despues_spans = self._spans(page)
            target_area = pymupdf.Rect(bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)
            despues = [
                self._span_signature(span)
                for span in despues_spans
                if not (str(span.get("text", "")).strip() == texto and target_area.contains(pymupdf.Rect(span["bbox"])))
            ]
            from collections import Counter
            if Counter(antes) != Counter(despues):
                return {
                    "ok": False,
                    "code": "NEIGHBORS_CHANGED",
                    "reason": "La edición habría cambiado otros objetos de texto de la página. No se guardó nada.",
                    "other_spans_before": len(antes),
                    "other_spans_after": len(despues),
                }
            salida = self._save_advanced(doc, "tipografia", f"{self.source_filename.rsplit('.', 1)[0]}-tipografia.pdf")
            doc = None
            salida.update({
                "others_unchanged": True,
                "target_span": {
                    "page": node.page + 1,
                    "bbox": [round(value, 2) for value in bbox],
                    "old_text": node.text,
                    "new_text": texto,
                    "font": fuente,
                    "size_pt": round(tamano, 2),
                    "color": "#" + "".join(f"{round(canal * 255):02x}" for canal in (color_rgb or pymupdf.sRGB_to_pdf(int(objetivo.get("color", 0))))),
                },
            })
            return salida
        finally:
            if doc is not None:
                doc.close()

    def annotate_document(
        self,
        page_number: int,
        kind: str,
        text: Optional[str] = None,
        image_data_url: Optional[str] = None,
        x: float = 72,
        y: float = 72,
        width: float = 240,
        height: Optional[float] = None,
        font_size_pt: float = 12,
        color: Any = None,
    ) -> Dict[str, Any]:
        """Añade texto o imagen en una capa de anotación; el archivo resultante es nuevo."""
        self._assert_original_unmodified()
        doc = pymupdf.open(self.working_copy_path)
        try:
            if page_number < 1 or page_number > doc.page_count:
                return {"ok": False, "code": "PAGE_OUT_OF_RANGE", "reason": "La página no existe."}
            page = doc[page_number - 1]
            ocg = doc.add_ocg("Prometeo · anotaciones", on=1)
            rect = pymupdf.Rect(x, y, x + max(20.0, width), y + max(20.0, height or max(20.0, font_size_pt * 2.2)))
            if rect.x1 > page.rect.width or rect.y1 > page.rect.height or rect.x0 < 0 or rect.y0 < 0:
                return {"ok": False, "code": "ANNOTATION_OUT_OF_PAGE", "reason": "La anotación cae fuera de la página."}
            if kind == "text":
                contenido = (text or "").strip()
                if not contenido:
                    return {"ok": False, "code": "EMPTY_TEXT", "reason": "La anotación de texto está vacía."}
                rgb = self._color_rgb(color) or (0.1, 0.1, 0.1)
                sobrante = page.insert_textbox(rect, contenido, fontsize=float(font_size_pt), fontname="helv", color=rgb, align=0, oc=ocg)
                if sobrante < 0:
                    return {"ok": False, "code": "ANNOTATION_DOES_NOT_FIT", "reason": "El texto no cabe en la caja indicada.", "overflow_pt": round(abs(sobrante), 2)}
            elif kind == "image":
                if not image_data_url or "," not in image_data_url:
                    return {"ok": False, "code": "MISSING_IMAGE", "reason": "Falta la imagen de la anotación."}
                try:
                    stream = base64.b64decode(image_data_url.split(",", 1)[1], validate=True)
                except Exception:
                    return {"ok": False, "code": "BAD_IMAGE", "reason": "La imagen no es base64 válido."}
                if len(stream) > 12 * 1024 * 1024:
                    return {"ok": False, "code": "IMAGE_TOO_LARGE", "reason": "La imagen supera 12 MB."}
                page.insert_image(rect, stream=stream, keep_proportion=True, overlay=True, oc=ocg)
            else:
                return {"ok": False, "code": "UNKNOWN_ANNOTATION", "reason": "Tipo de anotación no soportado."}
            salida = self._save_advanced(doc, "anotacion", f"{self.source_filename.rsplit('.', 1)[0]}-anotado.pdf")
            doc = None
            salida.update({"layer": "Prometeo · anotaciones", "page": page_number, "kind": kind})
            return salida
        finally:
            if doc is not None:
                doc.close()

    def organize_pages(
        self,
        order: Optional[List[int]] = None,
        rotate: Optional[List[Dict[str, Any]]] = None,
        delete: Optional[List[int]] = None,
        merge: Optional[List[str]] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reordena, rota, quita y une PDFs; siempre produce un archivo nuevo."""
        self._assert_original_unmodified()
        doc = pymupdf.open(self.working_copy_path)
        try:
            for data_url in merge or []:
                if not data_url or "," not in data_url:
                    return {"ok": False, "code": "BAD_MERGE", "reason": "Un PDF para unir no llegó como data URL."}
                try:
                    stream = base64.b64decode(data_url.split(",", 1)[1], validate=True)
                except Exception:
                    return {"ok": False, "code": "BAD_MERGE", "reason": "El PDF para unir no es base64 válido."}
                if len(stream) > 200 * 1024 * 1024:
                    return {"ok": False, "code": "MERGE_TOO_LARGE", "reason": "El PDF para unir supera 200 MB."}
                with pymupdf.open(stream=stream, filetype="pdf") as otro:
                    doc.insert_pdf(otro)
            for numero in sorted(set(delete or []), reverse=True):
                if 1 <= numero <= doc.page_count:
                    doc.delete_page(numero - 1)
            for item in rotate or []:
                numero = int(item.get("page", 0))
                grados = int(item.get("degrees", 0))
                if 1 <= numero <= doc.page_count and grados % 90 == 0:
                    page = doc[numero - 1]
                    page.set_rotation((page.rotation + grados) % 360)
            if order:
                if sorted(order) != list(range(1, doc.page_count + 1)):
                    return {"ok": False, "code": "BAD_ORDER", "reason": "El orden debe incluir cada página existente exactamente una vez."}
                nuevo = pymupdf.open()
                for numero in order:
                    nuevo.insert_pdf(doc, from_page=numero - 1, to_page=numero - 1)
                doc.close()
                doc = nuevo
            salida = self._save_advanced(doc, "paginas", filename or f"{self.source_filename.rsplit('.', 1)[0]}-paginas.pdf")
            doc = None
            salida.update({"pages": len(order) if order else None})
            return salida
        finally:
            if doc is not None:
                doc.close()

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORTACIÓN VERIFICADA: PREPARE → STAGING → VERIFY → PUBLISH (PA-002/003/004)
    # ─────────────────────────────────────────────────────────────────────────

    def _staging_path(self, transaction_id: str, filename: str) -> str:
        staging_dir = os.path.join(self.session_dir, "staging", transaction_id)
        os.makedirs(staging_dir, mode=0o700, exist_ok=True)
        return os.path.join(staging_dir, filename)

    def _output_filename(self, output_filename: Optional[str]) -> str:
        base_name, _ = os.path.splitext(self.source_filename)
        return sanitize_filename(output_filename or f"{base_name}.prometeo-v1.pdf")

    def _finish(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Registra el resultado y comprueba (no supone) que el original no cambió."""
        self.transaction_state = result["transaction_state"]
        self.last_verifier_result = result["verifier_result"]
        self._assert_original_unmodified()
        # La interfaz solo muestra "su original no cambió" cuando este campo es True.
        result["original_unchanged"] = True
        result["original_sha256"] = self.source_sha256
        return result

    def save_verified_copy(self, target_dir: str) -> Dict[str, Any]:
        """Copia la salida verificada a una carpeta del usuario sin sobrescribir nada."""
        rec = self.get_verified_output()
        if rec is None:
            return {"ok": False, "error_code": "OUTPUT_NOT_VERIFIED",
                    "error": "No hay una copia verificada que guardar."}
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error_code": "SAVE_PERMISSION_DENIED" if e.errno in (1, 13) else "SAVE_FAILED",
                    "error": f"No se pudo crear la carpeta de destino: {e.strerror}"}
        base, ext = os.path.splitext(rec["filename"])
        candidate = os.path.join(target_dir, rec["filename"])
        n = 2
        while os.path.exists(candidate):
            candidate = os.path.join(target_dir, f"{base} ({n}){ext}")
            n += 1
        try:
            shutil.copyfile(rec["path"], candidate)
        except OSError as e:
            return {"ok": False, "error_code": "SAVE_PERMISSION_DENIED" if e.errno in (1, 13) else "SAVE_FAILED",
                    "error": f"No se pudo guardar el archivo: {e.strerror}"}
        digest = xp.sha256_path(candidate)
        if digest != rec["sha256"]:
            xp.discard(candidate)
            return {"ok": False, "error_code": "SAVE_FAILED", "error": "La copia guardada no coincide con la verificada."}
        self.saved_outputs.append(candidate)
        return {"ok": True, "path": candidate, "filename": os.path.basename(candidate),
                "folder": target_dir, "sha256": digest, "original_unchanged": self.original_is_unmodified()}

    def _publish_verified(self, staging_path: str, filename: str, result: Dict[str, Any],
                          transaction_id: str) -> Dict[str, Any]:
        verified_dir = os.path.join(self.session_dir, "verified", transaction_id)
        record = xp.publish(staging_path, verified_dir, filename)
        record.update({
            "transaction_id": transaction_id,
            "verdict": xp.VERDICT_PASS,
            "verifier_profile": result["verifier_result"].get("verifier_profile"),
        })
        self.published_output = record
        self.last_exported_path = record["path"]
        self.last_exported_filename = filename
        result["published"] = True
        result["output_filename"] = filename
        result["exported_filename"] = filename
        result["output_sha256"] = record["sha256"]
        return result

    def get_verified_output(self) -> Optional[Dict[str, Any]]:
        """Devuelve la salida publicada solo si sigue verificada e intacta en disco."""
        rec = self.published_output
        if not rec or self.transaction_state != xp.STATE_VERIFIED:
            return None
        if not os.path.isfile(rec["path"]) or xp.sha256_path(rec["path"]) != rec["sha256"]:
            return None
        return rec

    def verify_and_export(self, output_filename: Optional[str] = None) -> Dict[str, Any]:
        """Exporta una copia nueva y la publica únicamente si un verificador real la aprueba."""
        if not self.staged_operations:
            return xp.reject(xp.CODE_NO_STAGED, "No hay operaciones preparadas en la transacción.")

        self._assert_original_unmodified()
        # Un nuevo intento invalida cualquier salida publicada antes.
        self.published_output = None
        self.last_exported_path = None
        self.last_exported_filename = None
        self.last_diff = None

        kinds = xp.transaction_kinds(self.staged_operations)
        if len(kinds) > 1:
            return self._finish(xp.reject(
                xp.CODE_MIXED,
                "La transacción mezcla ediciones raster y de texto nativo. Esa combinación no se puede "
                "verificar como una unidad; no se exportó nada y no se descartó ninguna operación.",
            ))

        out_name = self._output_filename(output_filename)
        if kinds == {xp.OP_KIND_RASTER}:
            return self._verify_and_export_raster(out_name)
        return self._verify_and_export_vector(out_name)

    def _verify_and_export_raster(self, out_name: str) -> Dict[str, Any]:
        tx_id = f"rtx_{uuid.uuid4().hex[:12]}"
        self.active_transaction_id = tx_id
        raster_ops = [op["raster_op"] for op in self.staged_operations]
        with open(self.working_copy_path, "rb") as f:
            source_bytes = f.read()

        result, out_bytes = xp.run_raster_transaction(
            source_bytes,
            raster_ops,
            apply_fn=self._raster_apply_fn,
            verify_fn=self._raster_verify_loader(),
            semantic_available=self._semantic_authority_check(),
        )
        result["verifier_result"]["transaction_id"] = tx_id
        if not result["ok"] or out_bytes is None:
            return self._finish(result)

        staging_path = self._staging_path(tx_id, out_name)
        with open(staging_path, "wb") as f:
            f.write(out_bytes)
        if xp.sha256_path(staging_path) != xp.sha256_bytes(out_bytes):
            xp.discard(staging_path)
            return self._finish(xp.reject(xp.CODE_EXPORT_FAILED, "El archivo exportado no coincide con el verificado."))

        self._publish_verified(staging_path, out_name, result, tx_id)
        if hasattr(self, "_ocr_cache"):
            self._ocr_cache.clear()
        g_after = build_docgraph(self.published_output["path"], docgraph_version=self.docgraph_version)
        self.last_diff = docgraph_diff(self.graph, g_after)
        result["diff"] = self.last_diff
        return self._finish(result)

    def _verify_and_export_vector(self, out_name: str) -> Dict[str, Any]:
        # 1. Preparar operaciones para el Tool Contract (texto vectorial)
        tx_ops = []
        for op in self.staged_operations:
            entry = {"new_text": op["new_text"]}
            if op.get("target_id"):
                entry["target_id"] = op["target_id"]
            if op.get("node_id"):
                entry["node_id"] = op["node_id"]
            tx_ops.append(entry)

        # 2. Stage en el Core
        stage_res = self.tools.stage_transaction(
            document_id=self.document_id,
            operations=tx_ops,
            policy="ATOMIC",
        )
        if not stage_res.get("ok"):
            return self._finish(xp.reject(
                xp.CODE_CORE_REJECTED,
                stage_res.get("error", "Transacción rechazada por el Core."),
                details=[stage_res],
            ))

        tx_id = stage_res["transaction_id"]
        self.active_transaction_id = tx_id
        staging_path = self._staging_path(tx_id, out_name)

        # 3. Exportar a staging (nunca sobre el original ni al área publicada)
        exp_res = self.tools.export_transaction(
            document_id=self.document_id,
            transaction_id=tx_id,
            destination=staging_path,
        )
        if not exp_res.get("ok") or not os.path.isfile(staging_path):
            xp.discard(staging_path)
            return self._finish(xp.reject(
                xp.CODE_EXPORT_FAILED,
                exp_res.get("error") or "La exportación no produjo un archivo.",
                details=[exp_res], transaction_id=tx_id,
            ))

        # 4. Verificador físico: única autoridad
        try:
            ver_res = self.tools.verify_transaction(document_id=self.document_id, transaction_id=tx_id)
        except Exception as e:
            xp.discard(staging_path)
            return self._finish(xp.reject(
                xp.CODE_VERIFIER_ERROR,
                f"El verificador falló durante la verificación ({type(e).__name__}); no se aprueba nada.",
                transaction_id=tx_id,
            ))
        verdict = ver_res.get("verdict") if isinstance(ver_res, dict) else None
        if verdict not in (xp.VERDICT_PASS, xp.VERDICT_FAILED, "HONEST_REJECT", "AMBIGUOUS", "REJECTED"):
            xp.discard(staging_path)
            return self._finish(xp.reject(
                xp.CODE_VERIFIER_ERROR, "El verificador devolvió un resultado no interpretable.",
                details=[ver_res] if isinstance(ver_res, dict) else [], transaction_id=tx_id,
            ))

        if not (ver_res.get("ok") and verdict == xp.VERDICT_PASS):
            xp.discard(staging_path)
            return self._finish(xp.failed(
                xp.CODE_VERIFICATION_FAILED,
                "La verificación física del documento exportado no alcanzó conformidad.",
                details=[ver_res], transaction_id=tx_id,
                operations_verified=int(ver_res.get("operations_verified", 0) or 0),
            ))

        result = xp.outcome(
            ok=True, state=xp.STATE_VERIFIED, verdict=xp.VERDICT_PASS, code=None,
            reason="Verifier2 aprobó todas las operaciones sobre el archivo exportado.",
            verifier_executed=True,
            operations_verified=len(self.staged_operations),
            details=[ver_res], verifier_profile="VERIFIER2_VECTOR_TEXT", transaction_id=tx_id,
        )
        self._publish_verified(staging_path, out_name, result, tx_id)

        # 5. DocGraphDiff estructural sobre el archivo publicado
        g_after = build_docgraph(self.published_output["path"], docgraph_version=self.docgraph_version)
        self.last_diff = docgraph_diff(self.graph, g_after)
        summary = self.last_diff.get("summary", {})
        self.last_diff["is_identical"] = (
            summary.get("changed_count", 0) == 0
            and summary.get("added_count", 0) == 0
            and summary.get("removed_count", 0) == 0
        )
        result["diff"] = self.last_diff
        return self._finish(result)

    def get_diff(self) -> Optional[Dict[str, Any]]:
        """Retorna el último DocGraphDiff calculado si existe."""
        return self.last_diff

    def original_is_unmodified(self) -> bool:
        """Comprobación real (no supuesta) de que el original conserva su digest."""
        try:
            return sha256_file(self.source_path) == self.source_sha256
        except OSError:
            return False

    def get_version_manifest(self) -> Dict[str, Any]:
        """Manifiesto de versión: solo describe una salida si fue verificada y publicada."""
        rec = self.get_verified_output()
        return {
            "source_filename": self.source_filename,
            "source_sha256": self.source_sha256,
            "output_filename": rec["filename"] if rec else None,
            "output_sha256": rec["sha256"] if rec else None,
            "output_published_at": rec["published_at"] if rec else None,
            "transaction_id": getattr(self, "active_transaction_id", None),
            "verification_status": self.transaction_state,
            "verifier_profile": rec.get("verifier_profile") if rec else None,
            "generated_at": xp.utc_now(),
            "docgraph_version": self.docgraph_version,
            "prometeo_version": PROMETEO_VERSION,
        }

    def get_audit_export(self) -> Dict[str, Any]:
        """Reporte de verificación e historial transaccional con comprobaciones reales."""
        return {
            "manifest": self.get_version_manifest(),
            "transaction_state": self.transaction_state,
            "verifier_result": self.last_verifier_result,
            "diff_summary": self.last_diff.get("summary") if self.last_diff else None,
            "staged_operations_count": len(self.staged_operations),
            "original_immutable": self.original_is_unmodified(),
            "original_check": "sha256 recomputed at request time",
        }

    def close(self) -> None:
        """Cierra la sesión: comprueba el original y borra los archivos de la sesión."""
        self._assert_original_unmodified()
        self.is_active = False


class StudioSessionManager:
    """Gestiona el repositorio central de sesiones de Studio con aislamiento y seguridad."""

    def __init__(self, workspace_root: Optional[str] = None, instance_id: Optional[str] = None):
        if workspace_root is None:
            info = ws.resolve_workspace()
            if not info.ok:
                raise WorkspaceUnavailableError(info)
            workspace_root = info.root
        if ws.is_inside_app_bundle(workspace_root):
            raise WorkspaceUnavailableError(ws.WorkspaceInfo(
                ok=False, root=None, source=None,
                errors=["el workspace no puede estar dentro de un paquete .app"]))
        self.workspace_root = os.path.abspath(workspace_root)
        self.instance_id = instance_id or ws.new_instance_id()
        self.instance_root = os.path.join(self.workspace_root, "instances", self.instance_id)
        self.sessions_root = os.path.join(self.instance_root, "sessions")
        self.sessions: Dict[str, StudioDocumentSession] = {}
        os.makedirs(self.sessions_root, mode=0o700, exist_ok=True)
        # Sesiones de procesos que ya terminaron (cierre abrupto) no se acumulan.
        self.purged_instances = ws.purge_dead_instances(self.workspace_root, self.instance_id)

    def create_session_from_upload(self, file_bytes: bytes, filename: str) -> StudioDocumentSession:
        """Crea una nueva sesión a partir de un archivo PDF cargado por el usuario."""
        clean_name = sanitize_filename(filename)
        sess_id = f"studio_sess_{uuid.uuid4().hex[:12]}"

        sess_dir = os.path.join(self.sessions_root, sess_id)
        uploads_dir = os.path.join(sess_dir, "uploads")
        work_dir = os.path.join(sess_dir, "working_copy")
        os.makedirs(uploads_dir, mode=0o700, exist_ok=True)
        os.makedirs(work_dir, mode=0o700, exist_ok=True)

        source_path = os.path.join(uploads_dir, clean_name)
        working_path = os.path.join(work_dir, clean_name)

        # Escribir copia inmutable
        with open(source_path, "wb") as f:
            f.write(file_bytes)

        # Filtro de PDFs no confiables (CAMP-002 · F5): análisis completo en un subproceso con
        # límites ANTES de que el motor lo toque. Si falla, se borra todo lo escrito.
        try:
            gate = pdf_gate.preflight_cached(source_path, hashlib.sha256(file_bytes).hexdigest())
        except BaseException:
            # El propio filtro falló (p. ej. no pudo lanzar el subproceso): no se deja la copia.
            shutil.rmtree(sess_dir, ignore_errors=True)
            raise
        if not gate.ok:
            shutil.rmtree(sess_dir, ignore_errors=True)
            raise pdf_gate.PdfRejected(gate)

        # Escribir copia de trabajo
        with open(working_path, "wb") as f:
            f.write(file_bytes)

        sha = sha256_file(source_path)

        try:
            session = StudioDocumentSession(
                session_id=sess_id,
                source_filename=clean_name,
                source_path=source_path,
                working_copy_path=working_path,
                source_sha256=sha,
                session_dir=sess_dir,
            )
        except BaseException:
            shutil.rmtree(sess_dir, ignore_errors=True)
            raise
        self.sessions[sess_id] = session
        return session

    def create_session_from_sample(self, sample_key: str) -> StudioDocumentSession:
        """Crea una sesión copiando de forma inmutable una muestra autorizada del repositorio."""
        if sample_key not in AUTHORIZED_SAMPLES:
            raise ValueError(f"Muestra desconocida: {sample_key}. Disponibles: {list(AUTHORIZED_SAMPLES.keys())}")

        orig_path = AUTHORIZED_SAMPLES[sample_key]
        if not os.path.isfile(orig_path):
            raise FileNotFoundError(f"Archivo de muestra no encontrado en el host: {orig_path}")

        with open(orig_path, "rb") as f:
            content = f.read()

        filename = os.path.basename(orig_path)
        return self.create_session_from_upload(content, filename)

    def get_session(self, session_id: str) -> Optional[StudioDocumentSession]:
        sess = self.sessions.get(session_id)
        if sess and sess.is_active:
            return sess
        return None

    def close_session(self, session_id: str) -> bool:
        """Cierra la sesión y elimina sus archivos (copias, exportaciones, temporales)."""
        sess = self.sessions.pop(session_id, None)
        if not sess:
            return False
        try:
            sess.close()
        finally:
            ws.remove_tree_within(sess.session_dir, self.sessions_root)
        return True

    def shutdown(self) -> None:
        """Cierre ordenado del proceso: borra la carpeta de esta instancia."""
        for sid in list(self.sessions):
            try:
                self.close_session(sid)
            except Exception:
                pass
        ws.remove_tree_within(self.instance_root, os.path.join(self.workspace_root, "instances"))
