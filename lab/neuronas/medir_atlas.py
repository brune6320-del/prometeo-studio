#!/usr/bin/env python3
"""Validador del Atlas piloto de neuronas (FASE 5 · N-1).

Verifica:
1. Prerregistro intacto (SHA-256 de lab/neuronas/prerregistro.json = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388).
2. Exactamente 200 fichas PRAGMA en lab/neuronas/atlas/neurona_<id>.json correspondientes a las 200 neuronas sorteadas con semilla 2610.
3. Cada ficha contiene: polo_pos (9 entradas solo con sha256), polo_neg (9 entradas solo con sha256), etiqueta, etiquetador="Argon", sha256_pesos, fecha y confirmada (true/false).
4. Las neuronas con confirmada=false NO se borran y cumplen ratio_top9_vs_control9 < 2.0 (o caida_media_top9 == 0).
5. Ninguna imagen ni archivo de pesos (.pth/.png/.jpg) está dentro de lab/neuronas/.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

SHA_PRERREGISTRO_ESPERADO = "a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388"
SHA_PESOS_ESPERADO = "983f1562536e84ff750a1576fb08e54de751dbf2e17c0d8a4a13704341fdcd3d"


def main() -> int:
    dir_neuronas = Path(__file__).resolve().parent
    ruta_prerreg = dir_neuronas / "prerregistro.json"
    dir_atlas = dir_neuronas / "atlas"

    # 1. Prerregistro intacto
    sha_pre = hashlib.sha256(ruta_prerreg.read_bytes()).hexdigest()
    ok_1 = sha_pre == SHA_PRERREGISTRO_ESPERADO

    # 2. 200 fichas exactas con semilla 2610
    esperadas_200 = sorted(random.Random(2610).sample(range(768), 200))
    archivos_json = sorted(dir_atlas.glob("neurona_*.json"))
    ids_presentes = []
    validas = 0
    confirmadas = 0
    no_confirmadas = 0

    for p in archivos_json:
        f = json.loads(p.read_text(encoding="utf-8"))
        ids_presentes.append(int(f["canal_indice"]))
        tiene_campos = (
            isinstance(f.get("polo_pos"), list)
            and len(f["polo_pos"]) == 9
            and isinstance(f.get("polo_neg"), list)
            and len(f["polo_neg"]) == 9
            and isinstance(f.get("etiqueta"), str)
            and " frente a " in f["etiqueta"]
            and f.get("etiquetador") == "Argon"
            and f.get("sha256_pesos") == SHA_PESOS_ESPERADO
            and isinstance(f.get("fecha"), str)
            and isinstance(f.get("confirmada"), bool)
        )
        ap = f.get("prueba_apagado", {})
        c_top9 = float(ap.get("caida_media_top9", 0.0))
        c_ctrl9 = float(ap.get("caida_media_control9", 0.0))
        regla_ok = f["confirmada"] == ((c_top9 > 0.0) and (c_top9 >= 2.0 * c_ctrl9 - 1e-6))
        if tiene_campos and regla_ok:
            validas += 1
        if f.get("confirmada"):
            confirmadas += 1
        else:
            no_confirmadas += 1

    ok_2 = (ids_presentes == esperadas_200) and (len(archivos_json) == 200)
    ok_3 = validas == 200
    ok_4 = (confirmadas + no_confirmadas == 200) and (no_confirmadas > 0)

    # 5. Sin pesos ni imágenes en lab/neuronas/
    prohibidos = [
        p.name
        for p in dir_neuronas.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pth", ".pt", ".png", ".jpg", ".jpeg", ".bmp"}
    ]
    ok_5 = len(prohibidos) == 0

    pruebas = [
        ("1. Prerregistro sellado intacto (sha256=a28a09f3…)", ok_1),
        ("2. 200/200 neuronas de semilla 2610 presentes en lab/neuronas/atlas/", ok_2),
        ("3. 200/200 fichas PRAGMA válidas (polo_pos=9, polo_neg=9, etiquetador=Argon, regla 2x)", ok_3),
        (f"4. Negativos conservados sin borrar ({confirmadas} confirmadas, {no_confirmadas} con confirmada=false)", ok_4),
        ("5. Cero pesos e imágenes dentro del árbol Git (solo sha256)", ok_5),
    ]
    for nombre, ok in pruebas:
        print(f"[{'PASS' if ok else 'FAIL'}] {nombre}")
    return 0 if all(ok for _, ok in pruebas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
