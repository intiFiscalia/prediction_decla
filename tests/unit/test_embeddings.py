from pathlib import Path

import polars as pl

from decla.texto.embeddings import (
    MAXIMO,
    MEDIA,
    calcular_embeddings_relato,
    calcular_vectores_fragmentos,
    cargar_modelo_embeddings,
    escribir_embeddings_parquet,
    fragmentar_por_limite,
)

MODELO_RAPIDO = "paraphrase-multilingual-mpnet-base-v2"


def test_fragmentar_texto_corto_devuelve_un_fragmento() -> None:
    modelo = cargar_modelo_embeddings(MODELO_RAPIDO)
    fragmentos = fragmentar_por_limite("El sujeto fue capturado en flagrancia.", modelo)
    assert len(fragmentos) == 1


def test_fragmentar_texto_largo_respeta_el_limite_de_tokens() -> None:
    modelo = cargar_modelo_embeddings(MODELO_RAPIDO)
    texto_largo = " ".join(["El sujeto investigado realizó una transacción sospechosa."] * 60)
    fragmentos = fragmentar_por_limite(texto_largo, modelo)
    assert len(fragmentos) > 1
    for fragmento in fragmentos:
        n_tokens = len(modelo.tokenizer.encode(fragmento, add_special_tokens=True))
        assert n_tokens <= modelo.max_seq_length


def test_calcular_embeddings_relato_devuelve_media_y_maximo() -> None:
    resultado = calcular_embeddings_relato(
        "u1", "El vehículo transportaba mercancía.", MODELO_RAPIDO
    )
    agregaciones = {e.agregacion for e in resultado}
    assert agregaciones == {MEDIA, MAXIMO}
    for embedding in resultado:
        assert embedding.registro_uid == "u1"
        assert embedding.version_modelo == MODELO_RAPIDO
        assert len(embedding.vector) == 768


def test_calcular_embeddings_relato_texto_vacio_devuelve_lista_vacia() -> None:
    assert calcular_embeddings_relato("u1", None, MODELO_RAPIDO) == []
    assert calcular_embeddings_relato("u1", "   ", MODELO_RAPIDO) == []


def test_calcular_vectores_fragmentos_texto_vacio_devuelve_lista_vacia() -> None:
    assert calcular_vectores_fragmentos(None, MODELO_RAPIDO) == []
    assert calcular_vectores_fragmentos("   ", MODELO_RAPIDO) == []


def test_calcular_vectores_fragmentos_un_fragmento_por_texto_corto() -> None:
    fragmentos = calcular_vectores_fragmentos("El vehículo transportaba mercancía.", MODELO_RAPIDO)
    assert len(fragmentos) == 1
    assert fragmentos[0].texto == "El vehículo transportaba mercancía."
    assert len(fragmentos[0].vector) == 768


def test_calcular_vectores_fragmentos_varios_fragmentos_por_texto_largo() -> None:
    texto_largo = " ".join(["El sujeto investigado realizó una transacción sospechosa."] * 60)
    fragmentos = calcular_vectores_fragmentos(texto_largo, MODELO_RAPIDO)
    assert len(fragmentos) > 1


def test_escribir_embeddings_parquet(tmp_path: Path) -> None:
    embeddings = calcular_embeddings_relato("u1", "Un relato corto de prueba.", MODELO_RAPIDO)
    ruta = tmp_path / "embeddings" / "relato.parquet"
    escribir_embeddings_parquet(embeddings, ruta)

    df = pl.read_parquet(ruta)
    assert set(df.columns) == {"registro_uid", "version_modelo", "agregacion", "vector"}
    assert df.height == 2
