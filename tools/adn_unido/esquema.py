#!/usr/bin/env python3
"""Validador estricto del contrato de salida de ADN Unido (<nombre>.ficha.json v1.0.0 · Fase 4c)."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Dict, List, Tuple

from tools.adn_diseno.esquema import (
    SCHEMA_VERSION as SCHEMA_VERSION_ADN_DISENO,
    validar_estudio,
)

SCHEMA_VERSION_UNIDO = "1.0.0"
SCHEMA_VERSION_ADN_TIPO = "1.0.0"

COMMIT_ADN_TIPO = "dc5ddd5b768a3e745cbaf903efbd4ba36aac5805"
COMMIT_ADN_DISENO = "d25e70187db2424be43c16c214059687c01252d4"

CNN_MOTIVO_ESPERADO = "pesos.pt se entrenan en Colab (D-10), aún no entrenados"

UMBRAL_FRACCION_PALABRAS_REALES = 0.50
UMBRAL_CONFIANZA_TIPO = 0.35
UMBRAL_SESGO_ANTON = 3.0 * (1.0 / 12.0)  # 0.25 (25.0%)
IDIOMAS_SPELLCHECKER = ("es", "en", "de", "fr")

CLAVES_RAIZ_UNIDO = (
    "schema_version",
    "tipo",
    "diseno",
    "procedencia",
)

CLAVES_PROCEDENCIA = (
    "nombre_archivo",
    "sha256_imagen",
    "commit_adn_tipo",
    "commit_adn_diseno",
    "schema_version_adn_tipo",
    "schema_version_adn_diseno",
    "fecha_utc",
    "maquina",
    "sha256_ficha_determinista",
)

ESTADOS_TIPO_VALIDOS = (
    "calculado",
    "calculado_camino_b_sin_cnn",
    "sin_texto_ocr",
    "calculado_nativo_opentype",
    "no_calculado",
)

RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RE_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
RE_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def calcular_sha256_ficha_sin_fecha(ficha: Dict[str, Any]) -> str:
    """Calcula el SHA-256 determinista de una ficha excluyendo procedencia.fecha_utc
    y procedencia.sha256_ficha_determinista."""
    copia = copy.deepcopy(ficha)
    proc = copia.get("procedencia")
    if isinstance(proc, dict):
        proc.pop("fecha_utc", None)
        proc.pop("sha256_ficha_determinista", None)
    canonico = json.dumps(copia, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def validar_ficha_unida(ficha: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Valida que una ficha <nombre>.ficha.json cumpla el contrato v1.0.0 (Fase 4c) de tools/adn_unido/."""
    errores: List[str] = []

    if not isinstance(ficha, dict):
        return False, ["La ficha raíz debe ser un objeto JSON (dict)."]

    claves_presentes = set(ficha.keys())
    claves_esperadas = set(CLAVES_RAIZ_UNIDO)
    faltantes = claves_esperadas - claves_presentes
    extras = claves_presentes - claves_esperadas
    if faltantes:
        errores.append(f"Faltan claves de primer nivel: {sorted(faltantes)}")
    if extras:
        errores.append(f"Claves de primer nivel no permitidas: {sorted(extras)}")

    if ficha.get("schema_version") != SCHEMA_VERSION_UNIDO:
        errores.append(
            f"schema_version inválido: esperado '{SCHEMA_VERSION_UNIDO}', recibido '{ficha.get('schema_version')}'"
        )

    # 1. Validar bloque 'tipo'
    tipo = ficha.get("tipo")
    if not isinstance(tipo, dict):
        errores.append("El bloque 'tipo' debe ser un dict.")
    else:
        estado_t = tipo.get("estado")
        if estado_t not in ESTADOS_TIPO_VALIDOS:
            errores.append(f"tipo.estado inválido: {estado_t}")
        fuente_det = tipo.get("fuente_detectada")
        if not isinstance(fuente_det, str) or not fuente_det.strip():
            errores.append("tipo.fuente_detectada debe ser un string no vacío.")

        if estado_t in ("calculado_camino_b_sin_cnn", "sin_texto_ocr"):
            if not isinstance(tipo.get("fiable"), bool):
                errores.append("tipo.fiable debe ser un booleano explícito en carteles.")
            motivo_fiab = tipo.get("motivo_fiabilidad")
            if not isinstance(motivo_fiab, str) or len(motivo_fiab.strip()) < 5:
                errores.append("tipo.motivo_fiabilidad obligatorio en carteles.")

            cnn_blk = tipo.get("cnn")
            if not isinstance(cnn_blk, dict):
                errores.append("tipo.cnn obligatorio en carteles procesados por Camino B.")
            else:
                if cnn_blk.get("estado") != "no_calculado":
                    errores.append(f"tipo.cnn.estado esperado 'no_calculado', recibido '{cnn_blk.get('estado')}'")
                if cnn_blk.get("motivo") != CNN_MOTIVO_ESPERADO:
                    errores.append(
                        f"tipo.cnn.motivo esperado '{CNN_MOTIVO_ESPERADO}', recibido '{cnn_blk.get('motivo')}'"
                    )

            motor_ocr = tipo.get("motor_ocr")
            if not isinstance(motor_ocr, dict) or motor_ocr.get("psm") != 6 or motor_ocr.get("semilla") != 2610:
                errores.append("tipo.motor_ocr debe fijar psm=6 y semilla=2610.")

            filtro_ocr = tipo.get("filtro_ocr")
            if not isinstance(filtro_ocr, dict):
                errores.append("tipo.filtro_ocr obligatorio en carteles (Fase 4c).")
            else:
                frac = filtro_ocr.get("fraccion_palabras_reales")
                if not isinstance(frac, (int, float)) or not (0.0 <= float(frac) <= 1.0):
                    errores.append(f"filtro_ocr.fraccion_palabras_reales inválida: {frac}")

            conf_t = tipo.get("confianza_tipo")
            if not isinstance(conf_t, (int, float)) or not (0.0 <= float(conf_t) <= 1.0):
                errores.append(f"tipo.confianza_tipo debe estar en [0.0, 1.0], recibido: {conf_t}")

            fiable_val = bool(tipo.get("fiable"))
            metricas_l = tipo.get("metricas_letra")
            if not fiable_val:
                if metricas_l != "no_fiable":
                    errores.append(
                        f"Cuando tipo.fiable == false, tipo.metricas_letra debe ser 'no_fiable' (recibido: {type(metricas_l).__name__})."
                    )
            else:
                if not isinstance(metricas_l, dict):
                    errores.append("Cuando tipo.fiable == true, tipo.metricas_letra debe ser un dict.")
                else:
                    sesgo_blk = tipo.get("sesgo_vecino", {})
                    if sesgo_blk.get("es_sesgado") and metricas_l.get("fuente_vecino_top1") != "sesgado":
                        errores.append(
                            "Cuando sesgo_vecino.es_sesgado == true, metricas_letra.fuente_vecino_top1 debe marcarse como 'sesgado'."
                        )
        elif estado_t == "no_calculado":
            motivo = tipo.get("motivo")
            if not isinstance(motivo, str) or len(motivo.strip()) < 10:
                errores.append("tipo.motivo obligatorio y descriptivo cuando estado == 'no_calculado'.")
            if fuente_det != "no_calculado":
                errores.append("Cuando tipo.estado == 'no_calculado', fuente_detectada debe ser 'no_calculado'.")
        elif estado_t == "calculado_nativo_opentype":
            meta_ot = tipo.get("metadatos_opentype")
            if not isinstance(meta_ot, dict) or not meta_ot.get("familia"):
                errores.append("tipo.metadatos_opentype.familia obligatorio en estado 'calculado_nativo_opentype'.")

    # 2. Validar bloque 'diseno'
    diseno = ficha.get("diseno")
    if not isinstance(diseno, dict):
        errores.append("El bloque 'diseno' debe ser un dict.")
    else:
        estado_d = diseno.get("estado")
        if estado_d not in ("calculado", "no_calculado"):
            errores.append(f"diseno.estado inválido: {estado_d}")
        if estado_d == "calculado":
            copia_estudio = {k: v for k, v in diseno.items() if k != "estado"}
            ok_est, err_est = validar_estudio(copia_estudio)
            if not ok_est:
                for e in err_est:
                    errores.append(f"diseno.{e}")
        elif estado_d == "no_calculado":
            motivo_d = diseno.get("motivo")
            if not isinstance(motivo_d, str) or len(motivo_d.strip()) < 10:
                errores.append("diseno.motivo obligatorio cuando diseno.estado == 'no_calculado'.")
            for campo_nulo in ("k_elegido", "paleta_insuficiente", "confianza_global"):
                if campo_nulo not in diseno or diseno[campo_nulo] is not None:
                    errores.append(f"diseno.{campo_nulo} debe estar presente y ser null cuando estado == 'no_calculado'.")

    # 3. Validar bloque 'procedencia'
    proc = ficha.get("procedencia")
    if not isinstance(proc, dict):
        errores.append("El bloque 'procedencia' debe ser un dict.")
    else:
        faltantes_p = set(CLAVES_PROCEDENCIA) - set(proc.keys())
        if faltantes_p:
            errores.append(f"Faltan claves en 'procedencia': {sorted(faltantes_p)}")
        sha_img = str(proc.get("sha256_imagen", ""))
        if not RE_SHA256.match(sha_img):
            errores.append(f"procedencia.sha256_imagen inválido: '{sha_img}'")
        c_tipo = str(proc.get("commit_adn_tipo", ""))
        if not RE_COMMIT.match(c_tipo) or not COMMIT_ADN_TIPO.startswith(c_tipo):
            errores.append(f"procedencia.commit_adn_tipo inválido: '{c_tipo}' (esperado {COMMIT_ADN_TIPO})")
        c_dis = str(proc.get("commit_adn_diseno", ""))
        if not RE_COMMIT.match(c_dis) or not COMMIT_ADN_DISENO.startswith(c_dis):
            errores.append(f"procedencia.commit_adn_diseno inválido: '{c_dis}' (esperado {COMMIT_ADN_DISENO})")
        if proc.get("schema_version_adn_tipo") != SCHEMA_VERSION_ADN_TIPO:
            errores.append(
                f"procedencia.schema_version_adn_tipo inválido: {proc.get('schema_version_adn_tipo')}"
            )
        if proc.get("schema_version_adn_diseno") != SCHEMA_VERSION_ADN_DISENO:
            errores.append(
                f"procedencia.schema_version_adn_diseno inválido: {proc.get('schema_version_adn_diseno')}"
            )
        fecha = str(proc.get("fecha_utc", ""))
        if not RE_ISO_UTC.match(fecha):
            errores.append(f"procedencia.fecha_utc no cumple ISO-8601 UTC: '{fecha}'")
        if not isinstance(proc.get("maquina"), str) or not proc["maquina"].strip():
            errores.append("procedencia.maquina debe ser un string no vacío.")
        sha_det = str(proc.get("sha256_ficha_determinista", ""))
        sha_calc = calcular_sha256_ficha_sin_fecha(ficha)
        if not RE_SHA256.match(sha_det) or sha_det != sha_calc:
            errores.append(
                f"procedencia.sha256_ficha_determinista ('{sha_det}') no coincide con el cálculo canónico ('{sha_calc}')."
            )

    return len(errores) == 0, errores
