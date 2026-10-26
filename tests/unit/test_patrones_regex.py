from decla.texto.patrones_regex import (
    extraer_articulos_penales,
    extraer_cedulas,
    extraer_correos,
    extraer_fechas_en_texto,
    extraer_km_via,
    extraer_montos,
    extraer_motor_chasis,
    extraer_nit,
    extraer_placas,
    extraer_subpartidas,
    extraer_telefonos,
)


def test_extraer_articulos_penales_variantes() -> None:
    texto = "incurrió en el delito previsto en el Art. 323 C.P. y también artículo 320"
    resultados = extraer_articulos_penales(texto)
    valores = [r.valor_normalizado for r in resultados]
    assert "323" in valores
    assert "320" in valores


def test_extraer_montos_cifra_y_letras() -> None:
    texto = "se incautaron $50.000.000 en efectivo, equivalentes a cincuenta millones de pesos"
    resultados = extraer_montos(texto)
    categorias = {r.categoria for r in resultados}
    assert categorias == {"monto"}
    assert any("$50.000.000" in r.texto_evidencia for r in resultados)
    assert any("cincuenta millones de pesos" in r.texto_evidencia.lower() for r in resultados)


def test_extraer_placas_vehiculo_y_moto() -> None:
    texto = "el vehículo de placas ABC123 y la motocicleta XYZ12A fueron inmovilizados"
    resultados = extraer_placas(texto)
    evidencias = {r.texto_evidencia for r in resultados}
    assert "ABC123" in evidencias
    assert "XYZ12A" in evidencias


def test_extraer_cedulas_con_disparador() -> None:
    texto = "identificado con cédula de ciudadanía número 1.023.456.789"
    resultados = extraer_cedulas(texto)
    assert len(resultados) == 1
    assert resultados[0].valor_normalizado == "1.023.456.789"


def test_extraer_cedulas_no_dispara_sin_contexto() -> None:
    texto = "el radicado 1.023.456.789 fue asignado al despacho"
    assert extraer_cedulas(texto) == []


def test_extraer_nit_con_digito_de_verificacion() -> None:
    texto = "la empresa con NIT 900123456-7 figura como fachada"
    resultados = extraer_nit(texto)
    assert resultados[0].valor_normalizado == "900123456-7"


def test_extraer_telefonos_movil_y_fijo() -> None:
    texto = "contactado al 3101234567 o al teléfono 6012345678"
    resultados = extraer_telefonos(texto)
    categorias = {r.categoria for r in resultados}
    assert categorias == {"telefono"}
    assert len(resultados) == 2


def test_extraer_correos() -> None:
    texto = "envió la información a contacto@correo.com.co para coordinar el giro"
    resultados = extraer_correos(texto)
    assert resultados[0].texto_evidencia == "contacto@correo.com.co"


def test_extraer_motor_chasis() -> None:
    texto = "el vehículo tiene motor número AB12345CD y chasis 9BWZZZ377VT004251"
    resultados = extraer_motor_chasis(texto)
    categorias = {r.categoria for r in resultados}
    assert categorias == {"motor", "chasis"}


def test_extraer_km_via() -> None:
    texto = "el retén se ubicó en el km 23+500 de la vía al llano"
    resultados = extraer_km_via(texto)
    assert resultados[0].valor_normalizado == "23+500"


def test_extraer_subpartidas() -> None:
    texto = "declaró la mercancía bajo la subpartida arancelaria 2402.20.00.00"
    resultados = extraer_subpartidas(texto)
    assert resultados[0].valor_normalizado == "2402.20.00.00"


def test_extraer_fechas_numericas_y_con_mes_en_texto() -> None:
    texto = "ocurrió el 10/8/2026, confirmado también el 04 DE AGSOTO DEL 2026 y el 26/Agosto/2026"
    resultados = extraer_fechas_en_texto(texto)
    assert any(r.texto_evidencia == "10/8/2026" for r in resultados)
    con_mes_texto = [
        r for r in resultados if r.valor_normalizado and "agosto" in r.valor_normalizado
    ]
    assert len(con_mes_texto) == 2
    assert all("agosto" in r.valor_normalizado for r in con_mes_texto)
