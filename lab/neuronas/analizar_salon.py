#!/usr/bin/env python3
"""FASE 5d (v3d.1) · Analizador estadístico de «El salón» (CPU, 0 Colab).

Procesa los archivos JSON descargados por los participantes (`salon_respuesta_*.json`) junto con
la clave secreta (`clave_salon_no_abrir.json`):
1. Filtro de atención (Regla 5): descarta a quien falle AMBOS pares obvios de atención
   (`atencion_01` y `atencion_02`), resolviendo el lado mostrado por persona (`lado_polo_pos_mostrado`).
2. Botón central «Ninguno / se sienten igual» (`eleccion == "ninguno"`, v3d):
   - Entra en el denominador N de participantes válidos y cuenta como NO acierto (`0` aciertos,
     criterio conservador).
   - Se informa explícitamente `porcentaje_ninguno` por cada una de las 20 neuronas, en los
     4 controles al azar (`porcentaje_ninguno_4_controles_azar_pct`) y en la Parte 1.
3. Control de brillo (v3c):
   - Para cada par de la Parte 2, determina qué polo (`polo_pos` o `polo_neg`) elegiría alguien
     que solo mire «el más claro o el más oscuro» (según ΔL* CIE Lab de cada mosaico).
   - Informa qué neuronas aciertan MÁS que esa regla simple (`supera_regla_brillo = true`).
   - Declara que la neurona «se siente de verdad» (`se_siente_de_verdad = true`) si y solo si:
     acierto >= 70.0%, p_ajustado_Holm < 0.05 y supera_regla_brillo == true.
4. Sorteo izquierda/derecha por persona (v3c): verifica `semilla_apodo` y `lado_polo_pos_mostrado`.
5. Separación estricta de los ♥ de Bruno (v3c): solo los ♥ de Bruno cuentan para N-2 y D-8
   (`corazones_bruno_n2_d8.json`); los de los demás se guardan en `corazones_otros_participantes.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.dont_write_bytecode = True

RESPUESTAS_VALIDAS_PAR = ("izquierda", "derecha", "ninguno")


def p_valor_binomial_unilateral(exitos: int, n: int) -> float:
    """Calcula P(X >= exitos) para X ~ Binomial(n, 0.5)."""
    if n <= 0 or exitos <= 0:
        return 1.0
    if exitos > n:
        return 0.0
    casos = sum(math.comb(n, k) for k in range(exitos, n + 1))
    return float(casos) / float(2**n)


def holm_bonferroni(p_valores: List[float]) -> List[float]:
    """Corrección escalonada de Holm-Bonferroni para una familia de M pruebas."""
    m = len(p_valores)
    if m == 0:
        return []
    orden = sorted(range(m), key=lambda i: (p_valores[i], i))
    ajustados = [0.0] * m
    max_acum = 0.0
    for rank_idx, orig_idx in enumerate(orden):
        factor = m - rank_idx
        val = min(1.0, p_valores[orig_idx] * factor)
        if val < max_acum:
            val = max_acum
        else:
            max_acum = val
        ajustados[orig_idx] = round(val, 6)
    return ajustados


def _resolver_lado_polo_pos_mostrado(
    item_resp: Dict[str, Any], info_clave: Dict[str, Any]
) -> str:
    lado = item_resp.get("lado_polo_pos_mostrado")
    if lado in ("izquierda", "derecha"):
        return str(lado)
    sha_izq = item_resp.get("sha256_mostrado_izquierda")
    if sha_izq and sha_izq == info_clave.get("sha256_polo_pos"):
        return "izquierda"
    if sha_izq and sha_izq == info_clave.get("sha256_polo_neg"):
        return "derecha"
    return str(info_clave.get("lado_predicho", "izquierda"))


def analizar_respuestas_salon(
    carpeta_respuestas: Path,
    ruta_clave: Path,
) -> Dict[str, Any]:
    clave = json.loads(ruta_clave.read_text(encoding="utf-8"))
    archivos_json = sorted(
        p
        for p in carpeta_respuestas.glob("*.json")
        if p.name
        not in ("corazones_bruno_n2_d8.json", "corazones_otros_participantes.json")
    )

    atencion_clave = {x["id_item"]: x for x in clave["parte_2_atencion_2_clave"]}
    controles_clave = {x["id_item"]: x for x in clave["parte_2_controles_4_clave"]}
    neuronas_clave = clave["parte_2_neuronas_20_clave"]
    parte1_clave = {x["id_item"]: x for x in clave["parte_1_clave"]}
    parte3_clave = {x["id_item"]: x for x in clave["parte_3_clave"]}

    participantes_validos: List[Dict[str, Any]] = []
    participantes_excluidos_atencion: List[str] = []
    semillas_vistas: List[int] = []

    for ruta_r in archivos_json:
        datos = json.loads(ruta_r.read_text(encoding="utf-8"))
        part = datos.get("participante", {})
        if not part.get("consentimiento_informado", False):
            continue
        apodo = str(part.get("apodo", ruta_r.stem))
        if "semilla_apodo" in part:
            semillas_vistas.append(int(part["semilla_apodo"]))

        resp2_map = {x["id_item"]: x for x in datos.get("parte_2_sentir", [])}
        aciertos_at = 0
        for id_at, info_at in atencion_clave.items():
            if id_at in resp2_map:
                r_at = resp2_map[id_at]
                lado_pos_mostrado = _resolver_lado_polo_pos_mostrado(r_at, info_at)
                # En atención obvia, elegir "ninguno" o el lado opuesto no suma acierto
                if r_at.get("eleccion") == lado_pos_mostrado:
                    aciertos_at += 1
        if aciertos_at == 0:
            participantes_excluidos_atencion.append(apodo)
            continue
        participantes_validos.append(datos)

    n_val = len(participantes_validos)
    if n_val == 0:
        return {
            "fase": "FASE 5d (v3d.1) · Análisis de El Salón",
            "estado": "PENDIENTE_PARTICIPANTES",
            "archivos_encontrados": len(archivos_json),
            "participantes_validos": 0,
            "participantes_excluidos_por_fallar_ambos_controles_atencion": participantes_excluidos_atencion,
            "minimo_requerido": 6,
            "nota": "Aún no hay respuestas válidas en la carpeta de respuestas.",
        }

    # --- Control de brillo: tasa empírica de elegir «el más claro» vs «el más oscuro» en los 18 ejes no de brillo ---
    votos_al_mas_claro = 0
    votos_al_mas_oscuro = 0
    votos_totales_no_brillo = 0
    for n_info in neuronas_clave:
        if n_info.get("es_eje_solo_brillo", False):
            continue
        id_it = n_info["id_item"]
        polo_claro = n_info.get(
            "polo_mas_claro", "polo_pos" if n_info.get("delta_L", 0.0) >= 0 else "polo_neg"
        )
        for p_doc in participantes_validos:
            r_map = {x["id_item"]: x for x in p_doc.get("parte_2_sentir", [])}
            if id_it in r_map:
                r_it = r_map[id_it]
                el = r_it.get("eleccion")
                if el in RESPUESTAS_VALIDAS_PAR:
                    votos_totales_no_brillo += 1
                    if el in ("izquierda", "derecha"):
                        lado_pos = _resolver_lado_polo_pos_mostrado(r_it, n_info)
                        eligio_pos = el == lado_pos
                        eligio_claro = (
                            eligio_pos if polo_claro == "polo_pos" else (not eligio_pos)
                        )
                        if eligio_claro:
                            votos_al_mas_claro += 1
                        else:
                            votos_al_mas_oscuro += 1

    q_claro_pct = votos_al_mas_claro * 100.0 / max(1, votos_totales_no_brillo)
    q_oscuro_pct = votos_al_mas_oscuro * 100.0 / max(1, votos_totales_no_brillo)

    # Análisis por cada una de las 20 neuronas
    resultados_neuronas: List[Dict[str, Any]] = []
    p_crudos_20: List[float] = []

    for n_info in neuronas_clave:
        id_it = n_info["id_item"]
        dL = float(n_info.get("delta_L", 0.0))
        polo_claro = n_info.get("polo_mas_claro", "polo_pos" if dL >= 0 else "polo_neg")
        polo_oscuro = n_info.get("polo_mas_oscuro", "polo_pos" if dL < 0 else "polo_neg")
        es_solo_brillo = bool(n_info.get("es_eje_solo_brillo", False))

        aciertos_tot = 0
        ninguno_tot = 0
        cont_tot = 0
        aciertos_diseno = 0
        cont_diseno = 0
        aciertos_fuera = 0
        cont_fuera = 0
        tiempos_ms: List[int] = []

        for p_doc in participantes_validos:
            es_diseno = (
                str(
                    p_doc.get("participante", {}).get("trabaja_en_diseno_o_arte", "")
                ).lower()
                == "si"
            )
            r_map = {x["id_item"]: x for x in p_doc.get("parte_2_sentir", [])}
            if id_it in r_map:
                r_it = r_map[id_it]
                el = r_it.get("eleccion")
                if el in RESPUESTAS_VALIDAS_PAR:
                    cont_tot += 1
                    lado_pos = _resolver_lado_polo_pos_mostrado(r_it, n_info)
                    # Regla v3d: "ninguno" cuenta en cont_tot pero como NO acierto (ok = False)
                    if el == "ninguno":
                        ninguno_tot += 1
                        ok = False
                    else:
                        ok = el == lado_pos
                    if ok:
                        aciertos_tot += 1
                    if es_diseno:
                        cont_diseno += 1
                        if ok:
                            aciertos_diseno += 1
                    else:
                        cont_fuera += 1
                        if ok:
                            aciertos_fuera += 1
                    if "tiempo_ms" in r_it:
                        tiempos_ms.append(int(r_it["tiempo_ms"]))

        p_raw = p_valor_binomial_unilateral(aciertos_tot, cont_tot)
        p_crudos_20.append(p_raw)
        pct_tot = round(aciertos_tot * 100.0 / max(1, cont_tot), 2)
        pct_ninguno = round(ninguno_tot * 100.0 / max(1, cont_tot), 2)
        pct_dis = (
            round(aciertos_diseno * 100.0 / cont_diseno, 2) if cont_diseno > 0 else None
        )
        pct_fue = (
            round(aciertos_fuera * 100.0 / cont_fuera, 2) if cont_fuera > 0 else None
        )

        if es_solo_brillo:
            acierto_brillo_pct = 100.0
        else:
            q_emp_polo = q_claro_pct if polo_claro == "polo_pos" else q_oscuro_pct
            cota_salto_lum = 50.0 + 50.0 * min(1.0, abs(dL) / 35.0)
            acierto_brillo_pct = round(max(q_emp_polo, cota_salto_lum), 2)

        supera_brillo = (not es_solo_brillo) and (pct_tot > acierto_brillo_pct)

        resultados_neuronas.append(
            {
                "orden": n_info["orden_neurona"],
                "id_neurona": n_info["id_neurona"],
                "etapa": n_info["etapa"],
                "eje_sensacion": n_info["eje_sensacion"],
                "pregunta": n_info["pregunta"],
                "indicacion_director": n_info.get("indicacion_director", ""),
                "delta_L": dL,
                "polo_mas_claro": polo_claro,
                "polo_mas_oscuro": polo_oscuro,
                "es_eje_solo_brillo": es_solo_brillo,
                "aciertos": aciertos_tot,
                "conteo_ninguno": ninguno_tot,
                "participantes_evaluados": cont_tot,
                "porcentaje_acierto": pct_tot,
                "porcentaje_ninguno": pct_ninguno,
                "acierto_regla_simple_brillo_pct": acierto_brillo_pct,
                "ventaja_sobre_regla_brillo_pp": round(pct_tot - acierto_brillo_pct, 2),
                "supera_regla_brillo": bool(supera_brillo),
                "porcentaje_diseno_arte": pct_dis,
                "porcentaje_fuera_diseno": pct_fue,
                "tiempo_medio_ms": round(sum(tiempos_ms) / max(1, len(tiempos_ms)), 1),
                "p_valor_binomial_crudo": round(p_raw, 6),
            }
        )

    p_holm_20 = holm_bonferroni(p_crudos_20)
    cnt_se_sienten_70_holm = 0
    cnt_superan_brillo = 0
    cnt_se_sienten_de_verdad = 0
    ids_se_sienten_de_verdad: List[str] = []

    for idx, r_n in enumerate(resultados_neuronas):
        r_n["p_valor_ajustado_holm"] = p_holm_20[idx]
        pasa_70_holm = (r_n["porcentaje_acierto"] >= 70.0) and (p_holm_20[idx] < 0.05)
        r_n["se_siente_70pct_holm"] = bool(pasa_70_holm)
        se_siente_verdad = bool(pasa_70_holm and r_n["supera_regla_brillo"])
        r_n["se_siente_de_verdad"] = se_siente_verdad

        if pasa_70_holm:
            cnt_se_sienten_70_holm += 1
        if r_n["supera_regla_brillo"]:
            cnt_superan_brillo += 1
        if se_siente_verdad:
            cnt_se_sienten_de_verdad += 1
            ids_se_sienten_de_verdad.append(r_n["id_neurona"])

    # Controles al azar (4 pares): "ninguno" cuenta como NO acierto y se reporta su %
    aciertos_ctrl = 0
    ninguno_ctrl = 0
    total_ctrl = 0
    elecciones_izq_ctrl = 0
    for p_doc in participantes_validos:
        r_map = {x["id_item"]: x for x in p_doc.get("parte_2_sentir", [])}
        for id_c, info_c in controles_clave.items():
            if id_c in r_map:
                r_c = r_map[id_c]
                el = r_c.get("eleccion")
                if el in RESPUESTAS_VALIDAS_PAR:
                    total_ctrl += 1
                    lado_pos_c = _resolver_lado_polo_pos_mostrado(r_c, info_c)
                    if el == "ninguno":
                        ninguno_ctrl += 1
                    elif el == lado_pos_c:
                        aciertos_ctrl += 1
                    if el == "izquierda":
                        elecciones_izq_ctrl += 1

    pct_ctrl = round(aciertos_ctrl * 100.0 / max(1, total_ctrl), 2)
    pct_ninguno_ctrl = round(ninguno_ctrl * 100.0 / max(1, total_ctrl), 2)
    pct_izq_ctrl = round(elecciones_izq_ctrl * 100.0 / max(1, total_ctrl), 2)

    tot_aciertos_reales = sum(x["aciertos"] for x in resultados_neuronas)
    tot_ninguno_reales = sum(x["conteo_ninguno"] for x in resultados_neuronas)
    tot_eval_reales = sum(x["participantes_evaluados"] for x in resultados_neuronas)
    pct_global_reales = round(tot_aciertos_reales * 100.0 / max(1, tot_eval_reales), 2)
    pct_ninguno_reales = round(tot_ninguno_reales * 100.0 / max(1, tot_eval_reales), 2)
    p_global_vs_azar = round(
        p_valor_binomial_unilateral(tot_aciertos_reales, tot_eval_reales), 6
    )

    n_diseno = sum(
        1
        for p in participantes_validos
        if str(p.get("participante", {}).get("trabaja_en_diseno_o_arte", "")).lower()
        == "si"
    )
    n_fuera = n_val - n_diseno

    # Parte 1 (5 segundos: incluye % de «Ninguno»)
    resumen_parte1 = []
    for id_p1, info_p1 in sorted(parte1_clave.items()):
        votos_pos = 0
        votos_ninguno = 0
        votos_tot = 0
        for p_doc in participantes_validos:
            r1_map = {
                x["id_item"]: x for x in p_doc.get("parte_1_primer_golpe_vista", [])
            }
            if id_p1 in r1_map:
                r1 = r1_map[id_p1]
                el = r1.get("eleccion")
                if el in RESPUESTAS_VALIDAS_PAR:
                    votos_tot += 1
                    lado_pos1 = _resolver_lado_polo_pos_mostrado(r1, info_p1)
                    if el == "ninguno":
                        votos_ninguno += 1
                    elif el == lado_pos1:
                        votos_pos += 1
        resumen_parte1.append(
            {
                "id_item": id_p1,
                "id_neurona": info_p1["id_neurona"],
                "porcentaje_elige_polo_activo_5s": round(
                    votos_pos * 100.0 / max(1, votos_tot), 2
                ),
                "porcentaje_ninguno_5s": round(
                    votos_ninguno * 100.0 / max(1, votos_tot), 2
                ),
            }
        )

    # Parte 3 (Ponerle nombre en 2 o 3 palabras)
    resumen_parte3 = []
    for id_p3, info_p3 in sorted(parte3_clave.items()):
        textos = []
        for p_doc in participantes_validos:
            r3_map = {x["id_item"]: x for x in p_doc.get("parte_3_ponerle_nombre", [])}
            if id_p3 in r3_map and r3_map[id_p3].get("palabras_usuario"):
                textos.append(str(r3_map[id_p3]["palabras_usuario"]))
        resumen_parte3.append(
            {
                "id_item": id_p3,
                "id_neurona": info_p3["id_neurona"],
                "descripciones_participantes": textos,
                "etiqueta_neurona_para_comparacion_claude": info_p3[
                    "etiqueta_interna_neurona"
                ],
            }
        )

    # Separación estricta de los ♥ de Bruno (para N-2 y D-8) frente a los demás
    corazones_bruno_lista: List[Dict[str, Any]] = []
    corazones_otros_por_apodo: Dict[str, List[Dict[str, Any]]] = {}
    conteo_otros_por_pieza: Dict[str, int] = {}

    for p_doc in participantes_validos:
        apodo_raw = str(p_doc.get("participante", {}).get("apodo", "")).strip()
        es_bruno = apodo_raw.lower() == "bruno"
        votos4 = p_doc.get("parte_4_gusto", {}).get("votos", [])
        for v in votos4:
            if v.get("corazon"):
                item_c = {
                    "id_pieza": v["id_pieza"],
                    "sha256_imagen": v.get("sha256_imagen", ""),
                }
                if es_bruno:
                    corazones_bruno_lista.append(item_c)
                else:
                    corazones_otros_por_apodo.setdefault(apodo_raw, []).append(item_c)
                    pid = v["id_pieza"]
                    conteo_otros_por_pieza[pid] = conteo_otros_por_pieza.get(pid, 0) + 1

    ruta_corazones_bruno = carpeta_respuestas / "corazones_bruno_n2_d8.json"
    ruta_corazones_otros = carpeta_respuestas / "corazones_otros_participantes.json"

    ruta_corazones_bruno.write_text(
        json.dumps(
            {
                "propietario": "Bruno",
                "uso_autorizado": "N-2 y D-8 (requiere >= 20 corazones de Bruno)",
                "total_corazones_bruno": len(corazones_bruno_lista),
                "desbloquea_n2_y_d8": len(corazones_bruno_lista) >= 20,
                "piezas_con_corazon": corazones_bruno_lista,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    ruta_corazones_otros.write_text(
        json.dumps(
            {
                "propietario": "Otros participantes (excluidos de N-2 y D-8)",
                "uso_autorizado": "Archivo separado de consulta; NO alimenta N-2 ni D-8",
                "total_corazones_otros": sum(
                    len(x) for x in corazones_otros_por_apodo.values()
                ),
                "por_participante": corazones_otros_por_apodo,
                "conteo_por_pieza": conteo_otros_por_pieza,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "fase": "FASE 5d (v3d.1) · Resultado de El Salón",
        "participantes_validos": n_val,
        "participantes_diseno_arte": n_diseno,
        "participantes_fuera_diseno": n_fuera,
        "participantes_excluidos_atencion": participantes_excluidos_atencion,
        "semillas_apodo_unicas_detectadas": len(set(semillas_vistas)),
        "cumple_minimo_6_personas": bool(n_val >= 6),
        "control_de_brillo": {
            "tasa_empirica_elige_mas_claro_pct": round(q_claro_pct, 2),
            "tasa_empirica_elige_mas_oscuro_pct": round(q_oscuro_pct, 2),
            "neuronas_que_superan_regla_simple_brillo": f"{cnt_superan_brillo}/20",
            "neuronas_que_se_sienten_de_verdad_70pct_holm_y_mas_que_brillo": f"{cnt_se_sienten_de_verdad}/20",
            "ids_neuronas_que_se_sienten_de_verdad": ids_se_sienten_de_verdad,
        },
        "resumen_global_parte_2": {
            "acierto_medio_20_neuronas_pct": pct_global_reales,
            "porcentaje_ninguno_medio_20_neuronas_pct": pct_ninguno_reales,
            "p_valor_global_vs_50pct": p_global_vs_azar,
            "acierto_medio_4_controles_azar_pct": pct_ctrl,
            "porcentaje_ninguno_4_controles_azar_pct": pct_ninguno_ctrl,
            "diferencia_neuronas_vs_controles_pp": round(
                pct_global_reales - pct_ctrl, 2
            ),
            "tasa_eleccion_izquierda_en_controles_pct": pct_izq_ctrl,
            "neuronas_70pct_holm005": f"{cnt_se_sienten_70_holm}/20",
            "neuronas_que_se_sienten_de_verdad": f"{cnt_se_sienten_de_verdad}/20",
        },
        "detalle_20_neuronas_parte_2": resultados_neuronas,
        "resumen_parte_1_golpe_vista_5s": resumen_parte1,
        "resumen_parte_3_ponerle_nombre": resumen_parte3,
        "resumen_parte_4_gusto_corazones": {
            "corazones_bruno_para_n2_y_d8": len(corazones_bruno_lista),
            "desbloquea_n2_y_d8_min_20_bruno": bool(len(corazones_bruno_lista) >= 20),
            "archivo_corazones_bruno": str(ruta_corazones_bruno),
            "corazones_otros_participantes_guardados_aparte": sum(
                len(x) for x in corazones_otros_por_apodo.values()
            ),
            "archivo_corazones_otros_aparte": str(ruta_corazones_otros),
        },
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analiza los JSON de respuestas de «El salón» (FASE 5d · v3d.1)."
    )
    parser.add_argument(
        "--carpeta-respuestas",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon/respuestas",
        help="Carpeta donde Bruno guarda los archivos salon_respuesta_*.json descargados.",
    )
    parser.add_argument(
        "--clave",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon/clave_salon_no_abrir.json",
        help="Ruta a clave_salon_no_abrir.json",
    )
    args = parser.parse_args(argv)
    res = analizar_respuestas_salon(
        Path(args.carpeta_respuestas).expanduser().resolve(),
        Path(args.clave).expanduser().resolve(),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
