#!/usr/bin/env python3
"""Lector multimodal de referentes (imagen, página de PDF, fotograma o pieza de recortador).

Convierte los píxeles de entrada inmediatamente al espacio perceptual CIE L*a*b* (D65, 2°)
para que ningún módulo posterior opere sobre RGB crudo.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LienzoLab:
    """Representación en memoria de un referente en espacio CIE L*a*b* (D65, 2°)."""

    id_referente: str
    tipo_entrada: str  # "imagen" | "pdf_pagina" | "fotograma" | "pieza_recortador"
    sha256_origen: str
    ancho_original: int
    alto_original: int
    ancho_analisis: int
    alto_analisis: int
    # Matriz alto_analisis x ancho_analisis de tuplas (L*, a*, b*)
    pixeles_lab: List[List[Tuple[float, float, float]]]
    metadatos_extra: Dict[str, Any]


def srgb_a_lab(r_u8: int, g_u8: int, b_u8: int) -> Tuple[float, float, float]:
    """Convierte un triplete sRGB [0..255] a CIE L*a*b* (D65, observador 2°).

    Esta función se usa exclusivamente en la frontera de ingestión de archivos binarios
    o generación de fixtures sintéticos de prueba.
    """
    # 1. Normalización [0, 1] y expansión gamma IEC 61966-2-1
    canales = []
    for c_u8 in (r_u8, g_u8, b_u8):
        v = max(0.0, min(1.0, c_u8 / 255.0))
        if v <= 0.04045:
            canales.append(v / 12.92)
        else:
            canales.append(((v + 0.055) / 1.055) ** 2.4)
    r_lin, g_lin, b_lin = canales

    # 2. Matriz sRGB -> CIE XYZ (D65)
    x = r_lin * 0.4124564 + g_lin * 0.3575761 + b_lin * 0.1804375
    y = r_lin * 0.2126729 + g_lin * 0.7151522 + b_lin * 0.0721750
    z = r_lin * 0.0193339 + g_lin * 0.1191920 + b_lin * 0.9503041

    # 3. Blanco de referencia D65 (2°)
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    eps = 216.0 / 24389.0  # (6/29)^3 ≈ 0.008856
    kappa = 24389.0 / 27.0  # (29/3)^3 ≈ 903.296

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > eps else (kappa * t + 16.0) / 116.0

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    l_star = max(0.0, min(100.0, 116.0 * fy - 16.0))
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return (l_star, a_star, b_star)


def lab_a_srgb_u8(l_star: float, a_star: float, b_star: float) -> Tuple[int, int, int]:
    """Inversa CIE L*a*b* (D65) -> sRGB [0..255] solo para serializar BMPs sintéticos en medir.py."""
    fy = (l_star + 16.0) / 116.0
    fx = a_star / 500.0 + fy
    fz = fy - b_star / 200.0

    eps = 216.0 / 24389.0
    kappa = 24389.0 / 27.0

    def finv(f_val: float) -> float:
        f3 = f_val ** 3
        return f3 if f3 > eps else (116.0 * f_val - 16.0) / kappa

    xn, yn, zn = 0.95047, 1.00000, 1.08883
    x = xn * finv(fx)
    y = yn * finv(fy)
    z = zn * finv(fz)

    r_lin = x * 3.2404542 - y * 1.5371385 - z * 0.4985314
    g_lin = -x * 0.9692660 + y * 1.8760108 + z * 0.0415560
    b_lin = x * 0.0556434 - y * 0.2040259 + z * 1.0572252

    out = []
    for v in (r_lin, g_lin, b_lin):
        v_c = max(0.0, min(1.0, v))
        if v_c <= 0.0031308:
            s = 12.92 * v_c
        else:
            s = 1.055 * (v_c ** (1.0 / 2.4)) - 0.055
        out.append(int(round(max(0.0, min(255.0, s * 255.0)))))
    return (out[0], out[1], out[2])


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def escribir_bmp_desde_lab(
    ruta_bmp: Path,
    pixeles_lab: List[List[Tuple[float, float, float]]],
) -> None:
    """Escribe un archivo BMP de 24 bits desde una matriz CIE L*a*b* (para tests sintéticos)."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    row_stride = (ancho * 3 + 3) & ~3
    padding = row_stride - ancho * 3
    pixel_data_size = row_stride * alto
    file_size = 54 + pixel_data_size

    header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        54,
    )
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,
        ancho,
        -alto,  # top-down BMP
        1,
        24,
        0,
        pixel_data_size,
        2835,
        2835,
        0,
        0,
    )
    ruta_bmp.parent.mkdir(parents=True, exist_ok=True)
    with ruta_bmp.open("wb") as f:
        f.write(header)
        f.write(dib)
        pad_bytes = b"\x00" * padding
        for fila in pixeles_lab:
            row_bytes = bytearray()
            for l_v, a_v, b_v in fila:
                r_u8, g_u8, b_u8 = lab_a_srgb_u8(l_v, a_v, b_v)
                row_bytes.extend((b_u8, g_u8, r_u8))
            f.write(row_bytes)
            if padding:
                f.write(pad_bytes)


def _leer_bmp_a_lab(ruta_bmp: Path) -> Tuple[int, int, List[List[Tuple[float, float, float]]]]:
    """Decodifica un archivo BMP descomprimido (24 o 32 bits) directamente a CIE L*a*b*."""
    data = ruta_bmp.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError(f"Archivo BMP inválido: {ruta_bmp}")

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    ancho = struct.unpack_from("<i", data, 18)[0]
    alto_raw = struct.unpack_from("<i", data, 22)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]

    alto = abs(alto_raw)
    top_down = alto_raw < 0

    if bpp not in (24, 32) or compression not in (0, 3):
        raise ValueError(f"Formato BMP no soportado (bpp={bpp}, comp={compression})")

    bytes_per_pixel = bpp // 8
    row_stride = ((ancho * bytes_per_pixel + 3) // 4) * 4

    # Cache rápida para colores repetidos
    cache_srgb_lab: Dict[Tuple[int, int, int], Tuple[float, float, float]] = {}
    matriz_lab: List[List[Tuple[float, float, float]]] = []

    for row_idx in range(alto):
        src_row = row_idx if top_down else (alto - 1 - row_idx)
        row_start = pixel_offset + src_row * row_stride
        fila_lab: List[Tuple[float, float, float]] = []
        for col_idx in range(ancho):
            px_off = row_start + col_idx * bytes_per_pixel
            if px_off + 3 > len(data):
                fila_lab.append((100.0, 0.0, 0.0))
                continue
            b_u8 = data[px_off]
            g_u8 = data[px_off + 1]
            r_u8 = data[px_off + 2]
            key = (r_u8, g_u8, b_u8)
            lab = cache_srgb_lab.get(key)
            if lab is None:
                lab = srgb_a_lab(r_u8, g_u8, b_u8)
                cache_srgb_lab[key] = lab
            fila_lab.append(lab)
        matriz_lab.append(fila_lab)

    return ancho, alto, matriz_lab


def _obtener_dimensiones_sips(ruta: Path) -> Optional[Tuple[int, int]]:
    sips_bin = shutil.which("sips")
    if not sips_bin:
        return None
    try:
        res = subprocess.run(
            [sips_bin, "-g", "pixelWidth", "-g", "pixelHeight", str(ruta)],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        w, h = None, None
        for line in res.stdout.splitlines():
            if "pixelWidth:" in line:
                w = int(line.split("pixelWidth:")[1].strip())
            elif "pixelHeight:" in line:
                h = int(line.split("pixelHeight:")[1].strip())
        if w and h:
            return w, h
    except Exception:
        pass
    return None


def cargar_referente(
    entrada: str | Path,
    max_dim_analisis: int = 192,
) -> LienzoLab:
    """Carga una imagen, página de PDF, fotograma o pieza de tools/recortador/ en CIE L*a*b*."""
    ruta_str = str(entrada)
    pagina_pdf = 1
    if "#page=" in ruta_str:
        ruta_str, pag_str = ruta_str.split("#page=", 1)
        pagina_pdf = max(1, int(pag_str))

    ruta = Path(ruta_str).expanduser().resolve()
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el referente de entrada: {ruta}")

    sha256_origen = _sha256_archivo(ruta)
    ext = ruta.suffix.lower()
    metadatos_extra: Dict[str, Any] = {}

    # Caso 1: Pieza JSON de tools/recortador/
    if ext == ".json":
        datos_json = json.loads(ruta.read_text(encoding="utf-8"))
        metadatos_extra["pieza_recortador"] = True
        img_rel = (
            datos_json.get("imagen")
            or datos_json.get("archivo_imagen")
            or datos_json.get("ruta_recorte")
            or datos_json.get("path")
        )
        if img_rel:
            img_path = (ruta.parent / img_rel).resolve() if not Path(img_rel).is_absolute() else Path(img_rel)
            sub_lienzo = cargar_referente(img_path, max_dim_analisis=max_dim_analisis)
            sub_lienzo.id_referente = datos_json.get("id", ruta.stem)
            sub_lienzo.tipo_entrada = "pieza_recortador"
            sub_lienzo.sha256_origen = sha256_origen
            sub_lienzo.metadatos_extra.update(metadatos_extra)
            return sub_lienzo
        raise ValueError(f"El JSON de pieza ({ruta}) no especifica ruta de imagen válida.")

    # Determinar tipo de entrada
    if ext == ".pdf":
        tipo_entrada = "pdf_pagina"
        metadatos_extra["pagina"] = pagina_pdf
    elif ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        tipo_entrada = "fotograma"
    elif "recortador" in str(ruta).lower() or "recorte" in ruta.stem.lower():
        tipo_entrada = "pieza_recortador"
    else:
        tipo_entrada = "imagen"

    # Si ya es un BMP y cabe en la dimensión de análisis, leer directo
    if ext == ".bmp":
        w_orig, h_orig, mat_lab = _leer_bmp_a_lab(ruta)
        if max(w_orig, h_orig) <= max_dim_analisis:
            return LienzoLab(
                id_referente=ruta.stem,
                tipo_entrada=tipo_entrada,
                sha256_origen=sha256_origen,
                ancho_original=w_orig,
                alto_original=h_orig,
                ancho_analisis=w_orig,
                alto_analisis=h_orig,
                pixeles_lab=mat_lab,
                metadatos_extra=metadatos_extra,
            )

    # Intentar primero con Pillow si está instalado (p.ej. en Colab)
    try:
        from PIL import Image  # type: ignore

        with Image.open(ruta) as im:
            w_orig, h_orig = im.size
            im_rgb = im.convert("RGB")
            escala = min(1.0, max_dim_analisis / float(max(w_orig, h_orig)))
            w_an = max(16, int(round(w_orig * escala)))
            h_an = max(16, int(round(h_orig * escala)))
            im_small = im_rgb.resize((w_an, h_an))
            px = im_small.load()
            cache: Dict[Tuple[int, int, int], Tuple[float, float, float]] = {}
            mat_lab = []
            for y in range(h_an):
                fila = []
                for x in range(w_an):
                    r_u8, g_u8, b_u8 = px[x, y]
                    k = (r_u8, g_u8, b_u8)
                    if k not in cache:
                        cache[k] = srgb_a_lab(r_u8, g_u8, b_u8)
                    fila.append(cache[k])
                mat_lab.append(fila)
            return LienzoLab(
                id_referente=ruta.stem,
                tipo_entrada=tipo_entrada,
                sha256_origen=sha256_origen,
                ancho_original=w_orig,
                alto_original=h_orig,
                ancho_analisis=w_an,
                alto_analisis=h_an,
                pixeles_lab=mat_lab,
                metadatos_extra=metadatos_extra,
            )
    except ImportError:
        pass

    # En macOS: usar sips (o qlmanage para vídeo/PDF multipágina) hacia un BMP temporal
    sips_bin = shutil.which("sips")
    if not sips_bin:
        raise RuntimeError("No se encontró ni Pillow ni /usr/bin/sips para decodificar la entrada.")

    dims_orig = _obtener_dimensiones_sips(ruta)
    with tempfile.TemporaryDirectory(prefix="adn_diseno_") as tmpdir:
        tmp_bmp = Path(tmpdir) / "analisis.bmp"
        fuente_para_sips = ruta

        if tipo_entrada == "fotograma":
            ql_bin = shutil.which("qlmanage")
            if ql_bin:
                subprocess.run(
                    [ql_bin, "-t", "-s", str(max_dim_analisis * 2), "-o", tmpdir, str(ruta)],
                    capture_output=True,
                    check=False,
                    timeout=20,
                )
                pngs = list(Path(tmpdir).glob("*.png"))
                if pngs:
                    fuente_para_sips = pngs[0]

        cmd = [
            sips_bin,
            "-Z",
            str(max_dim_analisis),
            "-s",
            "format",
            "bmp",
            str(fuente_para_sips),
            "--out",
            str(tmp_bmp),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        if not tmp_bmp.exists():
            raise RuntimeError(f"Error al decodificar {ruta} con sips: {res.stderr}")

        w_an, h_an, mat_lab = _leer_bmp_a_lab(tmp_bmp)
        w_orig, h_orig = dims_orig if dims_orig else (w_an, h_an)

        return LienzoLab(
            id_referente=ruta.stem,
            tipo_entrada=tipo_entrada,
            sha256_origen=sha256_origen,
            ancho_original=w_orig,
            alto_original=h_orig,
            ancho_analisis=w_an,
            alto_analisis=h_an,
            pixeles_lab=mat_lab,
            metadatos_extra=metadatos_extra,
        )
