import duckdb
import numpy as np

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.prediccion.atipicos import (
    calcular_puntajes_isolation_forest,
    calcular_rangos,
    codificar_para_modelo,
    construir_centroides_por_fenomeno,
    construir_matriz_estructurada,
    construir_tabla_atipicos,
    distancia_centroide_mas_cercano,
)


def _conexion_con_atipico(n_normales: int = 30) -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    registros = [
        {
            "caso_notica": f"caso_{i}",
            "delito_nombre": "LAVADO DE ACTIVOS",
            "cod_dpto_hechos": "11",
            "estado_norm": "ACTIVO",
            "etapa_norm": "INDAGACION",
            "dias_hecho_denuncia": 30 + (i % 5),
            "dias_denuncia_creacion": 2,
            "dias_creacion_asignacion": 1,
        }
        for i in range(n_normales)
    ]
    # Un caso claramente atípico: delito raro, departamento raro, rezago enorme.
    registros.append(
        {
            "caso_notica": "caso_atipico",
            "delito_nombre": "USURPACION_DE_PROPIEDAD_INDUSTRIAL",
            "cod_dpto_hechos": "99",
            "estado_norm": "INACTIVO",
            "etapa_norm": "EJECUCION_DE_PENAS",
            "dias_hecho_denuncia": 9000,
            "dias_denuncia_creacion": 500,
            "dias_creacion_asignacion": 400,
        }
    )
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    return conexion


def test_calcular_rangos_ordena_descendente() -> None:
    rangos = calcular_rangos([1.0, 5.0, 3.0])
    assert rangos == [3, 1, 2]  # 5.0 es el más alto -> rango 1


def test_distancia_centroide_mas_cercano_elige_el_mas_cercano() -> None:
    centroides = {
        "a": np.array([1.0, 0.0]),
        "b": np.array([0.0, 1.0]),
    }
    fenomeno, distancia = distancia_centroide_mas_cercano([0.9, 0.1], centroides)
    assert fenomeno == "a"
    assert distancia < 0.1


def test_construir_matriz_estructurada_y_codificar_sin_nan() -> None:
    conexion = _conexion_con_atipico()
    matriz = construir_matriz_estructurada(conexion)
    assert matriz.height == 31
    ids, matriz_numerica = codificar_para_modelo(matriz)
    assert len(ids) == 31
    assert not np.isnan(matriz_numerica).any()
    conexion.close()


def test_calcular_puntajes_isolation_forest_detecta_el_atipico_inyectado() -> None:
    conexion = _conexion_con_atipico()
    matriz = construir_matriz_estructurada(conexion)
    ids, matriz_numerica = codificar_para_modelo(matriz)
    puntajes = calcular_puntajes_isolation_forest(matriz_numerica, semilla=20260101)
    rangos = calcular_rangos(puntajes.tolist())

    indice_atipico = ids.index("caso_atipico")
    assert rangos[indice_atipico] == 1  # el más atípico de todos
    conexion.close()


def test_construir_centroides_por_fenomeno_promedia_embeddings() -> None:
    conexion = duckdb.connect(":memory:")
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [
            {"registro_uid": "uid_1", "codigo_fenomeno": "x"},
            {"registro_uid": "uid_2", "codigo_fenomeno": "x"},
        ],
    )
    embeddings = {"uid_1": [1.0, 0.0], "uid_2": [3.0, 0.0]}
    centroides = construir_centroides_por_fenomeno(conexion, embeddings)
    assert centroides["x"].tolist() == [2.0, 0.0]
    conexion.close()


def test_construir_tabla_atipicos_extremo_a_extremo() -> None:
    """Prueba la unión caso_notica -> registro_uid (texto.relato_procesado) -> embeddings:
    plata.registros_limpios y texto.relato_procesado tienen cada uno su propio registro_uid
    (hashes distintos por tabla de origen, CLAUDE.md §2.4); caso_notica es la llave compartida.
    """
    conexion = _conexion_con_atipico(n_normales=5)
    relato_procesado = [
        {"registro_uid": f"relato_uid_{i}", "caso_notica": f"caso_{i}"} for i in range(5)
    ] + [{"registro_uid": "relato_uid_atipico", "caso_notica": "caso_atipico"}]
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relato_procesado)
    escribir_tabla_polars(
        conexion,
        "fenomenos",
        "asignacion_fenomeno",
        [{"registro_uid": f"relato_uid_{i}", "codigo_fenomeno": "x"} for i in range(5)],
    )
    embeddings = {f"relato_uid_{i}": [1.0, 0.0] for i in range(5)}
    embeddings["relato_uid_atipico"] = [0.0, 1.0]  # semánticamente lejos del centroide de "x"

    filas = construir_tabla_atipicos(conexion, embeddings, run_id="r1")
    assert len(filas) == 6
    fila_atipico = next(f for f in filas if f["caso_notica"] == "caso_atipico")
    assert fila_atipico["fenomeno_mas_cercano"] == "x"
    assert fila_atipico["distancia_centroide"] > 0.5  # lejos, no cerca
    conexion.close()
