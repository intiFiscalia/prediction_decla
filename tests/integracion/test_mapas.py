from pathlib import Path

from decla.analitica.mapas import (
    generar_mapa_departamental,
    generar_mapa_municipal,
    matriz_origen_destino,
)
from decla.comun.duckdb_io import conectar
from decla.entidades.orquestador import construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _preparar(tmp_path: Path):
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    construir_entidades(conexion, "LOTE1")
    return conexion


def test_matriz_origen_destino(tmp_path: Path) -> None:
    conexion = _preparar(tmp_path)
    df = matriz_origen_destino(conexion)
    assert df.height > 0
    assert {"cod_dpto_hechos", "cod_dpto_unidad", "n_registros"} <= set(df.columns)
    conexion.close()


def test_generar_mapa_departamental(tmp_path: Path) -> None:
    conexion = _preparar(tmp_path)
    ruta_salida = tmp_path / "salida" / "mapa_dpto.png"
    generar_mapa_departamental(conexion, ruta_salida)
    assert ruta_salida.exists()
    assert ruta_salida.stat().st_size > 0
    conexion.close()


def test_generar_mapa_municipal(tmp_path: Path) -> None:
    conexion = _preparar(tmp_path)
    ruta_salida = tmp_path / "salida" / "mapa_mpio.png"
    generar_mapa_municipal(conexion, ruta_salida)
    assert ruta_salida.exists()
    assert ruta_salida.stat().st_size > 0
    conexion.close()


def test_mapas_misma_escala_entre_llamadas(tmp_path: Path) -> None:
    conexion = _preparar(tmp_path)
    ruta1 = tmp_path / "mapa1.png"
    ruta2 = tmp_path / "mapa2.png"
    generar_mapa_departamental(conexion, ruta1, vmin=0, vmax=100)
    generar_mapa_departamental(conexion, ruta2, vmin=0, vmax=100)
    assert ruta1.exists() and ruta2.exists()
    conexion.close()
