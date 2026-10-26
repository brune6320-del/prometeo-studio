#!/usr/bin/env python3
"""Análisis de composición editorial: retícula, vacío/aire, jerarquía y escala tipográfica (D-10).

Opera exclusivamente sobre la matriz CIE L*a*b* del referente y calcula la confianza de cada
bloque mediante fórmulas continuas sobre el residuo/SNR espacial de la imagen (Ley 8, sin constantes fijas).
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .color_lab import delta_e2000


PHI = (1.0 + math.sqrt(5.0)) / 2.0  # 1.6180339887...
INV_PHI = 1.0 / PHI                 # 0.6180339887...
COMP_PHI = 1.0 - INV_PHI            # 0.3819660112...


def _estimar_color_fondo_lab(
    pixeles_lab: List[List[Tuple[float, float, float]]],
) -> Tuple[float, float, float]:
    """Estima el color CIE L*a*b* del soporte/papel buscando el modo de bajo gradiente interior."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    if alto < 4 or ancho < 4:
        return pixeles_lab[0][0] if (alto and ancho) else (95.0, 0.0, 0.0)

    y0 = max(1, int(alto * 0.03))
    y1 = min(alto - 1, max(y0 + 1, int(alto * 0.97)))
    x0 = max(1, int(ancho * 0.03))
    x1 = min(ancho - 1, max(x0 + 1, int(ancho * 0.97)))

    bins: Dict[Tuple[int, int, int], List[float]] = {}
    for y in range(y0, y1):
        for x in range(x0, x1):
            l_v, a_v, b_v = pixeles_lab[y][x]
            gx = abs(pixeles_lab[y][x + 1][0] - pixeles_lab[y][x - 1][0]) * 0.5
            gy = abs(pixeles_lab[y + 1][x][0] - pixeles_lab[y - 1][x][0]) * 0.5
            if math.hypot(gx, gy) > 5.5:
                continue
            k = (int(round(l_v / 4.0)), int(round(a_v / 4.0)), int(round(b_v / 4.0)))
            acc = bins.get(k)
            if acc is None:
                bins[k] = [l_v, a_v, b_v, 1.0]
            else:
                acc[0] += l_v
                acc[1] += a_v
                acc[2] += b_v
                acc[3] += 1.0

    if not bins:
        for y in range(y0, y1):
            for x in range(x0, x1):
                l_v, a_v, b_v = pixeles_lab[y][x]
                k = (int(round(l_v / 5.0)), int(round(a_v / 5.0)), int(round(b_v / 5.0)))
                acc = bins.setdefault(k, [0.0, 0.0, 0.0, 0.0])
                acc[0] += l_v
                acc[1] += a_v
                acc[2] += b_v
                acc[3] += 1.0

    mejor = max(bins.values(), key=lambda v: v[3])
    return (mejor[0] / mejor[3], mejor[1] / mejor[3], mejor[2] / mejor[3])


def _calcular_mapas_actividad(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    fondo_lab: Tuple[float, float, float],
) -> Tuple[List[List[float]], List[List[float]], List[List[float]], List[List[bool]], float, float, float]:
    """Calcula mapa de peso visual W(y,x), gradientes |∂x L*|, |∂y L*|, máscara de aire/vacío y métricas de limpieza."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    total_px = float(max(1, alto * ancho))

    peso_visual: List[List[float]] = [[0.0] * ancho for _ in range(alto)]
    grad_x: List[List[float]] = [[0.0] * ancho for _ in range(alto)]
    grad_y: List[List[float]] = [[0.0] * ancho for _ in range(alto)]
    es_aire: List[List[bool]] = [[True] * ancho for _ in range(alto)]

    borde_y = max(1, int(alto * 0.03))
    borde_x = max(1, int(ancho * 0.03))

    conteo_liso = 0
    suma_de_figura = 0.0
    cnt_figura = 0
    suma_ruido_aire = 0.0
    cnt_aire = 0

    for y in range(alto):
        y_prev = max(0, y - 1)
        y_next = min(alto - 1, y + 1)
        en_marco_y = (y < borde_y) or (y >= alto - borde_y)
        for x in range(ancho):
            x_prev = max(0, x - 1)
            x_next = min(ancho - 1, x + 1)
            en_marco_x = (x < borde_x) or (x >= ancho - borde_x)

            px_lab = pixeles_lab[y][x]
            de_fondo = delta_e2000(px_lab, fondo_lab)

            dl_x = abs(pixeles_lab[y][x_next][0] - pixeles_lab[y][x_prev][0]) * 0.5
            dl_y = abs(pixeles_lab[y_next][x][0] - pixeles_lab[y_prev][x][0]) * 0.5
            da_x = abs(pixeles_lab[y][x_next][1] - pixeles_lab[y][x_prev][1]) * 0.25
            da_y = abs(pixeles_lab[y_next][x][1] - pixeles_lab[y_prev][x][1]) * 0.25
            gx = dl_x + da_x
            gy = dl_y + da_y
            g_mag = math.hypot(gx, gy)

            if g_mag < 4.5:
                conteo_liso += 1

            if en_marco_y or en_marco_x:
                if px_lab[0] > 80.0 or de_fondo < 12.0:
                    grad_x[y][x] = 0.0
                    grad_y[y][x] = 0.0
                    es_aire[y][x] = True
                    peso_visual[y][x] = 0.0
                    cnt_aire += 1
                    continue

            grad_x[y][x] = gx
            grad_y[y][x] = gy

            aire = (de_fondo < 10.5) and (g_mag < 5.0)
            es_aire[y][x] = aire

            if aire:
                peso_visual[y][x] = 0.0
                suma_ruido_aire += de_fondo + g_mag
                cnt_aire += 1
            else:
                peso_visual[y][x] = de_fondo + 0.9 * g_mag
                suma_de_figura += de_fondo
                cnt_figura += 1

    frac_liso = conteo_liso / total_px
    media_de_fig = (suma_de_figura / float(cnt_figura)) if cnt_figura > 0 else 0.0
    media_ruido_aire = (suma_ruido_aire / float(cnt_aire)) if cnt_aire > 0 else 15.0
    return peso_visual, grad_x, grad_y, es_aire, frac_liso, media_de_fig, media_ruido_aire


def _suavizar_1d(arr: List[float], radio: int = 2) -> List[float]:
    n = len(arr)
    if n == 0 or radio <= 0:
        return list(arr)
    out = [0.0] * n
    for i in range(n):
        ini = max(0, i - radio)
        fin = min(n, i + radio + 1)
        out[i] = sum(arr[ini:fin]) / float(fin - ini)
    return out


def _detectar_picos_1d(
    perfil: List[float],
    num_max: int = 6,
    dist_min_rel: float = 0.08,
    umbral_rel: float = 0.22,
) -> List[Tuple[float, float]]:
    """Devuelve lista de (posicion_rel, fuerza_norm) de los picos locales más fuertes."""
    n = len(perfil)
    if n < 5:
        return []
    i0 = max(1, int(n * 0.03))
    i1 = min(n - 1, max(i0 + 2, int(n * 0.97)))
    max_v = max(perfil[i0:i1], default=0.0)
    if max_v <= 1e-6:
        return []
    norm = [min(1.0, v / max_v) for v in perfil]
    candidatos: List[Tuple[float, float]] = []
    for i in range(i0, i1):
        if norm[i] >= umbral_rel and norm[i] >= norm[i - 1] and norm[i] >= norm[i + 1]:
            candidatos.append((i / float(n - 1), norm[i]))
    candidatos.sort(key=lambda t: t[1], reverse=True)

    seleccionados: List[Tuple[float, float]] = []
    for pos, f in candidatos:
        if all(abs(pos - s[0]) >= dist_min_rel for s in seleccionados):
            seleccionados.append((round(pos, 4), round(f, 4)))
            if len(seleccionados) >= num_max:
                break
    seleccionados.sort(key=lambda t: t[0])
    return seleccionados


def _detectar_valles_internos(
    perfil_ocupacion: List[float],
    ini_rel: float,
    fin_rel: float,
    dist_min_rel: float = 0.14,
) -> List[Tuple[float, float]]:
    """Detecta medianiles (valles de baja ocupación entre bloques activos) dentro de [ini_rel, fin_rel]."""
    n = len(perfil_ocupacion)
    if n < 8:
        return []
    suave = _suavizar_1d(perfil_ocupacion, radio=max(1, n // 40))
    i_ini = max(2, int(round((ini_rel + 0.08) * (n - 1))))
    i_fin = min(n - 3, int(round((fin_rel - 0.08) * (n - 1))))
    if i_fin <= i_ini + 2:
        return []

    tramo = suave[i_ini : i_fin + 1]
    media_tramo = sum(tramo) / float(len(tramo))
    if media_tramo < 0.03:
        return []

    valles: List[Tuple[float, float, float]] = []
    for i in range(i_ini, i_fin + 1):
        v = suave[i]
        if v <= suave[i - 1] and v <= suave[i + 1] and v < media_tramo * 0.62:
            izq_max = max(suave[max(i_ini - 1, i - n // 5) : i], default=0.0)
            der_max = max(suave[i + 1 : min(i_fin + 2, i + 1 + n // 5)], default=0.0)
            if izq_max > media_tramo * 0.75 and der_max > media_tramo * 0.75:
                umbral_med = (v + 0.5 * min(izq_max, der_max)) * 0.5
                l_idx, r_idx = i, i
                while l_idx > i_ini and suave[l_idx - 1] <= umbral_med:
                    l_idx -= 1
                while r_idx < i_fin and suave[r_idx + 1] <= umbral_med:
                    r_idx += 1
                ancho_rel = max(1.0 / n, (r_idx - l_idx + 1) / float(n))
                profundidad = 1.0 - (v / max(1e-6, min(izq_max, der_max)))
                valles.append((i / float(n - 1), ancho_rel, profundidad))

    valles.sort(key=lambda t: t[2], reverse=True)
    elegidos: List[Tuple[float, float]] = []
    for pos, ancho_rel, _ in valles:
        if all(abs(pos - e[0]) >= dist_min_rel for e in elegidos):
            elegidos.append((round(pos, 4), round(ancho_rel, 4)))
            if len(elegidos) >= 4:
                break
    elegidos.sort(key=lambda t: t[0])
    return elegidos


def _autocorrelacion_paso(perfil: List[float]) -> Tuple[Optional[float], float]:
    """Estima el paso periódico dominante (en unidades relativas [0,1]) y su fuerza de autocorrelación."""
    n = len(perfil)
    if n < 16:
        return None, 0.0
    media = sum(perfil) / float(n)
    centrado = [v - media for v in perfil]
    var = sum(v * v for v in centrado)
    if var < 1e-8:
        return None, 0.0

    min_lag = max(3, int(round(0.06 * n)))
    max_lag = min(n // 2, int(round(0.45 * n)))
    if max_lag <= min_lag + 2:
        return None, 0.0

    corrs: List[Tuple[int, float]] = []
    for lag in range(min_lag, max_lag + 1):
        c = sum(centrado[i] * centrado[i + lag] for i in range(n - lag)) / var
        corrs.append((lag, c))

    mejor_lag = None
    mejor_c = 0.0
    for idx in range(1, len(corrs) - 1):
        lag, c = corrs[idx]
        if c >= corrs[idx - 1][1] and c >= corrs[idx + 1][1] and c > mejor_c:
            mejor_c = c
            mejor_lag = lag

    if mejor_lag is None or mejor_c < 0.10:
        return None, round(max(0.0, mejor_c), 4)
    return round(mejor_lag / float(n), 4), round(min(1.0, mejor_c), 4)


def _segmentar_regiones_jerarquia(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    peso_visual: List[List[float]],
    es_aire: List[List[bool]],
    fondo_lab: Tuple[float, float, float],
) -> Tuple[List[Dict[str, Any]], float]:
    """Segmenta regiones activas en una rejilla morfológica 64x64 y devuelve (niveles, fraccion_peso_explicada)."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    gh = min(64, alto)
    gw = min(64, ancho)

    celda_activa = [[False] * gw for _ in range(gh)]
    celda_peso = [[0.0] * gw for _ in range(gh)]
    celda_lab: List[List[Tuple[float, float, float]]] = [[fondo_lab] * gw for _ in range(gh)]
    peso_activo_total_grilla = 0.0

    for cy in range(gh):
        y0 = int(cy * alto / gh)
        y1 = max(y0 + 1, int((cy + 1) * alto / gh))
        for cx in range(gw):
            x0 = int(cx * ancho / gw)
            x1 = max(x0 + 1, int((cx + 1) * ancho / gw))
            cnt_act = 0
            tot_c = 0
            sum_w = 0.0
            sum_l, sum_a, sum_b = 0.0, 0.0, 0.0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tot_c += 1
                    if not es_aire[y][x]:
                        cnt_act += 1
                        w = peso_visual[y][x]
                        sum_w += w
                        l_v, a_v, b_v = pixeles_lab[y][x]
                        sum_l += l_v
                        sum_a += a_v
                        sum_b += b_v
            if cnt_act > 0 and (cnt_act / float(tot_c)) >= 0.25:
                celda_activa[cy][cx] = True
                w_celda = sum_w / float(tot_c)
                celda_peso[cy][cx] = w_celda
                peso_activo_total_grilla += w_celda
                celda_lab[cy][cx] = (sum_l / cnt_act, sum_a / cnt_act, sum_b / cnt_act)

    visitado = [[False] * gw for _ in range(gh)]
    componentes: List[Dict[str, Any]] = []
    total_celdas = float(gh * gw)

    for cy in range(gh):
        for cx in range(gw):
            if celda_activa[cy][cx] and not visitado[cy][cx]:
                cola = deque([(cy, cx)])
                visitado[cy][cx] = True
                celdas_comp: List[Tuple[int, int]] = []
                lab_semilla = celda_lab[cy][cx]

                while cola:
                    y_c, x_c = cola.popleft()
                    celdas_comp.append((y_c, x_c))
                    lab_actual = celda_lab[y_c][x_c]
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = y_c + dy, x_c + dx
                        if 0 <= ny < gh and 0 <= nx < gw and celda_activa[ny][nx] and not visitado[ny][nx]:
                            if (
                                delta_e2000(celda_lab[ny][nx], lab_actual) < 14.0
                                and delta_e2000(celda_lab[ny][nx], lab_semilla) < 18.0
                            ):
                                visitado[ny][nx] = True
                                cola.append((ny, nx))

                if len(celdas_comp) < max(2, int(0.004 * total_celdas)):
                    continue

                ys = [p[0] for p in celdas_comp]
                xs = [p[1] for p in celdas_comp]
                min_y, max_y = min(ys), max(ys)
                min_x, max_x = min(xs), max(xs)

                peso_comp = sum(celda_peso[y_i][x_i] for y_i, x_i in celdas_comp)
                if peso_comp <= 1e-6:
                    continue

                cx_bar = sum((x_i + 0.5) * celda_peso[y_i][x_i] for y_i, x_i in celdas_comp) / (peso_comp * gw)
                cy_bar = sum((y_i + 0.5) * celda_peso[y_i][x_i] for y_i, x_i in celdas_comp) / (peso_comp * gh)

                n_c = float(len(celdas_comp))
                mean_lab = (
                    sum(celda_lab[y_i][x_i][0] for y_i, x_i in celdas_comp) / n_c,
                    sum(celda_lab[y_i][x_i][1] for y_i, x_i in celdas_comp) / n_c,
                    sum(celda_lab[y_i][x_i][2] for y_i, x_i in celdas_comp) / n_c,
                )
                contraste_de = delta_e2000(mean_lab, fondo_lab)

                caja_rel = [
                    round(min_x / float(gw), 4),
                    round(min_y / float(gh), 4),
                    round((max_x - min_x + 1) / float(gw), 4),
                    round((max_y - min_y + 1) / float(gh), 4),
                ]
                area_rel = len(celdas_comp) / total_celdas
                componentes.append(
                    {
                        "caja_rel": caja_rel,
                        "area_rel": round(area_rel, 4),
                        "peso_bruto": peso_comp,
                        "centro_rel": (round(cx_bar, 4), round(cy_bar, 4)),
                        "contraste_local_delta_e2000": round(contraste_de, 3),
                    }
                )

    componentes.sort(key=lambda c: c["peso_bruto"], reverse=True)
    top_comp = componentes[:8]
    peso_top = sum(c["peso_bruto"] for c in top_comp)
    fraccion_explicada = (
        min(1.0, peso_top / peso_activo_total_grilla)
        if peso_activo_total_grilla > 1e-6
        else 0.0
    )

    if not top_comp:
        top_comp = [
            {
                "caja_rel": [0.1, 0.1, 0.8, 0.8],
                "area_rel": 0.5,
                "peso_bruto": 1.0,
                "centro_rel": (0.5, 0.5),
                "contraste_local_delta_e2000": 10.0,
            }
        ]
        fraccion_explicada = 0.0

    suma_peso = sum(c["peso_bruto"] for c in top_comp) or 1.0

    niveles_out: List[Dict[str, Any]] = []
    for idx, comp in enumerate(top_comp):
        if idx == 0:
            rol = "primario_focal"
        elif idx <= 2:
            rol = "secundario"
        else:
            rol = "terciario_apoyo"
        niveles_out.append(
            {
                "rango": idx + 1,
                "id_region": f"r{idx + 1}",
                "rol_jerarquico": rol,
                "caja_rel": comp["caja_rel"],
                "area_rel": comp["area_rel"],
                "peso_visual_rel": round(comp["peso_bruto"] / suma_peso, 4),
                "centro_rel": {
                    "x_rel": comp["centro_rel"][0],
                    "y_rel": comp["centro_rel"][1],
                },
                "contraste_local_delta_e2000": comp["contraste_local_delta_e2000"],
            }
        )

    return niveles_out, fraccion_explicada


def _analizar_escala_tipografica(
    grad_x: List[List[float]],
    grad_y: List[List[float]],
    es_aire: List[List[bool]],
    frac_liso: float,
    ruta_referente: Optional[Path] = None,
) -> Tuple[Dict[str, Any], float, str]:
    """Detecta bandas tipográficas, llama a tools/adn_tipo/ si existe y calcula confianza continua."""
    alto = len(grad_x)
    ancho = len(grad_x[0]) if alto > 0 else 0

    dir_tools = Path(__file__).resolve().parent.parent
    dir_adn_tipo = dir_tools / "adn_tipo"
    adn_tipo_disponible = dir_adn_tipo.is_dir()
    datos_adn_tipo: Optional[Dict[str, Any]] = None

    if adn_tipo_disponible and ruta_referente is not None:
        for script_candidato in ("estudiar.py", "analizar.py", "main.py", "__init__.py"):
            cand = dir_adn_tipo / script_candidato
            if cand.exists():
                try:
                    res = subprocess.run(
                        [sys.executable, str(cand), str(ruta_referente)],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=20,
                    )
                    if res.returncode == 0 and res.stdout.strip().startswith("{"):
                        datos_adn_tipo = json.loads(res.stdout.strip())
                        break
                except Exception:
                    pass

    perfil_texto_y: List[float] = []
    for y in range(alto):
        sum_gx = 0.0
        cnt_act = 0
        for x in range(ancho):
            if not es_aire[y][x] and grad_x[y][x] > 5.0:
                sum_gx += grad_x[y][x]
                cnt_act += 1
        densidad_fila = (sum_gx / float(max(1, ancho))) if cnt_act >= max(3, ancho // 20) else 0.0
        perfil_texto_y.append(densidad_fila)

    max_ty = max(perfil_texto_y, default=0.0)
    ord_ty = sorted(perfil_texto_y)
    mediana_ty = ord_ty[len(ord_ty) // 2] if ord_ty else 0.0
    snr_bandas = (max_ty - mediana_ty) / (max_ty + mediana_ty + 1.5)

    umbral_linea = max(1.8, max_ty * 0.25)
    bandas: List[Tuple[int, int]] = []
    en_banda = False
    y_ini = 0
    for y, v in enumerate(perfil_texto_y):
        if v >= umbral_linea and not en_banda:
            en_banda = True
            y_ini = y
        elif v < umbral_linea and en_banda:
            en_banda = False
            h_b = y - y_ini
            if 2 <= h_b <= max(3, int(0.24 * alto)):
                bandas.append((y_ini, y))
    if en_banda:
        h_b = alto - y_ini
        if 2 <= h_b <= max(3, int(0.24 * alto)):
            bandas.append((y_ini, alto))

    zonas_texto: List[Dict[str, Any]] = []
    alturas_rel: List[float] = []
    for b_y0, b_y1 in bandas:
        h_rel = round((b_y1 - b_y0) / float(alto), 4)
        xs_act = [
            x
            for x in range(ancho)
            if any(grad_x[y][x] > 5.0 for y in range(b_y0, b_y1))
        ]
        if not xs_act:
            continue
        x0_rel = round(min(xs_act) / float(ancho), 4)
        w_rel = round((max(xs_act) - min(xs_act) + 1) / float(ancho), 4)
        if w_rel < 0.08:
            continue
        alturas_rel.append(h_rel)
        rol_t = "titular" if h_rel >= 0.055 else ("subtitulo" if h_rel >= 0.03 else "cuerpo")
        zonas_texto.append(
            {
                "rol": rol_t,
                "caja_rel": [x0_rel, round(b_y0 / float(alto), 4), w_rel, h_rel],
                "altura_rel": h_rel,
            }
        )

    alturas_ordenadas = sorted(alturas_rel, reverse=True)
    niveles_unicos: List[float] = []
    for h_val in alturas_ordenadas:
        if not niveles_unicos or abs(niveles_unicos[-1] - h_val) > 0.008:
            niveles_unicos.append(h_val)
    niveles_unicos = niveles_unicos[:5]

    razon_escala: Optional[float] = None
    if len(niveles_unicos) >= 2 and niveles_unicos[-1] > 1e-4:
        razon_escala = round(niveles_unicos[0] / niveles_unicos[1], 3)

    hay_texto = len(zonas_texto) > 0
    densidad_tipografica = round(sum(z["caja_rel"][2] * z["caja_rel"][3] for z in zonas_texto), 4)

    fuente_str = "tools/adn_tipo" if (adn_tipo_disponible and datos_adn_tipo is not None) else "hueco_estimacion_estructural"

    # Confianza continua (Ley 8): producto de la limpieza estructural del lienzo (frac_liso)
    # y la relación señal-a-ruido de las bandas horizontales (o pureza de ausencia de ruido).
    confianza_continua = max(
        0.0,
        min(1.0, frac_liso * (0.50 + 0.50 * snr_bandas)),
    )

    nota = (
        "Integrado con tools/adn_tipo/ (D-10)."
        if datos_adn_tipo is not None
        else f"Hueco D-10 activo; SNR de bandas horizontales={snr_bandas:.3f}, limpieza={frac_liso:.3f}."
    )

    bloque_escala = {
        "fuente_analisis": fuente_str,
        "adn_tipo_disponible": adn_tipo_disponible,
        "hay_texto_detectado": hay_texto,
        "niveles_detectados": len(niveles_unicos),
        "alturas_relativas_lineas": niveles_unicos,
        "razon_escala": razon_escala,
        "densidad_tipografica_rel": min(1.0, densidad_tipografica),
        "zonas_texto_rel": zonas_texto[:10],
        "datos_adn_tipo": datos_adn_tipo,
    }
    return bloque_escala, round(confianza_continua, 4), nota


def estudiar_composicion(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    ruta_referente: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, float], Dict[str, str]]:
    """Produce los bloques (reticula, escala_tipografica, vacio, jerarquia) y sus confianzas continuas."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0
    total_px = float(max(1, alto * ancho))

    fondo_lab = _estimar_color_fondo_lab(pixeles_lab)
    (
        peso_visual,
        grad_x,
        grad_y,
        es_aire,
        frac_liso,
        media_de_fig,
        media_ruido_aire,
    ) = _calcular_mapas_actividad(pixeles_lab, fondo_lab)

    conteo_aire = 0
    conteo_aire_contiguo = 0
    mitad_y = alto // 2
    mitad_x = ancho // 2
    aire_cuad = {"sup_izq": [0, 0], "sup_der": [0, 0], "inf_izq": [0, 0], "inf_der": [0, 0]}

    sum_peso = 0.0
    sum_wx = 0.0
    sum_wy = 0.0

    ocupacion_x = [0.0] * ancho
    ocupacion_y = [0.0] * alto
    borde_vert_x = [0.0] * ancho
    borde_horiz_y = [0.0] * alto

    for y in range(alto):
        y_rel = (y + 0.5) / float(alto)
        y_prev = max(0, y - 1)
        y_next = min(alto - 1, y + 1)
        for x in range(ancho):
            x_rel = (x + 0.5) / float(ancho)
            x_prev = max(0, x - 1)
            x_next = min(ancho - 1, x + 1)
            clave_c = (
                ("sup_izq" if x < mitad_x else "sup_der")
                if y < mitad_y
                else ("inf_izq" if x < mitad_x else "inf_der")
            )
            aire_cuad[clave_c][1] += 1
            if es_aire[y][x]:
                conteo_aire += 1
                aire_cuad[clave_c][0] += 1
                if (
                    es_aire[y_prev][x]
                    and es_aire[y_next][x]
                    and es_aire[y][x_prev]
                    and es_aire[y][x_next]
                ):
                    conteo_aire_contiguo += 1
            else:
                ocupacion_x[x] += 1.0 / float(alto)
                ocupacion_y[y] += 1.0 / float(ancho)

            w = peso_visual[y][x]
            sum_peso += w
            sum_wx += w * x_rel
            sum_wy += w * y_rel

            borde_vert_x[x] += grad_x[y][x]
            borde_horiz_y[y] += grad_y[y][x]

    prop_aire = conteo_aire / total_px
    pct_aire = prop_aire * 100.0
    contig_aire = (conteo_aire_contiguo / float(conteo_aire)) if conteo_aire > 0 else 0.0

    if sum_peso > 1e-6:
        cx_peso = sum_wx / sum_peso
        cy_peso = sum_wy / sum_peso
    else:
        cx_peso, cy_peso = 0.5, 0.5

    dx = cx_peso - 0.5
    dy = cy_peso - 0.5
    dist_centro = math.hypot(dx, dy)

    if dist_centro <= 0.055:
        equilibrio = "centrado"
    elif abs(dx) >= 0.05 and abs(dy) >= 0.05:
        equilibrio = "diagonal_dinamico"
    elif abs(dy) >= abs(dx):
        equilibrio = "superior_dominante" if dy < 0 else "inferior_dominante"
    else:
        equilibrio = "izquierda_dominante" if dx < 0 else "derecha_dominante"

    bloque_vacio = {
        "porcentaje_aire": round(pct_aire, 2),
        "proporcion_aire": round(prop_aire, 4),
        "distribucion_cuadrantes": {
            k: round(v[0] / float(max(1, v[1])), 4) for k, v in aire_cuad.items()
        },
        "centro_peso_visual": {
            "x_rel": round(cx_peso, 4),
            "y_rel": round(cy_peso, 4),
            "desviacion_del_centro": {
                "dx": round(dx, 4),
                "dy": round(dy, 4),
                "distancia_euclidea": round(dist_centro, 4),
            },
            "equilibrio": equilibrio,
        },
    }

    umbral_act_col = 0.04
    indices_x_act = [x for x, v in enumerate(ocupacion_x) if v >= umbral_act_col]
    indices_y_act = [y for y, v in enumerate(ocupacion_y) if v >= umbral_act_col]

    margen_izq = (indices_x_act[0] / float(ancho)) if indices_x_act else 0.0
    margen_der = ((ancho - 1 - indices_x_act[-1]) / float(ancho)) if indices_x_act else 0.0
    margen_sup = (indices_y_act[0] / float(alto)) if indices_y_act else 0.0
    margen_inf = ((alto - 1 - indices_y_act[-1]) / float(alto)) if indices_y_act else 0.0

    sim_horiz = max(0.0, 1.0 - abs(margen_izq - margen_der) / max(0.05, margen_izq + margen_der))
    sim_vert = max(0.0, 1.0 - abs(margen_sup - margen_inf) / max(0.05, margen_sup + margen_inf))

    x_ini_rel = margen_izq
    x_fin_rel = max(x_ini_rel + 0.1, 1.0 - margen_der)
    y_ini_rel = margen_sup
    y_fin_rel = max(y_ini_rel + 0.1, 1.0 - margen_inf)

    valles_x = _detectar_valles_internos(ocupacion_x, x_ini_rel, x_fin_rel)
    valles_y = _detectar_valles_internos(ocupacion_y, y_ini_rel, y_fin_rel)

    cortes_col = [x_ini_rel] + [v[0] for v in valles_x] + [x_fin_rel]
    anchos_col = [round(max(0.01, cortes_col[i + 1] - cortes_col[i]), 4) for i in range(len(cortes_col) - 1)]
    num_columnas = len(anchos_col)
    if num_columnas > 1:
        media_col = sum(anchos_col) / float(num_columnas)
        desv_col = sum(abs(w - media_col) for w in anchos_col) / float(num_columnas)
        reg_col = max(0.0, min(1.0, 1.0 - (desv_col / max(1e-4, media_col))))
    else:
        reg_col = 1.0

    ancho_medio_medianil = (
        round(sum(v[1] for v in valles_x) / float(len(valles_x)), 4) if valles_x else 0.0
    )

    ejes_v = _detectar_picos_1d(_suavizar_1d(borde_vert_x, radio=2), num_max=6, dist_min_rel=0.07)
    ejes_h = _detectar_picos_1d(_suavizar_1d(borde_horiz_y, radio=2), num_max=6, dist_min_rel=0.07)

    lineas_tercios = (1.0 / 3.0, 2.0 / 3.0)
    lineas_aureas = (COMP_PHI, INV_PHI)

    puntos_clave_pos = (
        [e[0] for e in ejes_v]
        + [e[0] for e in ejes_h]
        + [cx_peso, cy_peso]
        + [v[0] for v in valles_x]
    )

    def _afinidad_canon(lineas_obj: Tuple[float, float]) -> Tuple[float, List[float]]:
        if not puntos_clave_pos:
            return 0.0, []
        proximos: List[float] = []
        scores: List[float] = []
        for l_obj in lineas_obj:
            dist_min = min(abs(p - l_obj) for p in puntos_clave_pos)
            sc = math.exp(-((dist_min / 0.06) ** 2))
            scores.append(sc)
            if dist_min <= 0.055:
                proximos.append(round(l_obj, 4))
        return round(sum(scores) / float(len(scores)), 4), proximos

    afin_tercios, prox_tercios = _afinidad_canon(lineas_tercios)
    afin_aurea, prox_aureos = _afinidad_canon(lineas_aureas)

    if sim_horiz >= 0.85 and abs(cx_peso - 0.5) <= 0.045 and max(afin_tercios, afin_aurea) < 0.72:
        sist_dom = "modular_simetrico"
    elif afin_aurea >= afin_tercios and afin_aurea >= 0.55:
        sist_dom = "aureo"
    elif afin_tercios >= 0.55:
        sist_dom = "tercios"
    else:
        sist_dom = "asimetrico_libre"

    paso_v, reg_v = _autocorrelacion_paso(_suavizar_1d(borde_horiz_y, radio=1))
    paso_h, reg_h = _autocorrelacion_paso(_suavizar_1d(borde_vert_x, radio=1))
    regularidad_ritmica = round(max(reg_v, reg_h), 4)

    niveles_jer, fraccion_peso_explicada = _segmentar_regiones_jerarquia(
        pixeles_lab, peso_visual, es_aire, fondo_lab
    )
    area_max = max((n["area_rel"] for n in niveles_jer), default=1.0) or 1.0
    peso_max = max((n["peso_visual_rel"] for n in niveles_jer), default=1.0) or 1.0

    razones_tamano = [round(n["area_rel"] / area_max, 4) for n in niveles_jer]
    razones_peso = [round(n["peso_visual_rel"] / peso_max, 4) for n in niveles_jer]
    if len(niveles_jer) >= 2 and niveles_jer[1]["peso_visual_rel"] > 1e-4:
        indice_dominancia = round(
            niveles_jer[0]["peso_visual_rel"] / niveles_jer[1]["peso_visual_rel"], 3
        )
    else:
        indice_dominancia = 1.0

    recorrido_visual = [
        {
            "orden": idx + 1,
            "x_rel": n["centro_rel"]["x_rel"],
            "y_rel": n["centro_rel"]["y_rel"],
            "peso": n["peso_visual_rel"],
        }
        for idx, n in enumerate(niveles_jer[:5])
    ]

    bloque_reticula = {
        "columnas": {
            "num_columnas": num_columnas,
            "anchos_relativos": anchos_col,
            "regularidad": round(reg_col, 4),
        },
        "margenes": {
            "superior_rel": round(margen_sup, 4),
            "inferior_rel": round(margen_inf, 4),
            "izquierdo_rel": round(margen_izq, 4),
            "derecho_rel": round(margen_der, 4),
            "simetria_horizontal": round(sim_horiz, 4),
            "simetria_vertical": round(sim_vert, 4),
        },
        "medianiles": {
            "medianiles_verticales_x_rel": [v[0] for v in valles_x],
            "ancho_medio_rel": ancho_medio_medianil,
            "medianiles_horizontales_y_rel": [v[0] for v in valles_y],
        },
        "ejes_alineacion": {
            "verticales_x_rel": [{"pos": p, "fuerza": f} for p, f in ejes_v],
            "horizontales_y_rel": [{"pos": p, "fuerza": f} for p, f in ejes_h],
        },
        "proporciones_geometricas": {
            "alineacion_tercios": afin_tercios,
            "alineacion_aurea": afin_aurea,
            "ejes_proximos_tercios": prox_tercios,
            "ejes_proximos_aureos": prox_aureos,
            "sistema_dominante": sist_dom,
        },
        "ritmo_y_repeticion": {
            "paso_vertical_rel": paso_v,
            "paso_horizontal_rel": paso_h,
            "regularidad_ritmica": regularidad_ritmica,
            "repeticion_bloques": len(niveles_jer),
        },
    }

    bloque_jerarquia = {
        "num_elementos_principales": len(niveles_jer),
        "razones_tamano": razones_tamano,
        "razones_peso_visual": razones_peso,
        "indice_dominancia": indice_dominancia,
        "niveles": niveles_jer,
        "recorrido_visual_rel": recorrido_visual,
    }

    bloque_escala, conf_escala, nota_escala = _analizar_escala_tipografica(
        grad_x, grad_y, es_aire, frac_liso, ruta_referente=ruta_referente
    )

    # --- Cálculo continuo de confianzas sobre la señal de la imagen (Ley 8, sin constantes fijas) ---
    # 1. Retícula: coeficiente de variación de los perfiles de borde proyectados + fracción lisa del soporte
    def _cv_perfil(arr: List[float]) -> float:
        if not arr:
            return 0.0
        m = sum(arr) / float(len(arr))
        if m <= 1e-6:
            return 0.0
        v = sum((x - m) ** 2 for x in arr) / float(len(arr))
        return math.sqrt(max(0.0, v)) / m

    cv_bordes = 0.5 * (_cv_perfil(borde_vert_x) + _cv_perfil(borde_horiz_y))
    snr_ejes = cv_bordes / (cv_bordes + 0.45)
    conf_reticula = max(
        0.0,
        min(
            1.0,
            frac_liso * (0.60 * snr_ejes + 0.20 * reg_col + 0.20 * max(afin_tercios, afin_aurea)),
        ),
    )

    # 2. Vacío: contigüidad espacial del aire + separabilidad bimodal figura/aire
    sep_bimodal = media_de_fig / (media_de_fig + media_ruido_aire + 4.0)
    conf_vacio = max(
        0.0,
        min(1.0, 0.55 * contig_aire + 0.45 * sep_bimodal * frac_liso),
    )

    # 3. Jerarquía: fracción de peso visual explicada por regiones conexas * contraste medio de las regiones
    contraste_medio_reg = (
        sum(n["contraste_local_delta_e2000"] * n["peso_visual_rel"] for n in niveles_jer)
        if niveles_jer
        else 0.0
    )
    factor_contraste_jer = contraste_medio_reg / (contraste_medio_reg + 10.0)
    conf_jerarquia = max(
        0.0,
        min(1.0, fraccion_peso_explicada * (0.60 * frac_liso + 0.40 * factor_contraste_jer)),
    )

    confianzas = {
        "reticula": round(conf_reticula, 4),
        "escala_tipografica": round(conf_escala, 4),
        "vacio": round(conf_vacio, 4),
        "jerarquia": round(conf_jerarquia, 4),
    }
    notas = {
        "reticula": (
            f"Detectadas {num_columnas} col(s), {len(ejes_v)} ejes V y {len(ejes_h)} ejes H "
            f"(CV_bordes={cv_bordes:.3f}, frac_liso={frac_liso:.3f})."
        ),
        "escala_tipografica": nota_escala,
        "vacio": (
            f"Aire={pct_aire:.1f}%, contigüidad={contig_aire:.3f}, "
            f"separabilidad_bimodal={sep_bimodal:.3f}."
        ),
        "jerarquia": (
            f"Segmentadas {len(niveles_jer)} regiones (peso_explicado={fraccion_peso_explicada:.3f}, "
            f"dominancia={indice_dominancia})."
        ),
    }

    return bloque_reticula, bloque_escala, bloque_vacio, bloque_jerarquia, confianzas, notas
