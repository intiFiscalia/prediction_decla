from decla.normalizacion.alcance import filtrar_por_alcance, filtrar_por_ruptura


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


def test_filtrar_por_ruptura_excluye_valores_reales() -> None:
    filas = [
        {"RUPTURA": None, "CASO_NOTICIA": "1"},
        {"RUPTURA": "", "CASO_NOTICIA": "2"},
        {"RUPTURA": "  ", "CASO_NOTICIA": "3"},
        {"RUPTURA": '""', "CASO_NOTICIA": "4"},
        {"RUPTURA": "SE ROMPIO POR CONEXIDAD", "CASO_NOTICIA": "5"},
    ]
    sin_ruptura, resumen = filtrar_por_ruptura(filas)

    assert [f["CASO_NOTICIA"] for f in sin_ruptura] == ["1", "2", "3", "4"]
    assert resumen.n_entrada == 5
    assert resumen.n_con_ruptura == 1
    assert resumen.n_sin_ruptura == 4


def test_filtrar_por_ruptura_sin_exclusiones() -> None:
    filas = [{"RUPTURA": None}, {"RUPTURA": ""}]
    sin_ruptura, resumen = filtrar_por_ruptura(filas)
    assert len(sin_ruptura) == 2
    assert resumen.n_con_ruptura == 0


def test_filtrar_por_ruptura_columna_personalizada() -> None:
    filas = [{"otra_columna": "algo"}, {"otra_columna": None}]
    sin_ruptura, resumen = filtrar_por_ruptura(filas, columna_ruptura="otra_columna")
    assert resumen.n_con_ruptura == 1
    assert len(sin_ruptura) == 1
