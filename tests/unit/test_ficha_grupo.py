from decla.fenomenos.ficha_grupo import (
    calcular_c_tfidf,
    distribucion_metadata,
    indicador_dominancia_plantilla,
    indicador_dominancia_unidad,
    menciones_dominantes,
    seleccionar_medoides_y_bordes,
)


def test_calcular_c_tfidf_distingue_terminos_por_grupo() -> None:
    lemas = {
        0: "oro mina extraccion oro mineral oro",
        1: "ganado bovino finca ganado venta ganado",
    }
    resultado = calcular_c_tfidf(lemas, top_n=1)
    assert resultado[0][0][0] == "oro"
    assert resultado[1][0][0] == "ganado"


def test_calcular_c_tfidf_sin_lemas_devuelve_listas_vacias() -> None:
    resultado = calcular_c_tfidf({0: "", 1: ""})
    assert resultado == {0: [], 1: []}


def test_menciones_dominantes_ordena_por_frecuencia() -> None:
    menciones = [
        {"categoria": "sector", "valor_normalizado": "0722"},
        {"categoria": "sector", "valor_normalizado": "0722"},
        {"categoria": "lugar", "valor_normalizado": "CUCUTA"},
    ]
    resultado = menciones_dominantes(menciones)
    assert resultado[0] == ("sector", "0722", round(2 / 3, 4))


def test_menciones_dominantes_vacio() -> None:
    assert menciones_dominantes([]) == []


def test_distribucion_metadata() -> None:
    metadata = [{"departamento": "META"}, {"departamento": "META"}, {"departamento": "CESAR"}]
    resultado = distribucion_metadata(metadata, "departamento")
    assert resultado == {"META": 2, "CESAR": 1}


def test_seleccionar_medoides_y_bordes() -> None:
    vectores = {"a": [0.0, 0.0], "b": [0.1, 0.0], "c": [5.0, 5.0]}
    medoides, bordes = seleccionar_medoides_y_bordes(vectores, n_medoides=2, n_bordes=1)
    assert medoides == ["b", "a"]
    assert bordes == ["c"]


def test_seleccionar_medoides_y_bordes_no_repite_uid_en_ambos() -> None:
    vectores = {"a": [0.0, 0.0]}
    medoides, bordes = seleccionar_medoides_y_bordes(vectores, n_medoides=5, n_bordes=5)
    assert medoides == ["a"]
    assert bordes == []


def test_seleccionar_medoides_y_bordes_vacio() -> None:
    assert seleccionar_medoides_y_bordes({}) == ([], [])


def test_indicador_dominancia_plantilla() -> None:
    metodos = ["sin_marcador", "sin_marcador", "marcador_descripcion_hecho"]
    assert indicador_dominancia_plantilla(metodos) == round(2 / 3, 4)


def test_indicador_dominancia_plantilla_vacio() -> None:
    assert indicador_dominancia_plantilla([]) == 0.0


def test_indicador_dominancia_unidad() -> None:
    unidades = ["11", "11", "11", "50"]
    assert indicador_dominancia_unidad(unidades) == 0.75
