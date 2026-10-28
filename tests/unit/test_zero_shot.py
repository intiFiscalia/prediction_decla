from decla.conocimiento.zero_shot import (
    NO_CLASIFICADO,
    cargar_vocabulario,
    clasificar_fragmento,
    elegir_por_similitud,
)

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_cargar_vocabulario_mecanismo_tiene_los_12_fenomenos_plantados() -> None:
    vocabulario = cargar_vocabulario("mecanismo")
    codigos = {d.codigo for d in vocabulario}
    assert len(codigos) == 12
    assert "fraccionamiento_consignaciones" in codigos
    assert "captacion_ilegal" in codigos


def test_cargar_vocabulario_categoria_inexistente_devuelve_vacio() -> None:
    assert cargar_vocabulario("no_existe") == []


def test_elegir_por_similitud_caso_claro() -> None:
    vectores = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [-1.0, 0.0]}
    resultado = elegir_por_similitud(
        [0.99, 0.1], vectores, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.codigo == "a"


def test_elegir_por_similitud_bajo_umbral_queda_no_clasificado() -> None:
    # Vector a 45° de ambos: misma similitud (~0.707) con los dos, por debajo de 0.85.
    vectores = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    resultado = elegir_por_similitud(
        [0.7071, 0.7071], vectores, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.codigo == NO_CLASIFICADO


def test_clasificar_fragmento_vacio() -> None:
    resultado = clasificar_fragmento(
        "", {"a": [1.0, 0.0]}, MODELO_RAPIDO, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.codigo is None


def test_clasificar_fragmento_extremo_a_extremo_con_modelo_real() -> None:
    from decla.conocimiento.zero_shot import calcular_vectores_vocabulario

    vocabulario = cargar_vocabulario("mecanismo")
    vectores = calcular_vectores_vocabulario(vocabulario, MODELO_RAPIDO)
    resultado = clasificar_fragmento(
        "el investigado dividió la consignación en varias transacciones más pequeñas",
        vectores,
        MODELO_RAPIDO,
        confianza_minima=0.0,
        margen_minimo_top2=0.0,
    )
    assert resultado.codigo == "fraccionamiento_consignaciones"
