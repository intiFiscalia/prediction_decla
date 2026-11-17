"""Punto de entrada de `make analitica` (plan_trabajo.md Fase 7 completa, I3).

Lee `data/warehouse.duckdb` en lectura-escritura (debe existir ya, vía `make etl` + `make nlp` +
`make conocimiento` + `make fenomenos` + `scripts/congelar_taxonomia_v1.py`).

Primero materializa `fenomenos.asignacion_fenomeno` (plan Fase 4: "registro, fenómeno,
probabilidad, método") a partir de la taxonomía congelada — sin esto, ni `make emergencia` ni la
app pueden leer nada por fenómeno. Después calcula los indicadores, territorio y asociaciones de
I3 y los exporta a `reports/i3/` (completo) y `reports/agregados/i3/` (agregado y suprimido,
única carpeta que Claude Code puede leer).
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

import polars as pl

from decla.analitica import asociaciones as aso
from decla.analitica import indicadores as ind
from decla.analitica import territorio as terr
from decla.analitica.mapas import generar_mapa_flujos
from decla.comun.duckdb_io import conectar, escribir_tabla_polars
from decla.comun.ejecucion import RegistroEjecucion
from decla.comun.supresion import suprimir_celdas_bajas
from decla.fenomenos.asignacion import construir_asignacion_fenomeno

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_TAXONOMIA_DEFECTO = RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml"
RUTA_I3_DEFECTO = RAIZ_PROYECTO / "reports" / "i3"
RUTA_AGREGADOS_I3_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i3"

# Columnas de conteo por tabla exportada: se suprimen (< 5 → "<5") antes de publicar en
# reports/agregados/i3/ (CLAUDE.md §2.1). Las tablas que no aparecen aquí no tienen columnas de
# conteo por fila publicable (p. ej. son resúmenes de un solo valor agregado o ya están filtradas
# a categorías con n suficiente en el propio cálculo).
_COLUMNAS_CONTEO = {
    "fenomenos": ["n_noticias"],
    "sectores": ["n"],
    "mecanismo": ["n"],
    "territorio_predominio": ["n_total", "n_predominante", "n_segundo"],
    "territorio_dispersion_puntos": ["n_puntos_validos"],
}


def _calcular_tablas_indicadores(conexion: Any) -> dict[str, pl.DataFrame]:
    return {
        "fenomenos": ind.ind_fenomenos(conexion),
        "sectores": ind.ind_sectores(conexion),
        "mecanismo": ind.ind_mecanismo(conexion),
        "territorio_perfil": terr.matriz_perfil_territorial(conexion),
        "territorio_predominio": terr.predominio_territorial(conexion),
        "territorio_calidad_puntos": terr.resumen_calidad_puntos(conexion),
        "territorio_dispersion_puntos": terr.dispersion_puntos_por_fenomeno(conexion),
    }


def _calcular_asociaciones(conexion: Any) -> dict[str, Any]:
    """Solo las asociaciones que no requieren un parámetro elegido por un analista (p. ej.
    `calcular_moran` necesita escoger un fenómeno/nivel; se deja para la app, bajo demanda).
    """
    resultados: dict[str, Any] = {}
    resultados["chi2_fenomeno_delito"] = aso.chi2_fenomeno_delito(conexion)
    resultados["reglas_asociacion"] = aso.reglas_asociacion_fenomeno_sector_territorio(conexion)
    return resultados


def ejecutar_analitica(
    ruta_duckdb: Path = RUTA_DUCKDB_DEFECTO,
    ruta_taxonomia: Path = RUTA_TAXONOMIA_DEFECTO,
    directorio_completo: Path = RUTA_I3_DEFECTO,
    directorio_agregado: Path = RUTA_AGREGADOS_I3_DEFECTO,
) -> tuple[str, dict[str, Any]]:
    run_id = str(uuid.uuid4())
    conexion = conectar(ruta_duckdb, solo_lectura=False)
    resumen: dict[str, Any] = {}
    try:
        with RegistroEjecucion(conexion, paso="analitica"):
            filas_asignacion = construir_asignacion_fenomeno(conexion, ruta_taxonomia, run_id)
            escribir_tabla_polars(conexion, "fenomenos", "asignacion_fenomeno", filas_asignacion)
            resumen["n_filas_asignacion_fenomeno"] = len(filas_asignacion)

            directorio_completo.mkdir(parents=True, exist_ok=True)
            directorio_agregado.mkdir(parents=True, exist_ok=True)

            tablas = _calcular_tablas_indicadores(conexion)
            for nombre, df in tablas.items():
                df.write_csv(directorio_completo / f"{nombre}.csv")
                columnas_conteo = _COLUMNAS_CONTEO.get(nombre)
                df_publicable = (
                    suprimir_celdas_bajas(df, columnas_conteo) if columnas_conteo else df
                )
                df_publicable.write_csv(directorio_agregado / f"{nombre}.csv")
            resumen["tablas_exportadas"] = list(tablas)

            asociaciones = _calcular_asociaciones(conexion)
            if asociaciones["chi2_fenomeno_delito"].get("calculado"):
                resumen_chi2 = {
                    k: v
                    for k, v in asociaciones["chi2_fenomeno_delito"].items()
                    if k != "residuos_estandarizados"
                }
                pl.DataFrame([resumen_chi2]).write_csv(
                    directorio_completo / "asociaciones_chi2_fenomeno_delito.csv"
                )
                if resumen_chi2.get("n", 0) >= 5:
                    pl.DataFrame([resumen_chi2]).write_csv(
                        directorio_agregado / "asociaciones_chi2_fenomeno_delito.csv"
                    )
            reglas = asociaciones["reglas_asociacion"]
            reglas.write_csv(directorio_completo / "asociaciones_reglas.csv")
            if reglas.height > 0:
                # "support" es una fracción de canastas, no un conteo: hay que volver al conteo
                # absoluto (support × n_canastas) para aplicar el umbral de 5 correctamente
                # (CLAUDE.md §2.1) — nunca suprimir sobre una fracción, que no dice nada sobre
                # cuántos relatos hay detrás.
                n_canastas = conexion.sql(
                    "SELECT count(DISTINCT registro_uid) AS n FROM fenomenos.asignacion_fenomeno"
                ).pl()["n"].item()
                reglas.filter(pl.col("support") * n_canastas >= 5).write_csv(
                    directorio_agregado / "asociaciones_reglas.csv"
                )

            for directorio in (directorio_completo, directorio_agregado):
                generar_mapa_flujos(conexion, directorio / "mapa_flujos.png")
    finally:
        conexion.close()
    return run_id, resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--taxonomia", type=Path, default=RUTA_TAXONOMIA_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_I3_DEFECTO)
    parser.add_argument("--salida-agregados", type=Path, default=RUTA_AGREGADOS_I3_DEFECTO)
    args: Any = parser.parse_args(argv)

    run_id, resumen = ejecutar_analitica(
        args.duckdb, args.taxonomia, args.salida, args.salida_agregados
    )

    print(f"Analítica completa — run_id={run_id}")
    print(f"  Filas en fenomenos.asignacion_fenomeno: {resumen['n_filas_asignacion_fenomeno']}")
    print(f"  Tablas exportadas a {args.salida} / {args.salida_agregados}:")
    print(f"    {resumen['tablas_exportadas']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
