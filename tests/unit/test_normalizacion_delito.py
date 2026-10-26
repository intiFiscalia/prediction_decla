from decla.normalizacion.delito import construir_dim_delito, normalizar_delito


def test_normalizar_delito_parseable() -> None:
    resultado = normalizar_delito(
        "LAVADO DE ACTIVOS ART. 323 C.P.CUANTIA INFERIOR A 100 SMLM",
        titulo="TITULO X",
        capitulo="CAPITULO UNICO",
    )
    assert resultado.parseable
    assert resultado.delito_nombre == "LAVADO DE ACTIVOS"
    assert resultado.articulo_cp == "323"
    assert resultado.titulo == "TITULO X"
    assert resultado.capitulo == "CAPITULO UNICO"


def test_normalizar_delito_no_parseable() -> None:
    resultado = normalizar_delito("TEXTO SIN FORMATO", titulo=None, capitulo=None)
    assert not resultado.parseable
    assert resultado.delito_nombre is None


def test_construir_dim_delito_deduplica_por_nombre_y_articulo() -> None:
    delitos = [
        normalizar_delito("LAVADO DE ACTIVOS ART. 323 C.P.CUANTIA X", "TITULO X", "CAP UNICO"),
        normalizar_delito("LAVADO DE ACTIVOS ART. 323 C.P.CUANTIA Y", "TITULO X", "CAP UNICO"),
        normalizar_delito("CONTRABANDO ART. 319 C.P.CUANTIA Z", "TITULO XII", "CAP VIII"),
        normalizar_delito("TEXTO NO PARSEABLE", None, None),
    ]
    dim = construir_dim_delito(delitos)
    assert len(dim) == 2
    nombres = {d["delito_nombre"] for d in dim}
    assert nombres == {"LAVADO DE ACTIVOS", "CONTRABANDO"}
