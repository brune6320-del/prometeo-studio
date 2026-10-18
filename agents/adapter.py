"""PROMETEO · Agent Adapter Abstraction & Providers v0.2
──────────────────────────────────────────────────────
Desacopla la lógica del agente exterior respecto a PROMETEO.
El adaptador gestiona el intercambio de turnos entre la conversación,
las herramientas disponibles y el modelo LLM subyacente.

Soporta dos modalidades de transporte:
1. Transporte Discreto (execute_turn): Cada turno envía contexto completo (--ephemeral).
2. Transporte Persistente (start_session -> AgentSession): Mantiene un hilo/sesión
   reutilizable (codex exec resume), eliminando la reinyección redundante de
   schemas y contexto base en cada turno.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class AgentTurn:
    """Representa el turno de decisión de un agente."""
    thought: str
    action: str  # "call_tool" | "finish" | "error"
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    raw_response: str = ""
    tokens_usage: Dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0})
    latency_ms: float = 0.0
    model_identifier: str = ""
    provider: str = ""
    session_id: str = ""


class AgentSession(ABC):
    """Representa una sesión conversacional persistente con un agente."""

    @property
    @abstractmethod
    def session_id(self) -> str:
        """Identificador canónico de la sesión (e.g. UUID de thread en Codex)."""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Indica si la sesión permanece abierta y puede recibir más turnos."""
        pass

    @property
    def initial_turn(self) -> Optional[AgentTurn]:
        """Devuelve el turno inicial devuelto al crear la sesión."""
        return None

    @abstractmethod
    def execute_turn(self, prompt: str) -> AgentTurn:
        """Ejecuta un nuevo turno en la sesión activa, enviando únicamente el prompt del turno."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Cierra la sesión y libera recursos asociados."""
        pass


class DiscreteFallbackSession(AgentSession):
    """Implementa AgentSession envolviendo un adapter puramente discreto.
    Garantiza compatibilidad hacia atrás si un adapter no soporta sesiones nativas."""

    def __init__(
        self,
        adapter: AgentAdapter,
        messages: List[Dict[str, str]],
        tools_schemas: List[Dict[str, Any]],
        initial_turn: AgentTurn,
        session_id: str,
    ):
        self._adapter = adapter
        self._messages = list(messages)
        self._tools_schemas = list(tools_schemas)
        self._initial_turn = initial_turn
        self._session_id = session_id
        self._is_active = True

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def initial_turn(self) -> Optional[AgentTurn]:
        return self._initial_turn

    def execute_turn(self, prompt: str) -> AgentTurn:
        if not self._is_active:
            raise RuntimeError(f"La sesión {self._session_id} ha sido cerrada.")
        self._messages.append({"role": "user", "content": prompt})
        turn = self._adapter.execute_turn(self._messages, self._tools_schemas)
        turn.session_id = self._session_id
        if turn.action == "call_tool":
            self._messages.append({
                "role": "model",
                "content": json.dumps({
                    "thought": turn.thought,
                    "action": "call_tool",
                    "tool_name": turn.tool_name,
                    "arguments": turn.arguments,
                }),
            })
        return turn

    def close(self) -> None:
        self._is_active = False


class AgentAdapter(ABC):
    """Interfaz abstracta e intercambiable para cualquier proveedor o modelo."""

    @property
    @abstractmethod
    def provider(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def execute_turn(
        self,
        messages: List[Dict[str, str]],
        tools_schemas: List[Dict[str, Any]],
        temperature: float = 0.0,
    ) -> AgentTurn:
        """Envía el historial conversacional y las definiciones de herramientas,
        devolviendo el siguiente AgentTurn tipado (modo discreto)."""
        pass

    def start_session(
        self,
        initial_prompt: str,
        tools_schemas: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> AgentSession:
        """Inicia una sesión persistente con el agente.
        Por defecto genera una DiscreteFallbackSession para adapters que no
        implementen sesiones nativas."""
        session_id = f"fallback_{uuid.uuid4().hex[:12]}"
        messages = [{"role": "user", "content": initial_prompt}]
        first_turn = self.execute_turn(messages, tools_schemas, temperature=temperature)
        first_turn.session_id = session_id
        if first_turn.action == "call_tool":
            messages.append({
                "role": "model",
                "content": json.dumps({
                    "thought": first_turn.thought,
                    "action": "call_tool",
                    "tool_name": first_turn.tool_name,
                    "arguments": first_turn.arguments,
                }),
            })
        return DiscreteFallbackSession(
            adapter=self,
            messages=messages,
            tools_schemas=tools_schemas,
            initial_turn=first_turn,
            session_id=session_id,
        )


class CodexSession(AgentSession):
    """Sesión persistente respaldada por hilos nativos de Codex CLI (codex exec resume)."""

    def __init__(
        self,
        adapter: CodexCLIAdapter,
        thread_id: str,
        initial_turn: AgentTurn,
    ):
        self._adapter = adapter
        self._thread_id = thread_id
        self._initial_turn = initial_turn
        self._is_active = True

    @property
    def session_id(self) -> str:
        return self._thread_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def initial_turn(self) -> Optional[AgentTurn]:
        return self._initial_turn

    def execute_turn(self, prompt: str) -> AgentTurn:
        if not self._is_active:
            raise RuntimeError(f"La sesión {self._thread_id} ha sido cerrada y no acepta más turnos.")
        return self._adapter._execute_resume_turn(self._thread_id, prompt)

    def close(self, cleanup_remote: bool = False) -> None:
        if self._is_active:
            self._is_active = False
            if cleanup_remote:
                self._adapter._delete_session(self._thread_id)


class CodexCLIAdapter(AgentAdapter):
    """Adaptador real basado en el CLI de Codex y cuenta ChatGPT (OpenAI gpt-5.6-luna).
    Soporta modo discreto y modo de sesión persistente nativa (resume)."""

    def __init__(
        self,
        codex_bin: str = "codex",
        model: str = "gpt-5.6-luna",
        timeout_seconds: int = 90,
    ):
        self.codex_bin = codex_bin
        self._model = model
        self.timeout_seconds = timeout_seconds

    @property
    def provider(self) -> str:
        return "openai_codex_cli"

    @property
    def model_name(self) -> str:
        return self._model

    def _build_system_prompt(self, tools_schemas: List[Dict[str, Any]]) -> str:
        schemas_str = json.dumps(tools_schemas, indent=2, ensure_ascii=False)
        return (
            "Eres un agente autónomo interactuando con el sistema operativo documental PROMETEO.\n"
            "Tu objetivo es cumplir las instrucciones humanas sobre documentos PDF usando ÚNICAMENTE "
            "las 7 herramientas documentales disponibles.\n\n"
            "REGLAS FUNDAMENTALES Y CRÍTICAS:\n"
            "1. MODEL ≠ PROMETEO: Tú NO tienes acceso al sistema de archivos del PDF ni a PyMuPDF.\n"
            "2. NUNCA afirmes verbalmente que una operación fue exitosa (PASS) antes de que la herramienta "
            "'verify_operation' haya devuelto explícitamente result_state == 'PASS'.\n"
            "3. Flujo típico de modificación:\n"
            "   open_document → inspect_document → find_text → select_target (si hay candidatos) → "
            "replace_text → export_document → verify_operation.\n"
            "4. Si 'find_text' devuelve estado AMBIGUOUS (más de una coincidencia), NO adivines ni inventes targets: "
            "debes inspeccionar los candidatos y usar 'select_target' con el 'candidate_id' apropiado, o pedir aclaración.\n"
            "5. Si 'replace_text' devuelve HONEST_REJECT, acéptalo honestamente y NO intentes forzar la mutación.\n"
            "6. Solo puedes llamar a UNA herramienta por turno.\n\n"
            f"HERRAMIENTAS DISPONIBLES (JSON SCHEMA):\n{schemas_str}\n\n"
            "FORMATO OBLIGATORIO DE RESPUESTA:\n"
            "Debes responder SIEMPRE y ÚNICAMENTE un objeto JSON válido con este esquema exacto:\n"
            "Para invocar una herramienta:\n"
            "{\n"
            '  "thought": "<tu razonamiento conciso>",\n'
            '  "action": "call_tool",\n'
            '  "tool_name": "<nombre de la herramienta>",\n'
            '  "arguments": { <diccionario con los parámetros requeridos> }\n'
            "}\n"
            "Para finalizar y comunicar el resultado al usuario:\n"
            "{\n"
            '  "thought": "<tu conclusión>",\n'
            '  "action": "finish",\n'
            '  "message": "<mensaje final describiendo el resultado y la evidencia de verify_operation>"\n'
            "}\n"
            "No incluyas texto antes o después del JSON. Solo el JSON."
        )

    def _run_subprocess(self, cmd: List[str], t0: float) -> Tuple[Optional[subprocess.CompletedProcess], str, str, float]:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            return proc, proc.stdout, proc.stderr, elapsed
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return None, "", f"El modelo excedió el timeout de {self.timeout_seconds}s", elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return None, "", str(e), elapsed

    def _parse_json_stream(
        self,
        raw_stdout: str,
        raw_stderr: str,
        returncode: int,
        elapsed: float,
    ) -> Tuple[str, AgentTurn]:
        """Parsea la salida JSONL emitida por codex --json, extrayendo thread_id, tokens y decisión."""
        thread_id = ""
        agent_text = ""
        usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

        for line in raw_stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
                ev_type = ev.get("type")
                if ev_type == "thread.started":
                    thread_id = ev.get("thread_id", "")
                elif ev_type == "item.completed":
                    item = ev.get("item", {})
                    if item.get("type") == "agent_message":
                        agent_text = item.get("text", "")
                elif ev_type == "turn.completed":
                    u = ev.get("usage", {})
                    usage["input_tokens"] = u.get("input_tokens", 0)
                    usage["output_tokens"] = u.get("output_tokens", 0)
                    usage["cached_tokens"] = u.get("cached_input_tokens", 0)
            except Exception:
                pass

        if not agent_text and returncode != 0:
            turn = AgentTurn(
                thought="Error devuelto por Codex CLI",
                action="error",
                message=raw_stderr or "Codex CLI exited with non-zero code",
                raw_response=raw_stdout,
                latency_ms=elapsed,
                tokens_usage=usage,
                model_identifier=self._model,
                provider=self.provider,
            )
            return thread_id, turn

        # Extraer JSON de la respuesta del modelo
        cleaned = agent_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
            thought = parsed.get("thought", "")
            action = parsed.get("action", "finish")
            tool_name = parsed.get("tool_name")
            arguments = parsed.get("arguments", {})
            message = parsed.get("message", "")

            turn = AgentTurn(
                thought=thought,
                action=action,
                tool_name=tool_name,
                arguments=arguments if isinstance(arguments, dict) else {},
                message=message,
                raw_response=agent_text,
                tokens_usage=usage,
                latency_ms=elapsed,
                model_identifier=self._model,
                provider=self.provider,
            )
            return thread_id, turn
        except Exception as pe:
            turn = AgentTurn(
                thought="Fallo al parsear JSON devuelto por el modelo",
                action="error",
                message=f"JSON Parse Error: {pe}. Raw output: {agent_text}",
                raw_response=agent_text,
                tokens_usage=usage,
                latency_ms=elapsed,
                model_identifier=self._model,
                provider=self.provider,
            )
            return thread_id, turn

    def execute_turn(
        self,
        messages: List[Dict[str, str]],
        tools_schemas: List[Dict[str, Any]],
        temperature: float = 0.0,
    ) -> AgentTurn:
        """Modo discreto original: crea un proceso efímero nuevo con el historial completo."""
        t0 = time.perf_counter()
        system_prompt = self._build_system_prompt(tools_schemas)

        conv_parts = [system_prompt, "\n--- HISTORIAL DE CONVERSACIÓN ---"]
        for m in messages:
            role = m.get("role", "user").upper()
            content = m.get("content", "")
            conv_parts.append(f"[{role}]:\n{content}\n")
        conv_parts.append(
            "[INSTRUCCIÓN DE RETORNO]: Emite ahora tu siguiente decisión en el formato JSON obligatorio."
        )
        full_prompt = "\n".join(conv_parts)

        cmd = [
            self.codex_bin,
            "exec",
            "-m",
            self._model,
            "-s",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--json",
            full_prompt,
        ]

        proc, stdout, stderr, elapsed = self._run_subprocess(cmd, t0)
        if proc is None:
            return AgentTurn(
                thought="Error al ejecutar proceso Codex",
                action="error",
                message=stderr,
                latency_ms=elapsed,
                model_identifier=self._model,
                provider=self.provider,
            )

        _, turn = self._parse_json_stream(stdout, stderr, proc.returncode, elapsed)
        return turn

    def start_session(
        self,
        initial_prompt: str,
        tools_schemas: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> CodexSession:
        """Inicia una sesión persistente nativa (sin --ephemeral) en Codex CLI."""
        t0 = time.perf_counter()
        sys_prompt = system_prompt or self._build_system_prompt(tools_schemas)
        full_initial_prompt = (
            f"{sys_prompt}\n\n"
            "--- INSTRUCCIÓN DEL USUARIO ---\n"
            f"{initial_prompt}\n\n"
            "[INSTRUCCIÓN DE RETORNO]: Emite ahora tu siguiente decisión en el formato JSON obligatorio."
        )

        cmd = [
            self.codex_bin,
            "exec",
            "-m",
            self._model,
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--json",
            full_initial_prompt,
        ]

        proc, stdout, stderr, elapsed = self._run_subprocess(cmd, t0)
        if proc is None:
            err_turn = AgentTurn(
                thought="Error al iniciar sesión Codex",
                action="error",
                message=stderr,
                latency_ms=elapsed,
                model_identifier=self._model,
                provider=self.provider,
            )
            return CodexSession(
                adapter=self,
                thread_id=f"error_{int(time.time()*1000)}",
                initial_turn=err_turn,
            )

        thread_id, turn = self._parse_json_stream(stdout, stderr, proc.returncode, elapsed)
        if not thread_id:
            thread_id = f"thread_{int(time.time()*1000)}"

        turn.session_id = thread_id
        return CodexSession(
            adapter=self,
            thread_id=thread_id,
            initial_turn=turn,
        )

    def _execute_resume_turn(self, thread_id: str, prompt: str) -> AgentTurn:
        """Reanuda la sesión en Codex CLI enviando únicamente el prompt del turno."""
        t0 = time.perf_counter()
        cmd = [
            self.codex_bin,
            "exec",
            "resume",
            thread_id,
            prompt,
            "--skip-git-repo-check",
            "--json",
            "-m",
            self._model,
        ]

        proc, stdout, stderr, elapsed = self._run_subprocess(cmd, t0)
        if proc is None:
            return AgentTurn(
                thought="Error al reanudar sesión Codex",
                action="error",
                message=stderr,
                latency_ms=elapsed,
                model_identifier=self._model,
                provider=self.provider,
                session_id=thread_id,
            )

        _, turn = self._parse_json_stream(stdout, stderr, proc.returncode, elapsed)
        turn.session_id = thread_id
        return turn

    def _delete_session(self, thread_id: str) -> bool:
        """Elimina la sesión del almacenamiento local de Codex."""
        cmd = [self.codex_bin, "delete", "--force", thread_id]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return res.returncode == 0
        except Exception:
            return False


class MockAgentSession(AgentSession):
    """Sesión determinista para testing unitario y adversarial sin red."""

    def __init__(
        self,
        adapter: MockAgentAdapter,
        session_id: str,
        initial_turn: AgentTurn,
    ):
        self._adapter = adapter
        self._session_id = session_id
        self._initial_turn = initial_turn
        self._is_active = True

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def initial_turn(self) -> Optional[AgentTurn]:
        return self._initial_turn

    def execute_turn(self, prompt: str) -> AgentTurn:
        if not self._is_active:
            raise RuntimeError(f"La sesión {self._session_id} ha sido cerrada y no acepta más turnos.")
        turn = self._adapter._next_mock_turn()
        turn.session_id = self._session_id
        return turn

    def close(self) -> None:
        self._is_active = False


class MockAgentAdapter(AgentAdapter):
    """Adaptador offline determinista para pruebas automatizadas y de regresión sin red."""

    def __init__(
        self,
        scripted_turns: Optional[List[Dict[str, Any]]] = None,
        model_name: str = "mock-deterministic-v1",
    ):
        self.scripted_turns = scripted_turns or []
        self._model = model_name
        self.call_count = 0
        self.sessions_created: List[str] = []

    @property
    def provider(self) -> str:
        return "mock_deterministic"

    @property
    def model_name(self) -> str:
        return self._model

    def _next_mock_turn(self) -> AgentTurn:
        t0 = time.perf_counter()
        if self.call_count < len(self.scripted_turns):
            turn_data = self.scripted_turns[self.call_count]
            self.call_count += 1
        else:
            turn_data = {
                "thought": "No more scripted turns, finishing.",
                "action": "finish",
                "message": "Scripted execution complete.",
            }

        elapsed = (time.perf_counter() - t0) * 1000.0

        return AgentTurn(
            thought=turn_data.get("thought", ""),
            action=turn_data.get("action", "finish"),
            tool_name=turn_data.get("tool_name"),
            arguments=turn_data.get("arguments", {}),
            message=turn_data.get("message", ""),
            raw_response=json.dumps(turn_data),
            tokens_usage={"input_tokens": 100, "output_tokens": 50, "cached_tokens": 40},
            latency_ms=elapsed,
            model_identifier=self._model,
            provider=self.provider,
        )

    def execute_turn(
        self,
        messages: List[Dict[str, str]],
        tools_schemas: List[Dict[str, Any]],
        temperature: float = 0.0,
    ) -> AgentTurn:
        return self._next_mock_turn()

    def start_session(
        self,
        initial_prompt: str,
        tools_schemas: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> MockAgentSession:
        sess_id = f"mock_sess_{uuid.uuid4().hex[:12]}"
        self.sessions_created.append(sess_id)
        first_turn = self._next_mock_turn()
        first_turn.session_id = sess_id
        return MockAgentSession(
            adapter=self,
            session_id=sess_id,
            initial_turn=first_turn,
        )
