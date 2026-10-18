"""Filtro de PDFs no confiables (CAMP-002 · F5).

Antes de que el motor abra un PDF aportado por la persona, un subproceso aislado lo analiza
entero (`pdf_gate_worker.py`) con límites de tiempo, CPU, memoria y páginas. Si el análisis se
cuelga, revienta o se excede, el PDF se rechaza con un código claro y el motor sigue vivo.

Qué protege: la DISPONIBILIDAD del motor frente a PDFs que cuelgan, revientan o agotan la memoria
del analizador. Qué NO protege: después de pasar el filtro, el motor sigue usando MuPDF en su propio
proceso (render, edición, verificación), sin encierro. Un exploit que no se cuelgue ni reviente
pasaría el filtro (incluso podría falsificar la aprobación desde el subproceso) y se ejecutaría
después en el motor. Defensa completa: todo MuPDF en un proceso encerrado permanente (pendiente).
Ver PROMETEO_SECURITY_HARDENING.md.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_gate_worker.py")

# Tiempo de pared: base + margen por página (un libro legítimo de 1 500 páginas densas tarda
# ~30 s; con un límite fijo se rechazaba), con un techo absoluto.
TIMEOUT_S = float(os.environ.get("PROMETEO_PDF_GATE_TIMEOUT_S", "30"))
PER_PAGE_S = float(os.environ.get("PROMETEO_PDF_GATE_PER_PAGE_S", "0.05"))
MAX_TIMEOUT_S = float(os.environ.get("PROMETEO_PDF_GATE_MAX_TIMEOUT_S", "120"))
# CPU: respaldo para un analizador huérfano (el control efectivo es el tiempo de pared).
CPU_S = int(os.environ.get("PROMETEO_PDF_GATE_CPU_S", "180"))
MAX_RSS_MB = int(os.environ.get("PROMETEO_PDF_GATE_MAX_RSS_MB", "2048"))
MAX_PAGES = int(os.environ.get("PROMETEO_PDF_GATE_MAX_PAGES", "5000"))
# Salida máxima que se conserva del analizador (el veredicto es una línea JSON corta).
_KEEP_STDOUT = 1 << 20
_KEEP_STDERR = 64 << 10

# Encierro del analizador (macOS Seatbelt). Aunque un PDF hostil lograra ejecutar código en el
# subproceso, no podría: usar la red, escribir en disco, crear procesos, ejecutar otros programas
# (p. ej. `open` o `launchctl`), pedir servicios del sistema (mach-lookup) ni enviar señales a otros
# procesos (p. ej. matar al motor). SÍ puede leer archivos de la persona (sin vía de salida).
# `sandbox-exec` está marcado como obsoleto por Apple: si desaparece, el filtro sigue (solo
# límites) y cada veredicto lo registra (`details.sandboxed`).
SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def _sbpl_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sandbox_profile(runtime_root: str) -> str:
    return ("(version 1)(allow default)"
            "(deny network*)"
            '(deny file-write* (subpath "/"))(allow file-write-data (literal "/dev/null"))'
            "(deny process-fork)"
            "(deny process-exec*)(allow process-exec (subpath " + _sbpl_string(runtime_root) + "))"
            "(deny signal)(allow signal (target self))"
            "(deny mach-lookup)")


def _sandbox_available() -> bool:
    return sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC) and os.environ.get("PROMETEO_PDF_GATE_SANDBOX", "1") != "0"


# Grupos de procesos de analizadores vivos: el motor los mata al apagarse (`kill_live_workers`).
_LIVE: "set[int]" = set()
_LIVE_LOCK = threading.Lock()


def kill_live_workers() -> int:
    with _LIVE_LOCK:
        pgids = list(_LIVE)
        _LIVE.clear()
    for pgid in pgids:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            pass
    return len(pgids)


class PdfRejected(Exception):
    """El filtro rechazó el PDF (el motor no llegó a analizarlo)."""

    def __init__(self, result: "GateResult"):
        super().__init__(f"{result.code}: {result.reason}")
        self.result = result


@dataclass
class GateResult:
    ok: bool
    code: Optional[str] = None
    reason: str = ""
    pages: Optional[int] = None
    seconds: float = 0.0
    peak_rss_mb: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


# Aprobaciones recientes por huella SHA-256 del contenido: los mismos bytes producen el mismo
# análisis (MuPDF es determinista), así que reabrir un PDF ya aprobado no se reanaliza. Solo se
# guardan aprobaciones: un rechazo (p. ej. por tiempo con el Mac cargado) se vuelve a evaluar.
_PASSED: "OrderedDict[str, GateResult]" = OrderedDict()
_PASSED_MAX = 64
_PASSED_LOCK = threading.Lock()


def preflight_cached(path: str, content_sha256: str, **limits) -> GateResult:
    with _PASSED_LOCK:
        hit = _PASSED.get(content_sha256)
        if hit is not None:
            _PASSED.move_to_end(content_sha256)
            return GateResult(True, pages=hit.pages, seconds=0.0,
                              details={"cached": True, "sandboxed": hit.details.get("sandboxed")})
    result = preflight(path, **limits)
    if result.ok:
        with _PASSED_LOCK:
            _PASSED[content_sha256] = result
            while len(_PASSED) > _PASSED_MAX:
                _PASSED.popitem(last=False)
    return result


# Memoria del subproceso. En macOS se usa la huella física (phys_footprint, la de Monitor de
# Actividad): incluye la memoria comprimida. El RSS no la incluye y se queda corto con datos
# muy comprimibles (medido: 1,9 GB reservados se veían como 260 MB de RSS). Lección GENESIS L-05.
try:
    import ctypes

    class _RusageInfoV0(ctypes.Structure):
        _fields_ = [("ri_uuid", ctypes.c_uint8 * 16), ("ri_user_time", ctypes.c_uint64), ("ri_system_time", ctypes.c_uint64),
                    ("ri_pkg_idle_wkups", ctypes.c_uint64), ("ri_interrupt_wkups", ctypes.c_uint64), ("ri_pageins", ctypes.c_uint64),
                    ("ri_wired_size", ctypes.c_uint64), ("ri_resident_size", ctypes.c_uint64), ("ri_phys_footprint", ctypes.c_uint64),
                    ("ri_proc_start_abstime", ctypes.c_uint64), ("ri_proc_exit_abstime", ctypes.c_uint64)]

    _LIBPROC = ctypes.CDLL("/usr/lib/libproc.dylib") if sys.platform == "darwin" else None
except Exception:  # pragma: no cover - plataformas sin libproc
    _LIBPROC = None


def _memory_mb(pid: int) -> float:
    """Huella física en macOS (incluye memoria comprimida); RSS en otras plataformas."""
    if _LIBPROC is not None:
        info = _RusageInfoV0()
        if _LIBPROC.proc_pid_rusage(int(pid), 0, ctypes.byref(info)) == 0:
            return max(info.ri_phys_footprint, info.ri_resident_size) / (1024 * 1024)
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=2).stdout.strip()
        return int(out) / 1024 if out else 0.0
    except Exception:
        return 0.0


def preflight(path: str, timeout_s: float = TIMEOUT_S, max_rss_mb: int = MAX_RSS_MB,
              max_pages: int = MAX_PAGES, cpu_s: int = CPU_S) -> GateResult:
    sandboxed = _sandbox_available()
    result = _analyze(path, timeout_s, max_rss_mb, max_pages, cpu_s, sandboxed)
    # Todo veredicto (aprobación o rechazo) declara si el análisis corrió dentro del sandbox.
    result.details.setdefault("sandboxed", sandboxed)
    return result


def _drain(stream, buf: bytearray, keep: int, on_line=None) -> None:
    """Lee la salida del analizador mientras corre: si nadie la lee y supera el búfer de la tubería
    (~64 KB), el analizador se bloquea y el filtro lo rechazaría por tiempo, por la causa equivocada."""
    pending = b""
    try:
        while True:
            chunk = stream.read1(65536)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > keep:
                del buf[: len(buf) - keep]
            if on_line is not None:
                pending = (pending + chunk)[-65536:]
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    on_line(line)
    except Exception:
        pass


def _analyze(path: str, timeout_s: float, max_rss_mb: int, max_pages: int, cpu_s: int, sandboxed: bool) -> GateResult:
    t0 = time.monotonic()
    cmd = [sys.executable, "-I", WORKER, path, str(max_pages), str(cpu_s)]
    if sandboxed:
        runtime_root = os.path.realpath(sys.base_prefix)
        cmd = [SANDBOX_EXEC, "-p", sandbox_profile(runtime_root)] + cmd
    # Entorno mínimo (el del motor lleva el token de sesión) y una tubería en stdin que el analizador
    # vigila: si el motor muere, la tubería se cierra y el analizador termina (no queda huérfano).
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"}
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, start_new_session=True)
    with _LIVE_LOCK:
        _LIVE.add(proc.pid)
    out_buf, err_buf = bytearray(), bytearray()
    announced: Dict[str, int] = {}

    def on_line(line: bytes) -> None:
        try:
            msg = json.loads(line)
        except Exception:
            return
        if isinstance(msg, dict) and msg.get("stage") == "opened" and isinstance(msg.get("pages"), int):
            announced["pages"] = max(0, msg["pages"])

    readers = [threading.Thread(target=_drain, args=(proc.stdout, out_buf, _KEEP_STDOUT, on_line), daemon=True),
               threading.Thread(target=_drain, args=(proc.stderr, err_buf, _KEEP_STDERR), daemon=True)]
    for r in readers:
        r.start()
    peak = 0.0
    killed_for: Optional[str] = None
    next_rss = 0.0
    try:
        while proc.poll() is None:
            elapsed = time.monotonic() - t0
            deadline = min(timeout_s + PER_PAGE_S * min(announced.get("pages", 0), max_pages), max(timeout_s, MAX_TIMEOUT_S))
            if elapsed > deadline:
                killed_for = "timeout"
            elif elapsed >= next_rss:
                rss = _memory_mb(proc.pid)
                peak = max(peak, rss)
                if rss > max_rss_mb:
                    killed_for = "memory"
                next_rss = elapsed + 0.05
            if killed_for:
                break
            time.sleep(0.02)
    finally:
        # Siempre se barre el grupo de procesos (también si el supervisor recibe una excepción).
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        proc.wait()
        with _LIVE_LOCK:
            _LIVE.discard(proc.pid)
        try:
            proc.stdin.close()
        except Exception:
            pass
    # Espera acotada a los lectores: un nieto que conservara la tubería no puede bloquear el filtro.
    join_until = time.monotonic() + 2.0
    for r in readers:
        r.join(timeout=max(0.0, join_until - time.monotonic()))
    seconds = round(time.monotonic() - t0, 3)
    limit_s = round(min(timeout_s + PER_PAGE_S * min(announced.get("pages", 0), max_pages), max(timeout_s, MAX_TIMEOUT_S)), 1)
    if killed_for == "timeout":
        return GateResult(False, "PDF_PARSE_TIMEOUT", f"el análisis superó {limit_s:.0f} s", seconds=seconds,
                          peak_rss_mb=round(peak, 1), details={"limit_s": limit_s})
    if killed_for == "memory":
        return GateResult(False, "PDF_TOO_COMPLEX", f"el análisis superó {max_rss_mb} MB de memoria", seconds=seconds, peak_rss_mb=round(peak, 1))
    rc = proc.returncode
    if rc is not None and rc < 0:
        try:
            sig = signal.Signals(-rc).name
        except ValueError:
            sig = str(-rc)
        code = "PDF_PARSE_TIMEOUT" if sig == "SIGXCPU" else "PDF_REJECTED_UNSAFE"
        return GateResult(False, code, f"el analizador terminó con la señal {sig}", seconds=seconds, peak_rss_mb=round(peak, 1),
                          details={"signal": sig})
    payload: Dict[str, Any] = {}
    for raw in reversed(bytes(out_buf).decode("utf-8", "replace").strip().splitlines()):
        try:
            cand = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(cand, dict) and "ok" in cand:
            payload = cand
            break
    if not payload:
        return GateResult(False, "PDF_REJECTED_UNSAFE", f"el analizador terminó sin respuesta (código {rc})", seconds=seconds,
                          peak_rss_mb=round(peak, 1), details={"stderr": bytes(err_buf).decode("utf-8", "replace")[-300:]})
    if payload.get("ok") is True:
        return GateResult(True, pages=payload.get("pages"), seconds=seconds, peak_rss_mb=round(peak, 1),
                          details={"mupdf_warnings": payload.get("mupdf_warnings", 0)})
    return GateResult(False, payload.get("code") or "DOCUMENT_UNREADABLE", payload.get("reason", ""), seconds=seconds,
                      peak_rss_mb=round(peak, 1))
