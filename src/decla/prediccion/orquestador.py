"""Orquestador de detección de atípicos (plan_trabajo.md §8.4, Fase 9; I4, Bloque 4A).

Lee embeddings de relato (media) del lote más reciente en `data/embeddings/<lote_id>/
relato.parquet` — mismo cargador que usa `decla.fenomenos.orquestador`
(`decla.fenomenos.representacion.cargar_embeddings_segmento`, genérico a cualquier parquet con
columnas `registro_uid`/`agregacion`/`vector`, no solo a segmentos).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.fenomenos.representacion import MEDIA, cargar_embeddings_segmento
from decla.prediccion.atipicos import construir_tabla_atipicos


@dataclass(frozen=True)
class ResumenAtipicos:
    n_registros: int
    lote_id_embeddings: str


def procesar_atipicos(
    conexion: duckdb.DuckDBPyConnection,
    lote_id_embeddings: str,
    ruta_embeddings_datos: Path,
    run_id: str,
    semilla: int = 20260101,
) -> ResumenAtipicos:
    ruta_parquet = ruta_embeddings_datos / lote_id_embeddings / "relato.parquet"
    embeddings_por_uid = cargar_embeddings_segmento(ruta_parquet, agregacion=MEDIA)

    filas = construir_tabla_atipicos(conexion, embeddings_por_uid, run_id, semilla)
    escribir_tabla_polars(conexion, "oro", "atipicos", filas)

    return ResumenAtipicos(n_registros=len(filas), lote_id_embeddings=lote_id_embeddings)
