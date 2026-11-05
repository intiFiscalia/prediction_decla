"""`make lote ARCHIVO=... LOTE_ID=...` (plan_trabajo.md Fase 12; I4, Bloque 4C).

Ingiere un archivo CASOS nuevo como un lote adicional (reusa `decla.ingesta.bronce.
ingerir_tabla`, ya probado), lo valida contra el contrato de esquema, clasifica cada fila por
`CASO_NOTICIA` frente a los lotes ya existentes (nuevo / repetido / modificado, por hash de
contenido — nunca por `registro_uid`, que por diseño cambia entre lotes aunque el contenido sea
idéntico, CLAUDE.md §2.4), guarda la historia de cambios en `meta.historico_cambios` y calcula
deriva (PSI/KS) del volumen, la distribución de `DELITO` y de `DEPARTAMENTO_HECHOS` frente al
histórico.

**No recalcula automáticamente `nlp`/`fenómenos`/`analítica`/`emergencia`** — con un solo lote
real procesado hasta ahora no hay base para diseñar bien qué es "lo dependiente"; queda como
paso manual (ver `docs/manual_operacion.md`). Solo procesa **CASOS** (no RELATOS): es donde
viven los campos que cambian entre lotes (`ESTADO`, `ETAPA`, `ULTIMA_ACTUACION`); el texto de
RELATO rara vez cambia después de registrado.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from decla.comun.deriva import psi_categorico, psi_numerico
from decla.comun.duckdb_io import conectar, escribir_tabla_polars
from decla.ingesta.bronce import ingerir_tabla

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_LOTES_DEFECTO = RAIZ_PROYECTO / "data" / "raw" / "lotes"

NUEVO = "nuevo"
REPETIDO = "repetido"
MODIFICADO = "modificado"

_COLUMNAS_LINAJE = {"registro_uid", "lote_id", "tabla_origen", "n_fila"}

_CREAR_ESQUEMA_META = "CREATE SCHEMA IF NOT EXISTS meta"
_CREAR_TABLA_HISTORICO = """
CREATE TABLE IF NOT EXISTS meta.historico_cambios (
    caso_notica VARCHAR,
    campo VARCHAR,
    valor_anterior VARCHAR,
    valor_nuevo VARCHAR,
    lote_id_nuevo VARCHAR,
    fecha TIMESTAMP
)
"""


def hash_contenido_fila(fila: dict[str, Any]) -> str:
    """Hash del contenido de una fila **sin** las columnas de linaje (`registro_uid`, `lote_id`,
    `tabla_origen`, `n_fila`): dos filas con el mismo contenido en lotes distintos deben dar el
    mismo hash, aunque su `registro_uid` sea distinto por diseño.
    """
    columnas = sorted(c for c in fila if c not in _COLUMNAS_LINAJE)
    contenido = "|".join(f"{c}={fila.get(c) or ''}" for c in columnas)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


@dataclass
class ResumenClasificacion:
    nuevos: list[dict[str, Any]] = field(default_factory=list)
    repetidos: list[dict[str, Any]] = field(default_factory=list)
    modificados: list[dict[str, Any]] = field(default_factory=list)
    cambios: list[dict[str, Any]] = field(default_factory=list)


def clasificar_filas(
    filas_nuevas: list[dict[str, Any]],
    filas_existentes: list[dict[str, Any]],
    lote_id_nuevo: str,
) -> ResumenClasificacion:
    existentes_por_caso: dict[str, dict[str, Any]] = {}
    for fila in filas_existentes:
        caso = fila.get("CASO_NOTICIA")
        if caso:
            existentes_por_caso[caso] = fila  # último lote existente gana si hay varios

    resultado = ResumenClasificacion()
    for fila in filas_nuevas:
        caso = fila.get("CASO_NOTICIA")
        existente = existentes_por_caso.get(caso) if caso else None
        if existente is None:
            resultado.nuevos.append(fila)
            continue
        if hash_contenido_fila(fila) == hash_contenido_fila(existente):
            resultado.repetidos.append(fila)
            continue
        resultado.modificados.append(fila)
        for campo in sorted(set(fila) & set(existente) - _COLUMNAS_LINAJE):
            if fila.get(campo) != existente.get(campo):
                resultado.cambios.append(
                    {
                        "caso_notica": caso,
                        "campo": campo,
                        "valor_anterior": existente.get(campo),
                        "valor_nuevo": fila.get(campo),
                        "lote_id_nuevo": lote_id_nuevo,
                    }
                )
    return resultado


def calcular_deriva_lote(
    filas_nuevas: list[dict[str, Any]], filas_historicas: list[dict[str, Any]]
) -> dict[str, Any]:
    conteo_delito_base: dict[str, int] = {}
    conteo_delito_nuevo: dict[str, int] = {}
    conteo_depto_base: dict[str, int] = {}
    conteo_depto_nuevo: dict[str, int] = {}
    for fila in filas_historicas:
        delito = fila.get("DELITO") or "(vacío)"
        depto = fila.get("DEPARTAMENTO_HECHOS") or "(vacío)"
        conteo_delito_base[delito] = conteo_delito_base.get(delito, 0) + 1
        conteo_depto_base[depto] = conteo_depto_base.get(depto, 0) + 1
    for fila in filas_nuevas:
        delito = fila.get("DELITO") or "(vacío)"
        depto = fila.get("DEPARTAMENTO_HECHOS") or "(vacío)"
        conteo_delito_nuevo[delito] = conteo_delito_nuevo.get(delito, 0) + 1
        conteo_depto_nuevo[depto] = conteo_depto_nuevo.get(depto, 0) + 1

    return {
        "n_historico": len(filas_historicas),
        "n_nuevo": len(filas_nuevas),
        "psi_volumen": psi_numerico([len(filas_historicas)], [len(filas_nuevas)], n_bins=1),
        "psi_delito": psi_categorico(conteo_delito_base, conteo_delito_nuevo),
        "psi_departamento": psi_categorico(conteo_depto_base, conteo_depto_nuevo),
    }


@dataclass
class ResumenLoteOperacion:
    n_nuevos: int
    n_repetidos: int
    n_modificados: int
    n_validas: int
    n_cuarentena: int
    deriva: dict[str, Any]


RUTA_ESQUEMA_DEFECTO = RAIZ_PROYECTO / "config" / "esquema_fuente.yaml"


def procesar_lote(
    conexion: duckdb.DuckDBPyConnection,
    ruta_archivo: Path,
    lote_id_nuevo: str,
    directorio_lotes: Path,
    ruta_esquema: Path = RUTA_ESQUEMA_DEFECTO,
) -> ResumenLoteOperacion:
    from decla.calidad.esquemas import escribir_cuarentena, validar_tabla
    from decla.comun.configuracion import cargar_yaml

    filas_existentes = _consultar_si_existe_bronce(conexion, lote_id_nuevo)

    _copiar_y_registrar(ruta_archivo, lote_id_nuevo, directorio_lotes, conexion)
    df_nuevo = conexion.sql(
        "SELECT * FROM bronce.casos_raw WHERE lote_id = ?", params=[lote_id_nuevo]
    ).pl()
    filas_nuevas = df_nuevo.to_dicts()

    contrato = cargar_yaml(ruta_esquema)
    resultado_validacion = validar_tabla(df_nuevo, "CASOS", contrato, lote_id_nuevo)
    escribir_cuarentena(conexion, resultado_validacion.cuarentena)

    clasificacion = clasificar_filas(filas_nuevas, filas_existentes, lote_id_nuevo)
    _guardar_historico(conexion, clasificacion.cambios)
    deriva = calcular_deriva_lote(filas_nuevas, filas_existentes)

    return ResumenLoteOperacion(
        n_nuevos=len(clasificacion.nuevos),
        n_repetidos=len(clasificacion.repetidos),
        n_modificados=len(clasificacion.modificados),
        n_validas=resultado_validacion.n_validas,
        n_cuarentena=resultado_validacion.n_cuarentena,
        deriva=deriva,
    )


def _consultar_si_existe_bronce(
    conexion: duckdb.DuckDBPyConnection, lote_id_excluir: str
) -> list[dict[str, Any]]:
    try:
        return (
            conexion.sql(
                "SELECT * FROM bronce.casos_raw WHERE lote_id != ?", params=[lote_id_excluir]
            )
            .pl()
            .to_dicts()
        )
    except duckdb.CatalogException:
        return []


def _copiar_y_registrar(
    ruta_archivo: Path, lote_id: str, directorio_lotes: Path, conexion: duckdb.DuckDBPyConnection
) -> Path:
    from decla.ingesta.bronce import copiar_inmutable

    copia = copiar_inmutable(ruta_archivo, directorio_lotes, lote_id)
    ingerir_tabla(copia, "CASOS", lote_id, conexion, "casos_raw")
    return copia


def _guardar_historico(conexion: duckdb.DuckDBPyConnection, cambios: list[dict[str, Any]]) -> None:
    conexion.execute(_CREAR_ESQUEMA_META)
    conexion.execute(_CREAR_TABLA_HISTORICO)
    if not cambios:
        return
    ahora = datetime.now(UTC)
    filas = [{**c, "fecha": ahora} for c in cambios]
    escribir_tabla_polars(conexion, "meta", "historico_cambios", filas, modo="insertar")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--archivo", required=True, type=Path)
    parser.add_argument("--lote-id", required=True)
    parser.add_argument("--directorio-lotes", type=Path, default=RUTA_LOTES_DEFECTO)
    args: Any = parser.parse_args(argv)

    conexion = conectar(args.duckdb, solo_lectura=False)
    try:
        resumen = procesar_lote(conexion, args.archivo, args.lote_id, args.directorio_lotes)
    finally:
        conexion.close()

    print(f"Lote {args.lote_id} procesado")
    print(
        f"  Nuevos: {resumen.n_nuevos}  Repetidos: {resumen.n_repetidos}  "
        f"Modificados: {resumen.n_modificados}"
    )
    print(f"  Válidas: {resumen.n_validas}  Cuarentena: {resumen.n_cuarentena}")
    print(f"  Deriva: {resumen.deriva}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
