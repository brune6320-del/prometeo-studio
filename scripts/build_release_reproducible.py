#!/usr/bin/env python3
"""PROMETEO Studio · pipeline de release (CLAUDE-REMEDIATION-001 · PA-008, PA-009, PA-019)
──────────────────────────────────────────────────────────────────────────────────────
Pasos (cada uno falla en voz alta; nada se da por bueno sin comprobarlo):

  1. Procedencia Git real: HEAD, rama y lista de archivos modificados (nunca una constante).
  2. Frontend: tsc + vite build.
  3. Host Tauri: cargo build --release --offline (incrusta el frontend compilado).
  4. Ensamblado del .app desde cero: Info.plist generado desde tauri.conf.json, runtime
     Python y OCR desde studio-desktop/resources, código de la app copiado desde el repo
     con exclusiones (sin pruebas, experimentos, salidas de desarrollo ni cachés).
  5. Firma ad-hoc de dentro hacia fuera: cada Mach-O interno y después el paquete.
     Cualquier fallo de codesign aborta el build.
  6. Verificación: codesign --verify --deep --strict (obligatoria) y spctl (registrada).
  7. DMG con acceso directo a Aplicaciones y nota de instalación.
  8. Comprobación del DMG montado en solo lectura (firma del .app que se distribuye).
  9. PROMETEO_RELEASE_PROVENANCE.json con hashes de entradas y artefactos.

No hay notarización (requiere cuenta de desarrollador de Apple): se declara NOT_PERFORMED.
"""
from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "studio", "frontend")
SRC_TAURI = os.path.join(REPO_ROOT, "studio-desktop", "src-tauri")
VENDOR_RESOURCES = os.path.join(REPO_ROOT, "studio-desktop", "resources")
BUNDLE_ROOT = os.path.join(SRC_TAURI, "target", "release", "bundle")
PROVENANCE_PATH = os.path.join(REPO_ROOT, "PROMETEO_RELEASE_PROVENANCE.json")

with open(os.path.join(SRC_TAURI, "tauri.conf.json"), encoding="utf-8") as _f:
    TAURI_CONF = json.load(_f)
PRODUCT = TAURI_CONF["productName"]                   # "PROMETEO Studio"
BUNDLE_VERSION = TAURI_CONF["version"]                # "0.2.0"
IDENTIFIER = TAURI_CONF["identifier"]
EXECUTABLE = "prometeo-studio"

sys.path.insert(0, os.path.join(REPO_ROOT, "studio", "backend"))
from version import PROMETEO_VERSION  # noqa: E402  (versión de producto, p. ej. 0.2.0-rc1)

APP_PATH = os.path.join(BUNDLE_ROOT, "macos", f"{PRODUCT}.app")
DMG_NAME = f"PROMETEO-Studio-{PROMETEO_VERSION}-arm64.dmg"
DMG_PATH = os.path.join(BUNDLE_ROOT, "dmg", DMG_NAME)

GIT_ENV = dict(os.environ, GIT_CONFIG_COUNT="2",
               GIT_CONFIG_KEY_0="core.trustctime", GIT_CONFIG_VALUE_0="false",
               GIT_CONFIG_KEY_1="core.checkStat", GIT_CONFIG_VALUE_1="minimal",
               GIT_OPTIONAL_LOCKS="0")

STEPS: List[Dict[str, object]] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: List[str], cwd: Optional[str] = None, env=None, check: bool = True, timeout: int = 1800) -> subprocess.CompletedProcess:
    log("-> " + " ".join(cmd))
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if check and res.returncode != 0:
        raise RuntimeError(f"Falló ({res.returncode}): {' '.join(cmd)}\n{res.stdout[-2000:]}\n{res.stderr[-4000:]}")
    return res


def step(name: str):
    def deco(fn):
        def wrapper(*a, **kw):
            log(f"\n=== {name} ===")
            t0 = time.time()
            out = fn(*a, **kw)
            STEPS.append({"step": name, "status": "OK", "seconds": round(time.time() - t0, 1)})
            return out
        return wrapper
    return deco


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(root: str, patterns=("*",), exclude=()) -> str:
    """Hash estable de un árbol de archivos (ruta relativa + contenido)."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not any(fnmatch.fnmatch(d, e) for e in exclude))
        for name in sorted(filenames):
            if not any(fnmatch.fnmatch(name, p) for p in patterns) or any(fnmatch.fnmatch(name, e) for e in exclude):
                continue
            full = os.path.join(dirpath, name)
            h.update(os.path.relpath(full, root).encode())
            h.update(sha256_file(full).encode())
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────

@step("1. Procedencia Git")
def preflight(require_clean: bool) -> Dict[str, object]:
    head = run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, env=GIT_ENV).stdout.strip()
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, env=GIT_ENV).stdout.strip()
    status = run(["git", "status", "--porcelain=v1", "-unormal"], cwd=REPO_ROOT, env=GIT_ENV, timeout=300).stdout
    dirty = [line for line in status.splitlines() if line.strip()]
    log(f"HEAD {head} ({branch}); archivos modificados o sin seguimiento: {len(dirty)}")
    if dirty and require_clean:
        raise RuntimeError("El árbol de trabajo no está limpio:\n" + "\n".join(dirty[:50]))
    return {"head": head, "branch": branch, "clean_working_tree": not dirty, "dirty_entries": dirty}


@step("2. Frontend (tsc + vite)")
def build_frontend() -> Dict[str, str]:
    run(["npm", "run", "build"], cwd=FRONTEND_DIR, timeout=900)
    dist = os.path.join(FRONTEND_DIR, "dist")
    return {"dist_tree_sha256": tree_digest(dist, exclude=("*.tar.gz",)),
            "index_html_sha256": sha256_file(os.path.join(dist, "index.html"))}


@step("3. Host Tauri (cargo --release --offline)")
def build_host() -> str:
    run(["cargo", "build", "--release", "--offline"], cwd=SRC_TAURI, timeout=3600)
    binary = os.path.join(SRC_TAURI, "target", "release", "app")
    if not os.path.isfile(binary):
        raise RuntimeError("No se encontró el binario compilado")
    return binary


def _copy_tree(src: str, dst: str, exclude_dirs=(), exclude_files=()) -> None:
    def ignore(d, names):
        out = []
        for n in names:
            full = os.path.join(d, n)
            if os.path.isdir(full) and any(fnmatch.fnmatch(n, p) for p in exclude_dirs):
                out.append(n)
            elif os.path.isfile(full) and any(fnmatch.fnmatch(n, p) for p in exclude_files):
                out.append(n)
        return out
    shutil.copytree(src, dst, ignore=ignore, symlinks=True)


@step("4. Ensamblado del .app")
def assemble(binary: str) -> None:
    if os.path.exists(APP_PATH):
        shutil.rmtree(APP_PATH)
    contents = os.path.join(APP_PATH, "Contents")
    macos = os.path.join(contents, "MacOS")
    res = os.path.join(contents, "Resources")
    os.makedirs(macos)
    os.makedirs(res)

    shutil.copy2(binary, os.path.join(macos, EXECUTABLE))
    os.chmod(os.path.join(macos, EXECUTABLE), 0o755)
    shutil.copy2(os.path.join(SRC_TAURI, "icons", "icon.icns"), os.path.join(res, "icon.icns"))

    info = {
        "CFBundleDevelopmentRegion": "es",
        "CFBundleDisplayName": PRODUCT,
        "CFBundleName": PRODUCT,
        "CFBundleExecutable": EXECUTABLE,
        "CFBundleIdentifier": IDENTIFIER,
        "CFBundleIconFile": "icon.icns",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": BUNDLE_VERSION,
        "CFBundleVersion": PROMETEO_VERSION,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        # App Nap frenaba el árbol de procesos de la app (incluido el motor Python) cuando la
        # ventana no estaba en primer plano: 8–20 s de arranque frente a 0,7–2,7 s sin la app.
        "NSAppSleepDisabled": True,
        "NSHumanReadableCopyright": TAURI_CONF.get("bundle", {}).get("copyright", "PROMETEO"),
        "NSDownloadsFolderUsageDescription": "PROMETEO guarda en Descargas › PROMETEO las copias verificadas que tú decides guardar.",
    }
    with open(os.path.join(contents, "Info.plist"), "wb") as f:
        plistlib.dump(info, f)

    # Runtime Python y OCR: proveedor ya ensamblado en studio-desktop/resources.
    _copy_tree(os.path.join(VENDOR_RESOURCES, "runtime"), os.path.join(res, "runtime"),
               exclude_dirs=("__pycache__", "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip"),
               exclude_files=("*.pyc",))
    _copy_tree(os.path.join(VENDOR_RESOURCES, "ocr"), os.path.join(res, "ocr"))

    # Código de la aplicación: siempre desde el repositorio, nunca copias viejas.
    os.makedirs(os.path.join(res, "fase0", "assets"))
    for name in os.listdir(os.path.join(REPO_ROOT, "fase0")):
        src = os.path.join(REPO_ROOT, "fase0", name)
        if os.path.isfile(src) and (name.endswith(".py") or name.endswith(".json")):
            if fnmatch.fnmatch(name, "test_*") or name in ("conftest.py", "benchmark_raster.py", "make_fixtures.py",
                                                           "fixtures_raster.py", "demo.py", "gate_reality.py"):
                continue
            shutil.copy2(src, os.path.join(res, "fase0", name))
    for sample in ("case_a.pdf", "case_b_scan.pdf"):
        shutil.copy2(os.path.join(REPO_ROOT, "fase0", "assets", sample), os.path.join(res, "fase0", "assets", sample))
    common_dirs = ("__pycache__", "tests")
    common_files = ("*.pyc", ".DS_Store")
    _copy_tree(os.path.join(REPO_ROOT, "docgraph"), os.path.join(res, "docgraph"), common_dirs, common_files)
    _copy_tree(os.path.join(REPO_ROOT, "agents"), os.path.join(res, "agents"), common_dirs, common_files)
    os.makedirs(os.path.join(res, "studio"))
    _copy_tree(os.path.join(REPO_ROOT, "studio", "backend"), os.path.join(res, "studio", "backend"), common_dirs, common_files)
    with open(os.path.join(res, "studio", "__init__.py"), "w") as f:
        f.write("")
    _copy_tree(os.path.join(FRONTEND_DIR, "dist"), os.path.join(res, "studio", "frontend", "dist"),
               exclude_files=("*.tar.gz",))
    # Avisos de licencias de terceros dentro del paquete (CAMP-002). Los textos completos de
    # cada licencia no están en el runtime embebido: se declara en el propio README.
    lic = os.path.join(res, "licenses")
    os.makedirs(lic, exist_ok=True)
    shutil.copy2(os.path.join(REPO_ROOT, "THIRD_PARTY_NOTICES.md"), os.path.join(lic, "THIRD_PARTY_NOTICES.md"))
    with open(os.path.join(lic, "README.txt"), "w", encoding="utf-8") as f:
        f.write("PROMETEO Studio incluye software de terceros. THIRD_PARTY_NOTICES.md enumera cada componente,\n"
                "su licencia y sus avisos. Los textos completos de las licencias (p. ej. AGPLv3 de PyMuPDF/MuPDF,\n"
                "Apache-2.0 de Tesseract, PSF de Python) deben añadirse antes de cualquier distribución a terceros.\n"
                "Estado de distribución: DISTRIBUTION_BLOCKED_PENDING_LICENSE.\n")
    run(["xattr", "-cr", APP_PATH])


@step("4b. Bytecode precompilado")
def precompile() -> None:
    """Sin __pycache__, Python recompila todo en cada arranque (el motor tardaba ~6 s más).
    El paquete es inmutable y firmado: se usa invalidación por hash sin comprobación."""
    res = os.path.join(APP_PATH, "Contents", "Resources")
    py = os.path.join(res, "runtime", "bin", "python3")
    for sub in ("runtime/lib/python3.11", "fase0", "docgraph", "agents", "studio"):
        run([py, "-m", "compileall", "-q", "-j", "0", "--invalidation-mode", "unchecked-hash",
             os.path.join(res, sub)], timeout=900, check=False)
    missing = run([py, "-c", "import importlib.util,sys; sys.exit(0)"], check=False)
    if missing.returncode != 0:
        raise RuntimeError("El runtime empaquetado no arranca tras precompilar")


def _is_macho(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
    except OSError:
        return False
    return magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf", b"\xbe\xba\xfe\xca")


@step("5. Firma ad-hoc de dentro hacia fuera")
def sign() -> Dict[str, object]:
    main_exe = os.path.join(APP_PATH, "Contents", "MacOS", EXECUTABLE)
    nested: List[str] = []
    for dirpath, _, filenames in os.walk(os.path.join(APP_PATH, "Contents")):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if full != main_exe and not os.path.islink(full) and _is_macho(full):
                nested.append(full)
    # Los más profundos primero.
    nested.sort(key=lambda p: p.count(os.sep), reverse=True)
    # Atributos extendidos fuera: codesign rechaza com.apple.FinderInfo («detritus»), y el
    # proveedor de archivos de iCloud los pone en la raíz del paquete cuando target/ vive en una
    # carpeta sincronizada (CAMP-002, lección L-04).
    run(["xattr", "-cr", APP_PATH])
    for path in nested:
        run(["codesign", "--force", "--sign", "-", "--timestamp=none", path])
    run(["xattr", "-cr", APP_PATH])
    run(["codesign", "--force", "--sign", "-", "--timestamp=none", APP_PATH])
    return {"identity": "ad-hoc (-)", "nested_macho_signed": len(nested), "hardened_runtime": False}


@step("6. Verificación de firma")
def verify_signature(app_path: str) -> Dict[str, object]:
    strict = run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app_path], check=False)
    if strict.returncode != 0:
        raise RuntimeError("codesign --verify --strict falló:\n" + strict.stderr)
    spctl = run(["spctl", "--assess", "--type", "execute", "--verbose=2", app_path], check=False)
    return {
        "codesign_verify_deep_strict": "PASS",
        "codesign_output": strict.stderr.strip().splitlines()[-2:],
        "gatekeeper_spctl_assess": "ACCEPTED" if spctl.returncode == 0 else "REJECTED",
        "gatekeeper_output": (spctl.stderr or spctl.stdout).strip().splitlines()[-2:],
        "notarization": "NOT_PERFORMED (requiere cuenta Apple Developer)",
    }


@step("7. DMG")
def build_dmg() -> None:
    os.makedirs(os.path.dirname(DMG_PATH), exist_ok=True)
    if os.path.exists(DMG_PATH):
        os.remove(DMG_PATH)
    staging = tempfile.mkdtemp(prefix="prometeo_dmg_")
    try:
        staged_app = os.path.join(staging, f"{PRODUCT}.app")
        # Sin atributos extendidos: iCloud vuelve a poner com.apple.FinderInfo en la raíz del
        # paquete (target/ está en una carpeta sincronizada) y codesign lo rechaza dentro del DMG.
        run(["ditto", "--noextattr", "--noqtn", "--norsrc", APP_PATH, staged_app])
        run(["xattr", "-cr", staged_app])
        run(["codesign", "--verify", "--deep", "--strict", staged_app])
        os.symlink("/Applications", os.path.join(staging, "Aplicaciones"))
        shutil.copy2(os.path.join(REPO_ROOT, "THIRD_PARTY_NOTICES.md"), os.path.join(staging, "Avisos de licencias de terceros.md"))
        with open(os.path.join(staging, "Cómo instalar.txt"), "w", encoding="utf-8") as f:
            f.write("Arrastra «PROMETEO Studio» a la carpeta «Aplicaciones».\n"
                    "Después ábrelo desde Aplicaciones. También funciona abierto desde este disco.\n"
                    "La primera vez macOS puede pedir confirmación porque la app no está notarizada:\n"
                    "Ajustes del Sistema › Privacidad y seguridad › «Abrir igualmente».\n")
        run(["hdiutil", "create", "-volname", f"PROMETEO Studio {PROMETEO_VERSION}", "-srcfolder", staging,
             "-ov", "-format", "UDZO", DMG_PATH], timeout=1800)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


@step("8. Comprobación del DMG en solo lectura")
def check_dmg() -> Dict[str, object]:
    mount = tempfile.mkdtemp(prefix="prometeo_dmgcheck_")
    run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, DMG_PATH])
    try:
        app = os.path.join(mount, f"{PRODUCT}.app")
        strict = run(["codesign", "--verify", "--deep", "--strict", app], check=False)
        listing = sorted(os.listdir(mount))
        exe_sha = sha256_file(os.path.join(app, "Contents", "MacOS", EXECUTABLE))
        return {"mounted_read_only": True, "codesign_verify_inside_dmg": "PASS" if strict.returncode == 0 else "FAIL",
                "volume_listing": listing, "executable_sha256_inside_dmg": exe_sha}
    finally:
        run(["hdiutil", "detach", mount], check=False)


def toolchain() -> Dict[str, str]:
    def first(cmd):
        r = run(cmd, check=False)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "unavailable"
    runtime_py = os.path.join(VENDOR_RESOURCES, "runtime", "bin", "python3")
    return {
        "rustc": first(["rustc", "--version"]),
        "cargo": first(["cargo", "--version"]),
        "node": first(["node", "--version"]),
        "npm": first(["npm", "--version"]),
        "bundled_python": first([runtime_py, "--version"]),
        "bundled_tesseract": first([os.path.join(VENDOR_RESOURCES, "ocr", "bin", "tesseract"), "--version"]),
        "macos": first(["sw_vers", "-productVersion"]),
    }


def main() -> None:
    require_clean = "--require-clean" in sys.argv
    t0 = time.time()
    git = preflight(require_clean)
    frontend = build_frontend()
    binary = build_host()
    assemble(binary)
    precompile()
    signing = sign()
    verification = verify_signature(APP_PATH)
    build_dmg()
    dmg_check = check_dmg()
    if dmg_check["codesign_verify_inside_dmg"] != "PASS":
        raise RuntimeError("La firma del .app dentro del DMG no verifica")

    app_exe = os.path.join(APP_PATH, "Contents", "MacOS", EXECUTABLE)
    manifest = {
        "manifest_version": "2.0.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generator": "scripts/build_release_reproducible.py (CLAUDE-REMEDIATION-001)",
        "product": PRODUCT,
        "version": PROMETEO_VERSION,
        "bundle_version": BUNDLE_VERSION,
        "identifier": IDENTIFIER,
        "git_provenance": git,
        "toolchain": toolchain(),
        "inputs": {
            "Cargo.lock_sha256": sha256_file(os.path.join(SRC_TAURI, "Cargo.lock")),
            "package-lock.json_sha256": sha256_file(os.path.join(FRONTEND_DIR, "package-lock.json")),
            "tauri.conf.json_sha256": sha256_file(os.path.join(SRC_TAURI, "tauri.conf.json")),
            "backend_tree_sha256": tree_digest(os.path.join(REPO_ROOT, "studio", "backend"), ("*.py",), ("__pycache__", "tests")),
            "fase0_runtime_py_sha256": tree_digest(os.path.join(REPO_ROOT, "fase0"), ("*.py", "*.json"),
                                                   ("__pycache__", "experiments", "colab", "scratch", "reality_corpus",
                                                    "autonomous", "failure_corpus", "assets", "test_*")),
            "docgraph_tree_sha256": tree_digest(os.path.join(REPO_ROOT, "docgraph"), ("*.py",), ("__pycache__",)),
            "frontend": frontend,
            "vendor_runtime_tree_sha256": tree_digest(os.path.join(VENDOR_RESOURCES, "runtime"), exclude=("__pycache__", "*.pyc")),
        },
        "artifacts": {
            "app_path": os.path.relpath(APP_PATH, REPO_ROOT),
            "executable_sha256": sha256_file(app_exe),
            "executable_size_bytes": os.path.getsize(app_exe),
            "info_plist_sha256": sha256_file(os.path.join(APP_PATH, "Contents", "Info.plist")),
            "dmg_path": os.path.relpath(DMG_PATH, REPO_ROOT),
            "dmg_sha256": sha256_file(DMG_PATH),
            "dmg_size_bytes": os.path.getsize(DMG_PATH),
        },
        "signing": signing,
        "verification": verification,
        "dmg_read_only_check": dmg_check,
        "steps": STEPS,
        "total_seconds": round(time.time() - t0, 1),
        "verdict": "BUILD_AND_SIGNATURE_VERIFIED" if git["clean_working_tree"] else "BUILD_AND_SIGNATURE_VERIFIED_FROM_DIRTY_TREE",
        "not_claimed": ["notarization", "gatekeeper acceptance on other Macs", "human acceptance"],
    }
    with open(PROVENANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log(f"\nDMG: {DMG_PATH}\nSHA256: {manifest['artifacts']['dmg_sha256']}\nVeredicto: {manifest['verdict']}")


if __name__ == "__main__":
    main()
