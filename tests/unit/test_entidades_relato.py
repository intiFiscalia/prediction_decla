from pathlib import Path

import polars as pl

from decla.comun.duckdb_io import conectar, escribir_tabla_polars
from decla.entidades.relato import construir_relato_y_huerfanos


def _preparar(conexion, filas_plata: list[dict], filas_relatos_raw: list[dict]) -> None:
    escribir_tabla_polars(conexion, "plata", "registros_limpios", filas_plata)
    conexion.execute("CREATE SCHEMA IF NOT EXISTS bronce")
    df = pl.DataFrame(filas_relatos_raw)
    conexion.register("_tmp", df)
    conexion.execute("CREATE TABLE bronce.relatos_raw AS SELECT * FROM _tmp")
    conexion.unregister("_tmp")


def test_relato_coincidente_va_a_relato(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    _preparar(
        conexion,
        filas_plata=[{"caso_notica": "N1"}],
        filas_relatos_raw=[
            {"registro_uid": "r1", "lote_id": "L1", "CASO_NOTICIA": "N1", "RELATO": "texto normal"}
        ],
    )
    relatos, huerfanos = construir_relato_y_huerfanos(conexion, "L1")
    assert len(relatos) == 1
    assert len(huerfanos) == 0
    assert relatos[0]["relato"] == "texto normal"
    conexion.close()


def test_relato_sin_noticia_valida_va_a_huerfano(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    _preparar(
        conexion,
        filas_plata=[{"caso_notica": "N1"}],
        filas_relatos_raw=[
            {"registro_uid": "r1", "lote_id": "L1", "CASO_NOTICIA": "N_HUERFANA", "RELATO": "texto"}
        ],
    )
    relatos, huerfanos = construir_relato_y_huerfanos(conexion, "L1")
    assert len(relatos) == 0
    assert len(huerfanos) == 1
    assert huerfanos[0]["caso_notica"] == "N_HUERFANA"
    conexion.close()


def test_relato_con_sufijo_punto_cero_se_limpia_antes_de_comparar(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    _preparar(
        conexion,
        filas_plata=[{"caso_notica": "123"}],
        filas_relatos_raw=[
            {"registro_uid": "r1", "lote_id": "L1", "CASO_NOTICIA": "123.0", "RELATO": "texto"}
        ],
    )
    relatos, huerfanos = construir_relato_y_huerfanos(conexion, "L1")
    assert len(relatos) == 1
    assert len(huerfanos) == 0
    conexion.close()


def test_relato_repara_mojibake(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    original = "El señor José Núñez"
    corrupto = original.encode("cp1252", errors="replace").decode("cp1251", errors="replace")
    _preparar(
        conexion,
        filas_plata=[{"caso_notica": "N1"}],
        filas_relatos_raw=[
            {"registro_uid": "r1", "lote_id": "L1", "CASO_NOTICIA": "N1", "RELATO": corrupto}
        ],
    )
    relatos, _ = construir_relato_y_huerfanos(conexion, "L1")
    assert relatos[0]["relato"] == original
    assert relatos[0]["reparacion_codificacion"] is True
    conexion.close()


def test_relato_filtra_por_lote(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    _preparar(
        conexion,
        filas_plata=[{"caso_notica": "N1"}],
        filas_relatos_raw=[
            {"registro_uid": "r1", "lote_id": "L1", "CASO_NOTICIA": "N1", "RELATO": "lote 1"},
            {"registro_uid": "r2", "lote_id": "L2", "CASO_NOTICIA": "N1", "RELATO": "lote 2"},
        ],
    )
    relatos, _ = construir_relato_y_huerfanos(conexion, "L1")
    assert len(relatos) == 1
    assert relatos[0]["relato"] == "lote 1"
    conexion.close()
