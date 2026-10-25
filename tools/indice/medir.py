"""Mide recall@1/@5 solo con referentes sintéticos generados en memoria."""

from __future__ import annotations

import argparse
import json

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from modelo import MODEL_ID, ModeloVisual


def crear_pares_sinteticos(n: int = 12, lado: int = 224, semilla: int = 23):
    """Devuelve bases y consultas (imagen, positivo, transformación)."""
    if n < 6 or lado < 96:
        raise ValueError("Se requieren al menos 6 imágenes de 96 px")
    rng = np.random.default_rng(semilla)
    bases = []
    consultas = []
    for indice in range(n):
        color = tuple(int(x) for x in rng.integers(30, 210, size=3))
        imagen = Image.new("RGB", (lado, lado), (245, 244, 240))
        dibujo = ImageDraw.Draw(imagen)
        margen = lado // 9
        dibujo.rectangle((margen, margen, lado - margen, lado - margen), fill=color)
        for _ in range(5):
            x0 = int(rng.integers(margen, lado - margen))
            y0 = int(rng.integers(margen, lado - margen))
            ancho = int(rng.integers(lado // 16, lado // 4))
            trazo = tuple(int(x) for x in rng.integers(0, 255, size=3))
            dibujo.ellipse((x0, y0, x0 + ancho, y0 + ancho), outline=trazo, width=4)
        dibujo.text((margen + 4, lado // 2), f"REF {indice:02d}", fill="white", font=ImageFont.load_default())
        bases.append(imagen)
        recorte = lado // 12
        consultas.append((imagen.crop((recorte, recorte, lado - recorte, lado - recorte))
                          .resize((lado, lado), Image.Resampling.BICUBIC), indice, "recorte"))
        consultas.append((imagen.rotate(12, resample=Image.Resampling.BICUBIC,
                                        fillcolor=(245, 244, 240)), indice, "giro"))
        consultas.append((ImageEnhance.Color(imagen).enhance(0.45), indice, "color"))
    return bases, consultas


def evaluar(vectores_base: np.ndarray, vectores_consulta: np.ndarray,
            positivos: list[int], transformaciones: list[str]) -> dict:
    bases = np.asarray(vectores_base, dtype=np.float32)
    consultas = np.asarray(vectores_consulta, dtype=np.float32)
    if bases.ndim != 2 or consultas.ndim != 2 or bases.shape[1] != consultas.shape[1]:
        raise ValueError("Dimensiones de vectores incompatibles")
    if len(consultas) != len(positivos) or len(consultas) != len(transformaciones) or not len(consultas):
        raise ValueError("Consultas y positivos incompatibles")
    if any(p < 0 or p >= len(bases) for p in positivos):
        raise ValueError("Positivo fuera de la galería")
    if not np.all(np.isfinite(bases)) or not np.all(np.isfinite(consultas)):
        raise ValueError("Vectores no finitos")
    bases /= np.maximum(np.linalg.norm(bases, axis=1, keepdims=True), 1e-12)
    consultas /= np.maximum(np.linalg.norm(consultas, axis=1, keepdims=True), 1e-12)
    puntuaciones = consultas @ bases.T
    orden = np.argsort(-puntuaciones, axis=1, kind="stable")
    aciertos_1 = []
    aciertos_5 = []
    for fila, positivo in enumerate(positivos):
        aciertos_1.append(bool(positivo == orden[fila, 0]))
        aciertos_5.append(bool(positivo in orden[fila, :5]))

    def tasas(filas: list[int]) -> dict:
        return {
            "consultas": len(filas),
            "recall@1": round(sum(aciertos_1[i] for i in filas) / len(filas), 4),
            "recall@5": round(sum(aciertos_5[i] for i in filas) / len(filas), 4),
        }

    resultado = {"global": tasas(list(range(len(consultas)))), "por_transformacion": {}}
    for tipo in sorted(set(transformaciones)):
        resultado["por_transformacion"][tipo] = tasas([i for i, x in enumerate(transformaciones) if x == tipo])
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=12, help="Número de bases sintéticas")
    parser.add_argument("--dispositivo", choices=["cpu", "mps"], default="cpu")
    parser.add_argument("--lote", type=int, default=2)
    parser.add_argument("--semilla", type=int, default=23)
    args = parser.parse_args()
    bases, consultas = crear_pares_sinteticos(args.n, semilla=args.semilla)
    modelo = ModeloVisual(args.dispositivo)
    vectores_base = modelo.codificar(bases, lote=args.lote)
    vectores_consulta = modelo.codificar([x[0] for x in consultas], lote=args.lote)
    resultado = evaluar(vectores_base, vectores_consulta,
                        [x[1] for x in consultas], [x[2] for x in consultas])
    resultado.update({"modelo": MODEL_ID, "sha256_pesos": modelo.pesos_sha256,
                      "bases_sinteticas": len(bases), "semilla": args.semilla})
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
