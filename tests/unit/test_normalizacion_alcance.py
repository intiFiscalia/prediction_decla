from decla.normalizacion.alcance import filtrar_por_alcance


def test_filtrar_por_alcance_separa_dentro_y_fuera() -> None:
    filas = [
        {"SECC_DESCRIPCION": "LAVADO DE ACTIVOS", "X": "1"},
        {"SECC_DESCRIPCION": "DELITOS FISCALES", "X": "2"},
        {"SECC_DESCRIPCION": "LAVADO DE ACTIVOS", "X": "3"},
        {"SECC_DESCRIPCION": None, "X": "4"},
    ]
    dentro, resumen = filtrar_por_alcance(filas, "SECC_DESCRIPCION", {"LAVADO DE ACTIVOS"})

    assert len(dentro) == 2
    assert resumen.n_entrada == 4
    assert resumen.n_dentro_alcance == 2
    assert resumen.n_fuera_alcance == 2
    assert resumen.valores_excluidos == {"DELITOS FISCALES": 1, "(vacío)": 1}


def test_filtrar_por_alcance_todas_dentro() -> None:
    filas = [{"SECC": "A"}, {"SECC": "A"}]
    dentro, resumen = filtrar_por_alcance(filas, "SECC", {"A"})
    assert len(dentro) == 2
    assert resumen.n_fuera_alcance == 0
    assert resumen.valores_excluidos == {}
