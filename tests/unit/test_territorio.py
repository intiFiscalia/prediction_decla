from pathlib import Path

import polars as pl

from decla.calidad.territorio import EntradaDivipola, emparejar_territorio, normalizar_texto

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

DIVIPOLA_PRUEBA = [
    EntradaDivipola("11", "11001", "BOGOTÁ, D.C.", "BOGOTÁ, D.C."),
    EntradaDivipola("50", "50001", "META", "VILLAVICENCIO"),
    EntradaDivipola("05", "05042", "ANTIOQUIA", "SAN LUIS"),
    EntradaDivipola("73", "73411", "TOLIMA", "SAN LUIS"),
]


def test_normalizar_texto_unifica_variantes_de_bogota() -> None:
    assert normalizar_texto("BOGOTÁ, D. C.") == normalizar_texto("Bogota D.C.")
    assert normalizar_texto("BOGOTÁ, D. C.") == normalizar_texto("BOGOTÁ, D.C.")


def test_emparejar_exacto() -> None:
    resultado = emparejar_territorio("META", "VILLAVICENCIO", DIVIPOLA_PRUEBA)
    assert resultado.metodo == "exacto"
    assert resultado.cod_mpio == "50001"
    assert resultado.confianza == 1.0


def test_emparejar_normalizado_por_variante_de_mayusculas_y_tildes() -> None:
    resultado = emparejar_territorio("Meta", "Villavicencio", DIVIPOLA_PRUEBA)
    assert resultado.metodo == "normalizado"
    assert resultado.cod_mpio == "50001"


def test_emparejar_difuso_por_error_de_digitacion() -> None:
    resultado = emparejar_territorio("META", "VILLAVICENCI", DIVIPOLA_PRUEBA, umbral_difuso=80.0)
    assert resultado.metodo == "difuso"
    assert resultado.cod_mpio == "50001"
    assert 0 < resultado.confianza < 1.0


def test_emparejar_no_resoluble_sin_coincidencia() -> None:
    resultado = emparejar_territorio("XYZ", "MUNICIPIO_INEXISTENTE", DIVIPOLA_PRUEBA)
    assert resultado.metodo == "no_resoluble"


def test_emparejar_sin_municipio_es_no_resoluble() -> None:
    resultado = emparejar_territorio("META", None, DIVIPOLA_PRUEBA)
    assert resultado.metodo == "no_resoluble"


def test_homonimo_se_desambigua_con_departamento() -> None:
    resultado_antioquia = emparejar_territorio("ANTIOQUIA", "SAN LUIS", DIVIPOLA_PRUEBA)
    resultado_tolima = emparejar_territorio("TOLIMA", "SAN LUIS", DIVIPOLA_PRUEBA)
    assert resultado_antioquia.cod_mpio == "05042"
    assert resultado_tolima.cod_mpio == "73411"
    assert resultado_antioquia.ambiguo_homonimo is False
    assert resultado_tolima.ambiguo_homonimo is False


def test_homonimo_sin_departamento_queda_no_resoluble_y_marcado() -> None:
    resultado = emparejar_territorio(None, "SAN LUIS", DIVIPOLA_PRUEBA)
    assert resultado.metodo == "no_resoluble"
    assert resultado.ambiguo_homonimo is True


def test_territorio_contra_gazetteer_sintetico_real() -> None:
    divipola_df = pl.read_csv(RAIZ_FIXTURES / "divipola_sintetico.csv", infer_schema_length=0)
    divipola = [
        EntradaDivipola(fila["cod_dpto"], fila["cod_mpio"], fila["departamento"], fila["municipio"])
        for fila in divipola_df.iter_rows(named=True)
    ]
    resultado = emparejar_territorio("meta", "VILLAVICENCIO", divipola)
    assert resultado.metodo in {"exacto", "normalizado"}
    assert resultado.cod_mpio == "50001"

    resultado_homonimo = emparejar_territorio("TOLIMA", "San Luis", divipola)
    assert resultado_homonimo.cod_mpio == "73411"
