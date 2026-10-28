import duckdb

from decla.fenomenos.representacion import construir_matriz, construir_vector_menciones


def test_construir_matriz_sin_menciones() -> None:
    embeddings = {"u2": [1.0, 2.0], "u1": [3.0, 4.0]}
    resultado = construir_matriz(embeddings)
    assert resultado.registros_uid == ["u1", "u2"]  # orden determinista (ordenado)
    assert resultado.matriz.tolist() == [[3.0, 4.0], [1.0, 2.0]]


def test_construir_matriz_con_menciones_concatena() -> None:
    embeddings = {"u1": [1.0, 2.0]}
    menciones = {"u1": [0.5, 0.5]}
    resultado = construir_matriz(embeddings, menciones, n_categorias_menciones=2)
    assert resultado.matriz.tolist() == [[1.0, 2.0, 0.5, 0.5]]


def test_construir_matriz_con_menciones_faltantes_usa_ceros() -> None:
    embeddings = {"u1": [1.0, 2.0], "u2": [3.0, 4.0]}
    menciones = {"u1": [0.5, 0.5]}  # u2 no tiene menciones
    resultado = construir_matriz(embeddings, menciones, n_categorias_menciones=2)
    assert resultado.matriz.tolist() == [[1.0, 2.0, 0.5, 0.5], [3.0, 4.0, 0.0, 0.0]]


def test_construir_matriz_vacia() -> None:
    resultado = construir_matriz({})
    assert resultado.registros_uid == []


def test_construir_vector_menciones_normaliza_por_total() -> None:
    conexion = duckdb.connect(":memory:")
    conexion.execute("CREATE SCHEMA texto")
    conexion.execute(
        "CREATE TABLE texto.menciones (registro_uid VARCHAR, categoria VARCHAR)"
    )
    conexion.execute(
        "INSERT INTO texto.menciones VALUES "
        "('u1','monto'), ('u1','monto'), ('u1','lugar'), ('u2','sector')"
    )

    vectores = construir_vector_menciones(conexion, ["monto", "lugar", "sector"])
    assert vectores["u1"] == [2 / 3, 1 / 3, 0.0]
    assert vectores["u2"] == [0.0, 0.0, 1.0]
    conexion.close()
