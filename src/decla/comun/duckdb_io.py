"""Conexión a DuckDB en modo lectura/escritura o solo lectura.

DuckDB admite un solo proceso escritor (plan_trabajo.md, Fase 2, riesgos): cualquier proceso de
consulta o lectura (la app, por ejemplo) debe abrir la base con `solo_lectura=True`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import polars as pl


def conectar(ruta_bd: Path, solo_lectura: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(ruta_bd), read_only=solo_lectura)


def tabla_existe(conexion: duckdb.DuckDBPyConnection, esquema: str, tabla: str) -> bool:
    resultado = conexion.sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = $esquema AND table_name = $tabla",
        params={"esquema": esquema, "tabla": tabla},
    ).pl()
    return resultado.height > 0


def escribir_tabla_polars(
    conexion: duckdb.DuckDBPyConnection,
    esquema: str,
    nombre_tabla: str,
    filas: list[dict[str, Any]],
    modo: str = "reemplazar",
) -> None:
    """Escribe `filas` (lista de dicts) como tabla de DuckDB vía una `pl.DataFrame` registrada
    temporalmente. `modo="reemplazar"` recrea la tabla; cualquier otro valor hace `INSERT INTO`
    sobre una tabla existente (debe existir).
    """
    conexion.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
    tabla_calificada = f"{esquema}.{nombre_tabla}"
    if not filas:
        if modo == "reemplazar":
            conexion.execute(f"DROP TABLE IF EXISTS {tabla_calificada}")
        return
    df = pl.DataFrame(filas, infer_schema_length=len(filas))
    conexion.register("_tmp_escribir_tabla_df", df)
    if modo == "reemplazar":
        conexion.execute(f"DROP TABLE IF EXISTS {tabla_calificada}")
        conexion.execute(f"CREATE TABLE {tabla_calificada} AS SELECT * FROM _tmp_escribir_tabla_df")
    else:
        conexion.execute(f"INSERT INTO {tabla_calificada} SELECT * FROM _tmp_escribir_tabla_df")
    conexion.unregister("_tmp_escribir_tabla_df")
