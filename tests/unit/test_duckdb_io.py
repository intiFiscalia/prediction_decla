from pathlib import Path

import duckdb
import pytest

from decla.comun.duckdb_io import conectar


def test_conectar_solo_lectura_impide_escritura(tmp_path: Path) -> None:
    ruta_bd = tmp_path / "prueba.duckdb"
    con_escritura = conectar(ruta_bd, solo_lectura=False)
    con_escritura.execute("CREATE TABLE t (x INTEGER)")
    con_escritura.close()

    con_lectura = conectar(ruta_bd, solo_lectura=True)
    try:
        with pytest.raises(duckdb.Error):
            con_lectura.execute("INSERT INTO t VALUES (1)")
    finally:
        con_lectura.close()
