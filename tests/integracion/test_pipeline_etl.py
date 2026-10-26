from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.ingesta.pipeline import ejecutar_etl

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_ejecutar_etl_extremo_a_extremo(tmp_path: Path) -> None:
    resultado = ejecutar_etl(
        directorio_entrada=RAIZ_FIXTURES,
        directorio_lotes=tmp_path / "lotes",
        ruta_duckdb=tmp_path / "warehouse.duckdb",
        lote_id="LOTE_PRUEBA",
        ruta_clave_hmac=tmp_path / "claves" / "hmac.key",
    )

    assert resultado.lote_id == "LOTE_PRUEBA"
    assert resultado.run_id
    assert len(resultado.bronce) == 2
    assert resultado.plata.n_registros_limpios > 0
    assert resultado.entidades.n_noticias > 0

    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=True)
    n_ejecuciones = conexion.execute(
        "SELECT count(*) FROM meta.ejecuciones WHERE paso = 'etl'"
    ).fetchone()[0]
    assert n_ejecuciones == 1
    conexion.close()
