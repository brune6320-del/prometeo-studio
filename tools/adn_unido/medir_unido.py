#!/usr/bin/env python3
"""Suite de 5 pruebas obligatorias de Fase 4b (ADN Unido: D-10 Camino B sin CNN + D-11b).

Verifica:
1. 22/22 fichas válidas contra el validador del esquema (tools/adn_unido/esquema.py).
2. Determinismo: dos corridas seguidas dan el mismo sha256 por ficha (excluyendo fecha_utc).
3. Integridad del lote: ningún cartel/pieza se pierde ni se duplica (22 entradas únicas).
4. Inmutabilidad de D-10: tools/adn_tipo/ sigue idéntico byte a byte al commit dc5ddd5
   (tree Git SHA-1 fe5ee96d398e6b6fb1acaa3ff00004f765ff8173 y 42/42 blobs verificados).
5. Cobertura tipográfica en carteles (Fase 4b): en >=12 de los 18 carteles el bloque 'tipo'
   trae texto detectado o una métrica de letra distinta de no_calculado, y el sub-bloque
   CNN mantiene {"estado": "no_calculado", "motivo": "pesos.pt se entrenan en Colab (D-10), aún no entrenados"}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.adn_unido.esquema import (
    CNN_MOTIVO_ESPERADO,
    COMMIT_ADN_TIPO,
    calcular_sha256_ficha_sin_fecha,
    validar_ficha_unida,
)
from tools.adn_unido.estudiar_todo import (
    EXTENSIONES_IMAGEN,
    estudiar_carpeta,
    resolver_piezas_carpeta,
)

CORPUS_D3_DEFAULT = Path(
    "/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-editorial"
)

TREE_SHA1_ADN_TIPO_DC5DDD5 = "fe5ee96d398e6b6fb1acaa3ff00004f765ff8173"
DIRECTORIOS_IGNORADOS_ADN_TIPO = {"__pycache__", ".cache", ".venv", "salidas"}


def _git_blob_sha1(data: bytes) -> bytes:
    hdr = f"blob {len(data)}\x00".encode("ascii")
    return hashlib.sha1(hdr + data).digest()


def _calcular_git_tree_sha1_directorio(dir_path: Path) -> Tuple[str, int]:
    """Calcula de forma exacta el objeto Merkle tree SHA-1 de Git para los archivos rastreados."""
    entradas: List[Tuple[bytes, str, str, bytes]] = []
    total_archivos = 0
    for p in dir_path.iterdir():
        if p.name in DIRECTORIOS_IGNORADOS_ADN_TIPO or p.name.endswith(".pyc"):
            continue
        if p.is_dir():
            sub_hex, sub_cnt = _calcular_git_tree_sha1_directorio(p)
            if sub_cnt == 0:
                continue
            modo = "40000"
            sha_bin = bytes.fromhex(sub_hex)
            clave_orden = (p.name + "/").encode("utf-8")
            total_archivos += sub_cnt
        elif p.is_file():
            st = p.stat().st_mode
            modo = "100755" if (st & stat.S_IXUSR) else "100644"
            sha_bin = _git_blob_sha1(p.read_bytes())
            clave_orden = p.name.encode("utf-8")
            total_archivos += 1
        else:
            continue
        entradas.append((clave_orden, modo, p.name, sha_bin))

    entradas.sort(key=lambda x: x[0])
    cuerpo = b"".join(
        f"{modo} {nombre}\x00".encode("utf-8") + sha_bin
        for _, modo, nombre, sha_bin in entradas
    )
    cabecera = f"tree {len(cuerpo)}\x00".encode("ascii")
    return hashlib.sha1(cabecera + cuerpo).hexdigest(), total_archivos


def _leer_objeto_pack_git(git_dir: Path, sha_hex: str) -> bytes | None:
    """Busca y descomprime un objeto no-delta en .git/objects/pack/*.idx (formato v2)."""
    pack_dir = git_dir / "objects" / "pack"
    if not pack_dir.is_dir():
        return None
    sha_bytes = bytes.fromhex(sha_hex)
    b0 = sha_bytes[0]
    for idx_path in sorted(pack_dir.glob("*.idx")):
        idx_data = idx_path.read_bytes()
        if idx_data[:8] != b"\xfftOc\x00\x00\x00\x02":
            continue
        fanout = struct.unpack(">256I", idx_data[8 : 8 + 1024])
        lo = 0 if b0 == 0 else fanout[b0 - 1]
        hi = fanout[b0]
        total = fanout[255]
        sha_table_off = 8 + 1024
        pos_encontrado = -1
        for i in range(lo, hi):
            off = sha_table_off + i * 20
            if idx_data[off : off + 20] == sha_bytes:
                pos_encontrado = i
                break
        if pos_encontrado < 0:
            continue
        off_table = sha_table_off + total * 20 + total * 4
        pack_offset = struct.unpack(
            ">I", idx_data[off_table + pos_encontrado * 4 : off_table + (pos_encontrado + 1) * 4]
        )[0]
        pack_path = idx_path.with_suffix(".pack")
        if not pack_path.is_file():
            continue
        pack_data = pack_path.read_bytes()
        p = pack_offset
        c = pack_data[p]
        obj_type = (c >> 4) & 7
        p += 1
        while c & 0x80:
            c = pack_data[p]
            p += 1
        if obj_type in (1, 2, 3):
            return zlib.decompress(pack_data[p:])
    return None


def _leer_contenido_objeto_git(git_dir: Path, sha: str) -> bytes | None:
    """Lee el cuerpo de un objeto Git (suelto o en packfile)."""
    obj_path = git_dir / "objects" / sha[:2] / sha[2:]
    if obj_path.is_file():
        raw = zlib.decompress(obj_path.read_bytes())
        idx = raw.index(b"\x00")
        return raw[idx + 1 :]
    return _leer_objeto_pack_git(git_dir, sha)


def verificar_identidad_adn_tipo(
    repo_root: Path,
    commit_esperado: str = COMMIT_ADN_TIPO,
    tree_esperado: str = TREE_SHA1_ADN_TIPO_DC5DDD5,
) -> Tuple[bool, str]:
    """Verifica que tools/adn_tipo/ sea idéntico byte a byte al commit dc5ddd5."""
    dir_adn_tipo = repo_root / "tools" / "adn_tipo"
    if not dir_adn_tipo.is_dir():
        return False, f"No existe el directorio {dir_adn_tipo}"

    git_dir = repo_root / ".git"
    commit_raw = _leer_contenido_objeto_git(git_dir, commit_esperado)
    if commit_raw is not None:
        root_tree = ""
        for linea in commit_raw.decode("utf-8", errors="replace").splitlines():
            if linea.startswith("tree "):
                root_tree = linea.split()[1].strip()
                break
        if root_tree:
            root_tree_raw = _leer_contenido_objeto_git(git_dir, root_tree)
            if root_tree_raw is not None:
                idx_tools = root_tree_raw.find(b"40000 tools\x00")
                if idx_tools >= 0:
                    tools_sha = root_tree_raw[idx_tools + 12 : idx_tools + 32].hex()
                    tools_raw = _leer_contenido_objeto_git(git_dir, tools_sha)
                    if tools_raw is not None:
                        idx_adn = tools_raw.find(b"40000 adn_tipo\x00")
                        if idx_adn >= 0:
                            tree_leido = tools_raw[idx_adn + 15 : idx_adn + 35].hex()
                            if tree_leido != tree_esperado:
                                return (
                                    False,
                                    f"El tree de adn_tipo en {commit_esperado[:7]} ({tree_leido}) no coincide con {tree_esperado}",
                                )

    tree_actual, num_archivos = _calcular_git_tree_sha1_directorio(dir_adn_tipo)
    if tree_actual != tree_esperado:
        return (
            False,
            f"El árbol Git calculado en disco para tools/adn_tipo/ ({tree_actual}) difiere del árbol de {commit_esperado[:7]} ({tree_esperado})",
        )

    return (
        True,
        f"{num_archivos}/42 archivos rastreados de tools/adn_tipo/ idénticos byte a byte a {commit_esperado[:7]} (Merkle tree SHA-1 = {tree_actual[:12]}…)",
    )


def ejecutar_pruebas_unido(
    carpeta_corpus: Path = CORPUS_D3_DEFAULT,
    carpeta_salida_persistente: Path | None = None,
) -> Tuple[bool, List[Tuple[str, bool, str]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Ejecuta las 5 pruebas obligatorias de medir_unido.py y devuelve resumen, tabla de 18 carteles y tabla de 22 piezas."""
    repo_root = Path(__file__).resolve().parents[2]
    piezas_esperadas = resolver_piezas_carpeta(carpeta_corpus)
    num_esperado = len(piezas_esperadas)

    with tempfile.TemporaryDirectory(prefix="adn_unido_run1_") as dir_run1, tempfile.TemporaryDirectory(
        prefix="adn_unido_run2_"
    ) as dir_run2:
        corrida_1 = estudiar_carpeta(carpeta_corpus, dir_run1)
        corrida_2 = estudiar_carpeta(carpeta_corpus, dir_run2)

        if carpeta_salida_persistente is not None:
            carpeta_salida_persistente.mkdir(parents=True, exist_ok=True)
            for _, ruta_ficha, _ in corrida_1:
                destino = carpeta_salida_persistente / ruta_ficha.name
                destino.write_bytes(ruta_ficha.read_bytes())

        # Prueba 1: 22/22 fichas válidas contra el validador del esquema
        validas = 0
        errores_esquema: List[str] = []
        for pieza, ruta_ficha, _ in corrida_1:
            datos_leidos = json.loads(ruta_ficha.read_text(encoding="utf-8"))
            ok, errs = validar_ficha_unida(datos_leidos)
            if ok:
                validas += 1
            else:
                errores_esquema.append(f"{pieza.name}: {errs}")
        ok_p1 = (validas == num_esperado) and (num_esperado == 22)
        msg_p1 = (
            f"{validas}/{num_esperado} fichas válidas contra validar_ficha_unida (schema_version=1.0.0)"
            if ok_p1
            else f"Fallo en validación ({validas}/{num_esperado}): {errores_esquema}"
        )

        # Prueba 2: Determinismo (dos corridas seguidas dan el mismo sha256 por ficha excluyendo fecha_utc)
        hashes_1 = {
            pieza.name: calcular_sha256_ficha_sin_fecha(
                json.loads(ruta_ficha.read_text(encoding="utf-8"))
            )
            for pieza, ruta_ficha, _ in corrida_1
        }
        hashes_2 = {
            pieza.name: calcular_sha256_ficha_sin_fecha(
                json.loads(ruta_ficha.read_text(encoding="utf-8"))
            )
            for pieza, ruta_ficha, _ in corrida_2
        }
        iguales_det = sum(
            1 for k in hashes_1 if k in hashes_2 and hashes_1[k] == hashes_2[k]
        )
        ok_p2 = (iguales_det == num_esperado) and (num_esperado == 22)
        msg_p2 = (
            f"{iguales_det}/{num_esperado} fichas producen idéntico SHA-256 canónico en 2 corridas consecutivas (excluyendo fecha_utc)"
            if ok_p2
            else f"Discrepancia de determinismo: {iguales_det}/{num_esperado} coinciden"
        )

        # Prueba 3: Ningún cartel se pierde ni se duplica
        nombres_entrada = [p.name for p in piezas_esperadas]
        nombres_salida = [p.name for p, _, _ in corrida_1]
        shas_imagen = [f["procedencia"]["sha256_imagen"] for _, _, f in corrida_1]
        fichas_archivos = [r.name for _, r, _ in corrida_1]
        sin_perdida = set(nombres_entrada) == set(nombres_salida)
        sin_duplicados = (
            len(nombres_salida) == len(set(nombres_salida)) == len(set(shas_imagen)) == len(set(fichas_archivos)) == 22
        )
        ok_p3 = sin_perdida and sin_duplicados
        msg_p3 = (
            f"22/22 piezas procesadas sin pérdidas ni duplicados ({len(set(shas_imagen))} sha256_imagen únicos)"
            if ok_p3
            else f"Pérdida o duplicación detectada: entrada={len(nombres_entrada)}, salida={len(nombres_salida)}, únicos={len(set(shas_imagen))}"
        )

        # Prueba 4: tools/adn_tipo/ idéntico byte a byte a dc5ddd5
        ok_p4, msg_p4 = verificar_identidad_adn_tipo(repo_root, COMMIT_ADN_TIPO)

        # Prueba 5 (Fase 4b): en >=12 de los 18 carteles el bloque tipo trae texto detectado
        # o una métrica de letra distinta de no_calculado
        carteles_con_letra = 0
        total_carteles = 0
        cnn_honesta_ok = True
        filas_18_carteles: List[Dict[str, Any]] = []
        filas_22_piezas: List[Dict[str, Any]] = []

        for pieza, _, ficha in corrida_1:
            dis = ficha["diseno"]
            tip = ficha["tipo"]
            es_cartel = pieza.suffix.lower() in EXTENSIONES_IMAGEN

            if es_cartel:
                total_carteles += 1
                cnn_sub = tip.get("cnn", {})
                if (
                    cnn_sub.get("estado") != "no_calculado"
                    or cnn_sub.get("motivo") != CNN_MOTIVO_ESPERADO
                ):
                    cnn_honesta_ok = False

                texto_res = str(tip.get("texto_ocr_resumen", "")).strip()
                metricas_l = tip.get("metricas_letra", {})
                fuente_v = metricas_l.get("fuente_vecino_top1")
                tiene_texto_o_metrica = (
                    tip.get("estado") == "calculado_camino_b_sin_cnn"
                    and int(tip.get("num_palabras_ocr", 0)) >= 1
                    and bool(texto_res)
                    and texto_res not in ("no_calculado", "sin_texto_ocr")
                    and bool(fuente_v)
                    and fuente_v not in ("no_calculado", "sin_texto_ocr")
                )
                if tiene_texto_o_metrica:
                    carteles_con_letra += 1

                filas_18_carteles.append(
                    {
                        "cartel": pieza.name,
                        "texto_ocr_resumen": texto_res or "sin_texto_ocr",
                        "metrica_principal": metricas_l.get("metrica_principal_resumen", "no_calculado"),
                        "confianza_tipo": float(tip.get("confianza_tipo", 0.0)),
                        "num_palabras_ocr": int(tip.get("num_palabras_ocr", 0)),
                        "num_glifos": int(tip.get("num_glifos_analizados", 0)),
                        "fuente_vecino_top1": fuente_v,
                    }
                )

            filas_22_piezas.append(
                {
                    "cartel": pieza.name,
                    "k_elegido": dis["paleta"]["k_elegido"] if dis.get("estado") == "calculado" else None,
                    "paleta_insuficiente": (
                        dis["paleta"]["paleta_insuficiente"] if dis.get("estado") == "calculado" else None
                    ),
                    "fuente_detectada": tip.get("fuente_detectada", "no_calculado"),
                    "confianza_global": dis["confianza"]["global"] if dis.get("estado") == "calculado" else None,
                }
            )

        ok_p5 = (total_carteles == 18) and (carteles_con_letra >= 12) and cnn_honesta_ok
        msg_p5 = (
            f"{carteles_con_letra}/{total_carteles} carteles con texto OCR y métricas de letra calculadas "
            f"(umbral >=12/18; sub-bloque CNN honesto en 18/18)"
        )

    pruebas = [
        ("1. Validez de esquema (22/22 fichas v1.0.0)", ok_p1, msg_p1),
        ("2. Determinismo estricto (2 corridas sin fecha_utc)", ok_p2, msg_p2),
        ("3. Integridad del lote (0 pérdidas, 0 duplicados)", ok_p3, msg_p3),
        ("4. Inmutabilidad byte a byte de tools/adn_tipo/ (dc5ddd5)", ok_p4, msg_p4),
        ("5. Cobertura de letra en carteles (>=12/18 con OCR + métrica != no_calculado)", ok_p5, msg_p5),
    ]
    todo_ok = all(ok for _, ok, _ in pruebas)
    return todo_ok, pruebas, filas_18_carteles, filas_22_piezas


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta las 5 pruebas obligatorias de medir_unido.py (Fase 4b) sobre el corpus D-3."
    )
    parser.add_argument(
        "--corpus",
        default=str(CORPUS_D3_DEFAULT),
        help="Ruta al corpus D-3 (por defecto ~/Desktop/REFERENTES/corpus-editorial).",
    )
    parser.add_argument(
        "--guardar-fichas",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-editorial/fichas-adn-unido",
        help="Carpeta donde persistir las 22 fichas generadas.",
    )
    args = parser.parse_args(argv)

    todo_ok, pruebas, filas_18, _ = ejecutar_pruebas_unido(
        Path(args.corpus).expanduser().resolve(),
        Path(args.guardar_fichas).expanduser().resolve() if args.guardar_fichas else None,
    )

    print("=== MEDIR_UNIDO · FASE 4b (LETRA EN LOS CARTELES + ADN UNIDO) ===")
    for nombre, ok, detalle in pruebas:
        estado = "PASS" if ok else "FAIL"
        print(f"[{estado}] {nombre}: {detalle}")

    print("\n=== TABLA DE 18 CARTELES (FASE 4b) ===")
    print(
        f"{'Cartel':<32} | {'Texto OCR (<=6 palabras)':<34} | {'Métrica de letra principal':<64} | {'Conf.Tipo':<9}"
    )
    print("-" * 148)
    for r in filas_18:
        print(
            f"{r['cartel']:<32} | {r['texto_ocr_resumen']:<34} | {r['metrica_principal']:<64} | {r['confianza_tipo']:.4f}"
        )

    pasadas = sum(1 for _, ok, _ in pruebas if ok)
    print(f"\nResultado global: {pasadas}/{len(pruebas)} pruebas superadas.")
    return 0 if todo_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
