from decla.texto.segmentacion import (
    MARCADOR_DESCRIPCION_HECHO,
    METODO_DENSIDAD,
    SIN_MARCADOR,
    VACIO,
    calcular_cobertura,
    calcular_cobertura_densidad,
    segmentar,
    segmentar_combinado,
    segmentar_por_densidad,
)

MARCADORES = ["los hechos objeto de", "se tuvo conocimiento de que", "en el desarrollo de"]

VOCABULARIO_ADMINISTRATIVO = {
    "siendo",
    "hora",
    "horas",
    "suscrito",
    "suscrita",
    "funcionario",
    "funcionaria",
    "adscrito",
    "adscrita",
    "despacho",
    "unidad",
    "seccional",
    "informe",
    "acta",
    "recibir",
    "recibido",
    "recibida",
    "diligencia",
    "cumplimiento",
    "correspondiente",
    "conocimiento",
    "manifestar",
}


def test_segmentar_texto_vacio() -> None:
    resultado = segmentar(None, MARCADORES)
    assert resultado.metodo == VACIO
    assert resultado.contexto_denuncia is None
    assert resultado.descripcion_hecho == ""


def test_segmentar_con_marcador_encontrado_divide_en_dos() -> None:
    texto = (
        "Siendo las 14:30 horas, el suscrito funcionario adscrito a la SIJIN informa que "
        "los hechos objeto de la presente investigación ocurrieron el día de ayer en la vía."
    )
    resultado = segmentar(texto, MARCADORES)
    assert resultado.metodo == MARCADOR_DESCRIPCION_HECHO
    assert resultado.marcador_usado is not None
    assert "funcionario adscrito" in resultado.contexto_denuncia
    assert resultado.descripcion_hecho.lower().startswith("los hechos objeto de")


def test_segmentar_sin_marcador_queda_todo_como_descripcion() -> None:
    texto = "El vehículo transportaba mercancía de contrabando sin documentos de importación."
    resultado = segmentar(texto, MARCADORES)
    assert resultado.metodo == SIN_MARCADOR
    assert resultado.contexto_denuncia is None
    assert resultado.descripcion_hecho == texto


def test_segmentar_marcador_al_inicio_no_produce_contexto_vacio() -> None:
    texto = "En el desarrollo de un control vial se incautó mercancía."
    resultado = segmentar(texto, MARCADORES)
    assert resultado.metodo == SIN_MARCADOR
    assert resultado.contexto_denuncia is None


def test_calcular_cobertura_sobre_lista_de_textos() -> None:
    textos = [
        "Siendo las 9:00 horas se recibió la denuncia. Los hechos objeto de investigación...",
        "El vehículo transportaba mercancía sin documentos.",
        "",
    ]
    cobertura = calcular_cobertura(textos, MARCADORES)
    assert cobertura == 0.5


def test_segmentar_por_densidad_texto_vacio() -> None:
    resultado = segmentar_por_densidad(None, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == VACIO
    assert resultado.contexto_denuncia is None
    assert resultado.descripcion_hecho == ""


def test_segmentar_por_densidad_encuentra_corte_sin_frase_exacta() -> None:
    texto = (
        "Siendo las catorce horas el suscrito funcionario adscrito a la unidad recibió el "
        "informe correspondiente. El vehículo transportaba mercancía de contrabando sin "
        "documentos de importación y fue interceptado por la policía en la vía."
    )
    resultado = segmentar_por_densidad(texto, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == METODO_DENSIDAD
    assert resultado.contexto_denuncia is not None
    assert "funcionario" in resultado.contexto_denuncia
    assert "contrabando" in resultado.descripcion_hecho
    assert "funcionario" not in resultado.descripcion_hecho


def test_segmentar_por_densidad_sin_evidencia_deja_todo_como_hecho() -> None:
    texto = "El vehículo transportaba mercancía de contrabando sin documentos de importación."
    resultado = segmentar_por_densidad(texto, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == SIN_MARCADOR
    assert resultado.contexto_denuncia is None
    assert resultado.descripcion_hecho == texto


def test_segmentar_por_densidad_ignora_oraciones_muy_cortas() -> None:
    texto = "Hoy. Siendo las horas el suscrito funcionario del despacho recibió el informe. Fin."
    resultado = segmentar_por_densidad(texto, VOCABULARIO_ADMINISTRATIVO, min_tokens_oracion=4)
    assert resultado.metodo == SIN_MARCADOR


def test_calcular_cobertura_densidad_sobre_lista_de_textos() -> None:
    textos = [
        (
            "Siendo las catorce horas el suscrito funcionario adscrito a la unidad recibió el "
            "informe correspondiente. El vehículo transportaba mercancía de contrabando."
        ),
        "El vehículo transportaba mercancía sin documentos.",
        "",
    ]
    cobertura = calcular_cobertura_densidad(textos, VOCABULARIO_ADMINISTRATIVO)
    assert cobertura == 0.5


def test_segmentar_combinado_prefiere_frase_exacta_sobre_densidad() -> None:
    texto = (
        "Siendo las 14:30 horas, el suscrito funcionario adscrito a la SIJIN informa que "
        "los hechos objeto de la presente investigación ocurrieron el día de ayer en la vía."
    )
    resultado = segmentar_combinado(texto, MARCADORES, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == MARCADOR_DESCRIPCION_HECHO


def test_segmentar_combinado_usa_densidad_cuando_no_hay_frase_exacta() -> None:
    texto = (
        "Siendo las catorce horas el suscrito funcionario adscrito a la unidad recibió el "
        "informe correspondiente. El vehículo transportaba mercancía de contrabando sin "
        "documentos de importación y fue interceptado por la policía en la vía."
    )
    resultado = segmentar_combinado(texto, MARCADORES, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == METODO_DENSIDAD


def test_segmentar_combinado_texto_vacio() -> None:
    resultado = segmentar_combinado(None, MARCADORES, VOCABULARIO_ADMINISTRATIVO)
    assert resultado.metodo == VACIO
