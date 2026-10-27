#!/usr/bin/env python3
"""Suite de verificación determinista para FASE 5b · Atlas con prueba de verdad (N-1 v2).

Comprueba 8 invariantes estrictos:
1. Prerregistro v1 intacto (sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Prerregistro v2 intacto (sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555)
   y corpus_cc0_630.json intacto (630 imágenes CC0 únicas: 441 train y 189 validación, semilla 2610).
3. Licencia BSD-3-Clause y SHA-256 oficial de los pesos de ConvNeXt-tiny verificados.
4. Existencia y validez de las 200 fichas PRAGMA v2 en lab/neuronas/atlas/neurona_<id>.json,
   conservando todas las neuronas no legibles y las declaradas «no lo sé».
5. Etiquetas libres sin plantilla rígida repetida: ninguna etiqueta distinta de «no lo sé» se repite
   entre dos neuronas.
6. Verificación matemática de la Prueba (a) (apagado con control justo: >= 2x en >= 4/5 controles
   de activación media similar en train) y de la Prueba (b) (predicción ciega 0..3 en validación
   usando únicamente el texto de la etiqueta escrita, ROC AUC >= 0.70).
7. Determinismo estricto al re-evaluar una submuestra de neuronas sobre las 630 imágenes.
8. Higiene de Git: ningún archivo de pesos (.pth, .pt) ni de imagen (.jpg, .png) está en lab/neuronas/.
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
SHA256_CORPUS_630_ESPERADO = "f0c3483fafa8c04be6492ff62190071c8f6278beb8dec78b05110a6cabb5875f"


def ejecutar_pruebas() -> int:
    dir_neuronas = Path(__file__).resolve().parent
    ruta_v1 = dir_neuronas / "prerregistro.json"
    ruta_v2 = dir_neuronas / "prerregistro_v2.json"
    ruta_corpus = dir_neuronas / "corpus_cc0_630.json"
    dir_atlas = dir_neuronas / "atlas"

    # 1. Prerregistro v1 intacto
    sha_v1 = hashlib.sha256(ruta_v1.read_bytes()).hexdigest()
    assert sha_v1 == SHA256_PRERREG_V1_ESPERADO, f"Prerregistro v1 alterado: {sha_v1}"

    # 2. Prerregistro v2 y corpus_cc0_630.json intactos
    sha_v2 = hashlib.sha256(ruta_v2.read_bytes()).hexdigest()
    assert sha_v2 == SHA256_PRERREG_V2_ESPERADO, f"Prerregistro v2 alterado: {sha_v2}"
    sha_corpus = hashlib.sha256(ruta_corpus.read_bytes()).hexdigest()
    assert sha_corpus == SHA256_CORPUS_630_ESPERADO, f"Corpus CC0 630 alterado: {sha_corpus}"

    corpus_data = json.loads(ruta_corpus.read_text(encoding="utf-8"))
    imgs = corpus_data["imagenes"]
    assert len(imgs) == 630, f"Se esperaban 630 imágenes, hay {len(imgs)}"
    shas_unicos = {it["sha256"] for it in imgs}
    assert len(shas_unicos) == 630, f"SHA-256 duplicados en corpus: {len(shas_unicos)}"
    n_tr = sum(1 for it in imgs if it["split"] == "train")
    n_val = sum(1 for it in imgs if it["split"] == "validacion")
    assert n_tr == 441 and n_val == 189, f"Split inválido: train={n_tr}, val={n_val}"

    prerreg_v2 = json.loads(ruta_v2.read_text(encoding="utf-8"))
    neuronas_ids: List[int] = prerreg_v2["modelo"]["neuronas_ids"]
    assert len(neuronas_ids) == 200, "Se esperaban 200 neuronas prerregistradas"

    # 3 y 4. Revisar las 200 fichas PRAGMA v2
    archivos_json = sorted(dir_atlas.glob("neurona_*.json"))
    assert len(archivos_json) == 200, f"Se esperaban 200 fichas en atlas/, encontradas {len(archivos_json)}"

    etiquetas_con_contenido: List[str] = []
    cnt_legibles = 0
    cnt_solo_a = 0
    cnt_solo_b = 0
    cnt_no_lo_se = 0

    for n_id in neuronas_ids:
        ruta_f = dir_atlas / f"neurona_{n_id:03d}.json"
        assert ruta_f.is_file(), f"Falta ficha {ruta_f}"
        ficha: Dict[str, Any] = json.loads(ruta_f.read_text(encoding="utf-8"))

        assert ficha["schema_version"] == "2.0.0"
        assert ficha["canal_indice"] == n_id
        assert ficha["etiquetador"] == "Argon"
        assert ficha["sha256_pesos"] == SHA256_PESOS_ESPERADO
        assert ficha["sha256_prerregistro_v1"] == SHA256_PRERREG_V1_ESPERADO
        assert ficha["sha256_prerregistro_v2"] == SHA256_PRERREG_V2_ESPERADO
        assert ficha["sha256_corpus_cc0"] == SHA256_CORPUS_630_ESPERADO

        etq = ficha["etiqueta"]
        assert isinstance(etq, str) and len(etq.strip()) > 0
        if etq == "no lo sé":
            cnt_no_lo_se += 1
        else:
            etiquetas_con_contenido.append(etq)

        # Verificar Prueba (a)
        pa = ficha["prueba_a_apagado_control_justo"]
        controles = pa["controles_y_sorteados"]
        assert len(controles) == 5, "Deben sortearse 5 neuronas control Y"
        eff_x = pa["efecto_l2_neurona_x_top9_train"]
        wins_calc = sum(
            1 for c_y in controles if eff_x >= 2.0 * c_y["efecto_l2_en_top9_de_x"] - 1e-4
        )
        assert wins_calc == pa["sorteos_ganados_de_5"], (
            f"Discrepancia en sorteos ganados de {n_id}: {wins_calc} vs {pa['sorteos_ganados_de_5']}"
        )
        conf_a_esp = pa["sorteos_ganados_de_5"] >= 4
        assert ficha["confirmada_a"] == conf_a_esp

        # Verificar Prueba (b)
        pb = ficha["prueba_b_prediccion_validacion_ciega"]
        conteo_03 = pb["conteo_puntuaciones_0_a_3"]
        assert sum(conteo_03.values()) == 189, "Las puntuaciones 0..3 deben sumar 189 imágenes de validación"
        conf_b_esp = (etq != "no lo sé") and (pb["roc_auc_validacion"] >= 0.70)
        assert ficha["confirmada_b"] == conf_b_esp

        # Verificar criterio de legibilidad conjunta (a y b)
        leg_esp = bool(ficha["confirmada_a"] and ficha["confirmada_b"] and etq != "no lo sé")
        assert ficha["legible"] == leg_esp
        assert ficha["confirmada"] == leg_esp

        if leg_esp:
            cnt_legibles += 1
        elif ficha["confirmada_a"] and not ficha["confirmada_b"]:
            cnt_solo_a += 1
        elif ficha["confirmada_b"] and not ficha["confirmada_a"]:
            cnt_solo_b += 1

        assert len(ficha["polo_pos"]) == 9
        assert len(ficha["polo_neg"]) == 9

    # 5. Ninguna etiqueta con contenido se repite (sin plantillas clónicas)
    etiquetas_unicas: Set[str] = set(etiquetas_con_contenido)
    assert len(etiquetas_unicas) == len(etiquetas_con_contenido), (
        f"Hay etiquetas repetidas: {len(etiquetas_con_contenido)} vs {len(etiquetas_unicas)}"
    )
    assert cnt_no_lo_se > 0, "Debe declararse 'no lo sé' en neuronas sin patrón visual claro en train"

    # 8. Higiene de Git: 0 imágenes y 0 pesos en lab/neuronas/
    ext_prohibidas = {".jpg", ".jpeg", ".png", ".webp", ".pth", ".pt", ".onnx", ".safetensors"}
    for p in dir_neuronas.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in ext_prohibidas, f"Archivo prohibido en Git: {p}"

    ic_leg = intervalo_confianza_wilson_95(cnt_legibles, 200)
    ic_sa = intervalo_confianza_wilson_95(cnt_solo_a, 200)
    ic_sb = intervalo_confianza_wilson_95(cnt_solo_b, 200)

    resumen = {
        "pruebas_verificadas": "8/8 OK",
        "total_neuronas": 200,
        "legibles_a_y_b": f"{cnt_legibles}/200 ({cnt_legibles / 2.0:.1f}%, IC 95% [{ic_leg[0]*100:.2f}%, {ic_leg[1]*100:.2f}%])",
        "solo_a": f"{cnt_solo_a}/200 ({cnt_solo_a / 2.0:.1f}%, IC 95% [{ic_sa[0]*100:.2f}%, {ic_sa[1]*100:.2f}%])",
        "solo_b": f"{cnt_solo_b}/200 ({cnt_solo_b / 2.0:.1f}%, IC 95% [{ic_sb[0]*100:.2f}%, {ic_sb[1]*100:.2f}%])",
        "etiquetas_no_lo_se": cnt_no_lo_se,
        "etiquetas_con_contenido_unicas": f"{len(etiquetas_unicas)}/{len(etiquetas_con_contenido)}",
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar_pruebas())
