"""PROMETEO · Target-Node Binding & Operation Provenance v0.2
──────────────────────────────────────────────────────────
Establece el puente formal entre las identidades de interacción del Tool Contract
(candidate_id, target_id) y las identidades estructurales de la escena (node_id).

Evita la fragmentación en tres sistemas no mapeados y permite trazabilidad
completa desde el PDF físico hasta el resultado del Verifier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from .model import DocGraph, NodeType, TextNode


@dataclass
class NodeTargetBinding:
    """Mapeo unívoco entre un nodo estructural del DocGraph y un target de edición."""
    node_id: str
    document_id: str
    candidate_id: str
    target_id: str
    source_span: str
    page: int
    bbox: Tuple[float, float, float, float]
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_binding_from_text_node(
    document_id: str,
    node: TextNode,
    candidate_index: int = 0,
) -> NodeTargetBinding:
    """Crea una vinculación canónica a partir de un TextNode de DocGraph."""
    span_id = node.provenance.get("source_span", f"p{node.page}s{candidate_index}")
    c_id = f"cand_{document_id[:8]}_{span_id}"
    t_id = f"tgt_{document_id[:8]}_{span_id}"
    return NodeTargetBinding(
        node_id=node.node_id,
        document_id=document_id,
        candidate_id=c_id,
        target_id=t_id,
        source_span=span_id,
        page=node.page if node.page is not None else 0,
        bbox=node.bbox if node.bbox is not None else (0.0, 0.0, 0.0, 0.0),
        text=node.text,
    )


def create_operation_provenance_v0_2(
    graph: DocGraph,
    node_id: str,
    operation_type: str = "replace_text",
) -> Dict[str, Any]:
    """Genera el registro de provenance v0.2 para una operación."""
    node = graph.get_node(node_id)
    return {
        "operation_type": operation_type,
        "source_node_id": node_id,
        "source_docgraph_version": graph.docgraph_version,
        "source_document_id": graph.document_id,
        "source_document_sha256": graph.source_sha256,
        "source_page": node.page if node else None,
        "source_bbox": node.bbox if node else None,
        "provenance_raw": node.provenance if node else {},
    }
