from decla.texto.pipeline_spacy import analizar, construir_patrones_gazetteer


def test_construir_patrones_gazetteer_incluye_las_tres_fuentes() -> None:
    patrones = construir_patrones_gazetteer()
    etiquetas = {p["label"] for p in patrones}
    assert "INSTITUCION" in etiquetas
    assert "TIPO_DOCUMENTO" in etiquetas
    assert "LOC" in etiquetas


def test_analizar_reconoce_institucion_del_gazetteer() -> None:
    doc = analizar("La UIAF reportó una operación sospechosa.")
    instituciones = [e.text for e in doc.ents if e.label_ == "INSTITUCION"]
    assert "UIAF" in instituciones


def test_analizar_reconoce_tipo_documento_del_gazetteer() -> None:
    doc = analizar("Se citó textualmente el informe FPJ-5 de captura en flagrancia.")
    tipos = [e.text for e in doc.ents if e.label_ == "TIPO_DOCUMENTO"]
    assert "FPJ-5" in tipos


def test_analizar_reconoce_municipio_divipola_como_loc() -> None:
    doc = analizar("Los hechos ocurrieron en el municipio de Acacías, departamento del Meta.")
    locs = [e.text for e in doc.ents if e.label_ == "LOC"]
    assert "Acacías" in locs
    assert "Meta" in locs


def test_analizar_produce_tokens_y_lemas() -> None:
    doc = analizar("El Fiscal informó sobre el caso.")
    assert len(list(doc.sents)) >= 1
    assert any(token.lemma_ == "informar" for token in doc)
