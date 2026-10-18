"""PROMETEO · External Agent Bridge Layer v0.1 (PROMETEO-BRIDGE-0001)
──────────────────────────────────────────────────────────────────
Capa agnóstica para permitir a agentes externos (OpenAI, Claude, Gemini,
o modelos locales) interactuar con el sistema operativo documental PROMETEO
exclusivamente a través de su Tool Contract público.

PRINCIPIO CENTRAL:
  MODEL ≠ PROMETEO
  El Core documental no depende de ningún SDK o proveedor LLM.
  El agente no tiene acceso a PyMuPDF ni a funciones internas del Core.
  Solo verify_operation tiene autoridad para producir PASS.
"""

from .adapter import AgentAdapter, AgentTurn, CodexCLIAdapter, MockAgentAdapter
from .bridge_runner import BridgeRunner, BridgeExecutionReport, BridgeStepLog

__all__ = [
    "AgentAdapter",
    "AgentTurn",
    "CodexCLIAdapter",
    "MockAgentAdapter",
    "BridgeRunner",
    "BridgeExecutionReport",
    "BridgeStepLog",
]
