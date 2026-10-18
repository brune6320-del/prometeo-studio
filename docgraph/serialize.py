"""PROMETEO · DocGraph Serialization v0.1
────────────────────────────────────────
Serialización y deserialización determinista de Document Scene Graphs a JSON/Dict.

Garantías:
1. Mismo DocGraph produce idéntica cadena JSON (claves ordenadas).
2. Reconstrucción completa y tipada de nodos (DocumentNode, PageNode, GroupNode, TextNode, ImageNode, VectorNode).
3. Round-trip verificado: from_json(to_json(g)) == g.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .model import (
    BaseNode,
    DocGraph,
    DocumentNode,
    GroupNode,
    ImageNode,
    NodeType,
    PageNode,
    Relation,
    TextNode,
    VectorNode,
)


def _node_from_dict(d: Dict[str, Any]) -> BaseNode:
    """Reconstruye un nodo tipado según su campo node_type."""
    ntype = d.get("node_type")
    raw_bbox = d.get("bbox")
    bbox: Optional[Tuple[float, float, float, float]] = tuple(float(c) for c in raw_bbox) if raw_bbox is not None else None

    common_kwargs = {
        "node_id": d["node_id"],
        "node_type": ntype,
        "page": d.get("page"),
        "bbox": bbox,
        "parent_id": d.get("parent_id"),
        "children_ids": list(d.get("children_ids", [])),
        "z_order": d.get("z_order"),
        "visible": bool(d.get("visible", True)),
        "locked": bool(d.get("locked", False)),
        "metadata": dict(d.get("metadata", {})),
        "provenance": dict(d.get("provenance", {})),
    }

    if ntype == NodeType.DOCUMENT.value:
        return DocumentNode(
            source_path=d.get("source_path", ""),
            source_sha256=d.get("source_sha256", ""),
            page_count=int(d.get("page_count", 0)),
            docgraph_version=d.get("docgraph_version", "0.1"),
            created_from_engine_version=d.get("created_from_engine_version", "prometeo_v0.1_tools"),
            **common_kwargs,
        )

    elif ntype == NodeType.PAGE.value:
        return PageNode(
            page_number=int(d.get("page_number", d.get("page", 0))),
            width_pt=float(d.get("width_pt", 0.0)),
            height_pt=float(d.get("height_pt", 0.0)),
            rotation=int(d.get("rotation", 0)),
            **common_kwargs,
        )

    elif ntype == NodeType.GROUP.value:
        return GroupNode(
            group_type=d.get("group_type", "TEXT_BLOCK"),
            **common_kwargs,
        )

    elif ntype == NodeType.TEXT.value:
        raw_orig = d.get("origin")
        origin: Optional[Tuple[float, float]] = tuple(float(c) for c in raw_orig) if raw_orig is not None else None
        return TextNode(
            text=d.get("text", ""),
            font=d.get("font", ""),
            font_size=float(d.get("font_size", 0.0)),
            origin=origin,
            clearance_pt=float(d.get("clearance_pt", 0.0)),
            color=d.get("color"),
            flags=d.get("flags"),
            rotation=d.get("rotation"),
            **common_kwargs,
        )

    elif ntype == NodeType.IMAGE.value:
        return ImageNode(
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            xref=d.get("xref"),
            colorspace=d.get("colorspace"),
            alpha=d.get("alpha"),
            **common_kwargs,
        )

    elif ntype == NodeType.VECTOR.value:
        return VectorNode(
            drawing_type=d.get("drawing_type", "stroke"),
            stroke_color=d.get("stroke_color"),
            fill_color=d.get("fill_color"),
            stroke_width=float(d["stroke_width"]) if d.get("stroke_width") is not None else None,
            items_count=int(d.get("items_count", 1)),
            **common_kwargs,
        )

    else:
        return BaseNode(**common_kwargs)


def docgraph_to_dict(graph: DocGraph) -> Dict[str, Any]:
    """Serializa un DocGraph a diccionario ordenado."""
    return graph.to_dict()


def docgraph_to_json(graph: DocGraph, indent: Optional[int] = 2) -> str:
    """Serializa un DocGraph a cadena JSON determinista con claves ordenadas."""
    return json.dumps(docgraph_to_dict(graph), indent=indent, sort_keys=True, ensure_ascii=False)


def docgraph_from_dict(d: Dict[str, Any]) -> DocGraph:
    """Reconstruye un objeto DocGraph completamente tipado a partir de un diccionario."""
    version = d.get("docgraph_version", "0.1")
    raw_doc = d.get("document", {})
    doc_node = _node_from_dict(raw_doc)
    if not isinstance(doc_node, DocumentNode):
        # Asegurar tipo DocumentNode
        doc_node = DocumentNode(
            node_id=raw_doc.get("node_id", "doc_unknown"),
            node_type=NodeType.DOCUMENT.value,
            source_path=raw_doc.get("source_path", ""),
            source_sha256=raw_doc.get("source_sha256", ""),
            page_count=raw_doc.get("page_count", 0),
        )

    nodes: Dict[str, BaseNode] = {}
    for nid, ndict in d.get("nodes", {}).items():
        nodes[nid] = _node_from_dict(ndict)

    relations: List[Relation] = []
    for rdict in d.get("relations", []):
        relations.append(Relation.from_dict(rdict))

    return DocGraph(
        document=doc_node,
        nodes=nodes,
        relations=relations,
        docgraph_version=version,
    )


def docgraph_from_json(json_str: str) -> DocGraph:
    """Reconstruye un DocGraph desde una cadena JSON."""
    d = json.loads(json_str)
    return docgraph_from_dict(d)
