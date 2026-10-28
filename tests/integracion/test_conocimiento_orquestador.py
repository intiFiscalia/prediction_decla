from pathlib import Path

import duckdb
import pytest

from decla.comun.duckdb_io import conectar
from decla.conocimiento.orquestador import ResumenConocimiento, procesar_conocimiento
from decla.entidades.orquestador import ResumenEntidades, construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata
from decla.texto.orquestador import procesar_texto

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

COLUMNAS_MENCIONES_ESPERADAS = {
    "mencion_id", "registro_uid", "run_id", "categoria", "subcategoria",
    "valor_normalizado", "texto_evidencia", "inicio", "fin", "segmento",
    "origen", "polaridad", "confianza", "extractor", "version_extractor",
    "estado_revision", "revisor", "fecha_revision",
}


@pytest.fixture(scope="module")
def pipeline_completo(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[duckdb.DuckDBPyConnection, ResumenEntidades, ResumenConocimiento]:
    """Corre bronce→plata→entidades→texto(2A)→conocimiento(2B) una sola vez para todo el
    módulo: las pruebas de este archivo son todas de solo lectura sobre el resultado.
    """
    tmp_path = tmp_path_factory.mktemp("conocimiento")
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    resumen_entidades = construir_entidades(conexion, "LOTE1")
    procesar_texto(conexion, "LOTE1", "RUN1", ruta_embeddings_datos=tmp_path / "embeddings")
    resumen_conocimiento = procesar_conocimiento(conexion, "RUN2")
    return conexion, resumen_entidades, resumen_conocimiento


def test_conocimiento_orquestador_extremo_a_extremo(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenEntidades, ResumenConocimiento],
) -> None:
    conexion, resumen_entidades, resumen = pipeline_completo

    assert resumen.n_relatos == resumen_entidades.n_relatos
    assert resumen.n_menciones > 0
    # Una mención de sector por relato (siempre se intenta clasificar, aunque el resultado quede
    # indeterminado); el mecanismo puede quedar sin mención si el texto está vacío.
    assert resumen.n_menciones_por_categoria.get("sector", 0) == resumen.n_relatos
    assert resumen.n_menciones_por_categoria.get("mecanismo", 0) <= resumen.n_relatos
    assert (
        resumen.n_sector_explicito + resumen.n_sector_inferido + resumen.n_sector_indeterminado
        == resumen.n_relatos - resumen.n_sector_sin_texto
    )

    df = conexion.sql("SELECT * FROM texto.menciones").pl()
    assert df.height == resumen.n_menciones
    assert set(df.columns) == COLUMNAS_MENCIONES_ESPERADAS


def test_ninguna_mencion_de_sector_se_asocia_a_persona(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenEntidades, ResumenConocimiento],
) -> None:
    """CLAUDE.md §2.3 / plan_trabajo.md §6.4: el sector se asigna al relato, nunca a una persona
    u organización. La tabla texto.menciones no tiene (ni debe tener) ninguna columna que
    identifique a una persona, y las menciones de sector solo referencian registro_uid.
    """
    conexion, _, _ = pipeline_completo
    df = conexion.sql("SELECT * FROM texto.menciones WHERE categoria = 'sector'").pl()
    assert df.height > 0

    columnas_prohibidas = {"numero_documento", "fiscal_asignado_despacho", "persona", "cedula"}
    assert not (columnas_prohibidas & set(df.columns))
    assert set(df.columns) == COLUMNAS_MENCIONES_ESPERADAS


def test_menciones_sector_quedan_en_valores_validos(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenEntidades, ResumenConocimiento],
) -> None:
    from decla.conocimiento.sectores import SECTOR_INDETERMINADO

    conexion, _, _ = pipeline_completo
    df = conexion.sql(
        "SELECT valor_normalizado FROM texto.menciones WHERE categoria = 'sector'"
    ).pl()
    for valor in df["valor_normalizado"].to_list():
        if valor == SECTOR_INDETERMINADO:
            continue
        assert valor is not None
        assert len(valor) == 4
        assert valor.isdigit()


def test_coincidencias_a_menciones_reutiliza_patrones_de_2a(
    pipeline_completo: tuple[duckdb.DuckDBPyConnection, ResumenEntidades, ResumenConocimiento],
) -> None:
    """La fecha es la única categoría de patrones_regex con cobertura garantizada en los
    fixtures sintéticos (CLAUDE.md §4.12-§4.20): confirma que la reutilización de 2A sí produce
    menciones reales, no solo las de NER/sector/mecanismo.
    """
    conexion, _, resumen = pipeline_completo
    assert resumen.n_menciones_por_categoria.get("fecha", 0) > 0

    df = conexion.sql("SELECT * FROM texto.menciones WHERE categoria = 'fecha' LIMIT 1").pl()
    assert df["extractor"].to_list() == ["patrones_regex"]
    assert df["origen"].to_list() == ["explicito_regla"]
