from decla.conocimiento.menciones import (
    ORIGEN_EXPLICITO_REGLA,
    calcular_mencion_id,
    coincidencias_a_menciones,
)
from decla.texto.negacion import AFIRMADA, NEGADA
from decla.texto.patrones_regex import Coincidencia


def test_coincidencias_a_menciones_convierte_solo_categorias_analiticas() -> None:
    coincidencias = [
        Coincidencia("articulo_penal", "Art. 323", 0, 8, valor_normalizado="323"),
        Coincidencia("placa", "ABC123", 20, 26),
        Coincidencia("monto", "$50.000.000", 30, 41),
    ]
    menciones = coincidencias_a_menciones(coincidencias, "u1", "r1", "descripcion_hecho")
    categorias = {m.categoria for m in menciones}
    assert categorias == {"articulo_penal", "monto"}
    assert len(menciones) == 2


def test_coincidencias_a_menciones_subpartida_mapea_a_bien() -> None:
    coincidencias = [
        Coincidencia("subpartida", "2402.20.00.00", 0, 13, valor_normalizado="2402.20.00.00")
    ]
    menciones = coincidencias_a_menciones(coincidencias, "u1", "r1", "descripcion_hecho")
    assert menciones[0].categoria == "bien"
    assert menciones[0].subcategoria == "subpartida_arancelaria"


def test_coincidencias_a_menciones_sin_polaridad_queda_afirmada() -> None:
    coincidencias = [Coincidencia("monto", "$1.000.000", 0, 10)]
    menciones = coincidencias_a_menciones(coincidencias, "u1", "r1", "descripcion_hecho")
    assert menciones[0].polaridad == AFIRMADA


def test_coincidencias_a_menciones_usa_polaridad_dada() -> None:
    coincidencias = [Coincidencia("monto", "$1.000.000", 0, 10)]
    menciones = coincidencias_a_menciones(
        coincidencias, "u1", "r1", "descripcion_hecho", polaridad_por_coincidencia={0: NEGADA}
    )
    assert menciones[0].polaridad == NEGADA


def test_coincidencias_a_menciones_campos_basicos() -> None:
    coincidencias = [Coincidencia("articulo_penal", "artículo 323", 5, 17, valor_normalizado="323")]
    menciones = coincidencias_a_menciones(coincidencias, "u1", "r1", "descripcion_hecho")
    mencion = menciones[0]
    assert mencion.registro_uid == "u1"
    assert mencion.run_id == "r1"
    assert mencion.segmento == "descripcion_hecho"
    assert mencion.origen == ORIGEN_EXPLICITO_REGLA
    assert mencion.confianza == 1.0
    assert mencion.estado_revision == "pendiente"
    assert mencion.valor_normalizado == "323"


def test_calcular_mencion_id_es_deterministico() -> None:
    id_a = calcular_mencion_id("u1", "monto", None, 0, 10, "patrones_regex")
    id_b = calcular_mencion_id("u1", "monto", None, 0, 10, "patrones_regex")
    id_c = calcular_mencion_id("u1", "monto", None, 0, 11, "patrones_regex")
    assert id_a == id_b
    assert id_a != id_c
