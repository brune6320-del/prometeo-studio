"""PROMETEO · Compact Context Protocol & Windowing v0.2
────────────────────────────────────────────────────
Resuelve el problema de context-window permitiendo a los agentes navegar
estructuras documentales de forma progresiva sin saturación de tokens:

- LEVEL 0: Document Summary (~200 tokens)
- LEVEL 1: Hierarchical Outline (~2k-4k tokens)
- LEVEL 2: Node Window (~300 tokens)
- LEVEL 3: Local Graph / Spatial Neighborhood (~600 tokens)
- LEVEL 4: Full Graph (solo debugging offline)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from .model import BaseNode, DocGraph, GroupNode, NodeType, PageNode, TextNode
from .outline import render_outline


def get_document_summary(graph: DocGraph) -> Dict[str, Any]:
    """LEVEL 0: Resumen ultracompacto del documento (~150-250 tokens)."""
    text_nodes = graph.nodes_by_type(NodeType.TEXT)
    vector_nodes = graph.nodes_by_type(NodeType.VECTOR)
    image_nodes = graph.nodes_by_type(NodeType.IMAGE)
    group_nodes = graph.nodes_by_type(NodeType.GROUP)
    pages = [n for n in graph.nodes.values() if isinstance(n, PageNode)]
    pages.sort(key=lambda p: p.page_number)

    fonts = sorted({t.font for t in text_nodes if isinstance(t, TextNode) and t.font})
    total_chars = sum(len(t.text) for t in text_nodes if isinstance(t, TextNode))

    page_dimensions = [
        {"page": p.page_number, "width_pt": p.width_pt, "height_pt": p.height_pt}
        for p in pages
    ]

    return {
        "context_level": "LEVEL_0_SUMMARY",
        "document_id": graph.document_id,
        "source_sha256": graph.source_sha256,
        "page_count": graph.page_count,
        "total_nodes": len(graph.nodes),
        "node_counts": {
            "text": len(text_nodes),
            "vector": len(vector_nodes),
            "image": len(image_nodes),
            "group": len(group_nodes),
        },
        "total_characters": total_chars,
        "fonts_present": fonts,
        "pages": page_dimensions,
    }


def get_document_outline_context(
    graph: DocGraph,
    pages: Optional[Sequence[int]] = None,
    types: Optional[Sequence[str]] = None,
    max_depth: Optional[int] = None,
    max_text_len: int = 50,
    show_bbox: bool = False,
    show_ids: bool = True,
    include_vectors: bool = False,
) -> Dict[str, Any]:
    """LEVEL 1: Representación en árbol jerárquico legible (~1.5k-4k tokens)."""
    text = render_outline(
        graph,
        pages=pages,
        types=types,
        max_depth=max_depth,
        max_text_len=max_text_len,
        show_bbox=show_bbox,
        show_ids=show_ids,
        include_vectors=include_vectors,
    )
    return {
        "context_level": "LEVEL_1_OUTLINE",
        "document_id": graph.document_id,
        "outline_text": text,
        "line_count": len(text.splitlines()),
        "character_count": len(text),
    }


def get_node_window(graph: DocGraph, node_id: str) -> Optional[Dict[str, Any]]:
    """LEVEL 2: Ventana local centrada en un nodo específico (~300 tokens)."""
    node = graph.get_node(node_id)
    if not node:
        return None

    parent = graph.get_node(node.parent_id) if node.parent_id else None
    siblings = [
        graph.nodes[cid].to_dict()
        for cid in (parent.children_ids if parent else [])
        if cid != node_id and cid in graph.nodes
    ]

    # Identificar nodo de texto previo y siguiente en la misma página
    prev_node = None
    next_node = None
    if node.page is not None and node.node_type == NodeType.TEXT.value:
        page_texts = [
            n for n in graph.nodes.values()
            if n.page == node.page and n.node_type == NodeType.TEXT.value
        ]
        # Orden de lectura aproximado: top to bottom, left to right
        page_texts.sort(key=lambda n: (n.bbox[1] if n.bbox else 0, n.bbox[0] if n.bbox else 0))
        for idx, t in enumerate(page_texts):
            if t.node_id == node_id:
                if idx > 0:
                    prev_node = page_texts[idx - 1].to_dict()
                if idx + 1 < len(page_texts):
                    next_node = page_texts[idx + 1].to_dict()
                break

    return {
        "context_level": "LEVEL_2_NODE_WINDOW",
        "target_node": node.to_dict(),
        "parent_group": parent.to_dict() if parent else None,
        "siblings_count": len(siblings),
        "siblings": siblings[:5],  # Máximo 5 hermanos inmediatos para brevedad
        "previous_text_node": prev_node,
        "next_text_node": next_node,
    }


def get_node_neighbors(
    graph: DocGraph,
    node_id: str,
    same_page: bool = True,
    spatial_radius: Optional[float] = 36.0,
    relation_types: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    """LEVEL 3: Subgrafo espacial y relacional de vecindad (~500 tokens)."""
    node = graph.get_node(node_id)
    if not node:
        return None

    # 1. Vecinos por relaciones (materializadas y derivadas)
    direct_relations = []
    rel_type_param = relation_types[0] if (relation_types and len(relation_types) == 1) else None
    allowed_rel_types = set(relation_types) if relation_types else None

    for r in graph.relations_of(node_id, relation_type=rel_type_param, direction="both", include_derived=True):
        if allowed_rel_types and r.relation_type not in allowed_rel_types:
            continue
        direction = "out" if r.source_id == node_id else "in"
        other_id = r.target_id if r.source_id == node_id else r.source_id
        other_node = graph.get_node(other_id)
        if other_node:
            direct_relations.append({
                "direction": direction,
                "relation_type": r.relation_type,
                "relation_origin": r.metadata.get("relation_origin", "MATERIALIZED"),
                "neighbor": other_node.to_dict(),
            })

    # 2. Vecinos espaciales dentro de spatial_radius
    spatial_neighbors = []
    if spatial_radius is not None and node.page is not None and node.bbox is not None:
        x0, y0, x1, y1 = node.bbox
        search_rect = [
            x0 - spatial_radius,
            y0 - spatial_radius,
            x1 + spatial_radius,
            y1 + spatial_radius,
        ]
        in_area = graph.nodes_in_rect(
            page=node.page,
            rect=search_rect,
            contain_mode="intersects",
            include_pages=False,
        )
        for n in in_area:
            if n.node_id != node_id:
                spatial_neighbors.append({
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "bbox": n.bbox,
                    "text": getattr(n, "text", None),
                })

    return {
        "context_level": "LEVEL_3_LOCAL_GRAPH",
        "node_id": node_id,
        "direct_relations_count": len(direct_relations),
        "direct_relations": direct_relations[:10],
        "spatial_radius_pt": spatial_radius,
        "spatial_neighbors_count": len(spatial_neighbors),
        "spatial_neighbors": spatial_neighbors[:10],
    }
