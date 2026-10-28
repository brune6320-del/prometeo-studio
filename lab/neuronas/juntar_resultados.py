#!/usr/bin/env python3
"""FASE 5e · «El salón para llevar»: decodificador y agregador de códigos Base64 (CPU, 0 Colab).

Lee un archivo de texto con todos los códigos Base64 pegados por Bruno (uno por línea, enviados
por WhatsApp desde `salon_para_llevar.html`):
1. Rechaza cualquier línea/código que no sea Base64 válido o que no traiga el `sha256` oficial
   del prerregistro v3d.1 (`a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4` o
   el de `PRERREGISTRO-v3d.md` `f9faf3fd8a01c565816db097f43f04f8d5f3bbe96c25661e5e369d260f6fb9ff`).
2. Reconstruye de forma determinista el archivo `salon_respuesta_<apodo>.json` de cada
   participante válido con la misma estructura exacta que produce `salon_sensaciones.html`.
3. Invoca `analizar_respuestas_salon` (de `lab/neuronas/analizar_salon.py`) y escribe la tabla
   completa de resultados (`tabla_resultados_salon.json` y `TABLA-RESULTADOS-SALON.md`).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.neuronas.analizar_salon import analizar_respuestas_salon
from lab.neuronas.generar_salon import (
    SHA256_PRERREG_V3D_ESPERADO,
    calcular_semilla_apodo,
    sortear_lados_equilibrados_mulberry32,
)

SHA256_PRERREG_V3D_MD_ESPERADO = (
    "f9faf3fd8a01c565816db097f43f04f8d5f3bbe96c25661e5e369d260f6fb9ff"
)
SHAS_V3D1_VALIDOS = {SHA256_PRERREG_V3D_ESPERADO, SHA256_PRERREG_V3D_MD_ESPERADO}

MAPA_CODIGO_ELECCION = {
    "i": "izquierda",
    "d": "derecha",
    "n": "ninguno",
    "izquierda": "izquierda",
    "derecha": "derecha",
    "ninguno": "ninguno",
}


def codificar_resultado_a_base64(doc_participante: Dict[str, Any]) -> str:
    """Convierte un documento completo `salon_respuesta_<apodo>.json` en el código corto Base64
    idéntico al que genera `salon_para_llevar.html` al terminar la sesión."""
    part = doc_participante.get("participante", {})
    p1 = [
        [
            "i"
            if x.get("eleccion") == "izquierda"
            else ("d" if x.get("eleccion") == "derecha" else "n"),
            int(x.get("tiempo_ms", 0)),
            1 if x.get("respondio_tras_ocultar_5s", False) else 0,
        ]
        for x in doc_participante.get("parte_1_primer_golpe_vista", [])
    ]
    p2 = [
        [
            "i"
            if x.get("eleccion") == "izquierda"
            else ("d" if x.get("eleccion") == "derecha" else "n"),
            int(x.get("tiempo_ms", 0)),
        ]
        for x in doc_participante.get("parte_2_sentir", [])
    ]
    p3 = [
        str(x.get("palabras_usuario", ""))
        for x in doc_participante.get("parte_3_ponerle_nombre", [])
    ]
    votos4 = doc_participante.get("parte_4_gusto", {}).get("votos", [])
    p4_bits = "".join("1" if v.get("corazon") else "0" for v in votos4)

    compacto = {
        "v": "3.3.1 (v3d.1)",
        "sha256_prerregistro": SHA256_PRERREG_V3D_ESPERADO,
        "sha256_prerregistro_md": SHA256_PRERREG_V3D_MD_ESPERADO,
        "apodo": part.get("apodo", ""),
        "edad": part.get("edad_aproximada", ""),
        "diseno": part.get("trabaja_en_diseno_o_arte", ""),
        "consent": bool(part.get("consentimiento_informado", False)),
        "seed": int(
            part.get(
                "semilla_apodo", calcular_semilla_apodo(str(part.get("apodo", "")))
            )
        ),
        "fecha": doc_participante.get("fecha_iso", "2026-10-28T00:00:00Z"),
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "p4": p4_bits,
        "cierre": doc_participante.get("cierre", {}).get("que_te_sorprendio", ""),
    }
    raw_bytes = json.dumps(compacto, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return base64.b64encode(raw_bytes).decode("ascii")


def _orden_items_parte2_para_semilla(
    semilla_apodo: int, clave_data: Dict[str, Any]
) -> List[Tuple[Dict[str, Any], str]]:
    """Reconstruye los 26 ítems de la Parte 2 en el orden exacto presentado al participante
    y devuelve pares (info_clave, lado_polo_pos_mostrado)."""
    n20_clave = clave_data["parte_2_neuronas_20_clave"]
    c4_clave = clave_data["parte_2_controles_4_clave"]
    a2_clave = clave_data["parte_2_atencion_2_clave"]

    lados20 = sortear_lados_equilibrados_mulberry32(semilla_apodo, len(n20_clave))
    lados_ctrl = sortear_lados_equilibrados_mulberry32(
        (semilla_apodo + 202) & 0xFFFFFFFF, len(c4_clave)
    )
    lados_at = sortear_lados_equilibrados_mulberry32(
        (semilla_apodo + 303) & 0xFFFFFFFF, len(a2_clave)
    )

    p2 = [(n20_clave[i], lados20[i]) for i in range(len(n20_clave))]
    p2.insert(4, (c4_clave[0], lados_ctrl[0]))
    p2.insert(8, (a2_clave[0], lados_at[0]))
    p2.insert(12, (c4_clave[1], lados_ctrl[1]))
    p2.insert(17, (c4_clave[2], lados_ctrl[2]))
    p2.insert(20, (a2_clave[1], lados_at[1]))
    p2.insert(24, (c4_clave[3], lados_ctrl[3]))
    return p2


def _piezas_parte4_desde_prerregistro(
    ruta_prerregistro_v3d: Path,
    ruta_corpus_json: Path,
    carpeta_atlas_f7: Path,
    carpeta_atlas_f5: Path,
) -> List[Dict[str, str]]:
    """Obtiene la lista determinista de 40 piezas únicas mostradas en la Parte 4."""
    prerreg = json.loads(ruta_prerregistro_v3d.read_text(encoding="utf-8"))
    corpus_items = json.loads(ruta_corpus_json.read_text(encoding="utf-8"))["imagenes"]
    sha_por_id = {it["id_origen"]: it["sha256"] for it in corpus_items}

    fichas_por_id: Dict[str, Dict[str, Any]] = {}
    for p in sorted(carpeta_atlas_f7.glob("neurona_*.json")) + sorted(
        carpeta_atlas_f5.glob("neurona_f5_*.json")
    ):
        d = json.loads(p.read_text(encoding="utf-8"))
        fichas_por_id[d["id_neurona"]] = d

    vistas: List[str] = []

    def reg(id_neurona: str) -> None:
        f = fichas_por_id[id_neurona]
        ids_5 = [x["id_pieza"] for x in f["polo_pos"][:3]] + [
            x["id_pieza"] for x in f["polo_neg"][:2]
        ]
        for pid in ids_5:
            if pid not in vistas:
                vistas.append(pid)

    for it1 in prerreg["estructura_sesion_v3d"][
        "parte_1_primer_golpe_vista_12_pares"
    ]:
        reg(it1["id_neurona"])
    for it2 in prerreg["estructura_sesion_v3d"]["parte_2_sentir_20_neuronas"]:
        reg(it2["id_neurona"])
    for it3 in prerreg["estructura_sesion_v3d"]["parte_3_ponerle_nombre_6_pares"]:
        reg(it3["id_neurona"])

    return [
        {"id_pieza": pid, "sha256_imagen": sha_por_id[pid]} for pid in vistas[:40]
    ]


def decodificar_linea_base64(
    linea: str,
    clave_data: Dict[str, Any],
    piezas_40: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Decodifica un código Base64 individual, valida el sha256 de v3d.1 y reconstruye el JSON."""
    limpia = linea.strip()
    if limpia.startswith("SALON_V3D1:"):
        limpia = limpia.split("SALON_V3D1:", 1)[1].strip()
    # Permitir que la línea venga pegada con espacios accidentales alrededor
    limpia = re.sub(r"\s+", "", limpia)
    if not limpia:
        raise ValueError("Línea vacía")

    try:
        raw_bytes = base64.b64decode(limpia, validate=True)
        obj = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Base64 o JSON inválido: {exc}") from exc

    sha_recibido = str(obj.get("sha256_prerregistro", ""))
    sha_md_recibido = str(obj.get("sha256_prerregistro_md", ""))
    if (
        sha_recibido not in SHAS_V3D1_VALIDOS
        and sha_md_recibido not in SHAS_V3D1_VALIDOS
    ):
        raise ValueError(
            f"Código rechazado: sha256_prerregistro '{sha_recibido}' no coincide con v3d.1 ({SHA256_PRERREG_V3D_ESPERADO[:12]}...)"
        )

    apodo = str(obj.get("apodo", "")).strip()
    if not apodo:
        raise ValueError("Código sin apodo")

    semilla_apodo = int(obj.get("seed", calcular_semilla_apodo(apodo)))
    es_bruno = apodo.lower() == "bruno"

    # Reconstruir Parte 1 (12 pares)
    p1_clave = clave_data["parte_1_clave"]
    lados1 = sortear_lados_equilibrados_mulberry32(
        (semilla_apodo + 101) & 0xFFFFFFFF, len(p1_clave)
    )
    resp1_raw = obj.get("p1", [])
    resp1_full = []
    for i, info1 in enumerate(p1_clave):
        lado_pos = lados1[i]
        sha_izq = (
            info1["sha256_polo_pos"]
            if lado_pos == "izquierda"
            else info1["sha256_polo_neg"]
        )
        sha_der = (
            info1["sha256_polo_neg"]
            if lado_pos == "izquierda"
            else info1["sha256_polo_pos"]
        )
        r_item = resp1_raw[i] if i < len(resp1_raw) else ["n", 0, 0]
        el_str = MAPA_CODIGO_ELECCION.get(str(r_item[0]), "ninguno")
        resp1_full.append(
            {
                "orden": info1["orden"],
                "id_item": info1["id_item"],
                "semilla_apodo": semilla_apodo,
                "lado_polo_pos_mostrado": lado_pos,
                "sha256_mostrado_izquierda": sha_izq,
                "sha256_mostrado_derecha": sha_der,
                "eleccion": el_str,
                "tiempo_ms": int(r_item[1]) if len(r_item) > 1 else 0,
                "respondio_tras_ocultar_5s": bool(r_item[2])
                if len(r_item) > 2
                else False,
            }
        )

    # Reconstruir Parte 2 (26 pares)
    p2_ordenados = _orden_items_parte2_para_semilla(semilla_apodo, clave_data)
    resp2_raw = obj.get("p2", [])
    resp2_full = []
    for i, (info2, lado_pos2) in enumerate(p2_ordenados):
        sha_izq = (
            info2["sha256_polo_pos"]
            if lado_pos2 == "izquierda"
            else info2["sha256_polo_neg"]
        )
        sha_der = (
            info2["sha256_polo_neg"]
            if lado_pos2 == "izquierda"
            else info2["sha256_polo_pos"]
        )
        r_item = resp2_raw[i] if i < len(resp2_raw) else ["n", 0]
        el_str = MAPA_CODIGO_ELECCION.get(str(r_item[0]), "ninguno")
        resp2_full.append(
            {
                "orden_presentacion": i + 1,
                "id_item": info2["id_item"],
                "tipo_item": info2["tipo_item"],
                "pregunta": info2["pregunta"],
                "indicacion_director": info2.get("indicacion_director", ""),
                "semilla_apodo": semilla_apodo,
                "lado_polo_pos_mostrado": lado_pos2,
                "sha256_mostrado_izquierda": sha_izq,
                "sha256_mostrado_derecha": sha_der,
                "eleccion": el_str,
                "tiempo_ms": int(r_item[1]) if len(r_item) > 1 else 0,
            }
        )

    # Reconstruir Parte 3 (6 pares)
    p3_clave = clave_data["parte_3_clave"]
    lados3 = sortear_lados_equilibrados_mulberry32(
        (semilla_apodo + 404) & 0xFFFFFFFF, len(p3_clave)
    )
    resp3_raw = obj.get("p3", [])
    resp3_full = []
    for i, info3 in enumerate(p3_clave):
        lado_pos3 = lados3[i]
        sha_izq = (
            info3["sha256_polo_pos"]
            if lado_pos3 == "izquierda"
            else info3["sha256_polo_neg"]
        )
        sha_der = (
            info3["sha256_polo_neg"]
            if lado_pos3 == "izquierda"
            else info3["sha256_polo_pos"]
        )
        pal_str = str(resp3_raw[i]) if i < len(resp3_raw) else ""
        resp3_full.append(
            {
                "orden": info3["orden"],
                "id_item": info3["id_item"],
                "semilla_apodo": semilla_apodo,
                "lado_polo_pos_mostrado": lado_pos3,
                "sha256_mostrado_izquierda": sha_izq,
                "sha256_mostrado_derecha": sha_der,
                "palabras_usuario": pal_str,
            }
        )

    # Reconstruir Parte 4 (40 piezas ♥ / ✕)
    p4_bits = str(obj.get("p4", ""))
    votos4_full = []
    corazones_cnt = 0
    for i, p_meta in enumerate(piezas_40):
        gusta = (i < len(p4_bits)) and (p4_bits[i] == "1")
        if gusta:
            corazones_cnt += 1
        votos4_full.append(
            {
                "id_pieza": p_meta["id_pieza"],
                "sha256_imagen": p_meta["sha256_imagen"],
                "corazon": bool(gusta),
            }
        )

    return {
        "fase": "FASE 5d · El Salón (Prueba de sensaciones con personas · v3d.1)",
        "version_prerregistro": "3.3.1 (v3d.1)",
        "sha256_prerregistro": SHA256_PRERREG_V3D_ESPERADO,
        "fecha_iso": str(obj.get("fecha", "2026-10-28T00:00:00Z")),
        "participante": {
            "apodo": apodo,
            "semilla_apodo": semilla_apodo,
            "es_bruno_n2_d8": es_bruno,
            "edad_aproximada": obj.get("edad", ""),
            "trabaja_en_diseno_o_arte": obj.get("diseno", ""),
            "consentimiento_informado": bool(obj.get("consent", False)),
        },
        "parte_1_primer_golpe_vista": resp1_full,
        "parte_2_sentir": resp2_full,
        "parte_3_ponerle_nombre": resp3_full,
        "parte_4_gusto": {
            "cuenta_para_n2_y_d8": es_bruno,
            "total_corazones": corazones_cnt,
            "total_evaluadas": len(votos4_full),
            "votos": votos4_full,
        },
        "cierre": {
            "que_te_sorprendio": str(obj.get("cierre", "")),
        },
    }


def _formatear_tabla_markdown(analisis: Dict[str, Any]) -> str:
    lineas = [
        "# Tabla de Resultados · El Salón (v3d.1)",
        "",
        f"- **Participantes válidos:** `{analisis.get('participantes_validos', 0)}` "
        f"(Diseño/arte: `{analisis.get('participantes_diseno_arte', 0)}`, "
        f"Fuera de diseño: `{analisis.get('participantes_fuera_diseno', 0)}`)",
        f"- **Excluidos por atención:** `{len(analisis.get('participantes_excluidos_atencion', []))}`",
    ]
    if "resumen_global_parte_2" in analisis:
        rg = analisis["resumen_global_parte_2"]
        lineas.extend(
            [
                f"- **Acierto medio (20 neuronas):** `{rg['acierto_medio_20_neuronas_pct']}%` "
                f"(`% Ninguno`: `{rg['porcentaje_ninguno_medio_20_neuronas_pct']}%`)",
                f"- **Acierto en 4 controles al azar:** `{rg['acierto_medio_4_controles_azar_pct']}%` "
                f"(`% Ninguno`: `{rg['porcentaje_ninguno_4_controles_azar_pct']}%`)",
                f"- **Neuronas que se sienten de verdad ($\ge 70\%$, $p_{{\\text{{Holm}}}} < 0,05$ y $>$ brillo):** `{rg['neuronas_que_se_sienten_de_verdad']}`",
                "",
                "| # | Neurona | Eje | Acierto (%) | % Ninguno | Regla brillo (%) | $p_{\\text{Holm}}$ | ¿Se siente de verdad? |",
                "|---:|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for r in analisis.get("detalle_20_neuronas_parte_2", []):
            lineas.append(
                f"| {r['orden']} | `{r['id_neurona']}` | `{r['eje_sensacion']}` | "
                f"`{r['porcentaje_acierto']}%` | `{r['porcentaje_ninguno']}%` | "
                f"`{r['acierto_regla_simple_brillo_pct']}%` | `{r['p_valor_ajustado_holm']}` | "
                f"`{'SÍ' if r['se_siente_de_verdad'] else 'no'}` |"
            )
    return "\n".join(lineas) + "\n"


def juntar_resultados_desde_txt(
    ruta_txt_codigos: Path,
    carpeta_salida_respuestas: Path,
    ruta_clave: Path,
    ruta_prerregistro_v3d: Path,
    ruta_corpus_json: Path,
    carpeta_atlas_f7: Path,
    carpeta_atlas_f5: Path,
) -> Dict[str, Any]:
    clave_data = json.loads(ruta_clave.read_text(encoding="utf-8"))
    piezas_40 = _piezas_parte4_desde_prerregistro(
        ruta_prerregistro_v3d, ruta_corpus_json, carpeta_atlas_f7, carpeta_atlas_f5
    )

    carpeta_salida_respuestas.mkdir(parents=True, exist_ok=True)
    lineas_raw = (
        ruta_txt_codigos.read_text(encoding="utf-8").splitlines()
        if ruta_txt_codigos.is_file()
        else []
    )

    aceptados = 0
    rechazados: List[Dict[str, Any]] = []
    archivos_escritos: List[str] = []

    for num_linea, linea in enumerate(lineas_raw, start=1):
        if not linea.strip() or linea.strip().startswith("#"):
            continue
        try:
            doc = decodificar_linea_base64(linea, clave_data, piezas_40)
            apodo_limpio = re.sub(
                r"[^a-zA-Z0-9_-]", "_", doc["participante"]["apodo"]
            ).lower()
            ruta_out = (
                carpeta_salida_respuestas
                / f"salon_respuesta_{apodo_limpio}_{num_linea:02d}.json"
            )
            ruta_out.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            aceptados += 1
            archivos_escritos.append(str(ruta_out))
        except ValueError as exc:
            rechazados.append({"linea": num_linea, "motivo": str(exc)})

    analisis = analizar_respuestas_salon(carpeta_salida_respuestas, ruta_clave)
    ruta_tabla_json = carpeta_salida_respuestas / "tabla_resultados_salon.json"
    ruta_tabla_md = carpeta_salida_respuestas / "TABLA-RESULTADOS-SALON.md"

    salida = {
        "fase": "FASE 5e · Juntar resultados de El Salón para llevar",
        "sha256_prerregistro_requerido": SHA256_PRERREG_V3D_ESPERADO,
        "codigos_aceptados": aceptados,
        "codigos_rechazados": len(rechazados),
        "detalle_rechazados": rechazados,
        "archivos_json_reconstruidos": archivos_escritos,
        "analisis_salon": analisis,
    }
    ruta_tabla_json.write_text(
        json.dumps(salida, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ruta_tabla_md.write_text(_formatear_tabla_markdown(analisis), encoding="utf-8")
    return salida


def main(argv: List[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Lee un archivo de texto con códigos Base64 (uno por línea), valida el sha256 de v3d.1 y genera la tabla de analizar_salon.py."
    )
    parser.add_argument(
        "--codigos-txt",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon/codigos_whatsapp.txt",
        help="Archivo de texto con los códigos Base64 pegados (uno por línea).",
    )
    parser.add_argument(
        "--salida-respuestas",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon/respuestas",
        help="Carpeta donde escribir los JSON reconstruidos y la tabla de resultados.",
    )
    parser.add_argument(
        "--clave",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/el-salon/clave_salon_no_abrir.json",
    )
    parser.add_argument(
        "--prerregistro-v3d", default=str(base_dir / "prerregistro_v3d.json")
    )
    parser.add_argument("--corpus-json", default=str(base_dir / "corpus_cc0_630.json"))
    parser.add_argument("--atlas-f7", default=str(base_dir / "atlas"))
    parser.add_argument("--atlas-f5", default=str(base_dir / "atlas_f5"))
    args = parser.parse_args(argv)

    res = juntar_resultados_desde_txt(
        ruta_txt_codigos=Path(args.codigos_txt).expanduser().resolve(),
        carpeta_salida_respuestas=Path(args.salida_respuestas).expanduser().resolve(),
        ruta_clave=Path(args.clave).expanduser().resolve(),
        ruta_prerregistro_v3d=Path(args.prerregistro_v3d).expanduser().resolve(),
        ruta_corpus_json=Path(args.corpus_json).expanduser().resolve(),
        carpeta_atlas_f7=Path(args.atlas_f7).expanduser().resolve(),
        carpeta_atlas_f5=Path(args.atlas_f5).expanduser().resolve(),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
