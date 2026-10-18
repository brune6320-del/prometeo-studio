"""PROMETEO · DocGraph Diff v0.1
──────────────────────────────
Compara estructuralmente dos instancias de DocGraph (ej. original vs documento editado).
Genera una explicación interpretable de cambios para auditoría, agentes y futuro Studio:
- Nodos añadidos
- Nodos eliminados
- Nodos modificados (deltas de texto, tipografía y desplazamiento geométrico AABB)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .model import DocGraph, NodeType, TextNode


def _calc_bbox_delta(
    b1: Optional[Tuple[float, float, float, float]],
    b2: Optional[Tuple[float, float, float, float]],
) -> Optional[Dict[str, float]]:
    if b1 is None or b2 is None:
        return None
    return {
        "dx0": round(b2[0] - b1[0], 4),
        "dy0": round(b2[1] - b1[1], 4),
        "dx1": round(b2[2] - b1[2], 4),
        "dy1": round(b2[3] - b1[3], 4),
        "d_width": round((b2[2] - b2[0]) - (b1[2] - b1[0]), 4),
        "d_height": round((b2[3] - b2[1]) - (b1[3] - b1[1]), 4),
    }


def docgraph_diff(graph_before: DocGraph, graph_after: DocGraph) -> Dict[str, Any]:
    """Calcula la diferencia estructural entre dos escenas documentales."""
    if graph_before.source_sha256 == graph_after.source_sha256:
        return {
            "document_id_before": graph_before.document_id,
            "document_id_after": graph_after.document_id,
            "source_sha256_before": graph_before.source_sha256,
            "source_sha256_after": graph_after.source_sha256,
            "summary": {
                "added_count": 0,
                "removed_count": 0,
                "changed_count": 0,
                "total_nodes_before": len(graph_before.nodes),
                "total_nodes_after": len(graph_after.nodes),
            },
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": [],
        }

    nodes_before = graph_before.nodes
    nodes_after = graph_after.nodes

    # Separar TextNodes de otros nodos estructurales
    text_before = [n for n in nodes_before.values() if isinstance(n, TextNode)]
    text_after = [n for n in nodes_after.values() if isinstance(n, TextNode)]

    other_before = {k: v for k, v in nodes_before.items() if not isinstance(v, TextNode)}
    other_after = {k: v for k, v in nodes_after.items() if not isinstance(v, TextNode)}

    # Comparar otros nodos por ID
    other_ids_before = set(other_before.keys())
    other_ids_after = set(other_after.keys())
    other_added = sorted(other_ids_after - other_ids_before)
    other_removed = sorted(other_ids_before - other_ids_after)
    other_common = sorted(other_ids_before & other_ids_after)

    changed_nodes: List[Dict[str, Any]] = []

    for nid in other_common:
        n1 = other_before[nid]
        n2 = other_after[nid]
        if n1.bbox != n2.bbox:
            changed_nodes.append({
                "node_id": nid,
                "node_type": n1.node_type,
                "page": n1.page,
                "bbox_changed": True,
                "old_bbox": n1.bbox,
                "new_bbox": n2.bbox,
                "geometry_delta": _calc_bbox_delta(n1.bbox, n2.bbox),
            })

    # Alinear TextNodes espacialmente por (page, origin)
    matched_after_ids = set()
    text_removed = []

    for n1 in text_before:
        # Buscar en text_after candidato con misma página y origen cercano
        candidates = [
            n2 for n2 in text_after
            if n2.page == n1.page
            and n2.node_id not in matched_after_ids
            and abs(n2.origin[1] - n1.origin[1]) <= 2.5
            and abs(n2.origin[0] - n1.origin[0]) <= 3.0
        ]
        if candidates:
            # Seleccionar el más cercano geométricamente
            n2 = min(candidates, key=lambda c: (c.origin[0] - n1.origin[0])**2 + (c.origin[1] - n1.origin[1])**2)
            matched_after_ids.add(n2.node_id)

            t1_norm = n1.text.replace("\xa0", " ")
            t2_norm = n2.text.replace("\xa0", " ")
            text_changed = (t1_norm != t2_norm)
            font_changed = (n1.font != n2.font or abs(n1.font_size - n2.font_size) > 0.05)
            bbox_changed = any(abs(c1 - c2) > 0.5 for c1, c2 in zip(n1.bbox, n2.bbox))

            if text_changed or font_changed or bbox_changed:
                changed_nodes.append({
                    "node_id": n1.node_id,
                    "target_node_id": n2.node_id,
                    "node_type": NodeType.TEXT.value,
                    "page": n1.page,
                    "text_changed": text_changed,
                    "old_text": t1_norm,
                    "new_text": t2_norm,
                    "font_changed": font_changed,
                    "old_font": n1.font,
                    "new_font": n2.font,
                    "old_font_size": n1.font_size,
                    "new_font_size": n2.font_size,
                    "bbox_changed": bbox_changed,
                    "old_bbox": n1.bbox,
                    "new_bbox": n2.bbox,
                    "geometry_delta": _calc_bbox_delta(n1.bbox, n2.bbox),
                })
        else:
            text_removed.append(n1)

    text_added = [n for n in text_after if n.node_id not in matched_after_ids]

    added_nodes = [other_after[nid].to_dict() for nid in other_added] + [n.to_dict() for n in text_added]
    removed_nodes = [other_before[nid].to_dict() for nid in other_removed] + [n.to_dict() for n in text_removed]

    return {
        "document_id_before": graph_before.document_id,
        "document_id_after": graph_after.document_id,
        "source_sha256_before": graph_before.source_sha256,
        "source_sha256_after": graph_after.source_sha256,
        "summary": {
            "added_count": len(added_nodes),
            "removed_count": len(removed_nodes),
            "changed_count": len(changed_nodes),
            "total_nodes_before": len(nodes_before),
            "total_nodes_after": len(nodes_after),
        },
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "changed_nodes": changed_nodes,
    }
