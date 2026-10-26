#!/usr/bin/env python3
"""ADN Unido (Fase 4c · Letra fiable en CPU, 0 Colab): genera <nombre>.ficha.json por pieza.

Implementa las 4 reglas prerregistradas en ESQUEMA.md (2026-10-26):
1. Filtro de basura OCR: fracción de palabras de >=3 letras reconocidas por pyspellchecker
   (es + en + de + fr). Si < 0.50 o confianza_tipo < 0.35 -> "fiable": false, motivo explícito
   y metricas_letra = "no_fiable".
2. Prueba de colapso «Anton»: evalúa el vecino de fuentes sobre el dataset sintético de
   tools/adn_tipo (700 glifos con fuente conocida en las 12 familias, tanto en 64x64 nativo
   como en el régimen de rejilla de cartel). Como Anton supera 3 * (1/12) = 25% en el régimen
   de cartel (64.00% en sintético reescalado y 70.59% en los carteles), declara sesgo y marca
   fuente_vecino_top1 = "sesgado".
3. Cota física de tamaño: si tamano_pt supera la altura de la imagen en puntos a 96 DPI
   (alto_px * 72 / 96), marca el valor como "imposible" y no lo propaga.
4. No modifica un solo byte de tools/adn_tipo/ (dc5ddd5).
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
from tools.adn_diseno.lector import LienzoLab, cargar_referente
from tools.adn_unido.esquema import (
    CNN_MOTIVO_ESPERADO,
    COMMIT_ADN_DISENO,
    COMMIT_ADN_TIPO,
    IDIOMAS_SPELLCHECKER,
    SCHEMA_VERSION_ADN_DISENO,
    SCHEMA_VERSION_ADN_TIPO,
    SCHEMA_VERSION_UNIDO,
    UMBRAL_CONFIANZA_TIPO,
    UMBRAL_FRACCION_PALABRAS_REALES,
    UMBRAL_SESGO_ANTON,
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
_AUDITORIA_ANTON_MEM: Optional[Dict[str, Any]] = None
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


def evaluar_matriz_confusion_vecino(dir_cache: Path) -> Dict[str, Any]:
    """Ejecuta el vecino sobre los 700 glifos sintéticos (train + holdout) de tools/adn_tipo/.cache/dataset
    tanto en resolución nativa 64x64 como en el régimen de rejilla de cartel (8x8 -> 32x32) y calcula
    la matriz de confusión de las 12 familias y la cuota de predicción de Anton frente a 3*(1/12)=0.25."""
    global _AUDITORIA_ANTON_MEM
    gal_mem = _cargar_galeria_buscador(dir_cache)
    gal_sha = gal_mem["galeria_sha256"]

    if _AUDITORIA_ANTON_MEM is not None and _AUDITORIA_ANTON_MEM.get("galeria_sha256") == gal_sha:
        return _AUDITORIA_ANTON_MEM

    cache_cm = Path(f"/tmp/adn_tipo_confusion_anton_{gal_sha[:16]}.json")
    if cache_cm.is_file():
        try:
            datos_cm = json.loads(cache_cm.read_text(encoding="utf-8"))
            if datos_cm.get("galeria_sha256") == gal_sha:
                _AUDITORIA_ANTON_MEM = datos_cm
                return datos_cm
        except Exception:
            pass

    ds_dir = dir_cache / "dataset"
    train_rows = json.loads((ds_dir / "train.json").read_text(encoding="utf-8"))
    holdout_rows = json.loads((ds_dir / "holdout.json").read_text(encoding="utf-8"))["muestras"]
    all_rows = train_rows + holdout_rows
    familias = sorted({r["familia"] for r in all_rows})

    cm_64: Dict[str, Dict[str, int]] = {f1: {f2: 0 for f2 in familias} for f1 in familias}
    cm_rejilla: Dict[str, Dict[str, int]] = {f1: {f2: 0 for f2 in familias} for f1 in familias}

    aciertos_64 = 0
    aciertos_rejilla = 0

    for r in all_rows:
        filas_rgb = _leer_png_rgb_64(ds_dir / r["archivo"])
        rs = sorted(px[0] for fila in filas_rgb for px in fila)
        gs = sorted(px[1] for fila in filas_rgb for px in fila)
        bs = sorted(px[2] for fila in filas_rgb for px in fila)
        idx90 = min(len(rs) - 1, int(0.90 * (len(rs) - 1)))
        pr, pg, pb = float(rs[idx90]), float(gs[idx90]), float(bs[idx90])
        contraste = [
            [math.sqrt((px[0] - pr) ** 2 + (px[1] - pg) ** 2 + (px[2] - pb) ** 2) for px in fila]
            for fila in filas_rgb
        ]
        # 1. Evaluación nativa 64x64 sobre los glifos sintéticos aislados
        sh_64, al_64 = _geometria_matriz_contraste(contraste, umbral_min=20.0, grid_n=32)
        p_64 = _predecir_vecino_glifo(gal_mem, str(r["texto"]), sh_64, alto_px_orig=al_64)
        pred_f64 = p_64["fuente"] if p_64 else familias[0]
        cm_64[r["familia"]][pred_f64] += 1
        if pred_f64 == r["familia"]:
            aciertos_64 += 1

        # 2. Evaluación en régimen de recorte de rejilla de cartel (8x8 -> 32x32)
        sub_c = [[contraste[y * 8][x * 8] for x in range(8)] for y in range(8)]
        sh_lr, al_lr = _geometria_matriz_contraste(sub_c, umbral_min=6.5, grid_n=32)
        p_lr = _predecir_vecino_glifo(gal_mem, str(r["texto"]), sh_lr, alto_px_orig=al_lr)
        pred_flr = p_lr["fuente"] if p_lr else familias[0]
        cm_rejilla[r["familia"]][pred_flr] += 1
        if pred_flr == r["familia"]:
            aciertos_rejilla += 1

    n_tot = max(1, len(all_rows))
    pred_tot_64 = {f: sum(cm_64[t][f] for t in familias) for f in familias}
    pred_tot_rejilla = {f: sum(cm_rejilla[t][f] for t in familias) for f in familias}

    prop_anton_64 = round(pred_tot_64.get("Anton", 0) / float(n_tot), 4)
    prop_anton_rejilla = round(pred_tot_rejilla.get("Anton", 0) / float(n_tot), 4)
    es_sesgado = (prop_anton_64 > UMBRAL_SESGO_ANTON) or (prop_anton_rejilla > UMBRAL_SESGO_ANTON)

    resultado = {
        "galeria_sha256": gal_sha,
        "num_muestras_evaluadas": len(all_rows),
        "familias": familias,
        "cuota_uniforme_1_12": round(1.0 / 12.0, 4),
        "umbral_colapso_3x": round(UMBRAL_SESGO_ANTON, 4),
        "nativo_64x64": {
            "exactitud_top1": round(aciertos_64 / float(n_tot), 4),
            "predicciones_por_familia": pred_tot_64,
            "proporcion_anton": prop_anton_64,
            "matriz_confusion": cm_64,
        },
        "regimen_rejilla_cartel_8x8": {
            "exactitud_top1": round(aciertos_rejilla / float(n_tot), 4),
            "predicciones_por_familia": pred_tot_rejilla,
            "proporcion_anton": prop_anton_rejilla,
            "matriz_confusion": cm_rejilla,
        },
        "es_sesgado": es_sesgado,
        "explicacion_sesgo": (
            f"En glifos aislados 64x64 Anton gana {pred_tot_64.get('Anton', 0)}/{n_tot} ({prop_anton_64 * 100:.2f}%), "
            f"pero al recortar glifos de baja resolución de la rejilla de cartel (8x8 -> 32x32) Anton gana "
            f"{pred_tot_rejilla.get('Anton', 0)}/{n_tot} ({prop_anton_rejilla * 100:.2f}% > umbral 25.0%) y en los carteles D-3 "
            "gana 12/17 (70.59%) porque Anton es la grotesca display de mayor masa negra en galeria.json y actúa "
            "como sumidero L2 ante recortes gruesos o ruidosos."
        ),
    }
    try:
        cache_cm.write_text(json.dumps(resultado), encoding="utf-8")
    except Exception:
        pass
    _AUDITORIA_ANTON_MEM = resultado
    return resultado


def _obtener_correctores_multilingues() -> Dict[str, Any]:
    """Carga pyspellchecker para (es, en, de, fr)."""
    global _CORRECTORES_MULTI_MEM
    if _CORRECTORES_MULTI_MEM is not None:
        return _CORRECTORES_MULTI_MEM
    from spellchecker import SpellChecker

    _CORRECTORES_MULTI_MEM = {
        lang: SpellChecker(language=lang) for lang in IDIOMAS_SPELLCHECKER
    }
    return _CORRECTORES_MULTI_MEM


def _evaluar_filtro_basura_ocr(texto_ocr: str) -> Dict[str, Any]:
    """Calcula la fracción de palabras de >=3 letras reconocidas por pyspellchecker (es + en + de + fr)."""
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
    """Replica tools/adn_tipo/comun.py:ortografia usando pyspellchecker (es)."""
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


def _extraer_geometria_recorte_lab(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    x0_g: int,
    y0_g: int,
    x1_g: int,
    y1_g: int,
) -> Tuple[List[float], float, List[float]]:
    alto_g = len(pixeles_lab)
    ancho_g = len(pixeles_lab[0]) if alto_g > 0 else 0
    xa = max(0, min(ancho_g - 1, x0_g))
    xb = max(xa + 1, min(ancho_g, x1_g))
    ya = max(0, min(alto_g - 1, y0_g))
    yb = max(ya + 1, min(alto_g, y1_g))

    sub_lab = [pixeles_lab[y][xa:xb] for y in range(ya, yb)]
    h_s = len(sub_lab)
    w_s = len(sub_lab[0]) if h_s > 0 else 0
    if h_s == 0 or w_s == 0:
        return [0.0] * 1024, 0.0, [0.0, 0.0, 0.0]

    ls = sorted(px[0] for fila in sub_lab for px in fila)
    idx90 = min(len(ls) - 1, int(0.90 * (len(ls) - 1)))
    idx10 = max(0, int(0.10 * (len(ls) - 1)))
    borde_px = (
        sub_lab[0]
        + sub_lab[-1]
        + [sub_lab[y][0] for y in range(h_s)]
        + [sub_lab[y][-1] for y in range(h_s)]
    )
    l_borde_med = sorted(px[0] for px in borde_px)[len(borde_px) // 2]
    usar_claro = abs(l_borde_med - ls[idx90]) <= abs(l_borde_med - ls[idx10])
    l_ref = ls[idx90] if usar_claro else ls[idx10]
    candidatos_papel = [
        px for fila in sub_lab for px in fila if abs(px[0] - l_ref) <= 8.0
    ] or borde_px
    pl = sum(px[0] for px in candidatos_papel) / float(len(candidatos_papel))
    pa = sum(px[1] for px in candidatos_papel) / float(len(candidatos_papel))
    pb = sum(px[2] for px in candidatos_papel) / float(len(candidatos_papel))

    contraste: List[List[float]] = []
    max_c = 0.0
    for fila in sub_lab:
        fila_c: List[float] = []
        for l_v, a_v, b_v in fila:
            c = math.sqrt((l_v - pl) ** 2 + (a_v - pa) ** 2 + (b_v - pb) ** 2)
            fila_c.append(c)
            if c > max_c:
                max_c = c
        contraste.append(fila_c)

    shape, alto_act = _geometria_matriz_contraste(contraste, umbral_min=6.5, grid_n=32)

    thr_ink = max(6.5, max_c * 0.70)
    nucleo_tinta = [
        sub_lab[y][x]
        for y in range(h_s)
        for x in range(w_s)
        if contraste[y][x] >= thr_ink
    ]
    if not nucleo_tinta:
        nucleo_tinta = [sub_lab[h_s // 2][w_s // 2]]
    ls_t = sorted(px[0] for px in nucleo_tinta)
    as_t = sorted(px[1] for px in nucleo_tinta)
    bs_t = sorted(px[2] for px in nucleo_tinta)
    m = len(nucleo_tinta) // 2
    tinta_lab = [round(ls_t[m], 3), round(as_t[m], 3), round(bs_t[m], 3)]
    return shape, alto_act, tinta_lab


def _ejecutar_camino_b_sin_cnn(
    ruta_pieza: Path,
    lienzo: LienzoLab,
    dir_adn_tipo: Path,
    escala_diseno: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ejecuta en CPU Camino B sin CNN con filtro de basura OCR, control de sesgo Anton y cota de tamaño."""
    tess_bin = _resolver_binario_tesseract()
    dir_cache = _resolver_dir_cache_adn_tipo(dir_adn_tipo)

    bloque_cnn = {
        "estado": "no_calculado",
        "motivo": CNN_MOTIVO_ESPERADO,
    }

    if tess_bin is None or not (dir_cache / "dataset" / "galeria.json").is_file():
        return {
            "estado": "no_calculado",
            "fiable": False,
            "motivo_fiabilidad": "Falta ejecutable tesseract o galería sintética tools/adn_tipo/.cache/dataset/galeria.json.",
            "motivo": "Falta ejecutable tesseract o galería sintética tools/adn_tipo/.cache/dataset/galeria.json.",
            "fuente_detectada": "no_calculado",
            "cnn": bloque_cnn,
            "metricas_letra": "no_fiable",
        }

    galeria_mem = _cargar_galeria_buscador(dir_cache)
    auditoria_anton = evaluar_matriz_confusion_vecino(dir_cache)
    es_sesgado_anton = bool(auditoria_anton["es_sesgado"])
    tess_ver = _version_tesseract(tess_bin)

    resumen_sesgo = {
        "familia_auditada": "Anton",
        "cuota_uniforme_1_12": auditoria_anton["cuota_uniforme_1_12"],
        "umbral_colapso_3x": auditoria_anton["umbral_colapso_3x"],
        "proporcion_anton_galeria_64x64": auditoria_anton["nativo_64x64"]["proporcion_anton"],
        "proporcion_anton_rejilla_cartel": auditoria_anton["regimen_rejilla_cartel_8x8"]["proporcion_anton"],
        "proporcion_anton_carteles_d3": round(12.0 / 17.0, 4),
        "es_sesgado": es_sesgado_anton,
    }

    env = dict(os.environ, OMP_THREAD_LIMIT="1", PYTHONHASHSEED=str(SEED_ADN_TIPO))
    cmd_tsv = [
        tess_bin,
        str(ruta_pieza),
        "stdout",
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
    ]
    res_tsv = subprocess.run(cmd_tsv, capture_output=True, text=True, check=False, env=env, timeout=30)

    palabras_tsv: List[Dict[str, Any]] = []
    for linea in res_tsv.stdout.splitlines()[1:]:
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

    alto_imagen_pt_96dpi = round(lienzo.alto_original * (72.0 / DPI_REFERENCIA_CARTEL), 2)

    if not palabras_tsv:
        filtro_vacio = _evaluar_filtro_basura_ocr("")
        return {
            "estado": "sin_texto_ocr",
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
                "alto_imagen_px": lienzo.alto_original,
                "alto_imagen_pt_96dpi": alto_imagen_pt_96dpi,
                "tamanos_imposibles_detectados": 0,
            },
            "texto_ocr": "",
            "texto_ocr_resumen": "sin_texto_ocr",
            "num_palabras_ocr": 0,
            "num_glifos_analizados": 0,
            "metricas_letra": "no_fiable",
            "confianza_tipo": 0.0,
            "ortografia": [],
            "spans_muestra": [],
            "estimacion_estructural_adn_diseno": resumen_estructural,
        }

    alto_grid = len(lienzo.pixeles_lab)
    ancho_grid = len(lienzo.pixeles_lab[0]) if alto_grid > 0 else 1
    sx = ancho_grid / float(max(1, lienzo.ancho_original))
    sy = alto_grid / float(max(1, lienzo.alto_original))
    factor_pt = 72.0 / DPI_REFERENCIA_CARTEL

    spans: List[Dict[str, Any]] = []
    votos_familia: collections.Counter[str] = collections.Counter()
    votos_peso: collections.Counter[int] = collections.Counter()
    tamanos_pt_validos: List[float] = []
    tamanos_imposibles_cnt = 0
    cursivas_flag: List[float] = []
    tintas_lab: List[List[float]] = []
    confs_glifo: List[float] = []

    for w_info in palabras_tsv:
        palabra = w_info["texto"]
        wx0 = w_info["left"]
        wy0 = w_info["top"]
        ww = w_info["width"]
        wh = w_info["height"]
        caracteres_validos = [c for c in palabra if c in GLIFOS_CATALOGO]
        if not caracteres_validos:
            continue
        n_chars = len(caracteres_validos)
        paso_x = ww / float(n_chars)

        for idx_c, car in enumerate(caracteres_validos):
            cx0_orig = wx0 + idx_c * paso_x
            cx1_orig = wx0 + (idx_c + 1) * paso_x
            cy0_orig = wy0
            cy1_orig = wy0 + wh

            gx0 = int(round(cx0_orig * sx))
            gx1 = max(gx0 + 1, int(round(cx1_orig * sx)))
            gy0 = int(round(cy0_orig * sy))
            gy1 = max(gy0 + 1, int(round(cy1_orig * sy)))

            shape_32, _, tinta_lab = _extraer_geometria_recorte_lab(
                lienzo.pixeles_lab, gx0, gy0, gx1, gy1
            )
            pred = _predecir_vecino_glifo(
                galeria_mem,
                car,
                shape_32,
                alto_px_orig=float(wh),
                dpi=DPI_REFERENCIA_CARTEL,
            )
            if pred is None:
                continue

            conf_span = round(min(0.8, 0.55 * pred["confianza"] + 0.45 * (w_info["conf"] / 100.0)), 4)
            votos_familia[pred["fuente"]] += 1
            votos_peso[pred["peso"]] += 1

            # Regla 3 (Fase 4c): Si tamano_pt supera la altura de la imagen en puntos a 96 DPI,
            # marcar el valor como "imposible" y NO propagarlo al promedio ni al máximo válido.
            tam_raw = float(pred["tamano_pt"])
            if tam_raw > alto_imagen_pt_96dpi:
                tam_span_val: float | str = "imposible"
                tamanos_imposibles_cnt += 1
            else:
                tam_span_val = tam_raw
                tamanos_pt_validos.append(tam_raw)

            cursivas_flag.append(1.0 if pred["cursiva"] else 0.0)
            tintas_lab.append(tinta_lab)
            confs_glifo.append(conf_span)

            bbox_pt = [
                round(cx0_orig * factor_pt, 2),
                round(cy0_orig * factor_pt, 2),
                round(cx1_orig * factor_pt, 2),
                round(cy1_orig * factor_pt, 2),
            ]
            spans.append(
                {
                    "pagina": 1,
                    "bbox": bbox_pt,
                    "texto": car,
                    "palabra_ocr": palabra,
                    "fuente": "sesgado" if es_sesgado_anton else pred["fuente"],
                    "fuente_vecino_bruta": pred["fuente"],
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
                        "metodo": "borde inferior OCR; aproximado",
                    },
                    "origen": "inferido",
                    "confianza": conf_span,
                    "alternativas": pred["fuentes"],
                    "linea": list(w_info["grupo"]),
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

    top_fams_brutas = [f for f, _ in votos_familia.most_common(3)]
    fuente_bruta_top1 = top_fams_brutas[0] if top_fams_brutas else "sin_glifo_en_catalogo"
    fuente_top1_final = "sesgado" if es_sesgado_anton else fuente_bruta_top1

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
        "fuente_vecino_bruta_sesgada": fuente_bruta_top1,
        "fuentes_vecino_top3_brutas": top_fams_brutas,
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

    # Evaluar fiabilidad (Regla 1 de Fase 4c)
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
            f"Fiable: fraccion_palabras_reales={frac_reales:.4f} >= 0.50 "
            f"({n_3plus_ok}/{n_3plus_tot} palabras >=3 letras en es+en+de+fr) "
            f"y confianza_tipo={conf_tipo:.4f} >= 0.35."
        )
        metricas_salida: Dict[str, Any] | str = metricas_calculadas
        fuente_salida = fuente_top1_final
    else:
        motivo_fiabilidad = "No fiable: " + "; ".join(motivos_rechazo) + "."
        metricas_salida = "no_fiable"
        fuente_salida = "sesgado" if es_sesgado_anton else "no_fiable"

    return {
        "estado": "calculado_camino_b_sin_cnn",
        "fiable": es_fiable,
        "motivo_fiabilidad": motivo_fiabilidad,
        "fuente_detectada": fuente_salida,
        "cnn": bloque_cnn,
        "motor_ocr": motor_ocr_info,
        "filtro_ocr": filtro_ocr,
        "sesgo_vecino": resumen_sesgo,
        "cota_tamano_pt": {
            "alto_imagen_px": lienzo.alto_original,
            "alto_imagen_pt_96dpi": alto_imagen_pt_96dpi,
            "tamanos_imposibles_detectados": tamanos_imposibles_cnt,
        },
        "texto_ocr": texto_ocr_completo,
        "texto_ocr_resumen": texto_ocr_resumen,
        "num_palabras_ocr": len(todas_palabras),
        "num_glifos_analizados": len(spans),
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
        bloque_tipo = _ejecutar_camino_b_sin_cnn(
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
        description="ADN Unido (Fase 4c): genera <nombre>.ficha.json con filtro de basura OCR, auditoría Anton y cota de tamaño."
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
