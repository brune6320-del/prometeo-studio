#!/usr/bin/env python3
"""FASE 5d · Analizador estadístico de «El salón» (Regla 8 · CPU, 0 Colab).

Procesa los archivos JSON descargados por los participantes en la carpeta de respuestas
(`salon_respuesta_*.json`) junto con la clave secreta (`clave_salon_no_abrir.json`):
1. Filtro de atención (Regla 5): descarta a quien falle AMBOS pares obvios de atención
   (`atencion_01` y `atencion_02`).
2. Por cada una de las 20 neuronas de la Parte 2 (Sentir):
   - Calcula el % de personas válidas que eligen el lado predicho por la neurona (`polo_pos`).
   - Calcula el p-valor binomial exacto unilateral frente al azar (p = 0.5).
   - Aplica la corrección escalonada de Holm-Bonferroni sobre las 20 neuronas.
   - Declara que la neurona «se siente» (`se_siente = true`) si y solo si:
     acierto >= 70.0% y p_ajustado_Holm < 0.05.
3. Global y controles (Reglas 4 y 8):
   - Acierto medio en las 20 neuronas frente al 50% y frente al acierto medio en los
     4 pares de control al azar (`control_azar_01..04`), más tasa de elección izquierda/derecha.
   - Desglose separado entre gente de diseño/arte (`si`) y gente de fuera (`no`).
4. Parte 1 (5 s), Parte 3 (texto libre 2-3 palabras para Claude) y Parte 4 (conteo de ♥
   para desbloquear N-2 y D-8 cuando Bruno marque >= 20 ♥).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.dont_write_bytecode = True


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


def analizar_respuestas_salon(
    carpeta_respuestas: Path,
    ruta_clave: Path,
) -> Dict[str, Any]:
    clave = json.loads(ruta_clave.read_text(encoding="utf-8"))
    archivos_json = sorted(carpeta_respuestas.glob("*.json"))

    mapa_atencion = {
        x["id_item"]: x["lado_esperado_atencion"]
        for x in clave["parte_2_atencion_2_clave"]
    }
    mapa_controles = {
        x["id_item"]: x["lado_predicho_ficticio"]
        for x in clave["parte_2_controles_4_clave"]
    }
    neuronas_clave = clave["parte_2_neuronas_20_clave"]
    parte1_clave = {x["id_item"]: x for x in clave["parte_1_clave"]}
    parte3_clave = {x["id_item"]: x for x in clave["parte_3_clave"]}

    participantes_validos: List[Dict[str, Any]] = []
    participantes_excluidos_atencion: List[str] = []

    for ruta_r in archivos_json:
        datos = json.loads(ruta_r.read_text(encoding="utf-8"))
        part = datos.get("participante", {})
        if not part.get("consentimiento_informado", False):
            continue
        apodo = str(part.get("apodo", ruta_r.stem))
        resp2_map = {
            x["id_item"]: x for x in datos.get("parte_2_sentir", [])
        }
        aciertos_at = 0
        for id_at, lado_esp in mapa_atencion.items():
            if resp2_map.get(id_at, {}).get("eleccion") == lado_esp:
                aciertos_at += 1
        # Regla 5: las respuestas de quien falle los dos (aciertos_at == 0) no cuentan
        if aciertos_at == 0:
            participantes_excluidos_atencion.append(apodo)
            continue
        participantes_validos.append(datos)

    n_val = len(participantes_validos)
    if n_val == 0:
        return {
            "fase": "FASE 5d · Análisis de El Salón",
            "estado": "PENDIENTE_PARTICIPANTES",
            "archivos_encontrados": len(archivos_json),
            "participantes_validos": 0,
            "participantes_excluidos_por_fallar_ambos_controles_atencion": participantes_excluidos_atencion,
            "minimo_requerido": 6,
            "nota": "Aún no hay respuestas válidas en la carpeta de respuestas.",
        }

    # Análisis por neurona (20 neuronas de la Parte 2)
    resultados_neuronas: List[Dict[str, Any]] = []
    p_crudos_20: List[float] = []

    for n_info in neuronas_clave:
        id_it = n_info["id_item"]
        lado_pred = n_info["lado_predicho"]
        aciertos_tot = 0
        cont_tot = 0
        aciertos_diseno = 0
        cont_diseno = 0
        aciertos_fuera = 0
        cont_fuera = 0
        tiempos_ms: List[int] = []

        for p_doc in participantes_validos:
            es_diseno = (
                str(p_doc.get("participante", {}).get("trabaja_en_diseno_o_arte", "")).lower()
                == "si"
            )
            r_map = {x["id_item"]: x for x in p_doc.get("parte_2_sentir", [])}
            if id_it in r_map:
                el = r_map[id_it].get("eleccion")
                if el in ("izquierda", "derecha"):
                    cont_tot += 1
                    ok = el == lado_pred
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
                    if "tiempo_ms" in r_map[id_it]:
                        tiempos_ms.append(int(r_map[id_it]["tiempo_ms"]))

        p_raw = p_valor_binomial_unilateral(aciertos_tot, cont_tot)
        p_crudos_20.append(p_raw)
        pct_tot = round(aciertos_tot * 100.0 / max(1, cont_tot), 2)
        pct_dis = (
            round(aciertos_diseno * 100.0 / cont_diseno, 2) if cont_diseno > 0 else None
        )
        pct_fue = (
            round(aciertos_fuera * 100.0 / cont_fuera, 2) if cont_fuera > 0 else None
        )

        resultados_neuronas.append(
            {
                "orden": n_info["orden_neurona"],
                "id_neurona": n_info["id_neurona"],
                "etapa": n_info["etapa"],
                "eje_sensacion": n_info["eje_sensacion"],
                "pregunta": n_info["pregunta"],
                "lado_predicho": lado_pred,
                "aciertos": aciertos_tot,
                "participantes_evaluados": cont_tot,
                "porcentaje_acierto": pct_tot,
                "porcentaje_diseno_arte": pct_dis,
                "porcentaje_fuera_diseno": pct_fue,
                "tiempo_medio_ms": round(sum(tiempos_ms) / max(1, len(tiempos_ms)), 1),
                "p_valor_binomial_crudo": round(p_raw, 6),
            }
        )

    p_holm_20 = holm_bonferroni(p_crudos_20)
    neuronas_que_se_sienten = 0
    for idx, r_n in enumerate(resultados_neuronas):
        r_n["p_valor_ajustado_holm"] = p_holm_20[idx]
        se_siente = (r_n["porcentaje_acierto"] >= 70.0) and (p_holm_20[idx] < 0.05)
        r_n["se_siente"] = bool(se_siente)
        if se_siente:
            neuronas_que_se_sienten += 1

    # Controles al azar (4 pares)
    aciertos_ctrl = 0
    total_ctrl = 0
    elecciones_izq_ctrl = 0
    for p_doc in participantes_validos:
        r_map = {x["id_item"]: x for x in p_doc.get("parte_2_sentir", [])}
        for id_c, lado_fic in mapa_controles.items():
            el = r_map.get(id_c, {}).get("eleccion")
            if el in ("izquierda", "derecha"):
                total_ctrl += 1
                if el == lado_fic:
                    aciertos_ctrl += 1
                if el == "izquierda":
                    elecciones_izq_ctrl += 1

    pct_ctrl = round(aciertos_ctrl * 100.0 / max(1, total_ctrl), 2)
    pct_izq_ctrl = round(elecciones_izq_ctrl * 100.0 / max(1, total_ctrl), 2)

    # Totales globales y por segmento (diseño vs fuera)
    tot_aciertos_reales = sum(x["aciertos"] for x in resultados_neuronas)
    tot_eval_reales = sum(x["participantes_evaluados"] for x in resultados_neuronas)
    pct_global_reales = round(tot_aciertos_reales * 100.0 / max(1, tot_eval_reales), 2)
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

    # Parte 1 (5 segundos: qué salta a la vista)
    resumen_parte1 = []
    for id_p1, info_p1 in sorted(parte1_clave.items()):
        votos_pos = 0
        votos_tot = 0
        for p_doc in participantes_validos:
            r1_map = {
                x["id_item"]: x for x in p_doc.get("parte_1_primer_golpe_vista", [])
            }
            el = r1_map.get(id_p1, {}).get("eleccion")
            if el in ("izquierda", "derecha"):
                votos_tot += 1
                if el == info_p1["lado_polo_pos"]:
                    votos_pos += 1
        resumen_parte1.append(
            {
                "id_item": id_p1,
                "id_neurona": info_p1["id_neurona"],
                "porcentaje_elige_polo_activo_5s": round(
                    votos_pos * 100.0 / max(1, votos_tot), 2
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

    # Parte 4 (Gusto ♥ para N-2 y D-8)
    corazones_por_pieza: Dict[str, int] = {}
    corazones_bruno = 0
    for p_doc in participantes_validos:
        apodo = str(p_doc.get("participante", {}).get("apodo", "")).strip().lower()
        votos4 = p_doc.get("parte_4_gusto", {}).get("votos", [])
        for v in votos4:
            if v.get("corazon"):
                pid = v["id_pieza"]
                corazones_por_pieza[pid] = corazones_por_pieza.get(pid, 0) + 1
                if "bruno" in apodo:
                    corazones_bruno += 1

    return {
        "fase": "FASE 5d · Resultado de El Salón (Prueba de sensaciones con personas)",
        "participantes_validos": n_val,
        "participantes_diseno_arte": n_diseno,
        "participantes_fuera_diseno": n_fuera,
        "participantes_excluidos_atencion": participantes_excluidos_atencion,
        "cumple_minimo_6_personas": bool(n_val >= 6),
        "resumen_global_parte_2": {
            "acierto_medio_20_neuronas_pct": pct_global_reales,
            "p_valor_global_vs_50pct": p_global_vs_azar,
            "acierto_medio_4_controles_azar_pct": pct_ctrl,
            "diferencia_neuronas_vs_controles_pp": round(
                pct_global_reales - pct_ctrl, 2
            ),
            "tasa_eleccion_izquierda_en_controles_pct": pct_izq_ctrl,
            "neuronas_que_se_sienten_70pct_holm005": f"{neuronas_que_se_sienten}/20",
        },
        "detalle_20_neuronas_parte_2": resultados_neuronas,
        "resumen_parte_1_golpe_vista_5s": resumen_parte1,
        "resumen_parte_3_ponerle_nombre": resumen_parte3,
        "resumen_parte_4_gusto_corazones": {
            "total_corazones_salon": sum(corazones_por_pieza.values()),
            "corazones_bruno": corazones_bruno,
            "desbloquea_n2_y_d8_min_20_bruno": bool(corazones_bruno >= 20),
            "top_piezas_mas_votadas": sorted(
                corazones_por_pieza.items(), key=lambda x: (-x[1], x[0])
            )[:15],
        },
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analiza los JSON de respuestas de «El salón» (FASE 5d)."
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
