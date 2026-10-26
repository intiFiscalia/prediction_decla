from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.entidades.orquestador import construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_bronce_plata_entidades_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    resumen_plata = procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    resumen_entidades = construir_entidades(conexion, "LOTE1")

    # Los fixtures plantan duplicados a propósito (CLAUDE.md §4.2): una noticia puede tener más
    # de una fila en registros_limpios (multidelito), así que el número de noticias/casos únicos
    # es <= el número de filas, nunca al revés.
    n_caso_notica_unicos = conexion.execute(
        "SELECT count(DISTINCT caso_notica) FROM plata.registros_limpios"
    ).fetchone()[0]
    n_caso_id_unicos = conexion.execute(
        "SELECT count(DISTINCT caso_id) FROM plata.registros_limpios"
    ).fetchone()[0]
    assert resumen_entidades.n_noticias == n_caso_notica_unicos
    assert resumen_entidades.n_casos == n_caso_id_unicos
    assert resumen_entidades.n_noticias <= resumen_plata.n_registros_limpios
    assert resumen_entidades.n_relatos + resumen_entidades.n_relatos_huerfanos > 0

    n_noticia_criminal = conexion.execute(
        "SELECT count(*) FROM entidades.noticia_criminal"
    ).fetchone()[0]
    assert n_noticia_criminal == resumen_entidades.n_noticias

    for tabla in [
        "noticia_criminal", "caso", "grupo_conexo",
        "puente_noticia_delito", "puente_registro_noticia_caso",
    ]:
        conexion.execute(f"SELECT * FROM entidades.{tabla} LIMIT 1")

    conexion.close()
