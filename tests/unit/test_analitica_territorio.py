import duckdb
import numpy as np

from decla.analitica.territorio import (
    TAMANIO_MINIMO_PREDOMINIO,
    agrupar_perfiles_territoriales,
    calcular_moran,
    dispersion_puntos_por_fenomeno,
    distancia_hellinger,
    matriz_distancia_hellinger,
    matriz_perfil_territorial,
    predominio_territorial,
    resumen_calidad_puntos,
)
from decla.comun.duckdb_io import escribir_tabla_polars


def _conexion_territorio() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    # 3 relatos en dpto "05" (2x lavado_de_activos, 1x organizacion_criminal, tamaño < mínimo),
    # 6 relatos en dpto "11" (5x lavado_de_activos, 1x organizacion_criminal, >= mínimo).
    relatos = [
        {"registro_uid": f"uid_{i}", "caso_notica": f"caso_{i}"} for i in range(1, 10)
    ]
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)

    registros = [
        {
            "caso_notica": "caso_1", "cod_dpto_hechos": "05", "cod_mpio_hechos": "05001",
            "lat_hechos": 6.25, "long_hechos": -75.56, "calidad_coord_hechos": "exacta",
        },
        {
            "caso_notica": "caso_2", "cod_dpto_hechos": "05", "cod_mpio_hechos": "05001",
            "lat_hechos": 6.26, "long_hechos": -75.57, "calidad_coord_hechos": "exacta",
        },
        {
            "caso_notica": "caso_3", "cod_dpto_hechos": "05", "cod_mpio_hechos": "05001",
            "lat_hechos": None, "long_hechos": None, "calidad_coord_hechos": "faltante",
        },
    ] + [
        {
            "caso_notica": f"caso_{i}", "cod_dpto_hechos": "11", "cod_mpio_hechos": "11001",
            "lat_hechos": 4.6 + i * 0.001, "long_hechos": -74.08, "calidad_coord_hechos": "exacta",
        }
        for i in range(4, 10)
    ]
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)

    asignacion = [
        {"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_2", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_3", "codigo_fenomeno": "organizacion_criminal"},
        {"registro_uid": "uid_4", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_5", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_6", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_7", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_8", "codigo_fenomeno": "lavado_de_activos"},
        {"registro_uid": "uid_9", "codigo_fenomeno": "organizacion_criminal"},
    ]
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    return conexion


def test_distancia_hellinger_identicos_es_cero() -> None:
    p = np.array([0.5, 0.5])
    assert distancia_hellinger(p, p) == 0.0


def test_distancia_hellinger_disjuntos_es_uno() -> None:
    p = np.array([1.0, 0.0])
    q = np.array([0.0, 1.0])
    assert abs(distancia_hellinger(p, q) - 1.0) < 1e-9


def test_matriz_perfil_territorial_normaliza_a_proporciones() -> None:
    conexion = _conexion_territorio()
    perfil = matriz_perfil_territorial(conexion)
    assert perfil.height == 2  # dptos "05" y "11"
    columnas_fenomeno = [c for c in perfil.columns if c != "cod_dpto_hechos"]
    for fila in perfil.iter_rows(named=True):
        assert abs(sum(fila[c] for c in columnas_fenomeno) - 1.0) < 1e-9
    conexion.close()


def test_agrupar_perfiles_territoriales_devuelve_una_etiqueta_por_territorio() -> None:
    conexion = _conexion_territorio()
    perfil = matriz_perfil_territorial(conexion)
    territorios, distancias = matriz_distancia_hellinger(perfil, "cod_dpto_hechos")
    etiquetas = agrupar_perfiles_territoriales(territorios, distancias, n_grupos=2)
    assert set(etiquetas) == set(territorios)
    conexion.close()


def test_predominio_territorial_respeta_tamanio_minimo() -> None:
    conexion = _conexion_territorio()
    df = predominio_territorial(conexion)
    fila_05 = df.filter(df["cod_dpto_hechos"] == "05").row(0, named=True)
    fila_11 = df.filter(df["cod_dpto_hechos"] == "11").row(0, named=True)

    assert fila_05["n_total"] == 3 < TAMANIO_MINIMO_PREDOMINIO
    assert fila_05["cumple_tamanio_minimo"] is False
    assert fila_05.get("fenomeno_predominante") is None

    assert fila_11["cumple_tamanio_minimo"] is True
    assert fila_11["fenomeno_predominante"] == "lavado_de_activos"
    assert fila_11["n_predominante"] == 5
    assert fila_11["p_valor_supera_segundo"] < 0.5  # 5 contra 1, debería ganar claramente
    conexion.close()


def test_resumen_calidad_puntos_suma_100() -> None:
    conexion = _conexion_territorio()
    df = resumen_calidad_puntos(conexion)
    assert abs(df["pct"].sum() - 100.0) < 0.01
    conexion.close()


def test_dispersion_puntos_por_fenomeno_excluye_coordenadas_no_exactas() -> None:
    conexion = _conexion_territorio()
    df = dispersion_puntos_por_fenomeno(conexion)
    n_por_fenomeno = dict(
        zip(df["codigo_fenomeno"].to_list(), df["n_puntos_validos"].to_list(), strict=True)
    )
    # uid_3 (organizacion_criminal, dpto 05) tiene calidad_coord_hechos='faltante': se excluye.
    assert n_por_fenomeno["organizacion_criminal"] == 1  # solo uid_9
    assert n_por_fenomeno["lavado_de_activos"] == 7
    conexion.close()


def test_calcular_moran_insuficiente_cobertura_con_pocos_datos() -> None:
    conexion = _conexion_territorio()
    resultado = calcular_moran(conexion, "lavado_de_activos", nivel="departamento")
    assert resultado["calculado"] is False
    assert resultado["motivo"] == "cobertura insuficiente"
    assert "n_unidades_con_datos" in resultado
    conexion.close()


def test_calcular_moran_nivel_invalido_lanza_error() -> None:
    conexion = _conexion_territorio()
    try:
        calcular_moran(conexion, "lavado_de_activos", nivel="pais")
        raise AssertionError("debió lanzar ValueError")
    except ValueError:
        pass
    conexion.close()
