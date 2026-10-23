from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.comun.ejecucion import RegistroEjecucion


def test_registro_ejecucion_escribe_meta_ejecuciones(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)

    with RegistroEjecucion(conexion, paso="prueba", parametros={"semilla": 42}) as reg:
        run_id = reg.run_id

    filas = conexion.execute(
        "SELECT run_id, paso, estado FROM meta.ejecuciones WHERE run_id = ?", [run_id]
    ).fetchall()
    conexion.close()

    assert filas == [(run_id, "prueba", "ok")]


def test_registro_ejecucion_registra_error(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)

    run_id = None
    try:
        with RegistroEjecucion(conexion, paso="prueba_error") as reg:
            run_id = reg.run_id
            raise ValueError("falla simulada")
    except ValueError:
        pass

    estado = conexion.execute(
        "SELECT estado FROM meta.ejecuciones WHERE run_id = ?", [run_id]
    ).fetchone()[0]
    conexion.close()

    assert estado == "error"
