import polars as pl

from decla.comun.supresion import suprimir_celdas_bajas


def test_suprimir_celdas_bajas_reemplaza_valores_pequenos() -> None:
    df = pl.DataFrame({"territorio": ["A", "B", "C"], "conteo": [2, 10, 4]})
    resultado = suprimir_celdas_bajas(df, columnas_conteo=["conteo"], umbral=5)
    assert resultado["conteo"].to_list() == ["<5", "10", "<5"]


def test_suprimir_celdas_bajas_no_afecta_columnas_no_listadas() -> None:
    df = pl.DataFrame({"territorio": ["A"], "conteo": [3]})
    resultado = suprimir_celdas_bajas(df, columnas_conteo=["conteo"])
    assert resultado["territorio"].to_list() == ["A"]
