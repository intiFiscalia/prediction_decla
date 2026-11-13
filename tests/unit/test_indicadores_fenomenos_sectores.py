import duckdb

from decla.analitica.indicadores import (
    ind_delito_dentro_de_fenomeno,
    ind_fenomenos,
    ind_mecanismo,
    ind_mecanismo_dentro_de_fenomeno,
    ind_sector_dentro_de_fenomeno,
    ind_sectores,
    ranking_tendencia_delito,
)
from decla.comun.duckdb_io import escribir_tabla_polars


def _conexion_con_fenomenos() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    # Universo: 4 relatos procesados; uid_4 no tiene ningún fenómeno asignado (no_clasificado).
    escribir_tabla_polars(
        conexion,
        "texto",
        "relato_procesado",
        [{"registro_uid": f"uid_{i}"} for i in range(1, 5)],
    )
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [
            {"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_2", "codigo_fenomeno": "lavado_de_activos"},
            # uid_1 también cae en otro código (particiones distintas, ver asignacion.py).
            {"registro_uid": "uid_1", "codigo_fenomeno": "organizacion_criminal"},
            {"registro_uid": "uid_3", "codigo_fenomeno": "organizacion_criminal"},
        ],
    )
    return conexion


def test_ind_fenomenos_participacion_contra_total_no_contra_suma() -> None:
    conexion = _conexion_con_fenomenos()
    df = ind_fenomenos(conexion)
    por_codigo = dict(zip(df["codigo_fenomeno"].to_list(), df["n_noticias"].to_list(), strict=True))

    assert por_codigo["lavado_de_activos"] == 2
    assert por_codigo["organizacion_criminal"] == 2
    assert por_codigo["(no_clasificado)"] == 1  # uid_4

    # 2 + 2 + 1 = 5 > 4 relatos del universo: el solape (uid_1 en dos códigos) es esperado.
    assert df["n_noticias"].sum() == 5

    pct = dict(zip(df["codigo_fenomeno"].to_list(), df["pct_participacion"].to_list(), strict=True))
    assert pct["lavado_de_activos"] == 50.0  # 2/4, no 2/5
    assert pct["(no_clasificado)"] == 25.0  # 1/4
    conexion.close()


def test_ind_fenomenos_sin_relatos_no_clasificados() -> None:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion, "texto", "relato_procesado", [{"registro_uid": "uid_1"}]
    )
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [{"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"}],
    )
    df = ind_fenomenos(conexion)
    assert "(no_clasificado)" not in df["codigo_fenomeno"].to_list()
    conexion.close()


def _conexion_con_menciones_sector() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "texto",
        "menciones",
        [
            {
                "registro_uid": "uid_1",
                "categoria": "sector",
                "origen": "explicito_regla",
                "valor_normalizado": "4661",
                "polaridad": "afirmada",
            },
            {
                "registro_uid": "uid_2",
                "categoria": "sector",
                "origen": "inferido_modelo",
                "valor_normalizado": "0142",
                "polaridad": "afirmada",
            },
            {
                "registro_uid": "uid_3",
                "categoria": "sector",
                "origen": "inferido_modelo",
                "valor_normalizado": "indeterminado",
                "polaridad": "afirmada",
            },
            {
                "registro_uid": "uid_4",
                "categoria": "sector",
                "origen": "inferido_modelo",
                "valor_normalizado": None,
                "polaridad": "afirmada",
            },
            # Mención de otra categoría: no debe contarse en ind_sectores.
            {
                "registro_uid": "uid_5",
                "categoria": "mecanismo",
                "origen": "inferido_modelo",
                "valor_normalizado": "fraccionamiento",
                "polaridad": "afirmada",
            },
            # Negada: excluida por defecto aunque fuera "sector" (CLAUDE.md §2.3, §6.4).
            {
                "registro_uid": "uid_6",
                "categoria": "sector",
                "origen": "explicito_regla",
                "valor_normalizado": "4661",
                "polaridad": "negada",
            },
        ],
    )
    return conexion


def test_ind_sectores_tres_columnas_separadas_sin_negadas() -> None:
    conexion = _conexion_con_menciones_sector()
    df = ind_sectores(conexion)
    n_por_categoria = dict(zip(df["categoria_sector"].to_list(), df["n"].to_list(), strict=True))

    assert n_por_categoria["explicito"] == 1
    assert n_por_categoria["inferido_alta_confianza"] == 1
    assert n_por_categoria["indeterminado"] == 2  # valor_normalizado='indeterminado' y NULL
    assert sum(n_por_categoria.values()) == 4  # uid_5 (mecanismo) y uid_6 (negada) excluidos
    assert abs(df["pct"].sum() - 100.0) < 0.01
    conexion.close()


def _conexion_delito_dentro_de_fenomeno() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "texto",
        "relato_procesado",
        [{"registro_uid": f"uid_{i}", "caso_notica": f"caso_{i}"} for i in range(1, 4)],
    )
    escribir_tabla_polars(
        conexion,
        "plata",
        "registros_limpios",
        [
            {"caso_notica": "caso_1", "delito_nombre": "LAVADO DE ACTIVOS", "articulo_cp": "323"},
            {
                "caso_notica": "caso_2",
                "delito_nombre": "ENRIQUECIMIENTO ILICITO",
                "articulo_cp": "412",
            },
            {"caso_notica": "caso_3", "delito_nombre": "LAVADO DE ACTIVOS", "articulo_cp": "323"},
        ],
    )
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [
            {"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_2", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_3", "codigo_fenomeno": "organizacion_criminal"},
        ],
    )
    return conexion


def test_ind_delito_dentro_de_fenomeno_distingue_delitos_del_mismo_fenomeno() -> None:
    conexion = _conexion_delito_dentro_de_fenomeno()
    df = ind_delito_dentro_de_fenomeno(conexion, "lavado_de_activos")
    por_delito = dict(zip(df["delito_nombre"].to_list(), df["n"].to_list(), strict=True))

    # Solo uid_1 y uid_2 están en lavado_de_activos; uid_3 (también LAVADO DE ACTIVOS) queda
    # fuera porque está asignado a organizacion_criminal, no a lavado_de_activos.
    assert por_delito == {"LAVADO DE ACTIVOS": 1, "ENRIQUECIMIENTO ILICITO": 1}
    conexion.close()


def test_ind_sector_dentro_de_fenomeno_usa_valor_no_origen() -> None:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [
            {"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_2", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_3", "codigo_fenomeno": "organizacion_criminal"},
        ],
    )
    escribir_tabla_polars(
        conexion,
        "texto",
        "menciones",
        [
            {
                "registro_uid": "uid_1", "categoria": "sector", "origen": "explicito_regla",
                "valor_normalizado": "financiero", "polaridad": "afirmada",
            },
            {
                "registro_uid": "uid_2", "categoria": "sector", "origen": "inferido_modelo",
                "valor_normalizado": "indeterminado", "polaridad": "afirmada",
            },
            # Mismo sector/fenómeno que uid_1, pero en otro fenómeno: no debe contarse aquí.
            {
                "registro_uid": "uid_3", "categoria": "sector", "origen": "explicito_regla",
                "valor_normalizado": "financiero", "polaridad": "afirmada",
            },
        ],
    )
    df = ind_sector_dentro_de_fenomeno(conexion, "lavado_de_activos")
    por_sector = dict(zip(df["sector"].to_list(), df["n"].to_list(), strict=True))
    assert por_sector == {"financiero": 1, "indeterminado": 1}
    conexion.close()


def _conexion_con_mecanismo() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [
            {"registro_uid": "uid_1", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_2", "codigo_fenomeno": "lavado_de_activos"},
            {"registro_uid": "uid_3", "codigo_fenomeno": "organizacion_criminal"},
        ],
    )
    escribir_tabla_polars(
        conexion,
        "texto",
        "menciones",
        [
            {
                "registro_uid": "uid_1", "categoria": "mecanismo", "polaridad": "afirmada",
                "valor_normalizado": "compra_ganado",
            },
            {
                "registro_uid": "uid_2", "categoria": "mecanismo", "polaridad": "afirmada",
                "valor_normalizado": None,
            },
            # Mismo mecanismo, pero en otro fenómeno: no debe contarse en la versión "dentro de".
            {
                "registro_uid": "uid_3", "categoria": "mecanismo", "polaridad": "afirmada",
                "valor_normalizado": "compra_ganado",
            },
        ],
    )
    return conexion


def test_ind_mecanismo_incluye_no_clasificado() -> None:
    conexion = _conexion_con_mecanismo()
    df = ind_mecanismo(conexion)
    por_mecanismo = dict(zip(df["mecanismo"].to_list(), df["n"].to_list(), strict=True))
    assert por_mecanismo == {"compra_ganado": 2, "no_clasificado": 1}
    conexion.close()


def test_ind_mecanismo_dentro_de_fenomeno_filtra_por_fenomeno() -> None:
    conexion = _conexion_con_mecanismo()
    df = ind_mecanismo_dentro_de_fenomeno(conexion, "lavado_de_activos")
    por_mecanismo = dict(zip(df["mecanismo"].to_list(), df["n"].to_list(), strict=True))
    assert por_mecanismo == {"compra_ganado": 1, "no_clasificado": 1}
    conexion.close()


def _fila_pronostico(delito: str, territorio: str, metodo: str, **extra: object) -> dict:
    base = {
        "delito_nombre": delito, "territorio": territorio, "periodo_pronosticado": 24324,
        "metodo": metodo, "valor_punto": 1.0, "intervalo_80_inf": None, "intervalo_80_sup": None,
        "intervalo_95_inf": None, "intervalo_95_sup": None, "mase_backtest": None,
        "wape_backtest": None, "n_origenes_backtest": 0, "supera_ingenuo": None,
        "fecha_corte": 24323, "run_id": "r1",
    }
    base.update(extra)
    return base


def test_ranking_tendencia_delito_solo_reporta_series_que_superan_el_ingenuo() -> None:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "oro",
        "pronosticos_delito",
        [
            _fila_pronostico("LAVADO DE ACTIVOS", "11", "ingenuo", valor_punto=10.0),
            _fila_pronostico(
                "LAVADO DE ACTIVOS", "11", "ets_tendencia", valor_punto=20.0,
                supera_ingenuo=True, mase_backtest=0.5,
            ),
            # Otro delito también con tendencia pero sin superar el ingenuo: no debe aparecer.
            _fila_pronostico("ENRIQUECIMIENTO ILICITO", "11", "ingenuo", valor_punto=5.0),
            _fila_pronostico(
                "ENRIQUECIMIENTO ILICITO", "11", "ets_tendencia", valor_punto=8.0,
                supera_ingenuo=False, mase_backtest=1.2,
            ),
        ],
    )
    df = ranking_tendencia_delito(conexion)
    assert df.height == 1
    fila = df.row(0, named=True)
    assert fila["delito_nombre"] == "LAVADO DE ACTIVOS"
    assert fila["variacion_pct_vs_ingenuo"] == 100.0  # (20-10)/10*100
    conexion.close()


def test_ranking_tendencia_delito_sin_tabla_no_falla() -> None:
    # `oro.pronosticos_delito` todavía no existe (`make prediccion` no ha corrido, o no escribió
    # filas): escribir_tabla_polars con lista vacía deja la tabla inexistente a propósito.
    conexion = duckdb.connect(":memory:")
    df = ranking_tendencia_delito(conexion)
    assert df.height == 0
    conexion.close()
