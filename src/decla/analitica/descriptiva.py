"""Analítica descriptiva de I1 e informe HTML (`make analitica-descriptiva`, `make informe`).

Calcula los indicadores de §8.1 y los mapas/matriz de §8.2, exporta CSVs e imágenes completos a
`reports/i1/` y la versión agregada+suprimida a `reports/agregados/i1/` (única carpeta que
Claude Code puede leer), y ensambla `informe.html` en ambas.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import polars as pl

from decla.analitica import indicadores as ind
from decla.analitica.mapas import (
    generar_mapa_departamental,
    generar_mapa_municipal,
    matriz_origen_destino,
)
from decla.comun.duckdb_io import conectar
from decla.comun.supresion import ocultar_columnas_derivadas_de_conteo_bajo, suprimir_celdas_bajas

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_I1_DEFECTO = RAIZ_PROYECTO / "reports" / "i1"
RUTA_AGREGADOS_I1_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i1"

NOTA_OBLIGATORIA = (
    "Toda cifra de este informe mide actividad institucional registrada, no la incidencia real "
    "del delito. Asociación no implica causalidad. Alcance limitado a Lavado de Activos (ADR 0008)."
)

_ESPECIFICACIONES: list[tuple[str, str]] = [
    ("volumen", "Volumen"),
    ("composicion_delito", "Composición por delito"),
    ("composicion_estado_etapa", "Composición por estado y etapa"),
    ("territorio_conteo", "Conteo territorial"),
    ("territorio_cociente_localizacion", "Cociente de localización"),
    ("territorio_tasa", "Tasa por 100.000 hab. (cruda y suavizada)"),
    ("tiempo_mensual", "Serie mensual y variación interanual"),
    ("rezagos", "Rezagos procesales (medianas)"),
    ("procesales", "Distribución procesal y cercanía a prescripción declarada"),
    ("conexidad", "Conexidad declarada"),
    ("calidad", "Calidad del lote"),
    ("matriz_origen_destino", "Matriz origen-destino (hechos × unidad)"),
]

_COLUMNAS_CONTEO = {
    "volumen": ["n_registros", "n_noticias", "n_casos"],
    "composicion_delito": ["n"],
    "composicion_estado_etapa": ["n"],
    "territorio_conteo": ["n_registros"],
    "territorio_cociente_localizacion": ["n", "n_total_mpio", "n_nacional", "n_total_nacional"],
    "territorio_tasa": ["n_registros"],
    "tiempo_mensual": ["n_registros", "n_registros_anio_anterior"],
    "procesales": ["n", "n_cerca_prescripcion_declarada"],
    "conexidad": ["n_noticias", "n_con_conexos_declarados"],
    "matriz_origen_destino": ["n_registros"],
}

# Columnas calculadas a partir de un conteo de `_COLUMNAS_CONTEO`: si ese conteo se suprime pero
# la columna derivada no, despejar la fórmula recupera el conteo exacto (ver
# `ocultar_columnas_derivadas_de_conteo_bajo`). Se ocultan juntas, antes de convertir el conteo a
# texto con `suprimir_celdas_bajas`.
_COLUMNAS_DERIVADAS_DE_CONTEO: dict[str, tuple[list[str], list[str]]] = {
    "composicion_delito": (["n"], ["pct"]),
    "composicion_estado_etapa": (["n"], ["pct"]),
    "territorio_cociente_localizacion": (
        ["n", "n_total_mpio", "n_nacional", "n_total_nacional"],
        ["cociente_localizacion"],
    ),
    "territorio_tasa": (["n_registros"], ["tasa_por_100k", "tasa_suavizada_por_100k"]),
    "tiempo_mensual": (
        ["n_registros", "n_registros_anio_anterior"],
        ["variacion_interanual_pct"],
    ),
    "conexidad": (["n_con_conexos_declarados"], ["pct_con_conexos_declarados"]),
}


def _calcular_todos(conexion: duckdb.DuckDBPyConnection) -> dict[str, pl.DataFrame]:
    funciones = {
        "volumen": ind.ind_volumen,
        "composicion_delito": ind.ind_composicion_delito,
        "composicion_estado_etapa": ind.ind_composicion_estado_etapa,
        "territorio_conteo": ind.ind_territorio_conteo,
        "territorio_cociente_localizacion": ind.ind_territorio_cociente_localizacion,
        "territorio_tasa": ind.ind_territorio_tasa,
        "tiempo_mensual": ind.ind_tiempo_mensual,
        "rezagos": ind.ind_rezagos,
        "procesales": ind.ind_procesales,
        "conexidad": ind.ind_conexidad,
        "calidad": ind.ind_calidad,
        "matriz_origen_destino": matriz_origen_destino,
    }
    return {nombre: funcion(conexion) for nombre, funcion in funciones.items()}


def ejecutar_analitica_descriptiva(
    conexion: duckdb.DuckDBPyConnection,
    directorio_completo: Path = RUTA_I1_DEFECTO,
    directorio_agregado: Path = RUTA_AGREGADOS_I1_DEFECTO,
) -> dict[str, pl.DataFrame]:
    directorio_completo.mkdir(parents=True, exist_ok=True)
    directorio_agregado.mkdir(parents=True, exist_ok=True)

    resultados = _calcular_todos(conexion)
    for nombre, df in resultados.items():
        df.write_csv(directorio_completo / f"{nombre}.csv")
        df_publicable = df
        disparadoras_y_derivadas = _COLUMNAS_DERIVADAS_DE_CONTEO.get(nombre)
        if disparadoras_y_derivadas is not None:
            disparadoras, derivadas = disparadoras_y_derivadas
            df_publicable = ocultar_columnas_derivadas_de_conteo_bajo(
                df_publicable, disparadoras, derivadas
            )
        columnas_conteo = _COLUMNAS_CONTEO.get(nombre)
        if columnas_conteo:
            df_publicable = suprimir_celdas_bajas(df_publicable, columnas_conteo)
        df_publicable.write_csv(directorio_agregado / f"{nombre}.csv")

    for directorio in (directorio_completo, directorio_agregado):
        generar_mapa_departamental(conexion, directorio / "mapa_departamental.png")
        generar_mapa_municipal(conexion, directorio / "mapa_municipal.png")

    return resultados


def _tabla_html(df: pl.DataFrame, n_filas: int = 30) -> str:
    return df.head(n_filas).to_pandas().to_html(index=False, na_rep="")


def _construir_html(resultados: dict[str, pl.DataFrame]) -> str:
    partes = [
        "<html><head><meta charset='utf-8'><title>Informe I1 — Base confiable e indicadores "
        "descriptivos</title></head><body>",
        f"<p><strong>{NOTA_OBLIGATORIA}</strong></p>",
        '<h2>Mapas</h2><img src="mapa_departamental.png" style="max-width:45%">'
        '<img src="mapa_municipal.png" style="max-width:45%">',
    ]
    for clave, titulo in _ESPECIFICACIONES:
        df = resultados.get(clave)
        if df is None:
            continue
        partes.append(f"<h2>{titulo}</h2>")
        partes.append(_tabla_html(df))
    partes.append("</body></html>")
    return "\n".join(partes)


def ejecutar_informe(
    resultados: dict[str, pl.DataFrame],
    directorio_completo: Path = RUTA_I1_DEFECTO,
    directorio_agregado: Path = RUTA_AGREGADOS_I1_DEFECTO,
) -> None:
    html = _construir_html(resultados)
    for directorio in (directorio_completo, directorio_agregado):
        directorio.mkdir(parents=True, exist_ok=True)
        (directorio / "informe.html").write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_I1_DEFECTO)
    parser.add_argument("--salida-agregados", type=Path, default=RUTA_AGREGADOS_I1_DEFECTO)
    args = parser.parse_args(argv)

    conexion = conectar(args.duckdb, solo_lectura=True)
    try:
        resultados = ejecutar_analitica_descriptiva(conexion, args.salida, args.salida_agregados)
        ejecutar_informe(resultados, args.salida, args.salida_agregados)
    finally:
        conexion.close()

    print(f"Analítica descriptiva e informe escritos en {args.salida} y {args.salida_agregados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
