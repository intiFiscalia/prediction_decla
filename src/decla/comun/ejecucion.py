"""Registro de ejecución (CLAUDE.md §2.4): cada paso del pipeline queda trazado en
`meta.ejecuciones` con run_id, commit de git, parámetros y estado, sin contenido de filas.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import duckdb

_CREAR_ESQUEMA = "CREATE SCHEMA IF NOT EXISTS meta"
_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS meta.ejecuciones (
    run_id VARCHAR,
    paso VARCHAR,
    inicio TIMESTAMP,
    fin TIMESTAMP,
    commit_git VARCHAR,
    parametros VARCHAR,
    estado VARCHAR
)
"""


def _commit_git() -> str:
    try:
        resultado = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return resultado.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "desconocido"


@dataclass
class RegistroEjecucion:
    """Gestor de contexto: `with RegistroEjecucion(conexion, "etl") as reg: ...`."""

    conexion: duckdb.DuckDBPyConnection
    paso: str
    parametros: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __enter__(self) -> RegistroEjecucion:
        self._inicio = datetime.now(UTC)
        self.conexion.execute(_CREAR_ESQUEMA)
        self.conexion.execute(_CREAR_TABLA)
        return self

    def __exit__(self, tipo_exc: object, exc: object, tb: object) -> Literal[False]:
        fin = datetime.now(UTC)
        estado = "error" if tipo_exc else "ok"
        self.conexion.execute(
            "INSERT INTO meta.ejecuciones VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                self.run_id,
                self.paso,
                self._inicio,
                fin,
                _commit_git(),
                json.dumps(self.parametros, ensure_ascii=False),
                estado,
            ],
        )
        return False
