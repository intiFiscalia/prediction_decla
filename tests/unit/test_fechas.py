from datetime import date
from pathlib import Path

from decla.calidad.fechas import (
    FORMATO_AMBIGUO,
    FORMATO_DMY,
    FORMATO_MDY,
    detectar_formato_fecha,
    evaluar_columna_fecha,
    parsear_fecha,
    verificar_orden_logico,
    verificar_prescripcion,
)
from decla.ingesta.lectores import leer_csv

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_detectar_formato_mdy_por_segunda_posicion() -> None:
    # "10/8/2026" con 8 en la segunda posición no decide nada (<=12); se necesita un valor que
    # pruebe el formato: "3/25/2026" -> 25 en segunda posición => solo puede ser M/D/AAAA.
    formato, confianza = detectar_formato_fecha(["10/8/2026", "3/25/2026"])
    assert formato == FORMATO_MDY
    assert confianza > 0


def test_detectar_formato_dmy_por_primera_posicion() -> None:
    formato, confianza = detectar_formato_fecha(["25/3/2026", "02/09/2026"])
    assert formato == FORMATO_DMY
    assert confianza > 0


def test_detectar_formato_ambiguo_sin_evidencia() -> None:
    formato, confianza = detectar_formato_fecha(["10/8/2026", "1/1/2026"])
    assert formato == FORMATO_AMBIGUO
    assert confianza == 0.0


def test_detectar_formato_ambiguo_con_evidencia_contradictoria() -> None:
    # Un valor prueba D/M (25 en 1ª posición) y otro prueba M/D (25 en 2ª posición): la columna
    # mezcla formatos o tiene errores; no se debe forzar ninguno de los dos.
    formato, _ = detectar_formato_fecha(["25/3/2026", "3/25/2026"])
    assert formato == FORMATO_AMBIGUO


def test_parsear_fecha_mdy_y_dmy() -> None:
    assert parsear_fecha("3/25/2026", FORMATO_MDY) == date(2026, 3, 25)
    assert parsear_fecha("25/3/2026", FORMATO_DMY) == date(2026, 3, 25)


def test_parsear_fecha_invalida_devuelve_none() -> None:
    assert parsear_fecha("13/15/2026", FORMATO_MDY) is None
    assert parsear_fecha("no es fecha", FORMATO_MDY) is None
    assert parsear_fecha(None, FORMATO_MDY) is None


def test_evaluar_columna_fecha_cuenta_invalidas_y_futuras() -> None:
    # "2/30/2026" aporta evidencia de M/D/AAAA (30 en 2ª posición) sin contradecir a las demás,
    # pero como fecha (30 de febrero) es inválida: separa evidencia de formato de validez.
    valores = ["3/25/2026", "2/30/2026", "1/1/1900", None, "3/1/2099"]
    resumen = evaluar_columna_fecha(
        "FECHA_HECHO", valores, hoy=date(2026, 10, 23), valores_invalidos_conocidos={"1/1/1900"}
    )
    assert resumen.formato_detectado == FORMATO_MDY
    assert resumen.n_total == 4
    assert resumen.n_invalidas == 1  # "2/30/2026" (30 de febrero no existe)
    assert resumen.n_valores_invalidos_conocidos == 1  # "1/1/1900" es válida pero sentinel
    assert resumen.n_futuras == 1


def test_verificar_orden_logico_detecta_violacion() -> None:
    filas = [
        {"A": "1/1/2026", "B": "1/5/2026"},  # ok
        {"A": "1/10/2026", "B": "1/5/2026"},  # violación: A > B
        {"A": None, "B": "1/5/2026"},  # no comparable
    ]
    resumen = verificar_orden_logico(filas, "A", "B", {"A": FORMATO_MDY, "B": FORMATO_MDY})
    assert resumen.n_comparables == 2
    assert resumen.n_violaciones == 1
    assert resumen.pct_violaciones == 50.0


def test_verificar_prescripcion_regla_cumplida_y_desviacion() -> None:
    filas = [
        {"HECHO": "1/1/2006", "PRESCRIPCION": "1/1/2026"},  # +20 años exacto
        {"HECHO": "1/1/2006", "PRESCRIPCION": "1/1/2020"},  # +14 años, no cumple
    ]
    formatos = {"HECHO": FORMATO_MDY, "PRESCRIPCION": FORMATO_MDY}
    resumen = verificar_prescripcion(filas, "HECHO", "PRESCRIPCION", anios=20, formatos=formatos)
    assert resumen.n_comparables == 2
    assert resumen.n_cumple_regla == 1
    assert resumen.pct_cumple_regla == 50.0


def test_fechas_contra_fixture_real_produce_resumen_plausible() -> None:
    tabla = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    valores = [f.get("FECHA_HECHO") for f in tabla.filas]
    conocidos = {"1/1/1900", "0/0/0000"}
    resumen = evaluar_columna_fecha(
        "FECHA_HECHO", valores, hoy=date(2026, 10, 23), valores_invalidos_conocidos=conocidos
    )
    assert resumen.formato_detectado in {FORMATO_MDY, FORMATO_DMY, FORMATO_AMBIGUO}
    assert resumen.n_total > 0
    assert resumen.n_invalidas >= 0
