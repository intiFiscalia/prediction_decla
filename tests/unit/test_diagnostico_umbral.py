import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.conocimiento.diagnostico_umbral import (
    UMBRALES_CANDIDATOS,
    construir_diagnostico_umbral,
    percentiles_confianza,
    sensibilidad_umbral,
)


def _fila_mencion(categoria: str, origen: str, confianza: float, i: int) -> dict:
    return {
        "registro_uid": f"uid_{categoria}_{i}",
        "categoria": categoria,
        "origen": origen,
        "confianza": confianza,
        "valor_normalizado": None,
    }


def _conexion_con_confianzas() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    filas = (
        # 10 menciones de mecanismo inferidas, confianza de 0.50 a 0.95 en pasos de 0.05.
        [
            _fila_mencion("mecanismo", "inferido_modelo", round(0.50 + 0.05 * i, 2), i)
            for i in range(10)
        ]
        # 3 explícitas (confianza=1.0, no deben contarse en la calibración del modelo).
        + [_fila_mencion("mecanismo", "explicito_regla", 1.0, 100 + i) for i in range(3)]
    )
    escribir_tabla_polars(conexion, "texto", "menciones", filas)
    return conexion


def test_percentiles_confianza_excluye_explicitas() -> None:
    conexion = _conexion_con_confianzas()
    df = percentiles_confianza(conexion, "mecanismo")
    fila = df.row(0, named=True)
    assert fila["n_inferido"] == 10  # no cuenta las 3 explícitas
    assert fila["p50"] > 0
    conexion.close()


def test_percentiles_confianza_categoria_sin_datos_no_falla() -> None:
    conexion = _conexion_con_confianzas()
    df = percentiles_confianza(conexion, "sector")
    assert df.row(0, named=True)["n_inferido"] == 0
    conexion.close()


def test_sensibilidad_umbral_cuenta_cuantas_pasarian_por_umbral() -> None:
    conexion = _conexion_con_confianzas()
    df = sensibilidad_umbral(conexion, "mecanismo", umbrales=[0.5, 0.85])
    por_umbral = dict(
        zip(df["umbral_candidato"].to_list(), df["n_pasaria"].to_list(), strict=True)
    )
    # confianzas: 0.50, 0.55, ..., 0.95 (10 valores). Con 0.5 pasan las 10; con 0.85 pasan 3
    # (0.85/0.90/0.95), pero queda suprimido por ser < 5 (CLAUDE.md §2.1).
    assert por_umbral[0.5] == "10"
    assert por_umbral[0.85] == "<5"
    conexion.close()


def test_construir_diagnostico_umbral_devuelve_ambas_tablas() -> None:
    conexion = _conexion_con_confianzas()
    percentiles, sensibilidad = construir_diagnostico_umbral(conexion, categorias=["mecanismo"])
    assert percentiles.height == 1
    assert sensibilidad.height == len(UMBRALES_CANDIDATOS)
    conexion.close()
