"""PROMETEO · Multi-Operation Transaction Model v0.1
────────────────────────────────────────────────────
Implementa transacciones atómicas documentales con política 'ALL-OR-NOTHING':
- Estados: CREATED, STAGED, VALIDATED, EXPORTED, VERIFIED, ROLLED_BACK, HONEST_REJECT, FAILED.
- Detección de conflictos antes de cualquier mutación física.
- Exportación única con preservación estricta del original.
- Verificación exhaustiva: PASS global solo si el 100% de operaciones verifican.
- Cero tolerancia a éxito parcial silencioso (SILENT_FAILURE == 0).
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
import docgraph
from docgraph import DocGraph, GLOBAL_DOCGRAPH_CACHE, docgraph_diff
from fase0 import operations, render


class TransactionState(str, Enum):
    CREATED = "CREATED"
    STAGED = "STAGED"
    VALIDATED = "VALIDATED"
    EXPORTED = "EXPORTED"
    VERIFIED = "VERIFIED"
    ROLLED_BACK = "ROLLED_BACK"
    HONEST_REJECT = "HONEST_REJECT"
    FAILED = "FAILED"


class TransactionPolicy(str, Enum):
    ATOMIC = "ATOMIC"


@dataclass
class TransactionOperation:
    """Operación individual dentro de una transacción."""
    op_id: str
    target_id: str
    target_text: str
    new_text: str
    page: int
    bbox: Tuple[float, float, float, float]
    font: str
    font_size: float
    clearance_pt: float
    origin: Tuple[float, float]
    span_id: str = ""
    node_id: Optional[str] = None
    status: str = "PENDING"
    error_message: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "target_id": self.target_id,
            "span_id": self.span_id,
            "target_text": self.target_text,
            "new_text": self.new_text,
            "page": self.page,
            "bbox": list(self.bbox),
            "font": self.font,
            "font_size": self.font_size,
            "clearance_pt": self.clearance_pt,
            "origin": list(self.origin),
            "node_id": self.node_id,
            "status": self.status,
            "error_message": self.error_message,
            "verification_result": self.verification_result,
        }


@dataclass
class Transaction:
    """Contenedor de transacción documental multi-operación."""
    transaction_id: str
    document_id: str
    source_pdf_path: str
    source_sha256: str
    policy: TransactionPolicy = TransactionPolicy.ATOMIC
    state: TransactionState = TransactionState.CREATED
    operations: List[TransactionOperation] = field(default_factory=list)
    output_pdf_path: Optional[str] = None
    output_sha256: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    docgraph_diff_result: Optional[Dict[str, Any]] = None
    model: Optional[Dict[str, Any]] = None

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        self.audit_log.append({
            "timestamp": time.time(),
            "event": event_type,
            "state": self.state.value,
            "details": details,
        })
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "document_id": self.document_id,
            "source_pdf_path": self.source_pdf_path,
            "source_sha256": self.source_sha256,
            "policy": self.policy.value,
            "state": self.state.value,
            "operations_count": len(self.operations),
            "operations": [op.to_dict() for op in self.operations],
            "output_pdf_path": self.output_pdf_path,
            "output_sha256": self.output_sha256,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "audit_log": list(self.audit_log),
            "docgraph_diff_summary": self.docgraph_diff_result.get("summary") if self.docgraph_diff_result else None,
        }


class TransactionManager:
    """Gestor de transacciones atómicas documentales."""

    def __init__(self) -> None:
        self._transactions: Dict[str, Transaction] = {}

    def create_transaction(
        self,
        document_id: str,
        source_pdf_path: str,
        source_sha256: str,
        policy: TransactionPolicy = TransactionPolicy.ATOMIC,
    ) -> Transaction:
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        tx = Transaction(
            transaction_id=tx_id,
            document_id=document_id,
            source_pdf_path=os.path.abspath(source_pdf_path),
            source_sha256=source_sha256,
            policy=policy,
            state=TransactionState.CREATED,
        )
        tx.log_event("TRANSACTION_CREATED", {"policy": policy.value, "document_id": document_id})
        self._transactions[tx_id] = tx
        return tx

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        return self._transactions.get(transaction_id)

    def stage_operations(
        self,
        transaction_id: str,
        operations_spec: List[Dict[str, Any]],
        targets_registry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Valida y añade operaciones a la transacción bajo política ATOMIC."""
        tx = self._transactions.get(transaction_id)
        if not tx:
            return {"status": "FAILED", "error": f"Transacción no encontrada: {transaction_id}"}

        if tx.state not in (TransactionState.CREATED, TransactionState.STAGED):
            return {"status": "FAILED", "error": f"Estado de transacción no válido para staging: {tx.state.value}"}

        # 1. Detección de conflictos previos
        target_ids_seen = set()
        staged_ops: List[TransactionOperation] = []

        for idx, spec in enumerate(operations_spec):
            tgt_id = spec.get("target_id")
            new_text = spec.get("new_text", "")

            # Conflicto: target_id ausente
            if not tgt_id:
                tx.state = TransactionState.HONEST_REJECT
                tx.log_event("CONFLICT_DETECTED", {"error": "Missing target_id", "index": idx})
                return {
                    "status": "HONEST_REJECT",
                    "reason": "MISSING_TARGET_ID",
                    "details": f"Operación en índice {idx} carece de target_id",
                }

            # Conflicto: target duplicado en la misma transacción
            if tgt_id in target_ids_seen:
                tx.state = TransactionState.HONEST_REJECT
                tx.log_event("CONFLICT_DETECTED", {"error": "Duplicate target in transaction", "target_id": tgt_id})
                return {
                    "status": "HONEST_REJECT",
                    "reason": "DUPLICATE_TARGET_IN_TRANSACTION",
                    "details": f"El target '{tgt_id}' aparece más de una vez en la misma transacción",
                }
            target_ids_seen.add(tgt_id)

            # Conflicto: target no encontrado en el registro
            target_info = targets_registry.get(tgt_id)
            if not target_info:
                tx.state = TransactionState.HONEST_REJECT
                tx.log_event("CONFLICT_DETECTED", {"error": "Target not registered", "target_id": tgt_id})
                return {
                    "status": "HONEST_REJECT",
                    "reason": "TARGET_NOT_FOUND",
                    "details": f"Target '{tgt_id}' no encontrado o no resuelto previamente",
                }

            # Conflicto: clearance overflow estimado
            clearance_pt = float(target_info.get("clearance_pt", 100.0))
            font_size = float(target_info.get("font_size", 10.0))
            estimated_width = len(new_text) * (font_size * 0.52)

            if estimated_width > clearance_pt:
                tx.state = TransactionState.HONEST_REJECT
                tx.log_event("CLEARANCE_OVERFLOW", {
                    "target_id": tgt_id,
                    "estimated_width": estimated_width,
                    "clearance_pt": clearance_pt,
                })
                return {
                    "status": "HONEST_REJECT",
                    "reason": "CLEARANCE_OVERFLOW",
                    "details": f"El nuevo texto '{new_text}' excede el clearance disponible ({estimated_width:.1f}pt > {clearance_pt:.1f}pt)",
                    "target_id": tgt_id,
                }

            op_id = f"op_{tx.transaction_id}_{idx}"
            span_id = str(target_info.get("span_id") or tgt_id.replace("target_", ""))
            staged_ops.append(TransactionOperation(
                op_id=op_id,
                target_id=tgt_id,
                span_id=span_id,
                target_text=target_info.get("text", ""),
                new_text=new_text,
                page=int(target_info.get("page", 0)),
                bbox=tuple(float(c) for c in target_info.get("bbox", (0, 0, 0, 0))),
                font=str(target_info.get("font", "Helvetica")),
                font_size=font_size,
                clearance_pt=clearance_pt,
                origin=tuple(float(c) for c in target_info.get("origin", (0, 0))),
                node_id=target_info.get("node_id"),
                status="STAGED",
            ))

        tx.operations = staged_ops
        tx.state = TransactionState.STAGED
        tx.log_event("OPERATIONS_STAGED", {"staged_count": len(staged_ops)})
        return {
            "status": "STAGED",
            "transaction_id": tx.transaction_id,
            "operations_count": len(staged_ops),
            "operations": [op.to_dict() for op in staged_ops],
        }

    def export_transaction(
        self,
        transaction_id: str,
        output_pdf_path: str,
    ) -> Dict[str, Any]:
        """Aplica atómicamente todas las operaciones staged a una copia limpia del PDF."""
        tx = self._transactions.get(transaction_id)
        if not tx:
            return {"status": "FAILED", "error": f"Transacción no encontrada: {transaction_id}"}

        if tx.state != TransactionState.STAGED:
            return {"status": "FAILED", "error": f"Transacción no está en estado STAGED (estado: {tx.state.value})"}

        abs_out = os.path.abspath(output_pdf_path)
        if abs_out == tx.source_pdf_path:
            return {"status": "FAILED", "error": "Exportación no puede sobreescribir el archivo original."}

        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        try:
            from fase0.operations import ReplaceText
            from fase0 import engine

            model = engine.extract(tx.source_pdf_path)
            engine_ops = []
            for op in tx.operations:
                span = engine.span_by_id(model, op.span_id)
                old_t = op.target_text if (span and op.target_text in span["text"]) else (span["text"] if span else op.target_text)
                engine_ops.append(
                    ReplaceText(
                        target_span_id=op.span_id,
                        old_text=old_t,
                        new_text=op.new_text,
                    )
                )

            report = engine.export_version(
                src_path=tx.source_pdf_path,
                ops=engine_ops,
                out_path=abs_out,
            )

            if not os.path.exists(abs_out):
                tx.state = TransactionState.FAILED
                tx.log_event("EXPORT_FAILED", {"reason": "Output file not created", "results": report.get("results")})
                return {"status": "FAILED", "error": "Fallo durante la exportación del lote", "details": report.get("results")}

            out_sha = docgraph.sha256_file(abs_out)
            tx.output_pdf_path = abs_out
            tx.output_sha256 = out_sha
            tx.model = model
            tx.state = TransactionState.EXPORTED
            tx.log_event("TRANSACTION_EXPORTED", {"output_path": abs_out, "output_sha256": out_sha})

            for op in tx.operations:
                op.status = "EXPORTED"

            return {
                "status": "EXPORTED",
                "transaction_id": tx.transaction_id,
                "output_pdf_path": abs_out,
                "output_sha256": out_sha,
                "operations_applied": len(tx.operations),
            }
        except Exception as e:
            tx.state = TransactionState.FAILED
            tx.log_event("EXPORT_FAILED", {"error": str(e)})
            if os.path.exists(abs_out):
                try:
                    os.remove(abs_out)
                except OSError:
                    pass
            return {"status": "FAILED", "error": f"Fallo al exportar transacción: {str(e)}"}

    def verify_transaction(
        self,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """Verifica cada operación en el PDF exportado abriéndolo en fresco.
        
        Veredicto PASS solo si el 100% de las operaciones verifican (ALL-OR-NOTHING).
        Si el archivo exportado fue alterado o una sola operación falla, emite FAIL.
        """
        tx = self._transactions.get(transaction_id)
        if not tx:
            return {"status": "FAILED", "verdict": "FAIL", "error": f"Transacción no encontrada: {transaction_id}"}

        if tx.state != TransactionState.EXPORTED or not tx.output_pdf_path:
            return {"status": "FAILED", "verdict": "FAIL", "error": f"Transacción no está exportada (estado: {tx.state.value})"}

        if not os.path.exists(tx.output_pdf_path):
            tx.state = TransactionState.FAILED
            return {"status": "FAILED", "verdict": "FAIL", "error": "El PDF exportado no existe físicamente en disco"}

        import pymupdf
        from fase0 import engine

        out_doc = pymupdf.open(tx.output_pdf_path)
        all_passed = True
        verification_details = []

        try:
            for op in tx.operations:
                page = out_doc[op.page]
                expected_origin = op.origin
                expected_x = op.origin[0]
                expected_text = op.new_text

                band = []
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    for line in block["lines"]:
                        for s in line["spans"]:
                            if (abs(s["origin"][1] - expected_origin[1]) <= 2.5
                                    and s["origin"][0] >= expected_x - 2.0):
                                band.append(s)
                band.sort(key=lambda s: s["origin"][0])
                concat = "".join(s["text"] for s in band)

                norm_concat = engine._norm_text(concat)
                norm_expected = engine._norm_text(expected_text)

                text_ok = norm_expected in norm_concat and len(band) > 0

                dx_ok = False
                dy_ok = False
                font_ok = False
                if band:
                    first = band[0]
                    dx = abs(first["origin"][0] - expected_x)
                    dy = abs(first["origin"][1] - expected_origin[1])
                    dx_ok = (dx <= engine.ORIGIN_TOLERANCE_PT)
                    dy_ok = (dy <= engine.ORIGIN_TOLERANCE_PT)
                    fonts_obs = {s["font"] for s in band}
                    font_ok = any(engine._font_identity_match(op.font, f) for f in fonts_obs)

                op_pass = text_ok and dx_ok and dy_ok and font_ok
                if op_pass:
                    op.status = "VERIFIED"
                else:
                    op.status = "VERIFICATION_FAILED"
                    all_passed = False

                verification_details.append({
                    "op_id": op.op_id,
                    "target_id": op.target_id,
                    "expected_text": op.new_text,
                    "found_text": norm_concat,
                    "text_ok": text_ok,
                    "dx_ok": dx_ok,
                    "dy_ok": dy_ok,
                    "font_ok": font_ok,
                    "pass": op_pass,
                })
        finally:
            out_doc.close()

        if all_passed and len(tx.operations) > 0:
            tx.state = TransactionState.VERIFIED
            g_orig, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(tx.source_pdf_path)
            g_mut, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(tx.output_pdf_path)
            diff = docgraph_diff(g_orig, g_mut)
            tx.docgraph_diff_result = diff

            tx.log_event("TRANSACTION_VERIFIED_PASS", {
                "verified_count": len(tx.operations),
                "diff_summary": diff.get("summary"),
            })
            return {
                "verdict": "PASS",
                "status": "VERIFIED",
                "transaction_id": tx.transaction_id,
                "operations_verified": len(tx.operations),
                "details": verification_details,
                "docgraph_diff_summary": diff.get("summary"),
            }
        else:
            tx.state = TransactionState.FAILED
            tx.log_event("TRANSACTION_VERIFIED_FAIL", {"details": verification_details})
            return {
                "verdict": "FAIL",
                "status": "FAILED",
                "transaction_id": tx.transaction_id,
                "reason": "ONE_OR_MORE_OPERATIONS_FAILED_VERIFICATION",
                "details": verification_details,
            }

    def rollback_transaction(
        self,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """Revierte la transacción descartando estado staged y marcando outputs no verificados."""
        tx = self._transactions.get(transaction_id)
        if not tx:
            return {"status": "FAILED", "error": f"Transacción no encontrada: {transaction_id}"}

        prev_state = tx.state.value
        tx.state = TransactionState.ROLLED_BACK
        for op in tx.operations:
            op.status = "ROLLED_BACK"

        unverified_file = None
        if tx.output_pdf_path and os.path.exists(tx.output_pdf_path):
            unverified_file = tx.output_pdf_path

        tx.log_event("TRANSACTION_ROLLED_BACK", {
            "previous_state": prev_state,
            "unverified_artifact": unverified_file,
        })

        return {
            "status": "ROLLED_BACK",
            "transaction_id": tx.transaction_id,
            "previous_state": prev_state,
            "unverified_artifact_marked": unverified_file,
        }
