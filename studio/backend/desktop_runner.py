"""PROMETEO Desktop Sidecar Runner
───────────────────────────────────
Lanza el backend FastAPI de PROMETEO como proceso hijo gestionado (sidecar)
de la aplicación de escritorio Tauri:
- Enlaza estrictamente a loopback (127.0.0.1) en el puerto que asigna el host.
- Recibe el token de sesión por stdin (primera línea "TOKEN <valor>"), nunca por
  argumentos: los argumentos de un proceso son visibles con `ps`.
- Nunca escribe el token en registros.
- Termina cuando el host cierra stdin o muere (sin procesos huérfanos) y borra
  la carpeta de su instancia en el workspace.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time


def _cleanup_and_exit(code: int = 0) -> None:
    try:
        mod = sys.modules.get("studio.backend.app")
        if mod is not None and hasattr(mod, "shutdown_cleanup"):
            mod.shutdown_cleanup()
    except Exception:
        pass
    os._exit(code)


def _stdin_lifeline_thread() -> None:
    """Si el host cierra stdin (sale o muere), el sidecar termina."""
    try:
        if sys.stdin is not None and not sys.stdin.closed:
            sys.stdin.read()
    except Exception:
        pass
    finally:
        _cleanup_and_exit(0)


def _parent_pid_monitor(parent_pid: int) -> None:
    if parent_pid <= 0:
        return
    while True:
        time.sleep(1.0)
        try:
            os.kill(parent_pid, 0)
        except OSError:
            _cleanup_and_exit(0)


def _read_token_from_stdin(timeout_s: float = 10.0) -> str:
    """Primera línea de stdin: 'TOKEN <valor>'."""
    result = {"token": ""}

    def reader():
        line = sys.stdin.readline()
        if line.startswith("TOKEN "):
            result["token"] = line[6:].strip()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(timeout_s)
    return result["token"]


def main() -> None:
    parser = argparse.ArgumentParser(description="PROMETEO Desktop Sidecar Runner")
    parser.add_argument("--port", type=int, default=8000, help="Puerto loopback para escuchar")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host loopback")
    parser.add_argument("--token-stdin", action="store_true",
                        help="Leer el token de sesión de la primera línea de stdin")
    parser.add_argument("--parent-pid", type=int, default=0, help="PID del proceso host (Tauri)")
    parser.add_argument("--watch-stdin", action="store_true",
                        help="Terminar cuando stdin se cierre")
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("[PROMETEO SIDECAR] ERROR: solo se admite loopback", file=sys.stderr, flush=True)
        sys.exit(2)

    os.environ["PROMETEO_RUNTIME_MODE"] = "DESKTOP_SIDECAR"
    os.environ["PROMETEO_PORT"] = str(args.port)
    if args.token_stdin:
        token = _read_token_from_stdin()
        if not token:
            print("[PROMETEO SIDECAR] ERROR: no se recibió el token de sesión por stdin", file=sys.stderr, flush=True)
            sys.exit(3)
        os.environ["PROMETEO_AUTH_TOKEN"] = token

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for p in (os.path.join(repo_root, "fase0"), repo_root):
        if p not in sys.path:
            sys.path.insert(0, p)

    if args.watch_stdin:
        threading.Thread(target=_stdin_lifeline_thread, daemon=True).start()
    if args.parent_pid > 0:
        threading.Thread(target=_parent_pid_monitor, args=(args.parent_pid,), daemon=True).start()

    signal.signal(signal.SIGINT, lambda s, f: _cleanup_and_exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: _cleanup_and_exit(0))

    print(f"[PROMETEO SIDECAR] arrancando pid={os.getpid()} puerto={args.port}", file=sys.stderr, flush=True)
    import uvicorn
    from studio.backend.app import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
