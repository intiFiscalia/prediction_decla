from decla.normalizacion.categoricas import normalizar_categoria, normalizar_fila_categoricas


def test_normalizar_categoria_unifica_mayusculas_y_tildes() -> None:
    assert normalizar_categoria("Indagación") == "INDAGACION"
    assert normalizar_categoria("  INDAGACION  ") == "INDAGACION"
    assert normalizar_categoria(None) is None


def test_normalizar_fila_categoricas_conserva_original() -> None:
    fila = {"ESTADO": "Activo", "ETAPA": "Indagación", "TIPO_NOTICIA": None}
    resultado = normalizar_fila_categoricas(fila, columnas=["ESTADO", "ETAPA", "TIPO_NOTICIA"])
    assert resultado["ESTADO"].valor_orig == "Activo"
    assert resultado["ESTADO"].valor_normalizado == "ACTIVO"
    assert resultado["TIPO_NOTICIA"].valor_orig is None
    assert resultado["TIPO_NOTICIA"].valor_normalizado is None
