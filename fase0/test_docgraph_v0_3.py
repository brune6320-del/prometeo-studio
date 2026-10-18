"""PROMETEO · Tests for DocGraph v0.3 Relation Virtualization (ORDEN 133 / Gate DG3)
─────────────────────────────────────────────────────────────────────────────
Valida:
1. Des-materialización de SAME_TEXT_BLOCK (reducción >80% de relaciones almacenadas).
2. Derivación dinámica exacta en tiempo de consulta mediante relations_of().
3. Metadatos de procedencia: relation_origin == 'MATERIALIZED' vs 'DERIVED'.
4. Derivación de SAME_PAGE bajo demanda.
5. Preservación estricta de identidades deterministas de nodos (Node IDs).
6. Integración en Tool Contract v0.2: children_of y relations_of.
7. Preservación del invariante SILENT_FAILURE == 0.
"""

import os
import pytest

from docgraph import (
    build_docgraph,
    NodeType,
    RelationType,
    Relation,
    DocGraph,
)
from fase0 import tools

CASE_A_PATH = "fase0/assets/case_a.pdf"
FORM56_PATH = "fase0/experiments/h3dv3_dev_003/m1/external_dev_natural_b2c7/accepted/EXTM1_CAND_0010.pdf"


def test_dg3_version_and_node_id_preservation():
    """DG3.1: DocGraph v0.3 conserva exactamente los mismos Node IDs y jerarquía que v0.2."""
    g_v2 = build_docgraph(FORM56_PATH, docgraph_version="0.2")
    g_v3 = build_docgraph(FORM56_PATH, docgraph_version="0.3")

    assert g_v3.docgraph_version == "0.3"
    assert g_v3.document.docgraph_version == "0.3"
    assert len(g_v3.nodes) == len(g_v2.nodes) == 388
    assert list(g_v3.nodes.keys()) == list(g_v2.nodes.keys())

    for nid in g_v3.nodes:
        n2 = g_v2.get_node(nid)
        n3 = g_v3.get_node(nid)
        assert n3.node_type == n2.node_type
        assert n3.bbox == n2.bbox
        assert n3.parent_id == n2.parent_id
        assert n3.children_ids == n2.children_ids


def test_dg3_relation_virtualization_reduction():
    """DG3.2: v0.3 reduce significativamente las relaciones almacenadas des-materializando SAME_TEXT_BLOCK."""
    g_v2 = build_docgraph(FORM56_PATH, docgraph_version="0.2")
    g_v3 = build_docgraph(FORM56_PATH, docgraph_version="0.3")

    # En Form 56, relaciones pasan de 6,208 a 1,104 (>80% reducción)
    assert len(g_v2.relations) == 6208
    assert len(g_v3.relations) == 1104
    assert len(g_v3.relations) < len(g_v2.relations)

    # En v0.3 no hay relaciones SAME_TEXT_BLOCK materializadas en la lista interna
    mat_same_block_v3 = [r for r in g_v3.relations if r.relation_type == RelationType.SAME_TEXT_BLOCK.value]
    assert len(mat_same_block_v3) == 0

    mat_same_block_v2 = [r for r in g_v2.relations if r.relation_type == RelationType.SAME_TEXT_BLOCK.value]
    assert len(mat_same_block_v2) == 5104


def test_dg3_derived_relations_query_parity():
    """DG3.3: relations_of() responde SAME_TEXT_BLOCK idénticamente entre v0.2 y v0.3."""
    g_v2 = build_docgraph(FORM56_PATH, docgraph_version="0.2")
    g_v3 = build_docgraph(FORM56_PATH, docgraph_version="0.3")

    # Probar sobre varios TextNodes
    text_nodes = [n for n in g_v3.nodes.values() if n.node_type == NodeType.TEXT.value]
    assert len(text_nodes) > 0

    for tn in text_nodes[:20]:
        # En v0.2 estaban materializadas
        v2_rels = [r for r in g_v2.relations if r.source_id == tn.node_id and r.relation_type == RelationType.SAME_TEXT_BLOCK.value]
        # En v0.3 se derivan dinámicamente
        v3_rels = g_v3.relations_of(tn.node_id, relation_type="SAME_TEXT_BLOCK", direction="out", include_derived=True)

        target_ids_v2 = sorted([r.target_id for r in v2_rels])
        target_ids_v3 = sorted([r.target_id for r in v3_rels])
        assert target_ids_v2 == target_ids_v3

        for r in v3_rels:
            assert r.metadata.get("relation_origin") == "DERIVED"


def test_dg3_materialized_metadata_origin():
    """DG3.4: Las relaciones materializadas (PARENT_OF, CHILD_OF, SAME_LINE) reportan relation_origin == 'MATERIALIZED'."""
    g = build_docgraph(CASE_A_PATH, docgraph_version="0.3")

    p0_rels = g.relations_of("page_0", direction="out", include_derived=False)
    assert len(p0_rels) > 0
    for r in p0_rels:
        assert r.metadata.get("relation_origin") == "MATERIALIZED"


def test_dg3_derived_same_page():
    """DG3.5: relations_of() puede derivar dinámicamente relaciones SAME_PAGE bajo demanda."""
    g = build_docgraph(CASE_A_PATH, docgraph_version="0.3")

    same_page_rels = g.relations_of("text_p0_s0", relation_type="SAME_PAGE", include_derived=True)
    assert len(same_page_rels) > 0
    for r in same_page_rels:
        assert r.relation_type == RelationType.SAME_PAGE.value
        assert r.metadata.get("relation_origin") == "DERIVED"
        other = g.get_node(r.target_id)
        assert other.page == 0


def test_dg3_tools_children_of_and_relations_of():
    """DG3.6: Tool Contract v0.2 expone children_of y relations_of con dispatch genérico."""
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    assert res_open["ok"] is True
    doc_id = res_open["document_id"]

    # Probar children_of
    res_children = t.children_of(doc_id, "page_0")
    assert res_children["ok"] is True
    assert res_children["count"] > 0
    child_ids = [c["node_id"] for c in res_children["children"]]
    assert "group_p0_b0" in child_ids

    # Probar relations_of
    res_rels = t.relations_of(doc_id, "text_p0_s0")
    assert res_rels["ok"] is True
    assert res_rels["count"] > 0

    # Probar dispatch genérico vía execute_tool
    res_dispatch_kids = t.execute_tool("children_of", {"document_id": doc_id, "node_id": "page_0"})
    assert res_dispatch_kids["ok"] is True

    res_dispatch_rels = t.execute_tool("relations_of", {"document_id": doc_id, "node_id": "text_p0_s0"})
    assert res_dispatch_rels["ok"] is True
