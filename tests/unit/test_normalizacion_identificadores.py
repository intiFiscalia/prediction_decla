from decla.normalizacion.identificadores import descomponer_caso_noticia, limpiar_identificador


def test_limpiar_identificador_quita_sufijo_punto_cero() -> None:
    assert limpiar_identificador("12345.0") == "12345"
    assert limpiar_identificador("12345") == "12345"
    assert limpiar_identificador(None) is None


def test_descomponer_caso_noticia_valido() -> None:
    # 05001 (dane) + 17 (entidad) + 00002 (unidad) + 2026 (anio) + 00001 (consecutivo) = 21
    valor = "05001" + "17" + "00002" + "2026" + "00001"
    resultado = descomponer_caso_noticia(valor)
    assert resultado.valido_21_digitos is True
    assert resultado.cn_dane == "05001"
    assert resultado.cn_entidad == "17"
    assert resultado.cn_unidad == "00002"
    assert resultado.cn_anio == "2026"
    assert resultado.cn_consecutivo == "00001"


def test_descomponer_caso_noticia_quita_sufijo_antes_de_validar() -> None:
    valor = "05001" + "17" + "00002" + "2026" + "00001"
    resultado = descomponer_caso_noticia(valor + ".0")
    assert resultado.valido_21_digitos is True
    assert resultado.valor_limpio == valor


def test_descomponer_caso_noticia_invalido_por_longitud() -> None:
    resultado = descomponer_caso_noticia("12345")
    assert resultado.valido_21_digitos is False
    assert resultado.cn_dane is None


def test_descomponer_caso_noticia_invalido_no_numerico() -> None:
    resultado = descomponer_caso_noticia("abcde17000022026000012")
    assert resultado.valido_21_digitos is False


def test_descomponer_caso_noticia_none() -> None:
    resultado = descomponer_caso_noticia(None)
    assert resultado.valido_21_digitos is False
    assert resultado.valor_limpio is None
