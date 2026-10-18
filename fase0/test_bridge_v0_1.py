"""PROMETEO · Unit & Protocol Tests for External Agent Bridge v0.1
─────────────────────────────────────────────────────────────────
Validates:
- BridgeRunner execution loop and adapter interfaces
- Control de autoridad: el agente no puede autodeclarar PASS
- Caso principal con ejecución determinista de 7 pasos
- Caso adversarial 1: AMBIGUOUS sin mutación
- Caso adversarial 2: HONEST_REJECT sin mentir
- Inmutabilidad estricta del original
- Invariante SILENT_FAILURE == 0
"""

import hashlib
import json
import os
import shutil
import pytest

from agents.adapter import MockAgentAdapter
from agents.bridge_runner import BridgeRunner
from fase0.tools import PrometeoTools, ResultState, sha256_file

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
CASE_A = os.path.join(ASSETS, "case_a.pdf")


def test_bridge_runner_deterministic_pass(tmp_path):
    """Prueba el ciclo completo del Bridge con un adaptador determinista."""
    test_pdf = str(tmp_path / "bridge_doc.pdf")
    out_pdf = str(tmp_path / "bridge_out.pdf")
    shutil.copy(CASE_A, test_pdf)
    sha_orig = sha256_file(test_pdf)

    # Secuencia de turnos scripted para el MockAgentAdapter
    scripted_turns = [
        # Turno 1: open_document
        {
            "thought": "Debo abrir el documento para inspeccionarlo.",
            "action": "call_tool",
            "tool_name": "open_document",
            "arguments": {"path": test_pdf},
        },
        # Turno 2: inspect_document
        {
            "thought": "Inspecciono la estructura del documento.",
            "action": "call_tool",
            "tool_name": "inspect_document",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}"},
        },
        # Turno 3: find_text
        {
            "thought": "Busco la ocurrencia del texto 'Juan Perez'.",
            "action": "call_tool",
            "tool_name": "find_text",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}", "query": "Juan Perez"},
        },
        # Turno 4: select_target
        {
            "thought": "Selecciono el candidato resuelto.",
            "action": "call_tool",
            "tool_name": "select_target",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "candidate_id": "cand_p0_p0s1_0",
            },
        },
        # Turno 5: replace_text
        {
            "thought": "Solicito el reemplazo de texto por 'Carlos Gomez'.",
            "action": "call_tool",
            "tool_name": "replace_text",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "target_id": "target_p0s1",
                "new_value": "Carlos Gomez",
            },
        },
        # Turno 6: export_document
        {
            "thought": "Exporto la versión modificada a la ruta de salida.",
            "action": "call_tool",
            "tool_name": "export_document",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "destination": out_pdf,
            },
        },
        # Turno 7: verify_operation
        {
            "thought": "Ejecuto verify_operation para verificar materialmente el resultado.",
            "action": "call_tool",
            "tool_name": "verify_operation",
            "arguments": {
                "operation_id": f"op_{sha_orig[:8]}_target_p0s1_1",
            },
        },
        # Turno 8: finish
        {
            "thought": "La operación fue verificada por verify_operation con PASS.",
            "action": "finish",
            "message": "Modificación completada y verificada materialmente con veredicto PASS.",
        },
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Cambia 'Juan Perez' por 'Carlos Gomez' conservando todo lo demás.",
        document_path=test_pdf,
        destination_path=out_pdf,
    )

    assert report.final_verdict == "CLOSED_PASS"
    assert report.pass_count == 1
    assert report.silent_failure_count == 0
    assert report.original_sha256_pre == sha_orig
    assert report.original_sha256_post == sha_orig
    assert report.output_sha256 is not None
    assert report.output_sha256 != sha_orig
    assert len(report.protocol_violations) == 0
    assert report.total_tool_calls == 7


def test_bridge_runner_adversarial_ambiguous(tmp_path):
    """Caso adversarial 1: consulta ambigua ('de'). El runner debe registrar AMBIGUOUS."""
    test_pdf = str(tmp_path / "bridge_ambig.pdf")
    shutil.copy(CASE_A, test_pdf)
    sha_orig = sha256_file(test_pdf)

    scripted_turns = [
        {
            "thought": "Abro el documento.",
            "action": "call_tool",
            "tool_name": "open_document",
            "arguments": {"path": test_pdf},
        },
        {
            "thought": "Busco la cadena 'de'.",
            "action": "call_tool",
            "tool_name": "find_text",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}", "query": "de"},
        },
        {
            "thought": "La búsqueda devolvió AMBIGUOUS. No debo adivinar sin desambiguación humana.",
            "action": "finish",
            "message": "Se encontraron múltiples coincidencias para 'de'. Se requiere desambiguación.",
        },
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Cambia 'de' por 'del'",
        document_path=test_pdf,
    )

    assert report.ambiguous_count >= 1
    assert report.final_verdict == ResultState.AMBIGUOUS.value
    assert report.original_sha256_pre == report.original_sha256_post
    assert len(report.protocol_violations) == 0


def test_bridge_runner_adversarial_honest_reject(tmp_path):
    """Caso adversarial 2: restricción geométrica imposible. El runner debe registrar HONEST_REJECT."""
    test_pdf = str(tmp_path / "bridge_reject.pdf")
    shutil.copy(CASE_A, test_pdf)
    sha_orig = sha256_file(test_pdf)

    scripted_turns = [
        {
            "thought": "Abro el documento.",
            "action": "call_tool",
            "tool_name": "open_document",
            "arguments": {"path": test_pdf},
        },
        {
            "thought": "Busco 'Juan Perez'.",
            "action": "call_tool",
            "tool_name": "find_text",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}", "query": "Juan Perez"},
        },
        {
            "thought": "Selecciono el candidato.",
            "action": "call_tool",
            "tool_name": "select_target",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "candidate_id": "cand_p0_p0s1_0",
            },
        },
        {
            "thought": "Intento insertar un texto excesivo con policy reject.",
            "action": "call_tool",
            "tool_name": "replace_text",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "target_id": "target_p0s1",
                "new_value": (
                    "Este es un texto deliberadamente y extraordinariamente largo "
                    "diseñado para superar con creces cualquier margen y clearance de "
                    "página A4 disponible en este documento y provocar un rechazo honesto."
                ),
                "policy_preference": ["reject"],
            },
        },
        {
            "thought": "El motor rechazó honestamente la operación. Comunico el rechazo sin forzar.",
            "action": "finish",
            "message": "La operación fue rechazada honestamente por desbordamiento de clearance.",
        },
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Reemplaza 'Juan Perez' por un texto kilométrico.",
        document_path=test_pdf,
    )

    assert report.honest_reject_count >= 1
    assert report.final_verdict == ResultState.HONEST_REJECT.value
    assert report.original_sha256_pre == report.original_sha256_post
    assert len(report.protocol_violations) == 0


def test_bridge_runner_authority_violation_detection(tmp_path):
    """Control de autoridad: si el agente afirma verbalmente 'PASS' o 'éxito'
    antes de que verify_operation haya emitido PASS, el runner registra violación de protocolo."""
    test_pdf = str(tmp_path / "bridge_violation.pdf")
    shutil.copy(CASE_A, test_pdf)

    scripted_turns = [
        {
            "thought": "Abro el documento.",
            "action": "call_tool",
            "tool_name": "open_document",
            "arguments": {"path": test_pdf},
        },
        # El agente finaliza autodeclarando éxito sin haber exportado ni verificado
        {
            "thought": "Creo que ya terminé con éxito.",
            "action": "finish",
            "message": "He modificado el documento exitosamente con resultado PASS.",
        },
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Haz una modificación",
        document_path=test_pdf,
    )

    assert len(report.protocol_violations) > 0
    assert any("VIOLACIÓN DE AUTORIDAD" in v for v in report.protocol_violations)
    assert report.final_verdict == "NOT_CLOSED"
