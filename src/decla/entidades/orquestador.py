"""Orquestador de entidades analíticas (plan_trabajo.md Fase 3.4).

Lee `plata.registros_limpios` (ya filtrado por alcance) y `bronce.relatos_raw`, y escribe
`entidades.noticia_criminal`, `entidades.caso`, `entidades.grupo_conexo`, `entidades.relato`,
`entidades.relato_huerfano` y los puentes.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.entidades.noticia import (
    construir_caso,
    construir_grupo_conexo,
    construir_noticia_criminal,
    construir_puente_noticia_delito,
    construir_puente_registro_noticia_caso,
)
from decla.entidades.relato import construir_relato_y_huerfanos


@dataclass
class ResumenEntidades:
    n_noticias: int
    n_casos: int
    n_relatos: int
    n_relatos_huerfanos: int


def construir_entidades(conexion: duckdb.DuckDBPyConnection, lote_id: str) -> ResumenEntidades:
    filas_limpias = conexion.sql("SELECT * FROM plata.registros_limpios").pl().to_dicts()

    noticia_criminal = construir_noticia_criminal(filas_limpias)
    caso = construir_caso(filas_limpias)
    grupo_conexo = construir_grupo_conexo(filas_limpias)
    puente_noticia_delito = construir_puente_noticia_delito(filas_limpias)
    puente_registro_noticia_caso = construir_puente_registro_noticia_caso(filas_limpias)
    relatos, huerfanos = construir_relato_y_huerfanos(conexion, lote_id)

    escribir_tabla_polars(conexion, "entidades", "noticia_criminal", noticia_criminal)
    escribir_tabla_polars(conexion, "entidades", "caso", caso)
    escribir_tabla_polars(conexion, "entidades", "grupo_conexo", grupo_conexo)
    escribir_tabla_polars(conexion, "entidades", "puente_noticia_delito", puente_noticia_delito)
    escribir_tabla_polars(
        conexion, "entidades", "puente_registro_noticia_caso", puente_registro_noticia_caso
    )
    escribir_tabla_polars(conexion, "entidades", "relato", relatos)
    escribir_tabla_polars(conexion, "entidades", "relato_huerfano", huerfanos)

    return ResumenEntidades(
        n_noticias=len(noticia_criminal),
        n_casos=len(caso),
        n_relatos=len(relatos),
        n_relatos_huerfanos=len(huerfanos),
    )
