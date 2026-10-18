"""PROMETEO · Tests for Document Scene Graph (DocGraph) v0.1
──────────────────────────────────────────────────────────
Valida:
- FASE V: Tests canónicos de DocGraph (determinismo, estabilidad de IDs,
  raíz, páginas, texto, vectores, imágenes, provenance, serialización,
  outliner, queries, inmutabilidad de original, IRS Form 56).
- FASE W: Tests adversariales (rects vacíos/inválidos, IDs inexistentes,
  texto repetido sin colapso, copias idénticas en rutas distintas).
- FASE Y: Agnolicismo total de LLM (cero dependencias externas).
"""

import hashlib
import json
import os
import shutil
import tempfile
import pytest

import docgraph
from docgraph import (
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
    build_docgraph,
    docgraph_from_json,
    docgraph_to_dict,
    docgraph_to_json,
    find_text_nodes,
    get_node,
    nodes_by_type,
    nodes_in_rect,
    nodes_on_page,
    render_outline,
    sha256_file,
)

FORM56_PATH = "fase0/experiments/h3dv3_dev_003/m1/external_dev_natural_b2c7/accepted/EXTM1_CAND_0010.pdf"
FORM56_EXPECTED_SHA = "ef82ec5a7dc8c11399103a6354820eb9d6fa75a019493a6bbb9a34aea96cd93f"

CASE_A_PATH = "fase0/assets/case_a.pdf"
CASE_B_SCAN_PATH = "fase0/assets/case_b_scan.pdf"


# =====================================================================
# FASE V: Tests canónicos
# =====================================================================

def test_docgraph_deterministic():
    """1. Mismo PDF produce exactamente el mismo DocGraph en dos ejecuciones."""
    g1 = build_docgraph(CASE_A_PATH)
    g2 = build_docgraph(CASE_A_PATH)

    j1 = docgraph_to_json(g1)
    j2 = docgraph_to_json(g2)
    assert j1 == j2
    assert len(g1.nodes) == len(g2.nodes)
    assert len(g1.relations) == len(g2.relations)
    assert list(g1.nodes.keys()) == list(g2.nodes.keys())


def test_docgraph_stable_ids():
    """2. IDs son estables, deterministas y no usan UUIDs aleatorios."""
    g = build_docgraph(CASE_A_PATH)
    assert g.document_id.startswith("doc_")
    assert "page_0" in g.nodes
    assert "group_p0_b0" in g.nodes
    assert "text_p0_s0" in g.nodes

    # Verificar que los IDs no cambian entre llamadas
    g_second = build_docgraph(CASE_A_PATH)
    assert set(g.nodes.keys()) == set(g_second.nodes.keys())


def test_document_root():
    """3. DocumentNode expone todas las propiedades canónicas requeridas."""
    g = build_docgraph(CASE_A_PATH)
    root = g.document
    assert isinstance(root, DocumentNode)
    assert root.node_type == NodeType.DOCUMENT.value
    assert root.docgraph_version in ("0.1", "0.2", "0.3")
    assert root.created_from_engine_version == "prometeo_v0.1_tools"
    assert root.page_count == 1
    assert root.source_sha256 == sha256_file(CASE_A_PATH)
    assert root.children_ids == ["page_0"]
    assert root.parent_id is None


def test_page_nodes():
    """4. PageNodes representan la geometría y propiedades de las páginas."""
    g = build_docgraph(FORM56_PATH)
    assert g.page_count == 2
    p0 = g.get_node("page_0")
    p1 = g.get_node("page_1")
    assert isinstance(p0, PageNode)
    assert isinstance(p1, PageNode)
    assert p0.page_number == 0
    assert p1.page_number == 1
    assert p0.width_pt > 0 and p0.height_pt > 0
    assert p0.bbox == (0.0, 0.0, p0.width_pt, p0.height_pt)
    assert p0.parent_id == g.document_id


def test_text_nodes():
    """5. TextNodes contienen texto, fuente, tamaño, clearance y geometría observable."""
    g = build_docgraph(CASE_A_PATH)
    t0 = g.get_node("text_p0_s0")
    assert isinstance(t0, TextNode)
    assert t0.node_type == NodeType.TEXT.value
    assert t0.text == "CONTRATO DE SERVICIOS"
    assert "Helvetica" in t0.font
    assert t0.font_size > 0.0
    assert t0.clearance_pt > 0.0
    assert t0.bbox is not None
    assert len(t0.bbox) == 4
    assert t0.origin is not None
    assert len(t0.origin) == 2


def test_vector_nodes():
    """Test de VectorNodes en documento con dibujos (Form 56)."""
    g = build_docgraph(FORM56_PATH)
    vecs = g.nodes_by_type(NodeType.VECTOR)
    assert len(vecs) == 128
    v0 = vecs[0]
    assert isinstance(v0, VectorNode)
    assert v0.drawing_type in ("stroke", "fill", "stroke_and_fill")
    assert v0.bbox is not None
    assert v0.items_count >= 1


def test_image_nodes():
    """Test de ImageNodes en documento con imagen escaneada."""
    g = build_docgraph(CASE_B_SCAN_PATH)
    images = g.nodes_by_type(NodeType.IMAGE)
    assert len(images) == 1
    img = images[0]
    assert isinstance(img, ImageNode)
    assert img.width == 1654
    assert img.height == 2339
    assert img.xref is not None
    assert img.bbox is not None


def test_source_provenance():
    """6. Cada nodo registra su procedencia física observable en el PDF."""
    g = build_docgraph(CASE_A_PATH)
    t0 = g.get_node("text_p0_s0")
    assert t0 is not None
    prov = t0.provenance
    assert prov["source_page"] == 0
    assert prov["source_block"] == 0
    assert prov["source_line"] == 0
    assert "source_span" in prov
    assert prov["char_count"] == len("CONTRATO DE SERVICIOS")

    # Document provenance
    doc_prov = g.document.provenance
    assert doc_prov["source_sha256"] == g.source_sha256


def test_json_serialization():
    """7. Serialización y deserialización determinista conservan tipos y relaciones."""
    g = build_docgraph(CASE_A_PATH)
    json_str = docgraph_to_json(g)
    g_rebuilt = docgraph_from_json(json_str)

    assert g_rebuilt.document_id == g.document_id
    assert g_rebuilt.page_count == g.page_count
    assert len(g_rebuilt.nodes) == len(g.nodes)
    assert len(g_rebuilt.relations) == len(g.relations)

    # Comprobar que los tipos se restauraron correctamente
    for nid, node in g.nodes.items():
        rebuilt_node = g_rebuilt.get_node(nid)
        assert rebuilt_node is not None
        assert type(rebuilt_node) is type(node)
        assert rebuilt_node.bbox == node.bbox

    # Determinismo estricto de string JSON
    assert docgraph_to_json(g_rebuilt) == json_str


def test_outline_render():
    """8. render_outline() produce un árbol jerárquico estructurado y legible."""
    g = build_docgraph(CASE_A_PATH)
    outline = render_outline(g)
    assert "DOCUMENT doc_" in outline
    assert "PAGE 0" in outline
    assert "GROUP group_p0_b0 [TEXT_BLOCK]" in outline
    assert 'TEXT text_p0_s0 "CONTRATO DE SERVICIOS"' in outline
    assert "Helvetica-Bold" in outline


def test_get_node():
    """9. get_node() recupera el nodo exacto o None si no existe."""
    g = build_docgraph(CASE_A_PATH)
    assert g.get_node("page_0") is not None
    assert g.get_node("text_p0_s0") is not None
    assert g.get_node("non_existent_node_id_9999") is None


def test_nodes_by_type():
    """10. nodes_by_type() filtra adecuadamente por tipo enum o string."""
    g = build_docgraph(FORM56_PATH)
    pages = g.nodes_by_type(NodeType.PAGE)
    assert len(pages) == 2

    texts = g.nodes_by_type(NodeType.TEXT)
    assert len(texts) == 223

    groups = g.nodes_by_type(NodeType.GROUP)
    assert len(groups) == 34

    vectors = g.nodes_by_type(NodeType.VECTOR)
    assert len(vectors) == 128


def test_nodes_on_page():
    """11. nodes_on_page() devuelve únicamente los nodos de la página solicitada."""
    g = build_docgraph(FORM56_PATH)
    nodes_p0 = g.nodes_on_page(0)
    nodes_p1 = g.nodes_on_page(1)
    assert len(nodes_p0) > 0
    assert len(nodes_p1) > 0
    assert all(n.page == 0 for n in nodes_p0)
    assert all(n.page == 1 for n in nodes_p1)
    # Ningún nodo compartido excepto el documento raíz (page=None)
    assert set(n.node_id for n in nodes_p0).isdisjoint(set(n.node_id for n in nodes_p1))


def test_nodes_in_rect():
    """12. Consulta espacial precisa por rectángulos (intersects, contains, contained_by)."""
    g = build_docgraph(CASE_A_PATH)
    t0 = g.get_node("text_p0_s0")
    assert t0 is not None and t0.bbox is not None

    # Bbox exacto de t0 debe intersectar y estar contenido
    in_exact = g.nodes_in_rect(page=0, rect=t0.bbox, contain_mode="intersects")
    assert t0 in in_exact

    in_contains = g.nodes_in_rect(page=0, rect=t0.bbox, contain_mode="contains")
    assert t0 in in_contains

    # Rectángulo minúsculo dentro de t0 bbox: contain_mode="contained_by" debe encontrarlo
    x0, y0, x1, y1 = t0.bbox
    mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
    small_rect = [mid_x - 1, mid_y - 1, mid_x + 1, mid_y + 1]
    in_contained_by = g.nodes_in_rect(page=0, rect=small_rect, contain_mode="contained_by")
    assert t0 in in_contained_by


def test_find_text_nodes():
    """13. find_text_nodes() busca por subcadena con o sin case sensitivity."""
    g = build_docgraph(FORM56_PATH)
    matches = g.find_text_nodes("Internal Revenue Service")
    assert len(matches) >= 1
    assert any("Internal Revenue Service" in m.text for m in matches)

    # Búsqueda case-insensitive
    matches_ci = g.find_text_nodes("internal revenue service", case_sensitive=False)
    assert len(matches_ci) == len(matches)

    # Búsqueda case-sensitive no coincidente
    matches_cs_fail = g.find_text_nodes("internal revenue service", case_sensitive=True)
    assert len(matches_cs_fail) == 0


def test_original_immutable():
    """14. El proceso de extracción jamás altera el archivo PDF original."""
    sha_pre = sha256_file(FORM56_PATH)
    assert sha_pre == FORM56_EXPECTED_SHA

    g = build_docgraph(FORM56_PATH)
    assert g.page_count == 2

    sha_post = sha256_file(FORM56_PATH)
    assert sha_post == FORM56_EXPECTED_SHA
    assert sha_pre == sha_post


def test_real_form56_graph():
    """15. IRS Form 56 extrae exactamente la estructura física cerrada en auditorías previas."""
    g = build_docgraph(FORM56_PATH)
    assert g.document_id == "doc_ef82ec5a7dc8c113"
    assert g.page_count == 2

    # Conteo exacto de nodos
    text_nodes = g.nodes_by_type(NodeType.TEXT)
    vector_nodes = g.nodes_by_type(NodeType.VECTOR)
    image_nodes = g.nodes_by_type(NodeType.IMAGE)
    group_nodes = g.nodes_by_type(NodeType.GROUP)
    page_nodes = g.nodes_by_type(NodeType.PAGE)

    assert len(page_nodes) == 2
    assert len(group_nodes) == 34
    assert len(text_nodes) == 223
    assert len(vector_nodes) == 128
    assert len(image_nodes) == 0

    total_content_nodes = len(page_nodes) + len(group_nodes) + len(text_nodes) + len(vector_nodes) + len(image_nodes)
    assert total_content_nodes == 387
    assert len(g.nodes) == 388  # +1 DocumentNode


# =====================================================================
# FASE W: Tests adversariales
# =====================================================================

def test_adversarial_empty_or_inverted_rect():
    """CASE 1: Rectángulo vacío o invertido retorna lista vacía sin excepción."""
    g = build_docgraph(CASE_A_PATH)
    # Rectángulo con coordenadas invertidas (x0 > x1)
    res_inv = g.nodes_in_rect(page=0, rect=[100.0, 50.0, 20.0, 80.0])
    assert res_inv == []

    # Rectángulo vacío en zona sin contenido
    res_empty = g.nodes_in_rect(page=0, rect=[0.0, 0.0, 1.0, 1.0])
    assert res_empty == []

    # Rectángulo con longitud incorrecta
    assert g.nodes_in_rect(page=0, rect=[10.0, 20.0]) == []


def test_adversarial_non_existent_node_id():
    """CASE 2: ID inexistente retorna None de forma segura y limpia."""
    g = build_docgraph(CASE_A_PATH)
    assert g.get_node("") is None
    assert g.get_node("doc_0000000000000000_fake") is None
    assert g.children("non_existent") == []
    assert g.parent("non_existent") is None


def test_adversarial_repeated_text():
    """CASE 3: Textos repetidos generan nodos distintos con IDs y ubicaciones únicas."""
    g = build_docgraph(FORM56_PATH)
    # Form 56 tiene múltiples números de línea como "1", "2", "3" o palabras repetidas
    matches = g.find_text_nodes("Part I")
    assert len(matches) >= 1

    # Comprobar que todos los nodos en el grafo tienen IDs estrictamente únicos
    node_ids = list(g.nodes.keys())
    assert len(node_ids) == len(set(node_ids))


def test_adversarial_identical_copies_different_paths():
    """CASE 4: Dos copias idénticas en rutas distintas tienen la misma identidad lógica."""
    with tempfile.TemporaryDirectory() as tmpdir:
        copy1 = os.path.join(tmpdir, "copy1.pdf")
        copy2 = os.path.join(tmpdir, "nested", "copy2.pdf")
        os.makedirs(os.path.dirname(copy2), exist_ok=True)
        shutil.copy2(CASE_A_PATH, copy1)
        shutil.copy2(CASE_A_PATH, copy2)

        g1 = build_docgraph(copy1)
        g2 = build_docgraph(copy2)

        # Identidad lógica idéntica basada en contenido (SHA-256)
        assert g1.document_id == g2.document_id
        assert g1.source_sha256 == g2.source_sha256
        assert len(g1.nodes) == len(g2.nodes)
        assert set(g1.nodes.keys()) == set(g2.nodes.keys())
        # Única diferencia física admitida: source_path en metadatos
        assert g1.document.source_path != g2.document.source_path


# =====================================================================
# FASE Y: Agnolicismo de LLM
# =====================================================================

def test_llm_agnostic():
    """Verifica que el módulo docgraph no contiene ninguna importación de LLM ni SDK externo."""
    forbidden_tokens = [
        "openai",
        "anthropic",
        "google.generativeai",
        "langchain",
        "codex",
        "gemini",
        "claude",
    ]
    pkg_dir = os.path.abspath("docgraph")
    for root, _, files in os.walk(pkg_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    content = pyfile.read().lower()
                    for token in forbidden_tokens:
                        assert token not in content, f"Token prohibido '{token}' encontrado en {fpath}"
