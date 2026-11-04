import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.emergencia.artefactos import (
    clasificar_posible_artefacto,
    detectar_casi_duplicados_dominantes,
    detectar_concentracion_en_una_unidad,
    detectar_un_dia_de_carga,
)

INDICE_PERIODO = 2026 * 12 + 1


def _conexion_periodo(desp_ids: list[str], fechas: list[str]) -> duckdb.DuckDBPyConnection:
    conexion = duckdb.connect(":memory:")
    relatos = [{"registro_uid": f"uid_{i}", "caso_notica": f"caso_{i}"} for i in range(len(desp_ids))]
    registros = [
        {
            "caso_notica": f"caso_{i}", "cod_dpto_hechos": "11", "desp_id": desp_ids[i],
            "fecha_creacion": fechas[i], "anio_iso_creacion": 2026, "mes_creacion": 1,
        }
        for i in range(len(desp_ids))
    ]
    asignacion = [{"registro_uid": f"uid_{i}", "codigo_fenomeno": "x"} for i in range(len(desp_ids))]
    escribir_tabla_polars(conexion, "texto", "relato_procesado", relatos)
    escribir_tabla_polars(conexion, "plata", "registros_limpios", registros)
    escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", asignacion)
    return conexion


def test_detectar_concentracion_en_una_unidad_positivo() -> None:
    conexion = _conexion_periodo(
        desp_ids=["D1", "D1", "D1", "D1", "D2"],
        fechas=["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
    )
    resultado = detectar_concentracion_en_una_unidad(
        conexion, "x", "11", INDICE_PERIODO, umbral_pct=0.7
    )
    assert resultado["concentrado"] is True
    assert resultado["unidad_dominante"] == "D1"
    conexion.close()


def test_detectar_concentracion_en_una_unidad_repartido() -> None:
    conexion = _conexion_periodo(
        desp_ids=["D1", "D2", "D3", "D4", "D5"],
        fechas=["2026-01-01"] * 5,
    )
    resultado = detectar_concentracion_en_una_unidad(
        conexion, "x", "11", INDICE_PERIODO, umbral_pct=0.7
    )
    assert resultado["concentrado"] is False
    conexion.close()


def test_detectar_un_dia_de_carga_positivo() -> None:
    conexion = _conexion_periodo(
        desp_ids=["D1", "D2", "D3", "D4", "D5"],
        fechas=["2026-01-01"] * 4 + ["2026-01-02"],
    )
    resultado = detectar_un_dia_de_carga(conexion, "x", "11", INDICE_PERIODO, umbral_pct=0.7)
    assert resultado["concentrado"] is True
    assert resultado["fecha_dominante"] == "2026-01-01"
    conexion.close()


def test_detectar_casi_duplicados_dominantes_sin_tabla_de_duplicados() -> None:
    conexion = _conexion_periodo(
        desp_ids=["D1", "D2"], fechas=["2026-01-01", "2026-01-02"]
    )
    resultado = detectar_casi_duplicados_dominantes(conexion, "x", "11", INDICE_PERIODO)
    assert resultado["concentrado"] is False
    conexion.close()


def test_detectar_casi_duplicados_dominantes_con_grupo_real() -> None:
    conexion = _conexion_periodo(
        desp_ids=["D1", "D2", "D3"],
        fechas=["2026-01-01", "2026-01-02", "2026-01-03"],
    )
    escribir_tabla_polars(
        conexion,
        "texto",
        "duplicados",
        [
            {"registro_uid": "uid_0", "grupo_duplicado_id": "g1"},
            {"registro_uid": "uid_1", "grupo_duplicado_id": "g1"},
        ],
    )
    resultado = detectar_casi_duplicados_dominantes(
        conexion, "x", "11", INDICE_PERIODO, umbral_pct=0.5
    )
    assert resultado["concentrado"] is True  # 2 de 3 relatos están en el mismo grupo real
    conexion.close()


def test_clasificar_posible_artefacto_combina_motivos() -> None:
    resultado = clasificar_posible_artefacto(
        {"concentrado": True}, {"concentrado": False}, {"concentrado": False}
    )
    assert resultado["posible_artefacto"] is True
    assert resultado["motivos"] == ["concentrado_en_una_unidad"]


def test_clasificar_posible_artefacto_sin_motivos() -> None:
    resultado = clasificar_posible_artefacto(
        {"concentrado": False}, {"concentrado": False}, {"concentrado": False}
    )
    assert resultado["posible_artefacto"] is False
    assert resultado["motivos"] == []
