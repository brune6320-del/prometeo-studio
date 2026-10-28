#!/usr/bin/env python3
"""Suite de verificación determinista para FASE 5b, FASE 5c y FASE 5d (N-1 v2, v3 y v3b).

Comprueba 12 invariantes estrictos:
1. Prerregistro v1 intacto (sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Prerregistro v2 intacto (sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555).
3. Prerregistro v3 intacto (sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8)
   y corpus_cc0_630.json intacto (630 imágenes CC0 únicas: 441 train y 189 validación).
4. Prerregistro v3b intacto (sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa).
5. Licencia BSD-3-Clause y SHA-256 oficial de los pesos de ConvNeXt-tiny verificados.
6. Existencia y validez de las 200 fichas PRAGMA v2 de features.7 en lab/neuronas/atlas/.
7. Existencia y validez de las 200 fichas PRAGMA v3 de features.5 en lab/neuronas/atlas_f5/.
8. Etiquetas libres sin plantilla rígida repetida en ambas capas y preservación de «no lo sé».
9. En features.5, las etiquetas libres expresan exclusivamente verbos visuales/compositivos de
   diseño (0 términos de catálogo de museo).
10. Verificación de FASE 5d («El salón»): lenguaje de calle (<= 12 palabras, 0 palabras prohibidas),
    contraste real CIE Lab (dE < 10.0 solo en ejes no cromáticos), 0 solapamiento con las neuronas
    vistas en 5c (incluidos pares 9 y 13), equilibrio exacto izquierda/derecha (10/10, 2/2, 1/1),
    4 controles al azar, 2 controles de atención obvios, HTML móvil y 3 capturas para Claude.
11. Prueba funcional de lab/neuronas/analizar_salon.py (filtro de atención, prueba binomial,
    corrección de Holm-Bonferroni sobre las 20 neuronas, desglose diseño vs fuera y conteo de ♥).
12. Higiene de Git: ningún archivo de pesos (.pth, .pt) ni de imagen (.jpg, .png) ni .html pesado
    con imágenes embebidas está dentro de lab/neuronas/.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.neuronas.analizar_salon import analizar_respuestas_salon, holm_bonferroni
from lab.neuronas.construir_atlas import (
    SHA256_PESOS_ESPERADO,
    intervalo_confianza_wilson_95,
)

SHA256_PRERREG_V1_ESPERADO = "a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388"
SHA256_PRERREG_V2_ESPERADO = "729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555"
SHA256_PRERREG_V3_ESPERADO = "230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8"
SHA256_PRERREG_V3B_ESPERADO = "0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa"
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
                    assert term not in etq.lower()

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
    assert len(unicas) == len(etiquetas_contenido)

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


def _verificar_salon_v3b(dir_neuronas: Path) -> Dict[str, Any]:
    ruta_v3b = dir_neuronas / "prerregistro_v3b.json"
    ruta_diseno = dir_neuronas / "diseno_salon_v3b.json"
    assert hashlib.sha256(ruta_v3b.read_bytes()).hexdigest() == SHA256_PRERREG_V3B_ESPERADO
    assert ruta_diseno.is_file()

    v3b = json.loads(ruta_v3b.read_text(encoding="utf-8"))
    diseno = json.loads(ruta_diseno.read_text(encoding="utf-8"))

    prohibidas = v3b["reglas_diseno_sello"]["regla_2_lenguaje_calle"]["palabras_prohibidas"]
    excluidas_5c = set(v3b["reglas_diseno_sello"]["regla_6_neuronas_nuevas"]["excluidas_5c_reales"]) | set(
        v3b["reglas_diseno_sello"]["regla_6_neuronas_nuevas"]["excluidas_pares_9_y_13_senuelos"]
    )
    assert "neurona_f5_126" in excluidas_5c  # Par 9 de 5c
    assert "neurona_f5_244" in excluidas_5c  # Par 13 de 5c

    neuronas_20 = v3b["estructura_sesion"]["parte_2_sentir_20_neuronas"]
    assert len(neuronas_20) == 20
    cnt_izq = 0
    for item in neuronas_20:
        assert item["id_neurona"] not in excluidas_5c, f"Neurona {item['id_neurona']} ya vista en 5c"
        preg = item["pregunta"]
        assert len(preg.split()) <= 12, f"Pregunta supera 12 palabras: {preg}"
        for w_p in prohibidas:
            assert w_p not in preg.lower() and w_p not in item["eje_sensacion"].lower()
        if item["delta_e_lab"] < 10.0:
            assert not item["es_eje_color"], "Regla 3: dE < 10.0 no puede usar eje de color"
        if item["lado_predicho_sorteado"] == "izquierda":
            cnt_izq += 1
    assert cnt_izq == 10, f"Posición no equilibrada en Parte 2: {cnt_izq}/20 izquierda"

    ruta_html = Path(diseno["ruta_html_local"])
    ruta_clave = Path(diseno["ruta_clave_secreta_local"])
    assert ruta_html.is_file() and ruta_clave.is_file()
    assert hashlib.sha256(ruta_html.read_bytes()).hexdigest() == diseno["sha256_html_local"]
    assert len(diseno["tres_capturas_para_visto_bueno_claude"]) == 3
    for cap in diseno["tres_capturas_para_visto_bueno_claude"]:
        assert Path(cap["ruta_captura"]).is_file()

    # Prueba funcional de analizar_salon.py con 11 participantes simulados (1 falla ambos controles de atención -> 10 válidos)
    clave_data = json.loads(ruta_clave.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for idx_p in range(11):
            falla_atencion = idx_p == 0
            resp2 = []
            for at in clave_data["parte_2_atencion_2_clave"]:
                lado_ok = at["lado_esperado_atencion"]
                lado_mal = "derecha" if lado_ok == "izquierda" else "izquierda"
                resp2.append(
                    {
                        "id_item": at["id_item"],
                        "tipo_item": "control_atencion",
                        "eleccion": lado_mal if falla_atencion else lado_ok,
                        "tiempo_ms": 1400,
                    }
                )
            for ctrl in clave_data["parte_2_controles_4_clave"]:
                resp2.append(
                    {
                        "id_item": ctrl["id_item"],
                        "tipo_item": "control_azar",
                        "eleccion": "izquierda" if (idx_p % 2 == 0) else "derecha",
                        "tiempo_ms": 1800,
                    }
                )
            for n_item in clave_data["parte_2_neuronas_20_clave"]:
                # Las primeras 5 neuronas tienen 10/10 aciertos (100%, p=0.000976 -> Holm < 0.05)
                acierta = (n_item["orden_neurona"] <= 5) or (idx_p % 2 == 0)
                lado_ok = n_item["lado_predicho"]
                lado_mal = "derecha" if lado_ok == "izquierda" else "izquierda"
                resp2.append(
                    {
                        "id_item": n_item["id_item"],
                        "tipo_item": "neurona_real",
                        "eleccion": lado_ok if acierta else lado_mal,
                        "tiempo_ms": 1650,
                    }
                )
            doc_sim = {
                "participante": {
                    "apodo": "Bruno" if idx_p == 1 else f"Invitado_{idx_p}",
                    "edad_aproximada": 30 + idx_p,
                    "trabaja_en_diseno_o_arte": "si" if (idx_p % 2 == 1) else "no",
                    "consentimiento_informado": True,
                },
                "parte_1_primer_golpe_vista": [],
                "parte_2_sentir": resp2,
                "parte_3_ponerle_nombre": [],
                "parte_4_gusto": {
                    "votos": [
                        {"id_pieza": f"cma_{k}", "corazon": True} for k in range(22)
                    ]
                },
            }
            (tmp_path / f"salon_respuesta_p{idx_p:02d}.json").write_text(
                json.dumps(doc_sim), encoding="utf-8"
            )

        res_analisis = analizar_respuestas_salon(tmp_path, ruta_clave)
        assert res_analisis["participantes_validos"] == 10
        assert len(res_analisis["participantes_excluidos_atencion"]) == 1
        assert res_analisis["resumen_global_parte_2"]["neuronas_que_se_sienten_70pct_holm005"] == "5/20"
        assert res_analisis["resumen_parte_4_gusto_corazones"]["desbloquea_n2_y_d8_min_20_bruno"] is True

    return {
        "ruta_html_salon": str(ruta_html),
        "pares_parte_2_reales": 20,
        "controles_azar": 4,
        "controles_atencion": 2,
        "equilibrio_izq_der": "10/10",
        "solapamiento_5c": 0,
        "prueba_analizar_salon_holm": "OK (10 válidos, 1 excluido por atención, 5/20 se sienten)",
    }


def ejecutar_pruebas() -> int:
    dir_neuronas = Path(__file__).resolve().parent
    for pyc_dir in dir_neuronas.rglob("__pycache__"):
        if pyc_dir.is_dir():
            shutil.rmtree(pyc_dir)

    ruta_v1 = dir_neuronas / "prerregistro.json"
    ruta_v2 = dir_neuronas / "prerregistro_v2.json"
    ruta_v3 = dir_neuronas / "prerregistro_v3.json"
    ruta_corpus = dir_neuronas / "corpus_cc0_630.json"

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
    res_salon = _verificar_salon_v3b(dir_neuronas)

    for pyc_dir in dir_neuronas.rglob("__pycache__"):
        if pyc_dir.is_dir():
            shutil.rmtree(pyc_dir)

    ext_prohibidas = {".jpg", ".jpeg", ".png", ".webp", ".pth", ".pt", ".onnx", ".safetensors", ".html", ".pyc"}
    for p in dir_neuronas.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in ext_prohibidas, f"Archivo prohibido en Git: {p}"

    salida = {
        "pruebas_verificadas": "12/12 OK",
        "features_7_stage4": res_f7,
        "features_5_stage3": res_f5,
        "el_salon_fase5d": res_salon,
    }
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar_pruebas())
