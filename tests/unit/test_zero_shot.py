from decla.conocimiento.zero_shot import (
    NO_CLASIFICADO,
    cargar_expresiones_mecanismo,
    cargar_vocabulario,
    clasificar_fragmento,
    clasificar_mecanismo_explicito,
    elegir_mejor_fragmento,
    elegir_por_similitud,
)
from decla.texto.embeddings import FragmentoEmbedding

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_cargar_vocabulario_mecanismo_tiene_los_12_fenomenos_plantados_mas_excepciones() -> None:
    vocabulario = cargar_vocabulario("mecanismo")
    codigos = {d.codigo for d in vocabulario}
    assert len(codigos) == 15
    assert "fraccionamiento_consignaciones" in codigos
    assert "captacion_ilegal" in codigos
    assert "lavado_activos_sin_detalle" in codigos
    assert "transporte_de_divisas" in codigos
    assert "transporte_de_oro" in codigos


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


def test_elegir_mejor_fragmento_sin_fragmentos_devuelve_no_clasificado() -> None:
    resultado = elegir_mejor_fragmento(
        [], {"a": [1.0, 0.0], "b": [0.0, 1.0]}, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.codigo is None


def test_elegir_mejor_fragmento_ignora_fragmentos_ambiguos_y_gana_el_claro() -> None:
    # Dos fragmentos genéricos (ambiguos entre "a" y "b") y uno claro para "a": el claro debe
    # ganar porque se evalúa cada fragmento por separado, no un promedio de los tres.
    vectores_vocabulario = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    fragmentos = [
        FragmentoEmbedding("texto genérico uno", [0.7071, 0.7071]),
        FragmentoEmbedding("la oración específica de a", [0.99, 0.1]),
        FragmentoEmbedding("texto genérico dos", [0.7071, 0.7071]),
    ]
    resultado = elegir_mejor_fragmento(
        fragmentos, vectores_vocabulario, confianza_minima=0.85, margen_minimo_top2=0.01
    )
    assert resultado.codigo == "a"
    assert resultado.texto_evidencia == "la oración específica de a"


def test_cargar_expresiones_mecanismo_tiene_contenido_real() -> None:
    expresiones = cargar_expresiones_mecanismo()
    assert len(expresiones) > 0
    assert all({"expresion", "code"} <= set(e) for e in expresiones)


def test_clasificar_mecanismo_explicito_encuentra_coincidencia_literal() -> None:
    expresiones = [{"expresion": "compra de ganado", "code": "compra_ganado"}]
    resultado = clasificar_mecanismo_explicito(
        "Según los hechos, el investigado realizó la COMPRA DE GANADO con dinero ilícito.",
        expresiones,
    )
    assert resultado is not None
    assert resultado.codigo == "compra_ganado"
    assert resultado.texto_evidencia.lower() == "compra de ganado"


def test_clasificar_mecanismo_explicito_sin_coincidencia_devuelve_none() -> None:
    expresiones = [{"expresion": "compra de ganado", "code": "compra_ganado"}]
    resultado = clasificar_mecanismo_explicito("un texto sin relación alguna", expresiones)
    assert resultado is None


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


def test_clasificar_fragmento_no_diluye_una_mencion_puntual_en_relato_largo() -> None:
    """Reproduce el síntoma real reportado desde la app: un relato largo con lenguaje genérico
    de trámite (identificación, policía, UIAF...) y una sola oración que describe un mecanismo
    concreto. Antes de clasificar por fragmento, promediar todo el relato diluía esa oración; al
    comparar fragmento por fragmento, la oración específica debe ganar.
    """
    from decla.conocimiento.zero_shot import calcular_vectores_vocabulario

    relleno_generico = (
        "El señor investigado fue identificado por la policía judicial. "
        "Según el informe de la UIAF, se adelanta la investigación por el presunto delito. "
        "La fiscalía seccional asignó el caso al grupo especializado correspondiente. "
    ) * 15
    relato_largo = relleno_generico + (
        "En el desarrollo de los hechos, el investigado compró cabezas de ganado con dinero "
        "de origen ilícito para darle apariencia de legalidad a los recursos."
    )

    vocabulario = cargar_vocabulario("mecanismo")
    vectores = calcular_vectores_vocabulario(vocabulario, MODELO_RAPIDO)
    resultado = clasificar_fragmento(
        relato_largo, vectores, MODELO_RAPIDO, confianza_minima=0.75, margen_minimo_top2=0.01
    )
    assert resultado.codigo == "compra_ganado"
    assert "ganado" in (resultado.texto_evidencia or "")
