"""Promueve una versión entrenada del clasificador de fenómenos hacia `fenomenos.
asignacion_fenomeno` (ADR 0025) — el paso final entre `make entrenar-clasificador-fenomenos` y
volver a correr `make analitica`/`make prediccion`/`make app` para ver el resultado en el
dashboard.

Requiere revisar antes `reports/agregados/i4/clasificador_fenomenos_metricas.md` (F1/precisión/
exhaustividad por código, partición temporal) — este script no evalúa nada, solo copia filas ya
entrenadas. Exige `--confirmar` explícito porque inserta filas reales en
`fenomenos.asignacion_fenomeno`, que los indicadores, asociaciones, atípicos y la app ya leen.

Uso:
    uv run python scripts/promover_clasificador_fenomenos.py \
        --version-modelo clasificador_fenomenos-v1-xxxxxxxx --confirmar

Después de promover, correr en este orden para que el dashboard refleje el resultado:
    make analitica   # OJO: make analitica reconstruye asignacion_fenomeno desde cero.
                      # Correrlo DESPUÉS de make analitica, nunca antes.
    uv run python scripts/promover_clasificador_fenomenos.py --version-modelo <...> --confirmar
    make emergencia && make prediccion LOTE_ID=<...> && make app
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from decla.comun.duckdb_io import conectar, escribir_tabla_polars
from decla.fenomenos.herramienta_anotacion_fenomeno import (
    NO_CLASIFICADO,
    RUIDO_ADMINISTRATIVO,
    RUTA_TAXONOMIA_DEFECTO,
    cargar_codigos_fenomeno,
)
from decla.fenomenos.promocion import construir_filas_promocion

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--taxonomia", type=Path, default=RUTA_TAXONOMIA_DEFECTO)
    parser.add_argument(
        "--version-modelo",
        required=True,
        help="El que imprimió `make entrenar-clasificador-fenomenos`.",
    )
    parser.add_argument(
        "--version-taxonomia", default="1.0", help="Versión de taxonomía vigente."
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Sin esta bandera no escribe nada (revisa antes las métricas del modelo).",
    )
    args: Any = parser.parse_args(argv)

    if not args.confirmar:
        print(
            "No se escribió nada. Revisa "
            "reports/agregados/i4/clasificador_fenomenos_metricas.md y vuelve a correr con "
            "--confirmar cuando decidas promover esta versión."
        )
        return 0

    codigos_taxonomia = [
        c
        for c in cargar_codigos_fenomeno(args.taxonomia)
        if c not in (RUIDO_ADMINISTRATIVO, NO_CLASIFICADO)
    ]

    conexion = conectar(args.duckdb, solo_lectura=False)
    try:
        filas_modelo = conexion.sql(
            "SELECT registro_uid, codigo_fenomeno, confianza, version_modelo, run_id "
            "FROM fenomenos.asignacion_fenomeno_modelo WHERE version_modelo = $version_modelo",
            params={"version_modelo": args.version_modelo},
        ).pl()
        if filas_modelo.height == 0:
            print(f"No hay filas con version_modelo={args.version_modelo!r}. Nada que promover.")
            return 1

        filas_promocion = construir_filas_promocion(
            filas_modelo.to_dicts(), codigos_taxonomia, args.version_taxonomia
        )
        escribir_tabla_polars(
            conexion, "fenomenos", "asignacion_fenomeno", filas_promocion, modo="agregar"
        )
    finally:
        conexion.close()

    print(
        f"Promovidas {len(filas_promocion)} filas de {args.version_modelo} a "
        "fenomenos.asignacion_fenomeno. Corre `make emergencia`, `make prediccion` y `make app` "
        "para verlo reflejado."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
