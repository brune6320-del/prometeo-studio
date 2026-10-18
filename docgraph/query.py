"""PROMETEO · DocGraph Query Layer v0.1
────────────────────────────────────
Capa funcional de consulta e inspección sobre instancias de DocGraph.
Proporciona la interfaz requerida por el contrato de consulta estructural v0.1.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from .model import BaseNode, DocGraph, NodeType, Relation, TextNode


def get_node(graph: DocGraph, node_id: str) -> Optional[BaseNode]:
    """Obtiene un nodo por su identificador único."""
    return graph.get_node(node_id)


def children(graph: DocGraph, node_id: str) -> List[BaseNode]:
    """Devuelve los hijos directos de un nodo."""
    return graph.children(node_id)


def parent(graph: DocGraph, node_id: str) -> Optional[BaseNode]:
    """Devuelve el nodo padre directo si existe."""
    return graph.parent(node_id)


def nodes_by_type(graph: DocGraph, node_type: Union[str, NodeType]) -> List[BaseNode]:
    """Filtra todos los nodos que coinciden con el tipo indicado."""
    return graph.nodes_by_type(node_type)


def nodes_on_page(graph: DocGraph, page: int) -> List[BaseNode]:
    """Devuelve todos los nodos pertenecientes a una página."""
    return graph.nodes_on_page(page)


def nodes_in_rect(
    graph: DocGraph,
    page: int,
    rect: Sequence[float],
    contain_mode: str = "intersects",
    include_pages: bool = False,
) -> List[BaseNode]:
    """Consulta espacial: encuentra nodos en la página que coinciden con el rectángulo rect."""
    return graph.nodes_in_rect(page=page, rect=rect, contain_mode=contain_mode, include_pages=include_pages)


def find_text_nodes(
    graph: DocGraph,
    query: str,
    page: Optional[int] = None,
    case_sensitive: bool = False,
) -> List[TextNode]:
    """Encuentra nodos de texto que contengan la subcadena query."""
    return graph.find_text_nodes(query=query, page=page, case_sensitive=case_sensitive)


def relations_of(
    graph: DocGraph,
    node_id: str,
    relation_type: Optional[str] = None,
    direction: str = "both",
    include_derived: bool = True,
) -> List[Relation]:
    """Recupera relaciones (materializadas y derivadas) asociadas a un nodo."""
    return graph.relations_of(
        node_id=node_id,
        relation_type=relation_type,
        direction=direction,
        include_derived=include_derived,
    )
