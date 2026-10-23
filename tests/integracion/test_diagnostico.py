"""Integración de punta a punta del orquestador de diagnóstico (I0) sobre fixtures sintéticos.

Nunca corre contra `data/raw/` ni `data/private/`: todas las rutas usan `tmp_path` o
`tests/fixtures/`.
"""

from pathlib import Path

from decla.calidad.diagnostico import diagnosticar

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_diagnosticar_produce_los_artefactos_esperados(tmp_path: Path) -> None:
    salida = tmp_path / "salida"
    privado = tmp_path / "privado"
    duckdb = tmp_path / "warehouse.duckdb"

    resultado = diagnosticar(
        directorio_entrada=RAIZ_FIXTURES,
        directorio_salida=salida,
        directorio_privado=privado,
        ruta_divipola=RAIZ_FIXTURES / "divipola_sintetico.csv",
        ruta_duckdb=duckdb,
        n_muestra=20,
    )

    assert resultado["n_filas_casos"] > 0
    assert resultado["n_filas_relatos"] > 0

    assert (salida / "informe.md").exists()
    contenido = (salida / "informe.md").read_text(encoding="utf-8")
    assert "actividad institucional registrada" in contenido

    for nombre in [
        "esquema_casos.csv", "esquema_relatos.csv", "cardinalidad.csv", "union_casos_relatos.csv",
        "hipotesis_grano.csv", "caso_noticia_hipotesis.csv", "territorio_resumen.csv",
        "coordenadas_resumen.csv", "fechas_formato.csv", "fechas_orden_logico.csv",
        "fechas_prescripcion.csv", "delito_parseo.csv", "relatos_resumen.csv",
        "temporal_mensual.csv", "temporal_resumen.csv",
    ]:
        assert (salida / nombre).exists(), f"falta {nombre}"

    for nombre in ["volumen_mensual.png", "longitud_relato.png", "top_delitos.png"]:
        assert (salida / nombre).exists(), f"falta {nombre}"

    assert (privado / "muestra_lectura" / "muestra.html").exists()
    assert (privado / "muestra_lectura" / "anotacion.csv").exists()
    assert duckdb.exists()


def test_diagnosticar_sin_divipola_no_falla(tmp_path: Path) -> None:
    salida = tmp_path / "salida"
    privado = tmp_path / "privado"
    duckdb = tmp_path / "warehouse.duckdb"

    resultado = diagnosticar(
        directorio_entrada=RAIZ_FIXTURES,
        directorio_salida=salida,
        directorio_privado=privado,
        ruta_divipola=tmp_path / "no_existe.csv",
        ruta_duckdb=duckdb,
        n_muestra=5,
    )
    assert any("DIVIPOLA" in a for a in resultado["advertencias"])
    assert (salida / "informe.md").exists()
