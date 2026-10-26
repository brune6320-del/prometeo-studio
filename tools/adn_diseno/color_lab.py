#!/usr/bin/env python3
"""Motor cromático en CIE L*a*b* (D65, 2°): k-means con pesos por área y ΔE2000 (CIEDE2000).

Nunca emite ni opera sobre RGB crudo. Calcula proporción de cada color, matriz y pares ΔE2000,
armonía cromática en ángulo de tono h_ab, contraste de valores L*, temperatura y saturación C*ab.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


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


def _kmeans_lab_ponderado(
    pixeles_lab: List[List[Tuple[float, float, float]]],
    k: int = 5,
    max_iter: int = 25,
) -> List[Tuple[Tuple[float, float, float], float]]:
    """Ejecuta k-means determinista con pesos por área en espacio CIE L*a*b*."""
    alto = len(pixeles_lab)
    ancho = len(pixeles_lab[0]) if alto > 0 else 0

    # Ignorar el 2% exterior si hay reborde de escaneo para no distorsionar la paleta
    pad_y = max(0, int(alto * 0.02))
    pad_x = max(0, int(ancho * 0.02))
    y_ini, y_fin = pad_y, max(pad_y + 1, alto - pad_y)
    x_ini, x_fin = pad_x, max(pad_x + 1, ancho - pad_x)
    total_px = float(max(1, (y_fin - y_ini) * (x_fin - x_ini)))

    # 1. Agrupar píxeles en celdas cuantizadas de Lab (paso 3.0 unidades) con peso exacto de área
    celdas: Dict[Tuple[int, int, int], List[float]] = {}
    paso = 3.0
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
    if len(muestras) <= k:
        return muestras

    # 2. Inicialización k-means++ perceptual usando ΔE2000 para garantizar cobertura de tintas/acentos
    centroides: List[Tuple[float, float, float]] = [muestras[0][0]]
    while len(centroides) < k:
        mejor_pt = muestras[0][0]
        mejor_score = -1.0
        for pt, peso in muestras:
            if peso < 0.0015:
                continue
            dist_min_de = min(delta_e2000(pt, c) for c in centroides)
            if dist_min_de < 10.0:
                continue
            score = (peso ** 0.22) * (dist_min_de ** 1.65)
            if score > mejor_score:
                mejor_score = score
                mejor_pt = pt
        if mejor_score <= 1e-6:
            break
        centroides.append(mejor_pt)

    # 3. Iteraciones de Lloyd ponderadas por área
    asignaciones = [0] * len(muestras)
    for _ in range(max_iter):
        cambio = False
        for i, (pt, _) in enumerate(muestras):
            mejor_c = 0
            mejor_d = float("inf")
            for c_idx, c in enumerate(centroides):
                d = (pt[0] - c[0]) ** 2 + (pt[1] - c[1]) ** 2 + (pt[2] - c[2]) ** 2
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
                    sum_l += pt[0] * w
                    sum_a += pt[1] * w
                    sum_b += pt[2] * w
                    sum_w += w
            if sum_w > 0.0:
                nuevos_c.append((sum_l / sum_w, sum_a / sum_w, sum_b / sum_w))
            else:
                nuevos_c.append(centroides[c_idx])
        centroides = nuevos_c
        if not cambio:
            break

    # 4. Calcular pesos por clúster y fusionar clústeres cercanos (ΔE2000 < 8.5)
    pesos_cluster = [0.0] * len(centroides)
    for i, (_, w) in enumerate(muestras):
        pesos_cluster[asignaciones[i]] += w

    clusters = [
        (centroides[idx], pesos_cluster[idx])
        for idx in range(len(centroides))
        if pesos_cluster[idx] > 1e-4
    ]
    clusters.sort(key=lambda x: x[1], reverse=True)

    fusionados: List[Tuple[Tuple[float, float, float], float]] = []
    for c_lab, w in clusters:
        unido = False
        for j, (ex_lab, ex_w) in enumerate(fusionados):
            if delta_e2000(c_lab, ex_lab) < 8.5:
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
    k: int = 5,
) -> Tuple[Dict[str, Any], float]:
    """Produce el bloque 'paleta' de estudio.json y su puntuación de confianza."""
    clusters = _kmeans_lab_ponderado(pixeles_lab, k=k)
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

    bloque_paleta = {
        "espacio_color": "CIE_L*a*b*_D65_2deg",
        "metodo": "kmeans_lab_ponderado_area",
        "num_colores": n_col,
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

    confianza = 0.96 if n_col >= 2 else 0.85
    return bloque_paleta, confianza
