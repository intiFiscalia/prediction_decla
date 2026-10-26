import polars as pl

from decla.comun.supresion import ocultar_columnas_derivadas_de_conteo_bajo, suprimir_celdas_bajas


def test_suprimir_celdas_bajas_reemplaza_valores_pequenos() -> None:
    df = pl.DataFrame({"territorio": ["A", "B", "C"], "conteo": [2, 10, 4]})
    resultado = suprimir_celdas_bajas(df, columnas_conteo=["conteo"], umbral=5)
    assert resultado["conteo"].to_list() == ["<5", "10", "<5"]


def test_suprimir_celdas_bajas_no_afecta_columnas_no_listadas() -> None:
    df = pl.DataFrame({"territorio": ["A"], "conteo": [3]})
    resultado = suprimir_celdas_bajas(df, columnas_conteo=["conteo"])
    assert resultado["territorio"].to_list() == ["A"]


def test_ocultar_columnas_derivadas_evita_recuperar_el_conteo_suprimido() -> None:
    # Caso real (reports/agregados/i1/territorio_tasa.csv): n_registros=1 (sería "<5") pero
    # tasa_por_100k/poblacion permitían despejar n_registros = tasa * poblacion / 100_000 = 1.
    df = pl.DataFrame(
        {
            "n_registros": [1, 21],
            "poblacion_total": [20322.0, 2_526_795.0],
            "tasa_por_100k": [4.920775514221041, 0.8310923521694479],
        }
    )
    oculto = ocultar_columnas_derivadas_de_conteo_bajo(
        df, columnas_disparadoras=["n_registros"], columnas_derivadas=["tasa_por_100k"]
    )
    suprimido = suprimir_celdas_bajas(oculto, columnas_conteo=["n_registros"])

    assert suprimido["n_registros"].to_list() == ["<5", "21"]
    assert suprimido["tasa_por_100k"].to_list() == ["suprimido", "0.8310923521694479"]
    # La fórmula ya no puede despejar n_registros: el valor es texto, no el número original.
    assert "4.920775514221041" not in suprimido["tasa_por_100k"].to_list()


def test_ocultar_columnas_derivadas_dispara_con_cualquier_columna_disparadora() -> None:
    df = pl.DataFrame(
        {
            "n_registros": [10],
            "n_registros_anio_anterior": [3],
            "variacion_interanual_pct": [233.3],
        }
    )
    resultado = ocultar_columnas_derivadas_de_conteo_bajo(
        df,
        columnas_disparadoras=["n_registros", "n_registros_anio_anterior"],
        columnas_derivadas=["variacion_interanual_pct"],
    )
    assert resultado["variacion_interanual_pct"].to_list() == ["suprimido"]


def test_ocultar_columnas_derivadas_no_afecta_filas_sobre_el_umbral() -> None:
    df = pl.DataFrame({"n": [10], "pct": [100.0]})
    resultado = ocultar_columnas_derivadas_de_conteo_bajo(
        df, columnas_disparadoras=["n"], columnas_derivadas=["pct"]
    )
    assert resultado["pct"].to_list() == ["100.0"]
