"""Orquestador de emergencia (plan_trabajo.md §8.5; Fase 8). Para cada serie fenómeno×territorio:
ajusta la línea base, corre los detectores complementarios (CUSUM, EARS, Farrington simplificado,
puntos de cambio) como señales corroborantes, y usa una prueba de exceso de Poisson (un lado) de
la **ventana reciente agregada** (tamaño = persistencia mínima exigida) frente a la tasa de los
periodos base como el **p formal** sobre el que se aplica Benjamini-Hochberg (plan: "corrección
por comparaciones múltiples... FDR ≤ 10 %") — CUSUM/EARS/Farrington no producen un p-valor
comparable entre series, así que no pueden ser la base de la corrección múltiple; se guardan como
columnas adicionales, no como el criterio de significancia. Se usa la ventana agregada (no un
solo punto fuera de muestra) porque con series cortas dos periodos anómalos consecutivos se
enmascaran entre sí en un ajuste de tendencia — ver `_p_valor_exceso_ventana_reciente`.

Estados que el código asigna: `candidato_en_observacion` (exceso significativo que no cumple
persistencia/tamaño/unidades todavía) y `alerta` (cumple todas las condiciones de §8.5) o
`descartada` (significativo pero con motivo de artefacto). `confirmada` solo la asigna una
persona desde la cola de revisión de la app (Bloque 3E) — el código nunca se autoconfirma.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb
import polars as pl
from scipy.stats import poisson as poisson_dist
from statsmodels.stats.multitest import multipletests

from decla.emergencia.artefactos import (
    clasificar_posible_artefacto,
    detectar_casi_duplicados_dominantes,
    detectar_concentracion_en_una_unidad,
    detectar_un_dia_de_carga,
)
from decla.emergencia.detectores import cusum, ears_c, farrington_simplificado, puntos_de_cambio
from decla.emergencia.linea_base import ajustar_linea_base, construir_series_fenomeno_territorio

CANDIDATO = "candidato_en_observacion"
ALERTA = "alerta"
DESCARTADA = "descartada"


def _n_unidades_registradoras(
    conexion: duckdb.DuckDBPyConnection,
    codigo_fenomeno: str,
    territorio: str,
    indice_periodo: int,
    columna_territorio: str,
) -> int:
    resultado = conexion.sql(
        f"""
        SELECT count(DISTINCT r.desp_id) AS n
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE a.codigo_fenomeno = ? AND r.{columna_territorio} = ?
          AND r.anio_iso_creacion * 12 + r.mes_creacion = ?
        """,
        params=[codigo_fenomeno, territorio, indice_periodo],
    ).pl()
    return int(resultado["n"].item()) if resultado.height else 0


def _p_valor_exceso_ventana_reciente(serie: pl.DataFrame, ancho_ventana: int) -> float:
    """p-valor (Poisson, un lado) de que la **ventana reciente completa** (los últimos
    `ancho_ventana` periodos, el tamaño de la persistencia mínima exigida) exceda la tasa de los
    periodos base (todos los anteriores).

    No se usa un solo punto fuera de muestra (como `ajustar_linea_base`) porque con series cortas
    (~6-10 periodos) dos o más periodos anómalos consecutivos se "explican" entre sí en un ajuste
    de tendencia: el periodo evaluado nunca queda realmente fuera de la influencia del anterior
    si éste también es parte del pico. Comparar la ventana reciente agregada contra la tasa de
    los periodos base evita ese enmascaramiento — es la misma lógica de `detectores.
    razon_de_tasas`, aplicada aquí como prueba formal de significancia en vez de solo como
    descripción del cambio.
    """
    if serie.height <= ancho_ventana:
        return 1.0  # no hay periodos base fuera de la ventana reciente: no se puede comparar

    observados = serie["n"].to_list()
    volumenes = serie["volumen_total"].to_list()
    n_reciente, volumen_reciente = sum(observados[-ancho_ventana:]), sum(volumenes[-ancho_ventana:])
    n_base, volumen_base = sum(observados[:-ancho_ventana]), sum(volumenes[:-ancho_ventana])
    if volumen_base == 0:
        return 1.0

    tasa_base = n_base / volumen_base
    esperado_reciente = tasa_base * volumen_reciente
    return float(poisson_dist.sf(max(n_reciente - 1, 0), max(esperado_reciente, 1e-6)))


@dataclass(frozen=True)
class ResumenEmergencia:
    n_series_evaluadas: int
    n_candidatos: int
    n_alertas: int
    n_descartadas_por_artefacto: int


def procesar_emergencia(
    conexion: duckdb.DuckDBPyConnection,
    run_id: str,
    umbrales: dict[str, Any],
    columna_territorio: str = "cod_dpto_hechos",
) -> ResumenEmergencia:
    series = construir_series_fenomeno_territorio(conexion, columna_territorio)
    if series.height == 0:
        escribir_alertas(conexion, [])
        return ResumenEmergencia(0, 0, 0, 0)

    filas: list[dict[str, Any]] = []
    p_valores_indices: list[int] = []
    for (codigo_fenomeno, territorio), grupo in series.group_by(["codigo_fenomeno", "territorio"]):
        serie = grupo.sort("indice_periodo")
        base = ajustar_linea_base(serie)
        if not base["calculado"]:
            continue

        actual = base["n_observado"][-1]
        esperado_actual = base["n_esperado"][-1]
        periodo_actual = base["indice_periodo"][-1]
        p = _p_valor_exceso_ventana_reciente(
            serie, umbrales["persistencia_minima_periodos"]
        )

        resultado_cusum = cusum(
            base["residuos_pearson"], k=umbrales["cusum_k"], h=umbrales["cusum_h"]
        )
        resultado_ears = ears_c(base["n_observado"])
        resultado_farrington = farrington_simplificado(
            base["n_esperado"], base["n_observado"], umbrales["farrington_umbral_desviaciones"]
        )
        puntos = puntos_de_cambio(base["n_observado"])

        persistencia = 0
        observados_recientes_primero = reversed(base["n_observado"])
        esperados_recientes_primero = reversed(base["n_esperado"])
        for obs, esp in zip(observados_recientes_primero, esperados_recientes_primero, strict=True):
            if obs > esp:
                persistencia += 1
            else:
                break

        n_unidades = _n_unidades_registradoras(
            conexion, codigo_fenomeno, territorio, periodo_actual, columna_territorio
        )

        filas.append(
            {
                "codigo_fenomeno": codigo_fenomeno,
                "territorio": territorio,
                "periodo": periodo_actual,
                "magnitud": round(actual - esperado_actual, 4),
                "n_observado": actual,
                "n_esperado": round(esperado_actual, 4),
                "p": round(p, 4),
                "p_ajustado_bh": None,
                "persistencia_periodos": persistencia,
                "n_unidades_registradoras": n_unidades,
                "cusum_en_alerta": resultado_cusum["en_alerta"],
                "ears_en_alerta": resultado_ears.get("en_alerta", False),
                "farrington_en_alerta": resultado_farrington.get("en_alerta", False),
                "n_puntos_de_cambio": len(puntos),
                "run_id": run_id,
                "estado": None,  # se decide tras aplicar BH sobre todas las series
            }
        )
        p_valores_indices.append(len(filas) - 1)

    if p_valores_indices:
        p_valores = [filas[i]["p"] for i in p_valores_indices]
        _, p_ajustados, _, _ = multipletests(p_valores, method="fdr_bh")
        for indice, p_ajustado in zip(p_valores_indices, p_ajustados, strict=True):
            filas[indice]["p_ajustado_bh"] = round(float(p_ajustado), 4)

    filas_significativas = []
    for fila in filas:
        if fila["p_ajustado_bh"] is None or fila["p_ajustado_bh"] > umbrales["fdr_maximo"]:
            continue  # sin exceso significativo tras corrección: no se guarda como señal

        minimo_persistencia = umbrales["persistencia_minima_periodos"]
        minimo_unidades = umbrales["minimo_unidades_registradoras"]
        cumple_persistencia = fila["persistencia_periodos"] >= minimo_persistencia
        cumple_tamanio = fila["n_observado"] >= umbrales["tamanio_minimo_absoluto"]
        cumple_unidades = fila["n_unidades_registradoras"] >= minimo_unidades

        argumentos_fila = (
            conexion,
            fila["codigo_fenomeno"],
            fila["territorio"],
            fila["periodo"],
            columna_territorio,
        )
        concentracion_unidad = detectar_concentracion_en_una_unidad(*argumentos_fila)
        concentracion_dia = detectar_un_dia_de_carga(*argumentos_fila)
        concentracion_duplicados = detectar_casi_duplicados_dominantes(*argumentos_fila)
        artefacto = clasificar_posible_artefacto(
            concentracion_unidad, concentracion_dia, concentracion_duplicados
        )

        if artefacto["posible_artefacto"]:
            fila["estado"] = DESCARTADA
            fila["motivo"] = "posible_artefacto_de_registro: " + ", ".join(artefacto["motivos"])
        elif cumple_persistencia and cumple_tamanio and cumple_unidades:
            fila["estado"] = ALERTA
            fila["motivo"] = ""
        else:
            fila["estado"] = CANDIDATO
            fila["motivo"] = "no cumple aún persistencia/tamaño/unidades mínimas"
        filas_significativas.append(fila)

    escribir_alertas(conexion, filas_significativas)
    n_candidatos = sum(1 for f in filas_significativas if f["estado"] == CANDIDATO)
    n_alertas = sum(1 for f in filas_significativas if f["estado"] == ALERTA)
    n_descartadas = sum(1 for f in filas_significativas if f["estado"] == DESCARTADA)
    return ResumenEmergencia(
        n_series_evaluadas=len(filas),
        n_candidatos=n_candidatos,
        n_alertas=n_alertas,
        n_descartadas_por_artefacto=n_descartadas,
    )


def escribir_alertas(conexion: duckdb.DuckDBPyConnection, filas: list[dict[str, Any]]) -> None:
    from decla.comun.duckdb_io import escribir_tabla_polars

    escribir_tabla_polars(conexion, "oro", "alertas", filas)
