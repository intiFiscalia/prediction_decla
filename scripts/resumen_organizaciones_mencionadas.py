"""Cuenta las organizaciones criminales que el clasificador LLM encontró mencionadas
explícitamente en los relatos (ADR 0028) y escribe
`reports/agregados/i4/candidatos_organizacion_criminal.csv` (nombre crudo + conteo de relatos).

Es un reporte de candidatos, no una lista aprobada: nombres parecidos ("FARC" / "Farc-EP") no se
normalizan aquí — eso es una decisión humana antes de usarlos en cualquier indicador oficial
(mismo criterio que mecanismos/fenómenos nuevos, ADR 0020/0024).

Uso:
    uv run python scripts/resumen_organizaciones_mencionadas.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar, tabla_existe
from decla.fenomenos.organizacion_mencionada import (
    RUTA_CANDIDATOS_DEFECTO,
    escribir_candidatos_organizacion,
    identificar_candidatos_organizacion,
)
from decla.fenomenos.pipeline_clasificador_llm import RUTA_DUCKDB_DEFECTO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_CANDIDATOS_DEFECTO)
    args: Any = parser.parse_args(argv)

    conexion = conectar(args.duckdb, solo_lectura=True)
    try:
        if tabla_existe(conexion, "fenomenos", "organizacion_mencion_modelo"):
            filas = (
                conexion.sql(
                    "SELECT registro_uid, organizacion_nombre_crudo "
                    "FROM fenomenos.organizacion_mencion_modelo"
                )
                .pl()
                .to_dicts()
            )
        else:
            filas = []
    finally:
        conexion.close()

    candidatos = identificar_candidatos_organizacion(filas)
    escribir_candidatos_organizacion(candidatos, args.salida)
    print(f"{len(candidatos)} organizaciones distintas mencionadas. Resumen en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
