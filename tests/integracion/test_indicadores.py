from pathlib import Path

from decla.analitica import indicadores as ind
from decla.comun.duckdb_io import conectar
from decla.entidades.orquestador import construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_indicadores_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    construir_entidades(conexion, "LOTE1")

    df_volumen = ind.ind_volumen(conexion)
    assert df_volumen.height == 1
    assert df_volumen["n_registros"].item() > 0

    df_delito = ind.ind_composicion_delito(conexion)
    assert df_delito.height > 0
    assert abs(df_delito["pct"].sum() - 100.0) < 0.5

    df_estado_etapa = ind.ind_composicion_estado_etapa(conexion)
    assert df_estado_etapa.height > 0

    df_territorio = ind.ind_territorio_conteo(conexion)
    assert df_territorio.height > 0

    df_lq = ind.ind_territorio_cociente_localizacion(conexion)
    assert df_lq.height > 0
    assert "cociente_localizacion" in df_lq.columns

    df_tasa = ind.ind_territorio_tasa(conexion)
    assert df_tasa.height > 0
    assert "tasa_suavizada_por_100k" in df_tasa.columns
    assert df_tasa["poblacion_total"].null_count() < df_tasa.height  # al menos algo con población

    df_tiempo = ind.ind_tiempo_mensual(conexion)
    assert df_tiempo.height > 0

    df_rezagos = ind.ind_rezagos(conexion)
    assert df_rezagos.height == 1

    df_procesales = ind.ind_procesales(conexion)
    assert df_procesales.height > 0

    df_conexidad = ind.ind_conexidad(conexion)
    assert df_conexidad.height == 1
    assert df_conexidad["n_noticias"].item() > 0

    df_calidad = ind.ind_calidad(conexion)
    assert df_calidad.height > 0

    conexion.close()
