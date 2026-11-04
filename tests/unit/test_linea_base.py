import duckdb
import polars as pl

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.emergencia.linea_base import ajustar_linea_base, construir_series_fenomeno_territorio


def _conexion_serie() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    relatos, registros, asignacion = [], [], []
    # 6 periodos (2026-01 a 2026-06), un territorio, con 2 relatos/mes del fenómeno "x" y 10 del
    # "y" (volumen total del territorio = 12/mes).
    for mes in range(1, 7):
        for i in range(2):
            uid = f"uid_x_{mes}_{i}"
            caso = f"caso_x_{mes}_{i}"
            relatos.append({"registro_uid": uid, "caso_notica": caso})
            registros.append(
                {
                    "caso_notica": caso, "cod_dpto_hechos": "11",
                    "anio_iso_creacion": 2026, "mes_creacion": mes, "fecha_creacion_valida": True,
                }
            )
            asignacion.append({"registro_uid": uid, "codigo_fenomeno": "x"})
        for i in range(10):
            uid = f"uid_y_{mes}_{i}"
            caso = f"caso_y_{mes}_{i}"
            relatos.append({"registro_uid": uid, "caso_notica": caso})
            registros.append(
                {
                    "caso_notica": caso, "cod_dpto_hechos": "11",
                    "anio_iso_creacion": 2026, "mes_creacion": mes, "fecha_creacion_valida": True,
                }
            )
            asignacion.append({"registro_uid": uid, "codigo_fenomeno": "y"})
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    return conexion


def test_construir_series_incluye_periodos_con_cero() -> None:
    conexion = _conexion_serie()
    series = construir_series_fenomeno_territorio(conexion)
    serie_x = series.filter(pl.col("codigo_fenomeno") == "x")
    assert serie_x.height == 6  # un valor por mes, aunque todos tengan n>0 en este fixture
    assert serie_x["n"].to_list() == [2] * 6
    assert serie_x["volumen_total"].to_list() == [12] * 6
    conexion.close()


def test_construir_series_rellena_con_cero_si_falta_el_fenomeno_en_un_periodo() -> None:
    conexion = _conexion_serie()
    # Quita todas las filas de "x" de enero reasignándolas a "y" (simula que x no tuvo casos).
    conexion.execute(
        "UPDATE fenomenos.asignacion_fenomeno SET codigo_fenomeno = 'y' "
        "WHERE registro_uid LIKE 'uid_x_1_%'"
    )
    series = construir_series_fenomeno_territorio(conexion)
    serie_x = series.filter(pl.col("codigo_fenomeno") == "x").sort("indice_periodo")
    assert serie_x.height == 6
    assert serie_x["n"].to_list()[0] == 0  # enero quedó en 0, no se omitió la fila
    conexion.close()


def test_ajustar_linea_base_requiere_minimo_de_periodos() -> None:
    serie_corta = pl.DataFrame(
        {"indice_periodo": [1, 2], "n": [1, 2], "volumen_total": [10, 10]}
    )
    resultado = ajustar_linea_base(serie_corta)
    assert resultado["calculado"] is False


def test_ajustar_linea_base_detecta_tendencia_creciente() -> None:
    serie = pl.DataFrame(
        {
            "indice_periodo": list(range(6)),
            "n": [1, 1, 2, 3, 5, 8],
            "volumen_total": [10] * 6,
        }
    )
    resultado = ajustar_linea_base(serie)
    assert resultado["calculado"] is True
    assert resultado["metodo"] in {"poisson", "binomial_negativa"}
    assert len(resultado["n_esperado"]) == 6
    # El último valor esperado debería ser mayor que el primero (tendencia positiva).
    assert resultado["n_esperado"][-1] > resultado["n_esperado"][0]
