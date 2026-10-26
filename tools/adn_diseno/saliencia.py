#!/usr/bin/env python3
"""Mapa de saliencia visual (qué mira primero el ojo).

Combina el método clásico Spectral Residual (Hou & Zhang, CVPR 2007) mediante FFT 2D
radix-2 en Python puro con el contraste centro-entorno multi-escala en CIE L*a*b*
mediante ΔE2000 (Itti, Koch & Niebur, IEEE TPAMI 1998), y calcula su confianza de
forma continua a partir del SNR espacial y la coherencia local (Ley 8).
"""

from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List, Tuple

from .color_lab import delta_e2000


def _fft_1d(x: List[complex], inversa: bool = False) -> List[complex]:
    """Transformada rápida de Fourier 1D Cooley-Tukey radix-2 (longitud N potencia de 2)."""
    n = len(x)
    if n <= 1:
        return x
    pares = _fft_1d(x[0::2], inversa=inversa)
    impares = _fft_1d(x[1::2], inversa=inversa)
    signo = 2.0 * math.pi / n if inversa else -2.0 * math.pi / n
    mitad = n // 2
    out = [0j] * n
    for k in range(mitad):
        twiddle = cmath.rect(1.0, signo * k) * impares[k]
        out[k] = pares[k] + twiddle
        out[k + mitad] = pares[k] - twiddle
    if inversa:
        return [v * 0.5 for v in out]
    return out


def _fft_2d(mat: List[List[complex]], inversa: bool = False) -> List[List[complex]]:
    """FFT 2D separable sobre una matriz N x N (con N potencia de 2)."""
    h = len(mat)
    w = len(mat[0]) if h > 0 else 0
    filas = [_fft_1d(fila, inversa=inversa) for fila in mat]
    cols_t = [[filas[y][x] for y in range(h)] for x in range(w)]
    cols_fft = [_fft_1d(col, inversa=inversa) for col in cols_t]
    return [[cols_fft[x][y] for x in range(w)] for y in range(h)]


def _reenmuestrear_lab_potencia2(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    n: int = 64,
) -> List[List[Tuple[float, float, float]]]:
    """Reenmuestrea la matriz CIE L*a*b* a tamaño n x n (p.ej. 64x64) por promedio de área."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    out: List[List[Tuple[float, float, float]]] = []
    for gy in range(n):
        y0 = int(gy * alto / n)
        y1 = max(y0 + 1, int((gy + 1) * alto / n))
        fila: List[Tuple[float, float, float]] = []
        for gx in range(n):
            x0 = int(gx * ancho / n)
            x1 = max(x0 + 1, int((gx + 1) * ancho / n))
            sum_l, sum_a, sum_b = 0.0, 0.0, 0.0
            cnt = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    l_v, a_v, b_v = pixeles_lab[y][x]
                    sum_l += l_v
                    sum_a += a_v
                    sum_b += b_v
                    cnt += 1
            inv = 1.0 / float(max(1, cnt))
            fila.append((sum_l * inv, sum_a * inv, sum_b * inv))
        out.append(fila)
    return out


def _suavizado_gaussiano_2d(mat: List[List[float]], sigma: float = 1.6) -> List[List[float]]:
    """Filtro gaussiano 2D separable."""
    h = len(mat)
    w = len(mat[0]) if h > 0 else 0
    radio = max(1, int(math.ceil(2.5 * sigma)))
    kernel = [math.exp(-(i * i) / (2.0 * sigma * sigma)) for i in range(-radio, radio + 1)]
    suma_k = sum(kernel)
    kernel = [k / suma_k for k in kernel]

    temp = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            acc = 0.0
            for idx, k_v in enumerate(kernel):
                xx = min(w - 1, max(0, x + idx - radio))
                acc += mat[y][xx] * k_v
            temp[y][x] = acc

    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            acc = 0.0
            for idx, k_v in enumerate(kernel):
                yy = min(h - 1, max(0, y + idx - radio))
                acc += temp[yy][x] * k_v
            out[y][x] = acc
    return out


def _spectral_residual_canal(canal: List[List[float]]) -> List[List[float]]:
    """Implementa Hou & Zhang (CVPR 2007) sobre un canal 2D de tamaño N x N."""
    n = len(canal)
    mat_c = [[complex(canal[y][x], 0.0) for x in range(n)] for y in range(n)]
    espectro = _fft_2d(mat_c, inversa=False)

    log_amp = [[0.0] * n for _ in range(n)]
    fase = [[0.0] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            mag = abs(espectro[y][x])
            log_amp[y][x] = math.log(mag + 1e-9)
            fase[y][x] = cmath.phase(espectro[y][x])

    residual_c = [[0j] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            acc = 0.0
            cnt = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy = (y + dy) % n
                    xx = (x + dx) % n
                    acc += log_amp[yy][xx]
                    cnt += 1
            res = log_amp[y][x] - (acc / float(cnt))
            res_clamped = max(-12.0, min(12.0, res))
            residual_c[y][x] = cmath.rect(math.exp(res_clamped), fase[y][x])

    espacial = _fft_2d(residual_c, inversa=True)
    mapa_energia = [[abs(espacial[y][x]) ** 2 for x in range(n)] for y in range(n)]
    return _suavizado_gaussiano_2d(mapa_energia, sigma=1.8)


def _contraste_centro_entorno_lab(
    grid_lab: List[List[Tuple[float, float, float]]],
) -> List[List[float]]:
    """Contraste multi-escala Itti-Koch en CIE L*a*b* usando ΔE2000 respecto a vecindarios r in {2, 5, 9}."""
    n = len(grid_lab)
    radios = (2, 5, 9)

    int_l = [[0.0] * (n + 1) for _ in range(n + 1)]
    int_a = [[0.0] * (n + 1) for _ in range(n + 1)]
    int_b = [[0.0] * (n + 1) for _ in range(n + 1)]

    for y in range(n):
        sl, sa, sb = 0.0, 0.0, 0.0
        for x in range(n):
            l_v, a_v, b_v = grid_lab[y][x]
            sl += l_v
            sa += a_v
            sb += b_v
            int_l[y + 1][x + 1] = int_l[y][x + 1] + sl
            int_a[y + 1][x + 1] = int_a[y][x + 1] + sa
            int_b[y + 1][x + 1] = int_b[y][x + 1] + sb

    def media_caja(y0: int, x0: int, y1: int, x1: int) -> Tuple[float, float, float]:
        area = float(max(1, (y1 - y0) * (x1 - x0)))
        ml = (int_l[y1][x1] - int_l[y0][x1] - int_l[y1][x0] + int_l[y0][x0]) / area
        ma = (int_a[y1][x1] - int_a[y0][x1] - int_a[y1][x0] + int_a[y0][x0]) / area
        mb = (int_b[y1][x1] - int_b[y0][x1] - int_b[y1][x0] + int_b[y0][x0]) / area
        return (ml, ma, mb)

    out = [[0.0] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            centro = grid_lab[y][x]
            acc_de = 0.0
            for r in radios:
                y0, y1 = max(0, y - r), min(n, y + r + 1)
                x0, x1 = max(0, x - r), min(n, x + r + 1)
                entorno = media_caja(y0, x0, y1, x1)
                acc_de += delta_e2000(centro, entorno)
            out[y][x] = acc_de / float(len(radios))

    return _suavizado_gaussiano_2d(out, sigma=1.4)


def _normalizar_mapa(mat: List[List[float]]) -> List[List[float]]:
    vals = [v for fila in mat for v in fila]
    if not vals:
        return mat
    vmin, vmax = min(vals), max(vals)
    rango = vmax - vmin
    if rango < 1e-9:
        return [[0.0 for _ in fila] for fila in mat]
    return [[(v - vmin) / rango for v in fila] for fila in mat]


def _coherencia_espacial_grid(grid_lab: List[List[Tuple[float, float, float]]]) -> float:
    """Mide la coherencia local de objetos en la rejilla Lab (1 / (1 + ΔE2000_vecinos / 8))."""
    n = len(grid_lab)
    if n < 4:
        return 0.5
    diffs: List[float] = []
    for y in range(2, n - 2):
        for x in range(2, n - 2):
            c = grid_lab[y][x]
            diffs.append(delta_e2000(c, grid_lab[y][x + 1]))
            diffs.append(delta_e2000(c, grid_lab[y + 1][x]))
    media_de_vec = sum(diffs) / float(max(1, len(diffs)))
    return 1.0 / (1.0 + (media_de_vec / 7.5) ** 1.5)


def estudiar_saliencia(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    niveles_jerarquia: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], float]:
    """Calcula el mapa de saliencia visual y su confianza continua por SNR espacial (Ley 8)."""
    n = 64
    grid_lab = _reenmuestrear_lab_potencia2(pixeles_lab, n=n)

    canal_l = [[grid_lab[y][x][0] for x in range(n)] for y in range(n)]
    canal_c = [[math.hypot(grid_lab[y][x][1], grid_lab[y][x][2]) for x in range(n)] for y in range(n)]

    sr_l_raw = _spectral_residual_canal(canal_l)
    sr_c_raw = _spectral_residual_canal(canal_c)
    cs_lab_raw = _contraste_centro_entorno_lab(grid_lab)

    # SNR sobre el mapa bruto antes de reescalar a [0, 1]
    raw_interior: List[float] = []
    for y in range(4, n - 4):
        for x in range(4, n - 4):
            raw_interior.append(cs_lab_raw[y][x])
    raw_ord = sorted(raw_interior)
    p95_raw = raw_ord[int(0.95 * (len(raw_ord) - 1))] if raw_ord else 0.0
    p50_raw = raw_ord[len(raw_ord) // 2] if raw_ord else 0.0
    snr_espacial = (p95_raw - p50_raw) / (p95_raw + 0.5 * p50_raw + 1.0)

    sr_l = _normalizar_mapa(sr_l_raw)
    sr_c = _normalizar_mapa(sr_c_raw)
    cs_lab = _normalizar_mapa(cs_lab_raw)

    saliencia_64 = [[0.0] * n for _ in range(n)]
    for y in range(n):
        yn = (y + 0.5) / float(n)
        for x in range(n):
            xn = (x + 0.5) / float(n)
            dist_borde = min(xn, 1.0 - xn, yn, 1.0 - yn)
            if dist_borde < 0.05:
                borde_factor = 0.0
            elif dist_borde < 0.11:
                borde_factor = (dist_borde - 0.05) / 0.06
            else:
                borde_factor = 1.0
            val = (0.35 * sr_l[y][x] + 0.20 * sr_c[y][x] + 0.45 * cs_lab[y][x]) * borde_factor
            saliencia_64[y][x] = val

    saliencia_64 = _normalizar_mapa(_suavizado_gaussiano_2d(saliencia_64, sigma=1.5))

    picos: List[Tuple[float, float, float]] = []
    radio_nms = 5
    for y in range(3, n - 3):
        for x in range(3, n - 3):
            v = saliencia_64[y][x]
            if v < 0.25:
                continue
            es_max = True
            for dy in range(-radio_nms, radio_nms + 1):
                for dx in range(-radio_nms, radio_nms + 1):
                    if dy == 0 and dx == 0:
                        continue
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < n and 0 <= xx < n and saliencia_64[yy][xx] > v:
                        es_max = False
                        break
                if not es_max:
                    break
            if es_max:
                picos.append(((x + 0.5) / float(n), (y + 0.5) / float(n), v))

    picos.sort(key=lambda t: t[2], reverse=True)
    if not picos:
        picos.append((0.5, 0.5, 1.0))

    fp_x, fp_y, fp_int = picos[0]
    cuadrante_fp = (
        ("sup_izq" if fp_x < 0.5 else "sup_der")
        if fp_y < 0.5
        else ("inf_izq" if fp_x < 0.5 else "inf_der")
    )

    focos_sec: List[Dict[str, Any]] = []
    for idx, (sx, sy, sint) in enumerate(picos[1:5], start=2):
        focos_sec.append(
            {
                "orden": idx,
                "x_rel": round(sx, 4),
                "y_rel": round(sy, 4),
                "intensidad": round(sint, 4),
                "radio_rel": 0.095,
            }
        )

    rejilla_8x8: List[List[float]] = []
    paso_8 = n // 8
    for ry in range(8):
        fila_8: List[float] = []
        for rx in range(8):
            sub_vals = [
                saliencia_64[y][x]
                for y in range(ry * paso_8, (ry + 1) * paso_8)
                for x in range(rx * paso_8, (rx + 1) * paso_8)
            ]
            fila_8.append(round(sum(sub_vals) / float(len(sub_vals)), 4))
        rejilla_8x8.append(fila_8)

    flat_ord = sorted((v for fila in rejilla_8x8 for v in fila), reverse=True)
    suma_tot = sum(flat_ord) or 1.0
    concentracion = max(0.0, min(1.0, sum(flat_ord[:16]) / suma_tot))

    if niveles_jerarquia:
        c_jer = niveles_jerarquia[0]["centro_rel"]
        dist_jer_sal = math.hypot(fp_x - c_jer["x_rel"], fp_y - c_jer["y_rel"])
        coincidencia = max(0.0, min(1.0, 1.0 - dist_jer_sal / 0.7071))
    else:
        coincidencia = 0.5

    # Confianza continua (Ley 8): producto de coherencia local de objetos y SNR espacial del mapa
    coherencia_obj = _coherencia_espacial_grid(grid_lab)
    confianza_continua = max(
        0.0,
        min(1.0, coherencia_obj * (0.45 * snr_espacial + 0.55 * concentracion)),
    )

    bloque_saliencia = {
        "metodo": "spectral_residual_hou_zhang_2007_mas_itti_koch_ciede2000",
        "licencia_metodo": "Dominio público algorítmico (Hou & Zhang CVPR 2007 + Itti, Koch & Niebur PAMI 1998)",
        "foco_primario": {
            "x_rel": round(fp_x, 4),
            "y_rel": round(fp_y, 4),
            "intensidad": round(fp_int, 4),
            "cuadrante": cuadrante_fp,
        },
        "focos_secundarios": focos_sec,
        "concentracion_espacial": round(concentracion, 4),
        "snr_espacial": round(snr_espacial, 4),
        "coincidencia_jerarquia_saliencia": round(coincidencia, 4),
        "mapa_rejilla_8x8": rejilla_8x8,
    }

    return bloque_saliencia, round(confianza_continua, 4)
