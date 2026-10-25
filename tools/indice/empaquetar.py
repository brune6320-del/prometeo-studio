"""ZIP del propietario: fuentes, evidencias, recuperación, CRC-32 y SHA-256."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import zipfile
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "tools/indice/entrega"
PREFIJO = "tools/indice/"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=RAIZ)


def huellas(datos):
    return {"bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest(),
            "crc32": f"{zlib.crc32(datos) & 0xffffffff:08x}"}


def empaquetar():
    if git("branch", "--show-current").decode().strip() != "studio/indice-visual":
        raise RuntimeError("Empaquetar solo desde studio/indice-visual")
    pendientes = git("status", "--porcelain", "--untracked-files=all", "--", PREFIJO,
                     ":(exclude)tools/indice/entrega").decode()
    if pendientes.strip():
        raise RuntimeError("Primero guarda en un commit las fuentes y evidencias")
    head = git("rev-parse", "HEAD").decode().strip()
    base = git("merge-base", "HEAD", "origin/studio/collage").decode().strip()
    miembros = {}
    for nombre in git("ls-tree", "-r", "--name-only", "HEAD", "--", PREFIJO).decode().splitlines():
        if nombre.startswith(PREFIJO + "entrega/"):
            continue
        if Path(nombre).suffix.lower() in {".npz", ".safetensors", ".pt", ".pth", ".ckpt",
                                          ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".mp4", ".mov"}:
            raise RuntimeError(f"No se permite empaquetar medios ni pesos: {nombre}")
        miembros["FULL/" + nombre] = git("show", f"HEAD:{nombre}")
    commits = git("rev-list", "--reverse", f"{base}..{head}", "--", PREFIJO,
                  ":(exclude)tools/indice/entrega").decode().splitlines()
    for numero, commit in enumerate(commits, 1):
        miembros[f"RECUPERACION/{numero:03}-{commit[:12]}.patch"] = git(
            "format-patch", "--stdout", "-1", commit, "--", PREFIJO,
            ":(exclude)tools/indice/entrega")
    # Recuperar todos los commits de la herramienta en un repositorio temporal.
    # La base original aún no tenía tools/indice.
    if git("ls-tree", "-r", "--name-only", base, "--", PREFIJO).strip():
        raise RuntimeError("La base contiene herramientas; adaptar restauración antes de empaquetar")
    cache = RAIZ / PREFIJO / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temporal:
        recuperado = Path(temporal)
        subprocess.run(["git", "init", "-q", str(recuperado)], check=True)
        parches = []
        for nombre, datos in miembros.items():
            if nombre.endswith(".patch"):
                parche = recuperado / Path(nombre).name
                parche.write_bytes(datos)
                parches.append(str(parche))
        subprocess.run(["git", "-C", str(recuperado), "-c", "user.name=Codex",
                        "-c", "user.email=codex@openai.com", "am", "--quiet", *parches], check=True)
        for nombre, esperado in miembros.items():
            if nombre.startswith("FULL/"):
                assert (recuperado / nombre[5:]).read_bytes() == esperado, nombre
    miembros["RECUPERACION/verificacion.json"] = (json.dumps({
        "git_am_todos_los_parches_ok": True, "fuentes_recuperadas_identicas": True,
        "commits": commits}, indent=2) + "\n").encode()
    instrucciones = (
        f"D-2 | rama studio/indice-visual | fuente {head}\nBase: {base}\n\n"
        "FULL/ contiene exclusivamente tools/indice del commit fuente.\n"
        "RECUPERACION/ conserva cada cambio de esta herramienta en orden.\n"
        "Para recuperar: en un checkout limpio de la base, git am /ruta/RECUPERACION/*.patch.\n"
        "El ZIP maestro corresponde al propietario. No incluye imágenes ni pesos.\n"
        "Instalar requirements.txt en un venv local antes de usar; ver FULL/tools/indice/README.md.\n"
        "MANIFEST.json lista SHA-256 y CRC-32 de cada carga salvo el propio manifiesto.\n"
        "El archivo externo verificacion.json verifica también el manifiesto y el ZIP completo.\n"
    )
    miembros["LEEME.txt"] = instrucciones.encode()
    manifiesto = {"version": 1, "rama": "studio/indice-visual", "commit_fuente": head,
                  "base": base, "miembros": {k: huellas(v) for k, v in sorted(miembros.items())}}
    miembros["MANIFEST.json"] = (json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n").encode()
    SALIDA.mkdir(exist_ok=True)
    destino = SALIDA / "D2-indice-visual-master.zip"
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
        for nombre, datos in sorted(miembros.items()):
            info = zipfile.ZipInfo(nombre, date_time=(2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archivo.writestr(info, datos)
    with zipfile.ZipFile(destino) as archivo:
        assert archivo.testzip() is None, "CRC de un miembro incorrecto"
        assert sorted(archivo.namelist()) == sorted(miembros)
        for nombre, esperado in miembros.items():
            datos = archivo.read(nombre)
            assert huellas(datos) == huellas(esperado), nombre
            assert f"{archivo.getinfo(nombre).CRC:08x}" == huellas(datos)["crc32"], nombre
    resultado = {"zip": destino.name, "commit_fuente": head, "crc_zip_miembros_ok": True,
                 "sha256_todos_miembros_ok": True, **huellas(destino.read_bytes()),
                 "miembros": {k: huellas(v) for k, v in sorted(miembros.items())}}
    (SALIDA / "verificacion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in resultado.items() if k != "miembros"}, indent=2))


if __name__ == "__main__":
    empaquetar()
