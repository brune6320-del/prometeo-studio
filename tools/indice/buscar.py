"""Parecidos, duplicados y grupos sobre un índice visual local."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from indexar import VERSION
from modelo import ModeloVisual


def cargar_indice(carpeta: Path) -> tuple[np.ndarray, dict]:
    carpeta = carpeta.expanduser().resolve()
    with (carpeta / "indice.json").open(encoding="utf-8") as handle:
        indice = json.load(handle)
    if indice.get("version") != VERSION or indice.get("vectores") != "vectores.npz":
        raise ValueError("Versión o archivo de vectores no admitido")
    with np.load(carpeta / "vectores.npz", allow_pickle=False) as datos:
        vectores = datos["vectores"].astype(np.float32, copy=True)
        ids = datos["ids"].tolist()
        hashes = datos["sha256_archivos"].tolist()
    items = indice["items"]
    if (
        vectores.ndim != 2
        or len(items) != len(vectores)
        or not items
        or len(ids) != len(items)
        or len(hashes) != len(items)
        or vectores.shape[1] != indice["dimensiones"]
    ):
        raise ValueError("Índice y matriz no coinciden")
    if any(item["fila"] != i or item["id"] != ids[i] or item["sha256_archivo"] != hashes[i]
           for i, item in enumerate(items)):
        raise ValueError("IDs o SHA-256 no coinciden entre JSON y NPZ")
    if not np.all(np.isfinite(vectores)):
        raise ValueError("Vectores no finitos")
    normas = np.linalg.norm(vectores, axis=1)
    if np.any(normas < 1e-8):
        raise ValueError("Vectores nulos")
    vectores /= normas[:, None]
    return vectores, indice


def parecidos(vectores: np.ndarray, indice: dict, consulta: np.ndarray, n: int = 12,
              excluir_fila: int | None = None) -> list[dict]:
    if n < 1:
        raise ValueError("n debe ser positivo")
    consulta = np.asarray(consulta, dtype=np.float32).reshape(-1)
    if consulta.shape[0] != vectores.shape[1] or not np.all(np.isfinite(consulta)):
        raise ValueError("Consulta de dimensión inválida")
    norma = np.linalg.norm(consulta)
    if norma < 1e-8:
        raise ValueError("Consulta nula")
    similitudes = vectores @ (consulta / norma)
    if excluir_fila is not None:
        similitudes[excluir_fila] = -np.inf
    orden = np.argsort(-similitudes, kind="stable")[:n]
    return [dict(indice["items"][int(i)], similitud=round(float(similitudes[i]), 6))
            for i in orden if np.isfinite(similitudes[i])]


def duplicados(vectores: np.ndarray, indice: dict, distancia_hash: int = 6,
               similitud_minima: float = 0.95, max_pares: int = 1000) -> list[dict]:
    if not 0 <= distancia_hash <= 64 or not -1 <= similitud_minima <= 1 or max_pares < 1:
        raise ValueError("Umbrales de duplicados inválidos")
    items = indice["items"]
    huellas = [int(x["dhash"], 16) for x in items]
    pares = []
    for i, primero in enumerate(items):
        for j in range(i + 1, len(items)):
            segundo = items[j]
            mismo_archivo = (primero["tipo"] == segundo["tipo"] == "imagen"
                             and primero["sha256_archivo"] == segundo["sha256_archivo"])
            mismo_visual = primero["sha256_visual"] == segundo["sha256_visual"]
            distancia = (huellas[i] ^ huellas[j]).bit_count()
            similitud = float(vectores[i] @ vectores[j])
            cercano = distancia <= distancia_hash and similitud >= similitud_minima
            if mismo_archivo or mismo_visual or cercano:
                clase = "mismo_archivo" if mismo_archivo else "mismo_visual" if mismo_visual else "casi_exacto"
                pares.append({
                    "a": {"fila": i, "ruta": primero["ruta"], "fotograma": primero.get("fotograma")},
                    "b": {"fila": j, "ruta": segundo["ruta"], "fotograma": segundo.get("fotograma")},
                    "clase": clase,
                    "distancia_dhash": distancia,
                    "similitud": round(similitud, 6),
                })
                if len(pares) >= max_pares:
                    return pares
    return pares


def grupos(vectores: np.ndarray, indice: dict, k: int | None = None, semilla: int = 42,
           iteraciones: int = 50) -> list[dict]:
    n = len(vectores)
    if n == 0:
        return []
    if k is None:
        k = min(n, max(1, min(24, round((n / 2) ** 0.5))))
    if not 1 <= k <= n or iteraciones < 1:
        raise ValueError("k debe estar entre 1 y el número de elementos")
    rng = np.random.default_rng(semilla)
    elegidos = [int(rng.integers(n))]
    while len(elegidos) < k:
        mayor = (vectores @ vectores[elegidos].T).max(axis=1)
        mayor[elegidos] = np.inf
        elegidos.append(int(np.argmin(mayor)))
    centros = vectores[elegidos].copy()
    anterior = None
    for _ in range(iteraciones):
        asignacion = np.argmax(vectores @ centros.T, axis=1)
        if anterior is not None and np.array_equal(asignacion, anterior):
            break
        anterior = asignacion.copy()
        for grupo in range(k):
            miembros = vectores[asignacion == grupo]
            if len(miembros):
                centro = miembros.mean(axis=0)
                norma = np.linalg.norm(centro)
                centros[grupo] = centro / norma if norma > 1e-8 else miembros[0]
    resultado = []
    for numero in range(k):
        filas = np.flatnonzero(asignacion == numero)
        if not len(filas):
            continue
        representante = int(filas[np.argmax(vectores[filas] @ centros[numero])])
        resultado.append({
            "grupo": numero,
            "representante": {"fila": representante, "ruta": indice["items"][representante]["ruta"]},
            "elementos": [{"fila": int(i), "ruta": indice["items"][int(i)]["ruta"]} for i in filas],
        })
    return sorted(resultado, key=lambda x: (-len(x["elementos"]), x["grupo"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("parecidos", help="Hasta 12 vecinos de una imagen o fila")
    p.add_argument("indice", type=Path)
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--imagen", type=Path)
    origen.add_argument("--fila", type=int)
    p.add_argument("-n", type=int, default=12)
    p.add_argument("--dispositivo", choices=["cpu", "mps"], default="cpu")
    p = sub.add_parser("duplicados", help="Pares exactos o casi exactos")
    p.add_argument("indice", type=Path)
    p.add_argument("--distancia-hash", type=int, default=6)
    p.add_argument("--similitud-minima", type=float, default=0.95)
    p.add_argument("--max-pares", type=int, default=1000)
    p = sub.add_parser("grupos", help="k-means esférico")
    p.add_argument("indice", type=Path)
    p.add_argument("-k", type=int)
    p.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    vectores, indice = cargar_indice(args.indice)
    if args.accion == "parecidos":
        if args.fila is not None:
            if not 0 <= args.fila < len(vectores):
                parser.error("--fila fuera del índice")
            consulta = vectores[args.fila]
            resultado = parecidos(vectores, indice, consulta, args.n, args.fila)
        else:
            modelo = ModeloVisual(args.dispositivo)
            if modelo.pesos_sha256 != indice["sha256_pesos"]:
                raise RuntimeError("El índice fue creado con otros pesos")
            with Image.open(args.imagen) as original:
                imagen = ImageOps.exif_transpose(original).convert("RGB")
            consulta = modelo.codificar([imagen], lote=1)[0]
            resultado = parecidos(vectores, indice, consulta, args.n)
    elif args.accion == "duplicados":
        resultado = duplicados(vectores, indice, args.distancia_hash, args.similitud_minima, args.max_pares)
    else:
        resultado = grupos(vectores, indice, args.k, args.semilla)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
