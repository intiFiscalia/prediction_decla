"""Compara el clasificador LLM (ADR 0027) contra la anotación humana confirmada y escribe
`reports/agregados/i4/clasificador_fenomenos_llm_metricas.md` — la métrica que Claude Code lee
para decidir si el prompt necesita otra iteración.

Uso:
    uv run python scripts/evaluar_clasificador_llm.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar
from decla.fenomenos.evaluacion_clasificador_llm import (
    escribir_metricas_llm,
    evaluar_llm_contra_anotacion,
)
from decla.fenomenos.herramienta_anotacion_fenomeno import (
    RUTA_CALIFICACIONES_DEFECTO,
    RUTA_TAXONOMIA_DEFECTO,
    cargar_calificaciones_fenomeno,
    cargar_codigos_fenomeno,
)
from decla.fenomenos.pipeline_clasificador_llm import ORIGEN_LLM, RUTA_DUCKDB_DEFECTO

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_METRICAS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "clasificador_fenomenos_llm_metricas.md"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--calificaciones", type=Path, default=RUTA_CALIFICACIONES_DEFECTO)
    parser.add_argument("--taxonomia", type=Path, default=RUTA_TAXONOMIA_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_METRICAS_DEFECTO)
    args: Any = parser.parse_args(argv)

    calificaciones = cargar_calificaciones_fenomeno(args.calificaciones)
    codigos = cargar_codigos_fenomeno(args.taxonomia)

    conexion = conectar(args.duckdb, solo_lectura=True)
    try:
        filas = (
            conexion.sql(
                "SELECT registro_uid, codigo_fenomeno FROM fenomenos.asignacion_fenomeno_modelo "
                f"WHERE origen = '{ORIGEN_LLM}'"
            )
            .pl()
            .to_dicts()
        )
    finally:
        conexion.close()

    predicciones: dict[str, list[str]] = {}
    for fila in filas:
        predicciones.setdefault(fila["registro_uid"], []).append(fila["codigo_fenomeno"])

    metricas = evaluar_llm_contra_anotacion(calificaciones, predicciones, codigos)
    escribir_metricas_llm(metricas, args.salida)
    print(f"Métricas escritas en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
