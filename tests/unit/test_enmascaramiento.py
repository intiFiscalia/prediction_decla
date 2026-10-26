from decla.texto.enmascaramiento import enmascarar, extraer_direcciones


def test_enmascarar_texto_vacio() -> None:
    resultado = enmascarar(None)
    assert resultado.texto_enmascarado == ""
    assert resultado.conteos_por_tipo == {}


def test_enmascarar_cubre_los_seis_tipos_sin_solapes() -> None:
    texto = (
        "Juan Pérez, identificado con cédula de ciudadanía número 1.023.456.789, reside en la "
        "Calle 45 # 12-30 y puede contactarse al 3101234567 o al correo juan.perez@correo.com. "
        "El vehículo de placas ABC123 fue incautado."
    )
    resultado = enmascarar(texto)
    assert "[PERSONA]" in resultado.texto_enmascarado
    assert "[DOC]" in resultado.texto_enmascarado
    assert "[DIRECCION]" in resultado.texto_enmascarado
    assert "[TEL]" in resultado.texto_enmascarado
    assert "[CORREO]" in resultado.texto_enmascarado
    assert "[PLACA]" in resultado.texto_enmascarado
    assert "1.023.456.789" not in resultado.texto_enmascarado
    assert "3101234567" not in resultado.texto_enmascarado
    assert "juan.perez@correo.com" not in resultado.texto_enmascarado
    assert resultado.conteos_por_tipo == {
        "[PERSONA]": 1,
        "[DOC]": 1,
        "[DIRECCION]": 1,
        "[TEL]": 1,
        "[CORREO]": 1,
        "[PLACA]": 1,
    }


def test_enmascarar_no_toca_texto_sin_datos_personales() -> None:
    texto = "El vehículo transportaba mercancía de contrabando sin documentos de importación."
    resultado = enmascarar(texto)
    assert resultado.texto_enmascarado == texto
    assert resultado.conteos_por_tipo == {}


def test_enmascarar_resuelve_solape_priorizando_coincidencia_mas_especifica() -> None:
    # El teléfono móvil y un posible "fijo con disparador" podrían solaparse si ambos patrones
    # dispararan sobre el mismo número; el resultado nunca debe tener marcadores encimados.
    texto = "cel. 3101234567 es el número de contacto"
    resultado = enmascarar(texto)
    assert resultado.texto_enmascarado.count("[TEL]") == 1


def test_extraer_direcciones() -> None:
    texto = "la vivienda ubicada en la Carrera 7 # 45-12 fue allanada"
    resultados = extraer_direcciones(texto)
    assert len(resultados) == 1
    assert "Carrera 7" in resultados[0].texto_evidencia


def test_enmascarar_mapa_offsets_proyecta_region_no_enmascarada() -> None:
    texto = "El vehículo con placas ABC123 fue incautado en la vía pública"
    resultado = enmascarar(texto)
    posicion = resultado.texto_enmascarado.index("incautado")
    inicio, fin = resultado.mapa_offsets.proyectar(posicion, posicion + len("incautado"))
    assert texto[inicio:fin] == "incautado"
