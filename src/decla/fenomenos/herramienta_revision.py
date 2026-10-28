"""Herramienta de revisión de grupos descubiertos — taller de taxonomía (plan_trabajo.md §7.2;
Fase 6, Bloque 2C). Un analista aprueba, renombra, fusiona, divide, marca como artefacto o
descarta cada grupo de la ficha automática; la decisión se guarda en
`revision.decisiones_taxonomia` (DuckDB, escritura real — no concurrente con
`make etl/nlp/conocimiento/fenomenos`, mismo límite de un solo escritor de DuckDB,
`decla.comun.duckdb_io`).

También implementa la prueba de intrusión (plan §7.2): 5 relatos de un grupo + 1 "intruso" de
otro grupo, mezclados; si el revisor identifica el intruso, el grupo es internamente coherente.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb

APROBAR = "aprobar"
RENOMBRAR = "renombrar"
FUSIONAR = "fusionar"
DIVIDIR = "dividir"
ARTEFACTO = "artefacto"
DESCARTAR = "descartar"

_CREAR_ESQUEMA = "CREATE SCHEMA IF NOT EXISTS revision"
_CREAR_TABLA_DECISIONES = """
CREATE TABLE IF NOT EXISTS revision.decisiones_taxonomia (
    grupo_id VARCHAR,
    decision VARCHAR,
    nombre_nuevo VARCHAR,
    grupo_fusion_destino VARCHAR,
    calificador VARCHAR,
    fecha TIMESTAMP
)
"""
_CREAR_TABLA_INTRUSION = """
CREATE TABLE IF NOT EXISTS revision.resultados_intrusion (
    grupo_id VARCHAR,
    acierto BOOLEAN,
    calificador VARCHAR,
    fecha TIMESTAMP
)
"""


def guardar_decision(
    conexion: duckdb.DuckDBPyConnection,
    grupo_id: str,
    decision: str,
    calificador: str,
    nombre_nuevo: str | None = None,
    grupo_fusion_destino: str | None = None,
) -> None:
    conexion.execute(_CREAR_ESQUEMA)
    conexion.execute(_CREAR_TABLA_DECISIONES)
    conexion.execute(
        "INSERT INTO revision.decisiones_taxonomia VALUES (?, ?, ?, ?, ?, ?)",
        [grupo_id, decision, nombre_nuevo, grupo_fusion_destino, calificador, datetime.now(UTC)],
    )


def cargar_decisiones(conexion: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    conexion.execute(_CREAR_ESQUEMA)
    conexion.execute(_CREAR_TABLA_DECISIONES)
    return conexion.sql("SELECT * FROM revision.decisiones_taxonomia").pl().to_dicts()


@dataclass(frozen=True)
class CasoIntrusion:
    grupo_id: str
    registros_uid_mostrados: list[str]
    indice_intruso: int


def generar_caso_intrusion(
    grupo_id: str,
    registros_del_grupo: list[str],
    registros_de_otro_grupo: list[str],
    semilla: int,
    n_del_grupo: int = 5,
) -> CasoIntrusion | None:
    """`None` si no hay suficientes relatos para armar el caso (grupo muy chico, o no hay otro
    grupo del que tomar el intruso) — no se fuerza una prueba sin sentido.
    """
    if len(registros_del_grupo) < n_del_grupo or not registros_de_otro_grupo:
        return None
    rng = random.Random(semilla)
    elegidos = rng.sample(registros_del_grupo, n_del_grupo)
    intruso = rng.choice(registros_de_otro_grupo)
    mostrados = [*elegidos, intruso]
    rng.shuffle(mostrados)
    return CasoIntrusion(grupo_id, mostrados, mostrados.index(intruso))


def registrar_resultado_intrusion(
    conexion: duckdb.DuckDBPyConnection, grupo_id: str, acierto: bool, calificador: str
) -> None:
    conexion.execute(_CREAR_ESQUEMA)
    conexion.execute(_CREAR_TABLA_INTRUSION)
    conexion.execute(
        "INSERT INTO revision.resultados_intrusion VALUES (?, ?, ?, ?)",
        [grupo_id, acierto, calificador, datetime.now(UTC)],
    )


def cargar_resultados_intrusion(conexion: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    conexion.execute(_CREAR_ESQUEMA)
    conexion.execute(_CREAR_TABLA_INTRUSION)
    return conexion.sql("SELECT * FROM revision.resultados_intrusion").pl().to_dicts()


def calcular_tasa_intrusion(resultados: list[dict[str, object]]) -> float:
    if not resultados:
        return 0.0
    aciertos = sum(1 for r in resultados if r["acierto"])
    return round(aciertos / len(resultados), 4)
