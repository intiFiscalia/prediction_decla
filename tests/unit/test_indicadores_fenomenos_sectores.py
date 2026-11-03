import duckdb

from decla.analitica.indicadores import ind_fenomenos, ind_sectores
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
