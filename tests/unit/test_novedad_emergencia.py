import numpy as np

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.emergencia.novedad import (
    deriva_centroide,
    divergencia_js_vocabulario,
    novedad_combinatoria,
)


def test_divergencia_js_identicos_es_cero() -> None:
    d = divergencia_js_vocabulario({"a": 10, "b": 5}, {"a": 10, "b": 5})
    assert abs(d) < 1e-9


def test_divergencia_js_disjuntos_es_maxima() -> None:
    d = divergencia_js_vocabulario({"a": 10}, {"b": 10})
    assert abs(d - 1.0) < 1e-6


def test_deriva_centroide_mismo_vector_es_cero() -> None:
    v = np.array([1.0, 2.0, 3.0])
    assert abs(deriva_centroide(v, v)) < 1e-9


def test_deriva_centroide_vectores_ortogonales_es_uno() -> None:
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(deriva_centroide(a, b) - 1.0) < 1e-9


def test_novedad_combinatoria_detecta_combinacion_nueva() -> None:
    import duckdb

    conexion = duckdb.connect(":memory:")
    relatos = [{"registro_uid": f"uid_{i}", "caso_notica": f"caso_{i}"} for i in range(6)]
    registros = [
        # periodo 1 (base): solo fenómeno "x" en territorio "11"
        {"caso_notica": "caso_0", "cod_dpto_hechos": "11", "anio_iso_creacion": 2026,
         "mes_creacion": 1, "fecha_creacion_valida": True},
        {"caso_notica": "caso_1", "cod_dpto_hechos": "11", "anio_iso_creacion": 2026,
         "mes_creacion": 1, "fecha_creacion_valida": True},
        # periodo 2 (reciente): fenómeno "x" en territorio "05" -> combinación nueva
        {"caso_notica": "caso_2", "cod_dpto_hechos": "05", "anio_iso_creacion": 2026,
         "mes_creacion": 2, "fecha_creacion_valida": True},
        {"caso_notica": "caso_3", "cod_dpto_hechos": "05", "anio_iso_creacion": 2026,
         "mes_creacion": 2, "fecha_creacion_valida": True},
        # y sigue también en "11" (combinación vieja, no debe aparecer como nueva)
        {"caso_notica": "caso_4", "cod_dpto_hechos": "11", "anio_iso_creacion": 2026,
         "mes_creacion": 2, "fecha_creacion_valida": True},
        {"caso_notica": "caso_5", "cod_dpto_hechos": "11", "anio_iso_creacion": 2026,
         "mes_creacion": 2, "fecha_creacion_valida": True},
    ]
    asignacion = [{"registro_uid": f"uid_{i}", "codigo_fenomeno": "x"} for i in range(6)]
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    escribir_tabla_polars(
        conexion,
        "texto",
        "menciones",
        [
            {
                "registro_uid": "uid_no_existe", "categoria": "sector",
                "valor_normalizado": "x", "polaridad": "afirmada",
            }
        ],
    )

    indice_periodo_2 = 2026 * 12 + 2
    resultado = novedad_combinatoria(conexion, indice_periodo_corte=indice_periodo_2)
    assert resultado.height == 1
    fila = resultado.row(0, named=True)
    assert fila["codigo_fenomeno"] == "x"
    assert fila["territorio"] == "05"
    conexion.close()
