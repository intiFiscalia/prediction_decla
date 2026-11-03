from pathlib import Path

import duckdb
import yaml

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.fenomenos.asignacion import cargar_fenomenos_aprobados, construir_asignacion_fenomeno

TAXONOMIA_EJEMPLO = {
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
        {
            # Congelado antes de ADR 0014: sin traza de origen, debe omitirse.
            "codigo": "grupo_viejo_sin_traza",
            "nombre": "Grupo viejo",
        },
    ],
}


def _escribir_taxonomia(tmp_path: Path) -> Path:
    ruta = tmp_path / "v1.0.yaml"
    ruta.write_text(yaml.safe_dump(TAXONOMIA_EJEMPLO), encoding="utf-8")
    return ruta


def _conexion_con_borrador() -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    filas = [
        {"registro_uid": "uid_1", "grupo_id": "hdbscan_0", "metodo": "hdbscan", "run_id": "r1"},
        {"registro_uid": "uid_2", "grupo_id": "hdbscan_1", "metodo": "hdbscan", "run_id": "r1"},
        # uid_1 también cae en el grupo de NMF aprobado como "organizacion_criminal": overlap
        # esperado entre particiones distintas (ver docstring de asignacion.py).
        {"registro_uid": "uid_1", "grupo_id": "nmf_3", "metodo": "nmf", "run_id": "r1"},
        {"registro_uid": "uid_3", "grupo_id": "nmf_1", "metodo": "nmf", "run_id": "r1"},
    ]
    escribir_tabla_polars(conexion, "fenomenos", "grupo_asignacion_borrador", filas)
    return conexion


def test_cargar_fenomenos_aprobados(tmp_path: Path) -> None:
    ruta = _escribir_taxonomia(tmp_path)
    fenomenos = cargar_fenomenos_aprobados(ruta)
    assert len(fenomenos) == 3
    assert {f["codigo"] for f in fenomenos} == {
        "lavado_de_activos",
        "organizacion_criminal",
        "grupo_viejo_sin_traza",
    }


def test_construir_asignacion_fenomeno_filtra_por_grupo_y_metodo_origen(tmp_path: Path) -> None:
    ruta = _escribir_taxonomia(tmp_path)
    conexion = _conexion_con_borrador()

    filas = construir_asignacion_fenomeno(conexion, ruta, run_id="r2")

    por_codigo: dict[str, list[str]] = {}
    for fila in filas:
        por_codigo.setdefault(fila["codigo_fenomeno"], []).append(fila["registro_uid"])

    assert por_codigo["lavado_de_activos"] == ["uid_1"]
    assert por_codigo["organizacion_criminal"] == ["uid_1"]
    assert "grupo_viejo_sin_traza" not in por_codigo  # omitido: sin grupo_id_origen/metodo_origen
    assert all(f["probabilidad"] == 1.0 for f in filas)
    assert all(f["version_taxonomia"] == "1.0" for f in filas)
    assert all(f["run_id"] == "r2" for f in filas)
    conexion.close()


def test_construir_asignacion_fenomeno_relato_puede_quedar_en_dos_codigos(tmp_path: Path) -> None:
    """uid_1 está en hdbscan_0 (lavado_de_activos) Y en nmf_3 (organizacion_criminal) porque son
    particiones distintas del mismo corpus: el solape es esperado, no un bug (ver docstring)."""
    ruta = _escribir_taxonomia(tmp_path)
    conexion = _conexion_con_borrador()
    filas = construir_asignacion_fenomeno(conexion, ruta, run_id="r2")
    codigos_de_uid_1 = {f["codigo_fenomeno"] for f in filas if f["registro_uid"] == "uid_1"}
    assert codigos_de_uid_1 == {"lavado_de_activos", "organizacion_criminal"}
    conexion.close()


def test_construir_asignacion_fenomeno_relato_sin_fenomeno_no_aparece(tmp_path: Path) -> None:
    """uid_2 (hdbscan_1, excluido como artefacto) y uid_3 (nmf_1, descartado) no tienen fila: eso
    es lo que un indicador de "% no clasificado" (Bloque 3A) debe leer como no clasificado."""
    ruta = _escribir_taxonomia(tmp_path)
    conexion = _conexion_con_borrador()
    filas = construir_asignacion_fenomeno(conexion, ruta, run_id="r2")
    uids_con_fenomeno = {f["registro_uid"] for f in filas}
    assert uids_con_fenomeno == {"uid_1"}
    conexion.close()
