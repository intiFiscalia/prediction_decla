"""Ingesta bronce: copia inmutable, hash, carga como texto (CLAUDE.md §2.4, §3.3; Fase 3.1).

Bronce conserva el 100% de lo que llega (incluidas las filas que I1 excluirá por alcance
temático, ADR 0008): ninguna capa modifica a la anterior. Las filas totalmente vacías ya quedan
fuera desde `decla.ingesta.lectores` (se cuentan, no se cargan).
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl

from decla.ingesta.lectores import TablaLeida, leer_tabla, localizar_archivo

_CREAR_ESQUEMA_META = "CREATE SCHEMA IF NOT EXISTS meta"
_CREAR_ESQUEMA_BRONCE = "CREATE SCHEMA IF NOT EXISTS bronce"
_CREAR_TABLA_LOTES = """
CREATE TABLE IF NOT EXISTS meta.lotes (
    lote_id VARCHAR,
    archivo VARCHAR,
    hash_sha256 VARCHAR,
    fecha_ingesta TIMESTAMP,
    n_filas_declaradas INTEGER,
    n_filas_cargadas INTEGER,
    n_filas_vacias INTEGER
)
"""

_COLUMNAS_LINAJE = ("registro_uid", "lote_id", "tabla_origen", "n_fila")


def hash_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def calcular_registro_uid(
    lote_id: str, tabla_origen: str, n_fila: int, fila: dict[str, str | None]
) -> str:
    """`registro_uid` = sha256(lote_id | tabla_origen | n_fila | contenido_fila_normalizado)
    (CLAUDE.md §2.4). El contenido normalizado ordena las columnas para que el hash no dependa
    del orden en que `dict` las entregue.
    """
    contenido = "|".join(f"{columna}={fila.get(columna) or ''}" for columna in sorted(fila))
    cadena = f"{lote_id}|{tabla_origen}|{n_fila}|{contenido}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def copiar_inmutable(ruta_origen: Path, directorio_lotes: Path, lote_id: str) -> Path:
    destino_dir = directorio_lotes / lote_id
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / ruta_origen.name
    shutil.copy2(ruta_origen, destino)
    return destino


@dataclass
class ResumenLote:
    lote_id: str
    archivo: str
    hash_sha256: str
    tabla_destino: str
    n_filas_declaradas: int
    n_filas_cargadas: int
    n_filas_vacias: int


def _tabla_leida_a_dataframe(
    tabla_leida: TablaLeida, lote_id: str, tabla_origen: str
) -> pl.DataFrame:
    filas_con_linaje = [
        {
            "registro_uid": calcular_registro_uid(lote_id, tabla_origen, n_fila, fila),
            "lote_id": lote_id,
            "tabla_origen": tabla_origen,
            "n_fila": n_fila,
            **fila,
        }
        for n_fila, fila in zip(tabla_leida.fila_origen, tabla_leida.filas, strict=True)
    ]
    columnas = [*_COLUMNAS_LINAJE, *tabla_leida.columnas]
    esquema: dict[str, type[pl.DataType]] = dict.fromkeys(columnas, pl.Utf8)
    esquema["n_fila"] = pl.Int64
    if not filas_con_linaje:
        return pl.DataFrame(schema=esquema)
    return pl.DataFrame(filas_con_linaje, schema=esquema)


def ingerir_tabla(
    ruta: Path,
    tabla_origen: str,
    lote_id: str,
    conexion: duckdb.DuckDBPyConnection,
    nombre_tabla_bronce: str,
) -> ResumenLote:
    conexion.execute(_CREAR_ESQUEMA_META)
    conexion.execute(_CREAR_ESQUEMA_BRONCE)
    conexion.execute(_CREAR_TABLA_LOTES)

    tabla_leida = leer_tabla(ruta)
    df = _tabla_leida_a_dataframe(tabla_leida, lote_id, tabla_origen)

    conexion.register("_bronce_df", df)
    tabla_calificada = f"bronce.{nombre_tabla_bronce}"
    fila_conteo = conexion.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'bronce' AND table_name = ?",
        [nombre_tabla_bronce],
    ).fetchone()
    existe = fila_conteo is not None and fila_conteo[0] > 0
    if existe:
        conexion.execute(f"INSERT INTO {tabla_calificada} SELECT * FROM _bronce_df")
    else:
        conexion.execute(f"CREATE TABLE {tabla_calificada} AS SELECT * FROM _bronce_df")
    conexion.unregister("_bronce_df")

    hash_sha256 = hash_archivo(ruta)
    conexion.execute(
        "INSERT INTO meta.lotes VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            lote_id,
            ruta.name,
            hash_sha256,
            datetime.now(UTC),
            tabla_leida.n_filas_total,
            len(tabla_leida.filas),
            tabla_leida.n_filas_vacias,
        ],
    )

    return ResumenLote(
        lote_id=lote_id,
        archivo=ruta.name,
        hash_sha256=hash_sha256,
        tabla_destino=tabla_calificada,
        n_filas_declaradas=tabla_leida.n_filas_total,
        n_filas_cargadas=len(tabla_leida.filas),
        n_filas_vacias=tabla_leida.n_filas_vacias,
    )


def ingerir_lote(
    directorio_entrada: Path,
    directorio_lotes: Path,
    lote_id: str,
    conexion: duckdb.DuckDBPyConnection,
) -> list[ResumenLote]:
    """Localiza CASOS/RELATOS en `directorio_entrada`, los copia de forma inmutable a
    `directorio_lotes/<lote_id>/` y los carga a `bronce.casos_raw`/`bronce.relatos_raw`.
    """
    archivo_casos = localizar_archivo(directorio_entrada, "CASOS")
    archivo_relatos = localizar_archivo(directorio_entrada, "RELATOS")
    if archivo_casos is None:
        raise FileNotFoundError(f"No se encontró un archivo de CASOS en {directorio_entrada}")
    if archivo_relatos is None:
        raise FileNotFoundError(f"No se encontró un archivo de RELATOS en {directorio_entrada}")

    copia_casos = copiar_inmutable(archivo_casos, directorio_lotes, lote_id)
    copia_relatos = copiar_inmutable(archivo_relatos, directorio_lotes, lote_id)

    return [
        ingerir_tabla(copia_casos, "CASOS", lote_id, conexion, "casos_raw"),
        ingerir_tabla(copia_relatos, "RELATOS", lote_id, conexion, "relatos_raw"),
    ]
