from pathlib import Path

import duckdb
import yaml

from decla.analitica.pipeline import ejecutar_analitica
from decla.comun.duckdb_io import escribir_tabla_polars

TAXONOMIA = {
    "version": "1.0",
    "fenomenos": [
        {
            "codigo": "lavado_de_activos",
            "nombre": "Lavado de activos",
            "grupo_id_origen": "hdbscan_0",
            "metodo_origen": "hdbscan",
        },
        {
            "codigo": "organizacion_criminal",
            "nombre": "Organización criminal",
            "grupo_id_origen": "nmf_3",
            "metodo_origen": "nmf",
        },
    ],
}


def _preparar_base(ruta_duckdb: Path) -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(str(ruta_duckdb))
    relatos, registros, borrador, menciones = [], [], [], []
    for i in range(12):
        uid, caso = f"uid_{i}", f"caso_{i}"
        relatos.append({"registro_uid": uid, "caso_notica": caso})
        registros.append(
            {
                "caso_notica": caso,
                "delito_nombre": "LAVADO DE ACTIVOS" if i % 2 == 0 else "CONTRABANDO",
                "cod_dpto_hechos": "11" if i % 3 == 0 else "05",
                "cod_mpio_hechos": "11001" if i % 3 == 0 else "05001",
                "cod_dpto_unidad": "11",
                "lat_hechos": 4.6 + i * 0.001,
                "long_hechos": -74.08 - i * 0.001,
                "calidad_coord_hechos": "exacta",
                "desp_id": f"D{i % 2}",
            }
        )
        borrador.append(
            {
                "registro_uid": uid,
                "grupo_id": "hdbscan_0" if i % 2 == 0 else "nmf_3",
                "metodo": "hdbscan" if i % 2 == 0 else "nmf",
            }
        )
        menciones.append(
            {
                "registro_uid": uid,
                "categoria": "sector",
                "origen": "explicito_regla" if i % 2 == 0 else "inferido_modelo",
                "valor_normalizado": "4661" if i % 2 == 0 else "indeterminado",
                "polaridad": "afirmada",
            }
        )
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "grupo_asignacion_borrador", borrador)
    escribir_tabla_polars(conexion, "texto", "menciones", menciones)
    conexion.close()
    return conexion


def test_ejecutar_analitica_extremo_a_extremo(tmp_path: Path) -> None:
    ruta_duckdb = tmp_path / "warehouse.duckdb"
    _preparar_base(ruta_duckdb)

    ruta_taxonomia = tmp_path / "v1.0.yaml"
    ruta_taxonomia.write_text(yaml.safe_dump(TAXONOMIA), encoding="utf-8")

    run_id, resumen = ejecutar_analitica(
        ruta_duckdb=ruta_duckdb,
        ruta_taxonomia=ruta_taxonomia,
        directorio_completo=tmp_path / "reports" / "i3",
        directorio_agregado=tmp_path / "reports" / "agregados_i3",
    )

    assert run_id
    assert resumen["n_filas_asignacion_fenomeno"] == 12  # 6 + 6, sin solape en este fixture

    conexion = duckdb.connect(str(ruta_duckdb), read_only=True)
    asignacion = conexion.sql("SELECT * FROM fenomenos.asignacion_fenomeno").pl()
    assert asignacion.height == 12
    assert set(asignacion["codigo_fenomeno"].unique().to_list()) == {
        "lavado_de_activos",
        "organizacion_criminal",
    }
    conexion.close()

    directorio_completo = tmp_path / "reports" / "i3"
    directorio_agregado = tmp_path / "reports" / "agregados_i3"
    for nombre in resumen["tablas_exportadas"]:
        assert (directorio_completo / f"{nombre}.csv").exists()
        assert (directorio_agregado / f"{nombre}.csv").exists()
    assert (directorio_completo / "mapa_flujos.png").exists()
    assert (directorio_agregado / "mapa_flujos.png").exists()


def test_ejecutar_analitica_es_idempotente(tmp_path: Path) -> None:
    """Correr dos veces sobre la misma base no debe acumular filas duplicadas en
    fenomenos.asignacion_fenomeno (escribir_tabla_polars reemplaza la tabla, no inserta)."""
    ruta_duckdb = tmp_path / "warehouse.duckdb"
    _preparar_base(ruta_duckdb)
    ruta_taxonomia = tmp_path / "v1.0.yaml"
    ruta_taxonomia.write_text(yaml.safe_dump(TAXONOMIA), encoding="utf-8")

    ejecutar_analitica(
        ruta_duckdb=ruta_duckdb,
        ruta_taxonomia=ruta_taxonomia,
        directorio_completo=tmp_path / "r1",
        directorio_agregado=tmp_path / "a1",
    )
    ejecutar_analitica(
        ruta_duckdb=ruta_duckdb,
        ruta_taxonomia=ruta_taxonomia,
        directorio_completo=tmp_path / "r2",
        directorio_agregado=tmp_path / "a2",
    )

    conexion = duckdb.connect(str(ruta_duckdb), read_only=True)
    n = conexion.sql("SELECT count(*) AS n FROM fenomenos.asignacion_fenomeno").pl()["n"].item()
    assert n == 12
    conexion.close()
