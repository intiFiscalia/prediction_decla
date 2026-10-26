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


def ocultar_columnas_derivadas_de_conteo_bajo(
    df: pl.DataFrame,
    columnas_disparadoras: list[str],
    columnas_derivadas: list[str],
    umbral: int = UMBRAL_SUPRESION_DEFECTO,
    marcador: str = "suprimido",
) -> pl.DataFrame:
    """Oculta `columnas_derivadas` (tasas, porcentajes, cocientes) cuando alguna columna en
    `columnas_disparadoras` cae debajo del umbral, en la misma fila.

    `suprimir_celdas_bajas` solo reemplaza el conteo crudo; no basta cuando el mismo reporte
    también publica un valor calculado a partir de ese conteo (p. ej. `tasa_por_100k`), porque
    despejar la fórmula (`tasa_por_100k * poblacion / 100_000`) recupera el conteo exacto y
    anula la supresión (CLAUDE.md §2.1). Debe aplicarse ANTES de `suprimir_celdas_bajas` sobre las
    mismas `columnas_disparadoras`, mientras todavía son numéricas.
    """
    condicion = pl.any_horizontal([pl.col(columna) < umbral for columna in columnas_disparadoras])
    expresiones = [
        pl.when(condicion)
        .then(pl.lit(marcador))
        .otherwise(pl.col(columna).cast(pl.Utf8))
        .alias(columna)
        for columna in columnas_derivadas
    ]
    return df.with_columns(expresiones)
