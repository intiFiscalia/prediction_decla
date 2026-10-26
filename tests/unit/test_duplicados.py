from decla.texto.duplicados import (
    ParCasiDuplicado,
    calcular_minhash,
    construir_grupos_duplicados,
    detectar_casi_duplicados,
)

TEXTO_BASE = (
    "el día de los hechos se recibió información sobre una operación de contrabando de "
    "cigarrillos en el municipio de Maicao, Guajira, con participación de varios implicados"
)


def test_minhash_de_textos_identicos_tiene_jaccard_1() -> None:
    a = calcular_minhash(TEXTO_BASE)
    b = calcular_minhash(TEXTO_BASE)
    assert a.jaccard(b) == 1.0


def test_minhash_de_textos_muy_distintos_tiene_jaccard_bajo() -> None:
    a = calcular_minhash(TEXTO_BASE)
    b = calcular_minhash(
        "según manifiesta el denunciante, se presume enriquecimiento ilícito de un servidor "
        "público relacionado con contratos de infraestructura vial en el departamento del Meta"
    )
    assert a.jaccard(b) < 0.3


def test_detectar_casi_duplicados_encuentra_par_casi_identico() -> None:
    textos = {
        "u1": TEXTO_BASE,
        "u2": TEXTO_BASE + " adicionalmente se incautó un vehículo en el lugar",
        "u3": (
            "según manifiesta el denunciante, se presume enriquecimiento ilícito de un "
            "servidor público relacionado con contratos de infraestructura vial"
        ),
    }
    pares = detectar_casi_duplicados(textos, umbral_jaccard=0.6)
    claves = {(p.registro_uid_a, p.registro_uid_b) for p in pares}
    assert ("u1", "u2") in claves
    assert not any("u3" in clave for clave in claves)


def test_detectar_casi_duplicados_sin_pares_devuelve_lista_vacia() -> None:
    textos = {
        "u1": "contrabando de combustible en la frontera con Venezuela",
        "u2": "testaferrato en la compra de inmuebles de alto valor en Bogotá",
    }
    assert detectar_casi_duplicados(textos, umbral_jaccard=0.9) == []


def test_construir_grupos_duplicados_agrupa_componente_transitivo() -> None:
    pares = [
        ParCasiDuplicado("u2", "u1", 0.95),
        ParCasiDuplicado("u3", "u2", 0.9),
        ParCasiDuplicado("u9", "u8", 0.85),
    ]
    grupos = construir_grupos_duplicados(pares)
    assert grupos["u1"] == grupos["u2"] == grupos["u3"] == "u1"
    assert grupos["u8"] == grupos["u9"] == "u8"


def test_construir_grupos_duplicados_sin_pares_devuelve_vacio() -> None:
    assert construir_grupos_duplicados([]) == {}
