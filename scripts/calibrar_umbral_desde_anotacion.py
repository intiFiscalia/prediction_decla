"""Calibra `confianza_minima` de sector/mecanismo con evidencia medida, no adivinada (ADR 0019),
y detecta candidatos a mecanismo nuevo (ADR 0020): une las calificaciones humanas de
`app_anotacion_menciones.py` (`data/private/anotacion_menciones/calificaciones.csv`, nunca
leído por Claude Code) con la confianza real guardada en `texto.menciones` (DuckDB, solo
lectura). Solo escribe agregados con supresión de celdas < 5 (`decla.comun.supresion`) en
`reports/agregados/diagnostico/` — nunca un `mencion_id`, un `registro_uid` ni texto de relato.

Dos reportes:
1. `precision_por_umbral.csv`: precisión aproximada (confirmadas/evaluadas) por umbral
   candidato. Complementa a `decla.conocimiento.diagnostico_umbral` (percentiles sobre TODO el
   corpus, sin saber si cada caso es un acierto): este da precisión real, pero solo sobre la
   muestra etiquetada a mano.
2. `candidatos_mecanismo_nuevo.csv`: códigos que una persona escribió en "valor correcto" al
   corregir una mención de mecanismo, y que no están entre los códigos ya definidos en
   `config/categorias_menciones.yaml` — señal de una técnica de lavado que la taxonomía todavía
   no cubre, nunca descartada. La persona decide si la formaliza (CLAUDE.md §2.3: ninguna
   taxonomía se agrega sin aprobación humana).

Requiere haber calificado una muestra primero:
    uv run streamlit run src/decla/conocimiento/app_anotacion_menciones.py

Uso:
    uv run python scripts/calibrar_umbral_desde_anotacion.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import polars as pl

from decla.comun.supresion import ocultar_columnas_derivadas_de_conteo_bajo, suprimir_celdas_bajas
from decla.conocimiento.diagnostico_umbral import UMBRALES_CANDIDATOS
from decla.conocimiento.herramienta_anotacion_menciones import (
    RUTA_CALIFICACIONES_DEFECTO,
    calcular_precision_por_umbral,
    cargar_calificaciones_menciones,
    identificar_candidatos_mecanismo_nuevo,
)
from decla.conocimiento.zero_shot import cargar_vocabulario

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_SALIDA_PRECISION_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "diagnostico" / "precision_por_umbral.csv"
)
RUTA_SALIDA_CANDIDATOS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "diagnostico" / "candidatos_mecanismo_nuevo.csv"
)
CATEGORIAS = ["sector", "mecanismo"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--calificaciones", type=Path, default=RUTA_CALIFICACIONES_DEFECTO)
    parser.add_argument("--salida-precision", type=Path, default=RUTA_SALIDA_PRECISION_DEFECTO)
    parser.add_argument("--salida-candidatos", type=Path, default=RUTA_SALIDA_CANDIDATOS_DEFECTO)
    args = parser.parse_args(argv)

    calificaciones = cargar_calificaciones_menciones(args.calificaciones)
    if not calificaciones:
        print(f"No hay calificaciones en {args.calificaciones}; corre primero la app de anotación.")
        return 1

    conexion = duckdb.connect(str(args.duckdb), read_only=True)
    try:
        confianzas = conexion.sql(
            "SELECT mencion_id, confianza FROM texto.menciones WHERE origen = 'inferido_modelo'"
        ).pl()
    finally:
        conexion.close()
    confianza_por_mencion = dict(
        zip(confianzas["mencion_id"].to_list(), confianzas["confianza"].to_list(), strict=True)
    )

    filas = [
        {
            "categoria": metrica.categoria,
            "umbral_candidato": metrica.umbral_candidato,
            "n_evaluadas": metrica.n_evaluadas,
            "n_confirmadas": metrica.n_confirmadas,
            "precision_aproximada": metrica.precision_aproximada,
        }
        for categoria in CATEGORIAS
        for metrica in calcular_precision_por_umbral(
            calificaciones, confianza_por_mencion, categoria, UMBRALES_CANDIDATOS
        )
    ]
    df = pl.DataFrame(filas)
    df = ocultar_columnas_derivadas_de_conteo_bajo(df, ["n_evaluadas"], ["precision_aproximada"])
    df = suprimir_celdas_bajas(df, ["n_evaluadas", "n_confirmadas"])

    args.salida_precision.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.salida_precision)
    print(df)
    print(f"Escrito: {args.salida_precision}")

    codigos_conocidos = {d.codigo for d in cargar_vocabulario("mecanismo")}
    candidatos = identificar_candidatos_mecanismo_nuevo(calificaciones, codigos_conocidos)
    df_candidatos = pl.DataFrame(
        [{"codigo_propuesto": c.codigo_propuesto, "n_propuesto": c.n_propuesto} for c in candidatos]
    )
    if df_candidatos.height:
        df_candidatos = suprimir_celdas_bajas(df_candidatos, ["n_propuesto"])
    args.salida_candidatos.parent.mkdir(parents=True, exist_ok=True)
    df_candidatos.write_csv(args.salida_candidatos)
    print(df_candidatos)
    print(f"Escrito: {args.salida_candidatos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
