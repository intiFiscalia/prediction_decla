"""Orquestador de predicción (plan_trabajo.md §8.4, Fase 9; I4, Bloques 4A y 4E).

Atípicos (4A): lee embeddings de relato (media) del lote más reciente en
`data/embeddings/<lote_id>/relato.parquet` — mismo cargador que usa `decla.fenomenos.orquestador`
(`decla.fenomenos.representacion.cargar_embeddings_segmento`, genérico a cualquier parquet con
columnas `registro_uid`/`agregacion`/`vector`, no solo a segmentos).

Pronósticos (4E, ADR 0016): reusa `decla.emergencia.linea_base.construir_series_fenomeno_
territorio` (misma grilla fenómeno×territorio×periodo que ya usa emergencia, con ceros
explícitos) — no se duplica esa función.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from decla.comun.duckdb_io import escribir_tabla_polars
from decla.emergencia.linea_base import construir_series_fenomeno_territorio
from decla.fenomenos.representacion import MEDIA, cargar_embeddings_segmento
from decla.prediccion.atipicos import construir_tabla_atipicos
from decla.prediccion.pronosticos import (
    evaluar_rolling_origin,
    pronostico_ets_tendencia,
    pronostico_ingenuo,
    pronostico_poisson_nb_tendencia,
)


@dataclass(frozen=True)
class ResumenAtipicos:
    n_registros: int
    lote_id_embeddings: str


def procesar_atipicos(
    conexion: duckdb.DuckDBPyConnection,
    lote_id_embeddings: str,
    ruta_embeddings_datos: Path,
    run_id: str,
    semilla: int = 20260101,
) -> ResumenAtipicos:
    ruta_parquet = ruta_embeddings_datos / lote_id_embeddings / "relato.parquet"
    embeddings_por_uid = cargar_embeddings_segmento(ruta_parquet, agregacion=MEDIA)

    filas = construir_tabla_atipicos(conexion, embeddings_por_uid, run_id, semilla)
    escribir_tabla_polars(conexion, "oro", "atipicos", filas)

    return ResumenAtipicos(n_registros=len(filas), lote_id_embeddings=lote_id_embeddings)


@dataclass(frozen=True)
class ResumenPronosticos:
    n_series_evaluadas: int
    n_filas_escritas: int


_FUNCIONES_PRONOSTICO = {
    "ingenuo": lambda s, v, h: pronostico_ingenuo(s, h),
    "ets_tendencia": lambda s, v, h: pronostico_ets_tendencia(s, h),
    "poisson_nb_tendencia": lambda s, v, h: pronostico_poisson_nb_tendencia(s, v, h),
}


def procesar_pronosticos(
    conexion: duckdb.DuckDBPyConnection,
    run_id: str,
    horizonte: int = 3,
    columna_territorio: str = "cod_dpto_hechos",
) -> ResumenPronosticos:
    series = construir_series_fenomeno_territorio(conexion, columna_territorio)
    if series.height == 0:
        escribir_tabla_polars(conexion, "oro", "pronosticos", [])
        return ResumenPronosticos(0, 0)

    filas: list[dict[str, Any]] = []
    n_series_evaluadas = 0
    for (codigo_fenomeno, territorio), grupo in series.group_by(
        ["codigo_fenomeno", "territorio"]
    ):
        serie = grupo.sort("indice_periodo")
        serie_n = [float(v) for v in serie["n"].to_list()]
        volumenes = [float(v) for v in serie["volumen_total"].to_list()]
        indices = serie["indice_periodo"].to_list()
        if not indices:
            continue
        fecha_corte = indices[-1]
        n_series_evaluadas += 1

        for nombre_metodo, funcion in _FUNCIONES_PRONOSTICO.items():
            resultado = funcion(serie_n, volumenes, horizonte)
            backtest = evaluar_rolling_origin(serie_n, volumenes, nombre_metodo, horizonte=1)

            if not resultado.calculado:
                continue

            assert resultado.valores_punto is not None
            sin_intervalo: tuple[float | None, float | None] = (None, None)
            relleno = [sin_intervalo] * horizonte
            intervalos_80: list[tuple[float | None, float | None]] = (
                list(resultado.intervalo_80) if resultado.intervalo_80 else relleno
            )
            intervalos_95: list[tuple[float | None, float | None]] = (
                list(resultado.intervalo_95) if resultado.intervalo_95 else relleno
            )
            for paso in range(horizonte):
                intervalo_80 = intervalos_80[paso]
                intervalo_95 = intervalos_95[paso]
                filas.append(
                    {
                        "codigo_fenomeno": codigo_fenomeno,
                        "territorio": territorio,
                        "periodo_pronosticado": fecha_corte + paso + 1,
                        "metodo": resultado.metodo,
                        "valor_punto": round(resultado.valores_punto[paso], 4),
                        "intervalo_80_inf": intervalo_80[0],
                        "intervalo_80_sup": intervalo_80[1],
                        "intervalo_95_inf": intervalo_95[0],
                        "intervalo_95_sup": intervalo_95[1],
                        "mase_backtest": backtest.get("mase"),
                        "wape_backtest": backtest.get("wape"),
                        "n_origenes_backtest": backtest.get("n_origenes", 0),
                        "supera_ingenuo": backtest.get("supera_ingenuo"),
                        "fecha_corte": fecha_corte,
                        "run_id": run_id,
                    }
                )

    escribir_tabla_polars(conexion, "oro", "pronosticos", filas)
    return ResumenPronosticos(n_series_evaluadas=n_series_evaluadas, n_filas_escritas=len(filas))
