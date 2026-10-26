from decla.texto.offsets import ConstructorTextoConOffsets, MapaOffsets, Tramo, componer


def test_constructor_copia_simple_proyecta_identidad() -> None:
    constructor = ConstructorTextoConOffsets()
    constructor.agregar("hola mundo", 0, 10)
    texto, mapa = constructor.construir()

    assert texto == "hola mundo"
    assert mapa.proyectar(0, 4) == (0, 4)
    assert mapa.proyectar(5, 10) == (5, 10)


def test_constructor_con_fragmento_eliminado_no_agrega_tramo() -> None:
    constructor = ConstructorTextoConOffsets()
    constructor.agregar("ab", 0, 2)
    constructor.agregar("", 2, 4)
    constructor.agregar("cd", 4, 6)
    texto, mapa = constructor.construir()

    assert texto == "abcd"
    assert mapa.proyectar(0, 2) == (0, 2)
    assert mapa.proyectar(2, 4) == (4, 6)


def test_mapa_offsets_sin_tramos_cubiertos_devuelve_el_mismo_span() -> None:
    mapa = MapaOffsets(tramos=[])
    assert mapa.proyectar(3, 7) == (3, 7)


def test_mapa_offsets_tramo_mas_corto_que_el_original_devuelve_rango_envolvente() -> None:
    # Un tramo que colapsó "   " (3 espacios originales) en " " (1 espacio limpio).
    mapa = MapaOffsets(
        tramos=[Tramo(limpio_inicio=0, limpio_fin=1, original_inicio=0, original_fin=3)]
    )
    assert mapa.proyectar(0, 1) == (0, 3)


def test_mapa_offsets_span_que_cruza_varios_tramos_devuelve_envolvente_total() -> None:
    mapa = MapaOffsets(
        tramos=[
            Tramo(0, 2, 0, 2),
            Tramo(2, 4, 5, 7),
        ]
    )
    assert mapa.proyectar(1, 3) == (0, 7)


def test_componer_encadena_dos_transformaciones() -> None:
    # texto0 "A    B" (A + 4 espacios + B) -> texto1 "A B" (colapsa los 4 espacios a 1) ->
    # texto2 "AB" (un segundo paso elimina ese espacio por completo).
    mapa_colapso = MapaOffsets(
        tramos=[
            Tramo(0, 1, 0, 1),  # "A"
            Tramo(1, 2, 1, 5),  # "    " (4 espacios) -> " "
            Tramo(2, 3, 5, 6),  # "B"
        ]
    )
    mapa_elimina_espacio = MapaOffsets(
        tramos=[
            Tramo(0, 1, 0, 1),  # "A" (copia)
            # el espacio en texto1 (índice 1) se elimina: sin tramo.
            Tramo(1, 2, 2, 3),  # "B" (copia)
        ]
    )

    compuesto = componer(mapa_colapso, mapa_elimina_espacio)
    assert compuesto.proyectar(0, 1) == (0, 1)  # "A" sigue en su posición original
    assert compuesto.proyectar(1, 2) == (5, 6)  # "B" se rastrea hasta su posición original real
