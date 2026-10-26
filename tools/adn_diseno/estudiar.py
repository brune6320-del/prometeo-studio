#!/usr/bin/env python3
"""Punto de entrada principal de ADN de Diseño (D-11 / D-11b): genera estudio.json desde un referente."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .color_lab import estudiar_color
from .composicion import estudiar_composicion
from .esquema import SCHEMA_VERSION, validar_estudio
from .lector import LienzoLab, cargar_referente
from .saliencia import estudiar_saliencia


def estudiar_lienzo(
    lienzo: LienzoLab,
    num_colores: Optional[int] = None,
    k_min: int = 3,
    k_max: int = 10,
    umbral_de00: float = 5.0,
    ruta_referente: Optional[Path] = None,
) -> Dict[str, Any]:
    """Ejecuta todos los analizadores de ADN de diseño sobre un LienzoLab y valida el contrato v1.1.0."""
    paleta, conf_paleta = estudiar_color(
        lienzo.pixeles_lab,
        k=num_colores,
        k_min=k_min,
        k_max=k_max,
        umbral_de00=umbral_de00,
    )
    reticula, escala_tipo, vacio, jerarquia, confs_comp, notas_comp = estudiar_composicion(
        lienzo.pixeles_lab,
        ruta_referente=ruta_referente,
    )
    saliencia, conf_saliencia = estudiar_saliencia(
        lienzo.pixeles_lab,
        jerarquia.get("niveles", []),
    )

    rel_aspecto = round(
        lienzo.ancho_original / float(max(1, lienzo.alto_original)),
        4,
    )
    if abs(rel_aspecto - 1.0) <= 0.05:
        orientacion = "cuadrada"
    elif rel_aspecto < 1.0:
        orientacion = "vertical"
    else:
        orientacion = "horizontal"

    por_bloque = {
        "paleta": round(conf_paleta, 4),
        "reticula": round(confs_comp["reticula"], 4),
        "escala_tipografica": round(confs_comp["escala_tipografica"], 4),
        "vacio": round(confs_comp["vacio"], 4),
        "jerarquia": round(confs_comp["jerarquia"], 4),
        "saliencia": round(conf_saliencia, 4),
    }
    conf_global = round(sum(por_bloque.values()) / float(len(por_bloque)), 4)

    notas = {
        "paleta": (
            f"K={paleta['k_elegido']} elegido ({paleta['num_colores']} clústeres efectivos) en CIE L*a*b* (D65), "
            f"residuo medio ΔE2000={paleta['delta_e2000_cuantizacion_media']:.3f}, "
            f"paleta_insuficiente={paleta['paleta_insuficiente']}."
        ),
        **notas_comp,
        "saliencia": (
            f"Fusión Spectral Residual FFT 2D + contraste CIEDE2000 "
            f"(SNR={saliencia['snr_espacial']:.3f}, concentración={saliencia['concentracion_espacial']:.3f})."
        ),
    }

    estudio: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "referente": {
            "id": lienzo.id_referente,
            "tipo_entrada": lienzo.tipo_entrada,
            "sha256_origen": lienzo.sha256_origen,
            "dimensiones": {
                "ancho_px": lienzo.ancho_original,
                "alto_px": lienzo.alto_original,
                "relacion_aspecto": rel_aspecto,
                "orientacion": orientacion,
            },
        },
        "paleta": paleta,
        "reticula": reticula,
        "escala_tipografica": escala_tipo,
        "vacio": vacio,
        "jerarquia": jerarquia,
        "saliencia": saliencia,
        "confianza": {
            "global": conf_global,
            "por_bloque": por_bloque,
            "notas": notas,
        },
    }

    ok, errores = validar_estudio(estudio)
    if not ok:
        raise ValueError(f"El estudio generado viola el contrato v{SCHEMA_VERSION}: {errores}")
    return estudio


def estudiar_referente(
    entrada: str | Path,
    num_colores: Optional[int] = None,
    k_min: int = 3,
    k_max: int = 10,
    umbral_de00: float = 5.0,
    max_dim_analisis: int = 192,
) -> Dict[str, Any]:
    """Carga un referente (imagen, PDF, fotograma o pieza de recortador) y devuelve su estudio.json."""
    ruta_limpia = Path(str(entrada).split("#page=")[0]).expanduser().resolve()
    lienzo = cargar_referente(entrada, max_dim_analisis=max_dim_analisis)
    return estudiar_lienzo(
        lienzo,
        num_colores=num_colores,
        k_min=k_min,
        k_max=k_max,
        umbral_de00=umbral_de00,
        ruta_referente=ruta_limpia,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ADN de Diseño (D-11b): extrae estudio.json (CIE Lab + ΔE2000 con K adaptativo 3..10 y confianza continua)."
    )
    parser.add_argument("entrada", help="Ruta al referente (imagen, PDF, vídeo o pieza JSON de recortador).")
    parser.add_argument("-o", "--output", help="Ruta de salida para estudio.json (por defecto stdout).")
    parser.add_argument(
        "-k",
        "--colores",
        type=int,
        default=None,
        help="Fijar K manualmente (por defecto None: usa K adaptativo de 3 a 10 hasta ΔE2000 < 5.0).",
    )
    parser.add_argument("--max-dim", type=int, default=192, help="Dimensión máxima de rejilla de análisis.")
    args = parser.parse_args(argv)

    estudio = estudiar_referente(
        args.entrada,
        num_colores=args.colores,
        max_dim_analisis=args.max_dim,
    )
    texto_json = json.dumps(estudio, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(texto_json, encoding="utf-8")
    else:
        sys.stdout.write(texto_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
