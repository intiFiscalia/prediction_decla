"""Cuenta los fenómenos que el clasificador LLM describió como relevantes pero fuera de la
taxonomía congelada (ADR 0029) y escribe
`reports/agregados/i4/candidatos_fenomeno_no_listado.csv` (texto crudo + conteo de relatos).

Es un reporte de candidatos, no una lista aprobada: decidir si alguno se formaliza como código
nuevo de la taxonomía es un taller de revisión humana (mismo criterio que mecanismos/fenómenos
nuevos, ADR 0020/0024).

Uso:
    uv run python scripts/resumen_fenomenos_no_listados.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar, tabla_existe
from decla.fenomenos.fenomeno_no_listado import (
    RUTA_CANDIDATOS_DEFECTO,
    escribir_candidatos_fenomeno_llm,
    identificar_candidatos_fenomeno_llm,
)
from decla.fenomenos.pipeline_clasificador_llm import RUTA_DUCKDB_DEFECTO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_CANDIDATOS_DEFECTO)
    args: Any = parser.parse_args(argv)

    conexion = conectar(args.duckdb, solo_lectura=True)
    try:
        if tabla_existe(conexion, "fenomenos", "fenomeno_no_listado_modelo"):
            filas = (
                conexion.sql(
                    "SELECT registro_uid, texto_crudo FROM fenomenos.fenomeno_no_listado_modelo"
                )
                .pl()
                .to_dicts()
            )
        else:
            filas = []
    finally:
        conexion.close()

    candidatos = identificar_candidatos_fenomeno_llm(filas)
    escribir_candidatos_fenomeno_llm(candidatos, args.salida)
    print(f"{len(candidatos)} fenómenos no listados distintos. Resumen en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
