"""Validador del contrato de esquema `config/esquema_fuente.yaml` (CLAUDE.md §4.8).

Compara las columnas observadas en una `TablaLeida` contra el contrato: columnas faltantes,
nuevas, tipo observado (numérico/fecha/texto/mixto/vacío) y % vacío. No falla si el esquema
cambió: lo reporta, que es justo el propósito del diagnóstico.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from decla.comun.configuracion import cargar_yaml
from decla.ingesta.lectores import TablaLeida

RUTA_CONTRATO_DEFECTO = (
    Path(__file__).resolve().parents[3] / "config" / "esquema_fuente.yaml"
)

_PATRON_FECHA = re.compile(r"^\d{1,2}/\d{1,2}/\d{1,4}$")


def cargar_contrato(ruta: Path = RUTA_CONTRATO_DEFECTO) -> dict:
    return cargar_yaml(ruta)


def _es_numerico(valor: str) -> bool:
    try:
        float(valor)
    except ValueError:
        return False
    return True


def _inferir_tipo(valores: list[str | None]) -> str:
    no_nulos = [v for v in valores if v is not None]
    if not no_nulos:
        return "vacio"
    si_fecha = [bool(_PATRON_FECHA.match(v)) for v in no_nulos]
    if all(si_fecha):
        return "fecha"
    si_numerico = [_es_numerico(v) for v in no_nulos]
    if all(si_numerico):
        return "numerico"
    if any(si_numerico):
        return "mixto"
    return "texto"


@dataclass
class ResultadoColumna:
    columna: str
    presente: bool
    obligatoria: bool
    heredada: bool
    tipo_esperado: str
    tipo_observado: str
    pct_vacio: float


@dataclass
class ResultadoEsquema:
    tabla: str
    columnas_esperadas_faltantes: list[str] = field(default_factory=list)
    columnas_nuevas: list[str] = field(default_factory=list)
    resultados: list[ResultadoColumna] = field(default_factory=list)


def comparar_esquema(
    tabla_leida: TablaLeida, nombre_tabla: str, contrato: dict
) -> ResultadoEsquema:
    tablas_contrato = contrato.get("tablas", {}).get(nombre_tabla, {})
    columnas_contrato: dict = tablas_contrato.get("columnas", {})
    esperadas = set(columnas_contrato)
    observadas = set(tabla_leida.columnas)

    faltantes = sorted(
        c for c in esperadas - observadas if not columnas_contrato[c].get("heredada", False)
    )
    nuevas = sorted(observadas - esperadas)

    n = tabla_leida.n_filas_datos
    resultados = []
    for columna in tabla_leida.columnas:
        valores = [fila.get(columna) for fila in tabla_leida.filas]
        n_vacios = sum(1 for v in valores if v is None)
        meta = columnas_contrato.get(columna, {})
        resultados.append(
            ResultadoColumna(
                columna=columna,
                presente=True,
                obligatoria=bool(meta.get("obligatoria", False)),
                heredada=bool(meta.get("heredada", False)),
                tipo_esperado=meta.get("tipo_esperado", "desconocido"),
                tipo_observado=_inferir_tipo(valores),
                pct_vacio=round((n_vacios / n * 100), 2) if n else 0.0,
            )
        )

    for columna, meta in columnas_contrato.items():
        if columna in observadas:
            continue
        resultados.append(
            ResultadoColumna(
                columna=columna,
                presente=False,
                obligatoria=bool(meta.get("obligatoria", False)),
                heredada=bool(meta.get("heredada", False)),
                tipo_esperado=meta.get("tipo_esperado", "desconocido"),
                tipo_observado="no_aplica",
                pct_vacio=100.0,
            )
        )

    return ResultadoEsquema(
        tabla=nombre_tabla,
        columnas_esperadas_faltantes=faltantes,
        columnas_nuevas=nuevas,
        resultados=resultados,
    )
