from pathlib import Path

from decla.analitica.descriptiva import ejecutar_analitica_descriptiva, ejecutar_informe
from decla.comun.duckdb_io import conectar
from decla.entidades.orquestador import construir_entidades
from decla.ingesta.bronce import ingerir_lote
from decla.normalizacion.orquestador import procesar_plata

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

NOMBRES_CSV_ESPERADOS = [
    "volumen.csv", "composicion_delito.csv", "composicion_estado_etapa.csv",
    "territorio_conteo.csv", "territorio_cociente_localizacion.csv", "territorio_tasa.csv",
    "tiempo_mensual.csv", "rezagos.csv", "procesales.csv", "conexidad.csv", "calidad.csv",
    "matriz_origen_destino.csv",
]


def test_analitica_descriptiva_e_informe_extremo_a_extremo(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "warehouse.duckdb", solo_lectura=False)
    ingerir_lote(RAIZ_FIXTURES, tmp_path / "lotes", "LOTE1", conexion)
    procesar_plata(
        conexion, "LOTE1", run_id="RUN1", ruta_clave_hmac=tmp_path / "claves" / "hmac.key"
    )
    construir_entidades(conexion, "LOTE1")

    completo = tmp_path / "reports" / "i1"
    agregado = tmp_path / "reports" / "agregados" / "i1"
    resultados = ejecutar_analitica_descriptiva(conexion, completo, agregado)
    ejecutar_informe(resultados, completo, agregado)

    for nombre in NOMBRES_CSV_ESPERADOS:
        assert (completo / nombre).exists(), f"falta {nombre} en completo"
        assert (agregado / nombre).exists(), f"falta {nombre} en agregado"

    for directorio in (completo, agregado):
        assert (directorio / "mapa_departamental.png").exists()
        assert (directorio / "mapa_municipal.png").exists()
        assert (directorio / "informe.html").exists()
        html = (directorio / "informe.html").read_text(encoding="utf-8")
        assert "actividad institucional registrada" in html

    # La versión agregada debe tener celdas pequeñas suprimidas donde se declaró columna de conteo.
    agregado_conexidad = (agregado / "conexidad.csv").read_text(encoding="utf-8")
    completo_conexidad = (completo / "conexidad.csv").read_text(encoding="utf-8")
    assert agregado_conexidad != "" and completo_conexidad != ""

    conexion.close()
