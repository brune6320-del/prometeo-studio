"""PROMETEO Studio · Asistente (experimental, determinista, sin LLM)
────────────────────────────────────────────────────────────────────
- REVIEW_REQUIRED = True: el asistente solo PREPARA cambios; la persona decide y el
  verificador es la única autoridad para aprobar una copia (LLM != AUTHORITY).
- Si un texto aparece varias veces, nunca elige por la persona (ambigüedad explícita).
- No hay modelo de lenguaje conectado: entiende "Cambia «X» por «Y»".
"""

import re
from typing import Any, Dict, List, Optional

from agents.adapter import AgentAdapter
from .session import StudioDocumentSession


class StudioAgentBridge:
    """Orquesta las interacciones del asistente sobre una sesión de documento."""

    # "cambia <texto> por <texto>" con "por" como palabra completa; admite comillas.
    _CHANGE_RX = re.compile(
        r"^\s*(?:por\s+favor[,\s]+)?(?:cambia|reemplaza|sustituye)\s+[\"'«“]?(?P<old>.+?)[\"'»”]?\s+por\s+[\"'«“]?(?P<new>.+?)[\"'»”]?\s*[.!]?\s*$",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, session: StudioDocumentSession, adapter: Optional[AgentAdapter] = None):
        self.session = session
        self.adapter = adapter  # sin uso: no hay LLM conectado en Studio
        self.review_required = True
        self.conversation_history: List[Dict[str, Any]] = []

    @classmethod
    def parse_change_request(cls, message: str):
        """Devuelve (texto_actual, texto_nuevo) o None si el mensaje no es una petición de cambio."""
        m = cls._CHANGE_RX.match(message or "")
        if not m:
            return None
        old, new = m.group("old").strip(), m.group("new").strip()
        if not old or not new:
            return None
        return old, new

    def handle_user_message(self, message: str) -> Dict[str, Any]:
        """Propone, nunca decide; la verificación sigue siendo la autoridad."""
        self.conversation_history.append({"role": "user", "content": message})
        proposed_ops: List[Dict[str, Any]] = []
        activity: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        status = "COMPLETED"

        parsed = self.parse_change_request(message)
        if parsed:
            query, new_val = parsed
            activity.append({"tool": "find_text", "query": query, "status": "executed"})
            f_res = self.session.search_text(query)
            found = (f_res.get("candidates") or []) if f_res.get("ok") else []
            if not found:
                reply = f"No encontré «{query}» en el documento."
            elif len(found) > 1:
                # Ambigüedad: nunca se elige un candidato por la persona.
                candidates = [{"node_id": c.get("node_id"), "page": c.get("page"), "text": c.get("text")} for c in found[:20]]
                status = "AMBIGUOUS"
                reply = (f"«{query}» aparece {len(found)} veces. Selecciona en la página el texto exacto "
                         f"y usa «Preparar cambio» en el Inspector; no elegiré uno por ti.")
            else:
                cand = found[0]
                node = self.session.graph.get_node(cand.get("node_id")) if cand.get("node_id") else None
                full_old = getattr(node, "text", None) or cand.get("text") or query
                full_new = full_old.replace(query, new_val) if query in full_old else new_val
                stage_res = self.session.stage_edit(new_text=full_new, node_id=cand.get("node_id"))
                if stage_res.get("ok"):
                    activity.append({"tool": "stage_transaction", "status": "staged"})
                    op = stage_res.get("operation") or {}
                    proposed_ops.append({k: v for k, v in op.items() if k != "raster_op"})
                    status = "WAITING_HUMAN_APPROVAL"
                    reply = (f"Preparé el cambio de «{query}» por «{new_val}». Revísalo en «Cambios»; "
                             f"solo se aplicará si pulsas «Verificar y crear copia» y la verificación lo aprueba.")
                else:
                    reply = f"No pude preparar el cambio: {stage_res.get('error')}"
        else:
            summary = self.session.get_summary()
            activity.append({"tool": "document_summary", "status": "executed"})
            reply = (f"Documento {self.session.source_filename}: {summary['page_count']} página(s). "
                     "Por ahora entiendo peticiones como: Cambia «texto actual» por «texto nuevo».")

        response_entry = {
            "role": "agent",
            "content": reply,
            "tool_activity": activity,
            "proposed_operations": proposed_ops,
            "candidates": candidates,
            "review_required": self.review_required,
            "status": status,
            "engine": "DETERMINISTIC_PARSER_NO_LLM",
        }
        self.conversation_history.append(response_entry)
        return response_entry
