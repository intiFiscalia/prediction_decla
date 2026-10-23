"""Validación de esquema con Pandera y cuarentena (CLAUDE.md §2.4; plan_trabajo.md Fase 3.2).

Las filas que no cumplen el contrato de `config/esquema_fuente.yaml` (columnas obligatorias
presentes y no vacías) van a `plata.cuarentena` con la regla y el motivo; **nunca se descartan**.
La conciliación exige `n_entrada = n_validas + n_cuarentena`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import pandera.polars as pa
import polars as pl

_CREAR_ESQUEMA_PLATA = "CREATE SCHEMA IF NOT EXISTS plata"
_CREAR_TABLA_CUARENTENA = """
CREATE TABLE IF NOT EXISTS plata.cuarentena (
    registro_uid VARCHAR,
    lote_id VARCHAR,
    tabla_origen VARCHAR,
    regla VARCHAR,
    motivo VARCHAR
)
"""


def construir_esquema_pandera(nombre_tabla: str, contrato: dict) -> pa.DataFrameSchema:
    """Esquema mínimo desde el contrato: columnas obligatorias no nulas. Las reglas de
    contenido fino (21 dígitos de CASO_NOTICIA, formato de fecha, etc.) son de
    `decla.normalizacion`, no de esta validación estructural.
    """
    columnas_contrato = contrato.get("tablas", {}).get(nombre_tabla, {}).get("columnas", {})
    columnas = {}
    for nombre, meta in columnas_contrato.items():
        if meta.get("heredada"):
            continue
        obligatoria = bool(meta.get("obligatoria", False))
        columnas[nombre] = pa.Column(str, nullable=not obligatoria, required=obligatoria)
    return pa.DataFrameSchema(columnas, strict=False, coerce=False)


@dataclass
class ResultadoValidacion:
    n_entrada: int
    n_validas: int
    n_cuarentena: int
    registros_uid_validos: set[str] = field(default_factory=set)
    cuarentena: list[dict[str, str | None]] = field(default_factory=list)


def validar_tabla(
    df: pl.DataFrame, nombre_tabla: str, contrato: dict, lote_id: str
) -> ResultadoValidacion:
    esquema = construir_esquema_pandera(nombre_tabla, contrato)
    uids = df["registro_uid"].to_list()

    try:
        esquema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        fallos = exc.failure_cases
        uids_fallidos: dict[str, list[str]] = {}
        for fila in fallos.iter_rows(named=True):
            idx = fila["index"]
            uid = uids[idx] if idx is not None else "desconocido"
            motivo = f"columna={fila['column']}, valor={fila['failure_case']!r}"
            uids_fallidos.setdefault(uid, []).append(f"{fila['check']} ({motivo})")

        cuarentena: list[dict[str, str | None]] = [
            {
                "registro_uid": uid,
                "lote_id": lote_id,
                "tabla_origen": nombre_tabla,
                "regla": "esquema_pandera",
                "motivo": "; ".join(motivos),
            }
            for uid, motivos in uids_fallidos.items()
        ]
        uids_validos = set(uids) - set(uids_fallidos)
        return ResultadoValidacion(
            n_entrada=df.height,
            n_validas=len(uids_validos),
            n_cuarentena=len(uids_fallidos),
            registros_uid_validos=uids_validos,
            cuarentena=cuarentena,
        )

    return ResultadoValidacion(
        n_entrada=df.height,
        n_validas=df.height,
        n_cuarentena=0,
        registros_uid_validos=set(uids),
        cuarentena=[],
    )


def escribir_cuarentena(
    conexion: duckdb.DuckDBPyConnection, cuarentena: list[dict[str, str | None]]
) -> None:
    conexion.execute(_CREAR_ESQUEMA_PLATA)
    conexion.execute(_CREAR_TABLA_CUARENTENA)
    if not cuarentena:
        return
    df = pl.DataFrame(cuarentena)
    conexion.register("_cuarentena_df", df)
    conexion.execute("INSERT INTO plata.cuarentena SELECT * FROM _cuarentena_df")
    conexion.unregister("_cuarentena_df")


def conciliar(n_entrada: int, n_validas: int, n_cuarentena: int) -> bool:
    """Verifica `n_entrada = n_validas + n_cuarentena` (CLAUDE.md Fase 3, criterio de cierre)."""
    return n_entrada == n_validas + n_cuarentena
