"""PROMETEO · Document Scene Graph (DocGraph) Data Model v0.1
──────────────────────────────────────────────────────────
Representa la jerarquía navegable, geométrica y estructurada de un documento PDF:
DOCUMENT → PAGES → GROUPS / OBJECTS (Text, Image, Vector) → RELATIONS.

Principios:
1. Determinista y serializable.
2. Agnóstico de LLM (cero dependencias externas).
3. Read-only en v0.1 (la mutación pertenece al Core documental).
4. Geometría como ciudadano de primera clase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class NodeType(str, Enum):
    DOCUMENT = "DOCUMENT"
    PAGE = "PAGE"
    GROUP = "GROUP"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VECTOR = "VECTOR"


class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    PARENT_OF = "PARENT_OF"
    CHILD_OF = "CHILD_OF"
    INTERSECTS = "INTERSECTS"
    OVERLAPS = "OVERLAPS"
    SAME_PAGE = "SAME_PAGE"
    SAME_TEXT_BLOCK = "SAME_TEXT_BLOCK"
    SAME_LINE = "SAME_LINE"


@dataclass
class Relation:
    """Relación observable entre dos nodos del grafo de escena."""
    source_id: str
    target_id: str
    relation_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Relation:
        return cls(
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation_type=d["relation_type"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class BaseNode:
    """Nodo base para cualquier elemento del Scene Graph."""
    node_id: str
    node_type: str
    page: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    z_order: Optional[int] = None
    visible: bool = True
    locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "page": self.page,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "parent_id": self.parent_id,
            "children_ids": list(self.children_ids),
            "z_order": self.z_order,
            "visible": self.visible,
            "locked": self.locked,
            "metadata": dict(self.metadata),
            "provenance": dict(self.provenance),
        }


@dataclass
class DocumentNode(BaseNode):
    """Raíz del documento. Su identidad lógica depende del contenido (SHA256)."""
    source_path: str = ""
    source_sha256: str = ""
    page_count: int = 0
    docgraph_version: str = "0.3"
    created_from_engine_version: str = "prometeo_v0.1_tools"

    def __post_init__(self):
        self.node_type = NodeType.DOCUMENT.value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "page_count": self.page_count,
            "docgraph_version": self.docgraph_version,
            "created_from_engine_version": self.created_from_engine_version,
        })
        return d


@dataclass
class PageNode(BaseNode):
    """Nodo contenedor de página."""
    page_number: int = 0
    width_pt: float = 0.0
    height_pt: float = 0.0
    rotation: int = 0

    def __post_init__(self):
        self.node_type = NodeType.PAGE.value
        self.page = self.page_number
        if self.bbox is None:
            self.bbox = (0.0, 0.0, self.width_pt, self.height_pt)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "page_number": self.page_number,
            "width_pt": float(self.width_pt),
            "height_pt": float(self.height_pt),
            "rotation": self.rotation,
        })
        return d


@dataclass
class GroupNode(BaseNode):
    """Agrupación estructural observable (ej. bloque de texto en el PDF)."""
    group_type: str = "TEXT_BLOCK"

    def __post_init__(self):
        self.node_type = NodeType.GROUP.value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "group_type": self.group_type,
        })
        return d


@dataclass
class TextNode(BaseNode):
    """Nodo de texto observable (span con fuente, tamaño y clearance)."""
    text: str = ""
    font: str = ""
    font_size: float = 0.0
    origin: Optional[Tuple[float, float]] = None
    clearance_pt: float = 0.0
    color: Optional[Any] = None
    flags: Optional[int] = None
    rotation: Optional[int] = None

    def __post_init__(self):
        self.node_type = NodeType.TEXT.value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "text": self.text,
            "font": self.font,
            "font_size": float(self.font_size),
            "origin": list(self.origin) if self.origin is not None else None,
            "clearance_pt": float(self.clearance_pt),
            "color": self.color,
            "flags": self.flags,
            "rotation": self.rotation,
        })
        return d


@dataclass
class ImageNode(BaseNode):
    """Nodo de imagen observable colocado en la página."""
    width: int = 0
    height: int = 0
    xref: Optional[int] = None
    colorspace: Optional[str] = None
    alpha: Optional[bool] = None

    def __post_init__(self):
        self.node_type = NodeType.IMAGE.value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "width": self.width,
            "height": self.height,
            "xref": self.xref,
            "colorspace": self.colorspace,
            "alpha": self.alpha,
        })
        return d


@dataclass
class VectorNode(BaseNode):
    """Nodo de gráfico vectorial observable (drawing path / forma)."""
    drawing_type: str = "stroke"
    stroke_color: Optional[Any] = None
    fill_color: Optional[Any] = None
    stroke_width: Optional[float] = None
    items_count: int = 1

    def __post_init__(self):
        self.node_type = NodeType.VECTOR.value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "drawing_type": self.drawing_type,
            "stroke_color": self.stroke_color,
            "fill_color": self.fill_color,
            "stroke_width": float(self.stroke_width) if self.stroke_width is not None else None,
            "items_count": self.items_count,
        })
        return d


class DocGraph:
    """Contenedor inmutable y consultable del Scene Graph documental."""

    def __init__(
        self,
        document: DocumentNode,
        nodes: Dict[str, BaseNode],
        relations: Optional[List[Relation]] = None,
        docgraph_version: str = "0.3",
    ):
        self.document = document
        self.nodes = nodes
        self.relations = relations or []
        self.docgraph_version = getattr(document, "docgraph_version", docgraph_version) or docgraph_version
        # Índices perezosos (CAMP-002 · F4). Contrato: el grafo no se modifica tras construirse
        # (ningún código del producto lo hace; comprobado por el crítico de CAMP-002). La clave
        # (id, longitud) solo detecta que se SUSTITUYA la lista o cambie su longitud; una edición en
        # su sitio (reemplazar un elemento, reordenar, cambiar `node.page`) NO se detecta: quien
        # modifique el grafo debe llamar a `invalidate_indexes()`.
        self._rel_index: Optional[Dict[str, List[int]]] = None
        self._rel_index_key: Optional[Tuple[int, int]] = None
        self._page_index: Optional[Dict[Optional[int], List[str]]] = None
        self._page_index_key: Optional[Tuple[int, int]] = None

    def invalidate_indexes(self) -> None:
        """Descarta los índices perezosos (obligatorio tras modificar `nodes` o `relations` en su sitio)."""
        self._rel_index = self._rel_index_key = None
        self._page_index = self._page_index_key = None

    def _relation_indices(self, node_id: str) -> List[int]:
        """Posiciones (en orden) de las relaciones donde aparece el nodo como origen o destino."""
        key = (id(self.relations), len(self.relations))
        if self._rel_index is None or self._rel_index_key != key:
            index: Dict[str, List[int]] = {}
            for i, r in enumerate(self.relations):
                index.setdefault(r.source_id, []).append(i)
                if r.target_id != r.source_id:
                    index.setdefault(r.target_id, []).append(i)
            self._rel_index, self._rel_index_key = index, key
        return self._rel_index.get(node_id, [])

    def _page_node_ids(self, page: Optional[int]) -> List[str]:
        """Identificadores de los nodos de una página, en el orden de `nodes`."""
        key = (id(self.nodes), len(self.nodes))
        if self._page_index is None or self._page_index_key != key:
            index: Dict[Optional[int], List[str]] = {}
            for nid, n in self.nodes.items():
                index.setdefault(n.page, []).append(nid)
            self._page_index, self._page_index_key = index, key
        return self._page_index.get(page, [])

    @property
    def root_id(self) -> str:
        return self.document.node_id

    @property
    def document_id(self) -> str:
        return self.document.node_id

    @property
    def source_sha256(self) -> str:
        return self.document.source_sha256

    @property
    def page_count(self) -> int:
        return self.document.page_count

    def get_node(self, node_id: str) -> Optional[BaseNode]:
        """Recupera un nodo por su identificador único."""
        return self.nodes.get(node_id)

    def children(self, node_id: str) -> List[BaseNode]:
        """Obtiene los nodos hijos directos de un nodo."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]

    def parent(self, node_id: str) -> Optional[BaseNode]:
        """Obtiene el nodo padre directo si existe."""
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return None
        return self.nodes.get(node.parent_id)

    def relations_of(
        self,
        node_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        include_derived: bool = True,
    ) -> List[Relation]:
        """Recupera relaciones que involucran al nodo, soportando tanto relaciones
        materializadas como derivadas dinámicamente (SAME_TEXT_BLOCK, SAME_PAGE).
        
        Cada relación incluye metadata['relation_origin'] = 'MATERIALIZED' o 'DERIVED'.
        """
        results: List[Relation] = []
        seen = set()

        rel_type_filter = relation_type.upper() if relation_type else None

        # 1. Relaciones materializadas almacenadas (vía índice: mismo orden que recorrer la lista)
        for r in (self.relations[i] for i in self._relation_indices(node_id)):
            matches_dir = False
            if direction in ("out", "both") and r.source_id == node_id:
                matches_dir = True
            elif direction in ("in", "both") and r.target_id == node_id:
                matches_dir = True

            if matches_dir:
                if rel_type_filter is None or r.relation_type.upper() == rel_type_filter:
                    meta = dict(r.metadata)
                    meta.setdefault("relation_origin", "MATERIALIZED")
                    rel = Relation(r.source_id, r.target_id, r.relation_type, meta)
                    key = (rel.source_id, rel.target_id, rel.relation_type)
                    if key not in seen:
                        seen.add(key)
                        results.append(rel)

        # 2. Relaciones derivadas dinámicamente si include_derived es True
        if include_derived:
            node = self.get_node(node_id)
            if node:
                # 2a. SAME_TEXT_BLOCK: derivada de los hijos del GroupNode padre
                if rel_type_filter is None or rel_type_filter == RelationType.SAME_TEXT_BLOCK.value:
                    if node.parent_id:
                        parent_group = self.get_node(node.parent_id)
                        if parent_group and getattr(parent_group, "node_type", "") == NodeType.GROUP.value:
                            for cid in parent_group.children_ids:
                                if cid != node_id and cid in self.nodes:
                                    key_out = (node_id, cid, RelationType.SAME_TEXT_BLOCK.value)
                                    if key_out not in seen and direction in ("out", "both"):
                                        seen.add(key_out)
                                        results.append(Relation(
                                            source_id=node_id,
                                            target_id=cid,
                                            relation_type=RelationType.SAME_TEXT_BLOCK.value,
                                            metadata={"relation_origin": "DERIVED"},
                                        ))
                                    key_in = (cid, node_id, RelationType.SAME_TEXT_BLOCK.value)
                                    if key_in not in seen and direction in ("in", "both"):
                                        seen.add(key_in)
                                        results.append(Relation(
                                            source_id=cid,
                                            target_id=node_id,
                                            relation_type=RelationType.SAME_TEXT_BLOCK.value,
                                            metadata={"relation_origin": "DERIVED"},
                                        ))

                # 2b. SAME_PAGE: derivada del atributo page
                if rel_type_filter == RelationType.SAME_PAGE.value:
                    if node.page is not None:
                        for other in self.nodes_on_page(node.page):
                            if other.node_id != node_id and other.page == node.page and other.node_type not in (NodeType.DOCUMENT.value, NodeType.PAGE.value):
                                key_out = (node_id, other.node_id, RelationType.SAME_PAGE.value)
                                if key_out not in seen and direction in ("out", "both"):
                                    seen.add(key_out)
                                    results.append(Relation(
                                        source_id=node_id,
                                        target_id=other.node_id,
                                        relation_type=RelationType.SAME_PAGE.value,
                                        metadata={"relation_origin": "DERIVED"},
                                    ))

        return results

    def nodes_by_type(self, node_type: Union[str, NodeType]) -> List[BaseNode]:
        """Filtra todos los nodos que coinciden con el tipo indicado."""
        type_str = node_type.value if isinstance(node_type, NodeType) else str(node_type)
        return [n for n in self.nodes.values() if n.node_type == type_str]

    def nodes_on_page(self, page: int) -> List[BaseNode]:
        """Devuelve todos los nodos ubicados en una página específica."""
        return [self.nodes[nid] for nid in self._page_node_ids(page)]

    def find_text_nodes(
        self,
        query: str,
        page: Optional[int] = None,
        case_sensitive: bool = False,
    ) -> List[TextNode]:
        """Encuentra todos los TextNodes cuyo texto contiene la subcadena query."""
        res: List[TextNode] = []
        q = query if case_sensitive else query.lower()
        candidates = self.nodes_on_page(page) if page is not None else self.nodes.values()
        for n in candidates:
            if n.node_type == NodeType.TEXT.value and isinstance(n, TextNode):
                if page is not None and n.page != page:
                    continue
                node_text = n.text if case_sensitive else n.text.lower()
                if q in node_text:
                    res.append(n)
        return res

    def nodes_in_rect(
        self,
        page: int,
        rect: Sequence[float],
        contain_mode: str = "intersects",
        include_pages: bool = False,
    ) -> List[BaseNode]:
        """Consulta espacial: encuentra nodos en la página especificada según rect [x0, y0, x1, y1].
        
        contain_mode:
          - 'intersects': el bbox del nodo intersecta el rectángulo de consulta.
          - 'contains': el nodo está completamente contenido dentro del rectángulo.
          - 'contained_by': el nodo contiene completamente el rectángulo de consulta.
        include_pages:
          - False (por defecto): excluye el PageNode contenedor para devolver únicamente objetos documentales.
          - True: incluye también el PageNode si cumple la condición espacial.
        """
        if len(rect) != 4:
            return []
        rx0, ry0, rx1, ry1 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
        if rx0 >= rx1 or ry0 >= ry1:
            return []

        matched: List[BaseNode] = []
        for n in self.nodes_on_page(page):
            if n.page != page or n.bbox is None:
                continue
            if not include_pages and n.node_type in (NodeType.PAGE.value, NodeType.DOCUMENT.value):
                continue
            nx0, ny0, nx1, ny1 = n.bbox

            if contain_mode == "intersects":
                # Condición de intersección estándar de rectángulos AABB con área positiva
                if not (nx1 <= rx0 or nx0 >= rx1 or ny1 <= ry0 or ny0 >= ry1):
                    matched.append(n)
            elif contain_mode == "contains":
                # El nodo está totalmente dentro del rectángulo de búsqueda
                if nx0 >= rx0 and ny0 >= ry0 and nx1 <= rx1 and ny1 <= ry1:
                    matched.append(n)
            elif contain_mode == "contained_by":
                # El nodo envuelve totalmente el rectángulo de búsqueda
                if nx0 <= rx0 and ny0 <= ry0 and nx1 >= rx1 and ny1 >= ry1:
                    matched.append(n)

        return matched

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el DocGraph completo a diccionario determinista."""
        return {
            "docgraph_version": self.docgraph_version,
            "document": self.document.to_dict(),
            "nodes": {nid: n.to_dict() for nid, n in sorted(self.nodes.items())},
            "relations": [r.to_dict() for r in self.relations],
        }
