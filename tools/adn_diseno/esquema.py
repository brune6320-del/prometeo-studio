#!/usr/bin/env python3
"""Validador del contrato de salida estudio.json (v1.1.0) para Forja 4."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

SCHEMA_VERSION = "1.1.0"

BLOQUES_OBLIGATORIOS: Tuple[str, ...] = (
    "paleta",
    "reticula",
    "escala_tipografica",
    "vacio",
    "jerarquia",
    "saliencia",
    "confianza",
)

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _contiene_rgb_crudo(obj: Any, ruta: str = "paleta") -> List[str]:
    """Comprueba recursivamente que no existan claves RGB ni strings hexadecimales en paleta."""
    errores: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_low = str(k).lower()
            if k_low in {"rgb", "rgba", "srgb", "hex", "bgr"}:
                errores.append(f"Clave prohibida '{k}' detectada en {ruta}.{k}")
            errores.extend(_contiene_rgb_crudo(v, f"{ruta}.{k}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            errores.extend(_contiene_rgb_crudo(item, f"{ruta}[{idx}]"))
    elif isinstance(obj, str):
        if HEX_COLOR_RE.match(obj.strip()):
            errores.append(f"Color hexadecimal prohibido '{obj}' en {ruta}")
    return errores


def validar_estudio(estudio: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Valida que un diccionario estudio.json cumpla el contrato v1.1.0.

    Devuelve (es_valido, lista_de_errores).
    """
    errores: List[str] = []

    if not isinstance(estudio, dict):
        return False, ["El estudio raíz debe ser un objeto JSON (dict)."]

    if estudio.get("schema_version") != SCHEMA_VERSION:
        errores.append(
            f"schema_version inválido: esperado '{SCHEMA_VERSION}', "
            f"recibido '{estudio.get('schema_version')}'."
        )

    if "referente" not in estudio or not isinstance(estudio.get("referente"), dict):
        errores.append("Falta el bloque de metadatos 'referente'.")

    for bloque in BLOQUES_OBLIGATORIOS:
        if bloque not in estudio or not isinstance(estudio.get(bloque), dict):
            errores.append(f"Falta el bloque fijo obligatorio '{bloque}'.")

    if errores:
        return False, errores

    # 1. Validación de paleta (Lab + proporción + ΔE2000 + K adaptativo 3..10 + paleta_insuficiente)
    paleta = estudio["paleta"]
    errores.extend(_contiene_rgb_crudo(paleta, "paleta"))

    if paleta.get("espacio_color") != "CIE_L*a*b*_D65_2deg":
        errores.append("paleta.espacio_color debe ser 'CIE_L*a*b*_D65_2deg'.")

    colores = paleta.get("colores", [])
    if not isinstance(colores, list) or len(colores) == 0:
        errores.append("paleta.colores debe ser una lista no vacía.")
    else:
        suma_prop = 0.0
        for idx, col in enumerate(colores):
            lab = col.get("lab", {})
            if not all(k in lab for k in ("L", "a", "b")):
                errores.append(f"paleta.colores[{idx}].lab debe tener claves L, a, b.")
            else:
                l_val = float(lab["L"])
                if not (0.0 - 1e-3 <= l_val <= 100.0 + 1e-3):
                    errores.append(f"L* fuera de rango [0, 100] en color {idx}: {l_val}")
            prop = float(col.get("proporcion", -1.0))
            if not (0.0 <= prop <= 1.0):
                errores.append(f"Proporción fuera de [0, 1] en color {idx}: {prop}")
            suma_prop += prop
        if not math.isclose(suma_prop, 1.0, abs_tol=1e-2):
            errores.append(f"La suma de proporciones de paleta es {suma_prop:.4f} (esperado ~1.0).")

    for sub in (
        "k_elegido",
        "delta_e2000_cuantizacion_media",
        "paleta_insuficiente",
        "pares_delta_e2000",
        "matriz_delta_e2000",
        "armonia",
        "contraste_valores",
        "temperatura",
        "saturacion_media",
    ):
        if sub not in paleta:
            errores.append(f"Falta subcampo obligatorio 'paleta.{sub}'.")

    if "paleta_insuficiente" in paleta and not isinstance(paleta["paleta_insuficiente"], bool):
        errores.append("paleta.paleta_insuficiente debe ser booleano (true/false).")

    # 2. Validación de retícula
    reticula = estudio["reticula"]
    for sub in ("columnas", "margenes", "medianiles", "ejes_alineacion", "proporciones_geometricas", "ritmo_y_repeticion"):
        if sub not in reticula:
            errores.append(f"Falta subcampo obligatorio 'reticula.{sub}'.")

    # 3. Validación de escala_tipografica
    esc = estudio["escala_tipografica"]
    for sub in ("fuente_analisis", "adn_tipo_disponible", "hay_texto_detectado", "datos_adn_tipo"):
        if sub not in esc:
            errores.append(f"Falta subcampo obligatorio 'escala_tipografica.{sub}'.")

    # 4. Validación de vacío
    vacio = estudio["vacio"]
    for sub in ("porcentaje_aire", "proporcion_aire", "distribucion_cuadrantes", "centro_peso_visual"):
        if sub not in vacio:
            errores.append(f"Falta subcampo obligatorio 'vacio.{sub}'.")
    else:
        pct = float(vacio["porcentaje_aire"])
        if not (0.0 <= pct <= 100.0):
            errores.append(f"vacio.porcentaje_aire fuera de [0, 100]: {pct}")

    # 5. Validación de jerarquía
    jer = estudio["jerarquia"]
    for sub in ("num_elementos_principales", "razones_tamano", "indice_dominancia", "niveles", "recorrido_visual_rel"):
        if sub not in jer:
            errores.append(f"Falta subcampo obligatorio 'jerarquia.{sub}'.")

    # 6. Validación de saliencia
    sal = estudio["saliencia"]
    for sub in ("metodo", "licencia_metodo", "foco_primario", "focos_secundarios", "concentracion_espacial", "mapa_rejilla_8x8"):
        if sub not in sal:
            errores.append(f"Falta subcampo obligatorio 'saliencia.{sub}'.")
    else:
        rejilla = sal["mapa_rejilla_8x8"]
        if not (isinstance(rejilla, list) and len(rejilla) == 8 and all(isinstance(r, list) and len(r) == 8 for r in rejilla)):
            errores.append("saliencia.mapa_rejilla_8x8 debe ser una matriz 8x8.")

    # 7. Validación de confianza por bloque
    conf = estudio["confianza"]
    por_bloque = conf.get("por_bloque", {})
    for b in ("paleta", "reticula", "escala_tipografica", "vacio", "jerarquia", "saliencia"):
        if b not in por_bloque:
            errores.append(f"Falta confianza para el bloque '{b}' en confianza.por_bloque.")
        else:
            val = float(por_bloque[b])
            if not (0.0 <= val <= 1.0):
                errores.append(f"Confianza fuera de [0, 1] para '{b}': {val}")

    return len(errores) == 0, errores
