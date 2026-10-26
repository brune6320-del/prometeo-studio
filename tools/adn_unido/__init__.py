"""ADN Unido (Fase 4 · D-10 + D-11b): Ficha unificada de ADN tipográfico y ADN de diseño."""

from .esquema import (
    COMMIT_ADN_DISENO,
    COMMIT_ADN_TIPO,
    SCHEMA_VERSION_ADN_DISENO,
    SCHEMA_VERSION_ADN_TIPO,
    SCHEMA_VERSION_UNIDO,
    calcular_sha256_ficha_sin_fecha,
    validar_ficha_unida,
)
from .estudiar_todo import estudiar_carpeta, estudiar_pieza_unida

__all__ = [
    "COMMIT_ADN_DISENO",
    "COMMIT_ADN_TIPO",
    "SCHEMA_VERSION_ADN_DISENO",
    "SCHEMA_VERSION_ADN_TIPO",
    "SCHEMA_VERSION_UNIDO",
    "calcular_sha256_ficha_sin_fecha",
    "estudiar_carpeta",
    "estudiar_pieza_unida",
    "validar_ficha_unida",
]
