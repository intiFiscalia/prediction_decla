from pathlib import Path

from decla.calidad.categoricas import (
    catalogo_frecuencias,
    faltantes_por_anio_departamento,
    parsear_delito,
)
from decla.ingesta.lectores import leer_csv

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parsear_delito_caso_tipico() -> None:
    resultado = parsear_delito("LAVADO DE ACTIVOS ART. 323 C.P.CUANTIA INFERIOR A 100 SMLM")
    assert resultado.parseable
    assert resultado.nombre == "LAVADO DE ACTIVOS"
    assert resultado.articulo == "323"
    assert resultado.cuantia == "CUANTIA INFERIOR A 100 SMLM"


def test_parsear_delito_con_articulo_compuesto() -> None:
    texto = "FAVORECIMIENTO DE CONTRABANDO ART. 320-1 C.P. CUANTIA INDETERMINADA"
    resultado = parsear_delito(texto)
    assert resultado.parseable
    assert resultado.articulo == "320-1"


def test_parsear_delito_no_coincide_con_patron() -> None:
    resultado = parsear_delito("TEXTO LIBRE SIN FORMATO ESPERADO")
    assert not resultado.parseable
    assert resultado.nombre is None


def test_parsear_delito_vacio() -> None:
    resultado = parsear_delito(None)
    assert not resultado.parseable


def test_catalogo_frecuencias_agrupa_otros_bajo_umbral() -> None:
    valores = ["A"] * 10 + ["B"] * 6 + ["C"] * 2 + ["D"] * 1 + [None] * 3
    resumen = catalogo_frecuencias("COLUMNA", valores, umbral_otros=5)
    assert resumen.n_total == 19
    assert resumen.n_vacios == 3
    assert {e.valor for e in resumen.principales} == {"A", "B"}
    assert resumen.otros_conteo == 3  # 2 de "C" + 1 de "D"
    assert resumen.otros_valores_distintos == 2


def test_faltantes_por_anio_departamento_detecta_concentracion() -> None:
    filas = [
        {"FECHA_CREACION": "1/1/2025", "DEPARTAMENTO": "META", "COL": "x"},
        {"FECHA_CREACION": "1/2/2025", "DEPARTAMENTO": "META", "COL": None},
        {"FECHA_CREACION": "1/1/2026", "DEPARTAMENTO": "CASANARE", "COL": "y"},
    ]
    resultado = faltantes_por_anio_departamento(filas, "COL", "FECHA_CREACION", "DEPARTAMENTO")
    fila_meta = resultado.filter(
        (resultado["_anio"] == "2025") & (resultado["DEPARTAMENTO"] == "META")
    )
    assert fila_meta["n_filas"].item() == 2
    assert fila_meta["n_faltantes"].item() == 1
    assert fila_meta["pct_faltante"].item() == 50.0


def test_categoricas_contra_fixture_real() -> None:
    tabla = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    delitos = [parsear_delito(f.get("DELITO")) for f in tabla.filas]
    assert sum(1 for d in delitos if d.parseable) > 0

    resumen_estado = catalogo_frecuencias("ESTADO", [f.get("ESTADO") for f in tabla.filas])
    assert resumen_estado.n_valores_distintos > 0
