from decla.ingesta.lote import calcular_deriva_lote, clasificar_filas, hash_contenido_fila


def test_hash_contenido_fila_ignora_columnas_de_linaje() -> None:
    fila_a = {"CASO_NOTICIA": "1", "ESTADO": "ACTIVO", "registro_uid": "uid_a", "lote_id": "L1"}
    fila_b = {"CASO_NOTICIA": "1", "ESTADO": "ACTIVO", "registro_uid": "uid_b", "lote_id": "L2"}
    assert hash_contenido_fila(fila_a) == hash_contenido_fila(fila_b)


def test_hash_contenido_fila_detecta_cambio_real() -> None:
    fila_a = {"CASO_NOTICIA": "1", "ESTADO": "ACTIVO"}
    fila_b = {"CASO_NOTICIA": "1", "ESTADO": "INACTIVO"}
    assert hash_contenido_fila(fila_a) != hash_contenido_fila(fila_b)


def test_clasificar_filas_nuevo_repetido_modificado() -> None:
    existentes = [
        {"CASO_NOTICIA": "1", "ESTADO": "ACTIVO", "ETAPA": "INDAGACION"},
        {"CASO_NOTICIA": "2", "ESTADO": "ACTIVO", "ETAPA": "INDAGACION"},
    ]
    nuevas = [
        {"CASO_NOTICIA": "1", "ESTADO": "ACTIVO", "ETAPA": "INDAGACION"},  # repetido
        {"CASO_NOTICIA": "2", "ESTADO": "ACTIVO", "ETAPA": "JUICIO"},  # modificado (ETAPA)
        {"CASO_NOTICIA": "3", "ESTADO": "ACTIVO", "ETAPA": "INDAGACION"},  # nuevo
    ]
    resultado = clasificar_filas(nuevas, existentes, lote_id_nuevo="L2")

    assert len(resultado.nuevos) == 1
    assert resultado.nuevos[0]["CASO_NOTICIA"] == "3"
    assert len(resultado.repetidos) == 1
    assert resultado.repetidos[0]["CASO_NOTICIA"] == "1"
    assert len(resultado.modificados) == 1
    assert resultado.modificados[0]["CASO_NOTICIA"] == "2"

    assert len(resultado.cambios) == 1
    cambio = resultado.cambios[0]
    assert cambio["caso_notica"] == "2"
    assert cambio["campo"] == "ETAPA"
    assert cambio["valor_anterior"] == "INDAGACION"
    assert cambio["valor_nuevo"] == "JUICIO"
    assert cambio["lote_id_nuevo"] == "L2"


def test_clasificar_filas_sin_historico_todo_es_nuevo() -> None:
    nuevas = [{"CASO_NOTICIA": "1", "ESTADO": "ACTIVO"}]
    resultado = clasificar_filas(nuevas, [], lote_id_nuevo="L1")
    assert len(resultado.nuevos) == 1
    assert resultado.repetidos == []
    assert resultado.modificados == []


def test_calcular_deriva_lote_detecta_categoria_nueva() -> None:
    historicas = [{"DELITO": "LAVADO DE ACTIVOS", "DEPARTAMENTO_HECHOS": "BOGOTA"}] * 20
    nuevas = [{"DELITO": "CONTRABANDO", "DEPARTAMENTO_HECHOS": "BOGOTA"}] * 10
    deriva = calcular_deriva_lote(nuevas, historicas)
    assert deriva["psi_delito"] > 0.25  # categoría nueva que domina el lote nuevo
    assert deriva["n_historico"] == 20
    assert deriva["n_nuevo"] == 10
