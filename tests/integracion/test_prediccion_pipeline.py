from pathlib import Path

import duckdb
import polars as pl

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.prediccion.orquestador import procesar_atipicos


def test_procesar_atipicos_lee_parquet_real_y_escribe_oro(tmp_path: Path) -> None:
    conexion = duckdb.connect(":memory:")
    registros = [
        {
            "caso_notica": f"caso_{i}",
            "delito_nombre": "LAVADO DE ACTIVOS",
            "cod_dpto_hechos": "11",
            "estado_norm": "ACTIVO",
            "etapa_norm": "INDAGACION",
            "dias_hecho_denuncia": 30,
            "dias_denuncia_creacion": 2,
            "dias_creacion_asignacion": 1,
        }
        for i in range(10)
    ]
    relato_procesado = [
        {"registro_uid": f"uid_{i}", "caso_notica": f"caso_{i}"} for i in range(10)
    ]
    asignacion = [
        {"registro_uid": f"uid_{i}", "codigo_fenomeno": "lavado_de_activos"} for i in range(10)
    ]
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relato_procesado)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)

    directorio_embeddings = tmp_path / "embeddings" / "LOTE1"
    directorio_embeddings.mkdir(parents=True)
    pl.DataFrame(
        {
            "registro_uid": [f"uid_{i}" for i in range(10)],
            "version_modelo": ["modelo-x"] * 10,
            "agregacion": ["media"] * 10,
            "vector": [[1.0, 0.0] for _ in range(10)],
        }
    ).write_parquet(directorio_embeddings / "relato.parquet")

    resumen = procesar_atipicos(
        conexion,
        lote_id_embeddings="LOTE1",
        ruta_embeddings_datos=tmp_path / "embeddings",
        run_id="r1",
    )
    assert resumen.n_registros == 10

    tabla = conexion.sql("SELECT * FROM oro.atipicos").pl()
    assert tabla.height == 10
    assert set(tabla["rank_isolation_forest"].to_list()) == set(range(1, 11))
    conexion.close()
