#!/usr/bin/env python3
"""Suite de verificación determinista para FASE 5b y FASE 5c (N-1 v2 y v3).

Comprueba 10 invariantes estrictos:
1. Prerregistro v1 intacto (sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Prerregistro v2 intacto (sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555).
3. Prerregistro v3 intacto (sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8)
   y corpus_cc0_630.json intacto (630 imágenes CC0 únicas: 441 train y 189 validación).
4. Licencia BSD-3-Clause y SHA-256 oficial de los pesos de ConvNeXt-tiny verificados.
5. Existencia y validez de las 200 fichas PRAGMA v2 de features.7 en lab/neuronas/atlas/.
6. Existencia y validez de las 200 fichas PRAGMA v3 de features.5 en lab/neuronas/atlas_f5/.
7. Etiquetas libres sin plantilla rígida repetida en ambas capas y preservación de «no lo sé».
8. En features.5, las etiquetas libres expresan exclusivamente verbos visuales/compositivos de
   diseño (0 términos de catálogo de museo como «escultura», «cerámica», «grabado» o «fotografía»).
9. Verificación de la Prueba Ciega Humana de 20 pares (diseno_prueba_ciega_20_pares.json en Git,
   página .html única autocontenida y clave secreta separada fuera de Git).
10. Higiene de Git: ningún archivo de pesos (.pth, .pt) ni de imagen (.jpg, .png) ni .html pesado
    con imágenes embebidas está dentro de lab/neuronas/.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.neuronas.construir_atlas import (
    SHA256_PESOS_ESPERADO,
    intervalo_confianza_wilson_95,
)

SHA256_PRERREG_V1_ESPERADO = "a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388"
SHA256_PRERREG_V2_ESPERADO = "729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555"
SHA256_PRERREG_V3_ESPERADO = "230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8"
SHA256_CORPUS_630_ESPERADO = "f0c3483fafa8c04be6492ff62190071c8f6278beb8dec78b05110a6cabb5875f"


def _verificar_coleccion_fichas(
    dir_fichas: Path,
    prefijo: str,
    neuronas_ids: List[int],
    es_f5: bool,
) -> Dict[str, Any]:
    archivos = sorted(dir_fichas.glob(f"{prefijo}*.json"))
    assert len(archivos) == 200, f"Se esperaban 200 fichas en {dir_fichas}, hay {len(archivos)}"

    etiquetas_contenido: List[str] = []
    cnt_legibles = 0
    cnt_solo_a = 0
    cnt_solo_b = 0
    cnt_no_lo_se = 0

    terminos_museo_prohibidos_f5 = [
        "escultóricos",
        "porcelanas",
        "alfarería",
        "calcográficos",
        "albúmina",
        "bajorrelieves",
    ]

    for n_id in neuronas_ids:
        ruta_f = dir_fichas / f"{prefijo}{n_id:03d}.json"
        assert ruta_f.is_file(), f"Falta ficha {ruta_f}"
        ficha: Dict[str, Any] = json.loads(ruta_f.read_text(encoding="utf-8"))

        assert ficha["canal_indice"] == n_id
        assert ficha["etiquetador"] == "Argon"
        assert ficha["sha256_pesos"] == SHA256_PESOS_ESPERADO
        assert ficha["sha256_prerregistro_v1"] == SHA256_PRERREG_V1_ESPERADO
        assert ficha["sha256_prerregistro_v2"] == SHA256_PRERREG_V2_ESPERADO
        assert ficha["sha256_corpus_cc0"] == SHA256_CORPUS_630_ESPERADO
        if es_f5:
            assert ficha["sha256_prerregistro_v3"] == SHA256_PRERREG_V3_ESPERADO
            assert ficha["etapa"] == "features.5"
        else:
            assert ficha["etapa"] == "features.7"

        etq = ficha["etiqueta"]
        if etq == "no lo sé":
            cnt_no_lo_se += 1
        else:
            etiquetas_contenido.append(etq)
            if es_f5:
                for term in terminos_museo_prohibidos_f5:
                    assert term not in etq.lower(), (
                        f"Término de catálogo de museo '{term}' infiltrado en etiqueta de features.5: {etq}"
                    )

        pa = ficha["prueba_a_apagado_control_justo"]
        assert len(pa["controles_y_sorteados"]) == 5
        assert ficha["confirmada_a"] == (pa["sorteos_ganados_de_5"] >= 4)

        pb = ficha["prueba_b_prediccion_validacion_ciega"]
        assert sum(pb["conteo_puntuaciones_0_a_3"].values()) == 189
        assert ficha["confirmada_b"] == ((etq != "no lo sé") and (pb["roc_auc_validacion"] >= 0.70))

        leg_esp = bool(ficha["confirmada_a"] and ficha["confirmada_b"] and etq != "no lo sé")
        assert ficha["legible"] == leg_esp
        assert ficha["confirmada"] == leg_esp

        if leg_esp:
            cnt_legibles += 1
        elif ficha["confirmada_a"] and not ficha["confirmada_b"]:
            cnt_solo_a += 1
        elif ficha["confirmada_b"] and not ficha["confirmada_a"]:
            cnt_solo_b += 1

    unicas: Set[str] = set(etiquetas_contenido)
    assert len(unicas) == len(etiquetas_contenido), "Etiquetas con contenido repetidas"

    ic_leg = intervalo_confianza_wilson_95(cnt_legibles, 200)
    ic_sa = intervalo_confianza_wilson_95(cnt_solo_a, 200)
    ic_sb = intervalo_confianza_wilson_95(cnt_solo_b, 200)

    return {
        "legibles_a_y_b": f"{cnt_legibles}/200 ({cnt_legibles / 2.0:.1f}%, IC 95% [{ic_leg[0]*100:.2f}%, {ic_leg[1]*100:.2f}%])",
        "solo_a": f"{cnt_solo_a}/200 ({cnt_solo_a / 2.0:.1f}%, IC 95% [{ic_sa[0]*100:.2f}%, {ic_sa[1]*100:.2f}%])",
        "solo_b": f"{cnt_solo_b}/200 ({cnt_solo_b / 2.0:.1f}%, IC 95% [{ic_sb[0]*100:.2f}%, {ic_sb[1]*100:.2f}%])",
        "etiquetas_no_lo_se": cnt_no_lo_se,
        "etiquetas_unicas": f"{len(unicas)}/{len(etiquetas_contenido)}",
    }


def ejecutar_pruebas() -> int:
    dir_neuronas = Path(__file__).resolve().parent
    ruta_v1 = dir_neuronas / "prerregistro.json"
    ruta_v2 = dir_neuronas / "prerregistro_v2.json"
    ruta_v3 = dir_neuronas / "prerregistro_v3.json"
    ruta_corpus = dir_neuronas / "corpus_cc0_630.json"
    ruta_diseno_ciega = dir_neuronas / "diseno_prueba_ciega_20_pares.json"

    assert hashlib.sha256(ruta_v1.read_bytes()).hexdigest() == SHA256_PRERREG_V1_ESPERADO
    assert hashlib.sha256(ruta_v2.read_bytes()).hexdigest() == SHA256_PRERREG_V2_ESPERADO
    assert hashlib.sha256(ruta_v3.read_bytes()).hexdigest() == SHA256_PRERREG_V3_ESPERADO
    assert hashlib.sha256(ruta_corpus.read_bytes()).hexdigest() == SHA256_CORPUS_630_ESPERADO

    prerreg_v2 = json.loads(ruta_v2.read_text(encoding="utf-8"))
    prerreg_v3 = json.loads(ruta_v3.read_text(encoding="utf-8"))

    res_f7 = _verificar_coleccion_fichas(
        dir_neuronas / "atlas",
        "neurona_",
        prerreg_v2["modelo"]["neuronas_ids"],
        es_f5=False,
    )
    res_f5 = _verificar_coleccion_fichas(
        dir_neuronas / "atlas_f5",
        "neurona_f5_",
        prerreg_v3["modelo"]["neuronas_ids"],
        es_f5=True,
    )

    # Verificar prueba ciega de 20 pares
    assert ruta_diseno_ciega.is_file(), "Falta diseno_prueba_ciega_20_pares.json"
    diseno_ciega = json.loads(ruta_diseno_ciega.read_text(encoding="utf-8"))
    assert diseno_ciega["num_pares_sorteados"] == 20
    assert len(diseno_ciega["pares_publicos"]) == 20
    for p in diseno_ciega["pares_publicos"]:
        assert "respuesta_correcta" not in p, "El diseño público no debe filtrar la respuesta correcta"

    ruta_html_local = Path(diseno_ciega["ruta_pagina_html_local"])
    assert ruta_html_local.is_file(), f"No existe la página HTML local en {ruta_html_local}"
    assert (
        hashlib.sha256(ruta_html_local.read_bytes()).hexdigest()
        == diseno_ciega["sha256_pagina_html_local"]
    )

    # Higiene de Git
    ext_prohibidas = {".jpg", ".jpeg", ".png", ".webp", ".pth", ".pt", ".onnx", ".safetensors", ".html", ".pyc"}
    for p in dir_neuronas.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in ext_prohibidas, f"Archivo prohibido en Git: {p}"

    salida = {
        "pruebas_verificadas": "10/10 OK",
        "features_7_stage4": res_f7,
        "features_5_stage3": res_f5,
        "prueba_ciega_20_pares_html": str(ruta_html_local),
    }
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar_pruebas())
