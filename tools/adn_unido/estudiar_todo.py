#!/usr/bin/env python3
"""ADN Unido (Fase 4d · Recorte nativo por carácter en CPU, 0 Colab): genera <nombre>.ficha.json.

Implementa el Régimen C prerregistrado en ESQUEMA.md (2026-10-26):
1. Cajas por carácter a resolución original: extrae simultáneamente .tsv y .box (makebox /
   image_to_boxes) con Tesseract 5.5.3 sobre la imagen a resolución ORIGINAL, recorta cada
   carácter con margen exterior para estimar el color de papel y lo centra en una plantilla
   64x64 idéntica a la galería sintética (tools/adn_tipo/inferir.py líneas 29-31).
2. Evalúa los 3 regímenes (A: aislado 64x64, B: rejilla 8x8 -> 32x32, C: recorte nativo por
   caja de Tesseract en láminas de cartel) sobre los 700 glifos sintéticos.
3. Si el Régimen C cumple el prerregistro (acierto >= 50% y cuota de Anton <= 2 * 1/12 = 16,67%),
   fuente_vecino_top1 deja de marcarse como "sesgado" y reporta la fuente ganadora y su cuota.
4. Mantiene intactos los filtros de Fase 4c (fracción de palabras reales >= 0,50 en es+en+de+fr,
   confianza_tipo >= 0,35 y descarte de tamano_pt > alto_imagen_pt_96dpi como "imposible")
   sin tocar un solo byte de tools/adn_tipo/ (dc5ddd5).
"""

from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import math
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_RUTAS_VENV_CANDIDATAS = (
    Path(__file__).resolve().parents[2] / ".venv" / "lib" / "python3.11" / "site-packages",
    Path("/Users/gladys/.gemini/users/user1/Projects/prometeo-adn-diseno/.venv/lib/python3.11/site-packages"),
)
for _venv_sp in _RUTAS_VENV_CANDIDATAS:
    if _venv_sp.is_dir() and str(_venv_sp) not in sys.path:
        sys.path.insert(0, str(_venv_sp))

from tools.adn_diseno.estudiar import estudiar_lienzo
from tools.adn_diseno.lector import LienzoLab, cargar_referente, srgb_a_lab
from tools.adn_unido.esquema import (
    CNN_MOTIVO_ESPERADO,
    COMMIT_ADN_DISENO,
    COMMIT_ADN_TIPO,
    IDIOMAS_SPELLCHECKER,
    SCHEMA_VERSION_ADN_DISENO,
    SCHEMA_VERSION_ADN_TIPO,
    SCHEMA_VERSION_UNIDO,
    UMBRAL_ACIERTO_REGIMEN_C,
    UMBRAL_ANTON_REGIMEN_C,
    UMBRAL_CONFIANZA_TIPO,
    UMBRAL_FRACCION_PALABRAS_REALES,
    calcular_sha256_ficha_sin_fecha,
    validar_ficha_unida,
)

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".pdf"}
EXTENSIONES_FUENTE = {".ttf", ".otf"}

SEED_ADN_TIPO = 2610
PSM_FIJO_OCR = 6
OEM_FIJO_OCR = 1
DPI_REFERENCIA_CARTEL = 96.0
GLIFOS_CATALOGO = set(
    "abcdefghijklmnñopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZáéíóúüÁÉÍÓÚÜ0123456789.,;:!?¿¡()-"
)

_GALERIA_CACHE_MEM: Optional[Dict[str, Any]] = None
_AUDITORIA_ABC_MEM: Optional[Dict[str, Any]] = None
_CORRECTORES_MULTI_MEM: Optional[Dict[str, Any]] = None


def _identificador_maquina() -> str:
    nodo = platform.node() or "mac-mini"
    sist = platform.system()
    maq = platform.machine()
    py_ver = platform.python_version()
    return f"{nodo} ({sist} {maq}, Python {py_ver})"


def _resolver_binario_tesseract() -> Optional[str]:
    for ruta in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if os.path.isfile(ruta) and os.access(ruta, os.X_OK):
            return ruta
    return shutil.which("tesseract")


def _version_tesseract(tess_bin: str) -> str:
    try:
        res = subprocess.run(
            [tess_bin, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        primera = (res.stdout or res.stderr).splitlines()[0].strip()
        return primera.replace("tesseract ", "").strip() or "5.5.3"
    except Exception:
        return "desconocida"


def _resolver_dir_cache_adn_tipo(dir_adn_tipo: Path) -> Path:
    cand_local = dir_adn_tipo / ".cache"
    if (cand_local / "dataset" / "galeria.json").is_file():
        return cand_local
    cand_proj = Path(
        "/Users/gladys/.gemini/users/user1/Projects/prometeo-adn-diseno/tools/adn_tipo/.cache"
    )
    if (cand_proj / "dataset" / "galeria.json").is_file():
        return cand_proj
    return cand_local


def _leer_png_rgb_64(ruta_png: Path) -> List[List[Tuple[int, int, int]]]:
    data = ruta_png.read_bytes()
    pos = 8
    w = h = 0
    color_type = 2
    idat = bytearray()
    while pos < len(data):
        length, ctype = struct.unpack(">I4s", data[pos : pos + 8])
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h, _, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    bpp = 3 if color_type == 2 else 4
    stride = w * bpp
    filas: List[List[Tuple[int, int, int]]] = []
    prev = bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1 : i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif f == 3:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        prev = line
        filas.append([(line[x * bpp], line[x * bpp + 1], line[x * bpp + 2]) for x in range(w)])
    return filas


def _geometria_matriz_contraste(
    contraste: List[List[float]],
    umbral_min: float,
    grid_n: int = 32,
) -> Tuple[List[float], float]:
    """Replica exactamente la normalización geométrica 32x32 de tools/adn_tipo/modelo.py:geometria."""
    h = len(contraste)
    w = len(contraste[0]) if h > 0 else 0
    if h == 0 or w == 0:
        return [0.0] * (grid_n * grid_n), 0.0
    max_c = max((v for fila in contraste for v in fila), default=0.0)
    thr = max(umbral_min, max_c * 0.30)
    xmin, ymin, xmax, ymax = w, h, -1, -1
    mask_inv: List[List[float]] = [[1.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if contraste[y][x] > thr:
                mask_inv[y][x] = 0.0
                if x < xmin:
                    xmin = x
                if x > xmax:
                    xmax = x
                if y < ymin:
                    ymin = y
                if y > ymax:
                    ymax = y
    if xmax < xmin or ymax < ymin:
        return [0.0] * (grid_n * grid_n), 0.0

    cw = xmax - xmin + 1
    ch = ymax - ymin + 1
    shape: List[float] = []
    for gy in range(grid_n):
        fy = ymin + (gy + 0.5) * ch / float(grid_n) - 0.5
        y0 = max(ymin, min(ymax, int(math.floor(fy))))
        y1 = max(ymin, min(ymax, y0 + 1))
        wy = fy - math.floor(fy)
        for gx in range(grid_n):
            fx = xmin + (gx + 0.5) * cw / float(grid_n) - 0.5
            x0 = max(xmin, min(xmax, int(math.floor(fx))))
            x1 = max(xmin, min(xmax, x0 + 1))
            wx = fx - math.floor(fx)
            v00 = mask_inv[y0][x0]
            v01 = mask_inv[y0][x1]
            v10 = mask_inv[y1][x0]
            v11 = mask_inv[y1][x1]
            val = (1.0 - wy) * ((1.0 - wx) * v00 + wx * v01) + wy * ((1.0 - wx) * v10 + wx * v11)
            shape.append(round(val, 4))
    return shape, float(ch)


def _cargar_galeria_buscador(dir_cache: Path) -> Dict[str, Any]:
    global _GALERIA_CACHE_MEM
    dataset_dir = dir_cache / "dataset"
    manifest_path = dataset_dir / "manifest.json"
    galeria_path = dataset_dir / "galeria.json"
    if not manifest_path.is_file() or not galeria_path.is_file():
        raise FileNotFoundError(f"No existe la galería sintética en {dataset_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gal_sha = hashlib.sha256(galeria_path.read_bytes()).hexdigest()
    if gal_sha != manifest.get("galeria_sha256"):
        raise ValueError("Galería alterada: el SHA-256 de galeria.json no coincide con manifest.json")

    if _GALERIA_CACHE_MEM is not None and _GALERIA_CACHE_MEM.get("galeria_sha256") == gal_sha:
        return _GALERIA_CACHE_MEM

    cache_tmp = Path(f"/tmp/adn_tipo_galeria_features_{gal_sha[:16]}.json")
    if cache_tmp.is_file():
        try:
            datos_cache = json.loads(cache_tmp.read_text(encoding="utf-8"))
            if datos_cache.get("galeria_sha256") == gal_sha:
                _GALERIA_CACHE_MEM = datos_cache
                return datos_cache
        except Exception:
            pass

    galeria_raw = json.loads(galeria_path.read_text(encoding="utf-8"))
    por_caracter: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for r in galeria_raw:
        ruta_png = dataset_dir / r["archivo"]
        filas_rgb = _leer_png_rgb_64(ruta_png)
        rs = sorted(px[0] for fila in filas_rgb for px in fila)
        gs = sorted(px[1] for fila in filas_rgb for px in fila)
        bs = sorted(px[2] for fila in filas_rgb for px in fila)
        idx90 = min(len(rs) - 1, int(0.90 * (len(rs) - 1)))
        pr, pg, pb = float(rs[idx90]), float(gs[idx90]), float(bs[idx90])
        contraste = [
            [
                math.sqrt((px[0] - pr) ** 2 + (px[1] - pg) ** 2 + (px[2] - pb) ** 2)
                for px in fila
            ]
            for fila in filas_rgb
        ]
        shape, alto = _geometria_matriz_contraste(contraste, umbral_min=20.0, grid_n=32)
        por_caracter[str(r["texto"])].append(
            {
                "familia": r["familia"],
                "tamano_pt": float(r["tamano_pt"]),
                "peso": int(r["peso"]),
                "cursiva": bool(r["cursiva"]),
                "dpi": float(r["dpi"]),
                "alto": float(max(1.0, alto)),
                "shape": shape,
            }
        )

    datos_out = {
        "galeria_sha256": gal_sha,
        "holdout_sha256": manifest.get("holdout_sha256"),
        "seed": manifest.get("seed", SEED_ADN_TIPO),
        "por_caracter": dict(por_caracter),
    }
    try:
        cache_tmp.write_text(json.dumps(datos_out), encoding="utf-8")
    except Exception:
        pass
    _GALERIA_CACHE_MEM = datos_out
    return datos_out


def _predecir_vecino_glifo(
    galeria_mem: Dict[str, Any],
    caracter: str,
    shape_32: List[float],
    alto_px_orig: float,
    dpi: float = DPI_REFERENCIA_CARTEL,
) -> Optional[Dict[str, Any]]:
    """Replica exactamente Buscador.predecir (tools/adn_tipo/medir.py:23-39) sin CNN."""
    por_car = galeria_mem["por_caracter"]
    candidatos = por_car.get(caracter)
    if not candidatos and caracter.lower() in por_car:
        candidatos = por_car.get(caracter.lower())
    if not candidatos and caracter.upper() in por_car:
        candidatos = por_car.get(caracter.upper())
    if not candidatos:
        return None

    dists: List[Tuple[float, int]] = []
    n_dim = float(len(shape_32))
    for idx, item in enumerate(candidatos):
        sh_g = item["shape"]
        mse = sum((shape_32[k] - sh_g[k]) ** 2 for k in range(len(shape_32))) / n_dim
        dists.append((mse, idx))

    dists.sort(key=lambda t: (t[0], t[1]))
    vecinos: List[str] = []
    for _, idx in dists:
        fam = candidatos[idx]["familia"]
        if fam not in vecinos:
            vecinos.append(fam)

    _, mejor_idx = dists[0]
    r = candidatos[mejor_idx]
    size_pt = r["tamano_pt"] * max(1.0, alto_px_orig) / max(1.0, r["alto"]) * (r["dpi"] / dpi)

    if len(dists) > 1:
        v0 = dists[0][0]
        v1 = dists[1][0]
        conf = max(0.0, min(1.0, (v1 - v0) / (v1 + 1e-8)))
    else:
        conf = 0.0

    return {
        "fuentes": vecinos[:5],
        "fuente": r["familia"],
        "tamano_pt": round(float(size_pt), 2),
        "peso": int(r["peso"]),
        "cursiva": bool(r["cursiva"]),
        "confianza": round(float(conf), 4),
    }


def evaluar_regimenes_abc_vecino(dir_cache: Path) -> Dict[str, Any]:
    """Corre los 3 regímenes (A, B y C) sobre los 700 glifos sintéticos de tools/adn_tipo/.cache/dataset
    y verifica si el Régimen C cumple el prerregistro de Fase 4d (acierto >= 50% y cuota Anton <= 16.67%)."""
    global _AUDITORIA_ABC_MEM
    gal_mem = _cargar_galeria_buscador(dir_cache)
    gal_sha = gal_mem["galeria_sha256"]

    if _AUDITORIA_ABC_MEM is not None and _AUDITORIA_ABC_MEM.get("galeria_sha256") == gal_sha:
        return _AUDITORIA_ABC_MEM

    cache_abc = Path(f"/tmp/adn_tipo_regimenes_abc_{gal_sha[:16]}.json")
    if cache_abc.is_file():
        try:
            datos_abc = json.loads(cache_abc.read_text(encoding="utf-8"))
            if datos_abc.get("galeria_sha256") == gal_sha:
                _AUDITORIA_ABC_MEM = datos_abc
                return datos_abc
        except Exception:
            pass

    ds_dir = dir_cache / "dataset"
    train_rows = json.loads((ds_dir / "train.json").read_text(encoding="utf-8"))
    holdout_rows = json.loads((ds_dir / "holdout.json").read_text(encoding="utf-8"))["muestras"]
    all_rows = train_rows + holdout_rows
    familias = sorted({r["familia"] for r in all_rows})

    cm_a: Dict[str, Dict[str, int]] = {f1: {f2: 0 for f2 in familias} for f1 in familias}
    cm_b: Dict[str, Dict[str, int]] = {f1: {f2: 0 for f2 in familias} for f1 in familias}
    cm_c: Dict[str, Dict[str, int]] = {f1: {f2: 0 for f2 in familias} for f1 in familias}

    aciertos_a = 0
    aciertos_b = 0
    aciertos_c = 0
    cajas_tesseract_c = 0

    tess_bin = _resolver_binario_tesseract() or "/opt/homebrew/bin/tesseract"
    env = dict(os.environ, OMP_THREAD_LIMIT="1", PYTHONHASHSEED=str(SEED_ADN_TIPO))

    with tempfile.TemporaryDirectory(prefix="adn_regimen_c_") as tmpd:
        for sheet_idx in range(0, len(all_rows), 50):
            chunk = all_rows[sheet_idx : sheet_idx + 50]
            cols, rows_n = 10, 5
            W, H = cols * 64, rows_n * 64
            row_stride = (W * 3 + 3) & ~3
            img_size = row_stride * H
            header = struct.pack("<2sIHHI", b"BM", 54 + img_size, 0, 0, 54)
            dib = struct.pack("<IiiHHIIiiII", 40, W, -H, 1, 24, 0, img_size, 3780, 3780, 0, 0)
            bmp_bytes = bytearray(header + dib + b"\xf5" * img_size)
            cell_grids: List[List[List[Tuple[int, int, int]]]] = []

            for i_c, r in enumerate(chunk):
                filas_rgb = _leer_png_rgb_64(ds_dir / r["archivo"])
                cell_grids.append(filas_rgb)

                # --- Régimen A (aislado 64x64) y Régimen B (rejilla 8x8 -> 32x32) ---
                rs = sorted(px[0] for fila in filas_rgb for px in fila)
                gs = sorted(px[1] for fila in filas_rgb for px in fila)
                bs = sorted(px[2] for fila in filas_rgb for px in fila)
                idx90 = min(len(rs) - 1, int(0.90 * (len(rs) - 1)))
                pr, pg, pb = float(rs[idx90]), float(gs[idx90]), float(bs[idx90])
                contraste_a = [
                    [math.sqrt((px[0] - pr) ** 2 + (px[1] - pg) ** 2 + (px[2] - pb) ** 2) for px in fila]
                    for fila in filas_rgb
                ]
                sh_a, al_a = _geometria_matriz_contraste(contraste_a, umbral_min=20.0, grid_n=32)
                p_a = _predecir_vecino_glifo(gal_mem, str(r["texto"]), sh_a, alto_px_orig=al_a)
                pred_fa = p_a["fuente"] if p_a else familias[0]
                cm_a[r["familia"]][pred_fa] += 1
                if pred_fa == r["familia"]:
                    aciertos_a += 1

                sub_b = [[contraste_a[y * 8][x * 8] for x in range(8)] for y in range(8)]
                sh_b, al_b = _geometria_matriz_contraste(sub_b, umbral_min=6.5, grid_n=32)
                p_b = _predecir_vecino_glifo(gal_mem, str(r["texto"]), sh_b, alto_px_orig=al_b)
                pred_fb = p_b["fuente"] if p_b else familias[0]
                cm_b[r["familia"]][pred_fb] += 1
                if pred_fb == r["familia"]:
                    aciertos_b += 1

                # Montar celda en lámina de cartel para Régimen C
                cy0 = (i_c // cols) * 64
                cx0 = (i_c % cols) * 64
                for y in range(64):
                    base_off = 54 + (cy0 + y) * row_stride + cx0 * 3
                    fila = filas_rgb[y]
                    for x in range(64):
                        rv, gv, bv = fila[x]
                        off = base_off + x * 3
                        bmp_bytes[off] = bv
                        bmp_bytes[off + 1] = gv
                        bmp_bytes[off + 2] = rv

            bmp_path = Path(tmpd) / f"sheet_{sheet_idx}.bmp"
            bmp_path.write_bytes(bytes(bmp_bytes))
            res_box = subprocess.run(
                [
                    tess_bin,
                    str(bmp_path),
                    "stdout",
                    "-l",
                    "spa+eng",
                    "--psm",
                    str(PSM_FIJO_OCR),
                    "--oem",
                    str(OEM_FIJO_OCR),
                    "-c",
                    "OMP_THREAD_LIMIT=1",
                    "batch.nochop",
                    "makebox",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=30,
            )
            boxes: List[Tuple[str, int, int, int, int]] = []
            for line in res_box.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    ch = parts[0]
                    try:
                        x0, b_y0, x1, b_y1 = map(int, parts[1:5])
                    except ValueError:
                        continue
                    y0 = H - b_y1
                    y1 = H - b_y0
                    if x1 > x0 and y1 > y0:
                        boxes.append((ch, x0, y0, x1, y1))

            # --- Régimen C: recorte nativo por caja de símbolo de Tesseract + centrado 64x64 ---
            for i_c, r in enumerate(chunk):
                g_rgb = cell_grids[i_c]
                cy0 = (i_c // cols) * 64
                cx0 = (i_c % cols) * 64
                cy1, cx1 = cy0 + 64, cx0 + 64
                c_boxes = [
                    b
                    for b in boxes
                    if cx0 <= 0.5 * (b[1] + b[3]) < cx1 and cy0 <= 0.5 * (b[2] + b[4]) < cy1
                ]
                if c_boxes:
                    cajas_tesseract_c += 1
                    bx0 = max(0, min(b[1] - cx0 for b in c_boxes) - 3)
                    by0 = max(0, min(b[2] - cy0 for b in c_boxes) - 3)
                    bx1 = min(64, max(b[3] - cx0 for b in c_boxes) + 3)
                    by1 = min(64, max(b[4] - cy0 for b in c_boxes) + 3)
                else:
                    bx0, by0, bx1, by1 = 0, 0, 64, 64

                crop_rgb = [g_rgb[y][bx0:bx1] for y in range(by0, by1)]
                cw = max(1, bx1 - bx0)
                ch_px = max(1, by1 - by0)

                rs = sorted(px[0] for fila in crop_rgb for px in fila)
                gs = sorted(px[1] for fila in crop_rgb for px in fila)
                bs = sorted(px[2] for fila in crop_rgb for px in fila)
                idx90 = min(len(rs) - 1, int(0.90 * (len(rs) - 1)))
                papel = (rs[idx90], gs[idx90], bs[idx90])

                parche = [[papel] * 64 for _ in range(64)]
                ox = max(0, min(64 - cw, 32 - cw // 2))
                oy = max(0, min(64 - ch_px, 48 - ch_px))
                for yy in range(min(64 - oy, ch_px)):
                    for xx in range(min(64 - ox, cw)):
                        parche[oy + yy][ox + xx] = crop_rgb[yy][xx]

                pr, pg, pb = float(papel[0]), float(papel[1]), float(papel[2])
                contraste_c = [
                    [math.sqrt((px[0] - pr) ** 2 + (px[1] - pg) ** 2 + (px[2] - pb) ** 2) for px in fila]
                    for fila in parche
                ]
                sh_c, al_c = _geometria_matriz_contraste(contraste_c, umbral_min=20.0, grid_n=32)
                p_c = _predecir_vecino_glifo(gal_mem, str(r["texto"]), sh_c, alto_px_orig=al_c)
                pred_fc = p_c["fuente"] if p_c else familias[0]
                cm_c[r["familia"]][pred_fc] += 1
                if pred_fc == r["familia"]:
                    aciertos_c += 1

    n_tot = max(1, len(all_rows))
    pred_tot_a = {f: sum(cm_a[t][f] for t in familias) for f in familias}
    pred_tot_b = {f: sum(cm_b[t][f] for t in familias) for f in familias}
    pred_tot_c = {f: sum(cm_c[t][f] for t in familias) for f in familias}

    acc_a = round(aciertos_a / float(n_tot), 4)
    acc_b = round(aciertos_b / float(n_tot), 4)
    acc_c = round(aciertos_c / float(n_tot), 4)

    anton_a = round(pred_tot_a.get("Anton", 0) / float(n_tot), 4)
    anton_b = round(pred_tot_b.get("Anton", 0) / float(n_tot), 4)
    anton_c = round(pred_tot_c.get("Anton", 0) / float(n_tot), 4)

    exito_prerregistro_c = (acc_c >= UMBRAL_ACIERTO_REGIMEN_C) and (anton_c <= UMBRAL_ANTON_REGIMEN_C)
    es_sesgado_c = not exito_prerregistro_c

    resultado = {
        "galeria_sha256": gal_sha,
        "num_muestras_evaluadas": len(all_rows),
        "familias": familias,
        "cuota_uniforme_1_12": round(1.0 / 12.0, 4),
        "umbral_acierto_c": UMBRAL_ACIERTO_REGIMEN_C,
        "umbral_anton_c_2x": round(UMBRAL_ANTON_REGIMEN_C, 4),
        "regimen_A_aislado_64x64": {
            "exactitud_top1": acc_a,
            "aciertos": aciertos_a,
            "predicciones_por_familia": pred_tot_a,
            "proporcion_anton": anton_a,
            "matriz_confusion": cm_a,
        },
        "regimen_B_rejilla_8x8": {
            "exactitud_top1": acc_b,
            "aciertos": aciertos_b,
            "predicciones_por_familia": pred_tot_b,
            "proporcion_anton": anton_b,
            "matriz_confusion": cm_b,
        },
        "regimen_C_recorte_nativo_tesseract": {
            "exactitud_top1": acc_c,
            "aciertos": aciertos_c,
            "cajas_detectadas_tesseract": cajas_tesseract_c,
            "predicciones_por_familia": pred_tot_c,
            "proporcion_anton": anton_c,
            "matriz_confusion": cm_c,
        },
        "exito_prerregistro_c": exito_prerregistro_c,
        "es_sesgado": es_sesgado_c,
    }
    try:
        cache_abc.write_text(json.dumps(resultado), encoding="utf-8")
    except Exception:
        pass
    _AUDITORIA_ABC_MEM = resultado
    return resultado


def _obtener_correctores_multilingues() -> Dict[str, Any]:
    global _CORRECTORES_MULTI_MEM
    if _CORRECTORES_MULTI_MEM is not None:
        return _CORRECTORES_MULTI_MEM
    from spellchecker import SpellChecker

    _CORRECTORES_MULTI_MEM = {
        lang: SpellChecker(language=lang) for lang in IDIOMAS_SPELLCHECKER
    }
    return _CORRECTORES_MULTI_MEM


def _evaluar_filtro_basura_ocr(texto_ocr: str) -> Dict[str, Any]:
    tokens_3plus = re.findall(r"[^\W\d_]{3,}", texto_ocr, flags=re.UNICODE)
    if not tokens_3plus:
        return {
            "idiomas_diccionario": list(IDIOMAS_SPELLCHECKER),
            "palabras_3plus_totales": 0,
            "palabras_3plus_reconocidas": 0,
            "fraccion_palabras_reales": 0.0,
            "umbral_fraccion_palabras_reales": UMBRAL_FRACCION_PALABRAS_REALES,
            "umbral_confianza_tipo": UMBRAL_CONFIANZA_TIPO,
            "lista_palabras_3plus": [],
        }

    correctores = _obtener_correctores_multilingues()
    detalles: List[Dict[str, Any]] = []
    reconocidas = 0
    for tok in tokens_3plus:
        w_low = tok.lower()
        idiomas_ok = [lang for lang, sp in correctores.items() if w_low in sp]
        es_real = len(idiomas_ok) > 0
        if es_real:
            reconocidas += 1
        detalles.append(
            {
                "palabra": tok,
                "reconocida": es_real,
                "idiomas": idiomas_ok,
            }
        )

    frac = round(reconocidas / float(len(tokens_3plus)), 4)
    return {
        "idiomas_diccionario": list(IDIOMAS_SPELLCHECKER),
        "palabras_3plus_totales": len(tokens_3plus),
        "palabras_3plus_reconocidas": reconocidas,
        "fraccion_palabras_reales": frac,
        "umbral_fraccion_palabras_reales": UMBRAL_FRACCION_PALABRAS_REALES,
        "umbral_confianza_tipo": UMBRAL_CONFIANZA_TIPO,
        "lista_palabras_3plus": detalles[:40],
    }


def _ortografia_es(texto: str) -> List[Dict[str, Any]]:
    if not texto.strip():
        return []
    try:
        sp_es = _obtener_correctores_multilingues()["es"]
        palabras = list(re.finditer(r"[^\W\d_]+(?:['’][^\W\d_]+)?", texto, re.UNICODE))
        if not palabras:
            return []
        desconocidas = sp_es.unknown([m.group().lower() for m in palabras])
        return [
            {
                "texto": m.group(),
                "inicio": m.start(),
                "fin": m.end(),
                "marca": "revisar",
            }
            for m in palabras
            if m.group().lower() in desconocidas
        ]
    except Exception:
        return []


def _cargar_bmp_nativo(ruta_imagen: Path, tmp_dir: Path) -> Tuple[bytes, int, int, bool, int, int, int, int, int, int, int, int, int]:
    """Convierte la imagen a BMP sin reescalar vía /usr/bin/sips y devuelve su descriptor de bytes."""
    bmp_path = tmp_dir / f"{ruta_imagen.stem}_orig.bmp"
    subprocess.run(
        ["/usr/bin/sips", "-s", "format", "bmp", str(ruta_imagen), "--out", str(bmp_path)],
        capture_output=True,
        check=True,
        timeout=30,
    )
    data = bmp_path.read_bytes()
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    width, height_signed, _, bpp, compression = struct.unpack_from("<iiHHI", data, 18)
    top_down = height_signed < 0
    height = abs(height_signed)
    bytes_pp = bpp // 8
    row_stride = ((width * bpp + 31) // 32) * 4
    rmask, gmask, bmask = 0x00FF0000, 0x0000FF00, 0x000000FF
    if compression == 3 and dib_size >= 52:
        rmask, gmask, bmask = struct.unpack_from("<III", data, 54)

    def _shift_max(m: int) -> Tuple[int, int]:
        if m == 0:
            return 0, 1
        s = (m & -m).bit_length() - 1
        return s, (m >> s) or 1

    rs, rmax = _shift_max(rmask)
    gs, gmax = _shift_max(gmask)
    bs, bmax = _shift_max(bmask)
    return (
        data,
        pixel_offset,
        width,
        height,
        top_down,
        bytes_pp,
        row_stride,
        compression,
        rs,
        rmax,
        gs,
        gmax,
        bs,
        bmax,
    )


def _recortar_bmp_nativo_rgb(
    bmp_info: Tuple[Any, ...],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> List[List[Tuple[int, int, int]]]:
    """Recorta una caja (x0, y0, x1, y1) directamente a la resolución ORIGINAL del BMP."""
    (
        data,
        pixel_offset,
        width,
        height,
        top_down,
        bytes_pp,
        row_stride,
        compression,
        rs,
        rmax,
        gs,
        gmax,
        bs,
        bmax,
    ) = bmp_info
    xa = max(0, min(width - 1, x0))
    xb = max(xa + 1, min(width, x1))
    ya = max(0, min(height - 1, y0))
    yb = max(ya + 1, min(height, y1))
    filas: List[List[Tuple[int, int, int]]] = []
    for y in range(ya, yb):
        src_y = y if top_down else (height - 1 - y)
        row_start = pixel_offset + src_y * row_stride
        fila: List[Tuple[int, int, int]] = []
        for x in range(xa, xb):
            px_off = row_start + x * bytes_pp
            if bytes_pp == 3:
                b_v, g_v, r_v = data[px_off], data[px_off + 1], data[px_off + 2]
            else:
                val = struct.unpack_from("<I", data, px_off)[0]
                if compression == 3:
                    r_v = int(((val >> rs) & rmax) * 255 // rmax)
                    g_v = int(((val >> gs) & gmax) * 255 // gmax)
                    b_v = int(((val >> bs) & bmax) * 255 // bmax)
                else:
                    b_v, g_v, r_v = data[px_off], data[px_off + 1], data[px_off + 2]
            fila.append((r_v, g_v, b_v))
        filas.append(fila)
    return filas


def _ejecutar_camino_b_regimen_c(
    ruta_pieza: Path,
    lienzo: LienzoLab,
    dir_adn_tipo: Path,
    escala_diseno: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ejecuta en CPU el Camino B sin CNN usando el Régimen C (recorte nativo por caja de carácter
    de Tesseract a resolución original del cartel + centrado en plantilla 64x64)."""
    tess_bin = _resolver_binario_tesseract()
    dir_cache = _resolver_dir_cache_adn_tipo(dir_adn_tipo)

    bloque_cnn = {
        "estado": "no_calculado",
        "motivo": CNN_MOTIVO_ESPERADO,
    }

    if tess_bin is None or not (dir_cache / "dataset" / "galeria.json").is_file():
        return {
            "estado": "no_calculado",
            "regimen_recorte": "C_nativo_por_caracter",
            "fiable": False,
            "motivo_fiabilidad": "Falta ejecutable tesseract o galería sintética tools/adn_tipo/.cache/dataset/galeria.json.",
            "motivo": "Falta ejecutable tesseract o galería sintética tools/adn_tipo/.cache/dataset/galeria.json.",
            "fuente_detectada": "no_calculado",
            "cnn": bloque_cnn,
            "metricas_letra": "no_fiable",
        }

    galeria_mem = _cargar_galeria_buscador(dir_cache)
    auditoria_abc = evaluar_regimenes_abc_vecino(dir_cache)
    es_sesgado_c = bool(auditoria_abc["es_sesgado"])
    tess_ver = _version_tesseract(tess_bin)

    resumen_sesgo = {
        "regimen_aplicado": "C_nativo_por_caracter",
        "exito_prerregistro_c": auditoria_abc["exito_prerregistro_c"],
        "es_sesgado": es_sesgado_c,
        "acierto_regimen_A_64x64": auditoria_abc["regimen_A_aislado_64x64"]["exactitud_top1"],
        "cuota_anton_regimen_A": auditoria_abc["regimen_A_aislado_64x64"]["proporcion_anton"],
        "acierto_regimen_B_rejilla": auditoria_abc["regimen_B_rejilla_8x8"]["exactitud_top1"],
        "cuota_anton_regimen_B": auditoria_abc["regimen_B_rejilla_8x8"]["proporcion_anton"],
        "acierto_regimen_C_nativo": auditoria_abc["regimen_C_recorte_nativo_tesseract"]["exactitud_top1"],
        "cuota_anton_regimen_C": auditoria_abc["regimen_C_recorte_nativo_tesseract"]["proporcion_anton"],
        "umbral_acierto_c": UMBRAL_ACIERTO_REGIMEN_C,
        "umbral_anton_c_2x": round(UMBRAL_ANTON_REGIMEN_C, 4),
    }

    env = dict(os.environ, OMP_THREAD_LIMIT="1", PYTHONHASHSEED=str(SEED_ADN_TIPO))
    with tempfile.TemporaryDirectory(prefix="adn_unido_c_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        bmp_info = _cargar_bmp_nativo(ruta_pieza, tmp_dir)
        W_orig, H_orig = bmp_info[2], bmp_info[3]

        base_out = tmp_dir / "tess_out"
        cmd_tess = [
            tess_bin,
            str(ruta_pieza),
            str(base_out),
            "-l",
            "spa+eng",
            "--psm",
            str(PSM_FIJO_OCR),
            "--oem",
            str(OEM_FIJO_OCR),
            "-c",
            "OMP_THREAD_LIMIT=1",
            "-c",
            "preserve_interword_spaces=1",
            "tsv",
            "batch.nochop",
            "makebox",
        ]
        subprocess.run(cmd_tess, capture_output=True, text=True, check=False, env=env, timeout=30)

        tsv_path = base_out.with_suffix(".tsv")
        box_path = base_out.with_suffix(".box")
        tsv_lines = tsv_path.read_text(encoding="utf-8", errors="replace").splitlines()[1:] if tsv_path.is_file() else []
        box_lines = box_path.read_text(encoding="utf-8", errors="replace").splitlines() if box_path.is_file() else []

        palabras_tsv: List[Dict[str, Any]] = []
        for linea in tsv_lines:
            partes = linea.split("\t")
            if len(partes) < 12:
                continue
            texto_w = partes[11].strip()
            if not texto_w or not any(c.isalnum() for c in texto_w):
                continue
            try:
                left = int(partes[6])
                top = int(partes[7])
                width = int(partes[8])
                height = int(partes[9])
                conf_w = float(partes[10])
                block_num = int(partes[2])
                par_num = int(partes[3])
                line_num = int(partes[4])
            except ValueError:
                continue
            if width <= 0 or height <= 0:
                continue
            palabras_tsv.append(
                {
                    "texto": texto_w,
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "conf": max(0.0, conf_w),
                    "grupo": (block_num, par_num, line_num),
                }
            )

        motor_ocr_info = {
            "binario": tess_bin,
            "version": tess_ver,
            "lenguajes": "spa+eng",
            "psm": PSM_FIJO_OCR,
            "oem": OEM_FIJO_OCR,
            "omp_thread_limit": 1,
            "semilla": SEED_ADN_TIPO,
            "modo_cajas": "makebox_nativo_mas_tsv",
            "galeria_sha256": galeria_mem["galeria_sha256"],
        }

        resumen_estructural = None
        if isinstance(escala_diseno, dict):
            resumen_estructural = {
                "hay_texto_detectado": escala_diseno.get("hay_texto_detectado"),
                "niveles_detectados": escala_diseno.get("niveles_detectados"),
                "alturas_relativas_lineas": escala_diseno.get("alturas_relativas_lineas"),
                "razon_escala": escala_diseno.get("razon_escala"),
                "densidad_tipografica_rel": escala_diseno.get("densidad_tipografica_rel"),
            }

        alto_imagen_pt_96dpi = round(H_orig * (72.0 / DPI_REFERENCIA_CARTEL), 2)

        if not palabras_tsv:
            filtro_vacio = _evaluar_filtro_basura_ocr("")
            return {
                "estado": "sin_texto_ocr",
                "regimen_recorte": "C_nativo_por_caracter",
                "fiable": False,
                "motivo_fiabilidad": (
                    "No fiable: 0 palabras detectadas por OCR (--psm 6); "
                    "fraccion_palabras_reales=0.0000 < 0.50 y confianza_tipo=0.0000 < 0.35."
                ),
                "motivo": (
                    f"Tesseract {tess_ver} (--psm {PSM_FIJO_OCR} --oem {OEM_FIJO_OCR} -l spa+eng) "
                    "no detectó palabras alfanuméricas en este cartel."
                ),
                "fuente_detectada": "no_fiable",
                "cnn": bloque_cnn,
                "motor_ocr": motor_ocr_info,
                "filtro_ocr": filtro_vacio,
                "sesgo_vecino": resumen_sesgo,
                "cota_tamano_pt": {
                    "alto_imagen_px": H_orig,
                    "alto_imagen_pt_96dpi": alto_imagen_pt_96dpi,
                    "tamanos_imposibles_detectados": 0,
                },
                "texto_ocr": "",
                "texto_ocr_resumen": "sin_texto_ocr",
                "num_palabras_ocr": 0,
                "num_glifos_analizados": 0,
                "metricas_letra": "no_fiable",
                "metricas_letra_descartadas_auditoria": {
                    "fuente_vecino_top1": "sin_texto_ocr",
                    "cuota_fuente_top1": 0.0,
                    "votos_por_familia": {},
                },
                "confianza_tipo": 0.0,
                "ortografia": [],
                "spans_muestra": [],
                "estimacion_estructural_adn_diseno": resumen_estructural,
            }

        factor_pt = 72.0 / DPI_REFERENCIA_CARTEL
        spans: List[Dict[str, Any]] = []
        votos_familia: collections.Counter[str] = collections.Counter()
        votos_peso: collections.Counter[int] = collections.Counter()
        tamanos_pt_validos: List[float] = []
        tamanos_imposibles_cnt = 0
        cursivas_flag: List[float] = []
        tintas_lab: List[List[float]] = []
        confs_glifo: List[float] = []

        for line_b in box_lines:
            parts_b = line_b.split()
            if len(parts_b) < 5:
                continue
            car = parts_b[0]
            if car not in GLIFOS_CATALOGO:
                continue
            try:
                x0, by0, x1, by1 = map(int, parts_b[1:5])
            except ValueError:
                continue
            y0 = H_orig - by1
            y1 = H_orig - by0
            if x1 <= x0 or y1 <= y0:
                continue
            cw = x1 - x0
            ch_px = y1 - y0

            # Asociar cada caja de símbolo a su palabra TSV contenedora
            cx_m = 0.5 * (x0 + x1)
            cy_m = 0.5 * (y0 + y1)
            w_match: Optional[Dict[str, Any]] = None
            for w_info in palabras_tsv:
                wl, wt_y, ww, wh = w_info["left"], w_info["top"], w_info["width"], w_info["height"]
                if (wl - 4) <= cx_m <= (wl + ww + 4) and (wt_y - 4) <= cy_m <= (wt_y + wh + 4):
                    w_match = w_info
                    break
            if w_match is None:
                continue

            # Recorte nativo 1:1 con margen pequeño para estimar el color de papel en el anillo exterior
            pad = max(3, min(8, int(round(0.18 * max(cw, ch_px)))))
            crop_pad = _recortar_bmp_nativo_rgb(bmp_info, x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            hp = len(crop_pad)
            anillo = (
                crop_pad[0]
                + crop_pad[-1]
                + [crop_pad[yy][0] for yy in range(hp)]
                + [crop_pad[yy][-1] for yy in range(hp)]
            )
            rs_p = sorted(px[0] for px in anillo)
            gs_p = sorted(px[1] for px in anillo)
            bs_p = sorted(px[2] for px in anillo)
            idx_p = min(len(rs_p) - 1, int(0.75 * (len(rs_p) - 1)))
            papel = (rs_p[idx_p], gs_p[idx_p], bs_p[idx_p])

            crop_tight = _recortar_bmp_nativo_rgb(
                bmp_info,
                max(0, x0 - 1),
                max(0, y0 - 1),
                min(W_orig, x1 + 1),
                min(H_orig, y1 + 1),
            )
            ct_h = len(crop_tight)
            ct_w = len(crop_tight[0]) if ct_h > 0 else 0
            if ct_h == 0 or ct_w == 0:
                continue

            # Centrar en plantilla 64x64 igual que en inferir.py (líneas 27-31)
            esc = min(1.0, 56.0 / float(max(1, ct_w)), 42.0 / float(max(1, ct_h)))
            nw = max(1, int(round(ct_w * esc)))
            nh = max(1, int(round(ct_h * esc)))
            parche = [[papel] * 64 for _ in range(64)]
            ox = max(0, min(64 - nw, 32 - nw // 2))
            oy = max(0, min(64 - nh, 48 - nh))
            for yy in range(nh):
                sy = min(ct_h - 1, int(yy * ct_h / nh))
                for xx in range(nw):
                    sx = min(ct_w - 1, int(xx * ct_w / nw))
                    parche[oy + yy][ox + xx] = crop_tight[sy][sx]

            pr, pg, pb = float(papel[0]), float(papel[1]), float(papel[2])
            contraste: List[List[float]] = []
            max_c = 0.0
            for fila_p in parche:
                fila_c: List[float] = []
                for px in fila_p:
                    c_val = math.sqrt((px[0] - pr) ** 2 + (px[1] - pg) ** 2 + (px[2] - pb) ** 2)
                    fila_c.append(c_val)
                    if c_val > max_c:
                        max_c = c_val
                contraste.append(fila_c)

            shape_32, alto_32 = _geometria_matriz_contraste(contraste, umbral_min=20.0, grid_n=32)
            if alto_32 <= 0.0:
                continue

            # Color de tinta del núcleo oscuro (modelo.py línea 27)
            thr_ink = max(20.0, max_c * 0.75)
            nucleo_rgb = [
                parche[yy][xx]
                for yy in range(64)
                for xx in range(64)
                if contraste[yy][xx] >= thr_ink
            ]
            if not nucleo_rgb:
                nucleo_rgb = [crop_tight[ct_h // 2][ct_w // 2]]
            rs_i = sorted(px[0] for px in nucleo_rgb)
            gs_i = sorted(px[1] for px in nucleo_rgb)
            bs_i = sorted(px[2] for px in nucleo_rgb)
            m_i = len(nucleo_rgb) // 2
            tinta_lab = [
                round(v, 3)
                for v in srgb_a_lab(int(rs_i[m_i]), int(gs_i[m_i]), int(bs_i[m_i]))
            ]

            pred = _predecir_vecino_glifo(
                galeria_mem,
                car,
                shape_32,
                alto_px_orig=float(ch_px),
                dpi=DPI_REFERENCIA_CARTEL,
            )
            if pred is None:
                continue

            tam_raw = float(pred["tamano_pt"])
            # Regla de cota física de tamaño: si tamano_pt supera la altura de la imagen a 96 DPI -> "imposible"
            if tam_raw > alto_imagen_pt_96dpi or cw > int(0.60 * W_orig) or ch_px > int(0.60 * H_orig):
                tam_span_val: float | str = "imposible"
                tamanos_imposibles_cnt += 1
            else:
                tam_span_val = tam_raw
                tamanos_pt_validos.append(tam_raw)

            conf_span = round(
                min(0.8, 0.55 * pred["confianza"] + 0.45 * (w_match["conf"] / 100.0)),
                4,
            )
            if tam_span_val != "imposible":
                votos_familia[pred["fuente"]] += 1
                votos_peso[pred["peso"]] += 1
                cursivas_flag.append(1.0 if pred["cursiva"] else 0.0)
                tintas_lab.append(tinta_lab)
                confs_glifo.append(conf_span)

            bbox_pt = [
                round(x0 * factor_pt, 2),
                round(y0 * factor_pt, 2),
                round(x1 * factor_pt, 2),
                round(y1 * factor_pt, 2),
            ]
            spans.append(
                {
                    "pagina": 1,
                    "bbox": bbox_pt,
                    "texto": car,
                    "palabra_ocr": w_match["texto"],
                    "fuente": "sesgado" if es_sesgado_c else pred["fuente"],
                    "tamano_pt": tam_span_val,
                    "tamano_pt_bruto": tam_raw,
                    "peso": pred["peso"],
                    "cursiva": pred["cursiva"],
                    "inclinacion": 0.0,
                    "tinta_lab": tinta_lab,
                    "interletra": None,
                    "interlinea": None,
                    "linea_base": {
                        "origen": [bbox_pt[0], bbox_pt[3]],
                        "direccion": [1.0, 0.0],
                        "metodo": "borde inferior OCR makebox nativo",
                    },
                    "origen": "inferido",
                    "confianza": conf_span,
                    "alternativas": pred["fuentes"],
                    "linea": list(w_match["grupo"]),
                }
            )

    grupos_linea = sorted({tuple(s["linea"]) for s in spans if s.get("linea")})
    lineas_ordenadas: List[Tuple[Tuple[int, int, int], float, List[Dict[str, Any]]]] = []
    angulos_lineas: List[float] = []
    interletras_pt: List[float] = []
    interlineas_pt: List[float] = []

    for g in grupos_linea:
        ss = sorted(
            [s for s in spans if tuple(s.get("linea") or ()) == g],
            key=lambda s: s["bbox"][0],
        )
        xs_c = [0.5 * (s["bbox"][0] + s["bbox"][2]) for s in ss]
        ys_c = [s["bbox"][3] for s in ss]
        if len(ss) > 1 and (max(xs_c) - min(xs_c)) > 1.0:
            mx = sum(xs_c) / float(len(xs_c))
            my = sum(ys_c) / float(len(ys_c))
            num_sl = sum((xs_c[i] - mx) * (ys_c[i] - my) for i in range(len(ss)))
            den_sl = sum((xs_c[i] - mx) ** 2 for i in range(len(ss)))
            slope = (num_sl / den_sl) if den_sl > 1e-6 else 0.0
        else:
            slope = 0.0
        angle = round(math.degrees(math.atan(slope)), 2)
        angulos_lineas.append(abs(angle))
        dir_x = round(math.cos(math.atan(slope)), 4)
        dir_y = round(math.sin(math.atan(slope)), 4)

        for i_s, s in enumerate(ss):
            s["inclinacion"] = angle
            s["linea_base"]["direccion"] = [dir_x, dir_y]
            if i_s + 1 < len(ss):
                il = round(ss[i_s + 1]["bbox"][0] - s["bbox"][2], 2)
                s["interletra"] = il
                if -20.0 <= il <= 120.0:
                    interletras_pt.append(il)

        ys_ord = sorted(ys_c)
        med_y = ys_ord[len(ys_ord) // 2]
        lineas_ordenadas.append((g, med_y, ss))

    for i_l, (g, y_med, ss) in enumerate(lineas_ordenadas[:-1]):
        g_next, y_next, _ = lineas_ordenadas[i_l + 1]
        if g_next[:2] == g[:2]:
            diff_y = round(y_next - y_med, 2)
            for s in ss:
                s["interlinea"] = diff_y
            if diff_y > 0.0:
                interlineas_pt.append(diff_y)

    lineas_texto: Dict[Tuple[int, int, int], List[str]] = collections.defaultdict(list)
    todas_palabras: List[str] = []
    for w_info in palabras_tsv:
        lineas_texto[w_info["grupo"]].append(w_info["texto"])
        todas_palabras.append(w_info["texto"])

    texto_ocr_completo = "\n".join(" ".join(palabras_l) for _, palabras_l in sorted(lineas_texto.items()))
    texto_ocr_resumen = " ".join(todas_palabras[:6])

    filtro_ocr = _evaluar_filtro_basura_ocr(texto_ocr_completo)
    frac_reales = float(filtro_ocr["fraccion_palabras_reales"])
    n_3plus_tot = int(filtro_ocr["palabras_3plus_totales"])
    n_3plus_ok = int(filtro_ocr["palabras_3plus_reconocidas"])

    conf_tipo = round(sum(confs_glifo) / float(len(confs_glifo)), 4) if confs_glifo else 0.0

    total_votos = sum(votos_familia.values())
    top_fams = [f for f, _ in votos_familia.most_common(3)]
    if top_fams and total_votos > 0:
        fuente_ganadora, votos_ganadora = votos_familia.most_common(1)[0]
        cuota_ganadora = round(votos_ganadora / float(total_votos), 4)
    else:
        fuente_ganadora = "sin_glifo_valido"
        votos_ganadora = 0
        cuota_ganadora = 0.0

    # Paso 4 de Fase 4d: fuente_vecino_top1 solo deja de estar marcado "sesgado" si C cumplió el prerregistro
    fuente_top1_final = "sesgado" if es_sesgado_c else fuente_ganadora

    peso_dom = votos_peso.most_common(1)[0][0] if votos_peso else 400
    if tamanos_pt_validos:
        tam_medio: float | str = round(sum(tamanos_pt_validos) / float(len(tamanos_pt_validos)), 2)
        tam_max: float | str = round(max(tamanos_pt_validos), 2)
    else:
        tam_medio = "imposible"
        tam_max = "imposible"

    cursiva_prop = round(sum(cursivas_flag) / float(len(cursivas_flag)), 4) if cursivas_flag else 0.0
    incl_media = round(sum(angulos_lineas) / float(len(angulos_lineas)), 2) if angulos_lineas else 0.0
    interletra_med = round(sum(interletras_pt) / float(len(interletras_pt)), 2) if interletras_pt else 0.0
    interlinea_med = (
        round(sum(interlineas_pt) / float(len(interlineas_pt)), 2) if interlineas_pt else None
    )

    if tintas_lab:
        n_t = float(len(tintas_lab))
        tinta_media = [
            round(sum(t[0] for t in tintas_lab) / n_t, 3),
            round(sum(t[1] for t in tintas_lab) / n_t, 3),
            round(sum(t[2] for t in tintas_lab) / n_t, 3),
        ]
    else:
        tinta_media = [0.0, 0.0, 0.0]

    metricas_calculadas = {
        "fuente_vecino_top1": fuente_top1_final,
        "cuota_fuente_top1": cuota_ganadora,
        "votos_fuente_top1": f"{votos_ganadora}/{total_votos}",
        "fuentes_vecino_top3": top_fams,
        "votos_por_familia": dict(votos_familia),
        "tamano_pt_medio": tam_medio,
        "tamano_pt_max": tam_max,
        "tamanos_imposibles_descartados": tamanos_imposibles_cnt,
        "peso_dominante": peso_dom,
        "cursiva_proporcion": cursiva_prop,
        "inclinacion_lineas_deg": incl_media,
        "interletra_pt_media": interletra_med,
        "interlinea_pt_media": interlinea_med,
        "tinta_lab_media": tinta_media,
    }

    motivos_rechazo: List[str] = []
    if n_3plus_tot == 0:
        motivos_rechazo.append("0 palabras de >=3 letras (fraccion_palabras_reales=0.0000 < 0.50)")
    elif frac_reales < UMBRAL_FRACCION_PALABRAS_REALES:
        motivos_rechazo.append(
            f"fraccion_palabras_reales={frac_reales:.4f} < 0.50 ({n_3plus_ok}/{n_3plus_tot} palabras >=3 letras)"
        )
    if conf_tipo < UMBRAL_CONFIANZA_TIPO:
        motivos_rechazo.append(f"confianza_tipo={conf_tipo:.4f} < 0.35")
    if tam_medio == "imposible":
        motivos_rechazo.append(
            f"tamano_pt supera la altura de la imagen ({alto_imagen_pt_96dpi}pt a 96 DPI) -> imposible"
        )

    es_fiable = len(motivos_rechazo) == 0
    if es_fiable:
        motivo_fiabilidad = (
            f"Fiable (Régimen C): fraccion_palabras_reales={frac_reales:.4f} >= 0.50 "
            f"({n_3plus_ok}/{n_3plus_tot} palabras >=3 letras en es+en+de+fr) "
            f"y confianza_tipo={conf_tipo:.4f} >= 0.35."
        )
        metricas_salida: Dict[str, Any] | str = metricas_calculadas
        fuente_salida = fuente_top1_final
    else:
        motivo_fiabilidad = "No fiable: " + "; ".join(motivos_rechazo) + "."
        metricas_salida = "no_fiable"
        fuente_salida = "no_fiable"

    return {
        "estado": "calculado_camino_b_sin_cnn",
        "regimen_recorte": "C_nativo_por_caracter",
        "fiable": es_fiable,
        "motivo_fiabilidad": motivo_fiabilidad,
        "fuente_detectada": fuente_salida,
        "cnn": bloque_cnn,
        "motor_ocr": motor_ocr_info,
        "filtro_ocr": filtro_ocr,
        "sesgo_vecino": resumen_sesgo,
        "cota_tamano_pt": {
            "alto_imagen_px": H_orig,
            "alto_imagen_pt_96dpi": alto_imagen_pt_96dpi,
            "tamanos_imposibles_detectados": tamanos_imposibles_cnt,
        },
        "texto_ocr": texto_ocr_completo,
        "texto_ocr_resumen": texto_ocr_resumen,
        "num_palabras_ocr": len(todas_palabras),
        "num_glifos_analizados": total_votos,
        "metricas_letra": metricas_salida,
        "metricas_letra_descartadas_auditoria": None if es_fiable else metricas_calculadas,
        "confianza_tipo": conf_tipo,
        "ortografia": _ortografia_es(texto_ocr_completo)[:30],
        "spans_muestra": spans[:25],
        "estimacion_estructural_adn_diseno": resumen_estructural,
    }


def _cargar_catalogo_lock_adn_tipo(dir_adn_tipo: Path) -> Dict[str, Dict[str, Any]]:
    ruta_lock = dir_adn_tipo / "fuentes.lock.json"
    if not ruta_lock.is_file():
        return {}
    try:
        datos = json.loads(ruta_lock.read_text(encoding="utf-8"))
        out: Dict[str, Dict[str, Any]] = {}
        for item in datos.get("fuentes", []):
            nombre = str(item.get("familia") or item.get("fuente") or "").strip()
            if nombre:
                out[nombre.lower()] = {
                    "familia": nombre,
                    "archivo": item.get("archivo"),
                    "peso": item.get("peso"),
                    "cursiva": item.get("cursiva"),
                    "licencia": item.get("licencia"),
                }
        return out
    except Exception:
        return {}


def _parsear_tablas_opentype(ruta_ttf: Path) -> Dict[str, Any]:
    data = ruta_ttf.read_bytes()
    if len(data) < 12:
        raise ValueError(f"Archivo tipográfico demasiado corto: {ruta_ttf}")
    _, num_tables, _, _, _ = struct.unpack(">IHHHH", data[:12])
    tables: Dict[str, Tuple[int, int]] = {}
    for i in range(num_tables):
        off = 12 + i * 16
        if off + 16 > len(data):
            break
        tag, _, t_off, t_len = struct.unpack(">4sIII", data[off : off + 16])
        tables[tag.decode("ascii", errors="replace")] = (t_off, t_len)

    info: Dict[str, Any] = {
        "units_per_em": None,
        "usWeightClass": None,
        "usWidthClass": None,
        "italicAngle": 0.0,
        "familia": None,
        "subfamilia": None,
        "nombre_completo": None,
        "postscript_name": None,
        "es_variable": "fvar" in tables,
        "tablas_opentype": sorted(tables.keys()),
    }

    if "head" in tables:
        o, l = tables["head"]
        if o + 20 <= len(data) and l >= 20:
            info["units_per_em"] = struct.unpack(">H", data[o + 18 : o + 20])[0]

    if "OS/2" in tables:
        o, l = tables["OS/2"]
        if o + 8 <= len(data) and l >= 8:
            weight, width = struct.unpack(">HH", data[o + 4 : o + 8])
            info["usWeightClass"] = weight
            info["usWidthClass"] = width

    if "post" in tables:
        o, l = tables["post"]
        if o + 8 <= len(data) and l >= 8:
            italic_fixed = struct.unpack(">i", data[o + 4 : o + 8])[0]
            info["italicAngle"] = round(italic_fixed / 65536.0, 2)

    if "name" in tables:
        o, l = tables["name"]
        if o + 6 <= len(data) and l >= 6:
            _, count, str_off = struct.unpack(">HHH", data[o : o + 6])
            names: Dict[int, str] = {}
            for i in range(count):
                ro = o + 6 + i * 12
                if ro + 12 > len(data):
                    break
                pid, _, _, nid, slen, soff = struct.unpack(">HHHHHH", data[ro : ro + 12])
                if nid in (1, 2, 4, 6, 16, 17):
                    s_ini = o + str_off + soff
                    s_fin = s_ini + slen
                    if s_fin <= len(data):
                        raw = data[s_ini:s_fin]
                        try:
                            txt = raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman")
                            txt = txt.replace("\x00", "").strip()
                            if txt and (nid not in names or pid == 3):
                                names[nid] = txt
                        except Exception:
                            pass
            info["familia"] = names.get(16) or names.get(1)
            info["subfamilia"] = names.get(17) or names.get(2)
            info["nombre_completo"] = names.get(4)
            info["postscript_name"] = names.get(6)

    if not info["familia"]:
        info["familia"] = ruta_ttf.stem
    return info


def estudiar_pieza_unida(
    ruta_pieza: str | Path,
    max_dim_analisis: int = 192,
) -> Dict[str, Any]:
    """Construye y valida la ficha unida (<nombre>.ficha.json) para una pieza del corpus."""
    ruta = Path(ruta_pieza).expanduser().resolve()
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la pieza de entrada: {ruta}")

    sha256_bytes = hashlib.sha256(ruta.read_bytes()).hexdigest()
    sufijo = ruta.suffix.lower()

    dir_tools = Path(__file__).resolve().parent.parent
    dir_adn_tipo = dir_tools / "adn_tipo"
    catalogo_lock = _cargar_catalogo_lock_adn_tipo(dir_adn_tipo)

    if sufijo in EXTENSIONES_IMAGEN:
        lienzo = cargar_referente(ruta, max_dim_analisis=max_dim_analisis)
        estudio_diseno = estudiar_lienzo(lienzo, ruta_referente=ruta)
        bloque_diseno: Dict[str, Any] = {
            "estado": "calculado",
            **estudio_diseno,
        }
        escala_diseno = estudio_diseno.get("escala_tipografica")
        bloque_tipo = _ejecutar_camino_b_regimen_c(
            ruta,
            lienzo=lienzo,
            dir_adn_tipo=dir_adn_tipo,
            escala_diseno=escala_diseno,
        )
    elif sufijo in EXTENSIONES_FUENTE:
        bloque_diseno = {
            "estado": "no_calculado",
            "motivo": (
                "Archivo tipográfico vectorial OpenType/TrueType (.ttf) sin imagen rasterizada, "
                "paleta cromática ni retícula de cartel; no se inventa renderizado artificial (Ley 8)."
            ),
            "k_elegido": None,
            "paleta_insuficiente": None,
            "confianza_global": None,
        }
        meta_ot = _parsear_tablas_opentype(ruta)
        fam = str(meta_ot.get("familia") or ruta.stem)
        sub = str(meta_ot.get("subfamilia") or "Regular")
        peso = meta_ot.get("usWeightClass")
        etiqueta = f"{fam} ({sub}, peso={peso})" if peso is not None else f"{fam} ({sub})"
        bloque_tipo = {
            "estado": "calculado_nativo_opentype",
            "fiable": True,
            "motivo_fiabilidad": "Lectura directa exacta de las tablas binarias OpenType/TrueType (name, OS/2, head, post, fvar).",
            "motivo": (
                "Pieza vectorial OpenType/TrueType (.ttf): metadatos extraídos directamente de las tablas "
                "binarias (name, OS/2, head, post, fvar). La inferencia visual de carteles (inferir.py) "
                "no aplica a un contenedor de fuente sin imagen rasterizada."
            ),
            "fuente_detectada": etiqueta,
            "metadatos_opentype": meta_ot,
            "catalogo_adn_tipo": catalogo_lock.get(fam.lower()),
        }
    else:
        raise ValueError(f"Extensión de pieza no soportada en ADN Unido: {ruta.name}")

    fecha_utc = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    ficha: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_UNIDO,
        "tipo": bloque_tipo,
        "diseno": bloque_diseno,
        "procedencia": {
            "nombre_archivo": ruta.name,
            "sha256_imagen": sha256_bytes,
            "commit_adn_tipo": COMMIT_ADN_TIPO,
            "commit_adn_diseno": COMMIT_ADN_DISENO,
            "schema_version_adn_tipo": SCHEMA_VERSION_ADN_TIPO,
            "schema_version_adn_diseno": SCHEMA_VERSION_ADN_DISENO,
            "fecha_utc": fecha_utc,
            "maquina": _identificador_maquina(),
            "sha256_ficha_determinista": "",
        },
    }
    ficha["procedencia"]["sha256_ficha_determinista"] = calcular_sha256_ficha_sin_fecha(ficha)

    ok, errores = validar_ficha_unida(ficha)
    if not ok:
        raise ValueError(f"La ficha unida generada para {ruta.name} viola el esquema: {errores}")

    return ficha


def resolver_piezas_carpeta(carpeta_entrada: str | Path) -> List[Path]:
    base = Path(carpeta_entrada).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"No existe la carpeta de entrada: {base}")
    if base.is_file():
        return [base]

    dir_busqueda = (base / "muestras") if (base / "muestras").is_dir() else base
    extensiones_validas = EXTENSIONES_IMAGEN | EXTENSIONES_FUENTE
    piezas = [
        p
        for p in sorted(dir_busqueda.iterdir(), key=lambda x: x.name)
        if p.is_file() and p.suffix.lower() in extensiones_validas and not p.name.startswith(".")
    ]
    return piezas


def estudiar_carpeta(
    carpeta_entrada: str | Path,
    carpeta_salida: str | Path,
    max_dim_analisis: int = 192,
) -> List[Tuple[Path, Path, Dict[str, Any]]]:
    piezas = resolver_piezas_carpeta(carpeta_entrada)
    if not piezas:
        raise ValueError(f"No se encontraron piezas soportadas en {carpeta_entrada}")

    out_dir = Path(carpeta_salida).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    resultados: List[Tuple[Path, Path, Dict[str, Any]]] = []
    vistas_nombre: set[str] = set()

    for pieza in piezas:
        stem = pieza.stem
        nombre_ficha = f"{stem}.ficha.json" if stem not in vistas_nombre else f"{pieza.name}.ficha.json"
        vistas_nombre.add(stem)

        ficha = estudiar_pieza_unida(pieza, max_dim_analisis=max_dim_analisis)
        ruta_ficha = out_dir / nombre_ficha
        texto = json.dumps(ficha, indent=2, ensure_ascii=False) + "\n"
        ruta_ficha.write_text(texto, encoding="utf-8")
        resultados.append((pieza, ruta_ficha, ficha))

    return resultados


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ADN Unido (Fase 4d): genera <nombre>.ficha.json con Régimen C (recorte nativo por carácter)."
    )
    parser.add_argument(
        "carpeta_entrada",
        help="Carpeta de entrada con los carteles/piezas (p. ej. ~/Desktop/REFERENTES/corpus-editorial/).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="/tmp/adn_unido_fichas",
        help="Carpeta donde escribir los archivos <nombre>.ficha.json (por defecto /tmp/adn_unido_fichas).",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=192,
        help="Dimensión máxima de rejilla de análisis cromático/composicional (por defecto 192).",
    )
    args = parser.parse_args(argv)

    resultados = estudiar_carpeta(
        args.carpeta_entrada,
        args.output_dir,
        max_dim_analisis=args.max_dim,
    )
    print(f"Generadas {len(resultados)} fichas en {Path(args.output_dir).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
