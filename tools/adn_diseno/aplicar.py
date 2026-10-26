#!/usr/bin/env python3
"""aplicar.py — Propone ajustes sobre un tablero.json de Prometeo para respetar el ADN de un referente.

Cumple la regla estricta de D-11:
  «dada una composición nueva de Prometeo (tablero.json), proponer cambios para que respete
   el estudio de un referente: paleta, retícula y jerarquía. Propone, NO aplica solo.»

Opera exclusivamente en CIE L*a*b* (con ΔE2000) y coordenadas relativas/absolutas sin modificar
el archivo tablero.json original.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .color_lab import delta_e2000, lab_a_lch


def _normalizar_lab_dict(d: Optional[Dict[str, Any]], defecto: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if not isinstance(d, dict):
        return defecto
    if "lab" in d and isinstance(d["lab"], dict):
        d = d["lab"]
    if all(k in d for k in ("L", "a", "b")):
        return (float(d["L"]), float(d["a"]), float(d["b"]))
    return defecto


def _importancia_rol_elemento(elem: Dict[str, Any], idx: int) -> Tuple[int, str]:
    """Determina la prioridad jerárquica intrínseca de un elemento del tablero."""
    rol = str(elem.get("rol") or elem.get("tipo") or "bloque").lower()
    prioridad_explicita = elem.get("jerarquia") or elem.get("rango")
    if isinstance(prioridad_explicita, int) and prioridad_explicita >= 1:
        return prioridad_explicita, rol

    if rol in {"imagen_principal", "hero", "ilustracion", "figura", "imagen"}:
        return 1, "imagen"
    if rol in {"titulo", "titular", "headline", "cabecera"}:
        return 2, "titulo"
    if rol in {"subtitulo", "bajada", "deck", "destacado"}:
        return 3, "subtitulo"
    if rol in {"cuerpo", "texto", "parrafo", "nota", "pie"}:
        return 4, "cuerpo"
    if rol in {"acento", "sello", "logo", "etiqueta", "badge"}:
        return 5, "acento"
    return 6 + idx, rol


def _seleccionar_paleta_roles(
    estudio_paleta: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Asigna los clústeres CIE L*a*b* del referente a roles funcionales de diseño."""
    colores = estudio_paleta.get("colores", [])
    if not colores:
        neutro = {"id": "c0", "lab": {"L": 90.0, "a": 0.0, "b": 4.0}, "proporcion": 1.0}
        return {"fondo": neutro, "primario": neutro, "secundario": neutro, "acento": neutro, "apoyo": neutro}

    # El soporte/fondo suele ser el dominante c0 (o el fondo_papel si su proporción >= 0.25)
    fondo = colores[0]
    for c in colores:
        if c.get("rol") == "fondo_papel" and float(c.get("proporcion", 0.0)) >= 0.25:
            fondo = c
            break

    lab_fondo = (fondo["lab"]["L"], fondo["lab"]["a"], fondo["lab"]["b"])
    resto = [c for c in colores if c["id"] != fondo["id"]]
    if not resto:
        resto = [fondo]

    # El color primario/titular es el que ofrece mayor contraste ΔE2000 (y ΔL*) frente al soporte
    primario = max(
        resto,
        key=lambda c: (
            0.65 * delta_e2000((c["lab"]["L"], c["lab"]["a"], c["lab"]["b"]), lab_fondo)
            + 0.35 * abs(c["lab"]["L"] - lab_fondo[0])
        ),
    )

    # El color secundario es el de mayor proporción entre los restantes (o el segundo de mayor contraste)
    candidatos_sec = [c for c in resto if c["id"] != primario["id"]]
    secundario = candidatos_sec[0] if candidatos_sec else primario

    # El color de acento es el de mayor croma C*ab distinto del fondo
    acento = max(
        resto,
        key=lambda c: math.hypot(c["lab"]["a"], c["lab"]["b"]),
    )
    apoyo = candidatos_sec[1] if len(candidatos_sec) >= 2 else secundario

    return {
        "fondo": fondo,
        "primario": primario,
        "secundario": secundario,
        "acento": acento,
        "apoyo": apoyo,
    }


def _ajustar_a_eje_mas_cercano(
    valor_rel: float,
    ejes_candidatos: List[float],
    tolerancia: float = 0.18,
) -> Tuple[float, Optional[float]]:
    """Acerca una coordenada relativa al eje de la retícula más próximo si cae dentro de tolerancia."""
    if not ejes_candidatos:
        return valor_rel, None
    mejor_eje = min(ejes_candidatos, key=lambda e: abs(valor_rel - e))
    if abs(valor_rel - mejor_eje) <= tolerancia:
        return round(mejor_eje, 4), round(mejor_eje, 4)
    return round(valor_rel, 4), None


def proponer_cambios(
    tablero: Dict[str, Any],
    estudio_referente: Dict[str, Any],
) -> Dict[str, Any]:
    """Genera un diccionario de propuestas (sin mutar el tablero de entrada) para transferir el ADN del referente."""
    tablero_orig = copy.deepcopy(tablero)
    lienzo_cfg = tablero_orig.get("lienzo") or tablero_orig.get("dimensiones") or {}
    ancho_lienzo = float(lienzo_cfg.get("ancho") or lienzo_cfg.get("ancho_px") or 1000.0)
    alto_lienzo = float(lienzo_cfg.get("alto") or lienzo_cfg.get("alto_px") or 1400.0)
    area_lienzo = max(1.0, ancho_lienzo * alto_lienzo)

    paleta_ref = estudio_referente["paleta"]
    reticula_ref = estudio_referente["reticula"]
    vacio_ref = estudio_referente["vacio"]
    jerarquia_ref = estudio_referente["jerarquia"]
    escala_tipo_ref = estudio_referente["escala_tipografica"]

    roles_color = _seleccionar_paleta_roles(paleta_ref)
    lab_fondo_ref = _normalizar_lab_dict(roles_color["fondo"], (85.0, 0.0, 8.0))
    lab_fondo_actual = _normalizar_lab_dict(tablero_orig.get("fondo"), (95.0, 0.0, 0.0))

    acciones: List[Dict[str, Any]] = []

    # 1. Propuesta para el soporte/fondo en CIE L*a*b*
    de_fondo = round(delta_e2000(lab_fondo_actual, lab_fondo_ref), 3)
    if de_fondo > 1.5:
        acciones.append(
            {
                "elemento_id": "lienzo_fondo",
                "eje": "paleta",
                "tipo_cambio": "ajustar_color_soporte_lab",
                "parametro": "fondo.lab",
                "valor_actual": {
                    "L": round(lab_fondo_actual[0], 3),
                    "a": round(lab_fondo_actual[1], 3),
                    "b": round(lab_fondo_actual[2], 3),
                },
                "valor_propuesto": roles_color["fondo"]["lab"],
                "delta_e2000": de_fondo,
                "justificacion_esencia": (
                    f"Alinear el soporte con el color dominante del referente ({roles_color['fondo']['id']}, "
                    f"proporción {roles_color['fondo']['proporcion']:.1%}, temperatura "
                    f"'{paleta_ref['temperatura']['clasificacion']}')."
                ),
            }
        )

    # 2. Preparar geometría de retícula y márgenes del referente
    marg = reticula_ref["margenes"]
    m_izq = max(0.04, min(0.22, float(marg.get("izquierdo_rel", 0.06))))
    m_der = max(0.04, min(0.22, float(marg.get("derecho_rel", 0.06))))
    m_sup = max(0.04, min(0.22, float(marg.get("superior_rel", 0.06))))
    m_inf = max(0.04, min(0.22, float(marg.get("inferior_rel", 0.06))))

    ancho_caja_util = max(0.20, 1.0 - m_izq - m_der)
    alto_caja_util = max(0.20, 1.0 - m_sup - m_inf)

    ejes_v_ref = [float(e["pos"]) for e in reticula_ref.get("ejes_alineacion", {}).get("verticales_x_rel", [])]
    ejes_h_ref = [float(e["pos"]) for e in reticula_ref.get("ejes_alineacion", {}).get("horizontales_y_rel", [])]
    for canon_x in (m_izq, 0.5, 1.0 - m_der):
        if all(abs(canon_x - ex) > 0.03 for ex in ejes_v_ref):
            ejes_v_ref.append(canon_x)
    ejes_v_ref.sort()

    for canon_y in (m_sup, 0.382, 0.618, 1.0 - m_inf):
        if all(abs(canon_y - ey) > 0.03 for ey in ejes_h_ref):
            ejes_h_ref.append(canon_y)
    ejes_h_ref.sort()

    medianil_rel = max(0.025, float(reticula_ref.get("medianiles", {}).get("ancho_medio_rel") or 0.035))

    # 3. Ordenar elementos del tablero por importancia jerárquica
    elementos_in = list(tablero_orig.get("elementos", []))
    orden_jerarquico = sorted(
        range(len(elementos_in)),
        key=lambda i: _importancia_rol_elemento(elementos_in[i], i)[0],
    )

    razones_ref = list(jerarquia_ref.get("razones_tamano") or [1.0, 0.45, 0.22, 0.12])
    while len(razones_ref) < max(1, len(elementos_in)):
        razones_ref.append(round(razones_ref[-1] * 0.65, 4))

    razon_escala_tipo = float(escala_tipo_ref.get("razon_escala") or 1.618)

    # Objetivo de ocupación total según el aire/espacio negativo del referente
    prop_aire_ref = max(0.20, min(0.85, float(vacio_ref.get("proporcion_aire", 0.45))))
    ocupacion_objetivo_total = 1.0 - prop_aire_ref

    # Calcular pesos de área deseados por elemento respetando el contenido (título más largo, imagen vertical, etc.)
    pesos_area_obj: Dict[int, float] = {}
    for rank_idx, elem_idx in enumerate(orden_jerarquico):
        elem = elementos_in[elem_idx]
        _, rol_norm = _importancia_rol_elemento(elem, elem_idx)
        base_ratio = float(razones_ref[min(rank_idx, len(razones_ref) - 1)])

        # Si es texto (título/subtítulo/cuerpo) y el texto creció en longitud, permitir adaptación elástica controlada
        texto = str(elem.get("texto") or "")
        factor_contenido = 1.0
        if rol_norm == "titulo" and len(texto) > 28:
            # Un título más largo necesita algo más de caja pero manteniendo la razón jerárquica frente a la imagen principal
            factor_contenido = min(1.35, 1.0 + 0.008 * (len(texto) - 28))
        elif rol_norm == "subtitulo":
            base_ratio = min(base_ratio, razones_ref[0] / max(1.3, razon_escala_tipo))

        pesos_area_obj[elem_idx] = max(0.02, base_ratio * factor_contenido)

    suma_pesos_area = sum(pesos_area_obj.values()) or 1.0

    # 4. Construir propuestas por elemento (geometría, jerarquía y color Lab)
    elementos_propuestos: List[Dict[str, Any]] = [copy.deepcopy(e) for e in elementos_in]
    niveles_ref = jerarquia_ref.get("niveles", [])
    centro_peso_ref = vacio_ref.get("centro_peso_visual", {"x_rel": 0.5, "y_rel": 0.5})

    cursor_y_rel = m_sup
    de_paleta_antes: List[float] = []
    de_paleta_despues: List[float] = []

    for rank_idx, elem_idx in enumerate(orden_jerarquico):
        elem_orig = elementos_in[elem_idx]
        elem_prop = elementos_propuestos[elem_idx]
        elem_id = str(elem_orig.get("id") or f"elem_{elem_idx + 1}")
        _, rol_norm = _importancia_rol_elemento(elem_orig, elem_idx)

        # Coordenadas actuales normalizadas [0, 1]
        es_relativo = bool(elem_orig.get("coordenadas_relativas", False)) or (
            max(
                float(elem_orig.get("x", 0.0)),
                float(elem_orig.get("y", 0.0)),
                float(elem_orig.get("ancho", 0.0)),
                float(elem_orig.get("alto", 0.0)),
            )
            <= 1.05
        )
        if es_relativo:
            x_act = float(elem_orig.get("x", m_izq))
            y_act = float(elem_orig.get("y", m_sup))
            w_act = float(elem_orig.get("ancho", 0.4))
            h_act = float(elem_orig.get("alto", 0.2))
        else:
            x_act = float(elem_orig.get("x", 0.0)) / ancho_lienzo
            y_act = float(elem_orig.get("y", 0.0)) / alto_lienzo
            w_act = float(elem_orig.get("ancho", 200.0)) / ancho_lienzo
            h_act = float(elem_orig.get("alto", 150.0)) / alto_lienzo

        aspecto_elem = max(0.15, min(8.0, w_act / max(1e-4, h_act)))
        texto_elem = str(elem_orig.get("texto") or "")

        # Si es un título largo, ajustar la relación de aspecto de su caja para permitir salto de línea limpio
        if rol_norm in {"titulo", "subtitulo"} and len(texto_elem) > 0:
            lineas_estimadas = max(1, math.ceil(len(texto_elem) / 26.0))
            aspecto_elem = max(1.8, min(6.5, (ancho_caja_util * 0.92) / (0.065 * lineas_estimadas)))

        # Área objetivo proporcional a la jerarquía del referente y al aire del referente
        area_obj_rel = ocupacion_objetivo_total * (pesos_area_obj[elem_idx] / suma_pesos_area)
        w_prop = math.sqrt(area_obj_rel * aspecto_elem)
        h_prop = area_obj_rel / max(1e-4, w_prop)

        # Respetar los márgenes de la retícula del referente
        if w_prop > ancho_caja_util:
            w_prop = ancho_caja_util
            h_prop = min(alto_caja_util * 0.72, area_obj_rel / max(1e-4, w_prop))
        if h_prop > alto_caja_util * 0.75:
            h_prop = alto_caja_util * 0.75
            w_prop = min(ancho_caja_util, h_prop * aspecto_elem)

        # Posicionamiento según la región jerárquica correspondiente del referente y los ejes de alineación
        if rank_idx < len(niveles_ref):
            caja_ref_r = niveles_ref[rank_idx]["caja_rel"]
            x_pref = float(caja_ref_r[0])
            y_pref = float(caja_ref_r[1])
        else:
            x_pref = m_izq
            y_pref = cursor_y_rel

        # Encajar x_pref al margen o eje vertical más próximo sin salirse de la caja útil
        x_cand, eje_v_usado = _ajustar_a_eje_mas_cercano(x_pref, ejes_v_ref, tolerancia=0.14)
        x_prop = max(m_izq, min(1.0 - m_der - w_prop, x_cand))

        # Evitar solapamiento vertical con elementos de mayor jerarquía ya posicionados
        y_cand, eje_h_usado = _ajustar_a_eje_mas_cercano(max(m_sup, y_pref), ejes_h_ref, tolerancia=0.12)
        if rank_idx > 0 and abs(y_cand - cursor_y_rel) < medianil_rel:
            y_cand = cursor_y_rel
        y_prop = max(m_sup, min(1.0 - m_inf - h_prop, y_cand))
        cursor_y_rel = min(1.0 - m_inf, y_prop + h_prop + medianil_rel)

        # Selección de color CIE L*a*b* según rol jerárquico
        if rol_norm in {"titulo", "imagen"} and rank_idx == 0:
            col_ref_obj = roles_color["primario"]
        elif rol_norm == "titulo":
            col_ref_obj = roles_color["primario"]
        elif rol_norm == "acento":
            col_ref_obj = roles_color["acento"]
        elif rank_idx == 1:
            col_ref_obj = roles_color["secundario"]
        else:
            col_ref_obj = roles_color["apoyo"]

        lab_elem_act = _normalizar_lab_dict(elem_orig.get("lab") or elem_orig.get("color"), (20.0, 0.0, 0.0))
        lab_elem_prop = _normalizar_lab_dict(col_ref_obj, lab_elem_act)

        # Calcular distancia a la paleta del referente antes y después
        min_de_antes = min(
            delta_e2000(lab_elem_act, (c["lab"]["L"], c["lab"]["a"], c["lab"]["b"]))
            for c in paleta_ref["colores"]
        )
        min_de_despues = min(
            delta_e2000(lab_elem_prop, (c["lab"]["L"], c["lab"]["a"], c["lab"]["b"]))
            for c in paleta_ref["colores"]
        )
        de_paleta_antes.append(min_de_antes)
        de_paleta_despues.append(min_de_despues)

        de_cambio_elem = round(delta_e2000(lab_elem_act, lab_elem_prop), 3)
        contraste_vs_fondo = round(delta_e2000(lab_elem_prop, lab_fondo_ref), 3)

        # Registrar propuesta de color Lab
        acciones.append(
            {
                "elemento_id": elem_id,
                "eje": "paleta",
                "tipo_cambio": "asignar_color_jerarquico_lab",
                "parametro": "lab",
                "valor_actual": {
                    "L": round(lab_elem_act[0], 3),
                    "a": round(lab_elem_act[1], 3),
                    "b": round(lab_elem_act[2], 3),
                },
                "valor_propuesto": col_ref_obj["lab"],
                "delta_e2000_ajuste": de_cambio_elem,
                "contraste_vs_fondo_delta_e2000": contraste_vs_fondo,
                "justificacion_esencia": (
                    f"Asignar color del referente ({col_ref_obj['id']}, rol '{col_ref_obj.get('rol')}') "
                    f"para mantener contraste ΔE2000={contraste_vs_fondo} frente al soporte."
                ),
            }
        )

        # Registrar propuesta de retícula y jerarquía
        if es_relativo:
            geom_actual = {
                "x": round(x_act, 4),
                "y": round(y_act, 4),
                "ancho": round(w_act, 4),
                "alto": round(h_act, 4),
            }
            geom_prop = {
                "x": round(x_prop, 4),
                "y": round(y_prop, 4),
                "ancho": round(w_prop, 4),
                "alto": round(h_prop, 4),
            }
        else:
            geom_actual = {
                "x": round(x_act * ancho_lienzo, 1),
                "y": round(y_act * alto_lienzo, 1),
                "ancho": round(w_act * ancho_lienzo, 1),
                "alto": round(h_act * alto_lienzo, 1),
            }
            geom_prop = {
                "x": round(x_prop * ancho_lienzo, 1),
                "y": round(y_prop * alto_lienzo, 1),
                "ancho": round(w_prop * ancho_lienzo, 1),
                "alto": round(h_prop * alto_lienzo, 1),
            }

        acciones.append(
            {
                "elemento_id": elem_id,
                "eje": "reticula_y_jerarquia",
                "rango_jerarquico": rank_idx + 1,
                "rol_detectado": rol_norm,
                "tipo_cambio": "encajar_reticula_y_escalar_jerarquia",
                "parametro": "geometria",
                "valor_actual": geom_actual,
                "valor_propuesto": geom_prop,
                "relacion_aspecto_preservada": round(w_prop / max(1e-4, h_prop), 4),
                "eje_vertical_anclado": eje_v_usado,
                "eje_horizontal_anclado": eje_h_usado,
                "justificacion_esencia": (
                    f"Rango #{rank_idx + 1} ({rol_norm}): razón de área ajustada a la jerarquía del referente "
                    f"({razones_ref[min(rank_idx, len(razones_ref) - 1)]:.2f}) preservando relación de aspecto del contenido "
                    f"y márgenes relativos [{m_izq:.3f}, {m_sup:.3f}]."
                ),
            }
        )

        # Actualizar previsualización no destructiva
        elem_prop["lab"] = copy.deepcopy(col_ref_obj["lab"])
        elem_prop.pop("rgb", None)
        elem_prop.pop("hex", None)
        elem_prop["x"] = geom_prop["x"]
        elem_prop["y"] = geom_prop["y"]
        elem_prop["ancho"] = geom_prop["ancho"]
        elem_prop["alto"] = geom_prop["alto"]
        elem_prop["x_rel"] = round(x_prop, 4)
        elem_prop["y_rel"] = round(y_prop, 4)
        elem_prop["ancho_rel"] = round(w_prop, 4)
        elem_prop["alto_rel"] = round(h_prop, 4)
        elem_prop["rango_jerarquico_propuesto"] = rank_idx + 1

    # 5. Calcular métricas comparativas antes vs. propuesto
    areas_antes = sorted(
        [
            (
                float(e.get("ancho", 0.2)) * float(e.get("alto", 0.2))
                if (bool(e.get("coordenadas_relativas", False)) or float(e.get("ancho", 0.2)) <= 1.05)
                else (float(e.get("ancho", 200.0)) * float(e.get("alto", 150.0)) / area_lienzo)
            )
            for e in elementos_in
        ],
        reverse=True,
    )
    areas_prop = sorted(
        [float(e["ancho_rel"]) * float(e["alto_rel"]) for e in elementos_propuestos],
        reverse=True,
    )

    max_a_ant = max(areas_antes, default=1.0) or 1.0
    max_a_prop = max(areas_prop, default=1.0) or 1.0
    razones_antes = [round(a / max_a_ant, 4) for a in areas_antes]
    razones_prop = [round(a / max_a_prop, 4) for a in areas_prop]

    n_comp = min(len(razones_ref), len(razones_prop))
    err_jer_antes = (
        sum(abs(razones_antes[i] - razones_ref[i]) for i in range(n_comp)) / float(max(1, n_comp))
    )
    err_jer_prop = (
        sum(abs(razones_prop[i] - razones_ref[i]) for i in range(n_comp)) / float(max(1, n_comp))
    )

    aire_antes_pct = round(max(0.0, (1.0 - min(1.0, sum(areas_antes))) * 100.0), 2)
    aire_prop_pct = round(max(0.0, (1.0 - min(1.0, sum(areas_prop))) * 100.0), 2)

    tablero_preview = copy.deepcopy(tablero_orig)
    tablero_preview["fondo"] = {"lab": copy.deepcopy(roles_color["fondo"]["lab"])}
    tablero_preview["elementos"] = elementos_propuestos

    return {
        "schema_version": "1.0.0",
        "modo": "solo_propuesta_no_destructivo",
        "aplicado_automaticamente": False,
        "referente_id": estudio_referente.get("referente", {}).get("id", "desconocido"),
        "resumen_diagnostico": {
            "delta_e2000_medio_paleta_antes": round(
                sum(de_paleta_antes) / float(max(1, len(de_paleta_antes))), 3
            ),
            "delta_e2000_medio_paleta_propuesto": round(
                sum(de_paleta_despues) / float(max(1, len(de_paleta_despues))), 3
            ),
            "error_medio_razones_jerarquia_antes": round(err_jer_antes, 4),
            "error_medio_razones_jerarquia_propuesto": round(err_jer_prop, 4),
            "porcentaje_aire_referente": round(float(vacio_ref.get("porcentaje_aire", 45.0)), 2),
            "porcentaje_aire_antes": aire_antes_pct,
            "porcentaje_aire_propuesto": aire_prop_pct,
            "razones_tamano_referente": razones_ref[: len(elementos_in)],
            "razones_tamano_antes": razones_antes,
            "razones_tamano_propuestas": razones_prop,
        },
        "acciones_propuestas": acciones,
        "previsualizacion_tablero_propuesto": tablero_preview,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="aplicar.py (D-11): propone cambios sobre tablero.json para respetar el estudio.json de un referente (NO modifica el original)."
    )
    parser.add_argument("--tablero", required=True, help="Ruta al archivo tablero.json de Prometeo.")
    parser.add_argument("--estudio", required=True, help="Ruta al archivo estudio.json del referente.")
    parser.add_argument("-o", "--output", help="Ruta para guardar el JSON de propuestas (por defecto stdout).")
    args = parser.parse_args(argv)

    ruta_tablero = Path(args.tablero).expanduser().resolve()
    ruta_estudio = Path(args.estudio).expanduser().resolve()

    tablero_data = json.loads(ruta_tablero.read_text(encoding="utf-8"))
    estudio_data = json.loads(ruta_estudio.read_text(encoding="utf-8"))

    propuesta = proponer_cambios(tablero_data, estudio_data)
    salida = json.dumps(propuesta, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        out_p = Path(args.output).expanduser().resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(salida, encoding="utf-8")
    else:
        sys.stdout.write(salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
