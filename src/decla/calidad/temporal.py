"""Estabilidad temporal y viabilidad de pronósticos (CLAUDE.md §4.14; plan_trabajo.md §8.4).

La serie mensual usa `FECHA_CREACION` (fecha de registro, no de hecho) como referencia
provisional de diagnóstico (ver `docs/decisiones/`); I1 fijará la fecha de referencia definitiva
por indicador. Un solo año de datos (como la muestra real descrita en CLAUDE.md §4.14) no alcanza
el umbral del plan para pronósticos (≥36 meses): se reporta la condición, no se fuerza.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import polars as pl
import ruptures as rpt

from decla.calidad.fechas import parsear_fecha

UMBRAL_MESES_VIABLE_PRONOSTICO = 36


def calcular_volumen_mensual(fechas: list[str | None], formato: str) -> pl.DataFrame:
    meses = []
    for valor in fechas:
        fecha = parsear_fecha(valor, formato)
        if fecha:
            meses.append(f"{fecha.year:04d}-{fecha.month:02d}")
    conteo = Counter(meses)
    esquema = {"mes": pl.Utf8, "n_registros": pl.Int64}
    if not conteo:
        return pl.DataFrame({"mes": [], "n_registros": []}, schema=esquema)
    datos = {"mes": list(conteo.keys()), "n_registros": list(conteo.values())}
    return pl.DataFrame(datos).sort("mes")


def detectar_puntos_de_cambio(serie: list[int], penalidad: float = 5.0) -> list[int]:
    """Índices (dentro de `serie`) donde `ruptures.Pelt` detecta un cambio de nivel."""
    if len(serie) < 4:
        return []
    señal = np.asarray(serie, dtype=float)
    algoritmo = rpt.Pelt(model="rbf").fit(señal)
    puntos = algoritmo.predict(pen=penalidad)
    return [p for p in puntos if p < len(serie)]


@dataclass
class ResumenTemporal:
    volumen_mensual: pl.DataFrame
    n_meses_con_datos: int
    periodo_min: str | None
    periodo_max: str | None
    meses_con_punto_de_cambio: list[str]
    viable_pronostico: bool
    nota_viabilidad: str


def resumir_temporal(
    fechas: list[str | None],
    formato: str,
    umbral_meses_viable: int = UMBRAL_MESES_VIABLE_PRONOSTICO,
) -> ResumenTemporal:
    df = calcular_volumen_mensual(fechas, formato)
    n_meses = df.height

    indices_cambio = detectar_puntos_de_cambio(df["n_registros"].to_list())
    meses_cambio = [df["mes"][i] for i in indices_cambio]

    viable = n_meses >= umbral_meses_viable
    comparacion = "≥" if viable else "<"
    conclusion = (
        "pronósticos de conteo viables en principio (plan_trabajo.md §8.4)."
        if viable
        else "historia insuficiente: I4 (pronósticos) queda condicionado al periodo real."
    )
    nota = (
        f"{n_meses} meses con datos ({comparacion}{umbral_meses_viable} recomendado): "
        f"{conclusion}"
    )

    return ResumenTemporal(
        volumen_mensual=df,
        n_meses_con_datos=n_meses,
        periodo_min=str(df["mes"].min()) if n_meses else None,
        periodo_max=str(df["mes"].max()) if n_meses else None,
        meses_con_punto_de_cambio=meses_cambio,
        viable_pronostico=viable,
        nota_viabilidad=nota,
    )
