from decla.prediccion.pronosticos import (
    MINIMO_PERIODOS_ENTRENAMIENTO,
    evaluar_rolling_origin,
    pronostico_ets_tendencia,
    pronostico_ingenuo,
    pronostico_poisson_nb_tendencia,
)


def test_pronostico_ingenuo_repite_el_ultimo_valor() -> None:
    resultado = pronostico_ingenuo([1.0, 2.0, 3.0], horizonte=3)
    assert resultado.calculado is True
    assert resultado.valores_punto == [3.0, 3.0, 3.0]


def test_pronostico_ingenuo_serie_vacia_no_falla() -> None:
    resultado = pronostico_ingenuo([], horizonte=2)
    assert resultado.calculado is False


def test_pronostico_ets_tendencia_requiere_minimo_de_periodos() -> None:
    serie_corta = [1.0, 2.0]
    resultado = pronostico_ets_tendencia(serie_corta, horizonte=2)
    assert resultado.calculado is False
    assert "menos de" in (resultado.motivo or "")


def test_pronostico_ets_tendencia_detecta_tendencia_creciente() -> None:
    serie = [2.0, 3.0, 2.0, 5.0, 4.0, 6.0, 5.0, 8.0, 7.0, 9.0]
    resultado = pronostico_ets_tendencia(serie, horizonte=3)
    assert resultado.calculado is True
    assert resultado.valores_punto is not None
    assert resultado.valores_punto[-1] > serie[-1] * 0.5  # sigue la tendencia, no se derrumba
    assert resultado.intervalo_80 is not None
    assert resultado.intervalo_95 is not None
    # Los intervalos del 95% deben ser al menos tan anchos como los del 80% (ADR 0016: nunca
    # ocultar la incertidumbre real).
    ancho_80 = resultado.intervalo_80[0][1] - resultado.intervalo_80[0][0]
    ancho_95 = resultado.intervalo_95[0][1] - resultado.intervalo_95[0][0]
    assert ancho_95 >= ancho_80


def test_pronostico_poisson_nb_tendencia_serie_en_cero_no_falla() -> None:
    """Mismo problema de frontera encontrado en decla.emergencia.linea_base: Poisson con endog
    todo en cero rompe la IRLS — debe degradarse, no fallar."""
    resultado = pronostico_poisson_nb_tendencia(
        [0.0] * 10, [50.0] * 10, horizonte=2
    )
    assert resultado.calculado is False
    assert "ocurrencia" in (resultado.motivo or "")


def test_pronostico_poisson_nb_tendencia_con_tendencia() -> None:
    serie = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0, 5.0, 5.0]
    volumenes = [20.0] * 10
    resultado = pronostico_poisson_nb_tendencia(serie, volumenes, horizonte=2)
    assert resultado.calculado is True
    assert resultado.valores_punto is not None
    assert len(resultado.valores_punto) == 2
    assert resultado.valores_punto[0] > 0
    assert resultado.intervalo_95 is not None


def test_evaluar_rolling_origin_reporta_n_origenes_esperado() -> None:
    serie = list(range(1, 11))  # 10 periodos, tendencia perfecta
    volumenes = [20.0] * 10
    resultado = evaluar_rolling_origin(
        [float(v) for v in serie], volumenes, "ingenuo", horizonte=1
    )
    assert resultado["calculado"] is True
    # orígenes posibles: MINIMO..n-horizonte -> 10 - 4 = 6 orígenes con horizonte=1
    assert resultado["n_origenes"] == 10 - MINIMO_PERIODOS_ENTRENAMIENTO


def test_evaluar_rolling_origin_serie_muy_corta_no_calcula() -> None:
    resultado = evaluar_rolling_origin([1.0, 2.0], [10.0, 10.0], "ingenuo", horizonte=1)
    assert resultado["calculado"] is False
    assert resultado["n_origenes"] == 0


def test_evaluar_rolling_origin_metodo_con_tendencia_supera_al_ingenuo() -> None:
    """Con una tendencia perfecta sin ruido, un método que sí modela tendencia (ETS) debería
    tener MASE < 1 frente al ingenuo (que solo repite el último valor)."""
    serie = [float(v) for v in range(1, 11)]
    volumenes = [20.0] * 10
    resultado = evaluar_rolling_origin(serie, volumenes, "ets_tendencia", horizonte=1)
    assert resultado["calculado"] is True
    assert resultado["supera_ingenuo"] is True
    assert resultado["mase"] < 1.0
