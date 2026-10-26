"""Exporta un manifiesto de datos con holdout estable; no entrena ni copia imágenes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
from pathlib import Path

from buscar import cargar_indice
from modelo import sha256_archivo


def split_sha(sha: str, porcentaje: int, sal: str) -> str:
    if len(sha) != 64 or any(x not in "0123456789abcdef" for x in sha):
        raise ValueError("SHA-256 inválido")
    if not 1 <= porcentaje <= 50:
        raise ValueError("El holdout debe ser 1–50 %")
    digest = hashlib.sha256(f"{sal}:{sha}".encode("utf-8")).digest()
    return "holdout" if int.from_bytes(digest[:8], "big") % 10000 < porcentaje * 100 else "train"


def _voto(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    limpio = valor.strip().lower()
    if limpio in {"♥", "like", "me gusta"}:
        return "♥"
    if limpio in {"✕", "x", "nope", "no"}:
        return "✕"
    return None


def leer_gustos(path: Path | None) -> tuple[dict[str, tuple[str, float | None]], str | None]:
    if path is None:
        return {}, None
    with path.open(encoding="utf-8") as handle:
        datos = json.load(handle)
    etiquetas: dict[str, tuple[str, float | None]] = {}
    if isinstance(datos, dict):
        # Formato real de Studio: gustos.referentes = {id: peso acumulado}.
        referentes = datos.get("referentes", {})
        if isinstance(referentes, dict):
            for clave, peso in referentes.items():
                if (isinstance(clave, str) and isinstance(peso, (int, float))
                        and not isinstance(peso, bool) and math.isfinite(peso)):
                    if peso > 1:
                        etiquetas[clave] = ("♥", float(peso))
                    elif peso < 1:
                        etiquetas[clave] = ("✕", float(peso))
        items = datos.get("items", [])
    elif isinstance(datos, list):
        items = datos
    else:
        raise ValueError("Formato de gustos.json no admitido")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            clave = next((item[k] for k in ("sha256_archivo", "sha256", "id", "ruta", "referente")
                          if isinstance(item.get(k), str) and item[k]), None)
            voto = _voto(item.get("voto", item.get("gusto")))
            if clave and voto:
                if clave in etiquetas and etiquetas[clave][0] != voto:
                    raise ValueError(f"Votos contradictorios para {clave}")
                etiquetas[clave] = (voto, None)
    return etiquetas, sha256_archivo(path)


def _escribir_atomico(path: Path, contenido: str) -> None:
    temporal = path.with_name(path.name + ".tmp")
    try:
        with temporal.open("w", encoding="utf-8") as handle:
            handle.write(contenido)
            handle.flush()
            os.fsync(handle.fileno())
        temporal.replace(path)
    finally:
        temporal.unlink(missing_ok=True)


def origenes_indice(indice: dict, manifiesto: Path | None = None) -> dict[str, str]:
    """Linaje por hashes; piezas.json del recortador o mapa explícito para otros derivados."""
    enlaces = {}
    def agregar(hijo, padre):
        split_sha(hijo, 20, "validar")
        split_sha(padre, 20, "validar")
        if hijo in enlaces and enlaces[hijo] != padre:
            raise ValueError(f"Procedencia contradictoria: {hijo}")
        enlaces[hijo] = padre
    if manifiesto:
        for hijo, padre in json.loads(manifiesto.read_text()).items():
            agregar(hijo, padre)
    for raiz in indice.get("raices", {"carpeta": indice["raiz"]}).values():
        for path in sorted(Path(raiz).rglob("piezas.json")):
            datos = json.loads(path.read_text())
            for pieza in datos.get("piezas", []):
                agregar(pieza["sha256_png"], pieza["sha256_imagen_origen"])
    for item in indice["items"]:
        if item.get("sha256_origen"):
            agregar(item["sha256_archivo"], item["sha256_origen"])
    resultado = {}
    for item in indice["items"]:
        sha = item["sha256_archivo"]
        if item.get("origen") == "recortador" and sha not in enlaces:
            raise ValueError(f"Recorte sin procedencia: {item['ruta']}; aporta piezas.json o --origenes")
        actual, vistos = sha, set()
        while actual in enlaces and enlaces[actual] != actual:
            if actual in vistos:
                raise ValueError("Ciclo en la procedencia")
            vistos.add(actual)
            actual = enlaces[actual]
        resultado[sha] = actual
    return resultado


def exportar(indice_dir: Path, salida: Path, gustos: Path | None = None,
            porcentaje: int = 20, sal: str = "prometeo-indice-v1", origenes: Path | None = None) -> dict:
    indice_dir = indice_dir.expanduser().resolve()
    salida = salida.expanduser().resolve()
    _, indice = cargar_indice(indice_dir)
    linaje = origenes_indice(indice, origenes)
    if gustos is None:
        for candidato in (Path(indice["raiz"]) / "gustos.json", indice_dir / "gustos.json",
                          Path(__file__).resolve().parents[2] / "gustos.json"):
            if candidato.is_file():
                gustos = candidato
                break
    if gustos is not None:
        gustos = gustos.expanduser().resolve()
        if not gustos.is_file():
            raise FileNotFoundError(gustos)
    etiquetas, sha_gustos = leer_gustos(gustos)
    protegidos = {indice_dir / "indice.json", indice_dir / "vectores.npz"}
    if gustos is not None:
        protegidos.add(gustos)
    if origenes is not None:
        protegidos.add(origenes.resolve())
    nombres = {"holdout.json", "train.jsonl", "holdout.jsonl", "sin_etiqueta.jsonl", "manifest.json"}
    if any((salida / nombre).resolve() in protegidos for nombre in nombres):
        raise ValueError("La salida sobrescribiría una entrada de solo lectura")
    salida.mkdir(parents=True, exist_ok=True)
    congelado_path = salida / "holdout.json"
    if congelado_path.exists():
        congelado = json.loads(congelado_path.read_text(encoding="utf-8"))
        if congelado.get("version") != 2 or congelado.get("porcentaje") != porcentaje or congelado.get("sal") != sal:
            raise ValueError("El holdout existente usa otra política; no se puede reasignar")
        for hijo, padre in congelado.get("linaje", {}).items():
            if hijo in linaje and linaje[hijo] != padre:
                raise ValueError("El origen de un archivo congelado cambió")
        linaje = {**congelado.get("linaje", {}), **linaje}
        asignaciones = congelado.get("asignaciones", {})
        if not isinstance(asignaciones, dict):
            raise ValueError("holdout.json inválido")
        for sha, split in asignaciones.items():
            if split != split_sha(sha, porcentaje, sal):
                raise ValueError(f"Asignación congelada inconsistente para {sha}")
    else:
        asignaciones = {}
    usados = set()
    colecciones: dict[str, list[dict]] = {"train": [], "holdout": [], "sin_etiqueta": []}
    for item in indice["items"]:
        sha = item["sha256_archivo"]
        sha_origen = linaje[sha]
        calculado = split_sha(sha_origen, porcentaje, sal)
        split = asignaciones.setdefault(sha_origen, calculado)
        if split != calculado:
            raise ValueError(f"Asignación congelada inconsistente para {sha}")
        coincidencias = [(clave, etiquetas[clave]) for clave in (sha, sha_origen, item["id"], item["ruta"])
                         if clave in etiquetas]
        if len({valor[0] for _, valor in coincidencias}) > 1:
            raise ValueError(f"Etiquetas contradictorias para {item['ruta']}")
        for clave, _ in coincidencias:
            usados.add(clave)
        etiqueta, peso = coincidencias[0][1] if coincidencias else (None, None)
        registro = {
            "id": item["id"],
            "sha256_archivo": sha,
            "sha256_origen": sha_origen,
            "sha256_visual": item["sha256_visual"],
            "ruta": item["ruta"],
            "ruta_fuente": item.get("ruta_fuente", item["ruta"]),
            "origen": item.get("origen", "carpeta"),
            "tipo": item["tipo"],
            "fotograma": item.get("fotograma"),
            "pagina": item.get("pagina"),
            "split": split,
            "etiqueta": etiqueta,
            "peso_gusto": peso,
        }
        colecciones[split if etiqueta else "sin_etiqueta"].append(registro)
    congelado = {"version": 2, "clave": "sha256_origen", "porcentaje": porcentaje, "sal": sal,
                  "asignaciones": dict(sorted(asignaciones.items())), "linaje": dict(sorted(linaje.items()))}
    _escribir_atomico(congelado_path, json.dumps(congelado, ensure_ascii=False, indent=2) + "\n")
    hashes_salida = {}
    for nombre, registros in colecciones.items():
        path = salida / f"{nombre}.jsonl"
        _escribir_atomico(path, "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in registros))
        hashes_salida[path.name] = sha256_archivo(path)
    hashes_salida[congelado_path.name] = sha256_archivo(congelado_path)
    manifiesto = {
        "version": 2,
        "indice": str(indice_dir),
        "raiz_medios": indice["raiz"],
        "raices_medios": indice.get("raices", {"carpeta": indice["raiz"]}),
        "sha256_indice_json": sha256_archivo(indice_dir / "indice.json"),
        "sha256_vectores_npz": sha256_archivo(indice_dir / "vectores.npz"),
        "gustos": str(gustos) if gustos else None,
        "sha256_gustos": sha_gustos,
        "politica_holdout": {"porcentaje": porcentaje, "sal": sal, "clave": "sha256_origen"},
        "totales": {k: len(v) for k, v in colecciones.items()},
        "gustos_sin_vincular": sorted(set(etiquetas) - usados),
        "sha256_salidas": hashes_salida,
    }
    _escribir_atomico(salida / "manifest.json", json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n")
    return manifiesto


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indice", type=Path)
    parser.add_argument("--salida", type=Path, default=Path(__file__).parent / "salidas" / "dataset")
    parser.add_argument("--gustos", type=Path, help="Solo lectura; por defecto busca gustos.json junto a medios o índice")
    parser.add_argument("--holdout", type=int, default=20, help="Porcentaje fijo, 1–50")
    parser.add_argument("--sal", default="prometeo-indice-v1")
    parser.add_argument("--origenes", type=Path, help="JSON sha256_derivado -> sha256_fuente original")
    args = parser.parse_args()
    print(json.dumps(exportar(args.indice, args.salida, args.gustos, args.holdout, args.sal, args.origenes),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
