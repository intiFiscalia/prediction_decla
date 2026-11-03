"""Construye `fenomenos.asignacion_fenomeno` (plan_trabajo.md, Fase 4: "registro, fenómeno,
probabilidad, método") a partir de la taxonomía congelada (`config/taxonomia/v1.0.yaml`) y
`fenomenos.grupo_asignacion_borrador` (una fila por relato y método de clustering, Fase 6).

Cada fenómeno aprobado guarda su `grupo_id_origen`/`metodo_origen` (`taxonomia_v1.py`, ADR 0014):
esta función solo filtra `grupo_asignacion_borrador` por esa combinación y le pone la etiqueta
`codigo` del fenómeno. La probabilidad queda fija en 1.0 porque es membresía de clustering
(Fase 6), no de un clasificador calibrado (eso es Fase 9 / I4) — nunca se presenta como una
probabilidad real.

**Un mismo relato puede quedar bajo más de un `codigo_fenomeno`.** No es (todavía) el caso
multietiqueta genuino que anticipa el plan (§7.3, "un relato puede describir más de un
fenómeno"): es que los 4 códigos de v1.0 vienen de **dos particiones distintas** del mismo
corpus (`lavado_de_activos` de la partición de HDBSCAN; los otros 3 de la partición de NMF) —
cada partición cubre el 100 % de los relatos con grupos disjuntos entre sí, pero un relato puede
caer en el grupo de HDBSCAN que se aprobó Y en un grupo distinto de NMF que también se aprobó.
Esto se documenta aquí porque afecta cómo se lee "% no clasificado" y la suma de conteos por
fenómeno en los indicadores (Bloque 3A): la suma puede superar el total de relatos, y eso es
esperado, no un error de conteo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import yaml


def cargar_fenomenos_aprobados(ruta_taxonomia: Path) -> list[dict[str, Any]]:
    contenido = yaml.safe_load(ruta_taxonomia.read_text(encoding="utf-8"))
    return list(contenido.get("fenomenos", []))


def construir_asignacion_fenomeno(
    conexion: duckdb.DuckDBPyConnection,
    ruta_taxonomia: Path,
    run_id: str,
    version_taxonomia: str = "1.0",
) -> list[dict[str, Any]]:
    """Lee los fenómenos aprobados de `ruta_taxonomia` y `fenomenos.grupo_asignacion_borrador`
    ya en la base, y devuelve las filas de `fenomenos.asignacion_fenomeno` (quien llama decide
    si las escribe con `decla.comun.duckdb_io.escribir_tabla_polars`). Fenómenos congelados antes
    de ADR 0014 (sin `grupo_id_origen`/`metodo_origen`) se omiten explícitamente — no hay forma
    de saber a qué grupo pertenecen sin volver a congelar la taxonomía.
    """
    fenomenos = cargar_fenomenos_aprobados(ruta_taxonomia)
    borrador = conexion.sql(
        "SELECT registro_uid, grupo_id, metodo FROM fenomenos.grupo_asignacion_borrador"
    ).pl()

    filas: list[dict[str, Any]] = []
    for fenomeno in fenomenos:
        grupo_id_origen = fenomeno.get("grupo_id_origen")
        metodo_origen = fenomeno.get("metodo_origen")
        if grupo_id_origen is None or metodo_origen is None:
            continue
        miembros = borrador.filter(
            (borrador["grupo_id"] == grupo_id_origen) & (borrador["metodo"] == metodo_origen)
        )
        filas.extend(
            {
                "registro_uid": uid,
                "codigo_fenomeno": fenomeno["codigo"],
                "metodo_origen": metodo_origen,
                "probabilidad": 1.0,
                "version_taxonomia": version_taxonomia,
                "run_id": run_id,
            }
            for uid in miembros["registro_uid"].to_list()
        )
    return filas
