"""Entidades `noticia_criminal`, `caso`, `grupo_conexo` y sus puentes (plan_trabajo.md Fase 3.4;
CLAUDE.md §3.3).

Grano confirmado en I0 sobre el dataset real (ADR 0002): una fila de `plata.registros_limpios` =
una noticia criminal. `caso` se construye como tabla propia, con el mismo grano hoy, para que un
cambio futuro de cardinalidad `CASO_ID`↔`CASO_NOTICIA` no obligue a rediseñar el esquema.

`grupo_conexo` solo expone lo que los datos permiten: `NO_CASOS_CONEXOS` es un conteo, no hay
columna que identifique CUÁLES otras noticias están conectadas (plan_trabajo.md §12, pregunta 3,
sigue abierta). No se inventa el grafo.
"""

from __future__ import annotations

from typing import Any


def construir_noticia_criminal(filas_limpias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vistos: dict[str, dict[str, Any]] = {}
    for fila in filas_limpias:
        clave = fila.get("caso_notica")
        if not clave or clave in vistos:
            continue
        vistos[clave] = {
            "caso_notica": clave,
            "cod_dpto_hechos": fila.get("cod_dpto_hechos"),
            "cod_mpio_hechos": fila.get("cod_mpio_hechos"),
            "cod_dpto_unidad": fila.get("cod_dpto_unidad"),
            "cod_mpio_unidad": fila.get("cod_mpio_unidad"),
            "fecha_hecho": fila.get("fecha_hecho"),
            "fecha_creacion": fila.get("fecha_creacion"),
            "estado_norm": fila.get("estado_norm"),
            "etapa_norm": fila.get("etapa_norm"),
            "no_casos_conexos": fila.get("no_casos_conexos"),
        }
    return list(vistos.values())


def construir_puente_noticia_delito(filas_limpias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "caso_notica": fila.get("caso_notica"),
            "delito_nombre": fila.get("delito_nombre"),
            "articulo_cp": fila.get("articulo_cp"),
        }
        for fila in filas_limpias
        if fila.get("delito_nombre")
    ]


def construir_caso(filas_limpias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mismo grano que `noticia_criminal` en el dataset real (ADR 0002)."""
    vistos: dict[str, dict[str, Any]] = {}
    for fila in filas_limpias:
        clave = fila.get("caso_id")
        if not clave or clave in vistos:
            continue
        vistos[clave] = {"caso_id": clave, "caso_notica": fila.get("caso_notica")}
    return list(vistos.values())


def construir_puente_registro_noticia_caso(
    filas_limpias: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "registro_uid": fila.get("registro_uid"),
            "caso_notica": fila.get("caso_notica"),
            "caso_id": fila.get("caso_id"),
        }
        for fila in filas_limpias
    ]


def construir_grupo_conexo(filas_limpias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    salida = []
    for fila in filas_limpias:
        n_conexos = fila.get("no_casos_conexos")
        tiene_conexos = False
        if n_conexos is not None:
            try:
                tiene_conexos = int(n_conexos) > 0
            except ValueError:
                tiene_conexos = False
        salida.append(
            {
                "caso_notica": fila.get("caso_notica"),
                "no_casos_conexos_declarados": n_conexos,
                "tiene_conexos_declarados": tiene_conexos,
            }
        )
    return salida
