"""Representación vectorial de relatos para agrupamiento (plan_trabajo.md §7.1 paso 1; Fase 6,
Bloque 2C).

Dos variantes: (a) solo el embedding de `descripcion_hecho_enmascarada` (agregación media,
`data/embeddings/<lote_id>/segmento.parquet`, 2A); (b) ese mismo vector concatenado con un vector
de menciones (conteo por categoría de `texto.menciones`, normalizado por relato). Los metadatos
estructurados (DELITO, territorio, unidad) NUNCA entran aquí: solo describen los grupos después
(`ficha_grupo.py`), nunca los forman (regla explícita de Fase 6 / "no hagas" del skill).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl

MEDIA = "media"


@dataclass(frozen=True)
class MatrizRelatos:
    registros_uid: list[str]
    matriz: np.ndarray


def cargar_embeddings_segmento(
    ruta_parquet: Path, agregacion: str = MEDIA
) -> dict[str, list[float]]:
    df = pl.read_parquet(ruta_parquet).filter(pl.col("agregacion") == agregacion)
    return dict(zip(df["registro_uid"].to_list(), df["vector"].to_list(), strict=True))


def construir_vector_menciones(
    conexion: duckdb.DuckDBPyConnection, categorias: list[str]
) -> dict[str, list[float]]:
    """Un vector por `registro_uid`: proporción de menciones por categoría (en el orden de
    `categorias`), normalizada por el total de menciones del relato — para no confundir "relato
    largo con muchas menciones" con "relato de cierto fenómeno".
    """
    df: pl.DataFrame = conexion.sql(
        "SELECT registro_uid, categoria, count(*) AS n FROM texto.menciones "
        "GROUP BY registro_uid, categoria"
    ).pl()

    por_registro: dict[str, dict[str, int]] = {}
    for fila in df.iter_rows(named=True):
        por_registro.setdefault(fila["registro_uid"], {})[fila["categoria"]] = fila["n"]

    vectores: dict[str, list[float]] = {}
    for registro_uid, conteos in por_registro.items():
        total = sum(conteos.values())
        vectores[registro_uid] = [
            conteos.get(categoria, 0) / total if total else 0.0 for categoria in categorias
        ]
    return vectores


def construir_matriz(
    embeddings_segmento: dict[str, list[float]],
    vector_menciones: dict[str, list[float]] | None = None,
    n_categorias_menciones: int = 0,
) -> MatrizRelatos:
    registros_uid = sorted(embeddings_segmento)
    filas: list[list[float]] = []
    for registro_uid in registros_uid:
        fila: list[Any] = list(embeddings_segmento[registro_uid])
        if vector_menciones is not None:
            fila.extend(vector_menciones.get(registro_uid, [0.0] * n_categorias_menciones))
        filas.append(fila)
    return MatrizRelatos(registros_uid=registros_uid, matriz=np.array(filas))
