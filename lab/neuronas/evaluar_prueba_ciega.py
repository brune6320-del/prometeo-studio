#!/usr/bin/env python3
"""Evaluador de la Prueba Ciega Humana de Bruno (20 pares · FASE 5c).

Compara el archivo de respuestas guardado por Bruno (`respuestas_bruno_20_pares.json`)
contra la clave secreta (`clave_secreta_no_abrir.json`) y calcula:
- Acierto total sobre 20 pares y porcentaje.
- P-valor exacto en la prueba binomial unilateral frente al azar (p = 0.5).
- Confirmación de si alcanza el umbral prerregistrado (>= 15/20 aciertos, p < 0.05).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict


def p_valor_binomial_unilateral(aciertos: int, total: int = 20) -> float:
    """Calcula P(X >= aciertos) bajo H0: X ~ Binomial(total, 0.5)."""
    if aciertos <= 0:
        return 1.0
    if aciertos > total:
        return 0.0
    casos_favorables = sum(math.comb(total, k) for k in range(aciertos, total + 1))
    return round(casos_favorables / float(2**total), 6)


def evaluar_respuestas(ruta_respuestas: Path, ruta_clave: Path) -> Dict[str, Any]:
    resp_data = json.loads(ruta_respuestas.read_text(encoding="utf-8"))
    clave_data = json.loads(ruta_clave.read_text(encoding="utf-8"))

    mapa_resp = {
        int(r["id_par"]): r.get("eleccion") for r in resp_data.get("respuestas", [])
    }
    pares_clave = clave_data["pares"]

    aciertos = 0
    contestados = 0
    detalle = []

    for p in pares_clave:
        id_par = int(p["id_par"])
        correcta = p["respuesta_correcta"]
        elegida = mapa_resp.get(id_par)
        if elegida in ("izquierda", "derecha"):
            contestados += 1
        es_acierto = elegida == correcta
        if es_acierto:
            aciertos += 1
        detalle.append(
            {
                "id_par": id_par,
                "id_neurona_real": p["id_neurona_real"],
                "etapa": p["etapa"],
                "eleccion_bruno": elegida,
                "respuesta_correcta": correcta,
                "acierto": bool(es_acierto),
            }
        )

    total = len(pares_clave)
    p_val = p_valor_binomial_unilateral(aciertos, total)
    supera_umbral = (contestados == total) and (aciertos >= 15)

    return {
        "fase": "FASE 5c · Resultado de la Prueba Ciega Humana (Bruno)",
        "pares_totales": total,
        "pares_contestados": contestados,
        "aciertos": aciertos,
        "porcentaje_acierto": round(aciertos * 100.0 / total, 2),
        "p_valor_binomial_vs_azar": p_val,
        "umbral_minimo_aciertos": 15,
        "supera_umbral_p_menor_005": bool(supera_umbral),
        "detalle_por_par": detalle,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evalúa las respuestas de Bruno en la prueba ciega de 20 pares."
    )
    parser.add_argument(
        "--respuestas",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/prueba-ciega-bruno/respuestas_bruno_20_pares.json",
        help="Ruta al JSON de respuestas guardado por Bruno.",
    )
    parser.add_argument(
        "--clave",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/prueba-ciega-bruno/clave_secreta_no_abrir.json",
        help="Ruta a la clave secreta.",
    )
    args = parser.parse_args()
    res = evaluar_respuestas(
        Path(args.respuestas).expanduser().resolve(),
        Path(args.clave).expanduser().resolve(),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
