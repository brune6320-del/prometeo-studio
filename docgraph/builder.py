"""PROMETEO · DocGraph Builder v0.1
─────────────────────────────────
Construye el Scene Graph determinista a partir de la estructura física del PDF:
- Raíz: DocumentNode
- Contenedores: PageNodes
- Agrupaciones observables: GroupNodes (bloques de texto)
- Hojas de contenido: TextNodes, ImageNodes, VectorNodes
- Relaciones observables: PARENT_OF, CHILD_OF, SAME_PAGE, SAME_TEXT_BLOCK, SAME_LINE, INTERSECTS.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymupdf

from .model import (
    BaseNode,
    DocGraph,
    DocumentNode,
    GroupNode,
    ImageNode,
    NodeType,
    PageNode,
    Relation,
    RelationType,
    TextNode,
    VectorNode,
)

RIGHT_MARGIN_PT = 36.0


def sha256_file(path: str) -> str:
    """Calcula el digest SHA-256 de un archivo en disco de forma eficiente."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bboxes_intersect(b1: Tuple[float, float, float, float], b2: Tuple[float, float, float, float]) -> bool:
    """Comprueba si dos cajas de límites AABB se intersectan con área positiva."""
    return not (b1[2] <= b2[0] or b1[0] >= b2[2] or b1[3] <= b2[1] or b1[1] >= b2[3])


def build_docgraph(pdf_path: str, docgraph_version: str = "0.3") -> DocGraph:
    """Extrae la escena completa de un PDF produciendo un DocGraph inmutable y determinista.
    
    En docgraph_version="0.3", SAME_TEXT_BLOCK se des-materializa y se deriva dinámicamente
    mediante DocGraph.relations_of(), eliminando la explosión cuadrática en documentos extensos.
    """
    abs_path = os.path.abspath(pdf_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Documento no encontrado: {abs_path}")

    source_sha = sha256_file(abs_path)
    doc = pymupdf.open(abs_path)

    doc_id = f"doc_{source_sha[:16]}"
    doc_node = DocumentNode(
        node_id=doc_id,
        node_type=NodeType.DOCUMENT.value,
        page=None,
        bbox=None,
        parent_id=None,
        children_ids=[],
        source_path=abs_path,
        source_sha256=source_sha,
        page_count=len(doc),
        docgraph_version=docgraph_version,
        created_from_engine_version="prometeo_v0.1_tools",
        metadata={k: str(v) for k, v in (doc.metadata or {}).items() if v},
        provenance={"source_file": os.path.basename(abs_path), "source_sha256": source_sha},
    )

    nodes: Dict[str, BaseNode] = {doc_id: doc_node}
    relations: List[Relation] = []

    for pno, page in enumerate(doc):
        page_id = f"page_{pno}"
        width_pt = float(page.rect.width)
        height_pt = float(page.rect.height)
        page_bbox = (0.0, 0.0, width_pt, height_pt)

        page_node = PageNode(
            node_id=page_id,
            node_type=NodeType.PAGE.value,
            page=pno,
            bbox=page_bbox,
            parent_id=doc_id,
            children_ids=[],
            page_number=pno,
            width_pt=width_pt,
            height_pt=height_pt,
            rotation=int(page.rotation),
            provenance={"source_page": pno},
        )
        nodes[page_id] = page_node
        doc_node.children_ids.append(page_id)

        relations.append(Relation(doc_id, page_id, RelationType.PARENT_OF.value))
        relations.append(Relation(page_id, doc_id, RelationType.CHILD_OF.value))

        raw_dict = page.get_text("rawdict")
        blocks = raw_dict.get("blocks", [])

        span_idx = 0
        page_content_nodes: List[BaseNode] = []

        # 1. Extraer bloques de texto y spans (GroupNodes y TextNodes)
        for b_idx, block in enumerate(blocks):
            if block.get("type") != 0:
                continue

            group_id = f"group_p{pno}_b{b_idx}"
            b_box = tuple(float(c) for c in block["bbox"])
            group_node = GroupNode(
                node_id=group_id,
                node_type=NodeType.GROUP.value,
                page=pno,
                bbox=b_box,
                parent_id=page_id,
                children_ids=[],
                group_type="TEXT_BLOCK",
                provenance={"source_page": pno, "source_block": b_idx},
            )
            nodes[group_id] = group_node
            page_node.children_ids.append(group_id)
            page_content_nodes.append(group_node)

            relations.append(Relation(page_id, group_id, RelationType.PARENT_OF.value))
            relations.append(Relation(group_id, page_id, RelationType.CHILD_OF.value))

            block_text_node_ids: List[str] = []

            for l_idx, line in enumerate(block.get("lines", [])):
                line_spans = sorted(line.get("spans", []), key=lambda s: s["bbox"][0])
                line_text_node_ids: List[str] = []

                for i, s in enumerate(line_spans):
                    origin_x = float(s["origin"][0])
                    if i + 1 < len(line_spans):
                        available = float(line_spans[i + 1]["bbox"][0]) - origin_x
                    else:
                        available = width_pt - RIGHT_MARGIN_PT - origin_x

                    chars = s.get("chars", [])
                    if chars:
                        text = "".join(ch.get("c", "") for ch in chars)
                    else:
                        text = s.get("text", "")

                    text_id = f"text_p{pno}_s{span_idx}"
                    s_bbox = tuple(float(c) for c in s["bbox"])
                    s_origin = tuple(float(c) for c in s["origin"])
                    clearance = float(max(available, 1.0))

                    text_node = TextNode(
                        node_id=text_id,
                        node_type=NodeType.TEXT.value,
                        page=pno,
                        bbox=s_bbox,
                        parent_id=group_id,
                        children_ids=[],
                        text=text,
                        font=str(s.get("font", "")),
                        font_size=float(s.get("size", 0.0)),
                        origin=s_origin,
                        clearance_pt=clearance,
                        color=s.get("color"),
                        flags=s.get("flags"),
                        rotation=s.get("rotation"),
                        provenance={
                            "source_page": pno,
                            "source_block": b_idx,
                            "source_line": l_idx,
                            "source_span": f"p{pno}s{span_idx}",
                            "char_count": len(text),
                        },
                    )

                    nodes[text_id] = text_node
                    group_node.children_ids.append(text_id)
                    block_text_node_ids.append(text_id)
                    line_text_node_ids.append(text_id)

                    relations.append(Relation(group_id, text_id, RelationType.PARENT_OF.value))
                    relations.append(Relation(text_id, group_id, RelationType.CHILD_OF.value))
                    span_idx += 1

                # Relaciones SAME_LINE entre TextNodes de la misma línea
                if len(line_text_node_ids) > 1:
                    for idx_a in range(len(line_text_node_ids)):
                        for idx_b in range(idx_a + 1, len(line_text_node_ids)):
                            relations.append(Relation(line_text_node_ids[idx_a], line_text_node_ids[idx_b], RelationType.SAME_LINE.value))
                            relations.append(Relation(line_text_node_ids[idx_b], line_text_node_ids[idx_a], RelationType.SAME_LINE.value))

            # Relaciones SAME_TEXT_BLOCK: materializadas solo en versiones legadas (<0.3).
            # En v0.3 son virtuales y se derivan en tiempo de consulta mediante DocGraph.relations_of()
            if docgraph_version in ("0.1", "0.2") and len(block_text_node_ids) > 1:
                for idx_a in range(len(block_text_node_ids)):
                    for idx_b in range(idx_a + 1, len(block_text_node_ids)):
                        relations.append(Relation(block_text_node_ids[idx_a], block_text_node_ids[idx_b], RelationType.SAME_TEXT_BLOCK.value, metadata={"relation_origin": "MATERIALIZED"}))
                        relations.append(Relation(block_text_node_ids[idx_b], block_text_node_ids[idx_a], RelationType.SAME_TEXT_BLOCK.value, metadata={"relation_origin": "MATERIALIZED"}))

        # 2. Extraer imágenes observables (ImageNodes)
        img_info_list = page.get_image_info(xrefs=True)
        for img_idx, img in enumerate(img_info_list):
            img_id = f"image_p{pno}_i{img_idx}"
            ibox = tuple(float(c) for c in img.get("bbox", (0, 0, 0, 0)))
            image_node = ImageNode(
                node_id=img_id,
                node_type=NodeType.IMAGE.value,
                page=pno,
                bbox=ibox,
                parent_id=page_id,
                children_ids=[],
                width=int(img.get("width", 0)),
                height=int(img.get("height", 0)),
                xref=img.get("xref"),
                colorspace=img.get("cs-name"),
                alpha=bool(img.get("has-mask", False)),
                provenance={
                    "source_page": pno,
                    "source_image_idx": img_idx,
                    "xref": img.get("xref"),
                },
            )
            nodes[img_id] = image_node
            page_node.children_ids.append(img_id)
            page_content_nodes.append(image_node)

            relations.append(Relation(page_id, img_id, RelationType.PARENT_OF.value))
            relations.append(Relation(img_id, page_id, RelationType.CHILD_OF.value))

        # 3. Extraer gráficos vectoriales observables (VectorNodes)
        drawings = page.get_drawings()
        for d_idx, draw in enumerate(drawings):
            vec_id = f"vector_p{pno}_d{d_idx}"
            rect = draw.get("rect")
            vbox = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)) if rect else (0.0, 0.0, 0.0, 0.0)

            raw_type = draw.get("type", "s")
            type_map = {"s": "stroke", "f": "fill", "fs": "stroke_and_fill"}
            vec_type = type_map.get(raw_type, raw_type)

            vector_node = VectorNode(
                node_id=vec_id,
                node_type=NodeType.VECTOR.value,
                page=pno,
                bbox=vbox,
                parent_id=page_id,
                children_ids=[],
                drawing_type=vec_type,
                stroke_color=draw.get("color"),
                fill_color=draw.get("fill"),
                stroke_width=float(draw.get("width", 1.0)) if draw.get("width") is not None else None,
                items_count=len(draw.get("items", [])),
                provenance={
                    "source_page": pno,
                    "source_drawing_idx": d_idx,
                },
            )
            nodes[vec_id] = vector_node
            page_node.children_ids.append(vec_id)
            page_content_nodes.append(vector_node)

            relations.append(Relation(page_id, vec_id, RelationType.PARENT_OF.value))
            relations.append(Relation(vec_id, page_id, RelationType.CHILD_OF.value))

        # 4. Relaciones espaciales entre elementos de la página (INTERSECTS / OVERLAPS)
        for i_a in range(len(page_content_nodes)):
            node_a = page_content_nodes[i_a]
            if node_a.bbox is None:
                continue
            for i_b in range(i_a + 1, len(page_content_nodes)):
                node_b = page_content_nodes[i_b]
                if node_b.bbox is None:
                    continue
                if _bboxes_intersect(node_a.bbox, node_b.bbox):
                    relations.append(Relation(node_a.node_id, node_b.node_id, RelationType.INTERSECTS.value))
                    relations.append(Relation(node_b.node_id, node_a.node_id, RelationType.INTERSECTS.value))

    doc.close()
    return DocGraph(document=doc_node, nodes=nodes, relations=relations, docgraph_version=docgraph_version)
