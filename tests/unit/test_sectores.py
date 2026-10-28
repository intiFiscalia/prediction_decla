from decla.conocimiento.sectores import (
    SECTOR_INDETERMINADO,
    cargar_ciiu,
    cargar_expresiones,
    cargar_jerarquia_division_seccion,
    clasificar_sector_explicito,
    clasificar_sector_inferido,
    division_de_codigo,
    elegir_sector_por_similitud,
    seccion_de_codigo,
)

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_cargar_ciiu_real() -> None:
    entradas = cargar_ciiu()
    assert len(entradas) >= 490
    codigos = {e.code for e in entradas}
    assert "0722" in codigos  # extracción de oro, usado en sectores_expresiones.yaml


def test_cargar_jerarquia_cubre_88_divisiones() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    assert len(jerarquia) == 88
    assert jerarquia["01"] == "A"
    assert jerarquia["99"] == "U"


def test_division_y_seccion_de_codigo() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    assert division_de_codigo("6614") == "66"
    assert seccion_de_codigo("6614", jerarquia) == "K"
    assert seccion_de_codigo("0722", jerarquia) == "B"


def test_clasificar_sector_explicito_encuentra_expresion() -> None:
    expresiones = cargar_expresiones()
    jerarquia = cargar_jerarquia_division_seccion()
    resultado = clasificar_sector_explicito(
        "el sujeto operaba una CASA DE CAMBIO en el centro", expresiones, jerarquia
    )
    assert resultado is not None
    assert resultado.code == "6614"
    assert resultado.seccion == "K"
    assert resultado.confianza == 1.0
    assert resultado.texto_evidencia == "CASA DE CAMBIO"


def test_clasificar_sector_explicito_sin_coincidencia_devuelve_none() -> None:
    expresiones = cargar_expresiones()
    jerarquia = cargar_jerarquia_division_seccion()
    resultado = clasificar_sector_explicito(
        "el sujeto transportaba mercancía sin documentos", expresiones, jerarquia
    )
    assert resultado is None


def test_elegir_sector_por_similitud_caso_claro() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    vectores = {"0722": [1.0, 0.0], "4653": [0.1, 0.99], "9900": [-1.0, 0.0]}
    resultado = elegir_sector_por_similitud(
        [0.99, 0.1], vectores, jerarquia, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.code == "0722"
    assert resultado.seccion == "B"


def test_elegir_sector_por_similitud_margen_insuficiente_queda_indeterminado() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    vectores = {"0722": [1.0, 0.0], "4653": [0.999, 0.001]}
    resultado = elegir_sector_por_similitud(
        [1.0, 0.0], vectores, jerarquia, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.code == SECTOR_INDETERMINADO


def test_elegir_sector_por_similitud_confianza_insuficiente_queda_indeterminado() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    vectores = {"0722": [1.0, 0.0], "4653": [-1.0, 0.0]}
    resultado = elegir_sector_por_similitud(
        [0.5, 0.866], vectores, jerarquia, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.code == SECTOR_INDETERMINADO


def test_clasificar_sector_inferido_texto_vacio() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    resultado = clasificar_sector_inferido(
        "", {"0722": [1.0, 0.0]}, MODELO_RAPIDO, jerarquia, 0.85, 0.01
    )
    assert resultado.code is None


def test_clasificar_sector_inferido_extremo_a_extremo_con_modelo_real() -> None:
    jerarquia = cargar_jerarquia_division_seccion()
    from decla.conocimiento.sectores import calcular_vectores_ciiu

    entradas = [
        e
        for e in cargar_ciiu()
        if e.code in {"0722", "0141", "6614", "4731", "9900"}
    ]
    vectores = calcular_vectores_ciiu(entradas, MODELO_RAPIDO)
    resultado = clasificar_sector_inferido(
        "el sujeto extraía oro de forma artesanal en una mina",
        vectores,
        MODELO_RAPIDO,
        jerarquia,
        confianza_minima=0.0,
        margen_minimo_top2=0.0,
    )
    assert resultado.code == "0722"
