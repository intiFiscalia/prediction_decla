"""Conexión a DuckDB en modo lectura/escritura o solo lectura.

DuckDB admite un solo proceso escritor (plan_trabajo.md, Fase 2, riesgos): cualquier proceso de
consulta o lectura (la app, por ejemplo) debe abrir la base con `solo_lectura=True`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb


def conectar(ruta_bd: Path, solo_lectura: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(ruta_bd), read_only=solo_lectura)
