from decla.texto.segmentacion import (
    MARCADOR_DESCRIPCION_HECHO,
    SIN_MARCADOR,
    VACIO,
    calcular_cobertura,
    segmentar,
)

MARCADORES = ["los hechos objeto de", "se tuvo conocimiento de que", "en el desarrollo de"]


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
