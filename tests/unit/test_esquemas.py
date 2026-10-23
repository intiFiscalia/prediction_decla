from pathlib import Path

import polars as pl

from decla.calidad.esquemas import (
    conciliar,
    construir_esquema_pandera,
    escribir_cuarentena,
    validar_tabla,
)
from decla.comun.duckdb_io import conectar
from decla.ingesta.esquema import cargar_contrato

CONTRATO_PRUEBA = {
    "tablas": {
        "X": {
            "columnas": {
                "A": {"obligatoria": True, "tipo_esperado": "identificador"},
                "B": {"obligatoria": False, "tipo_esperado": "texto"},
                "VIEJA": {"obligatoria": False, "tipo_esperado": "texto", "heredada": True},
            }
        }
    }
}


def _df(filas: list[dict]) -> pl.DataFrame:
    columnas = sorted({k for f in filas for k in f})
    return pl.DataFrame(filas, schema={c: pl.Utf8 for c in columnas})


def test_construir_esquema_pandera_omite_columnas_heredadas() -> None:
    esquema = construir_esquema_pandera("X", CONTRATO_PRUEBA)
    assert "VIEJA" not in esquema.columns
    assert "A" in esquema.columns
    assert esquema.columns["A"].required is True
    assert esquema.columns["A"].nullable is False


def test_validar_tabla_todas_validas() -> None:
    df = _df(
        [
            {"registro_uid": "u1", "A": "1", "B": "x"},
            {"registro_uid": "u2", "A": "2", "B": None},
        ]
    )
    resultado = validar_tabla(df, "X", CONTRATO_PRUEBA, lote_id="L1")
    assert resultado.n_entrada == 2
    assert resultado.n_validas == 2
    assert resultado.n_cuarentena == 0
    assert resultado.registros_uid_validos == {"u1", "u2"}


def test_validar_tabla_envia_fila_invalida_a_cuarentena() -> None:
    df = _df(
        [
            {"registro_uid": "u1", "A": "1", "B": "x"},
            {"registro_uid": "u2", "A": None, "B": "y"},  # A es obligatoria
        ]
    )
    resultado = validar_tabla(df, "X", CONTRATO_PRUEBA, lote_id="L1")
    assert resultado.n_entrada == 2
    assert resultado.n_validas == 1
    assert resultado.n_cuarentena == 1
    assert resultado.registros_uid_validos == {"u1"}
    assert resultado.cuarentena[0]["registro_uid"] == "u2"
    assert "esquema_pandera" == resultado.cuarentena[0]["regla"]
    assert conciliar(resultado.n_entrada, resultado.n_validas, resultado.n_cuarentena)


def test_escribir_cuarentena_persiste_en_duckdb(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    cuarentena = [
        {
            "registro_uid": "u2",
            "lote_id": "L1",
            "tabla_origen": "X",
            "regla": "esquema_pandera",
            "motivo": "A vacío",
        }
    ]
    escribir_cuarentena(conexion, cuarentena)
    filas = conexion.execute("SELECT registro_uid, regla FROM plata.cuarentena").fetchall()
    assert filas == [("u2", "esquema_pandera")]
    conexion.close()


def test_escribir_cuarentena_vacia_no_falla(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.duckdb", solo_lectura=False)
    escribir_cuarentena(conexion, [])
    filas = conexion.execute("SELECT count(*) FROM plata.cuarentena").fetchone()[0]
    assert filas == 0
    conexion.close()


def test_conciliar() -> None:
    assert conciliar(10, 8, 2)
    assert not conciliar(10, 7, 2)


def test_validar_tabla_contra_contrato_real_y_fixture() -> None:
    raiz_fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    contrato = cargar_contrato()
    df = pl.read_csv(raiz_fixtures / "casos_sinteticos.csv", infer_schema_length=0)
    df = df.with_columns(pl.Series("registro_uid", [f"u{i}" for i in range(df.height)]))
    resultado = validar_tabla(df, "CASOS", contrato, lote_id="L1")
    assert resultado.n_entrada == df.height
    assert conciliar(resultado.n_entrada, resultado.n_validas, resultado.n_cuarentena)
