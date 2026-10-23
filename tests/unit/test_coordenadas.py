from decla.calidad.coordenadas import reparar_coordenadas


def test_coordenada_vacia() -> None:
    resultado = reparar_coordenadas(None, None)
    assert resultado.metodo == "vacia"


def test_coordenada_correcta_dentro_de_la_caja() -> None:
    resultado = reparar_coordenadas("4.142", "-73.6266")
    assert resultado.metodo == "correcta"
    assert resultado.lat_reparada == 4.142
    assert resultado.long_reparada == -73.6266


def test_coordenada_sin_separador_decimal_se_reescala() -> None:
    resultado = reparar_coordenadas("LAT 5316", "LONG -72423")
    assert resultado.metodo == "reparada_escala"
    assert resultado.lat_reparada is not None and abs(resultado.lat_reparada - 5.316) < 1e-6
    assert resultado.long_reparada is not None and abs(resultado.long_reparada - (-72.423)) < 1e-6


def test_coordenada_invertida_se_detecta_y_corrige() -> None:
    # lat/long reales de Villavicencio invertidos: lat=-73.6266 (imposible), long=4.142
    resultado = reparar_coordenadas("-73.6266", "4.142")
    assert resultado.metodo == "invertida"
    assert resultado.lat_reparada == 4.142
    assert resultado.long_reparada == -73.6266


def test_coordenada_fuera_de_colombia() -> None:
    resultado = reparar_coordenadas("40.4168", "-3.7038")  # Madrid
    assert resultado.metodo == "fuera_de_caja"


def test_coordenada_no_reparable_valor_no_numerico() -> None:
    resultado = reparar_coordenadas("no es un numero", "-73.6266")
    assert resultado.metodo == "no_reparable"


def test_coordenada_coincide_con_centroide() -> None:
    centroide = (4.142, -73.6266)
    resultado = reparar_coordenadas("4.142", "-73.6266", centroide=centroide)
    assert resultado.coincide_centroide is True


def test_coordenada_no_coincide_con_centroide() -> None:
    centroide = (11.5444, -72.9072)  # Riohacha, muy lejos de Villavicencio
    resultado = reparar_coordenadas("4.142", "-73.6266", centroide=centroide)
    assert resultado.coincide_centroide is False
