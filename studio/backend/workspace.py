"""PROMETEO Studio · Resolución del workspace mutable (CLAUDE-REMEDIATION-001 · PA-001)
─────────────────────────────────────────────────────────────────────────────────
El código de la aplicación es inmutable (puede vivir en un DMG de solo lectura,
en /Applications sin permisos de escritura o en una ruta de App Translocation).
Los datos de sesión son mutables y viven SIEMPRE fuera del paquete:

  1. PROMETEO_WORKSPACE (lo fija el host Tauri con su carpeta de datos de app).
  2. Modo desarrollo fuera de un .app: studio/workspace del repositorio.
  3. Carpeta de datos del usuario del sistema operativo.
  4. Carpeta temporal del sistema (último recurso).

Ninguna ruta dentro de un paquete .app se acepta, venga de donde venga.
Cada proceso trabaja en su propia carpeta de instancia, que se elimina al cerrar;
las carpetas de instancias muertas se purgan al arrancar.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

APP_ID = "com.prometeo.studio"
STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class WorkspaceInfo:
    ok: bool
    root: Optional[str]
    source: Optional[str]
    errors: List[str] = field(default_factory=list)

    def public(self) -> dict:
        return {"ok": self.ok, "source": self.source, "root": self.root, "errors": self.errors}


def is_inside_app_bundle(path: str) -> bool:
    norm = os.path.abspath(path).replace("\\", "/")
    return ".app/Contents/" in norm + "/"


def user_data_dir() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_ID)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, "PROMETEO Studio")
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(base, "prometeo-studio")


def _candidates() -> List[Tuple[str, str]]:
    env = os.environ.get("PROMETEO_WORKSPACE")
    if env:
        return [("env", env)]
    out: List[Tuple[str, str]] = []
    desktop = os.environ.get("PROMETEO_RUNTIME_MODE") == "DESKTOP_SIDECAR"
    if not desktop and not is_inside_app_bundle(STUDIO_ROOT):
        out.append(("dev", os.path.join(STUDIO_ROOT, "workspace")))
    out.append(("user_data", os.path.join(user_data_dir(), "workspace")))
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    out.append(("temp", os.path.join(tempfile.gettempdir(), f"prometeo-studio-{uid}", "workspace")))
    return out


def _probe_writable(path: str) -> None:
    os.makedirs(path, mode=0o700, exist_ok=True)
    probe = os.path.join(path, f".write-probe-{uuid.uuid4().hex[:8]}")
    with open(probe, "wb") as f:
        f.write(b"ok")
    os.remove(probe)


def resolve_workspace() -> WorkspaceInfo:
    errors: List[str] = []
    for source, path in _candidates():
        path = os.path.abspath(path)
        if is_inside_app_bundle(path):
            errors.append(f"{source}: rechazado, está dentro de un paquete .app")
            continue
        try:
            _probe_writable(path)
            return WorkspaceInfo(ok=True, root=path, source=source, errors=errors)
        except OSError as e:
            errors.append(f"{source}: {e.strerror or type(e).__name__}")
    return WorkspaceInfo(ok=False, root=None, source=None, errors=errors)


def new_instance_id() -> str:
    return f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def purge_dead_instances(workspace_root: str, current_instance: str, min_age_s: float = 60.0) -> List[str]:
    """Elimina carpetas de instancias cuyo proceso ya no existe. Devuelve las eliminadas."""
    removed: List[str] = []
    instances = os.path.join(workspace_root, "instances")
    if not os.path.isdir(instances):
        return removed
    now = time.time()
    for name in os.listdir(instances):
        if name == current_instance:
            continue
        path = os.path.join(instances, name)
        if not os.path.isdir(path) or os.path.islink(path):
            continue
        try:
            pid = int(name.split("-", 1)[0])
        except ValueError:
            continue
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            continue
        if _pid_alive(pid) or age < min_age_s:
            continue
        real = os.path.realpath(path)
        if not real.startswith(os.path.realpath(instances) + os.sep):
            continue
        shutil.rmtree(real, ignore_errors=True)
        removed.append(name)
    return removed


def remove_tree_within(path: str, root: str) -> bool:
    """Borra path solo si resuelve estrictamente dentro de root."""
    real, real_root = os.path.realpath(path), os.path.realpath(root)
    if real == real_root or not real.startswith(real_root + os.sep):
        return False
    shutil.rmtree(real, ignore_errors=True)
    return True
