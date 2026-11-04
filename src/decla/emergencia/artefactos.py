"""Filtro de artefactos de registro (plan_trabajo.md §8.5, Fase 8): antes de alertar, se verifica
si el aumento se concentra en una sola unidad/despacho, un solo día de carga, o en relatos
casi-duplicados (ya detectados en 2A, `texto.duplicados`) — si alguno se cumple, se etiqueta
"posible artefacto de registro" en vez de pasar directo a alerta.
"""

from __future__ import annotations

from typing import Any

import duckdb
import polars as pl


def _filas_del_periodo(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    territorio: str,
    indice_periodo: int,
    columna_territorio: str,
) -> list[dict[str, Any]]:
    return conexion.sql(
        f"""
        SELECT a.registro_uid, r.desp_id, r.fecha_creacion
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE a.codigo_fenomeno = ? AND r.{columna_territorio} = ?
          AND r.anio_iso_creacion * 12 + r.mes_creacion = ?
        """,
        params=[codigo_fenomeno, territorio, indice_periodo],
    ).pl().to_dicts()


def detectar_concentracion_en_una_unidad(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    territorio: str,
    indice_periodo: int,
    columna_territorio: str = "cod_dpto_hechos",
    umbral_pct: float = 0.8,
) -> dict[str, Any]:
    filas = _filas_del_periodo(
        conexion, codigo_fenomeno, territorio, indice_periodo, columna_territorio
    )
    if not filas:
        return {"concentrado": False, "n": 0}
    conteos: dict[str, int] = {}
    for fila in filas:
        conteos[fila["desp_id"]] = conteos.get(fila["desp_id"], 0) + 1
    unidad_top, n_top = max(conteos.items(), key=lambda kv: kv[1])
    pct = n_top / len(filas)
    return {"concentrado": pct >= umbral_pct, "unidad_dominante": unidad_top, "pct": round(pct, 4)}


def detectar_un_dia_de_carga(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    territorio: str,
    indice_periodo: int,
    columna_territorio: str = "cod_dpto_hechos",
    umbral_pct: float = 0.8,
) -> dict[str, Any]:
    filas = _filas_del_periodo(
        conexion, codigo_fenomeno, territorio, indice_periodo, columna_territorio
    )
    if not filas:
        return {"concentrado": False, "n": 0}
    conteos: dict[str, int] = {}
    for fila in filas:
        conteos[fila["fecha_creacion"]] = conteos.get(fila["fecha_creacion"], 0) + 1
    fecha_top, n_top = max(conteos.items(), key=lambda kv: kv[1])
    pct = n_top / len(filas)
    return {"concentrado": pct >= umbral_pct, "fecha_dominante": fecha_top, "pct": round(pct, 4)}


def detectar_casi_duplicados_dominantes(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    territorio: str,
    indice_periodo: int,
    columna_territorio: str = "cod_dpto_hechos",
    umbral_pct: float = 0.5,
) -> dict[str, Any]:
    """Usa `texto.duplicados` (2A, MinHash/LSH): un `grupo_duplicado_id` con más de un miembro es
    un grupo de casi-duplicados reales, no un fenómeno distinto repetido por azar. `texto.
    duplicados` puede no existir si el lote no tuvo ningún par casi-duplicado
    (`escribir_tabla_polars` no crea tabla para una lista vacía, CLAUDE.md: no inventar datos).
    """
    filas = _filas_del_periodo(
        conexion, codigo_fenomeno, territorio, indice_periodo, columna_territorio
    )
    if not filas:
        return {"concentrado": False, "n": 0}
    uids = [f["registro_uid"] for f in filas]
    try:
        grupos = conexion.sql(
            "SELECT registro_uid, grupo_duplicado_id FROM texto.duplicados "
            "WHERE registro_uid = ANY(?)",
            params=[uids],
        ).pl()
    except duckdb.CatalogException:
        return {"concentrado": False, "pct": 0.0}
    if grupos.height == 0:
        return {"concentrado": False, "pct": 0.0}

    tamanios_grupo = grupos.group_by("grupo_duplicado_id").agg(pl.len().alias("n_miembros"))
    grupos_reales = tamanios_grupo.filter(pl.col("n_miembros") > 1)["grupo_duplicado_id"].to_list()
    n_en_grupo_duplicado = grupos.filter(pl.col("grupo_duplicado_id").is_in(grupos_reales)).height
    pct = n_en_grupo_duplicado / len(filas)
    return {"concentrado": pct >= umbral_pct, "pct": round(pct, 4)}


def clasificar_posible_artefacto(
    concentracion_unidad: dict[str, Any],
    concentracion_dia: dict[str, Any],
    concentracion_duplicados: dict[str, Any],
) -> dict[str, Any]:
    motivos = []
    if concentracion_unidad.get("concentrado"):
        motivos.append("concentrado_en_una_unidad")
    if concentracion_dia.get("concentrado"):
        motivos.append("un_dia_de_carga")
    if concentracion_duplicados.get("concentrado"):
        motivos.append("casi_duplicados")
    return {"posible_artefacto": bool(motivos), "motivos": motivos}
