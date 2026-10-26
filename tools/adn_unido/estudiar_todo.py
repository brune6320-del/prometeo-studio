#!/usr/bin/env python3
"""ADN Unido (Fase 4 · D-10 + D-11b): genera <nombre>.ficha.json por pieza del corpus.

Une el ADN tipográfico (D-10, tools/adn_tipo/, commit dc5ddd5) y el ADN de diseño
(D-11b, tools/adn_diseno/, commit d25e701) sin modificar un solo byte de tools/adn_tipo/.
Respeta estrictamente la Ley 8: si alguna parte requiere GPU, ejecutables o pesos
no presentes en la Mac mini, declara {"estado": "no_calculado", "motivo": "…"}.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.adn_diseno.estudiar import estudiar_referente
from tools.adn_unido.esquema import (
    COMMIT_ADN_DISENO,
    COMMIT_ADN_TIPO,
    SCHEMA_VERSION_ADN_DISENO,
    SCHEMA_VERSION_ADN_TIPO,
    SCHEMA_VERSION_UNIDO,
    calcular_sha256_ficha_sin_fecha,
    validar_ficha_unida,
)

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".pdf"}
EXTENSIONES_FUENTE = {".ttf", ".otf"}


def _identificador_maquina() -> str:
    """Devuelve identificador determinista del nodo y arquitectura."""
    nodo = platform.node() or "mac-mini"
    sist = platform.system()
    maq = platform.machine()
    py_ver = platform.python_version()
    return f"{nodo} ({sist} {maq}, Python {py_ver})"


def _diagnosticar_entorno_adn_tipo(dir_adn_tipo: Path) -> List[str]:
    """Comprueba qué dependencias de tools/adn_tipo (Camino B: OCR + galería + CNN) faltan en la Mac mini."""
    faltantes: List[str] = []
    if shutil.which("tesseract") is None:
        faltantes.append("binario del sistema 'tesseract' (OCR)")
    for mod in ("numpy", "PIL", "pytesseract", "fitz", "skimage"):
        if importlib.util.find_spec(mod) is None:
            faltantes.append(f"módulo Python '{mod}'")
    dir_cache = dir_adn_tipo / ".cache"
    if not (dir_cache / "dataset").is_dir():
        faltantes.append("galería sintética 'tools/adn_tipo/.cache/dataset' (500 glifos)")
    if not (dir_cache / "modelo" / "pesos.pt").is_file():
        faltantes.append("pesos CNN 'tools/adn_tipo/.cache/modelo/pesos.pt' (entrenamiento GPU Colab)")
    return faltantes


def _cargar_catalogo_lock_adn_tipo(dir_adn_tipo: Path) -> Dict[str, Dict[str, Any]]:
    """Lee tools/adn_tipo/fuentes.lock.json (solo lectura) e indexa por nombre de familia en minúsculas."""
    ruta_lock = dir_adn_tipo / "fuentes.lock.json"
    if not ruta_lock.is_file():
        return {}
    try:
        datos = json.loads(ruta_lock.read_text(encoding="utf-8"))
        out: Dict[str, Dict[str, Any]] = {}
        for item in datos.get("fuentes", []):
            nombre = str(item.get("fuente", "")).strip()
            if nombre:
                out[nombre.lower()] = {
                    "fuente": item.get("fuente"),
                    "subfamilia_catalogo": item.get("subfamilia"),
                    "categoria": item.get("categoria"),
                    "contraste": item.get("contraste"),
                    "licencia": item.get("licencia"),
                }
        return out
    except Exception:
        return {}


def _parsear_tablas_opentype(ruta_ttf: Path) -> Dict[str, Any]:
    """Extrae metadatos tipográficos directamente de las tablas binarias OpenType/TrueType (.ttf/.otf)."""
    data = ruta_ttf.read_bytes()
    if len(data) < 12:
        raise ValueError(f"Archivo tipográfico demasiado corto: {ruta_ttf}")
    _, num_tables, _, _, _ = struct.unpack(">IHHHH", data[:12])
    tables: Dict[str, Tuple[int, int]] = {}
    for i in range(num_tables):
        off = 12 + i * 16
        if off + 16 > len(data):
            break
        tag, _, t_off, t_len = struct.unpack(">4sIII", data[off : off + 16])
        tables[tag.decode("ascii", errors="replace")] = (t_off, t_len)

    info: Dict[str, Any] = {
        "units_per_em": None,
        "usWeightClass": None,
        "usWidthClass": None,
        "italicAngle": 0.0,
        "familia": None,
        "subfamilia": None,
        "nombre_completo": None,
        "postscript_name": None,
        "es_variable": "fvar" in tables,
        "tablas_opentype": sorted(tables.keys()),
    }

    if "head" in tables:
        o, l = tables["head"]
        if o + 20 <= len(data) and l >= 20:
            info["units_per_em"] = struct.unpack(">H", data[o + 18 : o + 20])[0]

    if "OS/2" in tables:
        o, l = tables["OS/2"]
        if o + 8 <= len(data) and l >= 8:
            weight, width = struct.unpack(">HH", data[o + 4 : o + 8])
            info["usWeightClass"] = weight
            info["usWidthClass"] = width

    if "post" in tables:
        o, l = tables["post"]
        if o + 8 <= len(data) and l >= 8:
            italic_fixed = struct.unpack(">i", data[o + 4 : o + 8])[0]
            info["italicAngle"] = round(italic_fixed / 65536.0, 2)

    if "name" in tables:
        o, l = tables["name"]
        if o + 6 <= len(data) and l >= 6:
            _, count, str_off = struct.unpack(">HHH", data[o : o + 6])
            names: Dict[int, str] = {}
            for i in range(count):
                ro = o + 6 + i * 12
                if ro + 12 > len(data):
                    break
                pid, _, _, nid, slen, soff = struct.unpack(">HHHHHH", data[ro : ro + 12])
                if nid in (1, 2, 4, 6, 16, 17):
                    s_ini = o + str_off + soff
                    s_fin = s_ini + slen
                    if s_fin <= len(data):
                        raw = data[s_ini:s_fin]
                        try:
                            txt = raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman")
                            txt = txt.replace("\x00", "").strip()
                            if txt and (nid not in names or pid == 3):
                                names[nid] = txt
                        except Exception:
                            pass
            info["familia"] = names.get(16) or names.get(1)
            info["subfamilia"] = names.get(17) or names.get(2)
            info["nombre_completo"] = names.get(4)
            info["postscript_name"] = names.get(6)

    if not info["familia"]:
        info["familia"] = ruta_ttf.stem
    return info


def _evaluar_bloque_tipo(
    ruta_pieza: Path,
    dir_adn_tipo: Path,
    escala_diseno: Optional[Dict[str, Any]],
    catalogo_lock: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Ejecuta o diagnostica el bloque 'tipo' respetando el principio de negativo honesto (Ley 8)."""
    sufijo = ruta_pieza.suffix.lower()

    # Caso 1: Archivo tipográfico vectorial OpenType/TrueType (.ttf / .otf)
    if sufijo in EXTENSIONES_FUENTE:
        meta_ot = _parsear_tablas_opentype(ruta_pieza)
        fam = str(meta_ot.get("familia") or ruta_pieza.stem)
        sub = str(meta_ot.get("subfamilia") or "Regular")
        peso = meta_ot.get("usWeightClass")
        etiqueta = f"{fam} ({sub}, peso={peso})" if peso is not None else f"{fam} ({sub})"
        entrada_cat = catalogo_lock.get(fam.lower())
        return {
            "estado": "calculado_nativo_opentype",
            "motivo": (
                "Pieza vectorial OpenType/TrueType (.ttf): metadatos extraídos directamente de las tablas "
                "binarias (name, OS/2, head, post, fvar). La inferencia visual de carteles (inferir.py) "
                "no aplica a un contenedor de fuente sin imagen rasterizada."
            ),
            "fuente_detectada": etiqueta,
            "metadatos_opentype": meta_ot,
            "catalogo_adn_tipo": entrada_cat,
        }

    # Caso 2: Cartel / imagen rasterizada o PDF -> comprobar entorno de tools/adn_tipo
    faltantes = _diagnosticar_entorno_adn_tipo(dir_adn_tipo)
    if not faltantes:
        script_extraer = dir_adn_tipo / "extraer.py"
        try:
            res = subprocess.run(
                [sys.executable, str(script_extraer), str(ruta_pieza)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if res.returncode == 0 and res.stdout.strip().startswith("{"):
                salida_tipo = json.loads(res.stdout.strip())
                zonas = salida_tipo.get("zonas", [])
                top1 = (
                    zonas[0]["fuente_top3"][0]["fuente"]
                    if (zonas and zonas[0].get("fuente_top3"))
                    else "sin_zonas_detectadas"
                )
                return {
                    "estado": "calculado",
                    "fuente_detectada": top1,
                    "salida_adn_tipo": salida_tipo,
                }
        except Exception as exc:
            faltantes.append(f"error de ejecución en extraer.py: {exc}")

    resumen_estimacion = None
    if isinstance(escala_diseno, dict):
        resumen_estimacion = {
            "hay_texto_detectado": escala_diseno.get("hay_texto_detectado"),
            "niveles_detectados": escala_diseno.get("niveles_detectados"),
            "alturas_relativas_lineas": escala_diseno.get("alturas_relativas_lineas"),
            "razon_escala": escala_diseno.get("razon_escala"),
            "densidad_tipografica_rel": escala_diseno.get("densidad_tipografica_rel"),
        }

    return {
        "estado": "no_calculado",
        "motivo": (
            "Camino B de tools/adn_tipo (extraer.py / inferir.py) no ejecutable en esta Mac mini sin "
            + ", ".join(faltantes)
            + "."
        ),
        "fuente_detectada": "no_calculado",
        "dependencias_faltantes": faltantes,
        "estimacion_estructural_adn_diseno": resumen_estimacion,
    }


def estudiar_pieza_unida(
    ruta_pieza: str | Path,
    max_dim_analisis: int = 192,
) -> Dict[str, Any]:
    """Construye y valida la ficha unida (<nombre>.ficha.json) para una pieza del corpus."""
    ruta = Path(ruta_pieza).expanduser().resolve()
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la pieza de entrada: {ruta}")

    sha256_bytes = hashlib.sha256(ruta.read_bytes()).hexdigest()
    sufijo = ruta.suffix.lower()

    dir_tools = Path(__file__).resolve().parent.parent
    dir_adn_tipo = dir_tools / "adn_tipo"
    catalogo_lock = _cargar_catalogo_lock_adn_tipo(dir_adn_tipo)

    if sufijo in EXTENSIONES_IMAGEN:
        estudio_diseno = estudiar_referente(ruta, max_dim_analisis=max_dim_analisis)
        bloque_diseno: Dict[str, Any] = {
            "estado": "calculado",
            **estudio_diseno,
        }
        escala_diseno = estudio_diseno.get("escala_tipografica")
    elif sufijo in EXTENSIONES_FUENTE:
        bloque_diseno = {
            "estado": "no_calculado",
            "motivo": (
                "Archivo tipográfico vectorial OpenType/TrueType (.ttf) sin imagen rasterizada, "
                "paleta cromática ni retícula de cartel; no se inventa renderizado artificial (Ley 8)."
            ),
            "k_elegido": None,
            "paleta_insuficiente": None,
            "confianza_global": None,
        }
        escala_diseno = None
    else:
        raise ValueError(f"Extensión de pieza no soportada en ADN Unido: {ruta.name}")

    bloque_tipo = _evaluar_bloque_tipo(
        ruta,
        dir_adn_tipo=dir_adn_tipo,
        escala_diseno=escala_diseno,
        catalogo_lock=catalogo_lock,
    )

    fecha_utc = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    ficha: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_UNIDO,
        "tipo": bloque_tipo,
        "diseno": bloque_diseno,
        "procedencia": {
            "nombre_archivo": ruta.name,
            "sha256_imagen": sha256_bytes,
            "commit_adn_tipo": COMMIT_ADN_TIPO,
            "commit_adn_diseno": COMMIT_ADN_DISENO,
            "schema_version_adn_tipo": SCHEMA_VERSION_ADN_TIPO,
            "schema_version_adn_diseno": SCHEMA_VERSION_ADN_DISENO,
            "fecha_utc": fecha_utc,
            "maquina": _identificador_maquina(),
            "sha256_ficha_determinista": "",
        },
    }
    ficha["procedencia"]["sha256_ficha_determinista"] = calcular_sha256_ficha_sin_fecha(ficha)

    ok, errores = validar_ficha_unida(ficha)
    if not ok:
        raise ValueError(f"La ficha unida generada para {ruta.name} viola el esquema: {errores}")

    return ficha


def resolver_piezas_carpeta(carpeta_entrada: str | Path) -> List[Path]:
    """Localiza de forma determinista las piezas de una carpeta (o su subcarpeta muestras/)."""
    base = Path(carpeta_entrada).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"No existe la carpeta de entrada: {base}")
    if base.is_file():
        return [base]

    dir_busqueda = (base / "muestras") if (base / "muestras").is_dir() else base
    extensiones_validas = EXTENSIONES_IMAGEN | EXTENSIONES_FUENTE
    piezas = [
        p
        for p in sorted(dir_busqueda.iterdir(), key=lambda x: x.name)
        if p.is_file() and p.suffix.lower() in extensiones_validas and not p.name.startswith(".")
    ]
    return piezas


def estudiar_carpeta(
    carpeta_entrada: str | Path,
    carpeta_salida: str | Path,
    max_dim_analisis: int = 192,
) -> List[Tuple[Path, Path, Dict[str, Any]]]:
    """Procesa todas las piezas de carpeta_entrada y escribe <nombre>.ficha.json en carpeta_salida."""
    piezas = resolver_piezas_carpeta(carpeta_entrada)
    if not piezas:
        raise ValueError(f"No se encontraron piezas soportadas en {carpeta_entrada}")

    out_dir = Path(carpeta_salida).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    resultados: List[Tuple[Path, Path, Dict[str, Any]]] = []
    vistas_nombre: set[str] = set()

    for pieza in piezas:
        stem = pieza.stem
        nombre_ficha = f"{stem}.ficha.json" if stem not in vistas_nombre else f"{pieza.name}.ficha.json"
        vistas_nombre.add(stem)

        ficha = estudiar_pieza_unida(pieza, max_dim_analisis=max_dim_analisis)
        ruta_ficha = out_dir / nombre_ficha
        texto = json.dumps(ficha, indent=2, ensure_ascii=False) + "\n"
        ruta_ficha.write_text(texto, encoding="utf-8")
        resultados.append((pieza, ruta_ficha, ficha))

    return resultados


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ADN Unido (Fase 4): genera <nombre>.ficha.json unificando D-10 (adn_tipo) y D-11b (adn_diseno)."
    )
    parser.add_argument(
        "carpeta_entrada",
        help="Carpeta de entrada con los carteles/piezas (p. ej. ~/Desktop/REFERENTES/corpus-editorial/).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="/tmp/adn_unido_fichas",
        help="Carpeta donde escribir los archivos <nombre>.ficha.json (por defecto /tmp/adn_unido_fichas).",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=192,
        help="Dimensión máxima de rejilla de análisis cromático/composicional (por defecto 192).",
    )
    args = parser.parse_args(argv)

    resultados = estudiar_carpeta(
        args.carpeta_entrada,
        args.output_dir,
        max_dim_analisis=args.max_dim,
    )
    print(f"Generadas {len(resultados)} fichas en {Path(args.output_dir).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
