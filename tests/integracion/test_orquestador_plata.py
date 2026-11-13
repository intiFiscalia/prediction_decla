"""Integración del orquestador de plata sobre fixtures sintéticos (nunca contra data/raw real)."""

from pathlib import Path

from decla.comun.duckdb_io import conectar
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_procesar_plata_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)

    resumen = procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )

    assert resumen.n_entrada > 0
    assert resumen.n_cuarentena >= 0
    assert resumen.n_con_ruptura >= 0
    assert resumen.n_registros_limpios == (
        resumen.n_entrada
        - resumen.n_cuarentena
        - resumen.n_fuera_alcance
        - resumen.n_con_ruptura
    )

    n_plata = conexion.execute("SELECT count(*) FROM plata.registros_limpios").fetchone()[0]
    assert n_plata == resumen.n_registros_limpios

    # columnas clave presentes
    columnas = {
        c[0]
        for c in conexion.execute("DESCRIBE plata.registros_limpios").fetchall()
    }
    for esperada in [
        "cn_dane", "cod_mpio_hechos", "calidad_coord_hechos", "delito_nombre",
        "numero_documento_token", "fiscal_asignado_token", "dias_hecho_denuncia",
    ]:
        assert esperada in columnas, f"falta columna {esperada}"

    # seudonimización: el token no debe contener el documento original
    fila = conexion.execute(
        "SELECT numero_documento_token FROM plata.registros_limpios "
        "WHERE numero_documento_token IS NOT NULL LIMIT 1"
    ).fetchone()
    if fila:
        assert len(fila[0]) == 64  # hexdigest de sha256

    for tabla in ["dim_territorio", "dim_tiempo", "dim_despacho", "dim_delito", "reporte_calidad"]:
        n = conexion.execute(f"SELECT count(*) FROM plata.{tabla}").fetchone()[0]
        assert n > 0, f"plata.{tabla} está vacía"

    conexion.close()
