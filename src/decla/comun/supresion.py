"""Supresión estadística para todo lo publicado en `reports/agregados/` (CLAUDE.md §2.1): ninguna
celda con conteo menor al umbral puede salir tal cual, para evitar reidentificación.
"""

from __future__ import annotations

import polars as pl

UMBRAL_SUPRESION_DEFECTO = 5
MARCADOR_SUPRIMIDO = "<5"


def suprimir_celdas_bajas(
    df: pl.DataFrame, columnas_conteo: list[str], umbral: int = UMBRAL_SUPRESION_DEFECTO
) -> pl.DataFrame:
    """Reemplaza por `"<{umbral}"` cualquier valor menor al umbral en `columnas_conteo`.

    La columna resultante queda como texto (`Utf8`) porque mezcla números y el marcador de
    supresión; es la forma final para publicar, no para seguir calculando sobre ella.
    """
    marcador = f"<{umbral}"
    expresiones = [
        pl.when(pl.col(columna) < umbral)
        .then(pl.lit(marcador))
        .otherwise(pl.col(columna).cast(pl.Utf8))
        .alias(columna)
        for columna in columnas_conteo
    ]
    return df.with_columns(expresiones)
