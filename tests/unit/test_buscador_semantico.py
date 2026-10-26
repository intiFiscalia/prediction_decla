from decla.texto.buscador_semantico import buscar_similares, vector_de_consulta

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_buscar_similares_ordena_por_coseno_descendente() -> None:
    corpus = {
        "u1": [1.0, 0.0],
        "u2": [0.9, 0.1],
        "u3": [0.0, 1.0],
    }
    resultados = buscar_similares([1.0, 0.0], corpus, k=3)
    assert [r.registro_uid for r in resultados] == ["u1", "u2", "u3"]
    assert resultados[0].similitud == 1.0


def test_buscar_similares_respeta_k() -> None:
    corpus = {"u1": [1.0, 0.0], "u2": [0.9, 0.1], "u3": [0.0, 1.0]}
    resultados = buscar_similares([1.0, 0.0], corpus, k=2)
    assert len(resultados) == 2


def test_buscar_similares_excluye_uid_propio() -> None:
    corpus = {"u1": [1.0, 0.0], "u2": [0.9, 0.1]}
    resultados = buscar_similares([1.0, 0.0], corpus, k=5, excluir_uid="u1")
    assert all(r.registro_uid != "u1" for r in resultados)
    assert len(resultados) == 1


def test_buscar_similares_corpus_vacio_devuelve_lista_vacia() -> None:
    assert buscar_similares([1.0, 0.0], {}, k=5) == []


def test_vector_de_consulta_devuelve_vector_de_dimension_esperada() -> None:
    vector = vector_de_consulta("contrabando de cigarrillos en la frontera", MODELO_RAPIDO)
    assert len(vector) == 768


def test_buscador_recupera_relato_semanticamente_similar() -> None:
    from decla.texto.embeddings import MEDIA, calcular_embeddings_relato

    textos = {
        "u1": "contrabando de cigarrillos en la frontera con Venezuela",
        "u2": "testaferrato en la compra de inmuebles de alto valor",
    }
    corpus = {}
    for uid, texto in textos.items():
        embeddings = calcular_embeddings_relato(uid, texto, MODELO_RAPIDO)
        corpus[uid] = next(e.vector for e in embeddings if e.agregacion == MEDIA)

    vector_consulta = vector_de_consulta("contrabando de mercancías en la frontera", MODELO_RAPIDO)
    resultados = buscar_similares(vector_consulta, corpus, k=1)
    assert resultados[0].registro_uid == "u1"
