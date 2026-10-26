"""Entidad `relato` y `relato_huerfano` (plan_trabajo.md Fase 3.4; CLAUDE.md §4.3).

Une `bronce.relatos_raw` con las noticias que sí entraron a `plata.registros_limpios` (ya
filtradas por alcance). Un `CASO_NOTICIA` de RELATOS que no aparece ahí va a `relato_huerfano`,
nunca se descarta en silencio. Repara la codificación aquí (no es NLP: solo revierte el mojibake,
CLAUDE.md §2.3 — "no hagas NLP sobre relatos más allá de la reparación de codificación").
"""

from __future__ import annotations

from typing import Any

import duckdb

from decla.normalizacion.codificacion import reparar_texto
from decla.normalizacion.identificadores import limpiar_identificador


def construir_relato_y_huerfanos(
    conexion: duckdb.DuckDBPyConnection, lote_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    noticias_validas = {
        fila[0]
        for fila in conexion.execute(
            "SELECT DISTINCT caso_notica FROM plata.registros_limpios"
        ).fetchall()
    }
    filas_relatos_raw = conexion.sql(
        "SELECT * FROM bronce.relatos_raw WHERE lote_id = ?", params=[lote_id]
    ).pl().to_dicts()

    relatos: list[dict[str, Any]] = []
    huerfanos: list[dict[str, Any]] = []
    for fila in filas_relatos_raw:
        caso_notica = limpiar_identificador(fila.get("CASO_NOTICIA"))
        reparado = reparar_texto(fila.get("RELATO"))
        registro = {
            "registro_uid": fila["registro_uid"],
            "caso_notica": caso_notica,
            "relato": reparado.texto,
            "reparacion_codificacion": reparado.reparacion_codificacion,
            "reparacion_fallida": reparado.reparacion_fallida,
        }
        if caso_notica in noticias_validas:
            relatos.append(registro)
        else:
            huerfanos.append(registro)
    return relatos, huerfanos
