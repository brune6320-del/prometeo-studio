#!/usr/bin/env python3
"""medir.py — Batería de pruebas y validación relacional de ADN de Diseño (D-11 / D-11b).

Verifica (7/7 pruebas):
1. Exactitud matemática de CIEDE2000 (ΔE2000, Sharma et al. 2005) y contrato ESQUEMA.md v1.1.0.
2. Par sintético 1 (Mismo diseño, otra paleta): reconoce que cambió la paleta Lab (ΔE2000 alto)
   y que NO cambiaron la retícula, el vacío ni la jerarquía.
3. Par sintético 2 (Mismo diseño, desplazado): reconoce que NO cambió la paleta Lab (ΔE2000 ~ 0)
   ni las razones de tamaño, y que SÍ cambiaron la retícula, márgenes, centro de peso y saliencia.
4. La prueba que de verdad importa (Cambio de contenido: título más largo + imagen vertical):
   al proponer ajustes con aplicar.py sobre un contenido nuevo (título largo e imagen vertical),
   las relaciones del referente se mantienen mientras la imagen sigue siendo vertical y el título largo cabe.
5. Validación estructural del contrato v1.1.0 sobre muestras reales del corpus abierto D-3.
6. [D-11b Nuevo] Confianza continua (Ley 8, ningún número fijo): comprueba que la confianza BAJA
   en los 6 bloques con una imagen de ruido aleatorio y SUBE con una imagen limpia de 3 colores planos.
7. [D-11b Nuevo] Fidelidad cromática con K adaptativo (3..10) y registro de negativos ("paleta_insuficiente"):
   compara K=5 fijo vs K adaptativo (3..10) sobre los 5 carteles de D-3 y verifica que cuando un cartel
   con degradados continuos/salpicadura supera ΔE2000=5.0 incluso en K=10 (p.ej. met_335536.jpg / wikimedia_ed_03.jpg),
   se declara explícitamente "paleta_insuficiente": true como negativo sin esconderlo.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .aplicar import proponer_cambios
from .color_lab import delta_e2000
from .esquema import validar_estudio
from .estudiar import estudiar_lienzo, estudiar_referente
from .lector import LienzoLab, escribir_bmp_desde_lab, srgb_a_lab


def _crear_lienzo_sintetico(
    ancho: int,
    alto: int,
    fondo_lab: Tuple[float, float, float],
    bloques: List[Dict[str, Any]],
    id_ref: str = "sintetico",
) -> LienzoLab:
    """Renderiza una lista de bloques sobre una matriz CIE L*a*b* de tamaño alto x ancho."""
    mat: List[List[Tuple[float, float, float]]] = [
        [fondo_lab for _ in range(ancho)] for _ in range(alto)
    ]
    for b in bloques:
        x0 = max(0, min(ancho - 1, int(round(float(b["x_rel"]) * ancho))))
        y0 = max(0, min(alto - 1, int(round(float(b["y_rel"]) * alto))))
        x1 = max(x0 + 1, min(ancho, int(round((float(b["x_rel"]) + float(b["w_rel"])) * ancho))))
        y1 = max(y0 + 1, min(alto, int(round((float(b["y_rel"]) + float(b["h_rel"])) * alto))))
        c_lab: Tuple[float, float, float] = tuple(b["lab"])  # type: ignore
        es_texto = bool(b.get("simular_lineas_texto", False))

        for y in range(y0, y1):
            for x in range(x0, x1):
                if es_texto:
                    if ((y - y0) % 4 != 3) and ((x - x0) % 3 != 2):
                        mat[y][x] = c_lab
                else:
                    mat[y][x] = c_lab

    return LienzoLab(
        id_referente=id_ref,
        tipo_entrada="imagen",
        sha256_origen="0" * 64,
        ancho_original=ancho,
        alto_original=alto,
        ancho_analisis=ancho,
        alto_analisis=alto,
        pixeles_lab=mat,
        metadatos_extra={"sintetico": True},
    )


def probar_ciede2000_sharma() -> Dict[str, Any]:
    """1. Comprueba la fórmula ΔE2000 frente a los pares de referencia de Sharma et al. (2005) Tabla 1."""
    casos = [
        ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
        ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
        ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ]
    max_err = 0.0
    for lab1, lab2, esp in casos:
        calc = delta_e2000(lab1, lab2)
        err = abs(calc - esp)
        if err > max_err:
            max_err = err
    exito = max_err < 1e-3
    return {
        "prueba": "exactitud_ciede2000_sharma_2005",
        "exito": exito,
        "error_maximo": round(max_err, 6),
    }


def probar_par_sintetico_paleta() -> Dict[str, Any]:
    """2. Par sintético 1: Mismo diseño geométrico con dos paletas opuestas (cálida vs fría)."""
    ancho, alto = 128, 160
    fondo_calido = (88.0, 2.0, 16.0)
    bloques_calidos = [
        {"x_rel": 0.10, "y_rel": 0.10, "w_rel": 0.80, "h_rel": 0.12, "lab": (18.0, 4.0, 4.0), "simular_lineas_texto": True},
        {"x_rel": 0.10, "y_rel": 0.28, "w_rel": 0.48, "h_rel": 0.46, "lab": (42.0, 46.0, 28.0)},
        {"x_rel": 0.64, "y_rel": 0.28, "w_rel": 0.26, "h_rel": 0.26, "lab": (68.0, 14.0, 54.0)},
    ]

    fondo_frio = (88.0, -5.0, -14.0)
    bloques_frios = [
        {"x_rel": 0.10, "y_rel": 0.10, "w_rel": 0.80, "h_rel": 0.12, "lab": (18.0, -2.0, -18.0), "simular_lineas_texto": True},
        {"x_rel": 0.10, "y_rel": 0.28, "w_rel": 0.48, "h_rel": 0.46, "lab": (40.0, 10.0, -50.0)},
        {"x_rel": 0.64, "y_rel": 0.28, "w_rel": 0.26, "h_rel": 0.26, "lab": (66.0, -34.0, -12.0)},
    ]

    with tempfile.TemporaryDirectory(prefix="adn_par_paleta_") as tmp:
        p1 = Path(tmp) / "calido.bmp"
        p2 = Path(tmp) / "frio.bmp"
        l1 = _crear_lienzo_sintetico(ancho, alto, fondo_calido, bloques_calidos, "calido")
        l2 = _crear_lienzo_sintetico(ancho, alto, fondo_frio, bloques_frios, "frio")
        escribir_bmp_desde_lab(p1, l1.pixeles_lab)
        escribir_bmp_desde_lab(p2, l2.pixeles_lab)

        est1 = estudiar_referente(p1, max_dim_analisis=160)
        est2 = estudiar_referente(p2, max_dim_analisis=160)

    c1_dom = est1["paleta"]["colores"][0]["lab"]
    c2_dom = est2["paleta"]["colores"][0]["lab"]
    de_dom = delta_e2000(
        (c1_dom["L"], c1_dom["a"], c1_dom["b"]),
        (c2_dom["L"], c2_dom["a"], c2_dom["b"]),
    )
    c1_sec = est1["paleta"]["colores"][1]["lab"]
    c2_sec = est2["paleta"]["colores"][1]["lab"]
    de_sec = delta_e2000(
        (c1_sec["L"], c1_sec["a"], c1_sec["b"]),
        (c2_sec["L"], c2_sec["a"], c2_sec["b"]),
    )
    temp_cambio = est1["paleta"]["temperatura"]["clasificacion"] != est2["paleta"]["temperatura"]["clasificacion"]

    diff_aire = abs(est1["vacio"]["porcentaje_aire"] - est2["vacio"]["porcentaje_aire"])
    cp1 = est1["vacio"]["centro_peso_visual"]
    cp2 = est2["vacio"]["centro_peso_visual"]
    dist_centro_peso = math.hypot(cp1["x_rel"] - cp2["x_rel"], cp1["y_rel"] - cp2["y_rel"])

    r1 = est1["jerarquia"]["razones_tamano"]
    r2 = est2["jerarquia"]["razones_tamano"]
    n_r = min(len(r1), len(r2))
    diff_jerarquia = max((abs(r1[i] - r2[i]) for i in range(n_r)), default=0.0)

    m1 = est1["reticula"]["margenes"]
    m2 = est2["reticula"]["margenes"]
    diff_margenes = max(
        abs(m1["izquierdo_rel"] - m2["izquierdo_rel"]),
        abs(m1["superior_rel"] - m2["superior_rel"]),
    )

    reconocio_cambio_paleta = (max(de_dom, de_sec) > 20.0) and temp_cambio
    mantuvo_composicion = (diff_aire < 3.0) and (dist_centro_peso < 0.035) and (diff_jerarquia < 0.06) and (diff_margenes < 0.02)

    return {
        "prueba": "par_sintetico_cambio_paleta",
        "exito": bool(reconocio_cambio_paleta and mantuvo_composicion),
        "reconocio_cambio_paleta": bool(reconocio_cambio_paleta),
        "mantuvo_composicion_invariante": bool(mantuvo_composicion),
        "metricas": {
            "delta_e2000_dominante": round(de_dom, 3),
            "delta_e2000_secundario": round(de_sec, 3),
            "temperatura_1": est1["paleta"]["temperatura"]["clasificacion"],
            "temperatura_2": est2["paleta"]["temperatura"]["clasificacion"],
            "diferencia_porcentaje_aire": round(diff_aire, 3),
            "distancia_centro_peso_visual": round(dist_centro_peso, 4),
            "diferencia_max_razones_jerarquia": round(diff_jerarquia, 4),
            "diferencia_max_margenes": round(diff_margenes, 4),
        },
    }


def probar_par_sintetico_desplazado() -> Dict[str, Any]:
    """3. Par sintético 2: Misma paleta y mismos tamaños de bloque, pero desplazados de lugar."""
    ancho, alto = 128, 160
    fondo = (88.0, 2.0, 16.0)

    bloques_a = [
        {"x_rel": 0.08, "y_rel": 0.08, "w_rel": 0.50, "h_rel": 0.42, "lab": (38.0, 44.0, 26.0)},
        {"x_rel": 0.08, "y_rel": 0.54, "w_rel": 0.32, "h_rel": 0.16, "lab": (18.0, 2.0, 2.0)},
    ]
    bloques_b = [
        {"x_rel": 0.42, "y_rel": 0.32, "w_rel": 0.50, "h_rel": 0.42, "lab": (38.0, 44.0, 26.0)},
        {"x_rel": 0.60, "y_rel": 0.78, "w_rel": 0.32, "h_rel": 0.16, "lab": (18.0, 2.0, 2.0)},
    ]

    est_a = estudiar_lienzo(_crear_lienzo_sintetico(ancho, alto, fondo, bloques_a, "pos_a"))
    est_b = estudiar_lienzo(_crear_lienzo_sintetico(ancho, alto, fondo, bloques_b, "pos_b"))

    cols_a = est_a["paleta"]["colores"]
    cols_b = est_b["paleta"]["colores"]
    n_c = min(len(cols_a), len(cols_b))
    max_de_paleta = max(
        delta_e2000(
            (cols_a[i]["lab"]["L"], cols_a[i]["lab"]["a"], cols_a[i]["lab"]["b"]),
            (cols_b[i]["lab"]["L"], cols_b[i]["lab"]["a"], cols_b[i]["lab"]["b"]),
        )
        for i in range(n_c)
    )
    diff_aire = abs(est_a["vacio"]["porcentaje_aire"] - est_b["vacio"]["porcentaje_aire"])
    diff_razon_tam = abs(
        est_a["jerarquia"]["razones_tamano"][1] - est_b["jerarquia"]["razones_tamano"][1]
    )

    cpa = est_a["vacio"]["centro_peso_visual"]
    cpb = est_b["vacio"]["centro_peso_visual"]
    salto_centro_peso = math.hypot(cpa["x_rel"] - cpb["x_rel"], cpa["y_rel"] - cpb["y_rel"])

    ma = est_a["reticula"]["margenes"]
    mb = est_b["reticula"]["margenes"]
    salto_margen_izq = abs(ma["izquierdo_rel"] - mb["izquierdo_rel"])

    fpa = est_a["saliencia"]["foco_primario"]
    fpb = est_b["saliencia"]["foco_primario"]
    salto_saliencia = math.hypot(fpa["x_rel"] - fpb["x_rel"], fpa["y_rel"] - fpb["y_rel"])

    mantuvo_paleta_y_escala = (max_de_paleta < 1.5) and (diff_aire < 1.5) and (diff_razon_tam < 0.03)
    reconocio_desplazamiento = (salto_centro_peso > 0.20) and (salto_margen_izq > 0.25) and (salto_saliencia > 0.12)

    return {
        "prueba": "par_sintetico_desplazamiento",
        "exito": bool(mantuvo_paleta_y_escala and reconocio_desplazamiento),
        "mantuvo_paleta_y_escala": bool(mantuvo_paleta_y_escala),
        "reconocio_desplazamiento_espacial": bool(reconocio_desplazamiento),
        "metricas": {
            "delta_e2000_max_paleta": round(max_de_paleta, 4),
            "diferencia_porcentaje_aire": round(diff_aire, 3),
            "diferencia_razon_tamano_r2": round(diff_razon_tam, 4),
            "salto_centro_peso_visual": round(salto_centro_peso, 4),
            "salto_margen_izquierdo": round(salto_margen_izq, 4),
            "salto_foco_saliencia": round(salto_saliencia, 4),
        },
    }


def probar_transferencia_contenido_cambiado() -> Dict[str, Any]:
    """4. LA PRUEBA QUE DE VERDAD IMPORTA:
    Cambiar el contenido (título mucho más largo + imagen vertical en lugar de horizontal)
    y comprobar que aplicar.py propone una composición que mantiene las relaciones del referente.
    """
    ancho, alto = 128, 160
    fondo_ref = (86.0, 3.0, 18.0)
    bloques_ref = [
        {"x_rel": 0.12, "y_rel": 0.10, "w_rel": 0.76, "h_rel": 0.36, "lab": (36.0, 48.0, 28.0)},
        {"x_rel": 0.12, "y_rel": 0.52, "w_rel": 0.45, "h_rel": 0.12, "lab": (15.0, 1.0, 2.0), "simular_lineas_texto": True},
        {"x_rel": 0.12, "y_rel": 0.70, "w_rel": 0.36, "h_rel": 0.08, "lab": (64.0, 12.0, 48.0)},
    ]
    estudio_ref = estudiar_lienzo(_crear_lienzo_sintetico(ancho, alto, fondo_ref, bloques_ref, "referente_bauhaus"))

    tablero_nuevo = {
        "lienzo": {"ancho": 1000, "alto": 1400},
        "fondo": {"lab": {"L": 50.0, "a": -25.0, "b": -30.0}},
        "elementos": [
            {
                "id": "img_vertical_nueva",
                "rol": "imagen",
                "x": 20,
                "y": 20,
                "ancho": 240,
                "alto": 500,
                "lab": {"L": 70.0, "a": -40.0, "b": 10.0},
            },
            {
                "id": "titulo_largo_nuevo",
                "rol": "titulo",
                "texto": "EXPOSICIÓN INTERNACIONAL DE ARQUITECTURA, DISEÑO EDITORIAL Y TIPOGRAFÍA MODERNA",
                "x": 500,
                "y": 900,
                "ancho": 450,
                "alto": 380,
                "lab": {"L": 60.0, "a": 30.0, "b": -40.0},
            },
            {
                "id": "subtitulo_nuevo",
                "rol": "acento",
                "texto": "Pabellón Central · Octubre 2026",
                "x": 10,
                "y": 1280,
                "ancho": 380,
                "alto": 110,
                "lab": {"L": 30.0, "a": -10.0, "b": -20.0},
            },
        ],
    }

    copia_seguridad = copy.deepcopy(tablero_nuevo)
    propuesta = proponer_cambios(tablero_nuevo, estudio_ref)

    no_destructivo = (tablero_nuevo == copia_seguridad) and (propuesta["aplicado_automaticamente"] is False)

    preview = propuesta["previsualizacion_tablero_propuesto"]
    elems_p = {e["id"]: e for e in preview["elementos"]}
    img_p = elems_p["img_vertical_nueva"]
    tit_p = elems_p["titulo_largo_nuevo"]
    sub_p = elems_p["subtitulo_nuevo"]

    imagen_sigue_vertical = float(img_p["ancho_rel"]) < float(img_p["alto_rel"])
    titulo_respeta_margenes = (
        float(tit_p["x_rel"]) >= estudio_ref["reticula"]["margenes"]["izquierdo_rel"] - 0.02
        and (float(tit_p["x_rel"]) + float(tit_p["ancho_rel"]))
        <= 1.0 - estudio_ref["reticula"]["margenes"]["derecho_rel"] + 0.02
    )

    bloques_prop = [
        {
            "x_rel": img_p["x_rel"],
            "y_rel": img_p["y_rel"],
            "w_rel": img_p["ancho_rel"],
            "h_rel": img_p["alto_rel"],
            "lab": (img_p["lab"]["L"], img_p["lab"]["a"], img_p["lab"]["b"]),
        },
        {
            "x_rel": tit_p["x_rel"],
            "y_rel": tit_p["y_rel"],
            "w_rel": tit_p["ancho_rel"],
            "h_rel": tit_p["alto_rel"],
            "lab": (tit_p["lab"]["L"], tit_p["lab"]["a"], tit_p["lab"]["b"]),
            "simular_lineas_texto": True,
        },
        {
            "x_rel": sub_p["x_rel"],
            "y_rel": sub_p["y_rel"],
            "w_rel": sub_p["ancho_rel"],
            "h_rel": sub_p["alto_rel"],
            "lab": (sub_p["lab"]["L"], sub_p["lab"]["a"], sub_p["lab"]["b"]),
        },
    ]
    f_prop = preview["fondo"]["lab"]
    estudio_post = estudiar_lienzo(
        _crear_lienzo_sintetico(ancho, alto, (f_prop["L"], f_prop["a"], f_prop["b"]), bloques_prop, "propuesto")
    )

    diag = propuesta["resumen_diagnostico"]
    mejora_paleta = diag["delta_e2000_medio_paleta_propuesto"] < 1.0 and (
        diag["delta_e2000_medio_paleta_antes"] > 15.0
    )
    mejora_jerarquia = diag["error_medio_razones_jerarquia_propuesto"] < diag["error_medio_razones_jerarquia_antes"]
    misma_temperatura = (
        estudio_post["paleta"]["temperatura"]["clasificacion"]
        == estudio_ref["paleta"]["temperatura"]["clasificacion"]
    )
    contraste_conservado = (
        abs(
            estudio_post["paleta"]["contraste_valores"]["rango_L"]
            - estudio_ref["paleta"]["contraste_valores"]["rango_L"]
        )
        < 8.0
    )

    exito = (
        no_destructivo
        and imagen_sigue_vertical
        and titulo_respeta_margenes
        and mejora_paleta
        and mejora_jerarquia
        and misma_temperatura
        and contraste_conservado
    )

    return {
        "prueba": "transferencia_relaciones_con_cambio_de_contenido",
        "exito": bool(exito),
        "no_destructivo": bool(no_destructivo),
        "imagen_sigue_vertical": bool(imagen_sigue_vertical),
        "titulo_largo_en_reticula": bool(titulo_respeta_margenes),
        "misma_temperatura_cromatica": bool(misma_temperatura),
        "contraste_L_conservado": bool(contraste_conservado),
        "metricas": {
            "delta_e2000_medio_paleta_antes": diag["delta_e2000_medio_paleta_antes"],
            "delta_e2000_medio_paleta_propuesto": diag["delta_e2000_medio_paleta_propuesto"],
            "error_razones_jerarquia_antes": diag["error_medio_razones_jerarquia_antes"],
            "error_razones_jerarquia_propuesto": diag["error_medio_razones_jerarquia_propuesto"],
            "razones_tamano_referente": diag["razones_tamano_referente"],
            "razones_tamano_propuestas": diag["razones_tamano_propuestas"],
            "aspecto_imagen_propuesta": round(float(img_p["ancho_rel"]) / float(img_p["alto_rel"]), 3),
            "rango_L_referente": estudio_ref["paleta"]["contraste_valores"]["rango_L"],
            "rango_L_post_aplicacion": estudio_post["paleta"]["contraste_valores"]["rango_L"],
        },
    }


def probar_corpus_editorial_d3(dir_corpus: Path) -> Dict[str, Any]:
    """5. Ejecuta el estudio sobre los 5 carteles del corpus D-3 y valida el contrato ESQUEMA.md v1.1.0."""
    dir_muestras = dir_corpus / "muestras"
    archivos = sorted(dir_muestras.glob("*.jpg"))[:5] if dir_muestras.is_dir() else []
    resultados: List[Dict[str, Any]] = []
    todos_validos = True

    for ruta_img in archivos:
        est = estudiar_referente(ruta_img, max_dim_analisis=160)
        ok, errs = validar_estudio(est)
        if not ok:
            todos_validos = False
        resultados.append(
            {
                "archivo": ruta_img.name,
                "contrato_valido": ok,
                "errores": errs,
                "k_elegido": est["paleta"]["k_elegido"],
                "num_colores_lab": est["paleta"]["num_colores"],
                "delta_e2000_cuantizacion_media": est["paleta"]["delta_e2000_cuantizacion_media"],
                "paleta_insuficiente": est["paleta"]["paleta_insuficiente"],
                "armonia": est["paleta"]["armonia"]["tipo"],
                "porcentaje_aire": est["vacio"]["porcentaje_aire"],
                "sistema_reticula": est["reticula"]["proporciones_geometricas"]["sistema_dominante"],
                "confianza_global": est["confianza"]["global"],
            }
        )

    return {
        "prueba": "validacion_corpus_real_d3",
        "exito": bool(todos_validos and len(resultados) > 0),
        "muestras_evaluadas": len(resultados),
        "detalle_muestras": resultados,
    }


def probar_confianza_ruido_vs_planos() -> Dict[str, Any]:
    """6. [D-11b Punto 1] Comprueba que la confianza continua (Ley 8) BAJA con una imagen de
    ruido aleatorio y SUBE con una imagen limpia de 3 colores planos en los 6 bloques.
    """
    ancho, alto = 96, 120
    rng = random.Random(42)

    # A. Imagen de ruido cromático/tonal aleatorio uniforme
    mat_ruido = [
        [
            srgb_a_lab(
                rng.randint(0, 255),
                rng.randint(0, 255),
                rng.randint(0, 255),
            )
            for _ in range(ancho)
        ]
        for _ in range(alto)
    ]
    est_ruido = estudiar_lienzo(
        LienzoLab("ruido_aleatorio", "imagen", "0" * 64, ancho, alto, ancho, alto, mat_ruido, {})
    )

    # B. Imagen limpia de 3 colores planos dentro del gamut sRGB (papel crema, bloque bermellón, bloque azul marino)
    col_papel = srgb_a_lab(242, 234, 214)
    col_rojo = srgb_a_lab(198, 48, 42)
    col_azul = srgb_a_lab(24, 38, 92)

    mat_planos = [[col_papel for _ in range(ancho)] for _ in range(alto)]
    for y in range(12, 56):
        for x in range(12, 84):
            mat_planos[y][x] = col_rojo
    for y in range(68, 102):
        for x in range(12, 60):
            mat_planos[y][x] = col_azul

    est_planos = estudiar_lienzo(
        LienzoLab("tres_colores_planos", "imagen", "0" * 64, ancho, alto, ancho, alto, mat_planos, {})
    )

    c_ruido = est_ruido["confianza"]
    c_planos = est_planos["confianza"]

    bloques = ("paleta", "reticula", "escala_tipografica", "vacio", "jerarquia", "saliencia")
    sube_en_todos = all(
        c_planos["por_bloque"][b] > c_ruido["por_bloque"][b] + 0.25 for b in bloques
    )
    baja_en_ruido = (c_ruido["global"] < 0.12) and (est_ruido["paleta"]["paleta_insuficiente"] is True)
    sube_en_planos = (
        c_planos["global"] > 0.72
        and c_planos["por_bloque"]["paleta"] > 0.95
        and est_planos["paleta"]["k_elegido"] == 3
        and est_planos["paleta"]["paleta_insuficiente"] is False
    )

    return {
        "prueba": "confianza_continua_ruido_vs_3_colores_planos",
        "exito": bool(sube_en_todos and baja_en_ruido and sube_en_planos),
        "sube_en_los_6_bloques": bool(sube_en_todos),
        "baja_con_ruido": bool(baja_en_ruido),
        "sube_con_3_colores_planos": bool(sube_en_planos),
        "confianza_ruido": {
            "global": c_ruido["global"],
            "por_bloque": c_ruido["por_bloque"],
            "k_elegido": est_ruido["paleta"]["k_elegido"],
            "delta_e2000_medio": est_ruido["paleta"]["delta_e2000_cuantizacion_media"],
            "paleta_insuficiente": est_ruido["paleta"]["paleta_insuficiente"],
        },
        "confianza_3_colores_planos": {
            "global": c_planos["global"],
            "por_bloque": c_planos["por_bloque"],
            "k_elegido": est_planos["paleta"]["k_elegido"],
            "delta_e2000_medio": est_planos["paleta"]["delta_e2000_cuantizacion_media"],
            "paleta_insuficiente": est_planos["paleta"]["paleta_insuficiente"],
        },
    }


def probar_fidelidad_cromatica_k_adaptativo_d3(dir_corpus: Path) -> Dict[str, Any]:
    """7. [D-11b Puntos 2 y 3] Compara antes (K=5 fijo) vs después (K adaptativo 3..10) en los 5
    carteles de D-3 y verifica que cuando un cartel policromático con salpicadura/degradado continuo
    (p.ej. met_335536.jpg) sigue en ΔE2000 > 5.0 con K=10, se reporta como negativo ("paleta_insuficiente": true).
    """
    dir_muestras = dir_corpus / "muestras"
    archivos_5 = sorted(dir_muestras.glob("*.jpg"))[:5] if dir_muestras.is_dir() else []

    tabla_comparativa: List[Dict[str, Any]] = []
    for ruta_img in archivos_5:
        est_k5 = estudiar_referente(ruta_img, num_colores=5, max_dim_analisis=160)
        est_ad = estudiar_referente(ruta_img, num_colores=None, max_dim_analisis=160)
        p5 = est_k5["paleta"]
        pa = est_ad["paleta"]

        tabla_comparativa.append(
            {
                "archivo": ruta_img.name,
                "antes_k5": {
                    "k": 5,
                    "delta_e2000_medio": p5["delta_e2000_cuantizacion_media"],
                    "pasa_umbral_5": not p5["paleta_insuficiente"],
                },
                "despues_k_adaptativo": {
                    "k_elegido": pa["k_elegido"],
                    "num_colores": pa["num_colores"],
                    "delta_e2000_medio": pa["delta_e2000_cuantizacion_media"],
                    "paleta_insuficiente": pa["paleta_insuficiente"],
                    "pasa_umbral_5": not pa["paleta_insuficiente"],
                    "confianza_paleta": est_ad["confianza"]["por_bloque"]["paleta"],
                    "confianza_global": est_ad["confianza"]["global"],
                },
            }
        )

    # Verificar que los carteles que fallaban con K=5 (cma_1934_29 y cma_1968_257) suben K y bajan de 5.0,
    # logrando que los 5 carteles cumplan ΔE2000 < 5.0 con K adaptativo (3..10)
    rescata_degradados = all(
        fila["despues_k_adaptativo"]["pasa_umbral_5"]
        and fila["despues_k_adaptativo"]["delta_e2000_medio"] < 5.0
        for fila in tabla_comparativa
    ) and any(
        (not fila["antes_k5"]["pasa_umbral_5"]) and fila["despues_k_adaptativo"]["pasa_umbral_5"]
        for fila in tabla_comparativa
    )

    # Verificar también que un negativo real del corpus D-3 (met_335536.jpg o wikimedia_ed_03.jpg)
    # que con K=10 sigue > 5.0 declara honestamente "paleta_insuficiente": true
    negativos_declarados: List[Dict[str, Any]] = []
    for nombre_neg in ("met_335536.jpg", "wikimedia_ed_03.jpg"):
        ruta_neg = dir_muestras / nombre_neg
        if ruta_neg.exists():
            est_neg = estudiar_referente(ruta_neg, num_colores=None, max_dim_analisis=160)
            p_neg = est_neg["paleta"]
            negativos_declarados.append(
                {
                    "archivo": nombre_neg,
                    "k_elegido": p_neg["k_elegido"],
                    "delta_e2000_medio": p_neg["delta_e2000_cuantizacion_media"],
                    "paleta_insuficiente": p_neg["paleta_insuficiente"],
                    "confianza_paleta": est_neg["confianza"]["por_bloque"]["paleta"],
                }
            )

    negativo_honesto = all(
        n["k_elegido"] == 10 and n["paleta_insuficiente"] is True and n["delta_e2000_medio"] >= 5.0
        for n in negativos_declarados
    )

    return {
        "prueba": "fidelidad_cromatica_k_adaptativo_d3",
        "exito": bool(rescata_degradados and negativo_honesto and len(tabla_comparativa) == 5),
        "rescata_degradados_con_k_adaptativo": bool(rescata_degradados),
        "declara_negativos_paleta_insuficiente_k10": bool(negativo_honesto),
        "tabla_5_carteles_d3": tabla_comparativa,
        "negativos_en_k10_corpus_d3": negativos_declarados,
    }


def ejecutar_suite_completa(dir_corpus: Optional[Path] = None) -> Dict[str, Any]:
    if dir_corpus is None:
        dir_corpus = Path.home() / "Desktop" / "REFERENTES" / "corpus-editorial"

    pruebas = [
        probar_ciede2000_sharma(),
        probar_par_sintetico_paleta(),
        probar_par_sintetico_desplazado(),
        probar_transferencia_contenido_cambiado(),
        probar_corpus_editorial_d3(dir_corpus),
        probar_confianza_ruido_vs_planos(),
        probar_fidelidad_cromatica_k_adaptativo_d3(dir_corpus),
    ]
    todas_ok = all(p["exito"] for p in pruebas)
    return {
        "exito_global": todas_ok,
        "total_pruebas": len(pruebas),
        "pruebas_superadas": sum(1 for p in pruebas if p["exito"]),
        "resultados": pruebas,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="medir.py (D-11b): ejecuta las 7 pruebas (5 originales + confianza ruido/planos + K adaptativo D-3)."
    )
    parser.add_argument(
        "--corpus",
        default=str(Path.home() / "Desktop" / "REFERENTES" / "corpus-editorial"),
        help="Ruta al corpus editorial D-3.",
    )
    parser.add_argument("-o", "--output", help="Guardar informe JSON de mediciones.")
    args = parser.parse_args(argv)

    resumen = ejecutar_suite_completa(Path(args.corpus).expanduser().resolve())
    texto = json.dumps(resumen, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        out_p = Path(args.output).expanduser().resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)

    return 0 if resumen["exito_global"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
