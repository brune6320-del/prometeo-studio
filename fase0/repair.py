"""
PROMETEO · FASE 0B · REPARACIÓN DE FONDO (§10)
─────────────────────────────────────────────
Estrategias medibles, sin prejuicio (la directriz prohíbe asumir que
la IA gana). Benchmark en benchmark_raster.py decide.

  white  — relleno plano blanco (la línea base ingenua)
  mean   — color mediano del anillo circundante (fondo uniforme real)
  telea  — cv2.inpaint TELEA (clásico, difusión)
  ns     — cv2.inpaint NAVIER-STOKES (clásico)

LaMa (neuronal) queda PENDIENTE: requiere torch; se benchmarkeará en
la compuerta de Fase 1 con las mismas métricas y el mismo harness.
"""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

STRATEGIES = ("white", "mean", "telea", "ns")


def ring_stats(img: np.ndarray, x0: int, y0: int, x1: int, y1: int,
               width: int = 6) -> Tuple[float, float]:
    """Media y desviación del anillo alrededor de una región."""
    h, w = img.shape[:2]
    X0, Y0 = max(0, x0 - width), max(0, y0 - width)
    X1, Y1 = min(w, x1 + width), min(h, y1 + width)
    ring = np.ones((Y1 - Y0, X1 - X0), dtype=bool)
    ring[(y0 - Y0):(y1 - Y0), (x0 - X0):(x1 - X0)] = False
    vals = img[Y0:Y1, X0:X1][ring]
    return float(vals.mean()), float(vals.std())


def repair_region(img: np.ndarray, rect_px: Tuple[int, int, int, int],
                  strategy: str) -> np.ndarray:
    """Repara in-place la región [x0,y0,x1,y1] de una imagen GRIS."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = rect_px
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if strategy == "white":
        img[y0:y1, x0:x1] = 255
    elif strategy == "mean":
        m, _ = ring_stats(img, x0, y0, x1, y1)
        img[y0:y1, x0:x1] = m
    elif strategy in ("telea", "ns"):
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[y0:y1, x0:x1] = 255
        alg = cv2.INPAINT_TELEA if strategy == "telea" else cv2.INPAINT_NS
        img[:] = cv2.inpaint(img, mask, 5, alg)
    else:
        raise ValueError(f"estrategia desconocida: {strategy}")
    return img
