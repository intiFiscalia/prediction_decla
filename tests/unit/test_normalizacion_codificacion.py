from decla.normalizacion.codificacion import reparar_texto


def test_reparar_texto_sin_mojibake_no_cambia() -> None:
    resultado = reparar_texto("texto normal sin problemas")
    assert resultado.texto == "texto normal sin problemas"
    assert resultado.reparacion_codificacion is False
    assert resultado.reparacion_fallida is False


def test_reparar_texto_con_mojibake_se_repara() -> None:
    original = "El señor José Núñez"
    corrupto = original.encode("cp1252", errors="replace").decode("cp1251", errors="replace")
    resultado = reparar_texto(corrupto)
    assert resultado.texto == original
    assert resultado.reparacion_codificacion is True
    assert resultado.reparacion_fallida is False


def test_reparar_texto_none() -> None:
    resultado = reparar_texto(None)
    assert resultado.texto is None
    assert resultado.reparacion_codificacion is False
    assert resultado.reparacion_fallida is False
