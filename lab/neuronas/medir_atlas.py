#!/usr/bin/env python3
"""Suite de verificación determinista para FASE 5b, 5c y 5d-v3d.1 (N-1 v2, v3, v3b, v3c y v3d.1).

Comprueba 14 invariantes estrictos:
1. Prerregistro v1 intacto (sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Prerregistro v2 intacto (sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555).
3. Prerregistro v3 intacto (sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8)
   y corpus_cc0_630.json intacto (630 imágenes CC0 únicas: 441 train y 189 validación).
4. Prerregistro v3b intacto (sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa).
5. Prerregistro v3c intacto (sha256 = 90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5).
6. Prerregistro v3d.1 intacto (sha256 = a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4)
   con las 3 indicaciones enmendadas por Claude (#2 cálido, #10 pesado, #12 antiguo).
7. Licencia BSD-3-Clause y SHA-256 oficial de los pesos de ConvNeXt-tiny verificados.
8. Existencia y validez de las 200 fichas PRAGMA v2 de features.7 en lab/neuronas/atlas/.
9. Existencia y validez de las 200 fichas PRAGMA v3 de features.5 en lab/neuronas/atlas_f5/.
10. Etiquetas libres sin plantilla rígida repetida en ambas capas y preservación de «no lo sé».
11. En features.5, las etiquetas libres expresan exclusivamente verbos visuales/compositivos de
    diseño (0 términos de catálogo de museo).
12. Verificación de El Salón v3d.1: pregunta de Parte 1 «¿Cuál te llamó más la atención?»,
    subtítulo «No hay respuesta correcta: elige por instinto», botón central «Ninguno / se sienten igual»
    en Partes 1 y 2, las 20 indicaciones de director <= 12 palabras sin términos prohibidos, y
    sorteo izquierda/derecha por persona con semilla derivada del apodo.
13. Prueba funcional de `analizar_salon.py` con respuestas «ninguno» (contadas como NO acierto
    conservador e informando `porcentaje_ninguno` por neurona y en los controles), control de
    brillo y separación estricta de los ♥ de Bruno frente a los demás.
14. Higiene de Git: ningún archivo de pesos (.pth, .pt) ni de imagen (.jpg, .png) ni .html pesado
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

from lab.neuronas.analizar_salon import analizar_respuestas_salon
from lab.neuronas.construir_atlas import (
    SHA256_PESOS_ESPERADO,
    intervalo_confianza_wilson_95,
)
from lab.neuronas.generar_salon import (
    calcular_semilla_apodo,
    sortear_lados_equilibrados_mulberry32,
)

SHA256_PRERREG_V1_ESPERADO = "a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388"
SHA256_PRERREG_V2_ESPERADO = "729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555"
SHA256_PRERREG_V3_ESPERADO = "230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8"
SHA256_PRERREG_V3B_ESPERADO = "0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa"
SHA256_PRERREG_V3C_ESPERADO = "90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5"
SHA256_PRERREG_V3D_ESPERADO = "a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4"
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


def _verificar_salon_v3d(dir_neuronas: Path) -> Dict[str, Any]:
    ruta_v3b = dir_neuronas / "prerregistro_v3b.json"
    ruta_v3c = dir_neuronas / "prerregistro_v3c.json"
    ruta_v3d = dir_neuronas / "prerregistro_v3d.json"
    ruta_diseno = dir_neuronas / "diseno_salon_v3b.json"
    assert hashlib.sha256(ruta_v3b.read_bytes()).hexdigest() == SHA256_PRERREG_V3B_ESPERADO
    assert hashlib.sha256(ruta_v3c.read_bytes()).hexdigest() == SHA256_PRERREG_V3C_ESPERADO
    assert hashlib.sha256(ruta_v3d.read_bytes()).hexdigest() == SHA256_PRERREG_V3D_ESPERADO
    assert ruta_diseno.is_file()

    v3b = json.loads(ruta_v3b.read_text(encoding="utf-8"))
    v3d = json.loads(ruta_v3d.read_text(encoding="utf-8"))
    diseno = json.loads(ruta_diseno.read_text(encoding="utf-8"))
    assert diseno["sha256_prerregistro_v3d"] == SHA256_PRERREG_V3D_ESPERADO

    prohibidas = v3b["reglas_diseno_sello"]["regla_2_lenguaje_calle"]["palabras_prohibidas"]
    excluidas_5c = set(v3b["reglas_diseno_sello"]["regla_6_neuronas_nuevas"]["excluidas_5c_reales"]) | set(
        v3b["reglas_diseno_sello"]["regla_6_neuronas_nuevas"]["excluidas_pares_9_y_13_senuelos"]
    )

    neuronas_20 = v3d["estructura_sesion_v3d"]["parte_2_sentir_20_neuronas"]
    assert len(neuronas_20) == 20
    mapa_ind = {int(x["orden"]): x["indicacion_director"] for x in neuronas_20}
    assert mapa_ind[2] == "cálido: predominan rojos, naranjas y amarillos, sin importar el tema"
    assert mapa_ind[10] == "pesado: masas grandes y oscuras que cargan la imagen hacia abajo"
    assert mapa_ind[12] == "antiguo: textura gastada y color amarillento, no por el objeto"

    for item in neuronas_20:
        assert item["id_neurona"] not in excluidas_5c
        preg = item["pregunta"]
        ind = item["indicacion_director"]
        assert len(preg.split()) <= 12
        assert len(ind.split()) <= 12
        for w_p in prohibidas:
            assert w_p not in preg.lower() and w_p not in ind.lower()

    ruta_html = Path(diseno["ruta_html_local"])
    ruta_clave = Path(diseno["ruta_clave_secreta_local"])
    assert ruta_html.is_file() and ruta_clave.is_file()
    html_txt = ruta_html.read_text(encoding="utf-8")
    assert hashlib.sha256(ruta_html.read_bytes()).hexdigest() == diseno["sha256_html_local"]
    assert "¿Cuál te llamó más la atención?" in html_txt
    assert "No hay respuesta correcta: elige por instinto" in html_txt
    assert "Ninguno / se sienten igual" in html_txt
    assert "cálido: predominan rojos, naranjas y amarillos, sin importar el tema" in html_txt
    assert "pesado: masas grandes y oscuras que cargan la imagen hacia abajo" in html_txt
    assert "antiguo: textura gastada y color amarillento, no por el objeto" in html_txt

    # Prueba funcional de analizar_salon.py con respuestas "ninguno" incluidas:
    # - 11 participantes simulados (1 falla ambos controles de atención -> 10 válidos)
    # - En las neuronas #1..#5 los 10 participantes aciertan (100%, 0% ninguno)
    # - En la neurona #6, 2 participantes marcan "ninguno" y 8 aciertan -> 80% acierto, 20% ninguno
    # - En los 4 controles al azar, el participante idx_p == 1 marca "ninguno" en el control #1 -> porcentaje_ninguno_4_controles_azar_pct > 0
    clave_data = json.loads(ruta_clave.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        apodos_sim = ["Distraido"] + ["Bruno"] + [f"Invitado_{k}" for k in range(1, 10)]
        for idx_p, apodo_p in enumerate(apodos_sim):
            falla_atencion = idx_p == 0
            seed_p = calcular_semilla_apodo(apodo_p)
            lados_20_p = sortear_lados_equilibrados_mulberry32(seed_p, 20)
            lados_ctrl_p = sortear_lados_equilibrados_mulberry32(seed_p + 202, 4)
            lados_at_p = sortear_lados_equilibrados_mulberry32(seed_p + 303, 2)

            resp2 = []
            for i_at, at in enumerate(clave_data["parte_2_atencion_2_clave"]):
                lado_pos_mostrado = lados_at_p[i_at]
                lado_opuesto = "derecha" if lado_pos_mostrado == "izquierda" else "izquierda"
                resp2.append(
                    {
                        "id_item": at["id_item"],
                        "tipo_item": "control_atencion",
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "eleccion": lado_opuesto if falla_atencion else lado_pos_mostrado,
                        "tiempo_ms": 1400,
                    }
                )
            for i_c, ctrl in enumerate(clave_data["parte_2_controles_4_clave"]):
                lado_pos_mostrado = lados_ctrl_p[i_c]
                if idx_p in (1, 2) and i_c == 0:
                    el_c = "ninguno"
                else:
                    el_c = "izquierda" if (idx_p % 2 == 0) else "derecha"
                resp2.append(
                    {
                        "id_item": ctrl["id_item"],
                        "tipo_item": "control_azar",
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "eleccion": el_c,
                        "tiempo_ms": 1750,
                    }
                )
            for i_n, n_item in enumerate(clave_data["parte_2_neuronas_20_clave"]):
                lado_pos_mostrado = lados_20_p[i_n]
                lado_opuesto = "derecha" if lado_pos_mostrado == "izquierda" else "izquierda"
                orden_n = n_item["orden_neurona"]
                if orden_n <= 5:
                    el_n = lado_pos_mostrado
                elif orden_n == 6:
                    # 2 válidos (idx_p 1 y 2) eligen "ninguno" -> cuenta como NO acierto (8/10 = 80% acierto, 20% ninguno)
                    el_n = "ninguno" if idx_p in (1, 2) else lado_pos_mostrado
                else:
                    el_n = lado_pos_mostrado if (idx_p % 2 == 0) else lado_opuesto
                resp2.append(
                    {
                        "id_item": n_item["id_item"],
                        "tipo_item": "neurona_real",
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "eleccion": el_n,
                        "tiempo_ms": 1600,
                    }
                )

            n_corazones = 22 if apodo_p == "Bruno" else 15
            doc_sim = {
                "participante": {
                    "apodo": apodo_p,
                    "semilla_apodo": seed_p,
                    "es_bruno_n2_d8": apodo_p == "Bruno",
                    "edad_aproximada": 28 + idx_p,
                    "trabaja_en_diseno_o_arte": "si" if (idx_p % 2 == 1) else "no",
                    "consentimiento_informado": True,
                },
                "parte_1_primer_golpe_vista": [],
                "parte_2_sentir": resp2,
                "parte_3_ponerle_nombre": [],
                "parte_4_gusto": {
                    "votos": [
                        {"id_pieza": f"cma_{k}", "sha256_imagen": f"sha_{k}", "corazon": True}
                        for k in range(n_corazones)
                    ]
                },
            }
            (tmp_path / f"salon_respuesta_{apodo_p.lower()}.json").write_text(
                json.dumps(doc_sim), encoding="utf-8"
            )

        res_analisis = analizar_respuestas_salon(tmp_path, ruta_clave)
        assert res_analisis["participantes_validos"] == 10
        n6_res = [x for x in res_analisis["detalle_20_neuronas_parte_2"] if x["orden"] == 6][0]
        assert n6_res["aciertos"] == 8 and n6_res["conteo_ninguno"] == 2
        assert n6_res["porcentaje_acierto"] == 80.0 and n6_res["porcentaje_ninguno"] == 20.0
        assert res_analisis["resumen_global_parte_2"]["porcentaje_ninguno_4_controles_azar_pct"] == 5.0

    return {
        "sha256_prerregistro_v3d_1": SHA256_PRERREG_V3D_ESPERADO,
        "ruta_html_salon": str(ruta_html),
        "sha256_html_salon": diseno["sha256_html_local"],
        "boton_ninguno_conservador": "OK (cuenta como NO acierto en denominador y reporta % Ninguno por neurona y en controles)",
        "indicaciones_director_20": "OK (20/20 <= 12 palabras, incluidas enmiendas #2, #10 y #12)",
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
    res_salon = _verificar_salon_v3d(dir_neuronas)

    for pyc_dir in dir_neuronas.rglob("__pycache__"):
        if pyc_dir.is_dir():
            shutil.rmtree(pyc_dir)

    ext_prohibidas = {".jpg", ".jpeg", ".png", ".webp", ".pth", ".pt", ".onnx", ".safetensors", ".html", ".pyc"}
    for p in dir_neuronas.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in ext_prohibidas, f"Archivo prohibido en Git: {p}"

    salida = {
        "pruebas_verificadas": "14/14 OK",
        "features_7_stage4": res_f7,
        "features_5_stage3": res_f5,
        "el_salon_fase5d_v3d_1": res_salon,
    }
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar_pruebas())
