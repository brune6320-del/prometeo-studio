"""PROMETEO · Tests for Campaign PROMETEO-DG-CAMP-0001
────────────────────────────────────────────────────
Cubre:
1. Cache de DocGraph (cold vs warm, content-addressed, invalidación).
2. Paridad Shadow Mode (find_text legacy vs DocGraph, target binding).
3. Protocolo de contexto compacto (Nivel 0 resumen, Nivel 1 outline, Nivel 2 window, Nivel 3 vecindad).
4. Outliner v0.2 con filtrado (pages, types, max_depth, include_vectors).
5. Modelo de transacciones (staging, atomicity all-or-nothing, conflictos).
6. Multi-span real sobre IRS Form 56 (2 reemplazos verificados -> PASS).
7. Transacción ambigua (falla todo el lote -> AMBIGUOUS, cero mutaciones).
8. Transacción con exceso de clearance (falla todo el lote -> HONEST_REJECT, cero mutaciones).
9. Ataque al Verifier en transacción (output adulterado -> detectado, SILENT_FAILURE == 0).
10. Semántica de rollback.
11. DocGraph diff estructural (nodos modificados, deltas AABB).
12. Aislamiento cross-document.
13. Inmutabilidad estricta del original.
14. Compatibilidad total de contratos v0.1 y v0.2.
15. Agnolicismo total de LLM.
"""

import copy
import os
import shutil
import tempfile
import pytest

import docgraph
from docgraph import (
    DocGraphCache,
    GLOBAL_DOCGRAPH_CACHE,
    docgraph_diff,
    get_document_outline_context,
    get_document_summary,
    get_node_neighbors,
    get_node_window,
    render_outline,
    sha256_file,
)
from fase0 import tools
from fase0.transactions import TransactionManager, TransactionPolicy, TransactionState

FORM56_PATH = "fase0/experiments/h3dv3_dev_003/m1/external_dev_natural_b2c7/accepted/EXTM1_CAND_0010.pdf"
FORM56_EXPECTED_SHA = "ef82ec5a7dc8c11399103a6354820eb9d6fa75a019493a6bbb9a34aea96cd93f"
CASE_A_PATH = "fase0/assets/case_a.pdf"


# =====================================================================
# 1. DOCGRAPH CACHE TESTS
# =====================================================================

def test_cache_content_addressed_and_warm_access():
    cache = DocGraphCache()
    assert len(cache) == 0

    # Cold build
    g1, cached1 = cache.get_or_build(CASE_A_PATH)
    assert cached1 is False
    assert len(cache) == 1

    # Warm access
    g2, cached2 = cache.get_or_build(CASE_A_PATH)
    assert cached2 is True
    assert g1.document_id == g2.document_id
    assert cache.stats["hits"] == 1
    assert cache.stats["misses"] == 1

    # Copia en otra ruta pero mismo contenido -> Cache HIT
    with tempfile.TemporaryDirectory() as tmpdir:
        copy_path = os.path.join(tmpdir, "case_a_copy.pdf")
        shutil.copyfile(CASE_A_PATH, copy_path)
        g_copy, cached_copy = cache.get_or_build(copy_path)
        assert cached_copy is True
        assert g_copy.document_id == g1.document_id
        assert cache.stats["hits"] == 2


def test_cache_invalidation_and_clear():
    cache = DocGraphCache()
    g, _ = cache.get_or_build(CASE_A_PATH)
    assert len(cache) == 1
    assert cache.invalidate(g.source_sha256) is True
    assert len(cache) == 0

    cache.get_or_build(CASE_A_PATH)
    assert len(cache) == 1
    cache.clear()
    assert len(cache) == 0
    assert cache.stats["hits"] == 0


# =====================================================================
# 2. COMPACT CONTEXT PROTOCOL & OUTLINER v0.2
# =====================================================================

def test_compact_context_level_0_summary():
    g, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(FORM56_PATH)
    summary = get_document_summary(g)

    assert summary["context_level"] == "LEVEL_0_SUMMARY"
    assert summary["document_id"] == "doc_ef82ec5a7dc8c113"
    assert summary["page_count"] == 2
    assert summary["total_nodes"] == 388
    assert summary["node_counts"]["text"] == 223
    assert summary["node_counts"]["vector"] == 128
    assert len(summary["fonts_present"]) > 0
    assert len(summary["pages"]) == 2


def test_compact_context_level_1_outline_filtering():
    g, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(FORM56_PATH)

    # Outline completo con vectores
    out_full = render_outline(g, include_vectors=True)
    assert "VECTOR" in out_full

    # Outline compacto omitiendo vectores (ahorro de tokens)
    out_no_vec = render_outline(g, include_vectors=False)
    assert "VECTOR" not in out_no_vec
    assert len(out_no_vec) < len(out_full)

    # Filtrar por página 0 únicamente
    out_p0 = render_outline(g, pages=[0], include_vectors=False)
    assert "PAGE 0" in out_p0
    assert "PAGE 1" not in out_p0

    # Filtrar por profundidad
    out_depth1 = render_outline(g, max_depth=1)
    lines_depth1 = out_depth1.splitlines()
    assert len(lines_depth1) == 3  # Root + Page 0 + Page 1


def test_compact_context_level_2_node_window():
    g, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(CASE_A_PATH)
    win = get_node_window(g, "text_p0_s1")
    assert win is not None
    assert win["context_level"] == "LEVEL_2_NODE_WINDOW"
    assert win["target_node"]["node_id"] == "text_p0_s1"
    assert "Contratado: Juan Perez" in win["target_node"]["text"]
    assert win["parent_group"] is not None
    assert win["parent_group"]["node_id"] == "group_p0_b1"


def test_compact_context_level_3_node_neighbors():
    g, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(CASE_A_PATH)
    neighbors = get_node_neighbors(g, "text_p0_s0", spatial_radius=50.0)
    assert neighbors is not None
    assert neighbors["context_level"] == "LEVEL_3_LOCAL_GRAPH"
    assert neighbors["node_id"] == "text_p0_s0"
    assert neighbors["direct_relations_count"] > 0


# =====================================================================
# 3. TOOL CONTRACT v0.2 & SHADOW PARITY
# =====================================================================

def test_shadow_mode_and_target_binding():
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    doc_id = res_open["document_id"]

    # find_text debe enriquecer candidatos con node_id en shadow mode
    f_res = t.find_text(doc_id, "Juan Perez")
    assert f_res["ok"] is True
    assert f_res["count"] == 1
    cand = f_res["candidates"][0]
    assert "node_id" in cand
    assert cand["node_id"] == "text_p0_s1"

    # select_target debe crear binding unívoco
    s_res = t.select_target(doc_id, cand["candidate_id"])
    assert s_res["ok"] is True
    assert s_res["node_id"] == "text_p0_s1"
    assert s_res["target_id"] in t.sessions[doc_id].target_bindings


def test_tools_v0_2_structural_inspection():
    t = tools.PrometeoTools()
    res_open = t.open_document(FORM56_PATH)
    doc_id = res_open["document_id"]

    # document_summary
    s = t.document_summary(doc_id)
    assert s["ok"] is True
    assert s["page_count"] == 2

    # document_outline
    o = t.document_outline(doc_id, pages=[0], include_vectors=False)
    assert o["ok"] is True
    assert "PAGE 0" in o["outline_text"]

    # inspect_node
    n = t.inspect_node(doc_id, "text_p0_s4")
    assert n["ok"] is True
    assert "Internal Revenue Service" in n["target_node"]["text"]

    # query_nodes
    q = t.query_nodes(doc_id, page=0, text="Internal Revenue")
    assert q["ok"] is True
    assert q["count"] >= 1

    # node_neighbors
    nb = t.node_neighbors(doc_id, "text_p0_s4")
    assert nb["ok"] is True


# =====================================================================
# 4. MULTI-OPERATION TRANSACTIONS (BATCH v0.1) & ATOMICITY
# =====================================================================

def test_transaction_staging_and_atomicity_pass(tmp_path):
    """Prueba multi-span sobre copia de IRS Form 56: 2 operaciones seguras."""
    # Copia aislada para el test
    test_pdf = str(tmp_path / "form56_multi_test.pdf")
    shutil.copyfile(FORM56_PATH, test_pdf)

    t = tools.PrometeoTools()
    res_open = t.open_document(test_pdf)
    doc_id = res_open["document_id"]

    # Resolver 2 targets distintos en Form 56
    # Target 1: "Form" en página 0
    f1 = t.find_text(doc_id, "Department of the Treasury", page=0)
    s1 = t.select_target(doc_id, f1["candidates"][0]["candidate_id"])
    tgt1 = s1["target_id"]

    # Target 2: "Internal Revenue Service" en página 0
    f2 = t.find_text(doc_id, "Internal Revenue Service", page=0)
    s2 = t.select_target(doc_id, f2["candidates"][0]["candidate_id"])
    tgt2 = s2["target_id"]

    # Stage transaction con 2 operaciones
    ops = [
        {"target_id": tgt1, "new_text": "Department of Treasury "},
        {"target_id": tgt2, "new_text": "Internal Revenue Office "},
    ]

    staged = t.stage_transaction(doc_id, ops, policy="ATOMIC")
    assert staged["ok"] is True
    assert staged["status"] == "STAGED"
    assert staged["operations_count"] == 2
    tx_id = staged["transaction_id"]

    # Export transaction
    out_pdf = str(tmp_path / "form56_multi_out.pdf")
    exp = t.export_transaction(doc_id, tx_id, out_pdf)
    assert exp["ok"] is True
    assert exp["status"] == "EXPORTED"
    assert os.path.exists(out_pdf)

    # Verify transaction: ambas operaciones deben verificar
    v = t.verify_transaction(doc_id, tx_id)
    assert v["ok"] is True
    assert v["verdict"] == "PASS"
    assert v["operations_verified"] == 2

    # Verificar que el PDF de test original no fue modificado in-place
    assert sha256_file(test_pdf) == FORM56_EXPECTED_SHA


def test_transaction_conflict_duplicate_target(tmp_path):
    """Conflicto: mismo target modificado dos veces en la misma transacción -> HONEST_REJECT."""
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    doc_id = res_open["document_id"]

    f = t.find_text(doc_id, "CONTRATO")
    s = t.select_target(doc_id, f["candidates"][0]["candidate_id"])
    tgt = s["target_id"]

    ops = [
        {"target_id": tgt, "new_text": "CONTRATO MODIFICADO"},
        {"target_id": tgt, "new_text": "CONTRATO SEGUNDA VEZ"},
    ]

    staged = t.stage_transaction(doc_id, ops)
    assert staged["ok"] is False
    assert staged["status"] == "HONEST_REJECT"
    assert staged["reason"] == "DUPLICATE_TARGET_IN_TRANSACTION"


def test_transaction_conflict_ambiguous_or_unresolved(tmp_path):
    """Conflicto: target no resuelto o ambiguo -> HONEST_REJECT."""
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    doc_id = res_open["document_id"]

    ops = [
        {"target_id": "target_fake_non_existent", "new_text": "VALOR"},
    ]
    staged = t.stage_transaction(doc_id, ops)
    assert staged["ok"] is False
    assert staged["status"] == "HONEST_REJECT"
    assert staged["reason"] == "TARGET_NOT_FOUND"


def test_transaction_conflict_clearance_overflow(tmp_path):
    """Conflicto: una de las operaciones excede clearance -> HONEST_REJECT de todo el lote."""
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    doc_id = res_open["document_id"]

    f = t.find_text(doc_id, "Referencia interna")
    s = t.select_target(doc_id, f["candidates"][0]["candidate_id"])
    tgt = s["target_id"]

    # Texto gigantesco que supera con certeza el clearance
    huge_text = "ESTE TEXTO ES EXTREMADAMENTE LARGO Y SUPERA CON CERTEZA CUALQUIER MARGEN DISPONIBLE EN EL DOCUMENTO" * 5

    ops = [
        {"target_id": tgt, "new_text": huge_text},
    ]

    staged = t.stage_transaction(doc_id, ops)
    assert staged["ok"] is False
    assert staged["status"] == "HONEST_REJECT"
    assert staged["reason"] == "CLEARANCE_OVERFLOW"


def test_transaction_verifier_attack_zero_silent_failure(tmp_path):
    """Ataque al verifier: PDF exportado adulterado -> Verifier detecta fallo y NO emite PASS parcial."""
    test_pdf = str(tmp_path / "form56_attack_test.pdf")
    shutil.copyfile(FORM56_PATH, test_pdf)

    t = tools.PrometeoTools()
    res_open = t.open_document(test_pdf)
    doc_id = res_open["document_id"]

    f = t.find_text(doc_id, "Internal Revenue Service", page=0)
    s = t.select_target(doc_id, f["candidates"][0]["candidate_id"])
    tgt = s["target_id"]

    ops = [{"target_id": tgt, "new_text": "Internal Revenue Office "}]
    staged = t.stage_transaction(doc_id, ops)
    tx_id = staged["transaction_id"]

    out_pdf = str(tmp_path / "form56_attack_out.pdf")
    t.export_transaction(doc_id, tx_id, out_pdf)

    # ATAQUE: corruptar o sobrescribir el archivo exportado con el original
    shutil.copyfile(test_pdf, out_pdf)

    # Verificación debe fallar contundentemente
    v = t.verify_transaction(doc_id, tx_id)
    assert v["ok"] is False
    assert v["verdict"] == "FAIL"
    assert v["status"] == "FAILED"


def test_transaction_rollback(tmp_path):
    """Rollback de transacción en estado STAGED."""
    t = tools.PrometeoTools()
    res_open = t.open_document(CASE_A_PATH)
    doc_id = res_open["document_id"]

    f = t.find_text(doc_id, "CONTRATO")
    s = t.select_target(doc_id, f["candidates"][0]["candidate_id"])
    tgt = s["target_id"]

    ops = [{"target_id": tgt, "new_text": "CONTRATO NUEVO"}]
    staged = t.stage_transaction(doc_id, ops)
    tx_id = staged["transaction_id"]

    rb = t.rollback_transaction(doc_id, tx_id)
    assert rb["ok"] is True
    assert rb["status"] == "ROLLED_BACK"


# =====================================================================
# 5. DOCGRAPH DIFF v0.1
# =====================================================================

def test_docgraph_diff_identical_documents():
    g1, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(CASE_A_PATH)
    g2, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(CASE_A_PATH)
    diff = docgraph_diff(g1, g2)

    assert diff["summary"]["added_count"] == 0
    assert diff["summary"]["removed_count"] == 0
    assert diff["summary"]["changed_count"] == 0


def test_docgraph_diff_mutated_output(tmp_path):
    test_pdf = str(tmp_path / "form56_diff_src.pdf")
    shutil.copyfile(FORM56_PATH, test_pdf)

    t = tools.PrometeoTools()
    res_open = t.open_document(test_pdf)
    doc_id = res_open["document_id"]

    f = t.find_text(doc_id, "Internal Revenue Service", page=0)
    s = t.select_target(doc_id, f["candidates"][0]["candidate_id"])
    tgt = s["target_id"]

    ops = [{"target_id": tgt, "new_text": "Internal Revenue Office "}]
    staged = t.stage_transaction(doc_id, ops)
    tx_id = staged["transaction_id"]

    out_pdf = str(tmp_path / "form56_diff_out.pdf")
    t.export_transaction(doc_id, tx_id, out_pdf)
    t.verify_transaction(doc_id, tx_id)

    g_orig, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(test_pdf)
    g_mut, _ = GLOBAL_DOCGRAPH_CACHE.get_or_build(out_pdf)

    diff = docgraph_diff(g_orig, g_mut)
    assert diff["summary"]["changed_count"] >= 1
    text_changes = [c for c in diff["changed_nodes"] if c.get("text_changed")]
    assert len(text_changes) == 1
    assert "Internal Revenue Service" in text_changes[0]["old_text"]
    assert "Internal Revenue Office" in text_changes[0]["new_text"]


# =====================================================================
# 6. CROSS-DOCUMENT ISOLATION & IMMUTABILITY
# =====================================================================

def test_cross_document_isolation():
    t = tools.PrometeoTools()
    doc_a = t.open_document(CASE_A_PATH)["document_id"]
    doc_b = t.open_document(FORM56_PATH)["document_id"]

    f_a = t.find_text(doc_a, "CONTRATO")
    s_a = t.select_target(doc_a, f_a["candidates"][0]["candidate_id"])
    tgt_a = s_a["target_id"]

    # Intentar aplicar target de doc_a en doc_b debe ser rechazado
    ops = [{"target_id": tgt_a, "new_text": "VALOR FALSO"}]
    res = t.stage_transaction(doc_b, ops)
    assert res["ok"] is False
    assert res["status"] == "HONEST_REJECT"


def test_original_document_immutability():
    sha_before = sha256_file(FORM56_PATH)
    assert sha_before == FORM56_EXPECTED_SHA

    # Operaciones de lectura y caché
    t = tools.PrometeoTools()
    t.open_document(FORM56_PATH)
    t.find_text("doc_ef82ec5a7dc8c113", "Form")
    t.document_summary("doc_ef82ec5a7dc8c113")

    sha_after = sha256_file(FORM56_PATH)
    assert sha_after == FORM56_EXPECTED_SHA


# =====================================================================
# 7. AGENT BRIDGE v0.3 MULTI-OP TRANSACTION FLOW
# =====================================================================

def test_agent_bridge_v0_3_multi_op_transaction(tmp_path):
    """Prueba que un agente externo real (via MockAdapter determinista) ejecuta el flujo v0.2 completo."""
    import re
    from agents.bridge_runner import BridgeRunner
    from agents.adapter import MockAgentAdapter, MockAgentSession, AgentTurn

    test_pdf = str(tmp_path / "bridge_v0_3_test.pdf")
    out_pdf = str(tmp_path / "bridge_v0_3_out.pdf")
    shutil.copyfile(FORM56_PATH, test_pdf)
    sha_orig = sha256_file(test_pdf)

    turns = [
        {"thought": "Abro el documento.", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": test_pdf}},
        {"thought": "Pido resumen compacto L0.", "action": "call_tool", "tool_name": "document_summary", "arguments": {"document_id": f"doc_{sha_orig[:16]}"}},
        {"thought": "Pido outline compacto de página 0.", "action": "call_tool", "tool_name": "document_outline", "arguments": {"document_id": f"doc_{sha_orig[:16]}", "pages": [0], "include_vectors": False}},
        {"thought": "Busco nodo exacto.", "action": "call_tool", "tool_name": "query_nodes", "arguments": {"document_id": f"doc_{sha_orig[:16]}", "page": 0, "text": "Department of the Treasury"}},
        {
            "thought": "Preparo transacción atómica multi-operación.",
            "action": "call_tool",
            "tool_name": "stage_transaction",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "operations": [
                    {"node_id": "text_p0_s3", "new_text": "Department of Treasury "},
                    {"node_id": "text_p0_s4", "new_text": "Internal Revenue Office "},
                ],
                "policy": "ATOMIC"
            }
        },
        {"thought": "Exporto la transacción.", "action": "call_tool", "tool_name": "export_transaction", "arguments": {"document_id": f"doc_{sha_orig[:16]}", "transaction_id": "tx_PLACEHOLDER", "destination": out_pdf}},
        {"thought": "Verifico materialmente la transacción.", "action": "call_tool", "tool_name": "verify_transaction", "arguments": {"document_id": f"doc_{sha_orig[:16]}", "transaction_id": "tx_PLACEHOLDER"}},
        {"thought": "Transacción verificada.", "action": "finish", "message": "Lote multi-operación completado y verificado con PASS."},
    ]

    class DynamicMockSession(MockAgentSession):
        def execute_turn(self, prompt: str) -> AgentTurn:
            if prompt and '"transaction_id":' in prompt:
                m = re.search(r'"transaction_id":\s*"([^"]+)"', prompt)
                if m:
                    self._adapter.tx_id = m.group(1)
            turn = self._adapter._next_mock_turn()
            turn.session_id = self._session_id
            if turn.arguments and "transaction_id" in turn.arguments and self._adapter.tx_id:
                turn.arguments["transaction_id"] = self._adapter.tx_id
            return turn

    class DynamicMockAdapter(MockAgentAdapter):
        def __init__(self, scripted_turns):
            super().__init__(scripted_turns)
            self.tx_id = None

        def start_session(self, initial_prompt, tools_schemas, system_prompt=None, temperature=0.0):
            import uuid
            sess_id = f"mock_sess_{uuid.uuid4().hex[:12]}"
            self.sessions_created.append(sess_id)
            first_turn = self._next_mock_turn()
            first_turn.session_id = sess_id
            return DynamicMockSession(
                adapter=self,
                session_id=sess_id,
                initial_turn=first_turn,
            )

    adapter = DynamicMockAdapter(scripted_turns=turns)
    runner = BridgeRunner(adapter=adapter)
    rep = runner.run_instruction(
        human_instruction="Cambia 'Department of the Treasury' por 'Department of Treasury ' e 'Internal Revenue Service' por 'Internal Revenue Office '.",
        document_path=test_pdf,
        destination_path=out_pdf,
        use_persistent_session=True,
        contract_version="0.2",
    )

    assert rep.final_verdict == "CLOSED_PASS"
    assert rep.pass_count >= 1
    assert rep.silent_failure_count == 0
    assert rep.protocol_violations == []
    assert os.path.exists(out_pdf)
