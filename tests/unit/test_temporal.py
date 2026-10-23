from pathlib import Path

from decla.calidad.fechas import FORMATO_MDY
from decla.calidad.temporal import (
    calcular_volumen_mensual,
    detectar_puntos_de_cambio,
    resumir_temporal,
)
from decla.ingesta.lectores import leer_csv

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_calcular_volumen_mensual_agrupa_por_mes() -> None:
    fechas = ["1/5/2026", "1/20/2026", "2/1/2026", None, "no es fecha"]
    df = calcular_volumen_mensual(fechas, FORMATO_MDY)
    por_mes = dict(zip(df["mes"].to_list(), df["n_registros"].to_list(), strict=True))
    assert por_mes == {"2026-01": 2, "2026-02": 1}


def test_detectar_puntos_de_cambio_con_salto_claro() -> None:
    serie = [5] * 10 + [50] * 10
    puntos = detectar_puntos_de_cambio(serie)
    assert puntos, "debería detectar el salto de nivel en la mitad de la serie"
    assert any(8 <= p <= 12 for p in puntos)


def test_detectar_puntos_de_cambio_serie_corta_no_falla() -> None:
    assert detectar_puntos_de_cambio([1, 2]) == []


def test_resumir_temporal_marca_no_viable_con_pocos_meses() -> None:
    fechas = ["1/1/2026", "2/1/2026", "3/1/2026"]
    resumen = resumir_temporal(fechas, FORMATO_MDY, umbral_meses_viable=36)
    assert resumen.n_meses_con_datos == 3
    assert resumen.viable_pronostico is False
    assert "condicionado" in resumen.nota_viabilidad


def test_resumir_temporal_marca_viable_con_suficientes_meses() -> None:
    fechas = [f"{(m % 12) + 1}/1/{2020 + m // 12}" for m in range(40)]
    resumen = resumir_temporal(fechas, FORMATO_MDY, umbral_meses_viable=36)
    assert resumen.viable_pronostico is True


def test_resumir_temporal_contra_fixture_real() -> None:
    tabla = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    fechas = [f.get("FECHA_CREACION") for f in tabla.filas]
    resumen = resumir_temporal(fechas, FORMATO_MDY)
    assert resumen.n_meses_con_datos > 0
    assert resumen.periodo_min is not None
    assert resumen.periodo_max is not None
