#!/usr/bin/env python3
"""Motor cromático en CIE L*a*b* (D65, 2°): k-means adaptativo (K=3..10) con pesos por área y ΔE2000.

En D-11b:
- K adaptativo (de 3 a 10) crece hasta que la ΔE2000 media de los píxeles reales frente a su color de
  paleta (reconvertido a sRGB -> Lab) sea < 5.0, o hasta K=10.
- Si con K=10 sigue > 5.0, declara explícitamente "paleta_insuficiente": true.
- La confianza del bloque paleta se calcula de forma continua sobre el residuo ΔE2000 real (Ley 8).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .lector import lab_a_srgb_u8, srgb_a_lab


def lab_a_lch(l_star: float, a_star: float, b_star: float) -> Tuple[float, float, float]:
    """Convierte CIE L*a*b* a coordenadas cilíndricas CIE L*C*ab h_ab (grados [0, 360))."""
    c_star = math.hypot(a_star, b_star)
    if c_star < 1e-6:
        h_deg = 0.0
    else:
        h_deg = math.degrees(math.atan2(b_star, a_star)) % 360.0
    return (round(l_star, 4), round(c_star, 4), round(h_deg, 4))


def delta_e2000(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    kl: float = 1.0,
    kc: float = 1.0,
    kh: float = 1.0,
) -> float:
    """Calcula la diferencia de color perceptual CIEDE2000 (ΔE00) exacta (Sharma et al., 2005)."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = 0.5 * (c1 + c2)

    c_bar7 = c_bar ** 7
    pow25_7 = 25.0 ** 7  # 6103515625.0
    g = 0.5 * (1.0 - math.sqrt(c_bar7 / (c_bar7 + pow25_7)))

    a1_p = (1.0 + g) * a1
    a2_p = (1.0 + g) * a2

    c1_p = math.hypot(a1_p, b1)
    c2_p = math.hypot(a2_p, b2)

    h1_p = 0.0 if c1_p < 1e-9 else (math.degrees(math.atan2(b1, a1_p)) % 360.0)
    h2_p = 0.0 if c2_p < 1e-9 else (math.degrees(math.atan2(b2, a2_p)) % 360.0)

    delta_l_p = l2 - l1
    delta_c_p = c2_p - c1_p

    if c1_p * c2_p < 1e-9:
        delta_h_deg = 0.0
    else:
        diff = h2_p - h1_p
        if abs(diff) <= 180.0:
            delta_h_deg = diff
        elif diff > 180.0:
            delta_h_deg = diff - 360.0
        else:
            delta_h_deg = diff + 360.0

    delta_H_p = 2.0 * math.sqrt(c1_p * c2_p) * math.sin(math.radians(0.5 * delta_h_deg))

    l_bar_p = 0.5 * (l1 + l2)
    c_bar_p = 0.5 * (c1_p + c2_p)

    if c1_p * c2_p < 1e-9:
        h_bar_p = h1_p + h2_p
    else:
        if abs(h1_p - h2_p) <= 180.0:
            h_bar_p = 0.5 * (h1_p + h2_p)
        elif (h1_p + h2_p) < 360.0:
            h_bar_p = 0.5 * (h1_p + h2_p + 360.0)
        else:
            h_bar_p = 0.5 * (h1_p + h2_p - 360.0)

    t_factor = (
        1.0
        - 0.17 * math.cos(math.radians(h_bar_p - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * h_bar_p))
        + 0.32 * math.cos(math.radians(3.0 * h_bar_p + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * h_bar_p - 63.0))
    )

    delta_theta = 30.0 * math.exp(-(((h_bar_p - 275.0) / 25.0) ** 2))
    c_bar_p7 = c_bar_p ** 7
    r_c = 2.0 * math.sqrt(c_bar_p7 / (c_bar_p7 + pow25_7))

    l_term = (l_bar_p - 50.0) ** 2
    s_l = 1.0 + (0.015 * l_term) / math.sqrt(20.0 + l_term)
    s_c = 1.0 + 0.045 * c_bar_p
    s_h = 1.0 + 0.015 * c_bar_p * t_factor
    r_t = -math.sin(math.radians(2.0 * delta_theta)) * r_c

    term_l = delta_l_p / (kl * s_l)
    term_c = delta_c_p / (kc * s_c)
    term_h = delta_H_p / (kh * s_h)

    de00_sq = term_l ** 2 + term_c ** 2 + term_h ** 2 + r_t * term_c * term_h
    return math.sqrt(max(0.0, de00_sq))


def _diferencia_angular_deg(h1: float, h2: float) -> float:
    diff = abs((h1 - h2) % 360.0)
    return 360.0 - diff if diff > 180.0 else diff


def _preparar_muestras_lab(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    paso: float = 3.0,
    max_celdas: int = 360,
) -> List[Tuple[Tuple[float, float, float], float]]:
    """Cuantiza los píxeles interiores en celdas Lab con su peso exacto de área."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0

    pad_y = max(0, int(alto * 0.02))
    pad_x = max(0, int(ancho * 0.02))
    y_ini, y_fin = pad_y, max(pad_y + 1, alto - pad_y)
    x_ini, x_fin = pad_x, max(pad_x + 1, ancho - pad_x)
    total_px = float(max(1, (y_fin - y_ini) * (x_fin - x_ini)))

    celdas: Dict[Tuple[int, int, int], List[float]] = {}
    for y in range(y_ini, y_fin):
        fila = pixeles_lab[y]
        for x in range(x_ini, x_fin):
            l_v, a_v, b_v = fila[x]
            clave = (int(round(l_v / paso)), int(round(a_v / paso)), int(round(b_v / paso)))
            acc = celdas.get(clave)
            if acc is None:
                celdas[clave] = [l_v, a_v, b_v, 1.0]
            else:
                acc[0] += l_v
                acc[1] += a_v
                acc[2] += b_v
                acc[3] += 1.0

    muestras: List[Tuple[Tuple[float, float, float], float]] = []
    for acc in celdas.values():
        cnt = acc[3]
        muestras.append(((acc[0] / cnt, acc[1] / cnt, acc[2] / cnt), cnt / total_px))

    muestras.sort(key=lambda x: x[1], reverse=True)
    if len(muestras) > max_celdas:
        # Si hay miles de celdas (p.ej. ruido puro), conservar las más frecuentes + muestreo uniforme del resto
        top = muestras[: max_celdas // 2]
        resto = muestras[max_celdas // 2 :]
        stride = max(1, len(resto) // (max_celdas // 2))
        muestras = top + resto[::stride]
        suma_w = sum(w for _, w in muestras) or 1.0
        muestras = [(pt, w / suma_w) for pt, w in muestras]
    return muestras


def _kmeans_lab_fijo(
    muestras: List[Tuple[Tuple[float, float, float], float]],
    k: int = 5,
    max_iter: int = 18,
    umbral_fusion_de00: float = 2.0,
) -> List[Tuple[Tuple[float, float, float], float]]:
    """Ejecuta k-means en CIE L*a*b* para un K dado minimizando el residuo ponderado."""
    if not muestras:
        return [((90.0, 0.0, 0.0), 1.0)]
    if len(muestras) <= k:
        suma_w = sum(w for _, w in muestras) or 1.0
        return [(pt, w / suma_w) for pt, w in muestras]

    centroides: List[Tuple[float, float, float]] = [muestras[0][0]]
    while len(centroides) < k:
        mejor_pt = muestras[0][0]
        mejor_score = -1.0
        for pt, peso in muestras:
            dist_min_de = min(delta_e2000(pt, c) for c in centroides)
            if dist_min_de < umbral_fusion_de00:
                continue
            score = (peso ** 0.65) * (dist_min_de ** 2.0)
            if score > mejor_score:
                mejor_score = score
                mejor_pt = pt
        if mejor_score <= 1e-7:
            break
        centroides.append(mejor_pt)

    asignaciones = [0] * len(muestras)
    for _ in range(max_iter):
        cambio = False
        for i, (pt, _) in enumerate(muestras):
            mejor_c = 0
            mejor_d = float("inf")
            p0, p1, p2 = pt
            for c_idx, c in enumerate(centroides):
                # Distancia Lab rápida en el bucle interno de Lloyd
                d = (p0 - c[0]) ** 2 + (p1 - c[1]) ** 2 + (p2 - c[2]) ** 2
                if d < mejor_d:
                    mejor_d = d
                    mejor_c = c_idx
            if asignaciones[i] != mejor_c:
                asignaciones[i] = mejor_c
                cambio = True

        nuevos_c: List[Tuple[float, float, float]] = []
        for c_idx in range(len(centroides)):
            sum_l, sum_a, sum_b, sum_w = 0.0, 0.0, 0.0, 0.0
            for i, (pt, w) in enumerate(muestras):
                if asignaciones[i] == c_idx:
                    w_eff = w ** 0.80
                    sum_l += pt[0] * w_eff
                    sum_a += pt[1] * w_eff
                    sum_b += pt[2] * w_eff
                    sum_w += w_eff
            if sum_w > 0.0:
                nuevos_c.append((sum_l / sum_w, sum_a / sum_w, sum_b / sum_w))
            else:
                nuevos_c.append(centroides[c_idx])
        centroides = nuevos_c
        if not cambio:
            break

    # Asignación final exacta usando ΔE2000 y proporción de área exacta (w^1.0)
    clusters_acc = [[0.0, 0.0, 0.0, 0.0] for _ in centroides]
    for pt, w in muestras:
        mejor_c = min(range(len(centroides)), key=lambda idx: delta_e2000(pt, centroides[idx]))
        clusters_acc[mejor_c][0] += pt[0] * w
        clusters_acc[mejor_c][1] += pt[1] * w
        clusters_acc[mejor_c][2] += pt[2] * w
        clusters_acc[mejor_c][3] += w

    clusters: List[Tuple[Tuple[float, float, float], float]] = []
    for sl, sa, sb, sw in clusters_acc:
        if sw > 1e-4:
            clusters.append(((sl / sw, sa / sw, sb / sw), sw))

    clusters.sort(key=lambda x: x[1], reverse=True)

    fusionados: List[Tuple[Tuple[float, float, float], float]] = []
    for c_lab, w in clusters:
        unido = False
        for j, (ex_lab, ex_w) in enumerate(fusionados):
            if delta_e2000(c_lab, ex_lab) < umbral_fusion_de00:
                tot_w = ex_w + w
                nuevo_lab = (
                    (ex_lab[0] * ex_w + c_lab[0] * w) / tot_w,
                    (ex_lab[1] * ex_w + c_lab[1] * w) / tot_w,
                    (ex_lab[2] * ex_w + c_lab[2] * w) / tot_w,
                )
                fusionados[j] = (nuevo_lab, tot_w)
                unido = True
                break
        if not unido:
            fusionados.append((c_lab, w))

    suma_total = sum(w for _, w in fusionados) or 1.0
    fusionados = [(lab, w / suma_total) for lab, w in fusionados]
    fusionados.sort(key=lambda x: x[1], reverse=True)
    return fusionados


def evaluar_residuo_paleta_srgb(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    clusters: List[Tuple[Tuple[float, float, float], float]],
    muestras_ponderadas: Optional[List[Tuple[Tuple[float, float, float], float]]] = None,
) -> Tuple[float, float]:
    """Calcula la ΔE2000 media y desviación típica de los píxeles frente a su color de paleta
    reconvertido a sRGB (Lab -> sRGB -> Lab).
    """
    if not clusters or not pixeles_lab:
        return 0.0, 0.0

    centroides_srgb_lab: List[Tuple[float, float, float]] = []
    for c_lab, _ in clusters:
        r_u8, g_u8, b_u8 = lab_a_srgb_u8(c_lab[0], c_lab[1], c_lab[2])
        centroides_srgb_lab.append(srgb_a_lab(r_u8, g_u8, b_u8))

    if muestras_ponderadas is not None:
        media = 0.0
        dists_w: List[Tuple[float, float]] = []
        for pt, w in muestras_ponderadas:
            d_min = min(delta_e2000(pt, c_rt) for c_rt in centroides_srgb_lab)
            media += d_min * w
            dists_w.append((d_min, w))
        var = sum(w * ((d - media) ** 2) for d, w in dists_w)
        return media, math.sqrt(max(0.0, var))

    # Evaluación exacta sobre el 100% de los píxeles de la rejilla con caché por triplete Lab
    errores: List[float] = []
    cache_dist: Dict[Tuple[int, int, int], float] = {}
    for fila in pixeles_lab:
        for px in fila:
            k_px = (int(round(px[0] * 20)), int(round(px[1] * 20)), int(round(px[2] * 20)))
            d_min = cache_dist.get(k_px)
            if d_min is None:
                d_min = min(delta_e2000(px, c_rt) for c_rt in centroides_srgb_lab)
                cache_dist[k_px] = d_min
            errores.append(d_min)

    n = float(max(1, len(errores)))
    media = sum(errores) / n
    var = sum((e - media) ** 2 for e in errores) / n
    return media, math.sqrt(max(0.0, var))


def _kmeans_lab_adaptativo(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    k_min: int = 3,
    k_max: int = 10,
    umbral_de00: float = 5.0,
    k_fijo: Optional[int] = None,
) -> Tuple[List[Tuple[Tuple[float, float, float], float]], int, float, float, bool]:
    """Crece K desde k_min (3) hasta k_max (10) hasta que la ΔE2000 media de los píxeles
    frente a su color de paleta reconvertido a sRGB sea < umbral_de00 (5.0), o hasta K=10.
    """
    muestras = _preparar_muestras_lab(pixeles_lab, paso=2.5, max_celdas=360)

    if k_fijo is not None:
        clusters = _kmeans_lab_fijo(muestras, k=k_fijo)
        de_medio, de_std = evaluar_residuo_paleta_srgb(pixeles_lab, clusters)
        insuficiente = de_medio >= umbral_de00
        return clusters, k_fijo, de_medio, de_std, insuficiente

    mejor_clusters: List[Tuple[Tuple[float, float, float], float]] = []
    mejor_k = k_min
    mejor_de_medio = float("inf")
    mejor_de_std = 0.0

    for k_cand in range(k_min, k_max + 1):
        clusters = _kmeans_lab_fijo(muestras, k=k_cand)
        de_medio, de_std = evaluar_residuo_paleta_srgb(pixeles_lab, clusters)
        if de_medio < mejor_de_medio:
            mejor_clusters = clusters
            mejor_k = k_cand
            mejor_de_medio = de_medio
            mejor_de_std = de_std
        if de_medio < umbral_de00:
            return clusters, k_cand, de_medio, de_std, False

    return mejor_clusters, k_max, mejor_de_medio, mejor_de_std, (mejor_de_medio >= umbral_de00)


def _clasificar_armonia(colores_info: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Clasifica la armonía cromática a partir de los ángulos de tono h_ab y croma C*ab."""
    cromaticos = [
        c for c in colores_info if c["lch"]["C"] >= 9.0 and c["proporcion"] >= 0.015
    ]
    peso_cromatico = sum(c["proporcion"] for c in cromaticos)

    if not cromaticos or peso_cromatico < 0.08:
        return {
            "tipo": "acromatica",
            "diferencia_angular_principal_deg": 0.0,
            "explicacion": "Predominio de valores neutros/acromáticos (C*ab < 9) basados en contraste de luminosidad L*.",
        }

    if len(cromaticos) == 1:
        return {
            "tipo": "monocromatica",
            "diferencia_angular_principal_deg": 0.0,
            "explicacion": "Un único eje cromático dominante acompañado de neutros.",
        }

    h0 = cromaticos[0]["lch"]["h_deg"]
    h1 = cromaticos[1]["lch"]["h_deg"]
    diff_principal = _diferencia_angular_deg(h0, h1)

    max_diff = 0.0
    for i in range(len(cromaticos)):
        for j in range(i + 1, len(cromaticos)):
            d = _diferencia_angular_deg(cromaticos[i]["lch"]["h_deg"], cromaticos[j]["lch"]["h_deg"])
            if d > max_diff:
                max_diff = d

    if max_diff < 22.0:
        return {
            "tipo": "monocromatica",
            "diferencia_angular_principal_deg": round(diff_principal, 2),
            "explicacion": f"Variaciones de luminosidad y croma dentro de un cono estrecho de tono (Δh máx = {max_diff:.1f}°).",
        }
    if max_diff <= 68.0:
        return {
            "tipo": "analoga",
            "diferencia_angular_principal_deg": round(diff_principal, 2),
            "explicacion": f"Tonos contiguos en el círculo perceptual CIE L*C*h (Δh principal = {diff_principal:.1f}°, máx = {max_diff:.1f}°).",
        }
    if 150.0 <= diff_principal <= 180.0:
        return {
            "tipo": "complementaria",
            "diferencia_angular_principal_deg": round(diff_principal, 2),
            "explicacion": f"Oposición polar directa entre los dos tonos cromáticos principales (Δh = {diff_principal:.1f}°).",
        }
    if len(cromaticos) >= 3:
        h2 = cromaticos[2]["lch"]["h_deg"]
        d01 = _diferencia_angular_deg(h0, h1)
        d02 = _diferencia_angular_deg(h0, h2)
        d12 = _diferencia_angular_deg(h1, h2)
        if all(85.0 <= d <= 150.0 for d in (d01, d02, d12)):
            return {
                "tipo": "triada",
                "diferencia_angular_principal_deg": round(diff_principal, 2),
                "explicacion": f"Triángulo cromático equilibrado en CIE L*C*h ({d01:.1f}°, {d02:.1f}°, {d12:.1f}°).",
            }
        if 115.0 <= max(d01, d02) <= 165.0:
            return {
                "tipo": "complementaria_dividida",
                "diferencia_angular_principal_deg": round(diff_principal, 2),
                "explicacion": f"Tono dominante contrapuesto a un par desdoblado (Δh principal = {diff_principal:.1f}°).",
            }

    if 115.0 <= diff_principal < 150.0:
        return {
            "tipo": "complementaria_dividida",
            "diferencia_angular_principal_deg": round(diff_principal, 2),
            "explicacion": f"Contraste cromático oblicuo de alta tensión (Δh = {diff_principal:.1f}°).",
        }

    return {
        "tipo": "policromatica_compleja",
        "diferencia_angular_principal_deg": round(diff_principal, 2),
        "explicacion": f"Distribución multi-tono abierta (Δh principal = {diff_principal:.1f}°, rango = {max_diff:.1f}°).",
    }


def estudiar_color(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    k: Optional[int] = None,
    k_min: int = 3,
    k_max: int = 10,
    umbral_de00: float = 5.0,
) -> Tuple[Dict[str, Any], float]:
    """Produce el bloque 'paleta' de estudio.json con K adaptativo (3..10) y confianza continua."""
    clusters, k_elegido, de_medio_px, de_std_px, paleta_insuficiente = _kmeans_lab_adaptativo(
        pixeles_lab,
        k_min=k_min,
        k_max=k_max,
        umbral_de00=umbral_de00,
        k_fijo=k,
    )
    n_col = len(clusters)

    idx_mas_claro = max(range(n_col), key=lambda i: clusters[i][0][0])
    idx_mas_oscuro = min(range(n_col), key=lambda i: clusters[i][0][0])
    idx_mas_saturado = max(
        range(n_col),
        key=lambda i: math.hypot(clusters[i][0][1], clusters[i][0][2]),
    )

    colores_out: List[Dict[str, Any]] = []
    for i, (lab, prop) in enumerate(clusters):
        l_v, a_v, b_v = lab
        l_r, c_r, h_r = lab_a_lch(l_v, a_v, b_v)
        if i == 0:
            rol = "dominante"
        elif i == 1:
            rol = "secundario"
        elif i == idx_mas_saturado and c_r >= 18.0:
            rol = "acento"
        elif i == idx_mas_oscuro and l_v < 35.0:
            rol = "tinta_oscura"
        elif i == idx_mas_claro and l_v > 72.0:
            rol = "fondo_papel"
        else:
            rol = "apoyo"

        colores_out.append(
            {
                "id": f"c{i}",
                "rol": rol,
                "lab": {
                    "L": round(l_v, 3),
                    "a": round(a_v, 3),
                    "b": round(b_v, 3),
                },
                "lch": {
                    "L": round(l_r, 3),
                    "C": round(c_r, 3),
                    "h_deg": round(h_r, 2),
                },
                "proporcion": round(prop, 4),
            }
        )

    if colores_out:
        diff_suma = round(1.0 - sum(c["proporcion"] for c in colores_out), 4)
        colores_out[0]["proporcion"] = round(colores_out[0]["proporcion"] + diff_suma, 4)

    matriz_de00: List[List[float]] = []
    pares_de00: List[Dict[str, Any]] = []
    max_de00 = 0.0
    for i in range(n_col):
        fila_de: List[float] = []
        for j in range(n_col):
            if i == j:
                fila_de.append(0.0)
            else:
                de = round(delta_e2000(clusters[i][0], clusters[j][0]), 3)
                fila_de.append(de)
                if i < j:
                    dl = round(abs(clusters[i][0][0] - clusters[j][0][0]), 3)
                    pares_de00.append(
                        {
                            "par": [f"c{i}", f"c{j}"],
                            "delta_e2000": de,
                            "delta_L": dl,
                        }
                    )
                    if de > max_de00:
                        max_de00 = de
        matriz_de00.append(fila_de)

    valores_l = [c[0][0] for c in clusters]
    rango_l = max(valores_l) - min(valores_l) if valores_l else 0.0
    contraste_dom_sec_l = abs(clusters[0][0][0] - clusters[1][0][0]) if n_col >= 2 else 0.0
    media_l = sum(c[0][0] * c[1] for c in clusters)
    var_l = sum(c[1] * ((c[0][0] - media_l) ** 2) for c in clusters)
    std_l = math.sqrt(max(0.0, var_l))

    if rango_l >= 48.0 and std_l >= 14.0:
        clave_tonal = "alto_contraste"
    elif media_l >= 68.0:
        clave_tonal = "alta"
    elif media_l <= 35.0:
        clave_tonal = "baja"
    else:
        clave_tonal = "media"

    indice_calidez = sum(w * (0.75 * lab[2] + 0.25 * lab[1]) for lab, w in clusters)
    prop_calidos = 0.0
    prop_frios = 0.0
    for c in colores_out:
        c_val = c["lch"]["C"]
        h_val = c["lch"]["h_deg"]
        if c_val >= 6.0:
            if h_val <= 115.0 or h_val >= 325.0:
                prop_calidos += c["proporcion"]
            else:
                prop_frios += c["proporcion"]

    if prop_calidos >= 0.15 and prop_frios >= 0.15:
        clasif_temp = "contraste_termico"
    elif indice_calidez >= 4.0:
        clasif_temp = "calida"
    elif indice_calidez <= -4.0:
        clasif_temp = "fria"
    else:
        clasif_temp = "neutra"

    croma_medio = sum(c["lch"]["C"] * c["proporcion"] for c in colores_out)
    croma_max = max((c["lch"]["C"] for c in colores_out), default=0.0)
    if croma_medio < 14.0:
        clasif_sat = "apagada_editorial"
    elif croma_medio <= 32.0:
        clasif_sat = "moderada"
    else:
        clasif_sat = "viva"

    armonia = _clasificar_armonia(colores_out)

    # Fórmula continua de confianza (Ley 8): basada en el residuo real de cuantización ΔE2000
    # y la dispersión de error por píxel. Cae hacia 0 con ruido aleatorio y sube hacia ~0.98 con colores planos.
    factor_residuo = math.exp(-de_medio_px / 9.5)
    factor_dispersion = 1.0 / (1.0 + (de_std_px / 10.0))
    confianza_continua = max(0.0, min(1.0, factor_residuo * (0.70 + 0.30 * factor_dispersion)))

    bloque_paleta = {
        "espacio_color": "CIE_L*a*b*_D65_2deg",
        "metodo": "kmeans_lab_adaptativo_ponderado_area" if k is None else "kmeans_lab_ponderado_area",
        "k_rango_evaluado": [k_min, k_max] if k is None else [k, k],
        "k_elegido": k_elegido,
        "num_colores": n_col,
        "umbral_delta_e2000_objetivo": umbral_de00,
        "delta_e2000_cuantizacion_media": round(de_medio_px, 3),
        "delta_e2000_cuantizacion_std": round(de_std_px, 3),
        "paleta_insuficiente": bool(paleta_insuficiente),
        "colores": colores_out,
        "pares_delta_e2000": pares_de00,
        "matriz_delta_e2000": matriz_de00,
        "armonia": armonia,
        "contraste_valores": {
            "rango_L": round(rango_l, 3),
            "contraste_dominante_secundario_L": round(contraste_dom_sec_l, 3),
            "contraste_max_delta_e2000": round(max_de00, 3),
            "media_L_ponderada": round(media_l, 3),
            "desviacion_L_ponderada": round(std_l, 3),
            "clave_tonal": clave_tonal,
        },
        "temperatura": {
            "indice_calidez_lab": round(indice_calidez, 3),
            "clasificacion": clasif_temp,
            "proporcion_calidos": round(prop_calidos, 4),
            "proporcion_frios": round(prop_frios, 4),
        },
        "saturacion_media": {
            "croma_medio_C": round(croma_medio, 3),
            "croma_max_C": round(croma_max, 3),
            "clasificacion": clasif_sat,
        },
    }

    return bloque_paleta, round(confianza_continua, 4)
