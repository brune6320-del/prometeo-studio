"""PROMETEO · Document Scene Graph (DocGraph) Package v0.2
────────────────────────────────────────────────────────
Representación estructural determinista de un documento como escena de objetos.
Incluye:
- Modelo de nodos y relaciones
- Extracción determinista desde PDF físico
- Caché indexado por contenido (SHA-256)
- Protocolo de contexto compacto (Nivel 0 a 4)
- Diferenciación estructural de grafos (DocGraph Diff)
- Vinculación de identidades estructurales a targets (NodeTargetBinding)
"""

from .binding import (
    NodeTargetBinding,
    create_binding_from_text_node,
    create_operation_provenance_v0_2,
)
from .builder import build_docgraph, sha256_file
from .cache import GLOBAL_DOCGRAPH_CACHE, DocGraphCache
from .context import (
    get_document_outline_context,
    get_document_summary,
    get_node_neighbors,
    get_node_window,
)
from .diff import docgraph_diff
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
from .outline import render_outline
from .query import (
    children,
    find_text_nodes,
    get_node,
    nodes_by_type,
    nodes_in_rect,
    nodes_on_page,
    parent,
    relations_of,
)
from .serialize import (
    docgraph_from_dict,
    docgraph_from_json,
    docgraph_to_dict,
    docgraph_to_json,
)

__all__ = [
    "DocGraph",
    "NodeType",
    "RelationType",
    "Relation",
    "BaseNode",
    "DocumentNode",
    "PageNode",
    "GroupNode",
    "TextNode",
    "ImageNode",
    "VectorNode",
    "build_docgraph",
    "sha256_file",
    "render_outline",
    "docgraph_to_dict",
    "docgraph_to_json",
    "docgraph_from_dict",
    "docgraph_from_json",
    "get_node",
    "children",
    "parent",
    "nodes_by_type",
    "nodes_on_page",
    "nodes_in_rect",
    "find_text_nodes",
    "relations_of",
    "DocGraphCache",
    "GLOBAL_DOCGRAPH_CACHE",
    "get_document_summary",
    "get_document_outline_context",
    "get_node_window",
    "get_node_neighbors",
    "docgraph_diff",
    "NodeTargetBinding",
    "create_binding_from_text_node",
    "create_operation_provenance_v0_2",
]
