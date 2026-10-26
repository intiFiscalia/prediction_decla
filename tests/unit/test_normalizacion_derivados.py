from datetime import date

from decla.normalizacion.derivados import (
    derivar_componentes_fecha,
    dias_a_prescripcion_declarada,
    dias_entre,
    mismo_dpto_unidad_hechos,
    mismo_mpio,
)


def test_derivar_componentes_fecha() -> None:
    resultado = derivar_componentes_fecha(date(2026, 3, 15))
    assert resultado.anio_iso == 2026
    assert resultado.mes == 3
    assert resultado.semana_iso == 11


def test_derivar_componentes_fecha_none() -> None:
    resultado = derivar_componentes_fecha(None)
    assert resultado.anio_iso is None
    assert resultado.mes is None
    assert resultado.semana_iso is None


def test_dias_entre() -> None:
    assert dias_entre(date(2026, 1, 1), date(2026, 1, 11)) == 10
    assert dias_entre(None, date(2026, 1, 11)) is None
    assert dias_entre(date(2026, 1, 1), None) is None


def test_dias_a_prescripcion_declarada_es_informativo_no_valida_regla() -> None:
    # Diferencia de 5 años (no 20): dias_a_prescripcion_declarada solo informa, no rechaza.
    resultado = dias_a_prescripcion_declarada(date(2020, 1, 1), date(2025, 1, 1))
    assert resultado == 1827


def test_mismo_dpto_unidad_hechos() -> None:
    assert mismo_dpto_unidad_hechos("50", "50") is True
    assert mismo_dpto_unidad_hechos("50", "11") is False
    assert mismo_dpto_unidad_hechos(None, "50") is None


def test_mismo_mpio() -> None:
    assert mismo_mpio("50001", "50001") is True
    assert mismo_mpio("50001", "11001") is False
    assert mismo_mpio(None, None) is None
