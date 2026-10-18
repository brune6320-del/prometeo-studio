"""PROMETEO · Bridge Execution Harness & Protocol Auditing v0.2
─────────────────────────────────────────────────────────────
Orquesta la interacción ciega entre una instrucción humana, un modelo LLM externo
y el PROMETEO Tool Contract v0.1.

Soporta:
- Modo Persistente (AgentSession): reutiliza la sesión del agente eliminando
  overhead y tokens redundantes.
- Modo Discreto (execute_turn): ejecución clásica efímera de referencia.

AUDITA ESTRICTAMENTE:
1. Inmutabilidad absoluta del documento original (pre == post SHA256).
2. Autoridad exclusiva del Verifier (el agente no puede autodeclarar PASS).
3. SILENT_FAILURE == 0 invariante.
4. Trazabilidad completa de turnos, latencias, tokens y session_ids.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Import Tool Contract
try:
    from tools import PrometeoTools, ResultState, sha256_file
except ImportError:
    from fase0.tools import PrometeoTools, ResultState, sha256_file

from .adapter import AgentAdapter, AgentSession, AgentTurn


@dataclass
class BridgeStepLog:
    """Registro estructurado de cada paso o interacción en la sesión."""
    step_number: int
    timestamp: str
    role: str  # "human" | "model" | "tool"
    session_id: Optional[str] = None
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    result_state: Optional[str] = None
    document_id: Optional[str] = None
    operation_id: Optional[str] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BridgeExecutionReport:
    """Reporte formal de ejecución y auditoría para el Bridge de PROMETEO."""
    execution_id: str
    timestamp: str
    transport_mode: str  # "persistent_session" | "discrete_exec"
    session_id: Optional[str]
    human_instruction: str
    document_path: str
    destination_path: Optional[str]
    original_sha256_pre: str
    original_sha256_post: str
    output_sha256: Optional[str]
    provider: str
    model: str
    total_llm_calls: int
    total_tool_calls: int
    tools_used: List[str]
    invalid_tool_calls: int
    retries: int
    total_latency_ms: float
    llm_latency_ms: float
    tools_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    pass_count: int
    ambiguous_count: int
    honest_reject_count: int
    crash_count: int
    silent_failure_count: int
    protocol_violations: List[str]
    final_verdict: str  # "CLOSED_PASS" | "HONEST_REJECT" | "AMBIGUOUS" | "NOT_CLOSED"
    steps_log: List[Dict[str, Any]]
    verifier_result: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BridgeRunner:
    """Ejecutor del protocolo Bridge que comunica al agente con PROMETEO."""

    def __init__(self, adapter: AgentAdapter, tools: Optional[PrometeoTools] = None):
        self.adapter = adapter
        self.tools = tools or PrometeoTools()

    def run_instruction(
        self,
        human_instruction: str,
        document_path: str,
        destination_path: Optional[str] = None,
        max_turns: int = 12,
        use_persistent_session: bool = True,
        contract_version: str = "0.1",
    ) -> BridgeExecutionReport:
        t_global_start = time.perf_counter()
        exec_id = f"bridge_run_{int(time.time()*1000)}"
        timestamp_str = datetime.datetime.utcnow().isoformat() + "Z"
        transport_mode = "persistent_session" if use_persistent_session else "discrete_exec"

        abs_doc_path = os.path.abspath(document_path)
        sha_pre = sha256_file(abs_doc_path)

        steps: List[BridgeStepLog] = []
        messages: List[Dict[str, str]] = []
        protocol_violations: List[str] = []

        total_llm_calls = 0
        total_tool_calls = 0
        tools_used: List[str] = []
        invalid_tool_calls = 0
        retries = 0
        llm_latency_sum = 0.0
        tools_latency_sum = 0.0
        total_in_tokens = 0
        total_out_tokens = 0
        total_cached_tokens = 0

        pass_count = 0
        ambiguous_count = 0
        honest_reject_count = 0
        crash_count = 0
        silent_failure_count = 0

        last_document_id: Optional[str] = None
        last_operation_id: Optional[str] = None
        last_verifier_result: Optional[Dict[str, Any]] = None
        last_provenance: Optional[Dict[str, Any]] = None
        exported_path: Optional[str] = destination_path

        if contract_version == "0.2":
            tools_schemas = self.tools.get_tool_schemas_v0_2()
        else:
            tools_schemas = self.tools.get_tool_schemas()
        valid_tool_names = set(s["name"] for s in tools_schemas)

        # 1. Registrar instrucción humana inicial
        user_message_content = (
            f"Instrucción del usuario: {human_instruction}\n"
            f"Ruta del documento: {abs_doc_path}\n"
        )
        if destination_path:
            user_message_content += f"Ruta destino sugerida para exportar: {os.path.abspath(destination_path)}\n"

        session: Optional[AgentSession] = None
        current_session_id: Optional[str] = None

        if use_persistent_session:
            session = self.adapter.start_session(
                initial_prompt=user_message_content,
                tools_schemas=tools_schemas,
            )
            current_session_id = session.session_id
        else:
            messages.append({"role": "user", "content": user_message_content})

        steps.append(
            BridgeStepLog(
                step_number=len(steps) + 1,
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                role="human",
                session_id=current_session_id,
                message=user_message_content,
            )
        )

        turn_idx = 0
        verified_pass_reached = False

        # Si estamos en modo persistente, el turno 1 ya fue ejecutado por start_session
        current_turn: Optional[AgentTurn] = session.initial_turn if session else None

        try:
            while turn_idx < max_turns:
                turn_idx += 1
                total_llm_calls += 1

                if current_turn is None:
                    # Invocación en modo discreto
                    turn = self.adapter.execute_turn(messages, tools_schemas)
                else:
                    turn = current_turn
                    current_turn = None

                llm_latency_sum += turn.latency_ms
                in_tok = turn.tokens_usage.get("input_tokens", 0)
                out_tok = turn.tokens_usage.get("output_tokens", 0)
                cached_tok = turn.tokens_usage.get("cached_tokens", 0)
                total_in_tokens += in_tok
                total_out_tokens += out_tok
                total_cached_tokens += cached_tok

                if turn.session_id and not current_session_id:
                    current_session_id = turn.session_id

                # Registrar turno del modelo
                steps.append(
                    BridgeStepLog(
                        step_number=len(steps) + 1,
                        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                        role="model",
                        session_id=current_session_id,
                        thought=turn.thought,
                        tool_name=turn.tool_name,
                        tool_arguments=turn.arguments,
                        message=turn.message,
                        latency_ms=turn.latency_ms,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cached_tokens=cached_tok,
                        error=turn.message if turn.action == "error" else None,
                    )
                )

                if turn.action == "error":
                    retries += 1
                    err_prompt = f"Error en la llamada al modelo: {turn.message}. Por favor reintenta emitiendo JSON válido."
                    if session:
                        current_turn = session.execute_turn(err_prompt)
                    else:
                        messages.append({"role": "user", "content": err_prompt})
                    continue

                if turn.action == "finish":
                    # Control de autoridad: comprobar si el agente afirmó éxito sin verifier
                    finish_text_lower = (turn.message + " " + turn.thought).lower()
                    has_pass_mention = bool(re.search(r'\bpass\b', finish_text_lower))
                    negated_pass = bool(re.search(r'\b(no\s+(hubo|se\s+generó|hay|obtuvo|emitió)|ni\s+un|sin)\s+pass\b', finish_text_lower))
                    
                    has_exito = any(w in finish_text_lower for w in ["éxito", "exitosamente", "completado con éxito", "verificado con éxito"])
                    negated_exito = any(w in finish_text_lower for w in ["sin éxito", "no tuvo éxito", "no fue exitoso", "no con éxito"])

                    claims_success = (has_pass_mention and not negated_pass) or (has_exito and not negated_exito)
                    if claims_success and not verified_pass_reached:
                        violation = (
                            "VIOLACIÓN DE AUTORIDAD: El agente afirmó éxito o PASS verbalmente "
                            "sin que verify_operation haya producido un resultado PASS."
                        )
                        protocol_violations.append(violation)
                    break

                if turn.action == "call_tool":
                    total_tool_calls += 1
                    tname = turn.tool_name or ""
                    targs = turn.arguments or {}

                    if tname not in valid_tool_names:
                        invalid_tool_calls += 1
                        err_msg = f"Herramienta inválida o inexistente: '{tname}'. Solo puedes usar las 7 herramientas oficiales."
                        inv_res = {
                            "ok": False,
                            "result_state": ResultState.HONEST_REJECT.value,
                            "error": err_msg,
                        }
                        inv_prompt = f"Resultado de la herramienta {tname}:\n{json.dumps(inv_res, ensure_ascii=False)}\n[INSTRUCCIÓN DE RETORNO]: Emite ahora tu siguiente decisión en el formato JSON obligatorio."
                        if session:
                            current_turn = session.execute_turn(inv_prompt)
                        else:
                            messages.append({
                                "role": "model",
                                "content": json.dumps({
                                    "thought": turn.thought,
                                    "action": "call_tool",
                                    "tool_name": tname,
                                    "arguments": targs,
                                }),
                            })
                            messages.append({"role": "user", "content": inv_prompt})
                        continue

                    tools_used.append(tname)

                    # Ejecutar herramienta en PROMETEO Tool Contract
                    t_tool_start = time.perf_counter()
                    tool_res = self.tools.execute_tool(tname, targs)
                    tool_lat = (time.perf_counter() - t_tool_start) * 1000.0
                    tools_latency_sum += tool_lat

                    res_state = tool_res.get("result_state")
                    doc_id = tool_res.get("document_id") or targs.get("document_id")
                    op_id = tool_res.get("operation_id") or targs.get("operation_id")

                    if doc_id:
                        last_document_id = doc_id
                    if op_id:
                        last_operation_id = op_id

                    if tname in ("export_document", "export_transaction"):
                        exported_path = tool_res.get("destination") or tool_res.get("output_pdf_path")

                    # Actualizar contadores formales
                    if res_state == ResultState.PASS.value or (tname == "verify_transaction" and tool_res.get("verdict") == "PASS"):
                        pass_count += 1
                        verified_pass_reached = True
                        last_verifier_result = tool_res.get("verifier_result") or tool_res.get("details")
                        last_provenance = tool_res.get("provenance")
                    elif res_state == ResultState.AMBIGUOUS.value or (tname == "stage_transaction" and tool_res.get("reason") == "AMBIGUOUS"):
                        ambiguous_count += 1
                    elif res_state == ResultState.HONEST_REJECT.value or (tname in ("stage_transaction", "export_transaction", "verify_transaction") and tool_res.get("status") in ("HONEST_REJECT", "FAILED")):
                        honest_reject_count += 1
                    elif res_state == ResultState.CRASH.value:
                        crash_count += 1

                    # Auditoría de SILENT_FAILURE: si una herramienta afirmara ok=True en falso
                    if tool_res.get("ok") and res_state == ResultState.PASS.value:
                        if not tool_res.get("verifier_result", {}).get("ok"):
                            silent_failure_count += 1
                            protocol_violations.append(
                                "CRITICAL: Herramienta declaró PASS pero el verifier_result no es ok!"
                            )

                    # Registrar paso de la herramienta
                    steps.append(
                        BridgeStepLog(
                            step_number=len(steps) + 1,
                            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                            role="tool",
                            session_id=current_session_id,
                            tool_name=tname,
                            tool_arguments=targs,
                            tool_result=tool_res,
                            result_state=res_state,
                            document_id=last_document_id,
                            operation_id=last_operation_id,
                            latency_ms=tool_lat,
                        )
                    )

                    next_turn_prompt = (
                        f"Resultado de {tname}:\n"
                        f"{json.dumps(tool_res, ensure_ascii=False)}\n"
                        "[INSTRUCCIÓN DE RETORNO]: Emite ahora tu siguiente decisión en el formato JSON obligatorio."
                    )

                    if session:
                        current_turn = session.execute_turn(next_turn_prompt)
                    else:
                        messages.append({
                            "role": "model",
                            "content": json.dumps({
                                "thought": turn.thought,
                                "action": "call_tool",
                                "tool_name": tname,
                                "arguments": targs,
                            }),
                        })
                        messages.append({
                            "role": "user",
                            "content": next_turn_prompt,
                        })

        finally:
            if session:
                session.close()

        # Auditoría de Inmutabilidad del Original post-ejecución
        sha_post = sha256_file(abs_doc_path)
        if sha_pre != sha_post:
            protocol_violations.append(
                f"CORRUPCIÓN CRÍTICA: El archivo original {abs_doc_path} fue alterado en disco!"
            )

        output_sha: Optional[str] = None
        if exported_path and os.path.isfile(exported_path):
            output_sha = sha256_file(exported_path)

        total_elapsed = (time.perf_counter() - t_global_start) * 1000.0

        # Determinar veredicto final
        if verified_pass_reached and len(protocol_violations) == 0 and sha_pre == sha_post:
            verdict = "CLOSED_PASS"
        elif honest_reject_count > 0 and len(protocol_violations) == 0:
            verdict = ResultState.HONEST_REJECT.value
        elif ambiguous_count > 0 and len(protocol_violations) == 0:
            verdict = ResultState.AMBIGUOUS.value
        else:
            verdict = "NOT_CLOSED"

        return BridgeExecutionReport(
            execution_id=exec_id,
            timestamp=timestamp_str,
            transport_mode=transport_mode,
            session_id=current_session_id,
            human_instruction=human_instruction,
            document_path=abs_doc_path,
            destination_path=exported_path,
            original_sha256_pre=sha_pre,
            original_sha256_post=sha_post,
            output_sha256=output_sha,
            provider=self.adapter.provider,
            model=self.adapter.model_name,
            total_llm_calls=total_llm_calls,
            total_tool_calls=total_tool_calls,
            tools_used=tools_used,
            invalid_tool_calls=invalid_tool_calls,
            retries=retries,
            total_latency_ms=round(total_elapsed, 2),
            llm_latency_ms=round(llm_latency_sum, 2),
            tools_latency_ms=round(tools_latency_sum, 2),
            total_input_tokens=total_in_tokens,
            total_output_tokens=total_out_tokens,
            total_cached_tokens=total_cached_tokens,
            pass_count=pass_count,
            ambiguous_count=ambiguous_count,
            honest_reject_count=honest_reject_count,
            crash_count=crash_count,
            silent_failure_count=silent_failure_count,
            protocol_violations=protocol_violations,
            final_verdict=verdict,
            steps_log=[asdict(s) for s in steps],
            verifier_result=last_verifier_result,
            provenance=last_provenance,
        )
