from decla.emergencia.detectores import (
    cusum,
    ears_c,
    farrington_simplificado,
    puntos_de_cambio,
    razon_de_tasas,
)


def test_cusum_detecta_aumento_sostenido() -> None:
    residuos = [0.0, 0.1, -0.1, 0.0, 3.0, 3.0, 3.0, 3.0]
    resultado = cusum(residuos, k=0.5, h=4.0)
    assert resultado["en_alerta"] is True
    assert resultado["periodo_alerta"] is not None
    assert resultado["periodo_alerta"] >= 4


def test_cusum_sin_senal_no_entra_en_alerta() -> None:
    residuos = [0.0, 0.1, -0.2, 0.1, -0.1, 0.0]
    resultado = cusum(residuos, k=0.5, h=4.0)
    assert resultado["en_alerta"] is False
    assert resultado["periodo_alerta"] is None


def test_ears_c_requiere_mas_periodos_que_la_ventana() -> None:
    resultado = ears_c([1, 2, 3], ventana_base=3)
    assert resultado["calculado"] is False


def test_ears_c_detecta_pico_claro() -> None:
    conteos = [5, 5, 4, 5, 30]  # pico muy por encima de la ventana base [5,4,5]
    resultado = ears_c(conteos, ventana_base=3)
    assert resultado["calculado"] is True
    assert resultado["en_alerta"] is True


def test_farrington_simplificado_requiere_minimo_periodos() -> None:
    resultado = farrington_simplificado([1.0, 1.0], [1.0, 1.0])
    assert resultado["calculado"] is False


def test_farrington_simplificado_detecta_exceso() -> None:
    esperado = [2.0, 2.1, 2.0, 2.2, 2.0]
    observado = [2.0, 2.0, 2.0, 2.0, 20.0]
    resultado = farrington_simplificado(esperado, observado)
    assert resultado["calculado"] is True
    assert resultado["en_alerta"] is True


def test_farrington_simplificado_sin_exceso_no_alerta() -> None:
    esperado = [2.0, 2.1, 2.0, 2.2, 2.0]
    observado = [2.0, 2.0, 2.0, 2.0, 2.1]
    resultado = farrington_simplificado(esperado, observado)
    assert resultado["calculado"] is True
    assert resultado["en_alerta"] is False


def test_puntos_de_cambio_corta_serie_con_salto_claro() -> None:
    serie = [1, 1, 1, 1, 1, 10, 10, 10, 10, 10]
    puntos = puntos_de_cambio(serie, penalidad=1.0)
    assert len(puntos) >= 1
    assert any(3 <= p <= 6 for p in puntos)


def test_puntos_de_cambio_serie_corta_devuelve_vacio() -> None:
    assert puntos_de_cambio([1, 2]) == []


def test_razon_de_tasas_detecta_aumento() -> None:
    resultado = razon_de_tasas(n_reciente=20, periodos_reciente=1, n_base=5, periodos_base=4)
    assert resultado["calculado"] is True
    assert resultado["razon_de_tasas"] > 1.0
    assert resultado["ic_95"][0] <= resultado["razon_de_tasas"] <= resultado["ic_95"][1]


def test_razon_de_tasas_sin_datos_base() -> None:
    resultado = razon_de_tasas(n_reciente=5, periodos_reciente=1, n_base=0, periodos_base=2)
    assert resultado["calculado"] is False
