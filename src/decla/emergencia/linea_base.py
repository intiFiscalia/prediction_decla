"""Línea base por fenómeno × territorio agregado × periodo (plan_trabajo.md §8.5, Fase 8).

**Sin término de estacionalidad**: el dataset real cubre solo ene–oct 2026 (10 meses, I2 §4-bis),
menos del año que exige estimar un ciclo anual (el plan ya lo condiciona a "si hay ≥ 2 años"). El
modelo es Poisson/NB con tendencia lineal y *offset* del volumen total del territorio en el
periodo (para que un aumento general de registros no dispare una señal por sí solo).

Cada serie (una combinación fenómeno×territorio) se completa con los periodos donde el conteo es
0 — nunca se omiten los ceros: un detector de exceso necesita la serie completa, no solo los
periodos con actividad.
"""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import polars as pl


def construir_series_fenomeno_territorio(
    conexion: duckdb.DuckDBPyConnection, columna_territorio: str = "cod_dpto_hechos"
) -> pl.DataFrame:
    """Una fila por (codigo_fenomeno, territorio, indice_periodo), con `n` (conteo, 0 incluido)
    y `volumen_total` (todas las noticias del territorio en ese periodo, offset de la línea base).
    `indice_periodo` = año*12 + mes, entero creciente apto para una tendencia lineal.
    """
    fenomenos = conexion.sql(
        "SELECT DISTINCT codigo_fenomeno FROM fenomenos.asignacion_fenomeno"
    ).pl()["codigo_fenomeno"].to_list()
    if not fenomenos:
        return pl.DataFrame()

    volumen = conexion.sql(
        f"""
        SELECT {columna_territorio} AS territorio,
               anio_iso_creacion * 12 + mes_creacion AS indice_periodo,
               count(*) AS volumen_total
        FROM plata.registros_limpios
        WHERE {columna_territorio} IS NOT NULL AND fecha_creacion_valida
        GROUP BY {columna_territorio}, anio_iso_creacion, mes_creacion
        """
    ).pl()
    if volumen.height == 0:
        return pl.DataFrame()

    conteo = conexion.sql(
        f"""
        SELECT a.codigo_fenomeno, r.{columna_territorio} AS territorio,
               r.anio_iso_creacion * 12 + r.mes_creacion AS indice_periodo, count(*) AS n
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE r.{columna_territorio} IS NOT NULL AND r.fecha_creacion_valida
        GROUP BY a.codigo_fenomeno, r.{columna_territorio}, r.anio_iso_creacion, r.mes_creacion
        """
    ).pl()

    completa = volumen.join(pl.DataFrame({"codigo_fenomeno": fenomenos}), how="cross")
    return (
        completa.join(conteo, on=["codigo_fenomeno", "territorio", "indice_periodo"], how="left")
        .with_columns(pl.col("n").fill_null(0))
        .sort(["codigo_fenomeno", "territorio", "indice_periodo"])
    )


UMBRAL_SOBREDISPERSION = 1.5


def _varianza(mu: np.ndarray, metodo: str) -> np.ndarray:
    if metodo == "binomial_negativa":
        return mu + mu**2  # alpha=1, el mismo valor fijo de sm.families.NegativeBinomial()
    return mu


def ajustar_linea_base(serie: pl.DataFrame) -> dict[str, Any]:
    """Ajusta una serie (`indice_periodo`, `n`, `volumen_total`) con tendencia lineal y offset.
    Empieza en Poisson; si la sobredispersión de Pearson supera `UMBRAL_SOBREDISPERSION`, reajusta
    con binomial negativa. Requiere al menos 4 periodos (intercepto + tendencia + ≥2 grados de
    libertad) para que el ajuste tenga sentido; si no, devuelve `calculado=False`.

    **El último periodo nunca participa en su propio valor esperado.** Si se incluyera, un
    aumento real se "absorbería" como parte de la tendencia y se enmascararía a sí mismo (el
    mismo problema que Farrington evita comparando el punto evaluado contra una base que no lo
    incluye). El valor esperado del último periodo viene de un modelo ajustado solo con los
    periodos anteriores y evaluado (fuera de muestra) en el periodo actual; los periodos
    anteriores sí usan el ajuste con la serie completa, para no perder esa información al
    graficar la trayectoria entera.
    """
    if serie.height < 4:
        return {"calculado": False, "motivo": "menos de 4 periodos en la serie"}
    if serie["n"].sum() == 0:
        # Poisson GLM con endog todo en cero tiene un problema de frontera real en la IRLS de
        # statsmodels ("first guess on the deviance function returned a nan" — reproducido con
        # datos reales: un fenómeno que nunca ocurrió en ese territorio). No hay nada que
        # detectar en una serie sin ninguna ocurrencia, así que se omite explícitamente en vez
        # de forzar un ajuste que no tiene sentido numérico.
        return {"calculado": False, "motivo": "sin ninguna ocurrencia en este territorio"}

    import statsmodels.api as sm

    datos = serie.to_pandas()
    x = sm.add_constant(datos["indice_periodo"])
    offset = np.log(datos["volumen_total"].clip(lower=1))

    try:
        modelo_pleno = sm.GLM(datos["n"], x, family=sm.families.Poisson(), offset=offset).fit()
        residuos_dentro_de_muestra = modelo_pleno.resid_pearson
        grados_libertad = modelo_pleno.df_resid
        sobredispersion = (
            float((residuos_dentro_de_muestra**2).sum() / grados_libertad)
            if grados_libertad > 0
            else 0.0
        )
        metodo = "poisson"
        familia = sm.families.Poisson()
        if sobredispersion > UMBRAL_SOBREDISPERSION:
            familia = sm.families.NegativeBinomial()
            metodo = "binomial_negativa"
            modelo_pleno = sm.GLM(datos["n"], x, family=familia, offset=offset).fit()

        if datos["n"].iloc[:-1].sum() == 0:
            # Mismo problema de frontera que arriba, pero solo en la historia (el fenómeno
            # nunca había ocurrido en este territorio antes del último periodo): no hay nada
            # que ajustar, la tasa base es 0 por construcción — un epsilon, no un ajuste GLM
            # que no converge.
            mu_fuera_de_muestra = np.full(len(datos), 1e-6)
        else:
            modelo_sin_ultimo = sm.GLM(
                datos["n"].iloc[:-1], x.iloc[:-1], family=familia, offset=offset.iloc[:-1]
            ).fit()
            mu_fuera_de_muestra = modelo_sin_ultimo.predict(x, offset=offset).to_numpy()
    except ValueError as error:
        # Red de seguridad: con ~120 series reales (4 fenómenos × ~30 departamentos) no se
        # pueden enumerar a mano todos los patrones degenerados posibles de antemano. Dos ya
        # se identificaron y se manejan explícitamente arriba (serie en cero, emergencia sin
        # historia); cualquier otro problema numérico de la IRLS se reporta, no tumba el
        # pipeline completo por una sola serie.
        return {"calculado": False, "motivo": f"ajuste no numéricamente estable: {error}"}

    mu = modelo_pleno.fittedvalues.to_numpy().copy()
    mu[-1] = mu_fuera_de_muestra[-1]

    varianza = _varianza(mu, metodo)
    residuos = (datos["n"].to_numpy() - mu) / np.sqrt(varianza)

    return {
        "calculado": True,
        "metodo": metodo,
        "sobredispersion_pearson": round(sobredispersion, 4),
        "indice_periodo": datos["indice_periodo"].tolist(),
        "n_observado": datos["n"].tolist(),
        "n_esperado": mu.tolist(),
        "residuos_pearson": residuos.tolist(),
        "n_periodos": serie.height,
    }
