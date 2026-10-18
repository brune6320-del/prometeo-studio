"""PROMETEO · Tests for Tool Layer v0.1 (PROMETEO-TOOLS-0001)
────────────────────────────────────────────────────────────
Validates all requirements of FASE B, C, D, E and Gates G4–G13:
- Inmutabilidad estricta del original
- Vertical slice de las 7 herramientas mínimas
- Verificación material post-exportación (única fuente de PASS)
- Target ambiguo → AMBIGUOUS → sin mutación
- Restricción imposible → HONEST_REJECT
- SILENT_FAILURE == 0
- Desacoplamiento total de SDKs de LLM (MODEL ≠ PROMETEO)
- Provenance completa
"""

import ast
import hashlib
import json
import os
import shutil
import sys
import pytest
import pymupdf

# Import tools module
try:
    from tools import PrometeoTools, ResultState, OperationProvenance
except ImportError:
    from fase0.tools import PrometeoTools, ResultState, OperationProvenance


HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
CASE_A = os.path.join(ASSETS, "case_a.pdf")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────
# FASE E & G12: Agent-Agnostic / Sin dependencias de proveedores LLM
# ─────────────────────────────────────────────────────────────────
def test_g12_agent_agnostic_no_llm_sdk_imports():
    """G12: La Tool Layer NO debe importar SDKs de OpenAI, Anthropic, Google ni otros LLMs."""
    tools_file = os.path.join(HERE, "tools.py")
    with open(tools_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="tools.py")

    forbidden_modules = {
        "openai",
        "anthropic",
        "google.generativeai",
        "google.ai",
        "langchain",
        "llama_index",
        "litellm",
        "cohere",
        "transformers",
        "torch",
    }

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module.split(".")[0])

    overlap = forbidden_modules.intersection(imported_names)
    assert not overlap, f"La Tool Layer importa librerías de LLM prohibidas: {overlap}"


def test_tool_schemas_and_generic_dispatch():
    """Valida los schemas de herramientas y el despacho genérico execute_tool."""
    schemas = PrometeoTools.get_tool_schemas()
    assert len(schemas) == 7
    schema_names = [s["name"] for s in schemas]
    assert schema_names == [
        "open_document",
        "inspect_document",
        "find_text",
        "select_target",
        "replace_text",
        "export_document",
        "verify_operation",
    ]

    tools = PrometeoTools()
    # Despacho desconocido
    unknown_res = tools.execute_tool("herramienta_fantasma", {})
    assert unknown_res["ok"] is False
    assert unknown_res["result_state"] == ResultState.HONEST_REJECT.value


# ─────────────────────────────────────────────────────────────────
# FASE C & G6: Las 7 operaciones mínimas funcionan
# ─────────────────────────────────────────────────────────────────
def test_g6_seven_operations_interface():
    """G6: Las siete operaciones mínimas están implementadas y responden adecuadamente."""
    tools = PrometeoTools()
    for method_name in [
        "open_document",
        "inspect_document",
        "find_text",
        "select_target",
        "replace_text",
        "export_document",
        "verify_operation",
    ]:
        assert hasattr(tools, method_name), f"Falta el método {method_name} en PrometeoTools"


# ─────────────────────────────────────────────────────────────────
# FASE D, G4, G7, G8, G10: Vertical Slice Real End-to-End
# ─────────────────────────────────────────────────────────────────
def test_vertical_slice_end_to_end_pass(tmp_path):
    """G4, G7, G8, G10: Flujo completo original → open → inspect → find → select → replace → export → verify → PASS."""
    # Preparar copia de trabajo aislada del original
    test_pdf = str(tmp_path / "original_fixture.pdf")
    shutil.copy(CASE_A, test_pdf)
    initial_hash = _sha256(test_pdf)
    initial_bytes = open(test_pdf, "rb").read()

    tools = PrometeoTools()

    # 1. open_document
    open_res = tools.open_document(test_pdf)
    assert open_res["ok"] is True
    assert open_res["result_state"] == ResultState.OPENED.value
    doc_id = open_res["document_id"]
    assert open_res["source_sha256"] == initial_hash

    # 2. inspect_document
    insp_res = tools.inspect_document(doc_id)
    assert insp_res["ok"] is True
    assert insp_res["pages_count"] >= 1
    assert "Helvetica" in str(insp_res["fonts_present"]) or "helv" in str(insp_res["fonts_present"])

    # 3. find_text
    find_res = tools.find_text(doc_id, "Juan Perez")
    assert find_res["ok"] is True
    assert find_res["status"] == "UNIQUE"
    assert find_res["count"] == 1
    cand_id = find_res["candidate_id"]

    # 4. select_target
    sel_res = tools.select_target(doc_id, cand_id)
    assert sel_res["ok"] is True
    assert sel_res["status"] == "RESOLVED"
    target_id = sel_res["target_id"]
    assert "Juan Perez" in sel_res["current_text"]

    # 5. replace_text
    rep_res = tools.replace_text(doc_id, target_id, "Carlos Gomez")
    assert rep_res["ok"] is True
    assert rep_res["status"] == "STAGED"
    assert rep_res["result_state"] == ResultState.STAGED.value
    # Regla fundamental: replace_text NUNCA da PASS
    assert rep_res["result_state"] != ResultState.PASS.value
    op_id = rep_res["operation_id"]

    # 6. export_document
    out_pdf = str(tmp_path / "exported_modified.pdf")
    exp_res = tools.export_document(doc_id, out_pdf)
    assert exp_res["ok"] is True
    assert exp_res["status"] == "EXPORTED"
    assert exp_res["result_state"] == ResultState.EXPORTED.value
    assert os.path.exists(out_pdf)

    # Invariante G4: El original en disco no sufrió ninguna modificación byte a byte
    post_export_src_hash = _sha256(test_pdf)
    post_export_src_bytes = open(test_pdf, "rb").read()
    assert post_export_src_hash == initial_hash, "G4 violado: el archivo original cambió de hash!"
    assert post_export_src_bytes == initial_bytes, "G4 violado: los bytes del original cambiaron!"

    # El archivo de salida existe y su hash es distinto
    out_hash = _sha256(out_pdf)
    assert out_hash != initial_hash, "La salida modificada debe tener hash diferente al original."

    # 7. verify_operation (G8: ocurre post-exportación reabriendo fresco)
    ver_res = tools.verify_operation(op_id)
    assert ver_res["ok"] is True
    assert ver_res["result_state"] == ResultState.PASS.value
    assert ver_res["verifier_result"]["ok"] is True

    # Comprobar criterios materiales
    check = ver_res["verifier_result"]["checks"][0]
    assert check["ok"] is True
    assert check["dx_pt"] <= 1.5
    assert check["dy_pt"] <= 1.5
    assert check["font_identity_ok"] is True

    # Comprobar provenance completa
    prov = ver_res["provenance"]
    assert prov["operation_id"] == op_id
    assert prov["document_id"] == doc_id
    assert prov["source_document_hash"] == initial_hash
    assert prov["page"] == 0
    assert prov["target"] == target_id
    assert prov["requested_action"] == "replace_text"
    assert prov["requested_value"] == "Carlos Gomez"
    assert prov["engine_version"] == "prometeo_v0.1_tools"
    assert prov["result_state"] == ResultState.PASS.value
    assert prov["output_hash"] == out_hash
    assert prov["verifier_result"] is not None

    # Relectura directa con PyMuPDF del PDF exportado
    doc_out = pymupdf.open(out_pdf)
    text_out = doc_out[0].get_text()
    doc_out.close()
    assert "Carlos Gomez" in text_out
    assert "Juan Perez" not in text_out


# ─────────────────────────────────────────────────────────────────
# FASE D & G9: Target ambiguo → AMBIGUOUS → NO mutación automática
# ─────────────────────────────────────────────────────────────────
def test_negative_case_ambiguous_target_no_mutation(tmp_path):
    """G9: Si el texto es ambiguo y el target no se resuelve inequívocamente,
    emite AMBIGUOUS y NO muta."""
    test_pdf = str(tmp_path / "case_a_ambig.pdf")
    shutil.copy(CASE_A, test_pdf)
    initial_hash = _sha256(test_pdf)

    tools = PrometeoTools()
    open_res = tools.open_document(test_pdf)
    doc_id = open_res["document_id"]

    # "de" aparece múltiples veces en case_a.pdf
    find_res = tools.find_text(doc_id, "de")
    assert find_res["ok"] is True
    assert find_res["status"] == "AMBIGUOUS"
    assert find_res["result_state"] == ResultState.AMBIGUOUS.value
    assert find_res["count"] > 1

    # Intentar reemplazar directamente sin seleccionar target
    rep_res = tools.replace_text(doc_id, "target_inexistente_o_ambiguo", "valor_nuevo")
    assert rep_res["ok"] is False
    assert rep_res["status"] == "AMBIGUOUS"
    assert rep_res["result_state"] == ResultState.AMBIGUOUS.value
    assert rep_res["mutated"] is False
    assert rep_res["operation_id"] is None

    # Intentar exportar: no debe haber operaciones preparadas
    out_pdf = str(tmp_path / "out_should_not_exist.pdf")
    exp_res = tools.export_document(doc_id, out_pdf)
    assert exp_res["ok"] is False
    assert exp_res["result_state"] == ResultState.HONEST_REJECT.value
    assert not os.path.exists(out_pdf)

    # Invariante: Original completamente inmutable
    assert _sha256(test_pdf) == initial_hash


# ─────────────────────────────────────────────────────────────────
# FASE D & G10: Restricción imposible → HONEST_REJECT
# ─────────────────────────────────────────────────────────────────
def test_impossible_case_honest_reject_overflow(tmp_path):
    """G10: Si la restricción geométrica es imposible bajo la política,
    rechaza honestamente (HONEST_REJECT) y NO muta."""
    test_pdf = str(tmp_path / "case_a_overflow.pdf")
    shutil.copy(CASE_A, test_pdf)
    initial_hash = _sha256(test_pdf)

    tools = PrometeoTools()
    open_res = tools.open_document(test_pdf)
    doc_id = open_res["document_id"]

    find_res = tools.find_text(doc_id, "Juan Perez")
    cand_id = find_res["candidate_id"]
    sel_res = tools.select_target(doc_id, cand_id)
    target_id = sel_res["target_id"]

    # Intentar meter un texto ridículamente largo con policy=['reject']
    impossible_text = (
        "Nombre Extraordinariamente Excesivo Que Jamas Podria Entrar "
        "En Este Renglon Sin Destruir La Geometria Del Documento Entero"
    )
    rep_res = tools.replace_text(
        doc_id,
        target_id,
        impossible_text,
        policy_preference=["reject"],
    )

    assert rep_res["ok"] is False
    assert rep_res["status"] == "HONEST_REJECT"
    assert rep_res["result_state"] == ResultState.HONEST_REJECT.value
    assert rep_res["mutated"] is False

    # Original no se toca
    assert _sha256(test_pdf) == initial_hash


# ─────────────────────────────────────────────────────────────────
# FASE B & G4: Inmutabilidad in-place garantizada
# ─────────────────────────────────────────────────────────────────
def test_g4_inplace_modification_forbidden(tmp_path):
    """G4: Exportar sobre la ruta original está estrictamente prohibido."""
    test_pdf = str(tmp_path / "test_inplace.pdf")
    shutil.copy(CASE_A, test_pdf)
    initial_hash = _sha256(test_pdf)

    tools = PrometeoTools()
    open_res = tools.open_document(test_pdf)
    doc_id = open_res["document_id"]

    find_res = tools.find_text(doc_id, "Juan Perez")
    sel_res = tools.select_target(doc_id, find_res["candidate_id"])
    tools.replace_text(doc_id, sel_res["target_id"], "Ana Perez")

    # Intentar exportar sobre el mismo archivo fuente
    exp_res = tools.export_document(doc_id, test_pdf)
    assert exp_res["ok"] is False
    assert exp_res["result_state"] == ResultState.HONEST_REJECT.value
    assert "in-place" in exp_res["error"]

    # El original conserva su hash intacto
    assert _sha256(test_pdf) == initial_hash


# ─────────────────────────────────────────────────────────────────
# FASE B & G8: Ninguna afirmación de éxito anterior al Verifier
# ─────────────────────────────────────────────────────────────────
def test_g8_no_premature_success_declaration(tmp_path):
    """G8: verify_operation no puede emitir PASS si el archivo no fue exportado."""
    test_pdf = str(tmp_path / "case_a_premature.pdf")
    shutil.copy(CASE_A, test_pdf)

    tools = PrometeoTools()
    open_res = tools.open_document(test_pdf)
    doc_id = open_res["document_id"]

    find_res = tools.find_text(doc_id, "Juan Perez")
    sel_res = tools.select_target(doc_id, find_res["candidate_id"])
    rep_res = tools.replace_text(doc_id, sel_res["target_id"], "Ana Gomez")
    op_id = rep_res["operation_id"]

    # Intentar verificar ANTES de exportar
    ver_res = tools.verify_operation(op_id)
    assert ver_res["ok"] is False
    assert ver_res["result_state"] != ResultState.PASS.value


# ─────────────────────────────────────────────────────────────────
# FASE B & G11: SILENT_FAILURE == 0 Invariant
# ─────────────────────────────────────────────────────────────────
def test_g11_silent_failure_invariant_zero(tmp_path):
    """G11: Si la salida se corrompe materialmente, el Verifier rechaza y NO emite PASS."""
    test_pdf = str(tmp_path / "case_a_silent.pdf")
    shutil.copy(CASE_A, test_pdf)

    tools = PrometeoTools()
    open_res = tools.open_document(test_pdf)
    doc_id = open_res["document_id"]

    find_res = tools.find_text(doc_id, "Juan Perez")
    sel_res = tools.select_target(doc_id, find_res["candidate_id"])
    rep_res = tools.replace_text(doc_id, sel_res["target_id"], "Carlos Gomez")
    op_id = rep_res["operation_id"]

    out_pdf = str(tmp_path / "exported_tampered.pdf")
    tools.export_document(doc_id, out_pdf)

    # Simular una alteración externa en el documento exportado antes del verifier
    # (por ejemplo, reemplazar el archivo exportado con uno vacío o dañado)
    with open(out_pdf, "wb") as f:
        f.write(b"%PDF-1.4 corrupt content")

    ver_res = tools.verify_operation(op_id)
    assert ver_res["ok"] is False
    assert ver_res["result_state"] != ResultState.PASS.value
    # SILENT_FAILURE es prevenido y capturado como rechazo o crash, nunca PASS
    assert ver_res["result_state"] in (ResultState.HONEST_REJECT.value, ResultState.CRASH.value)


# ─────────────────────────────────────────────────────────────────
# FASE E: Despacho agnóstico completo vía execute_tool (Simulación LLM)
# ─────────────────────────────────────────────────────────────────
def test_agent_agnostic_execute_tool_full_flow(tmp_path):
    """Prueba que un agente puede ejecutar el vertical slice completo usando
    únicamente el despacho execute_tool(nombre, dict_argumentos)."""
    test_pdf = str(tmp_path / "case_a_agent.pdf")
    shutil.copy(CASE_A, test_pdf)
    tools = PrometeoTools()

    # 1. open_document
    r1 = tools.execute_tool("open_document", {"path": test_pdf})
    assert r1["ok"] is True
    doc_id = r1["document_id"]

    # 2. inspect_document
    r2 = tools.execute_tool("inspect_document", {"document_id": doc_id})
    assert r2["ok"] is True

    # 3. find_text
    r3 = tools.execute_tool("find_text", {"document_id": doc_id, "query": "Juan Perez"})
    assert r3["ok"] is True
    cand_id = r3["candidate_id"]

    # 4. select_target
    r4 = tools.execute_tool("select_target", {"document_id": doc_id, "candidate_id": cand_id})
    assert r4["ok"] is True
    target_id = r4["target_id"]

    # 5. replace_text
    r5 = tools.execute_tool("replace_text", {
        "document_id": doc_id,
        "target_id": target_id,
        "new_value": "Beatriz Viterbo"
    })
    assert r5["ok"] is True
    assert r5["result_state"] == ResultState.STAGED.value
    op_id = r5["operation_id"]

    # 6. export_document
    out_pdf = str(tmp_path / "out_agent.pdf")
    r6 = tools.execute_tool("export_document", {
        "document_id": doc_id,
        "destination": out_pdf
    })
    assert r6["ok"] is True
    assert r6["result_state"] == ResultState.EXPORTED.value

    # 7. verify_operation
    r7 = tools.execute_tool("verify_operation", {"operation_id": op_id})
    assert r7["ok"] is True
    assert r7["result_state"] == ResultState.PASS.value
    assert r7["verifier_result"]["ok"] is True


def test_disambiguation_flow_select_candidate(tmp_path):
    """Verifica que una consulta ambigua puede ser desambiguada seleccionando
    explícitamente uno de los candidatos."""
    test_pdf = str(tmp_path / "case_a_disambig.pdf")
    shutil.copy(CASE_A, test_pdf)
    tools = PrometeoTools()

    r1 = tools.open_document(test_pdf)
    doc_id = r1["document_id"]

    # "de" tiene múltiples ocurrencias
    r_find = tools.find_text(doc_id, "de")
    assert r_find["result_state"] == ResultState.AMBIGUOUS.value
    assert len(r_find["candidates"]) > 1

    # Desambiguar: elegir el segundo candidato
    chosen_cand = r_find["candidates"][1]
    r_sel = tools.select_target(doc_id, chosen_cand["candidate_id"])
    assert r_sel["ok"] is True
    assert r_sel["status"] == "RESOLVED"
    target_id = r_sel["target_id"]

    # Reemplazar texto en ese target específico
    r_rep = tools.replace_text(doc_id, target_id, "CONTRATO ESPECIAL")
    assert r_rep["ok"] is True
    assert r_rep["result_state"] == ResultState.STAGED.value

