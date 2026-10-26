from decla.texto.normalizacion_conservadora import normalizar_conservador


def test_normalizar_conservador_none_devuelve_none() -> None:
    texto, mapa = normalizar_conservador(None)
    assert texto is None
    assert mapa.tramos == []


def test_reune_palabras_partidas_por_salto_de_linea() -> None:
    texto, _ = normalizar_conservador("la organi-\nzación delictiva")
    assert "organización" in texto
    assert "organi-" not in texto


def test_unifica_comillas_y_guiones_tipograficos() -> None:
    texto, _ = normalizar_conservador('dijo “hola” y recibió una llamada – según el testigo')
    assert "“" not in texto and "”" not in texto
    assert '"hola"' in texto
    assert "–" not in texto


def test_colapsa_espacios_multiples_y_recorta_extremos() -> None:
    texto, _ = normalizar_conservador("  hola    mundo  \n\n  otra línea  ")
    assert texto == "hola mundo otra línea"


def test_mantiene_tildes_y_numeros() -> None:
    texto, _ = normalizar_conservador("El día 15 ocurrió según información recibida")
    assert "día" in texto
    assert "15" in texto


def test_baja_mayusculas_sostenidas_con_suficientes_palabras() -> None:
    texto, _ = normalizar_conservador("SIENDO LAS 14:30 HORAS DEL DIA DE HOY se recibió el caso")
    assert "siendo las 14:30 horas del dia de hoy" in texto
    assert "se recibió el caso" in texto


def test_no_baja_siglas_cortas_aisladas() -> None:
    texto, _ = normalizar_conservador("la DIAN informó del caso a la UIAF ayer")
    assert "DIAN" in texto
    assert "UIAF" in texto


def test_mapa_offsets_proyecta_region_sin_cambios_al_original() -> None:
    original = "El  reporte indica  lo siguiente"
    texto, mapa = normalizar_conservador(original)
    posicion = texto.index("reporte")
    inicio_original, fin_original = mapa.proyectar(posicion, posicion + len("reporte"))
    assert original[inicio_original:fin_original] == "reporte"
