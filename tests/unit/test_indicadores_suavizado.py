from decla.analitica.indicadores import suavizar_tasa_bayesiano_empirico


def test_suavizado_con_poblacion_grande_se_acerca_a_la_tasa_propia() -> None:
    # Población grande frente al peso del prior: la tasa suavizada se acerca a n/poblacion.
    resultado = suavizar_tasa_bayesiano_empirico(
        n_eventos=100, poblacion=1_000_000, tasa_referencia=0.00005, peso_prior=1_000.0
    )
    tasa_propia = 100 / 1_000_000
    assert resultado is not None
    assert abs(resultado - tasa_propia) < abs(resultado - 0.00005)


def test_suavizado_con_poblacion_pequena_se_acerca_al_prior() -> None:
    # Población pequeña frente al peso del prior: domina la tasa de referencia.
    resultado = suavizar_tasa_bayesiano_empirico(
        n_eventos=1, poblacion=50, tasa_referencia=0.0002, peso_prior=10_000.0
    )
    assert resultado is not None
    assert abs(resultado - 0.0002) < 0.0001


def test_suavizado_sin_poblacion_es_none() -> None:
    assert suavizar_tasa_bayesiano_empirico(1, None, 0.0001) is None
    assert suavizar_tasa_bayesiano_empirico(1, 0, 0.0001) is None


def test_suavizado_sin_tasa_referencia_es_none() -> None:
    assert suavizar_tasa_bayesiano_empirico(1, 1000, None) is None
