from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import pytest
import yaml

from decla.comun.duckdb_io import conectar
from decla.conocimiento.orquestador import procesar_conocimiento
from decla.entidades.orquestador import construir_entidades
from decla.fenomenos.estabilidad import precision_recuperacion_fenomeno
from decla.fenomenos.herramienta_revision import (
    APROBAR,
    cargar_decisiones,
    generar_caso_intrusion,
    guardar_decision,
)
from decla.fenomenos.orquestador import ResumenFenomenos, procesar_fenomenos
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata
from decla.texto.orquestador import procesar_texto

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pipeline_completo(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path]:
    """Corre bronce→plata→entidades→texto(2A)→conocimiento(2B)→fenómenos(2C) una sola vez."""
    tmp_path = tmp_path_factory.mktemp("fenomenos")
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    construir_entidades(conexion, "LOTE1")
    procesar_texto(conexion, "LOTE1", "RUN1", ruta_embeddings_datos=tmp_path / "embeddings")
    procesar_conocimiento(conexion, "RUN2")

    ruta_taxonomia = tmp_path / "taxonomia" / "v0.1-borrador.yaml"
    resumen = procesar_fenomenos(
        conexion,
        "LOTE1",
        "RUN3",
        ruta_embeddings_datos=tmp_path / "embeddings",
        ruta_taxonomia_borrador=ruta_taxonomia,
    )
    return conexion, resumen, ruta_taxonomia


def test_fenomenos_orquestador_extremo_a_extremo(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path],
) -> None:
    conexion, resumen, _ = pipeline_completo

    n_relatos_texto = conexion.sql("SELECT count(*) AS n FROM texto.relato_procesado").pl()[
        "n"
    ].item()
    assert resumen.n_relatos == n_relatos_texto

    assert resumen.n_grupos_hdbscan > 0
    assert 0.0 <= resumen.pct_ruido_hdbscan <= 1.0
    assert resumen.n_grupos_kmeans > 0
    assert resumen.n_grupos_nmf > 0
    assert resumen.n_grupos_agglomerative > 0

    for estabilidad in (
        resumen.estabilidad_hdbscan,
        resumen.estabilidad_kmeans,
        resumen.estabilidad_nmf,
        resumen.estabilidad_agglomerative,
    ):
        assert -1.0 <= estabilidad.ari_promedio <= 1.0
        assert estabilidad.n_corridas > 0


def test_tabla_grupos_descubiertos_y_asignacion(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path],
) -> None:
    conexion, resumen, _ = pipeline_completo

    grupos = conexion.sql("SELECT * FROM fenomenos.grupos_descubiertos").pl()
    assert grupos.height == resumen.n_grupos_hdbscan
    assert {"grupo_id", "n_miembros", "terminos_c_tfidf", "medoides", "bordes"} <= set(
        grupos.columns
    )

    asignacion = conexion.sql("SELECT * FROM fenomenos.grupo_asignacion_borrador").pl()
    assert asignacion.height == resumen.n_relatos
    assert set(asignacion.columns) == {"registro_uid", "grupo_id", "run_id"}


def test_taxonomia_borrador_no_es_v1(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path],
) -> None:
    _, _, ruta_taxonomia = pipeline_completo
    assert ruta_taxonomia.exists()
    contenido = yaml.safe_load(ruta_taxonomia.read_text(encoding="utf-8"))
    assert contenido["version"] == "0.1-borrador"
    assert all(grupo["estado"] == "pendiente_revision" for grupo in contenido["grupos"])
    # nunca se escribe sobre config/taxonomia/v1.0.yaml del repo real desde una prueba
    assert not (RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml").exists()


def test_recuperacion_de_fenomeno_plantado_supera_el_azar(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path],
) -> None:
    """No es una compuerta dura (eso lo decide el taller, plan_trabajo.md §7.2): solo confirma
    que el agrupamiento recupera algo de señal real sobre las fixtures, no puro ruido. Un valor
    bajo es un hallazgo esperado y documentado (ADR 0010), no una falla de esta prueba.
    """
    conexion, _, _ = pipeline_completo

    asignacion = conexion.sql(
        "SELECT a.registro_uid, a.grupo_id, r.caso_notica "
        "FROM fenomenos.grupo_asignacion_borrador a "
        "JOIN entidades.relato r ON a.registro_uid = r.registro_uid"
    ).pl()
    verdad = pl.read_parquet(RAIZ_FIXTURES / "verdad.parquet")
    fenomeno_por_caso = dict(
        zip(verdad["caso_noticia"].to_list(), verdad["fenomeno_plantado"].to_list(), strict=False)
    )

    etiquetas = asignacion["grupo_id"].to_list()
    fenomenos_en_orden = [
        fenomeno_por_caso.get(caso, "desconocido") for caso in asignacion["caso_notica"].to_list()
    ]
    precision = precision_recuperacion_fenomeno(
        np.array([int(e) for e in etiquetas]), fenomenos_en_orden
    )
    n_fenomenos_plantados = verdad["fenomeno_plantado"].n_unique()
    azar = 1 / n_fenomenos_plantados
    assert precision > azar


def test_herramienta_revision_funciona_sobre_grupos_reales(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenFenomenos, Path],
) -> None:
    conexion, _, _ = pipeline_completo
    asignacion = conexion.sql(
        "SELECT registro_uid, grupo_id FROM fenomenos.grupo_asignacion_borrador"
    ).pl()

    grupos_unicos = asignacion["grupo_id"].unique().to_list()
    assert len(grupos_unicos) >= 2

    grupo_a = grupos_unicos[0]
    registros_a = asignacion.filter(pl.col("grupo_id") == grupo_a)["registro_uid"].to_list()
    registros_otros = asignacion.filter(pl.col("grupo_id") != grupo_a)["registro_uid"].to_list()

    caso = generar_caso_intrusion(grupo_a, registros_a, registros_otros, semilla=1)
    if len(registros_a) >= 5 and registros_otros:
        assert caso is not None
        assert len(caso.registros_uid_mostrados) == 6

    guardar_decision(conexion, grupo_a, APROBAR, "analista_prueba")
    decisiones = cargar_decisiones(conexion)
    assert any(d["grupo_id"] == grupo_a and d["decision"] == APROBAR for d in decisiones)
