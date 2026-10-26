"""Normalización territorial con excepciones manuales (CLAUDE.md §4.16; Fase 3.3).

Aplica `decla.calidad.territorio.emparejar_territorio` (I0) contra el DIVIPOLA real; lo que queda
`no_resoluble` se consulta contra `config/territorio_manual.yaml`, llenado por una persona que
revisó el valor, nunca adivinado por el código.
"""

from __future__ import annotations

from dataclasses import dataclass

from decla.calidad.territorio import (
    EntradaDivipola,
    ResultadoMatchTerritorio,
    emparejar_territorio,
)


@dataclass(frozen=True)
class ExcepcionManual:
    departamento_original: str | None
    municipio_original: str | None
    cod_dpto: str
    cod_mpio: str
    nota: str = ""


def cargar_excepciones_manuales(
    contenido: dict,
) -> dict[tuple[str | None, str | None], ExcepcionManual]:
    excepciones = {}
    for entrada in contenido.get("excepciones", []) or []:
        clave = (entrada.get("departamento_original"), entrada.get("municipio_original"))
        excepciones[clave] = ExcepcionManual(
            departamento_original=entrada.get("departamento_original"),
            municipio_original=entrada.get("municipio_original"),
            cod_dpto=entrada["cod_dpto"],
            cod_mpio=entrada["cod_mpio"],
            nota=entrada.get("nota", ""),
        )
    return excepciones


def emparejar_con_manual(
    departamento: str | None,
    municipio: str | None,
    divipola: list[EntradaDivipola],
    excepciones_manuales: dict[tuple[str | None, str | None], ExcepcionManual],
    umbral_difuso: float = 85.0,
) -> ResultadoMatchTerritorio:
    resultado = emparejar_territorio(departamento, municipio, divipola, umbral_difuso)
    if resultado.metodo != "no_resoluble":
        return resultado

    excepcion = excepciones_manuales.get((departamento, municipio))
    if excepcion is None:
        return resultado

    return ResultadoMatchTerritorio(
        departamento_original=departamento,
        municipio_original=municipio,
        cod_dpto=excepcion.cod_dpto,
        cod_mpio=excepcion.cod_mpio,
        metodo="manual",
        confianza=1.0,
    )
