"""PROMETEO · TOOL CONTRACT v0.2 (PROMETEO-DG-CAMP-0001)
────────────────────────────────────────────────────────────
Capa de herramientas desacoplada para agentes autónomos.
Evolucionada para integrar Document Scene Graph (DocGraph v0.2) y transacciones
multi-operación atómicas (Batch v0.1), conservando 100% de compatibilidad hacia atrás
con el contrato v0.1.

PRINCIPIO FUNDAMENTAL:
  MODEL ≠ PROMETEO
  El LLM NO recibe permiso para afirmar que una operación fue exitosa.
  Solo el Verifier post-exportación puede producir PASS.

INVARIANTE OBLIGATORIO:
  SILENT_FAILURE == 0

ESTADOS DE RESULTADO:
  PASS
  HONEST_REJECT
  AMBIGUOUS
  CRASH
  SILENT_FAILURE
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pymupdf

# Soporte de importación tanto desde raíz como desde fase0/
try:
    from engine import (
        ORIGIN_TOLERANCE_PT,
        _font_identity_match,
        _norm_text,
        all_spans,
        export_version,
        extract,
        sha256_bytes,
        sha256_file,
        span_by_id,
        verify_output,
    )
    from operations import DEFAULT_POLICY_ORDER, ReplaceText, Verdict, validate_replace
    from render import FontBook, apply_replace
    import verifier2
except ImportError:
    from fase0.engine import (
        ORIGIN_TOLERANCE_PT,
        _font_identity_match,
        _norm_text,
        all_spans,
        export_version,
        extract,
        sha256_bytes,
        sha256_file,
        span_by_id,
        verify_output,
    )
    from fase0.operations import DEFAULT_POLICY_ORDER, ReplaceText, Verdict, validate_replace
    from fase0.render import FontBook, apply_replace
    from fase0 import verifier2

# Integración DocGraph y Transacciones
import docgraph
from docgraph import (
    DocGraph,
    GLOBAL_DOCGRAPH_CACHE,
    get_document_outline_context,
    get_document_summary,
    get_node_neighbors,
    get_node_window,
)

try:
    from transactions import TransactionManager, TransactionPolicy, TransactionState
except ImportError:
    from fase0.transactions import TransactionManager, TransactionPolicy, TransactionState


class ResultState(str, Enum):
    """Estados formales del contrato PROMETEO-TOOLS."""
    PASS = "PASS"
    HONEST_REJECT = "HONEST_REJECT"
    AMBIGUOUS = "AMBIGUOUS"
    CRASH = "CRASH"
    SILENT_FAILURE = "SILENT_FAILURE"
    # Estados de transición del pipeline (nunca finales de éxito)
    OPENED = "OPENED"
    INSPECTED = "INSPECTED"
    RESOLVED = "RESOLVED"
    STAGED = "STAGED"
    EXPORTED = "EXPORTED"


@dataclass
class OperationProvenance:
    """Registro de provenance para mutación documental (v0.2)."""
    operation_id: str
    document_id: str
    source_document_hash: str
    page: int
    target: str
    requested_action: str
    requested_value: str
    resolved_target: Dict[str, Any]
    engine_version: str
    timestamp: str
    result_state: str
    verifier_result: Optional[Dict[str, Any]] = None
    output_hash: Optional[str] = None
    # Metadatos v0.2
    source_node_id: Optional[str] = None
    source_docgraph_version: str = "0.2"
    source_bbox: Optional[List[float]] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "document_id": self.document_id,
            "source_document_hash": self.source_document_hash,
            "page": self.page,
            "target": self.target,
            "requested_action": self.requested_action,
            "requested_value": self.requested_value,
            "resolved_target": self.resolved_target,
            "engine_version": self.engine_version,
            "timestamp": self.timestamp,
            "result_state": self.result_state,
            "verifier_result": self.verifier_result,
            "output_hash": self.output_hash,
            "source_node_id": self.source_node_id,
            "source_docgraph_version": self.source_docgraph_version,
            "source_bbox": self.source_bbox,
        }


class DocumentSession:
    """Sesión en memoria para un documento cargado."""

    def __init__(self, document_id: str, source_path: str, source_sha256: str, model: Dict[str, Any]):
        self.document_id = document_id
        self.source_path = os.path.abspath(source_path)
        self.source_sha256 = source_sha256
        self.model = model
        self.candidates: Dict[str, Dict[str, Any]] = {}
        self.targets: Dict[str, Dict[str, Any]] = {}
        self.staged_operations: List[Dict[str, Any]] = []
        self.exported_destination: Optional[str] = None
        self.output_sha256: Optional[str] = None
        # Campos v0.2 para DocGraph
        self.graph: Optional[DocGraph] = None
        self.target_bindings: Dict[str, Any] = {}
        self.shadow_divergences: List[Dict[str, Any]] = []


class PrometeoTools:
    """Capa de herramientas v0.2 de PROMETEO.
    
    Compatible con vertical slice v0.1 y extendida con herramientas estructurales
    de navegación compacta y transacciones atómicas multi-operación.
    """

    ENGINE_VERSION = "prometeo_v0.1_tools"
    TOOL_CONTRACT_VERSION = "0.2"

    def __init__(self):
        self.sessions: Dict[str, DocumentSession] = {}
        self.operations: Dict[str, OperationProvenance] = {}
        self.op_metadata: Dict[str, Dict[str, Any]] = {}
        self.transaction_manager = TransactionManager()
        self.docgraph_cache = GLOBAL_DOCGRAPH_CACHE

    # ─────────────────────────────────────────────────────────────
    # 1. open_document (v0.1 + v0.2 DocGraph Cache binding)
    # ─────────────────────────────────────────────────────────────
    def open_document(self, path: str, docgraph_version: Optional[str] = None) -> Dict[str, Any]:
        """Abre un documento original, extrae su modelo espacial y
        registra su identidad criptográfica sin alterar el archivo original.

        `docgraph_version`: versión del DocGraph a usar (por defecto, la de la caché). Studio pasa
        la misma versión que su sesión para compartir un único grafo en la caché, en lugar de
        construir dos (CAMP-002 · F4: 73 págs, 9,4 s de 11,2 s eran dos construcciones)."""
        try:
            if not os.path.isfile(path):
                return {
                    "ok": False,
                    "result_state": ResultState.HONEST_REJECT.value,
                    "error": f"El archivo no existe o no es accesible: {path}",
                }

            abs_path = os.path.abspath(path)
            src_sha256 = sha256_file(abs_path)
            doc_id = f"doc_{src_sha256[:16]}"

            # Extraer modelo espacial usando el Core
            model = extract(abs_path)

            session = DocumentSession(
                document_id=doc_id,
                source_path=abs_path,
                source_sha256=src_sha256,
                model=model,
            )

            # Integración DocGraph v0.2 con caché transparente
            graph, was_cached = self.docgraph_cache.get_or_build(abs_path, version=docgraph_version)
            session.graph = graph

            self.sessions[doc_id] = session

            return {
                "ok": True,
                "document_id": doc_id,
                "source_path": abs_path,
                "source_sha256": src_sha256,
                "pages_count": len(model["pages"]),
                "docgraph_cached": was_cached,
                "docgraph_nodes_count": len(graph.nodes),
                "result_state": ResultState.OPENED.value,
                "message": f"Documento {doc_id} cargado e indexado correctamente.",
            }
        except Exception as e:
            return {
                "ok": False,
                "result_state": ResultState.CRASH.value,
                "error": f"Fallo al abrir documento: {str(e)}",
            }

    # ─────────────────────────────────────────────────────────────
    # 2. inspect_document (v0.1)
    # ─────────────────────────────────────────────────────────────
    def inspect_document(self, document_id: str) -> Dict[str, Any]:
        """Devuelve un resumen tipado y estructurado de la estructura espacial,
        páginas, dimensiones y fuentes presentes en el documento."""
        session = self.sessions.get(document_id)
        if session is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"document_id no encontrado: {document_id}",
            }

        pages_summary = []
        all_fonts = set()
        total_spans = 0

        for page in session.model["pages"]:
            page_fonts = set(s["font"] for s in page["spans"])
            all_fonts.update(page_fonts)
            total_spans += len(page["spans"])
            pages_summary.append({
                "page_number": page["number"],
                "width_pt": round(page["width_pt"], 2),
                "height_pt": round(page["height_pt"], 2),
                "rotation": page["rotation"],
                "spans_count": len(page["spans"]),
                "fonts": sorted(page_fonts),
            })

        return {
            "ok": True,
            "document_id": document_id,
            "source_sha256": session.source_sha256,
            "pages_count": len(session.model["pages"]),
            "pages": pages_summary,
            "total_spans": total_spans,
            "fonts_present": sorted(all_fonts),
            "staged_operations_count": len(session.staged_operations),
            "result_state": ResultState.INSPECTED.value,
        }

    # ─────────────────────────────────────────────────────────────
    # 3. find_text (v0.1 + Shadow Mode / Node Binding)
    # ─────────────────────────────────────────────────────────────
    def find_text(
        self,
        document_id: str,
        query: str,
        page: Optional[int] = None,
        case_sensitive: bool = True,
    ) -> Dict[str, Any]:
        """Busca texto en el documento espacial. Si existen múltiples coincidencias,
        emite estado AMBIGUOUS con lista de candidatos para desambiguación obligatoria.
        
        En v0.2: vincula de forma transparente cada candidato con su node_id estructural.
        """
        session = self.sessions.get(document_id)
        if session is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"document_id no encontrado: {document_id}",
            }

        if not query:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": "La consulta de texto (query) no puede estar vacía.",
            }

        candidates = []
        match_idx = 0

        for p in session.model["pages"]:
            if page is not None and p["number"] != page:
                continue
            for span in p["spans"]:
                span_text = span["text"] if case_sensitive else span["text"].lower()
                q_text = query if case_sensitive else query.lower()
                if q_text in span_text:
                    cand_id = f"cand_p{span['page']}_{span['id']}_{match_idx}"
                    cand = {
                        "candidate_id": cand_id,
                        "page": span["page"],
                        "span_id": span["id"],
                        "text": span["text"],
                        "matched_query": query,
                        "bbox": list(span["bbox"]),
                        "origin": list(span["origin"]),
                        "font": span["font"],
                        "size": span["size"],
                        "clearance_pt": span["clearance_pt"],
                    }
                    candidates.append(cand)
                    session.candidates[cand_id] = cand
                    match_idx += 1

        # Shadow mode comparison with DocGraph
        if session.graph:
            dg_matches = session.graph.find_text_nodes(query, page=page, case_sensitive=case_sensitive)
            if len(dg_matches) != len(candidates):
                session.shadow_divergences.append({
                    "query": query,
                    "legacy_count": len(candidates),
                    "dg_count": len(dg_matches),
                })
            # Vincular node_id a cada candidato coincidente
            for i, cand in enumerate(candidates):
                if i < len(dg_matches):
                    cand["node_id"] = dg_matches[i].node_id

        if len(candidates) == 0:
            return {
                "ok": False,
                "status": "NOT_FOUND",
                "result_state": ResultState.HONEST_REJECT.value,
                "document_id": document_id,
                "query": query,
                "count": 0,
                "candidates": [],
                "message": f"Texto no encontrado: {query!r}",
            }
        elif len(candidates) > 1:
            return {
                "ok": True,
                "status": "AMBIGUOUS",
                "result_state": ResultState.AMBIGUOUS.value,
                "document_id": document_id,
                "query": query,
                "count": len(candidates),
                "candidates": candidates,
                "message": f"Coincidencia AMBIGUA: se encontraron {len(candidates)} candidatos. Requiere select_target explícito.",
            }
        else:
            return {
                "ok": True,
                "status": "UNIQUE",
                "result_state": "UNIQUE",
                "document_id": document_id,
                "query": query,
                "count": 1,
                "candidates": candidates,
                "candidate_id": candidates[0]["candidate_id"],
                "node_id": candidates[0].get("node_id"),
                "message": f"Candidato único identificado: {candidates[0]['candidate_id']}.",
            }

    # ─────────────────────────────────────────────────────────────
    # 4. select_target (v0.1 + Node Binding)
    # ─────────────────────────────────────────────────────────────
    def select_target(self, document_id: str, candidate_id: str) -> Dict[str, Any]:
        """Resuelve inequívocamente un candidato seleccionado como objetivo de mutación."""
        session = self.sessions.get(document_id)
        if session is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"document_id no encontrado: {document_id}",
            }

        cand = session.candidates.get(candidate_id)
        if cand is None:
            return {
                "ok": False,
                "status": "AMBIGUOUS",
                "result_state": ResultState.AMBIGUOUS.value,
                "target_id": None,
                "error": f"candidate_id desconocido o ambiguo: {candidate_id}",
            }

        target_id = f"target_{cand['span_id']}"
        cand["target_id"] = target_id
        session.targets[target_id] = cand

        # Registrar binding explícito
        if cand.get("node_id"):
            session.target_bindings[target_id] = {
                "node_id": cand["node_id"],
                "candidate_id": candidate_id,
                "target_id": target_id,
                "span_id": cand["span_id"],
                "document_id": document_id,
            }

        return {
            "ok": True,
            "status": "RESOLVED",
            "result_state": ResultState.RESOLVED.value,
            "document_id": document_id,
            "target_id": target_id,
            "candidate_id": candidate_id,
            "node_id": cand.get("node_id"),
            "page": cand["page"],
            "span_id": cand["span_id"],
            "current_text": cand["text"],
            "bbox": cand["bbox"],
            "font": cand["font"],
            "clearance_pt": cand["clearance_pt"],
        }

    # ─────────────────────────────────────────────────────────────
    # 5. replace_text (v0.1 + Provenance v0.2)
    # ─────────────────────────────────────────────────────────────
    def replace_text(
        self,
        document_id: str,
        target_id: str,
        new_value: str,
        policy_preference: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Valida rigurosamente la sustitución antes de mutar."""
        session = self.sessions.get(document_id)
        if session is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"document_id no encontrado: {document_id}",
            }

        cand = session.targets.get(target_id)
        if cand is None:
            return {
                "ok": False,
                "status": "AMBIGUOUS",
                "result_state": ResultState.AMBIGUOUS.value,
                "operation_id": None,
                "mutated": False,
                "error": f"El objetivo {target_id!r} es ambiguo o no fue resuelto previamente. Mutación bloqueada.",
            }

        span = span_by_id(session.model, cand["span_id"])
        if span is None:
            return {
                "ok": False,
                "status": "HONEST_REJECT",
                "result_state": ResultState.HONEST_REJECT.value,
                "operation_id": None,
                "mutated": False,
                "error": "Span objetivo no encontrado en el modelo espacial.",
            }

        # Verificar si el target ya fue asignado en otra operación
        for staged in session.staged_operations:
            if staged["span"]["id"] == span["id"]:
                return {
                    "ok": False,
                    "status": "HONEST_REJECT",
                    "result_state": ResultState.HONEST_REJECT.value,
                    "operation_id": None,
                    "mutated": False,
                    "error": "El objetivo ya fue modificado en esta sesión.",
                }

        # Validación geométrica y tipográfica previa
        doc = pymupdf.open(session.source_path)
        fb = FontBook(doc, doc[span["page"]])

        fchk = fb.check_font_for_edit(span, new_value)
        if not fchk["usable"]:
            doc.close()
            op_id = f"op_rej_{session.source_sha256[:8]}_{target_id}_{len(session.staged_operations)+1}"
            prov = OperationProvenance(
                operation_id=op_id,
                document_id=document_id,
                source_document_hash=session.source_sha256,
                page=span["page"],
                target=target_id,
                requested_action="replace_text",
                requested_value=new_value,
                resolved_target={
                    "span_id": span["id"],
                    "page": span["page"],
                    "text": span["text"],
                    "font": span["font"],
                    "node_id": cand.get("node_id"),
                },
                engine_version=self.ENGINE_VERSION,
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                result_state=ResultState.HONEST_REJECT.value,
                source_node_id=cand.get("node_id"),
                source_docgraph_version=session.graph.docgraph_version if session.graph else "0.2",
                source_bbox=list(span["bbox"]),
            )
            self.operations[op_id] = prov
            return {
                "ok": False,
                "status": "HONEST_REJECT",
                "result_state": ResultState.HONEST_REJECT.value,
                "operation_id": op_id,
                "mutated": False,
                "reason": "FONT_UNUSABLE",
                "details": fchk["reason"],
            }

        # Validación con motor operations
        op = ReplaceText(
            target_span_id=span["id"],
            old_text=span["text"],
            new_text=new_value,
            policy_preference=policy_preference or DEFAULT_POLICY_ORDER,
        )
        verdict = validate_replace(op, span, measure=fb.measure, resolve=fb.resolve)
        doc.close()

        if not verdict.ok:
            op_id = f"op_rej_{session.source_sha256[:8]}_{target_id}_{len(session.staged_operations)+1}"
            prov = OperationProvenance(
                operation_id=op_id,
                document_id=document_id,
                source_document_hash=session.source_sha256,
                page=span["page"],
                target=target_id,
                requested_action="replace_text",
                requested_value=new_value,
                resolved_target={
                    "span_id": span["id"],
                    "page": span["page"],
                    "text": span["text"],
                    "font": span["font"],
                    "node_id": cand.get("node_id"),
                },
                engine_version=self.ENGINE_VERSION,
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                result_state=ResultState.HONEST_REJECT.value,
                source_node_id=cand.get("node_id"),
                source_docgraph_version=session.graph.docgraph_version if session.graph else "0.2",
                source_bbox=list(span["bbox"]),
            )
            self.operations[op_id] = prov
            return {
                "ok": False,
                "status": "HONEST_REJECT",
                "result_state": ResultState.HONEST_REJECT.value,
                "operation_id": op_id,
                "mutated": False,
                "reason": verdict.reason,
                "policy_attempted": verdict.policy,
                "error": f"Rechazo honesto: la operación no cumple el clearance disponible ({verdict.reason}).",
            }

        # Operación validada: preparación (STAGED)
        op_id = f"op_{session.source_sha256[:8]}_{target_id}_{len(session.staged_operations)+1}"
        staged_item = {
            "operation_id": op_id,
            "target_id": target_id,
            "node_id": cand.get("node_id"),
            "op": op,
            "span": span,
            "verdict": verdict,
            "new_value": new_value,
        }
        session.staged_operations.append(staged_item)

        prov = OperationProvenance(
            operation_id=op_id,
            document_id=document_id,
            source_document_hash=session.source_sha256,
            page=span["page"],
            target=target_id,
            requested_action="replace_text",
            requested_value=new_value,
            resolved_target={
                "span_id": span["id"],
                "page": span["page"],
                "text": span["text"],
                "font": span["font"],
                "node_id": cand.get("node_id"),
            },
            engine_version=self.ENGINE_VERSION,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            result_state=ResultState.STAGED.value,
            source_node_id=cand.get("node_id"),
            source_docgraph_version=session.graph.docgraph_version if session.graph else "0.2",
            source_bbox=list(span["bbox"]),
        )
        self.operations[op_id] = prov
        self.op_metadata[op_id] = {
            "document_id": document_id,
            "staged_item": staged_item,
        }

        return {
            "ok": True,
            "status": "STAGED",
            "result_state": ResultState.STAGED.value,
            "operation_id": op_id,
            "document_id": document_id,
            "target_id": target_id,
            "node_id": cand.get("node_id"),
            "policy_applied": verdict.policy,
            "estimated_width_pt": verdict.needed_width_pt,
            "clearance_pt": span["clearance_pt"],
            "mutated": False,
            "message": "Operación validada y preparada (STAGED). No se ha modificado ningún archivo todavía. Requiere export_document.",
        }

    # ─────────────────────────────────────────────────────────────
    # 6. export_document (v0.1)
    # ─────────────────────────────────────────────────────────────
    def export_document(self, document_id: str, destination: str) -> Dict[str, Any]:
        """Exporta las operaciones preparadas a un archivo destino limpio."""
        session = self.sessions.get(document_id)
        if session is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"document_id no encontrado: {document_id}",
            }

        abs_dest = os.path.abspath(destination)
        if abs_dest == session.source_path:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": "La modificación in-place del documento original está estrictamente prohibida.",
            }

        if not session.staged_operations:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": "No hay operaciones preparadas para exportar.",
            }

        # Verificar inmutabilidad del original previo a la exportación
        curr_src_hash = sha256_file(session.source_path)
        if curr_src_hash != session.source_sha256:
            return {
                "ok": False,
                "result_state": ResultState.CRASH.value,
                "error": "CORRUPCIÓN: El hash del archivo original cambió antes de exportar.",
            }

        try:
            doc = pymupdf.open(session.source_path)
            fontbooks: Dict[int, FontBook] = {}

            for item in session.staged_operations:
                pno = item["span"]["page"]
                if pno not in fontbooks:
                    fontbooks[pno] = FontBook(doc, doc[pno])
                apply_replace(doc[pno], fontbooks[pno], item["span"], item["verdict"])

            from engine import _deterministic_id
            data = _deterministic_id(doc.tobytes(garbage=3, deflate=True))
            doc.close()

            dest_dir = os.path.dirname(abs_dest)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            with open(abs_dest, "wb") as f:
                f.write(data)

            out_hash = sha256_bytes(data)
            session.exported_destination = abs_dest
            session.output_sha256 = out_hash

            post_src_hash = sha256_file(session.source_path)
            assert post_src_hash == session.source_sha256, "El archivo original fue alterado durante la exportación."

            exported_ops = []
            for item in session.staged_operations:
                op_id = item["operation_id"]
                if op_id in self.operations:
                    self.operations[op_id].result_state = ResultState.EXPORTED.value
                    self.operations[op_id].output_hash = out_hash
                exported_ops.append(op_id)

            return {
                "ok": True,
                "status": "EXPORTED",
                "result_state": ResultState.EXPORTED.value,
                "document_id": document_id,
                "destination": abs_dest,
                "output_sha256": out_hash,
                "source_sha256": session.source_sha256,
                "operations_exported": exported_ops,
                "message": "Documento exportado. Debe ejecutarse verify_operation para verificar y producir PASS.",
            }
        except Exception as e:
            return {
                "ok": False,
                "result_state": ResultState.CRASH.value,
                "error": f"Error durante export_document: {str(e)}",
            }

    # ─────────────────────────────────────────────────────────────
    # 7. verify_operation (v0.1)
    # ─────────────────────────────────────────────────────────────
    def verify_operation(self, operation_id: str, exported_path: Optional[str] = None) -> Dict[str, Any]:
        """Abre en fresco el PDF exportado y ejecuta la verificación física y material.
        
        ÚNICA FUNCIÓN AUTORIZADA PARA DECLARAR PASS EN OPERACIONES SIMPLES.
        """
        prov = self.operations.get(operation_id)
        if prov is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"operation_id no encontrado: {operation_id}",
            }

        if prov.result_state == ResultState.HONEST_REJECT.value:
            return {
                "ok": False,
                "operation_id": operation_id,
                "result_state": ResultState.HONEST_REJECT.value,
                "verifier_result": prov.verifier_result,
                "provenance": prov.as_dict(),
                "message": "La operación fue rechazada honestamente antes de la exportación.",
            }

        meta = self.op_metadata.get(operation_id)
        if meta is None:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"Metadatos no encontrados para {operation_id}",
            }

        doc_id = meta["document_id"]
        session = self.sessions[doc_id]
        target_path = exported_path or session.exported_destination

        if not target_path or not os.path.isfile(target_path):
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": "El archivo exportado no existe. La verificación requiere el documento exportado.",
            }

        staged_item = meta["staged_item"]
        verdicts_tuple = [(staged_item["op"], staged_item["span"], staged_item["verdict"])]

        try:
            verify_rep = verify_output(target_path, session.model, verdicts_tuple)

            curr_src_hash = sha256_file(session.source_path)
            out_file_hash = sha256_file(target_path)

            original_untouched = (curr_src_hash == session.source_sha256)
            checks = verify_rep.get("checks", [])
            core_ok = verify_rep.get("ok", False) and len(checks) > 0

            checks_valid = all(
                c.get("ok", False)
                and c.get("dx_pt", 999.0) <= ORIGIN_TOLERANCE_PT
                and c.get("dy_pt", 999.0) <= ORIGIN_TOLERANCE_PT
                and c.get("font_identity_ok", False) is True
                for c in checks
            )

            if original_untouched and core_ok and checks_valid:
                final_state = ResultState.PASS.value
                ok = True
                msg = "Operación VERIFICADA con éxito (PASS). Tolerancias geométricas e identidad tipográfica confirmadas."
            else:
                final_state = ResultState.HONEST_REJECT.value
                ok = False
                msg = f"La verificación falló. core_ok={core_ok}, checks_valid={checks_valid}, original_untouched={original_untouched}."

            prov.result_state = final_state
            prov.verifier_result = verify_rep
            prov.output_hash = out_file_hash

            return {
                "ok": ok,
                "operation_id": operation_id,
                "result_state": final_state,
                "verifier_result": verify_rep,
                "provenance": prov.as_dict(),
                "message": msg,
            }
        except Exception as e:
            prov.result_state = ResultState.CRASH.value
            return {
                "ok": False,
                "operation_id": operation_id,
                "result_state": ResultState.CRASH.value,
                "error": f"Fallo catastrófico en verificación: {str(e)}",
                "provenance": prov.as_dict(),
            }

    # ─────────────────────────────────────────────────────────────
    # HERRAMIENTAS v0.2: CONTEXTO COMPACTO Y NAVEGACIÓN ESTRUCTURAL
    # ─────────────────────────────────────────────────────────────
    def document_summary(self, document_id: str) -> Dict[str, Any]:
        """LEVEL 0: Resumen ultracompacto del documento (~200 tokens)."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        summary = get_document_summary(session.graph)
        summary["ok"] = True
        return summary

    def document_outline(
        self,
        document_id: str,
        pages: Optional[Sequence[int]] = None,
        types: Optional[Sequence[str]] = None,
        max_depth: Optional[int] = None,
        max_text_len: int = 50,
        show_bbox: bool = False,
        show_ids: bool = True,
        include_vectors: bool = False,
    ) -> Dict[str, Any]:
        """LEVEL 1: Representación en árbol jerárquico legible y configurable (~2k tokens)."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        ctx = get_document_outline_context(
            session.graph,
            pages=pages,
            types=types,
            max_depth=max_depth,
            max_text_len=max_text_len,
            show_bbox=show_bbox,
            show_ids=show_ids,
            include_vectors=include_vectors,
        )
        ctx["ok"] = True
        return ctx

    def inspect_node(self, document_id: str, node_id: str) -> Dict[str, Any]:
        """LEVEL 2: Ventana contextual centrada en un nodo específico (~300 tokens)."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        win = get_node_window(session.graph, node_id)
        if not win:
            return {"ok": False, "error": f"Nodo no encontrado: {node_id}"}
        win["ok"] = True
        return win

    def query_nodes(
        self,
        document_id: str,
        page: Optional[int] = None,
        node_type: Optional[str] = None,
        rect: Optional[Sequence[float]] = None,
        text: Optional[str] = None,
        contain_mode: str = "intersects",
    ) -> Dict[str, Any]:
        """Consulta estructural de nodos por página, tipo, rectángulo espacial o texto."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}

        g = session.graph
        matched = list(g.nodes.values())

        if page is not None:
            matched = [n for n in matched if n.page == page]

        if node_type is not None:
            type_str = node_type.upper()
            matched = [n for n in matched if n.node_type == type_str]

        if text is not None and text:
            matched = [n for n in matched if getattr(n, "text", None) and text.lower() in n.text.lower()]

        if rect is not None and len(rect) == 4 and page is not None:
            in_rect = g.nodes_in_rect(page=page, rect=rect, contain_mode=contain_mode)
            in_rect_ids = {n.node_id for n in in_rect}
            matched = [n for n in matched if n.node_id in in_rect_ids]

        return {
            "ok": True,
            "document_id": document_id,
            "count": len(matched),
            "nodes": [n.to_dict() for n in matched[:50]],  # Cap a 50 para seguridad de contexto
        }

    def node_neighbors(
        self,
        document_id: str,
        node_id: str,
        same_page: bool = True,
        spatial_radius: Optional[float] = 36.0,
        relation_types: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """LEVEL 3: Subgrafo espacial y relacional de vecindad de un nodo (~500 tokens)."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        res = get_node_neighbors(
            session.graph,
            node_id=node_id,
            same_page=same_page,
            spatial_radius=spatial_radius,
            relation_types=relation_types,
        )
        if not res:
            return {"ok": False, "error": f"Nodo no encontrado: {node_id}"}
        res["ok"] = True
        return res

    def children_of(self, document_id: str, node_id: str) -> Dict[str, Any]:
        """Obtiene los nodos hijos directos de un nodo en el DocGraph."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        kids = session.graph.children(node_id)
        return {
            "ok": True,
            "document_id": document_id,
            "node_id": node_id,
            "count": len(kids),
            "children": [k.to_dict() for k in kids],
        }

    def relations_of(
        self,
        document_id: str,
        node_id: str,
        relation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recupera relaciones (materializadas y derivadas) asociadas a un nodo."""
        session = self.sessions.get(document_id)
        if not session or not session.graph:
            return {"ok": False, "error": f"Documento o grafo no cargado para {document_id}"}
        rels = session.graph.relations_of(node_id=node_id, relation_type=relation_type, include_derived=True)
        return {
            "ok": True,
            "document_id": document_id,
            "node_id": node_id,
            "count": len(rels),
            "relations": [r.to_dict() for r in rels],
        }

    # ─────────────────────────────────────────────────────────────
    # HERRAMIENTAS v0.2: TRANSACCIONES ATÓMICAS MULTI-OPERACIÓN
    # ─────────────────────────────────────────────────────────────
    def stage_transaction(
        self,
        document_id: str,
        operations: List[Dict[str, Any]],
        policy: str = "ATOMIC",
    ) -> Dict[str, Any]:
        """Inicia y prepara una transacción atómica multi-operación (Batch v0.1)."""
        session = self.sessions.get(document_id)
        if not session:
            return {"ok": False, "error": f"Documento {document_id} no cargado"}

        # Mapear spec de operaciones: si vienen con node_id, resolver automáticamente a target
        mapped_specs = []
        for op in operations:
            spec = dict(op)
            if "node_id" in spec and "target_id" not in spec:
                # Resolver target a partir de node_id
                node = session.graph.get_node(spec["node_id"]) if session.graph else None
                if node and hasattr(node, "text"):
                    # Crear o reutilizar candidate/target
                    cand_id = f"cand_node_{node.node_id}"
                    tgt_id = f"target_node_{node.node_id}"
                    cand_dict = {
                        "candidate_id": cand_id,
                        "target_id": tgt_id,
                        "node_id": node.node_id,
                        "document_id": document_id,
                        "page": node.page,
                        "span_id": node.provenance.get("source_span", node.node_id),
                        "text": node.text,
                        "font": getattr(node, "font", "Helvetica"),
                        "font_size": getattr(node, "font_size", 10.0),
                        "clearance_pt": getattr(node, "clearance_pt", 100.0),
                        "bbox": node.bbox,
                        "origin": getattr(node, "origin", (0, 0)),
                    }
                    session.targets[tgt_id] = cand_dict
                    spec["target_id"] = tgt_id
            mapped_specs.append(spec)

        tx_policy = TransactionPolicy.ATOMIC if policy.upper() == "ATOMIC" else TransactionPolicy.ATOMIC
        tx = self.transaction_manager.create_transaction(
            document_id=document_id,
            source_pdf_path=session.source_path,
            source_sha256=session.source_sha256,
            policy=tx_policy,
        )

        res = self.transaction_manager.stage_operations(
            transaction_id=tx.transaction_id,
            operations_spec=mapped_specs,
            targets_registry=session.targets,
        )
        res["ok"] = (res.get("status") == "STAGED")
        return res

    def export_transaction(
        self,
        document_id: str,
        transaction_id: str,
        destination: str,
    ) -> Dict[str, Any]:
        """Exporta atómicamente todas las operaciones de una transacción a un archivo destino."""
        session = self.sessions.get(document_id)
        if not session:
            return {"ok": False, "error": f"Documento {document_id} no cargado"}

        abs_dest = os.path.abspath(destination)
        if abs_dest == session.source_path:
            return {
                "ok": False,
                "error": "La ruta de exportación no puede sobrescribir el archivo original.",
            }

        res = self.transaction_manager.export_transaction(
            transaction_id=transaction_id,
            output_pdf_path=abs_dest,
        )
        res["ok"] = (res.get("status") == "EXPORTED")
        return res

    def verify_transaction(
        self,
        document_id: str,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """Verifica cada una de las operaciones de la transacción. Emite PASS global solo si todas verifican."""
        session = self.sessions.get(document_id)
        if not session:
            return {"ok": False, "error": f"Documento {document_id} no cargado"}

        res = self.transaction_manager.verify_transaction(transaction_id=transaction_id)
        res["ok"] = (res.get("verdict") == "PASS")
        return res

    def rollback_transaction(
        self,
        document_id: str,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """Revierte una transacción staged o no verificada limpiamente."""
        res = self.transaction_manager.rollback_transaction(transaction_id=transaction_id)
        res["ok"] = (res.get("status") == "ROLLED_BACK")
        return res

    # ─────────────────────────────────────────────────────────────
    # Despacho agnóstico a modelo (Agent-Agnostic Dispatch)
    # ─────────────────────────────────────────────────────────────
    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Interfaz agnóstica para invocación de herramientas desde cualquier agente o JSON."""
        dispatch_table = {
            # Herramientas v0.1
            "open_document": lambda a: self.open_document(path=a.get("path", "")),
            "inspect_document": lambda a: self.inspect_document(document_id=a.get("document_id", "")),
            "find_text": lambda a: self.find_text(
                document_id=a.get("document_id", ""),
                query=a.get("query", ""),
                page=a.get("page"),
                case_sensitive=a.get("case_sensitive", True),
            ),
            "select_target": lambda a: self.select_target(
                document_id=a.get("document_id", ""),
                candidate_id=a.get("candidate_id", ""),
            ),
            "replace_text": lambda a: self.replace_text(
                document_id=a.get("document_id", ""),
                target_id=a.get("target_id", ""),
                new_value=a.get("new_value", ""),
                policy_preference=a.get("policy_preference"),
            ),
            "export_document": lambda a: self.export_document(
                document_id=a.get("document_id", ""),
                destination=a.get("destination", ""),
            ),
            "verify_operation": lambda a: self.verify_operation(
                operation_id=a.get("operation_id", ""),
                exported_path=a.get("exported_path"),
            ),
            # Herramientas v0.2
            "document_summary": lambda a: self.document_summary(document_id=a.get("document_id", "")),
            "document_outline": lambda a: self.document_outline(
                document_id=a.get("document_id", ""),
                pages=a.get("pages"),
                types=a.get("types"),
                max_depth=a.get("max_depth"),
                max_text_len=a.get("max_text_len", 50),
                show_bbox=a.get("show_bbox", False),
                show_ids=a.get("show_ids", True),
                include_vectors=a.get("include_vectors", False),
            ),
            "inspect_node": lambda a: self.inspect_node(
                document_id=a.get("document_id", ""),
                node_id=a.get("node_id", ""),
            ),
            "query_nodes": lambda a: self.query_nodes(
                document_id=a.get("document_id", ""),
                page=a.get("page"),
                node_type=a.get("node_type"),
                rect=a.get("rect"),
                text=a.get("text"),
                contain_mode=a.get("contain_mode", "intersects"),
            ),
            "node_neighbors": lambda a: self.node_neighbors(
                document_id=a.get("document_id", ""),
                node_id=a.get("node_id", ""),
                same_page=a.get("same_page", True),
                spatial_radius=a.get("spatial_radius", 36.0),
                relation_types=a.get("relation_types"),
            ),
            "children_of": lambda a: self.children_of(
                document_id=a.get("document_id", ""),
                node_id=a.get("node_id", ""),
            ),
            "relations_of": lambda a: self.relations_of(
                document_id=a.get("document_id", ""),
                node_id=a.get("node_id", ""),
                relation_type=a.get("relation_type"),
            ),
            "stage_transaction": lambda a: self.stage_transaction(
                document_id=a.get("document_id", ""),
                operations=a.get("operations", []),
                policy=a.get("policy", "ATOMIC"),
            ),
            "export_transaction": lambda a: self.export_transaction(
                document_id=a.get("document_id", ""),
                transaction_id=a.get("transaction_id", ""),
                destination=a.get("destination", ""),
            ),
            "verify_transaction": lambda a: self.verify_transaction(
                document_id=a.get("document_id", ""),
                transaction_id=a.get("transaction_id", ""),
            ),
            "rollback_transaction": lambda a: self.rollback_transaction(
                document_id=a.get("document_id", ""),
                transaction_id=a.get("transaction_id", ""),
            ),
        }

        if name not in dispatch_table:
            return {
                "ok": False,
                "result_state": ResultState.HONEST_REJECT.value,
                "error": f"Herramienta desconocida: {name}",
            }

        try:
            return dispatch_table[name](arguments)
        except Exception as e:
            return {
                "ok": False,
                "result_state": ResultState.CRASH.value,
                "error": f"Error no capturado en ejecución de {name}: {str(e)}",
            }

    @staticmethod
    def get_tool_schemas_v0_1() -> List[Dict[str, Any]]:
        """Devuelve los 7 schemas canónicos del Tool Contract v0.1."""
        return [
            {
                "name": "open_document",
                "description": "Abre un PDF original, genera su document_id criptográfico y extrae su modelo espacial sin modificar el archivo original.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Ruta absoluta o relativa al PDF fuente original."}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "inspect_document",
                "description": "Inspecciona la estructura geométrica, páginas, conteo de spans y fuentes del documento cargado.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento retornado por open_document."}
                    },
                    "required": ["document_id"]
                }
            },
            {
                "name": "find_text",
                "description": "Busca ocurrencias de texto en el documento. Si existen múltiples coincidencias, retorna estado AMBIGUOUS con la lista de candidatos para desambiguar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "query": {"type": "string", "description": "Cadena de texto a localizar."},
                        "page": {"type": "integer", "description": "Número de página opcional donde limitar la búsqueda."},
                        "case_sensitive": {"type": "boolean", "description": "Si la búsqueda distingue mayúsculas/minúsculas (por defecto True)."}
                    },
                    "required": ["document_id", "query"]
                }
            },
            {
                "name": "select_target",
                "description": "Selecciona y resuelve un candidato específico de búsqueda para convertirlo en target inequívoco de mutación.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "candidate_id": {"type": "string", "description": "ID del candidato obtenido de find_text."}
                    },
                    "required": ["document_id", "candidate_id"]
                }
            },
            {
                "name": "replace_text",
                "description": "Valida y prepara el reemplazo de texto sobre un target resuelto. Si es ambiguo o la política geométrica/tipográfica no se satisface, rechaza honestamente (AMBIGUOUS u HONEST_REJECT) y NO muta. Emite estado STAGED, nunca PASS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "target_id": {"type": "string", "description": "ID del target resuelto obtenido de select_target."},
                        "new_value": {"type": "string", "description": "Nuevo texto a insertar."},
                        "policy_preference": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Preferencia opcional de políticas de ajuste (ej: ['fit', 'shrink', 'reject'])."
                        }
                    },
                    "required": ["document_id", "target_id", "new_value"]
                }
            },
            {
                "name": "export_document",
                "description": "Exporta las operaciones preparadas a una nueva ruta de destino. El original nunca se modifica in-place. No emite PASS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "destination": {"type": "string", "description": "Ruta de archivo destino para guardar el nuevo PDF."}
                    },
                    "required": ["document_id", "destination"]
                }
            },
            {
                "name": "verify_operation",
                "description": "Reabre el documento exportado y realiza la verificación física, geométrica y tipográfica independiente. Es la ÚNICA herramienta facultada para emitir PASS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation_id": {"type": "string", "description": "ID de la operación obtenido al preparar el reemplazo."},
                        "exported_path": {"type": "string", "description": "Ruta opcional al archivo exportado si difiere de la registrada."}
                    },
                    "required": ["operation_id"]
                }
            }
        ]

    @staticmethod
    def get_tool_schemas_v0_2() -> List[Dict[str, Any]]:
        """Devuelve los schemas del Tool Contract v0.2 (compatibilidad total con v0.1 + navegación estructural + transacciones)."""
        schemas = PrometeoTools.get_tool_schemas_v0_1()
        schemas.extend([
            {
                "name": "document_summary",
                "description": "Obtiene un resumen ultracompacto del documento (Nivel 0: páginas, dimensiones, conteo de nodos por tipo, fuentes) para consumir mínimo contexto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."}
                    },
                    "required": ["document_id"]
                }
            },
            {
                "name": "document_outline",
                "description": "Devuelve la jerarquía del documento en un árbol textual compacto (Nivel 1), configurable por páginas, tipos y profundidad para evitar sobrecarga de contexto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "pages": {"type": "array", "items": {"type": "integer"}, "description": "Lista de números de página a incluir."},
                        "types": {"type": "array", "items": {"type": "string"}, "description": "Tipos de nodo permitidos (TEXT, GROUP, VECTOR, IMAGE)."},
                        "max_depth": {"type": "integer", "description": "Profundidad máxima del árbol."},
                        "include_vectors": {"type": "boolean", "description": "Si incluir nodos vectoriales (por defecto False para brevedad)."}
                    },
                    "required": ["document_id"]
                }
            },
            {
                "name": "inspect_node",
                "description": "Obtiene la ventana contextual local de un nodo estructural específico (Nivel 2: nodo, bloque padre, nodos hermanos, anterior/siguiente).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "node_id": {"type": "string", "description": "ID estructural del nodo (ej: text_p0_s4)."}
                    },
                    "required": ["document_id", "node_id"]
                }
            },
            {
                "name": "query_nodes",
                "description": "Busca y filtra nodos en la escena por página, tipo, subcadena de texto o región rectangular espacial.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "page": {"type": "integer", "description": "Página donde buscar."},
                        "node_type": {"type": "string", "description": "Tipo de nodo (TEXT, GROUP, VECTOR, IMAGE)."},
                        "text": {"type": "string", "description": "Subcadena de texto que debe contener."},
                        "rect": {"type": "array", "items": {"type": "number"}, "description": "Caja [x0, y0, x1, y1] en puntos PDF."}
                    },
                    "required": ["document_id"]
                }
            },
            {
                "name": "node_neighbors",
                "description": "Obtiene el subgrafo espacial y relacional de vecindad de un nodo (Nivel 3).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "node_id": {"type": "string", "description": "ID del nodo central."},
                        "spatial_radius": {"type": "number", "description": "Radio espacial en puntos para buscar vecinos cercanos (por defecto 36pt)."}
                    },
                    "required": ["document_id", "node_id"]
                }
            },
            {
                "name": "children_of",
                "description": "Obtiene los nodos hijos directos de un nodo en el DocGraph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "node_id": {"type": "string", "description": "ID del nodo padre."}
                    },
                    "required": ["document_id", "node_id"]
                }
            },
            {
                "name": "relations_of",
                "description": "Recupera relaciones (materializadas y derivadas) asociadas a un nodo en el DocGraph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "node_id": {"type": "string", "description": "ID del nodo a consultar."},
                        "relation_type": {"type": "string", "description": "Opcional: filtrar por tipo de relación (PARENT_OF, CHILD_OF, SAME_TEXT_BLOCK, SAME_LINE, INTERSECTS, SAME_PAGE)."}
                    },
                    "required": ["document_id", "node_id"]
                }
            },
            {
                "name": "stage_transaction",
                "description": "Prepara atómicamente un lote de operaciones de reemplazo de texto (Batch v0.1). Si existe cualquier conflicto o desbordamiento de clearance, rechaza todo el lote (ALL-OR-NOTHING).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "operations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target_id": {"type": "string", "description": "ID del target resuelto."},
                                    "node_id": {"type": "string", "description": "Opcionalmente, ID del TextNode directo."},
                                    "new_text": {"type": "string", "description": "Nuevo texto a insertar."}
                                },
                                "required": ["new_text"]
                            },
                            "description": "Lista de especificaciones de operaciones a ejecutar juntas."
                        },
                        "policy": {"type": "string", "description": "Política de transacción (por defecto 'ATOMIC')."}
                    },
                    "required": ["document_id", "operations"]
                }
            },
            {
                "name": "export_transaction",
                "description": "Aplica atómicamente todas las operaciones de la transacción a una nueva copia del PDF. El original queda intacto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "transaction_id": {"type": "string", "description": "ID de la transacción devuelto por stage_transaction."},
                        "destination": {"type": "string", "description": "Ruta destino del archivo PDF modificado."}
                    },
                    "required": ["document_id", "transaction_id", "destination"]
                }
            },
            {
                "name": "verify_transaction",
                "description": "Verifica exhaustivamente que cada una de las operaciones de la transacción se aplicó correctamente. Emite PASS solo si el 100% de operaciones son conformes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "transaction_id": {"type": "string", "description": "ID de la transacción."}
                    },
                    "required": ["document_id", "transaction_id"]
                }
            },
            {
                "name": "rollback_transaction",
                "description": "Descarta una transacción preparada o no verificada limpiamente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "ID del documento."},
                        "transaction_id": {"type": "string", "description": "ID de la transacción."}
                    },
                    "required": ["document_id", "transaction_id"]
                }
            }
        ])
        return schemas

    @staticmethod
    def get_tool_schemas() -> List[Dict[str, Any]]:
        """Alias predeterminado: devuelve schemas de Tool Contract v0.1 (7 herramientas) para compatibilidad."""
        return PrometeoTools.get_tool_schemas_v0_1()
