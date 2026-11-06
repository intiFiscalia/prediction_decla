from pathlib import Path

import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.prediccion.orquestador import procesar_pronosticos, procesar_pronosticos_delito


def _conexion_con_serie(n_periodos: int = 10) -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    relatos, registros, asignacion = [], [], []
    contador = 0
    for mes in range(1, n_periodos + 1):
        n_mes = mes  # tendencia creciente clara: 1, 2, 3, ...
        for _ in range(n_mes):
            uid, caso = f"uid_{contador}", f"caso_{contador}"
            contador += 1
            relatos.append({"registro_uid": uid, "caso_notica": caso})
            registros.append(
                {
                    "caso_notica": caso, "cod_dpto_hechos": "11",
                    "anio_iso_creacion": 2026, "mes_creacion": mes,
                    "fecha_creacion_valida": True, "delito_nombre": "LAVADO DE ACTIVOS",
                }
            )
            asignacion.append({"registro_uid": uid, "codigo_fenomeno": "lavado_de_activos"})
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    return conexion


def test_procesar_pronosticos_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = _conexion_con_serie()
    resumen = procesar_pronosticos(conexion, run_id="r1", horizonte=3)

    assert resumen.n_series_evaluadas >= 1
    assert resumen.n_filas_escritas > 0

    pronosticos = conexion.sql("SELECT * FROM oro.pronosticos").pl()
    assert pronosticos.height == resumen.n_filas_escritas
    assert set(pronosticos["metodo"].unique().to_list()) >= {"ingenuo"}

    # El ingenuo nunca falla con suficiente historia: debe estar presente para el fenómeno real.
    filas_ingenuo = pronosticos.filter(pronosticos["metodo"] == "ingenuo")
    assert filas_ingenuo.height == 3  # horizonte=3

    # supera_ingenuo solo tiene sentido para métodos no ingenuos con backtest calculado.
    filas_no_ingenuo = pronosticos.filter(pronosticos["metodo"] != "ingenuo")
    if filas_no_ingenuo.height:
        assert filas_no_ingenuo["n_origenes_backtest"].min() >= 0
    conexion.close()


def test_procesar_pronosticos_sin_datos_no_falla() -> None:
    conexion = duckdb.connect(":memory:")
    conexion.execute("CREATE SCHEMA fenomenos")
    conexion.execute(
        "CREATE TABLE fenomenos.asignacion_fenomeno (registro_uid VARCHAR, codigo_fenomeno VARCHAR)"
    )
    resumen = procesar_pronosticos(conexion, run_id="r2")
    assert resumen.n_series_evaluadas == 0
    assert resumen.n_filas_escritas == 0
    conexion.close()


def test_procesar_pronosticos_delito_extremo_a_extremo() -> None:
    conexion = _conexion_con_serie()
    resumen = procesar_pronosticos_delito(conexion, run_id="r3", horizonte=3)

    assert resumen.n_series_evaluadas >= 1
    assert resumen.n_filas_escritas > 0

    pronosticos = conexion.sql("SELECT * FROM oro.pronosticos_delito").pl()
    assert pronosticos.height == resumen.n_filas_escritas
    assert set(pronosticos["delito_nombre"].unique().to_list()) == {"LAVADO DE ACTIVOS"}
    conexion.close()


def test_procesar_pronosticos_delito_sin_datos_no_falla() -> None:
    conexion = duckdb.connect(":memory:")
    conexion.execute("CREATE SCHEMA plata")
    conexion.execute(
        "CREATE TABLE plata.registros_limpios (caso_notica VARCHAR, delito_nombre VARCHAR)"
    )
    resumen = procesar_pronosticos_delito(conexion, run_id="r4")
    assert resumen.n_series_evaluadas == 0
    assert resumen.n_filas_escritas == 0
    conexion.close()
