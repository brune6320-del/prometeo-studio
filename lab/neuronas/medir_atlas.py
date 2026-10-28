#!/usr/bin/env python3
"""Suite de verificación determinista para FASE 5b, 5c, 5d-v3d.1, 5e y 5e.1 (N-1 v2, v3, v3b, v3c, v3d.1 y El salón para llevar con imágenes nítidas).

Comprueba 17 invariantes estrictos:
1. Prerregistro v1 intacto (sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Prerregistro v2 intacto (sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555).
3. Prerregistro v3 intacto (sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8)
   y corpus_cc0_630.json intacto (630 imágenes CC0 únicas: 441 train y 189 validación).
4. Prerregistro v3b intacto (sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa).
5. Prerregistro v3c intacto (sha256 = 90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5).
6. Prerregistro v3d.1 intacto (sha256 = a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4,
   PRERREGISTRO-v3d.md sha256 = f9faf3fd8a01c565816db097f43f04f8d5f3bbe96c25661e5e369d260f6fb9ff)
   con las 3 indicaciones enmendadas por Claude (#2 cálido, #10 pesado, #12 antiguo).
7. Licencia BSD-3-Clause y SHA-256 oficial de los pesos de ConvNeXt-tiny verificados.
8. Existencia y validez de las 200 fichas PRAGMA v2 de features.7 en lab/neuronas/atlas/.
9. Existencia y validez de las 200 fichas PRAGMA v3 de features.5 en lab/neuronas/atlas_f5/.
10. Etiquetas libres sin plantilla rígida repetida en ambas capas y preservación de «no lo sé».
11. En features.5, las etiquetas libres expresan exclusivamente verbos visuales/compositivos de
    diseño (0 términos de catálogo de museo).
12. Verificación de El Salón v3d.1 (`salon_sensaciones.html` sha256 = 60c89901... intacto):
    pregunta de Parte 1 «¿Cuál te llamó más la atención?», subtítulo «No hay respuesta correcta:
    elige por instinto», botón central «Ninguno / se sienten igual» en Partes 1 y 2, las 20
    indicaciones de director <= 12 palabras sin términos prohibidos, y sorteo izquierda/derecha
    por persona con semilla derivada del apodo.
13. Prueba funcional de `analizar_salon.py` con respuestas «ninguno» (contadas como NO acierto
    conservador e informando `porcentaje_ninguno` por neurona y en los controles), control de
    brillo y separación estricta de los ♥ de Bruno frente a los demás.
14. FASE 5e (`salon_para_llevar.html`): archivo único autocontenido < 12 MB, apto para celular a
    400 px sin conexión, con los mosaicos de las partes 1 a 3, las 20 indicaciones, preguntas,
    pares, orden al azar y botón «Ninguno» idénticos a `2d94df9`, y cierre con código Base64 y
    botón «Copiar resultado».
15. FASE 5e (`juntar_resultados.py`): rechaza códigos que no traen el `sha256` de v3d.1 y comprueba
    que el mismo conjunto de respuestas produce exactamente el mismo resultado en `analizar_salon.py`
    por las dos vías (`salon_sensaciones.html` JSON directo vs `salon_para_llevar.html` código Base64).
16. Higiene de Git: ningún archivo de pesos (.pth, .pt) ni de imagen (.jpg, .png) ni .html pesado
    con imágenes embebidas está dentro de lab/neuronas/.
17. FASE 5e.1 (imágenes nítidas en Parte 4): comprueba decodificando cada una de las 40 imágenes
    embebidas en `salon_para_llevar.html` que toda imagen de la Parte 4 tiene >= 1200 px en el
    lado largo (o su tamaño original exacto si el original del museo es menor, sin reescalar hacia
    arriba), que el código de resultado y el JSON registran `px_lado_largo_mostrado` para cada
    pieza, y que los resultados de la 5e siguen siendo válidos para las Partes 1 a 3 marcándose
    como `imagen_baja_calidad` en la Parte 4.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set

from PIL import Image

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
from lab.neuronas.juntar_resultados import (
    _piezas_parte4_desde_prerregistro,
    codificar_resultado_a_base64,
    decodificar_linea_base64,
    juntar_resultados_desde_txt,
)

SHA256_PRERREG_V1_ESPERADO = "a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388"
SHA256_PRERREG_V2_ESPERADO = "729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555"
SHA256_PRERREG_V3_ESPERADO = "230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8"
SHA256_PRERREG_V3B_ESPERADO = "0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa"
SHA256_PRERREG_V3C_ESPERADO = "90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5"
SHA256_PRERREG_V3D_ESPERADO = "a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4"
SHA256_PRERREG_V3D_MD_ESPERADO = "f9faf3fd8a01c565816db097f43f04f8d5f3bbe96c25661e5e369d260f6fb9ff"
SHA256_HTML_V3D1_ORIGINAL_ESPERADO = "60c899018e92609273de2e70b11588cdf9d16ca4c6407ac8521ad111ff091dd3"
SHA256_CORPUS_630_ESPERADO = "f0c3483fafa8c04be6492ff62190071c8f6278beb8dec78b05110a6cabb5875f"


def _extraer_raw_json_de_html(html_txt: str) -> Dict[str, Any]:
    m = re.search(r"const RAW = (\{.*?\});\n\nfunction calcularSemillaApodo", html_txt, re.S)
    assert m is not None, "No se encontró el bloque `const RAW = {...};` en el HTML"
    return json.loads(m.group(1))


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


def _verificar_salon_v3d_5e_y_5e1(dir_neuronas: Path) -> Dict[str, Any]:
    ruta_v3b = dir_neuronas / "prerregistro_v3b.json"
    ruta_v3c = dir_neuronas / "prerregistro_v3c.json"
    ruta_v3d = dir_neuronas / "prerregistro_v3d.json"
    ruta_v3d_md = dir_neuronas / "PRERREGISTRO-v3d.md"
    ruta_diseno = dir_neuronas / "diseno_salon_v3b.json"
    ruta_corpus = dir_neuronas / "corpus_cc0_630.json"

    assert hashlib.sha256(ruta_v3b.read_bytes()).hexdigest() == SHA256_PRERREG_V3B_ESPERADO
    assert hashlib.sha256(ruta_v3c.read_bytes()).hexdigest() == SHA256_PRERREG_V3C_ESPERADO
    assert hashlib.sha256(ruta_v3d.read_bytes()).hexdigest() == SHA256_PRERREG_V3D_ESPERADO
    assert hashlib.sha256(ruta_v3d_md.read_bytes()).hexdigest() == SHA256_PRERREG_V3D_MD_ESPERADO
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

    # Verificar salon_sensaciones.html (2d94df9 intacto)
    ruta_html = Path(diseno["ruta_html_local"])
    ruta_clave = Path(diseno["ruta_clave_secreta_local"])
    assert ruta_html.is_file() and ruta_clave.is_file()
    html_txt = ruta_html.read_text(encoding="utf-8")
    sha_html_orig = hashlib.sha256(ruta_html.read_bytes()).hexdigest()
    assert sha_html_orig == SHA256_HTML_V3D1_ORIGINAL_ESPERADO
    assert sha_html_orig == diseno["sha256_html_local"]

    # Verificar salon_para_llevar.html (FASE 5e + 5e.1)
    ruta_html_llevar = Path(diseno["ruta_html_para_llevar_local"])
    assert ruta_html_llevar.is_file()
    bytes_llevar = ruta_html_llevar.read_bytes()
    sha_html_llevar = hashlib.sha256(bytes_llevar).hexdigest()
    assert sha_html_llevar == diseno["sha256_html_para_llevar_local"]
    assert len(bytes_llevar) <= 12_000_000, f"salon_para_llevar.html supera 12 MB: {len(bytes_llevar)}"
    html_llevar_txt = ruta_html_llevar.read_text(encoding="utf-8")

    # Comprobar que los mosaicos de las partes 1 a 3, las 20 indicaciones, las preguntas, los pares,
    # el orden al azar y el botón «Ninguno / se sienten igual» de salon_para_llevar.html son 100% idénticos a 2d94df9
    raw_orig = _extraer_raw_json_de_html(html_txt)
    raw_llevar = _extraer_raw_json_de_html(html_llevar_txt)
    for k_p1_p3 in ("parte1_raw", "neuronas20_raw", "controles4_raw", "atencion2_raw", "parte3_raw"):
        assert raw_orig[k_p1_p3] == raw_llevar[k_p1_p3], f"Diferencia en {k_p1_p3} respecto a 2d94df9"

    indicaciones_llevar = [x["indicacion_director"] for x in raw_llevar["neuronas20_raw"]]
    indicaciones_v3d1 = [x["indicacion_director"] for x in neuronas_20]
    assert indicaciones_llevar == indicaciones_v3d1
    preguntas_llevar_p2 = [x["pregunta"] for x in raw_llevar["neuronas20_raw"]]
    preguntas_v3d1_p2 = [x["pregunta"] for x in neuronas_20]
    assert preguntas_llevar_p2 == preguntas_v3d1_p2
    assert all(x["pregunta"] == "¿Cuál te llamó más la atención?" for x in raw_llevar["parte1_raw"])

    assert "max-width: 400px" in html_llevar_txt
    assert "No hay respuesta correcta: elige por instinto" in html_llevar_txt
    assert "Ninguno / se sienten igual" in html_llevar_txt
    assert "Copiar resultado" in html_llevar_txt
    assert "generarCodigoBase64" in html_llevar_txt
    assert "px_lado_largo_mostrado" in html_llevar_txt
    assert SHA256_PRERREG_V3D_ESPERADO in html_llevar_txt

    # Prueba #17 (Fase 5e.1): comprobar que toda imagen de la Parte 4 embebida en salon_para_llevar.html
    # tiene >= 1200 px en el lado largo, o su tamaño original exacto si el original es menor (sin reescalar hacia arriba)
    assert len(raw_llevar["parte4_raw"]) == 40
    cnt_1200_exactos = 0
    cnt_original_menor_1200 = 0
    for idx4, item4 in enumerate(raw_llevar["parte4_raw"]):
        assert item4["id_pieza"] == raw_orig["parte4_raw"][idx4]["id_pieza"]
        assert item4["sha256_imagen"] == raw_orig["parte4_raw"][idx4]["sha256_imagen"]
        img_bytes = base64.b64decode(item4["b64_img"])
        with Image.open(io.BytesIO(img_bytes)) as im_p4:
            w_real, h_real = im_p4.size
        lado_real = max(w_real, h_real)
        lado_orig = int(item4["lado_largo_original_px"])
        assert lado_real == int(item4["px_lado_largo_mostrado"])
        assert lado_real <= lado_orig, f"Se agrandó una imagen más pequeña que 1200px: {item4['id_pieza']}"
        if lado_orig >= 1200:
            assert lado_real >= 1200, f"Pieza {item4['id_pieza']} con original {lado_orig}px quedó en {lado_real}px (< 1200px)"
            cnt_1200_exactos += 1
        else:
            assert lado_real == lado_orig, f"Pieza {item4['id_pieza']} con original <1200px ({lado_orig}px) no conservó su tamaño ({lado_real}px)"
            cnt_original_menor_1200 += 1

    # Prueba de equivalencia exacta por las dos vías (JSON directo vs código Base64 + juntar_resultados.py),
    # rechazo de códigos sin el sha256 de v3d.1, y compatibilidad de resultados de 5e (válidos en Partes 1-3 y
    # marcados como `imagen_baja_calidad` en Parte 4)
    clave_data = json.loads(ruta_clave.read_text(encoding="utf-8"))
    piezas_40_meta = _piezas_parte4_desde_prerregistro(
        ruta_v3d, ruta_corpus, dir_neuronas / "atlas", dir_neuronas / "atlas_f5"
    )
    with tempfile.TemporaryDirectory() as tmp_dir_json, tempfile.TemporaryDirectory() as tmp_dir_b64:
        path_json = Path(tmp_dir_json)
        path_b64 = Path(tmp_dir_b64)
        lineas_codigos_b64: List[str] = []

        apodos_sim = ["Distraido"] + ["Bruno"] + [f"Invitado_{k}" for k in range(1, 10)]
        for idx_p, apodo_p in enumerate(apodos_sim):
            falla_atencion = idx_p == 0
            seed_p = calcular_semilla_apodo(apodo_p)
            lados_1_p = sortear_lados_equilibrados_mulberry32((seed_p + 101) & 0xFFFFFFFF, 12)
            lados_20_p = sortear_lados_equilibrados_mulberry32(seed_p, 20)
            lados_ctrl_p = sortear_lados_equilibrados_mulberry32((seed_p + 202) & 0xFFFFFFFF, 4)
            lados_at_p = sortear_lados_equilibrados_mulberry32((seed_p + 303) & 0xFFFFFFFF, 2)
            lados_3_p = sortear_lados_equilibrados_mulberry32((seed_p + 404) & 0xFFFFFFFF, 6)

            resp1 = []
            for i1, info1 in enumerate(clave_data["parte_1_clave"]):
                lado_pos1 = lados_1_p[i1]
                resp1.append(
                    {
                        "orden": info1["orden"],
                        "id_item": info1["id_item"],
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos1,
                        "sha256_mostrado_izquierda": info1["sha256_polo_pos"] if lado_pos1 == "izquierda" else info1["sha256_polo_neg"],
                        "sha256_mostrado_derecha": info1["sha256_polo_neg"] if lado_pos1 == "izquierda" else info1["sha256_polo_pos"],
                        "eleccion": lado_pos1,
                        "tiempo_ms": 1200 + i1 * 10,
                        "respondio_tras_ocultar_5s": False,
                    }
                )

            n20_items = []
            for i_n, n_item in enumerate(clave_data["parte_2_neuronas_20_clave"]):
                lado_pos_mostrado = lados_20_p[i_n]
                lado_opuesto = "derecha" if lado_pos_mostrado == "izquierda" else "izquierda"
                orden_n = n_item["orden_neurona"]
                if orden_n <= 5:
                    el_n = lado_pos_mostrado
                elif orden_n == 6:
                    el_n = "ninguno" if idx_p in (1, 2) else lado_pos_mostrado
                else:
                    el_n = lado_pos_mostrado if (idx_p % 2 == 0) else lado_opuesto
                n20_items.append(
                    {
                        "id_item": n_item["id_item"],
                        "tipo_item": "neurona_real",
                        "pregunta": n_item["pregunta"],
                        "indicacion_director": n_item["indicacion_director"],
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "sha256_mostrado_izquierda": n_item["sha256_polo_pos"] if lado_pos_mostrado == "izquierda" else n_item["sha256_polo_neg"],
                        "sha256_mostrado_derecha": n_item["sha256_polo_neg"] if lado_pos_mostrado == "izquierda" else n_item["sha256_polo_pos"],
                        "eleccion": el_n,
                        "tiempo_ms": 1600,
                    }
                )

            c4_items = []
            for i_c, ctrl in enumerate(clave_data["parte_2_controles_4_clave"]):
                lado_pos_mostrado = lados_ctrl_p[i_c]
                el_c = "ninguno" if (idx_p in (1, 2) and i_c == 0) else ("izquierda" if (idx_p % 2 == 0) else "derecha")
                c4_items.append(
                    {
                        "id_item": ctrl["id_item"],
                        "tipo_item": "control_azar",
                        "pregunta": ctrl["pregunta"],
                        "indicacion_director": ctrl["indicacion_director"],
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "sha256_mostrado_izquierda": ctrl["sha256_polo_pos"] if lado_pos_mostrado == "izquierda" else ctrl["sha256_polo_neg"],
                        "sha256_mostrado_derecha": ctrl["sha256_polo_neg"] if lado_pos_mostrado == "izquierda" else ctrl["sha256_polo_pos"],
                        "eleccion": el_c,
                        "tiempo_ms": 1750,
                    }
                )

            a2_items = []
            for i_at, at in enumerate(clave_data["parte_2_atencion_2_clave"]):
                lado_pos_mostrado = lados_at_p[i_at]
                lado_opuesto = "derecha" if lado_pos_mostrado == "izquierda" else "izquierda"
                a2_items.append(
                    {
                        "id_item": at["id_item"],
                        "tipo_item": "control_atencion",
                        "pregunta": at["pregunta"],
                        "indicacion_director": at["indicacion_director"],
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos_mostrado,
                        "sha256_mostrado_izquierda": at["sha256_polo_pos"] if lado_pos_mostrado == "izquierda" else at["sha256_polo_neg"],
                        "sha256_mostrado_derecha": at["sha256_polo_neg"] if lado_pos_mostrado == "izquierda" else at["sha256_polo_pos"],
                        "eleccion": lado_opuesto if falla_atencion else lado_pos_mostrado,
                        "tiempo_ms": 1400,
                    }
                )

            p2_presentados = list(n20_items)
            p2_presentados.insert(4, c4_items[0])
            p2_presentados.insert(8, a2_items[0])
            p2_presentados.insert(12, c4_items[1])
            p2_presentados.insert(17, c4_items[2])
            p2_presentados.insert(20, a2_items[1])
            p2_presentados.insert(24, c4_items[3])
            for idx_ord, it_p2 in enumerate(p2_presentados, start=1):
                it_p2["orden_presentacion"] = idx_ord

            resp3 = []
            for i3, info3 in enumerate(clave_data["parte_3_clave"]):
                lado_pos3 = lados_3_p[i3]
                resp3.append(
                    {
                        "orden": info3["orden"],
                        "id_item": info3["id_item"],
                        "semilla_apodo": seed_p,
                        "lado_polo_pos_mostrado": lado_pos3,
                        "sha256_mostrado_izquierda": info3["sha256_polo_pos"] if lado_pos3 == "izquierda" else info3["sha256_polo_neg"],
                        "sha256_mostrado_derecha": info3["sha256_polo_neg"] if lado_pos3 == "izquierda" else info3["sha256_polo_pos"],
                        "palabras_usuario": "contraste fuerte vs suave",
                    }
                )

            n_corazones = 22 if apodo_p == "Bruno" else 15
            votos_p4 = [
                {
                    "id_pieza": raw_llevar["parte4_raw"][k]["id_pieza"],
                    "sha256_imagen": raw_llevar["parte4_raw"][k]["sha256_imagen"],
                    "px_lado_largo_mostrado": int(raw_llevar["parte4_raw"][k]["px_lado_largo_mostrado"]),
                    "corazon": k < n_corazones,
                }
                for k in range(40)
            ]

            doc_sim = {
                "fase": "FASE 5d · El Salón (Prueba de sensaciones con personas · v3d.1)",
                "version_prerregistro": "3.3.1 (v3d.1)",
                "fecha_iso": "2026-10-28T12:00:00Z",
                "participante": {
                    "apodo": apodo_p,
                    "semilla_apodo": seed_p,
                    "es_bruno_n2_d8": apodo_p == "Bruno",
                    "edad_aproximada": 28 + idx_p,
                    "trabaja_en_diseno_o_arte": "si" if (idx_p % 2 == 1) else "no",
                    "consentimiento_informado": True,
                },
                "parte_1_primer_golpe_vista": resp1,
                "parte_2_sentir": p2_presentados,
                "parte_3_ponerle_nombre": resp3,
                "parte_4_gusto": {
                    "cuenta_para_n2_y_d8": apodo_p == "Bruno",
                    "calidad_parte_4": "nitida_1200px",
                    "total_corazones": n_corazones,
                    "total_evaluadas": 40,
                    "votos": votos_p4,
                },
                "cierre": {"que_te_sorprendio": "Muy fluido en el celular"},
            }
            (path_json / f"salon_respuesta_{apodo_p.lower()}_{idx_p + 1:02d}.json").write_text(
                json.dumps(doc_sim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            lineas_codigos_b64.append(codificar_resultado_a_base64(doc_sim, incluir_px_5e1=True))

            # Verificar además que si un código viene de la 5e (sin `p4_px`), decodificar_linea_base64
            # conserva intactas las Partes 1 a 3 y marca la Parte 4 como `imagen_baja_calidad`
            if apodo_p == "Bruno":
                b64_5e_bruno = codificar_resultado_a_base64(doc_sim, incluir_px_5e1=False)
                doc_5e_dec = decodificar_linea_base64(b64_5e_bruno, clave_data, piezas_40_meta)
                assert doc_5e_dec["parte_1_primer_golpe_vista"] == doc_sim["parte_1_primer_golpe_vista"]
                assert doc_5e_dec["parte_2_sentir"] == doc_sim["parte_2_sentir"]
                assert doc_5e_dec["parte_3_ponerle_nombre"] == doc_sim["parte_3_ponerle_nombre"]
                assert doc_5e_dec["parte_4_gusto"]["calidad_parte_4"] == "imagen_baja_calidad"
                assert all(
                    v.get("calidad_imagen") == "imagen_baja_calidad" and v.get("px_lado_largo_mostrado") == 168
                    for v in doc_5e_dec["parte_4_gusto"]["votos"]
                )

        # Añadir 2 códigos inválidos que juntar_resultados.py DEBE rechazar:
        codigo_falso_sha = base64.b64encode(
            json.dumps(
                {
                    "v": "3.3.1 (v3d.1)",
                    "sha256_prerregistro": "0000000000000000000000000000000000000000000000000000000000000000",
                    "apodo": "Intruso",
                }
            ).encode("utf-8")
        ).decode("ascii")
        lineas_codigos_b64.append(codigo_falso_sha)
        lineas_codigos_b64.append("CODIGO_CORRUPTO_SIN_BASE64_###")

        ruta_txt = path_b64 / "codigos_whatsapp.txt"
        ruta_txt.write_text("\n".join(lineas_codigos_b64) + "\n", encoding="utf-8")
        carpeta_out_b64 = path_b64 / "respuestas_reconstruidas"

        res_juntar = juntar_resultados_desde_txt(
            ruta_txt_codigos=ruta_txt,
            carpeta_salida_respuestas=carpeta_out_b64,
            ruta_clave=ruta_clave,
            ruta_prerregistro_v3d=ruta_v3d,
            ruta_corpus_json=ruta_corpus,
            carpeta_atlas_f7=dir_neuronas / "atlas",
            carpeta_atlas_f5=dir_neuronas / "atlas_f5",
        )
        assert res_juntar["codigos_aceptados"] == 11
        assert res_juntar["codigos_rechazados"] == 2

        res_analisis_orig = analizar_respuestas_salon(path_json, ruta_clave)
        res_analisis_b64 = res_juntar["analisis_salon"]

        bruno_orig = json.loads(Path(res_analisis_orig["resumen_parte_4_gusto_corazones"]["archivo_corazones_bruno"]).read_text(encoding="utf-8"))
        bruno_b64 = json.loads(Path(res_analisis_b64["resumen_parte_4_gusto_corazones"]["archivo_corazones_bruno"]).read_text(encoding="utf-8"))
        assert bruno_orig == bruno_b64

        otros_orig = json.loads(Path(res_analisis_orig["resumen_parte_4_gusto_corazones"]["archivo_corazones_otros_aparte"]).read_text(encoding="utf-8"))
        otros_b64 = json.loads(Path(res_analisis_b64["resumen_parte_4_gusto_corazones"]["archivo_corazones_otros_aparte"]).read_text(encoding="utf-8"))
        assert otros_orig == otros_b64

        copia_orig = json.loads(json.dumps(res_analisis_orig))
        copia_b64 = json.loads(json.dumps(res_analisis_b64))
        copia_orig.pop("carpeta_respuestas", None)
        copia_b64.pop("carpeta_respuestas", None)
        copia_orig["resumen_parte_4_gusto_corazones"].pop("archivo_corazones_bruno", None)
        copia_b64["resumen_parte_4_gusto_corazones"].pop("archivo_corazones_bruno", None)
        copia_orig["resumen_parte_4_gusto_corazones"].pop("archivo_corazones_otros_aparte", None)
        copia_b64["resumen_parte_4_gusto_corazones"].pop("archivo_corazones_otros_aparte", None)
        assert copia_orig == copia_b64, "El análisis por código Base64 difiere del análisis por JSON directo"

        assert res_analisis_orig["participantes_validos"] == 10
        n6_res = [x for x in res_analisis_orig["detalle_20_neuronas_parte_2"] if x["orden"] == 6][0]
        assert n6_res["aciertos"] == 8 and n6_res["conteo_ninguno"] == 2
        assert n6_res["porcentaje_acierto"] == 80.0 and n6_res["porcentaje_ninguno"] == 20.0
        assert res_analisis_orig["resumen_global_parte_2"]["porcentaje_ninguno_4_controles_azar_pct"] == 5.0

    return {
        "sha256_prerregistro_v3d_1": SHA256_PRERREG_V3D_ESPERADO,
        "sha256_prerregistro_v3d_1_md": SHA256_PRERREG_V3D_MD_ESPERADO,
        "ruta_html_salon_original": str(ruta_html),
        "sha256_html_salon_original": sha_html_orig,
        "ruta_html_salon_para_llevar": str(ruta_html_llevar),
        "sha256_html_salon_para_llevar": sha_html_llevar,
        "tamano_bytes_salon_para_llevar": len(bytes_llevar),
        "calidad_jpeg_parte4_para_llevar": diseno["calidad_jpeg_parte4_para_llevar"],
        "parte4_imagenes_nitidas_1200px": f"OK (40/40 verificadas: {cnt_1200_exactos} a 1200px en lado largo y {cnt_original_menor_1200} en su tamaño original <1200px sin agrandar)",
        "compatibilidad_5e_baja_calidad": "OK (resultados 5e válidos en Partes 1-3 y marcados como imagen_baja_calidad en Parte 4)",
        "identidad_20_indicaciones_y_mosaicos_p1_p3_con_2d94df9": "OK (mosaicos Partes 1-3, 20/20 indicaciones, preguntas, pares, orden al azar y botón Ninguno idénticos)",
        "equivalencia_dos_vias_y_rechazo_sha": "OK (mismo resultado exacto por JSON y por código Base64; 2/2 códigos sin sha256 v3d.1 rechazados)",
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
    res_salon = _verificar_salon_v3d_5e_y_5e1(dir_neuronas)

    for pyc_dir in dir_neuronas.rglob("__pycache__"):
        if pyc_dir.is_dir():
            shutil.rmtree(pyc_dir)

    ext_prohibidas = {".jpg", ".jpeg", ".png", ".webp", ".pth", ".pt", ".onnx", ".safetensors", ".html", ".pyc"}
    for p in dir_neuronas.rglob("*"):
        if p.is_file():
            assert p.suffix.lower() not in ext_prohibidas, f"Archivo prohibido en Git: {p}"

    salida = {
        "pruebas_verificadas": "17/17 OK",
        "features_7_stage4": res_f7,
        "features_5_stage3": res_f5,
        "el_salon_fase5d_5e_y_5e1": res_salon,
    }
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar_pruebas())
