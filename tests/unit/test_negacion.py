from decla.texto.negacion import AFIRMADA, ATRIBUIDA, HIPOTETICA, NEGADA, clasificar_polaridad

DISPARADORES_NEGACION = ["no se halló", "sin encontrar"]
DISPARADORES_HIPOTESIS = ["presuntamente", "al parecer"]
DISPARADORES_ATRIBUCION = ["según manifiesta", "según el denunciante"]


def _clasificar(texto: str, span_inicio: int, span_fin: int, ventana_tokens: int = 8) -> str:
    return clasificar_polaridad(
        texto,
        span_inicio,
        span_fin,
        DISPARADORES_NEGACION,
        DISPARADORES_HIPOTESIS,
        DISPARADORES_ATRIBUCION,
        ventana_tokens,
    )


def test_span_sin_disparadores_queda_afirmada() -> None:
    texto = "el vehículo transportaba mercancía de contrabando"
    inicio = texto.index("mercancía")
    assert _clasificar(texto, inicio, inicio + len("mercancía")) == AFIRMADA


def test_negacion_antes_del_span_domina() -> None:
    texto = "no se halló evidencia de dinero en efectivo en el inmueble"
    inicio = texto.index("dinero")
    assert _clasificar(texto, inicio, inicio + len("dinero")) == NEGADA


def test_negacion_fuera_de_la_ventana_no_aplica() -> None:
    texto = (
        "no se halló nada en la primera inspección realizada por los investigadores durante "
        "la diligencia que se extendió por varias horas hasta encontrar finalmente el dinero"
    )
    inicio = texto.index("dinero")
    assert _clasificar(texto, inicio, inicio + len("dinero"), ventana_tokens=5) == AFIRMADA


def test_hipotesis_despues_del_span() -> None:
    texto = "el dinero incautado sería, presuntamente, producto de actividades ilícitas"
    inicio = texto.index("dinero")
    assert _clasificar(texto, inicio, inicio + len("dinero")) == HIPOTETICA


def test_atribucion_sin_negacion_ni_hipotesis() -> None:
    texto = "según manifiesta el testigo, el dinero provenía de una venta de ganado"
    inicio = texto.index("dinero")
    assert _clasificar(texto, inicio, inicio + len("dinero")) == ATRIBUIDA


def test_negacion_domina_sobre_atribucion_si_ambas_aparecen() -> None:
    texto = "según manifiesta el testigo, no se halló el dinero en la propiedad"
    inicio = texto.index("dinero")
    assert _clasificar(texto, inicio, inicio + len("dinero")) == NEGADA
