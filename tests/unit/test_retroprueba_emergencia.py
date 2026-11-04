from decla.emergencia.retroprueba import ejecutar_retroprueba


def test_retroprueba_tasa_de_falsas_alarmas_cercana_al_fdr_nominal() -> None:
    """Sin incremento real, la tasa de falsas alarmas debería acercarse al `fdr_maximo` nominal
    (no exactamente, porque el p-valor de Poisson es discreto y conservador con conteos bajos,
    pero sí del mismo orden de magnitud, no 10× más alto).
    """
    resultado = ejecutar_retroprueba(n_series=300, fdr_maximo=0.10, semilla=1)
    assert resultado.tasa_falsas_alarmas <= 0.20


def test_retroprueba_sensibilidad_alta_con_incremento_fuerte() -> None:
    resultado = ejecutar_retroprueba(n_series=300, factor_incremento=5.0, semilla=2)
    assert resultado.sensibilidad > 0.5
    assert resultado.sensibilidad > resultado.tasa_falsas_alarmas


def test_retroprueba_sensibilidad_crece_con_el_factor_de_incremento() -> None:
    debil = ejecutar_retroprueba(n_series=300, factor_incremento=1.5, semilla=3)
    fuerte = ejecutar_retroprueba(n_series=300, factor_incremento=8.0, semilla=3)
    assert fuerte.sensibilidad >= debil.sensibilidad


def test_retroprueba_tiempo_a_deteccion_es_un_numero_acotado() -> None:
    """El tiempo a detección puede ser negativo (detección "temprana" por azar en un corte
    anterior al inicio real del incremento — no hay corrección por pruebas secuenciales en el
    barrido de cortes, igual que en la vigilancia real sin ajuste de "peeking"), pero debe
    quedar acotado por el largo de la serie, no ser un valor sin sentido.
    """
    resultado = ejecutar_retroprueba(n_series=300, n_periodos=10, factor_incremento=6.0, semilla=4)
    if resultado.tiempo_a_deteccion_medio is not None:
        assert -10 <= resultado.tiempo_a_deteccion_medio <= 10


def test_retroprueba_es_reproducible_con_la_misma_semilla() -> None:
    a = ejecutar_retroprueba(n_series=100, semilla=42)
    b = ejecutar_retroprueba(n_series=100, semilla=42)
    assert a == b
