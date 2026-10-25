"""Indexa imágenes y muestras de video con SigLIP; no copia medios ni pesos."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image, ImageOps

from modelo import MODEL_ID, ModeloVisual, sha256_archivo

IMAGENES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
VIDEOS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
VERSION = 1


def dhash(imagen: Image.Image) -> str:
    gris = imagen.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixeles = np.asarray(gris, dtype=np.uint8)
    bits = pixeles[:, :-1] > pixeles[:, 1:]
    valor = 0
    for bit in bits.flat:
        valor = (valor << 1) | int(bit)
    return f"{valor:016x}"


def sha_visual(imagen: Image.Image) -> str:
    rgb = imagen.convert("RGB")
    digest = hashlib.sha256()
    digest.update(rgb.width.to_bytes(4, "big"))
    digest.update(rgb.height.to_bytes(4, "big"))
    digest.update(rgb.tobytes())
    return digest.hexdigest()


def _fotogramas(path: Path, cada_segundos: float, max_fotogramas: int) -> Iterator[tuple[Image.Image, int, float]]:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Hay videos; instala opencv-python-headless para indexar fotogramas") from exc
    captura = cv2.VideoCapture(str(path))
    try:
        if not captura.isOpened():
            raise RuntimeError(f"No se pudo abrir video: {path}")
        fps = float(captura.get(cv2.CAP_PROP_FPS))
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
        if not np.isfinite(fps) or fps <= 0 or total <= 0:
            raise RuntimeError(f"FPS o duración inválidos en video: {path}")
        paso = max(1, round(fps * cada_segundos))
        for numero in range(0, total, paso):
            if numero // paso >= max_fotogramas:
                break
            captura.set(cv2.CAP_PROP_POS_FRAMES, numero)
            ok, bgr = captura.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            yield Image.fromarray(rgb), numero, numero / fps
    finally:
        captura.release()


def _entradas(raiz: Path, cada_segundos: float, max_fotogramas: int):
    for path in sorted(raiz.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        sufijo = path.suffix.lower()
        if sufijo not in IMAGENES | VIDEOS:
            continue
        sha_archivo = sha256_archivo(path)
        relativo = path.relative_to(raiz).as_posix()
        if sufijo in IMAGENES:
            with Image.open(path) as original:
                imagen = ImageOps.exif_transpose(original).convert("RGB")
            metadata = {
                "id": sha_archivo,
                "ruta": relativo,
                "tipo": "imagen",
                "sha256_archivo": sha_archivo,
                "sha256_visual": sha_visual(imagen),
                "dhash": dhash(imagen),
            }
            yield imagen, metadata
        else:
            for imagen, numero, segundo in _fotogramas(path, cada_segundos, max_fotogramas):
                visual = sha_visual(imagen)
                metadata = {
                    "id": f"{sha_archivo}:{numero}",
                    "ruta": relativo,
                    "tipo": "fotograma",
                    "sha256_archivo": sha_archivo,
                    "sha256_visual": visual,
                    "dhash": dhash(imagen),
                    "fotograma": numero,
                    "segundo": round(segundo, 3),
                }
                yield imagen, metadata


def construir_indice(
    raiz: Path,
    destino: Path,
    modelo: ModeloVisual,
    lote: int = 2,
    cada_segundos: float = 5,
    max_fotogramas: int = 24,
) -> dict:
    raiz = raiz.expanduser().resolve()
    destino = destino.expanduser().resolve()
    if not raiz.is_dir():
        raise ValueError(f"No existe la carpeta de imágenes: {raiz}")
    if lote < 1 or lote > 8 or cada_segundos <= 0 or max_fotogramas < 1:
        raise ValueError("lote 1–8, cada_segundos > 0 y max_fotogramas >= 1")
    destino.mkdir(parents=True, exist_ok=True)
    vectores: list[np.ndarray] = []
    items: list[dict] = []
    pendientes: list[Image.Image] = []
    metas: list[dict] = []

    def vaciar() -> None:
        if not pendientes:
            return
        nuevos = modelo.codificar(pendientes, lote=lote)
        if nuevos.shape[0] != len(pendientes) or nuevos.ndim != 2:
            raise RuntimeError("El modelo devolvió un número inválido de vectores")
        for vector, meta in zip(nuevos, metas):
            meta["fila"] = len(vectores)
            items.append(meta)
            vectores.append(np.asarray(vector, dtype=np.float32))
        for imagen in pendientes:
            imagen.close()
        pendientes.clear()
        metas.clear()

    try:
        for imagen, meta in _entradas(raiz, cada_segundos, max_fotogramas):
            pendientes.append(imagen)
            metas.append(meta)
            if len(pendientes) >= lote:
                vaciar()
        vaciar()
    finally:
        for imagen in pendientes:
            imagen.close()
    if not vectores:
        raise ValueError("No se encontraron imágenes ni fotogramas indexables")
    matriz = np.stack(vectores).astype(np.float32, copy=False)
    normas = np.linalg.norm(matriz, axis=1)
    if not np.all(np.isfinite(matriz)) or np.any(normas < 1e-8):
        raise RuntimeError("Embeddings inválidos")
    matriz /= normas[:, None]
    documento = {
        "version": VERSION,
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "raiz": str(raiz),
        "modelo": MODEL_ID,
        "sha256_pesos": modelo.pesos_sha256,
        "dimensiones": int(matriz.shape[1]),
        "vectores": "vectores.npz",
        "items": items,
    }
    temporal_npz = destino / "vectores.npz.tmp"
    temporal_json = destino / "indice.json.tmp"
    try:
        with temporal_npz.open("wb") as handle:
            np.savez_compressed(
                handle,
                vectores=matriz,
                ids=np.asarray([item["id"] for item in items]),
                sha256_archivos=np.asarray([item["sha256_archivo"] for item in items]),
            )
            handle.flush()
            os.fsync(handle.fileno())
        with temporal_json.open("w", encoding="utf-8") as handle:
            json.dump(documento, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporal_npz.replace(destino / "vectores.npz")
        temporal_json.replace(destino / "indice.json")
    finally:
        temporal_npz.unlink(missing_ok=True)
        temporal_json.unlink(missing_ok=True)
    return documento


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--salida", type=Path, default=Path(__file__).parent / "salidas")
    parser.add_argument("--dispositivo", choices=["cpu", "mps"], default="cpu")
    parser.add_argument("--lote", type=int, default=2)
    parser.add_argument("--cada-segundos", type=float, default=5)
    parser.add_argument("--max-fotogramas", type=int, default=24)
    args = parser.parse_args()
    modelo = ModeloVisual(args.dispositivo)
    documento = construir_indice(
        args.carpeta, args.salida, modelo, args.lote, args.cada_segundos, args.max_fotogramas
    )
    print(json.dumps({"salida": str(args.salida.resolve()), "elementos": len(documento["items"])}))


if __name__ == "__main__":
    main()
