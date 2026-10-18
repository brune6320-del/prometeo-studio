"""PROMETEO · DocGraph Outliner v0.2
─────────────────────────────────
Genera una representación textual jerárquica (ASCII/Unicode) del Scene Graph documental.
Soporta filtrado por páginas, tipos de nodo, profundidad máxima, proyección geométrica
y omisión de vectores para navegación ultracompacta por agentes.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Set

from .model import (
    BaseNode,
    DocGraph,
    DocumentNode,
    GroupNode,
    ImageNode,
    NodeType,
    PageNode,
    TextNode,
    VectorNode,
)


def _format_node_label(
    node: BaseNode,
    max_text_len: int = 50,
    show_bbox: bool = False,
    show_ids: bool = True,
) -> str:
    """Formatea la etiqueta descriptiva de una línea para un nodo."""
    bbox_str = ""
    if show_bbox and node.bbox:
        bbox_str = f" [bbox: {', '.join(f'{c:.1f}' for c in node.bbox)}]"

    id_str = f" {node.node_id}" if show_ids else ""

    if isinstance(node, DocumentNode):
        return f"DOCUMENT{id_str} (pages: {node.page_count}){bbox_str}"

    elif isinstance(node, PageNode):
        return f"PAGE {node.page_number} [{node.width_pt:.1f} x {node.height_pt:.1f} pt]{bbox_str}"

    elif isinstance(node, GroupNode):
        return f"GROUP{id_str} [{node.group_type}]{bbox_str}"

    elif isinstance(node, TextNode):
        clean_text = node.text.replace("\n", " ").replace("\r", "")
        if len(clean_text) > max_text_len:
            clean_text = clean_text[: max_text_len - 3] + "..."
        font_info = f"{node.font}, {node.font_size:.1f}pt"
        return f'TEXT{id_str} "{clean_text}" ({font_info}){bbox_str}'

    elif isinstance(node, ImageNode):
        xref_str = f", xref: {node.xref}" if node.xref is not None else ""
        return f"IMAGE{id_str} [{node.width}x{node.height} px{xref_str}]{bbox_str}"

    elif isinstance(node, VectorNode):
        return f"VECTOR{id_str} [{node.drawing_type}, items: {node.items_count}]{bbox_str}"

    else:
        return f"{node.node_type}{id_str}{bbox_str}"


def render_outline(
    graph: DocGraph,
    pages: Optional[Sequence[int]] = None,
    types: Optional[Sequence[str]] = None,
    max_depth: Optional[int] = None,
    max_text_len: int = 50,
    show_bbox: bool = False,
    show_ids: bool = True,
    include_vectors: bool = True,
) -> str:
    """Genera la representación en árbol jerárquico del DocGraph con filtrado configurable."""
    lines: List[str] = []
    allowed_types: Optional[Set[str]] = {t.upper() for t in types} if types else None
    allowed_pages: Optional[Set[int]] = set(pages) if pages is not None else None

    root = graph.document
    lines.append(_format_node_label(root, max_text_len=max_text_len, show_bbox=show_bbox, show_ids=show_ids))

    def _should_include(node: BaseNode) -> bool:
        if isinstance(node, PageNode):
            if allowed_pages is not None and node.page_number not in allowed_pages:
                return False
            return True

        if not include_vectors and node.node_type == NodeType.VECTOR.value:
            return False

        if allowed_types is not None:
            # Groups are structural containers: if any child is allowed, group is retained
            if node.node_type == NodeType.GROUP.value:
                has_valid_child = any(
                    graph.nodes[cid].node_type in allowed_types
                    for cid in node.children_ids
                    if cid in graph.nodes
                )
                return has_valid_child
            if node.node_type not in allowed_types:
                return False

        return True

    def _render_children(parent_id: str, prefix: str, depth: int) -> None:
        if max_depth is not None and depth >= max_depth:
            return

        parent = graph.get_node(parent_id)
        if not parent or not parent.children_ids:
            return

        candidate_children = [
            graph.nodes[cid]
            for cid in parent.children_ids
            if cid in graph.nodes and _should_include(graph.nodes[cid])
        ]
        total = len(candidate_children)

        for idx, child in enumerate(candidate_children):
            is_last = idx == total - 1
            branch = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "

            label = _format_node_label(
                child,
                max_text_len=max_text_len,
                show_bbox=show_bbox,
                show_ids=show_ids,
            )
            lines.append(f"{prefix}{branch}{label}")

            if child.children_ids:
                _render_children(child.node_id, prefix + child_prefix, depth + 1)

    _render_children(root.node_id, "", depth=0)
    return "\n".join(lines)
