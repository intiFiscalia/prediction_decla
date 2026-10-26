"""Prueba de idempotencia (CLAUDE.md §2.4): la misma entrada produce el mismo hash de datos en
dos corridas completas e independientes del ETL (excluyendo run_id, que cambia por diseño en
cada ejecución).
"""

import hashlib
from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.ingesta.pipeline import ejecutar_etl

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

TABLAS_A_COMPARAR = [
    ("bronce.casos_raw", []),
    ("bronce.relatos_raw", []),
    ("plata.registros_limpios", ["run_id"]),
    ("plata.dim_territorio", []),
    ("plata.dim_tiempo", []),
    ("plata.dim_despacho", []),
    ("plata.dim_delito", []),
    ("entidades.noticia_criminal", []),
    ("entidades.caso", []),
    ("entidades.grupo_conexo", []),
    ("entidades.relato", []),
    ("entidades.relato_huerfano", []),
]


def _hash_tabla(conexion, tabla: str, excluir_columnas: list[str]) -> str:
    columnas_df = conexion.sql(f"DESCRIBE {tabla}").pl()
    columnas = [c for c in columnas_df["column_name"].to_list() if c not in excluir_columnas]
    columnas_sql = ", ".join(f'"{c}"' for c in columnas)
    filas = conexion.sql(f"SELECT {columnas_sql} FROM {tabla} ORDER BY {columnas_sql}").pl()
    return hashlib.sha256(filas.write_csv().encode("utf-8")).hexdigest()


def test_etl_es_idempotente_entre_corridas_independientes(tmp_path: Path) -> None:
    # La misma clave HMAC en ambas corridas: de otro modo numero_documento_token/
    # fiscal_asignado_token diferirían aunque todo lo demás sea idéntico.
    clave_compartida = tmp_path / "claves_compartidas" / "hmac.key"

    ejecutar_etl(
        RAIZ_FIXTURES, tmp_path / "a" / "lotes", tmp_path / "a" / "warehouse.duckdb",
        "LOTE_IDEMPOTENCIA", clave_compartida,
    )
    ejecutar_etl(
        RAIZ_FIXTURES, tmp_path / "b" / "lotes", tmp_path / "b" / "warehouse.duckdb",
        "LOTE_IDEMPOTENCIA", clave_compartida,
    )

    con_a = conectar(tmp_path / "a" / "warehouse.duckdb", solo_lectura=True)
    con_b = conectar(tmp_path / "b" / "warehouse.duckdb", solo_lectura=True)

    for tabla, excluir in TABLAS_A_COMPARAR:
        hash_a = _hash_tabla(con_a, tabla, excluir)
        hash_b = _hash_tabla(con_b, tabla, excluir)
        assert hash_a == hash_b, f"{tabla} no es idéntica entre corridas (excluyendo {excluir})"

    con_a.close()
    con_b.close()
