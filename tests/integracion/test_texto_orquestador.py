from pathlib import Path

import polars as pl

from decla.comun.duckdb_io import conectar
from decla.entidades.orquestador import construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata
from decla.texto.orquestador import procesar_texto

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_texto_orquestador_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    resumen_entidades = construir_entidades(conexion, "LOTE1")

    directorio_embeddings = tmp_path / "embeddings"
    resumen_texto = procesar_texto(
        conexion, "LOTE1", "RUN1", ruta_embeddings_datos=directorio_embeddings
    )

    assert resumen_texto.n_relatos == resumen_entidades.n_relatos
    assert resumen_texto.n_relatos_en_grupo_duplicado <= resumen_texto.n_relatos
    assert resumen_texto.n_grupos_duplicados <= resumen_texto.n_relatos_en_grupo_duplicado
    assert resumen_texto.version_modelo_embeddings

    df_procesado = conexion.sql("SELECT * FROM texto.relato_procesado").pl()
    assert df_procesado.height == resumen_texto.n_relatos
    uids_entidades_relato = conexion.sql("SELECT registro_uid FROM entidades.relato").pl()
    assert set(df_procesado["registro_uid"].to_list()) == set(
        uids_entidades_relato["registro_uid"].to_list()
    )
    # El texto enmascarado nunca debe contener el marcador "[DOC]" sin que hubiera un disparador
    # de documento; lo que sí se exige es que nunca quede vacío cuando había relato normalizado.
    assert df_procesado.filter(pl.col("relato_normalizado") != "").select(
        pl.col("relato_enmascarado").is_not_null().all()
    ).item()

    ruta_relato_parquet = directorio_embeddings / "LOTE1" / "relato.parquet"
    ruta_segmento_parquet = directorio_embeddings / "LOTE1" / "segmento.parquet"
    assert ruta_relato_parquet.exists()
    assert ruta_segmento_parquet.exists()

    df_embeddings_relato = pl.read_parquet(ruta_relato_parquet)
    assert set(df_embeddings_relato.columns) == {
        "registro_uid", "version_modelo", "agregacion", "vector",
    }
    assert set(df_embeddings_relato["agregacion"].unique().to_list()) <= {"media", "maximo"}

    conexion.close()
