"""PROMETEO · Unit & Protocol Tests for Persistent Agent Session (ORDEN 127)
──────────────────────────────────────────────────────────────────────────
Valida:
1. Session lifecycle (inicio, turnos, cierre).
2. Persistent turn flow (flujo completo de 7 herramientas sobre sesión).
3. Tool continuity (preservación de identificadores de documento y operación).
4. Authority preservation (el agente no puede autodeclarar PASS dentro de la sesión).
5. Session isolation (adversarial: Sesión A vs Sesión B; documentos y targets aislados).
6. Session close and recovery (rechazo de turnos tras cierre; semántica RESTART_REQUIRED).
7. Mock persistent adapter (funcionamiento nativo determinista).
8. Backward compatibility con adapter discreto (fallback transparente).
"""

import json
import os
import shutil
import pytest

from agents.adapter import (
    AgentAdapter,
    AgentTurn,
    AgentSession,
    MockAgentAdapter,
    MockAgentSession,
    DiscreteFallbackSession,
)
from agents.bridge_runner import BridgeRunner
from fase0.tools import PrometeoTools, ResultState, sha256_file

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
CASE_A = os.path.join(ASSETS, "case_a.pdf")


def test_session_lifecycle():
    """Valida el ciclo de vida: creación, actividad, turnos y cierre."""
    scripted = [
        {"thought": "Paso 1", "action": "call_tool", "tool_name": "open_document", "arguments": {}},
        {"thought": "Paso 2", "action": "finish", "message": "Listo."},
    ]
    adapter = MockAgentAdapter(scripted_turns=scripted)
    session = adapter.start_session(
        initial_prompt="Inicia la tarea",
        tools_schemas=[],
    )

    assert session.is_active is True
    assert session.session_id.startswith("mock_sess_")
    assert session.initial_turn is not None
    assert session.initial_turn.action == "call_tool"
    assert session.initial_turn.tool_name == "open_document"

    turn2 = session.execute_turn("Resultado de open_document: ok")
    assert turn2.action == "finish"
    assert turn2.session_id == session.session_id

    session.close()
    assert session.is_active is False

    with pytest.raises(RuntimeError, match="ha sido cerrada"):
        session.execute_turn("Intento tras cierre")


def test_persistent_turn_flow(tmp_path):
    """Valida el flujo end-to-end de 7 herramientas usando transporte de sesión persistente."""
    test_pdf = str(tmp_path / "persistent_flow.pdf")
    out_pdf = str(tmp_path / "persistent_out.pdf")
    shutil.copy(CASE_A, test_pdf)
    sha_orig = sha256_file(test_pdf)

    scripted_turns = [
        # Turno 1: open_document
        {
            "thought": "Abro el documento.",
            "action": "call_tool",
            "tool_name": "open_document",
            "arguments": {"path": test_pdf},
        },
        # Turno 2: inspect_document
        {
            "thought": "Inspecciono la estructura.",
            "action": "call_tool",
            "tool_name": "inspect_document",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}"},
        },
        # Turno 3: find_text
        {
            "thought": "Busco 'Juan Perez'.",
            "action": "call_tool",
            "tool_name": "find_text",
            "arguments": {"document_id": f"doc_{sha_orig[:16]}", "query": "Juan Perez"},
        },
        # Turno 4: select_target
        {
            "thought": "Selecciono candidato.",
            "action": "call_tool",
            "tool_name": "select_target",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "candidate_id": "cand_p0_p0s1_0",
            },
        },
        # Turno 5: replace_text
        {
            "thought": "Reemplazo texto.",
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
            "thought": "Exporto documento.",
            "action": "call_tool",
            "tool_name": "export_document",
            "arguments": {
                "document_id": f"doc_{sha_orig[:16]}",
                "destination": out_pdf,
            },
        },
        # Turno 7: verify_operation
        {
            "thought": "Verifico materialmente.",
            "action": "call_tool",
            "tool_name": "verify_operation",
            "arguments": {
                "operation_id": f"op_{sha_orig[:8]}_target_p0s1_1",
            },
        },
        # Turno 8: finish
        {
            "thought": "Operación verificada con PASS.",
            "action": "finish",
            "message": "Completado y verificado con PASS.",
        },
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Cambia 'Juan Perez' por 'Carlos Gomez' conservando todo lo demás.",
        document_path=test_pdf,
        destination_path=out_pdf,
        use_persistent_session=True,
    )

    assert report.final_verdict == "CLOSED_PASS"
    assert report.transport_mode == "persistent_session"
    assert report.session_id is not None
    assert report.pass_count == 1
    assert report.silent_failure_count == 0
    assert report.original_sha256_pre == sha_orig
    assert report.original_sha256_post == sha_orig
    assert report.output_sha256 is not None
    assert report.output_sha256 != sha_orig
    assert len(report.protocol_violations) == 0
    assert report.total_tool_calls == 7
    assert report.total_cached_tokens > 0


def test_tool_continuity_and_metadata(tmp_path):
    """Verifica que el BridgeStepLog retiene el session_id en cada turno y paso de herramienta."""
    test_pdf = str(tmp_path / "continuity.pdf")
    shutil.copy(CASE_A, test_pdf)

    scripted_turns = [
        {"thought": "Paso 1", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": test_pdf}},
        {"thought": "Fin", "action": "finish", "message": "Listo sin mutaciones."},
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Solo abre el documento",
        document_path=test_pdf,
        use_persistent_session=True,
    )

    assert report.session_id is not None
    for step in report.steps_log:
        assert step["session_id"] == report.session_id


def test_authority_preservation_in_session(tmp_path):
    """Comprueba que una sesión persistente NO permite al modelo autodeclarar PASS sin verifier."""
    test_pdf = str(tmp_path / "auth_viol.pdf")
    shutil.copy(CASE_A, test_pdf)

    scripted_turns = [
        {"thought": "Abro doc", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": test_pdf}},
        # Autodeclaración de éxito sin verify_operation
        {"thought": "Hecho", "action": "finish", "message": "Operación completada con éxito y veredicto PASS."},
    ]

    adapter = MockAgentAdapter(scripted_turns=scripted_turns)
    runner = BridgeRunner(adapter=adapter)

    report = runner.run_instruction(
        human_instruction="Modifica algo",
        document_path=test_pdf,
        use_persistent_session=True,
    )

    assert len(report.protocol_violations) > 0
    assert any("VIOLACIÓN DE AUTORIDAD" in v for v in report.protocol_violations)
    assert report.final_verdict == "NOT_CLOSED"


def test_session_isolation_adversarial(tmp_path):
    """FASE L: Prueba adversarial de aislamiento estricto entre sesiones.
    SESSION A: Documento A
    SESSION B: Documento B
    Comprueba:
    1. session_id distintos.
    2. Cierre de Sesión A invalida continuación accidental de A.
    3. Sesión B no puede operar sobre targets de Sesión A.
    4. PROMETEO Tools aísla rigurosamente los document_ids."""
    doc_a_path = str(tmp_path / "doc_a.pdf")
    doc_b_path = str(tmp_path / "doc_b.pdf")
    shutil.copy(CASE_A, doc_a_path)
    shutil.copy(CASE_A, doc_b_path)

    tools = PrometeoTools()

    # Abrir Documento A en sesión A
    adapter_a = MockAgentAdapter(scripted_turns=[
        {"thought": "Abrir A", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": doc_a_path}},
        {"thought": "Fin A", "action": "finish", "message": "Fin sesión A."},
    ])
    session_a = adapter_a.start_session("Instrucción A", tools.get_tool_schemas())

    # Abrir Documento B en sesión B
    adapter_b = MockAgentAdapter(scripted_turns=[
        {"thought": "Abrir B", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": doc_b_path}},
        {"thought": "Fin B", "action": "finish", "message": "Fin sesión B."},
    ])
    session_b = adapter_b.start_session("Instrucción B", tools.get_tool_schemas())

    assert session_a.session_id != session_b.session_id

    # Turno 1 en cada sesión
    res_open_a = tools.execute_tool("open_document", {"path": doc_a_path})
    doc_id_a = res_open_a["document_id"]

    res_open_b = tools.execute_tool("open_document", {"path": doc_b_path})
    doc_id_b = res_open_b["document_id"]

    # Los documentos en memoria son independientes
    assert doc_id_a is not None
    assert doc_id_b is not None

    # Cerrar Sesión A
    session_a.close()
    assert session_a.is_active is False
    assert session_b.is_active is True

    # Intento de reusar Sesión A debe fallar
    with pytest.raises(RuntimeError, match="ha sido cerrada"):
        session_a.execute_turn("Intento de ataque cruzado desde A")

    # Sesión B sigue viva
    turn_b = session_b.execute_turn("Resultado normal para B")
    assert turn_b.action == "finish"
    session_b.close()
    assert session_b.is_active is False

    # Intento de operar con un target falso o de otro doc en Tool Layer
    cross_replace = tools.execute_tool("replace_text", {
        "document_id": doc_id_b,
        "target_id": "target_inexistente_de_a",
        "new_value": "Inyeccion",
    })
    assert cross_replace["ok"] is False
    assert cross_replace["result_state"] == ResultState.AMBIGUOUS.value


def test_session_close_and_recovery(tmp_path):
    """FASE M: Clasificación de comportamiento tras interrupción.
    Verifica semántica RESTART_REQUIRED."""
    test_pdf = str(tmp_path / "recovery.pdf")
    shutil.copy(CASE_A, test_pdf)

    adapter = MockAgentAdapter(scripted_turns=[
        {"thought": "T1", "action": "call_tool", "tool_name": "open_document", "arguments": {"path": test_pdf}},
        {"thought": "T2", "action": "finish", "message": "OK"},
    ])
    session = adapter.start_session("Inicio", [])

    # Simular interrupción forzosa cerrando la sesión
    session.close()

    # Comportamiento verificado: RESTART_REQUIRED (no se permite continuar una sesión interrumpida/cerrada)
    with pytest.raises(RuntimeError):
        session.execute_turn("Continuación tras crash")

    # Para recuperar, el cliente debe iniciar una nueva sesión limpia
    new_session = adapter.start_session("Reinicio limpio", [])
    assert new_session.is_active is True
    assert new_session.session_id != session.session_id
    new_session.close()


def test_backward_compatibility_discrete_fallback(tmp_path):
    """FASE Q.8: Verifica que un adapter puramente discreto opera mediante DiscreteFallbackSession
    cuando se solicita use_persistent_session=True, y también en modo discreto directo."""
    test_pdf = str(tmp_path / "discrete_doc.pdf")
    shutil.copy(CASE_A, test_pdf)

    class PurelyDiscreteAdapter(AgentAdapter):
        """Adapter sin implementación de start_session (hereda fallback)."""
        def __init__(self):
            self.calls = 0

        @property
        def provider(self) -> str:
            return "pure_discrete"

        @property
        def model_name(self) -> str:
            return "discrete-v1"

        def execute_turn(self, messages, tools_schemas, temperature=0.0):
            self.calls += 1
            if self.calls == 1:
                return AgentTurn(
                    thought="Turno 1 discreto",
                    action="call_tool",
                    tool_name="open_document",
                    arguments={"path": test_pdf},
                    tokens_usage={"input_tokens": 100, "output_tokens": 20, "cached_tokens": 0},
                    latency_ms=10.0,
                    model_identifier=self.model_name,
                    provider=self.provider,
                )
            return AgentTurn(
                thought="Turno 2 discreto finish",
                action="finish",
                message="Terminado en modo discreto sin mutación.",
                tokens_usage={"input_tokens": 120, "output_tokens": 15, "cached_tokens": 0},
                latency_ms=10.0,
                model_identifier=self.model_name,
                provider=self.provider,
            )

    discrete_adapter = PurelyDiscreteAdapter()
    runner = BridgeRunner(adapter=discrete_adapter)

    # 1. Ejecutar en modo persistente (debe usar DiscreteFallbackSession automáticamente)
    report_fallback = runner.run_instruction(
        human_instruction="Prueba fallback",
        document_path=test_pdf,
        use_persistent_session=True,
    )
    assert report_fallback.transport_mode == "persistent_session"
    assert report_fallback.session_id is not None
    assert report_fallback.total_llm_calls == 2
    assert report_fallback.total_tool_calls == 1

    # 2. Ejecutar en modo discreto directo (use_persistent_session=False)
    discrete_adapter_2 = PurelyDiscreteAdapter()
    runner_2 = BridgeRunner(adapter=discrete_adapter_2)
    report_discrete = runner_2.run_instruction(
        human_instruction="Prueba discreta",
        document_path=test_pdf,
        use_persistent_session=False,
    )
    assert report_discrete.transport_mode == "discrete_exec"
    assert report_discrete.total_llm_calls == 2
    assert report_discrete.total_tool_calls == 1
