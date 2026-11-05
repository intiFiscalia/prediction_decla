from pathlib import Path

import duckdb
import yaml

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.evaluacion.pipeline import ejecutar_evaluacion

METRICAS_PRUEBA = {
    "componentes": [
        {
            "nombre": "Componente de prueba",
            "metrica": "m",
            "valor": "v",
            "umbral": "u",
            "estado": "no_cumple",
            "fuente": "test",
        }
    ]
}

TAXONOMIA_PRUEBA = {
    "fenomenos": [{"codigo": "lavado_de_activos", "nombre": "Lavado de activos"}]
}


def test_ejecutar_evaluacion_sin_tablas_oro_no_falla(tmp_path: Path) -> None:
    """Antes de make prediccion/make emergencia, oro.atipicos y oro.alertas no existen — el
    reporte debe decirlo, no fallar."""
    ruta_duckdb = tmp_path / "warehouse.duckdb"
    duckdb.connect(str(ruta_duckdb)).close()

    ruta_metricas = tmp_path / "metricas.yaml"
    ruta_metricas.write_text(yaml.safe_dump(METRICAS_PRUEBA), encoding="utf-8")
    ruta_taxonomia = tmp_path / "v1.0.yaml"
    ruta_taxonomia.write_text(yaml.safe_dump(TAXONOMIA_PRUEBA), encoding="utf-8")
    ruta_salida = tmp_path / "evaluacion" / "v1.md"

    ruta_resultado = ejecutar_evaluacion(ruta_duckdb, ruta_metricas, ruta_taxonomia, ruta_salida)
    assert ruta_resultado == ruta_salida
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "Componente de prueba" in contenido
    assert "no_cumple" in contenido
    assert "lavado_de_activos" in contenido
    assert "sin correr todavía" in contenido  # ni atípicos ni alertas existen


def test_ejecutar_evaluacion_con_tablas_oro_las_reporta(tmp_path: Path) -> None:
    ruta_duckdb = tmp_path / "warehouse.duckdb"
    conexion = duckdb.connect(str(ruta_duckdb))
    escribir_tabla_polars(
        conexion, "oro", "atipicos", [{"caso_notica": "c1", "puntaje_isolation_forest": 0.5}]
    )
    escribir_tabla_polars(
        conexion, "oro", "alertas", [{"codigo_fenomeno": "x", "estado": "alerta"}]
    )
    conexion.close()

    ruta_metricas = tmp_path / "metricas.yaml"
    ruta_metricas.write_text(yaml.safe_dump(METRICAS_PRUEBA), encoding="utf-8")
    ruta_taxonomia = tmp_path / "v1.0.yaml"
    ruta_taxonomia.write_text(yaml.safe_dump(TAXONOMIA_PRUEBA), encoding="utf-8")
    ruta_salida = tmp_path / "evaluacion" / "v1.md"

    ejecutar_evaluacion(ruta_duckdb, ruta_metricas, ruta_taxonomia, ruta_salida)
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "1 registros evaluados" in contenido
    assert "alerta" in contenido
