"""Columnas derivadas: rezagos entre fechas, año/mes/semana ISO, coincidencia territorial
(plan_trabajo.md Fase 3.3).

`dias_a_prescripcion_declarada` nunca asume una regla fija de prescripción (ADR 0008: "hecho + 20
años" no se sostiene en el dataset real): solo informa la diferencia entre lo que el sistema
declaró, sin validarla contra ningún supuesto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DerivadosFecha:
    anio_iso: int | None
    mes: int | None
    semana_iso: int | None


def derivar_componentes_fecha(fecha: date | None) -> DerivadosFecha:
    if fecha is None:
        return DerivadosFecha(anio_iso=None, mes=None, semana_iso=None)
    anio_iso, semana_iso, _dia_iso = fecha.isocalendar()
    return DerivadosFecha(anio_iso=anio_iso, mes=fecha.month, semana_iso=semana_iso)


def dias_entre(fecha_inicio: date | None, fecha_fin: date | None) -> int | None:
    if fecha_inicio is None or fecha_fin is None:
        return None
    return (fecha_fin - fecha_inicio).days


def dias_a_prescripcion_declarada(
    fecha_hecho: date | None, fecha_prescripcion_declarada: date | None
) -> int | None:
    return dias_entre(fecha_hecho, fecha_prescripcion_declarada)


def mismo_dpto_unidad_hechos(
    cod_dpto_hechos: str | None, cod_dpto_unidad: str | None
) -> bool | None:
    if cod_dpto_hechos is None or cod_dpto_unidad is None:
        return None
    return cod_dpto_hechos == cod_dpto_unidad


def mismo_mpio(cod_mpio_hechos: str | None, cod_mpio_unidad: str | None) -> bool | None:
    if cod_mpio_hechos is None or cod_mpio_unidad is None:
        return None
    return cod_mpio_hechos == cod_mpio_unidad
