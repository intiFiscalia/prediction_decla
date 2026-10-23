"""Tipado de fechas con formato detectado por columna (CLAUDE.md §4.11; Fase 3.3).

Reusa `decla.calidad.fechas` (I0) para detectar el formato y parsear; aquí se producen los
valores tipados y las banderas que consume el resto de `plata`:
- `fecha_valida`: el valor parsea a una fecha real y no es un sentinel conocido (p. ej. "1/1/1900").
- `fecha_imputada`: el valor es un sentinel conocido; se trata como ausente, no como fecha real.
- `motivo`: por qué una fecha no es válida (`None` si es válida).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from decla.calidad.fechas import FORMATO_AMBIGUO, detectar_formato_fecha, parsear_fecha


@dataclass
class ColumnaFechaNormalizada:
    columna: str
    formato_detectado: str
    valores: list[date | None] = field(default_factory=list)
    fecha_valida: list[bool] = field(default_factory=list)
    fecha_imputada: list[bool] = field(default_factory=list)
    motivo: list[str | None] = field(default_factory=list)


def normalizar_columna_fecha(
    columna: str,
    valores_crudos: list[str | None],
    valores_invalidos_conocidos: set[str],
) -> ColumnaFechaNormalizada:
    formato, _confianza = detectar_formato_fecha(valores_crudos)
    resultado = ColumnaFechaNormalizada(columna=columna, formato_detectado=formato)

    for valor in valores_crudos:
        if valor is None:
            resultado.valores.append(None)
            resultado.fecha_valida.append(False)
            resultado.fecha_imputada.append(False)
            resultado.motivo.append(None)
            continue

        if valor in valores_invalidos_conocidos:
            resultado.valores.append(None)
            resultado.fecha_valida.append(False)
            resultado.fecha_imputada.append(True)
            resultado.motivo.append("valor_sentinel_conocido")
            continue

        if formato == FORMATO_AMBIGUO:
            resultado.valores.append(None)
            resultado.fecha_valida.append(False)
            resultado.fecha_imputada.append(False)
            resultado.motivo.append("formato_columna_ambiguo")
            continue

        fecha = parsear_fecha(valor, formato)
        resultado.valores.append(fecha)
        resultado.fecha_valida.append(fecha is not None)
        resultado.fecha_imputada.append(False)
        resultado.motivo.append(None if fecha is not None else "no_parseable")

    return resultado
