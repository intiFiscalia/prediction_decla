"""Validación de fechas sin asumir el formato (CLAUDE.md §4.11, §4.13; config/reglas_fechas.yaml).

El formato de cada columna se **detecta**, nunca se asume: si algún valor tiene un número > 12 en
la primera posición, la columna no puede ser M/D/AAAA; si lo tiene en la segunda, no puede ser
D/M/AAAA. Señales contradictorias o ausentes dejan la columna como "ambiguo", que se reporta, no
se adivina.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

FORMATO_MDY = "M/D/AAAA"
FORMATO_DMY = "D/M/AAAA"
FORMATO_AMBIGUO = "ambiguo"


def _partes_numericas(valor: str) -> tuple[int, int, int] | None:
    partes = valor.split("/")
    if len(partes) != 3:
        return None
    try:
        return int(partes[0]), int(partes[1]), int(partes[2])
    except ValueError:
        return None


def detectar_formato_fecha(valores: list[str | None]) -> tuple[str, float]:
    """Devuelve (formato, confianza). confianza = fracción de valores parseables que aportan
    evidencia a favor del formato elegido.
    """
    evidencia_dmy = 0  # 1ª posición > 12 y plausible como D/M (2ª <= 12): solo puede ser D/M
    evidencia_mdy = 0  # 2ª posición > 12 y plausible como M/D (1ª <= 12): solo puede ser M/D
    total_parseable = 0

    for valor in valores:
        if not valor:
            continue
        partes = _partes_numericas(valor)
        if partes is None:
            continue
        total_parseable += 1
        a, b, _anio = partes
        # Si ambas posiciones superan 12, el valor es inválido en cualquier formato (p. ej.
        # "13/15/2026"): no aporta evidencia a favor de ninguno, no es evidencia contradictoria.
        plausible_dmy = a <= 31 and b <= 12
        plausible_mdy = a <= 12 and b <= 31
        if a > 12 and plausible_dmy:
            evidencia_dmy += 1
        if b > 12 and plausible_mdy:
            evidencia_mdy += 1

    if total_parseable == 0:
        return FORMATO_AMBIGUO, 0.0
    if evidencia_dmy > 0 and evidencia_mdy == 0:
        return FORMATO_DMY, round(evidencia_dmy / total_parseable, 4)
    if evidencia_mdy > 0 and evidencia_dmy == 0:
        return FORMATO_MDY, round(evidencia_mdy / total_parseable, 4)
    return FORMATO_AMBIGUO, 0.0


def parsear_fecha(valor: str | None, formato: str) -> date | None:
    if not valor or formato == FORMATO_AMBIGUO:
        return None
    partes = _partes_numericas(valor)
    if partes is None:
        return None
    a, b, anio = partes
    mes, dia = (a, b) if formato == FORMATO_MDY else (b, a)
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


@dataclass
class ResumenColumnaFecha:
    columna: str
    formato_detectado: str
    confianza_formato: float
    n_total: int
    n_validas: int
    n_invalidas: int
    n_futuras: int
    n_valores_invalidos_conocidos: int
    pct_validas: float


def evaluar_columna_fecha(
    columna: str,
    valores: list[str | None],
    hoy: date,
    valores_invalidos_conocidos: set[str],
) -> ResumenColumnaFecha:
    formato, confianza = detectar_formato_fecha(valores)
    n_total = sum(1 for v in valores if v)
    n_conocidos = sum(1 for v in valores if v in valores_invalidos_conocidos)
    n_validas = 0
    n_futuras = 0
    for valor in valores:
        if not valor:
            continue
        fecha = parsear_fecha(valor, formato)
        if fecha is None:
            continue
        n_validas += 1
        if fecha > hoy:
            n_futuras += 1

    return ResumenColumnaFecha(
        columna=columna,
        formato_detectado=formato,
        confianza_formato=confianza,
        n_total=n_total,
        n_validas=n_validas,
        n_invalidas=n_total - n_validas,
        n_futuras=n_futuras,
        n_valores_invalidos_conocidos=n_conocidos,
        pct_validas=round(n_validas / n_total * 100, 2) if n_total else 0.0,
    )


@dataclass
class ResumenOrdenLogico:
    columna_anterior: str
    columna_posterior: str
    n_comparables: int
    n_violaciones: int
    pct_violaciones: float


def verificar_orden_logico(
    filas: list[dict[str, str | None]],
    columna_anterior: str,
    columna_posterior: str,
    formatos: dict[str, str],
) -> ResumenOrdenLogico:
    n_comparables = 0
    n_violaciones = 0
    formato_a = formatos.get(columna_anterior, FORMATO_AMBIGUO)
    formato_b = formatos.get(columna_posterior, FORMATO_AMBIGUO)
    for fila in filas:
        fecha_a = parsear_fecha(fila.get(columna_anterior), formato_a)
        fecha_b = parsear_fecha(fila.get(columna_posterior), formato_b)
        if fecha_a is None or fecha_b is None:
            continue
        n_comparables += 1
        if fecha_a > fecha_b:
            n_violaciones += 1

    return ResumenOrdenLogico(
        columna_anterior=columna_anterior,
        columna_posterior=columna_posterior,
        n_comparables=n_comparables,
        n_violaciones=n_violaciones,
        pct_violaciones=round(n_violaciones / n_comparables * 100, 2) if n_comparables else 0.0,
    )


@dataclass
class ResumenPrescripcion:
    n_comparables: int
    n_cumple_regla: int
    pct_cumple_regla: float
    desviaciones_dias: list[int] = field(default_factory=list)


def verificar_prescripcion(
    filas: list[dict[str, str | None]],
    columna_base: str,
    columna_resultado: str,
    anios: int,
    formatos: dict[str, str],
    tolerancia_dias: int = 0,
) -> ResumenPrescripcion:
    n_comparables = 0
    n_cumple = 0
    desviaciones: list[int] = []
    formato_base = formatos.get(columna_base, FORMATO_AMBIGUO)
    formato_resultado = formatos.get(columna_resultado, FORMATO_AMBIGUO)
    for fila in filas:
        fecha_base = parsear_fecha(fila.get(columna_base), formato_base)
        fecha_resultado = parsear_fecha(fila.get(columna_resultado), formato_resultado)
        if fecha_base is None or fecha_resultado is None:
            continue
        n_comparables += 1
        try:
            esperada = fecha_base.replace(year=fecha_base.year + anios)
        except ValueError:
            esperada = fecha_base.replace(year=fecha_base.year + anios, day=28)
        diferencia = (fecha_resultado - esperada) / timedelta(days=1)
        desviaciones.append(int(diferencia))
        if abs(diferencia) <= tolerancia_dias:
            n_cumple += 1

    return ResumenPrescripcion(
        n_comparables=n_comparables,
        n_cumple_regla=n_cumple,
        pct_cumple_regla=round(n_cumple / n_comparables * 100, 2) if n_comparables else 0.0,
        desviaciones_dias=desviaciones,
    )
