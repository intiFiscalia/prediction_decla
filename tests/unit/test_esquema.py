from pathlib import Path

from decla.ingesta.esquema import cargar_contrato, comparar_esquema
from decla.ingesta.lectores import TablaLeida, leer_csv

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _tabla(columnas: list[str], filas: list[dict]) -> TablaLeida:
    return TablaLeida(
        nombre="prueba",
        columnas=columnas,
        filas=filas,
        fila_origen=list(range(2, 2 + len(filas))),
        n_filas_total=len(filas),
        n_filas_vacias=0,
    )


def test_contrato_real_carga_y_declara_eje_tematico_sin_fusionar() -> None:
    contrato = cargar_contrato()
    columnas_casos = contrato["tablas"]["CASOS"]["columnas"]
    assert "Eje temático APLICA" in columnas_casos
    assert "EJE_TEMATICO" in columnas_casos
    assert columnas_casos["EJE_TEMATICO"].get("heredada") is True


def test_comparar_esquema_contra_fixture_casos_no_reporta_columnas_nuevas() -> None:
    contrato = cargar_contrato()
    tabla = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    resultado = comparar_esquema(tabla, "CASOS", contrato)
    assert resultado.columnas_nuevas == []
    assert resultado.columnas_esperadas_faltantes == []


def test_comparar_esquema_detecta_columna_faltante_y_nueva() -> None:
    contrato = {
        "tablas": {
            "X": {
                "columnas": {
                    "A": {"obligatoria": True, "tipo_esperado": "numerico"},
                    "B": {"obligatoria": True, "tipo_esperado": "texto"},
                }
            }
        }
    }
    tabla = _tabla(["A", "C"], [{"A": "1", "C": "x"}])
    resultado = comparar_esquema(tabla, "X", contrato)
    assert resultado.columnas_esperadas_faltantes == ["B"]
    assert resultado.columnas_nuevas == ["C"]


def test_comparar_esquema_no_reporta_faltante_si_es_heredada() -> None:
    contrato = {
        "tablas": {
            "X": {
                "columnas": {
                    "A": {"obligatoria": True, "tipo_esperado": "numerico"},
                    "VIEJA": {"obligatoria": False, "tipo_esperado": "texto", "heredada": True},
                }
            }
        }
    }
    tabla = _tabla(["A"], [{"A": "1"}])
    resultado = comparar_esquema(tabla, "X", contrato)
    assert resultado.columnas_esperadas_faltantes == []


def test_inferir_tipo_numerico_fecha_texto_mixto_vacio() -> None:
    contrato = {
        "tablas": {
            "X": {
                "columnas": {
                    "NUM": {"tipo_esperado": "numerico"},
                    "FECHA": {"tipo_esperado": "fecha"},
                    "TEXTO": {"tipo_esperado": "texto"},
                    "MIXTA": {"tipo_esperado": "desconocido"},
                    "VACIA": {"tipo_esperado": "desconocido"},
                }
            }
        }
    }
    filas = [
        {"NUM": "1", "FECHA": "10/8/2026", "TEXTO": "ACTIVO", "MIXTA": "1", "VACIA": None},
        {"NUM": "2.0", "FECHA": "1/1/2026", "TEXTO": "INACTIVO", "MIXTA": "x", "VACIA": None},
    ]
    tabla = _tabla(["NUM", "FECHA", "TEXTO", "MIXTA", "VACIA"], filas)
    resultado = comparar_esquema(tabla, "X", contrato)
    por_columna = {r.columna: r.tipo_observado for r in resultado.resultados}
    assert por_columna["NUM"] == "numerico"
    assert por_columna["FECHA"] == "fecha"
    assert por_columna["TEXTO"] == "texto"
    assert por_columna["MIXTA"] == "mixto"
    assert por_columna["VACIA"] == "vacio"
