"""Normalización territorial difusa contra DIVIPOLA (CLAUDE.md §4.16; plan_trabajo.md Fase 1.5).

Clasifica cada valor de departamento/municipio en `exacto` / `normalizado` / `difuso` /
`no_resoluble`: nunca se descarta en silencio, el 100 % de los valores recibe una clasificación.
Los municipios homónimos en distintos departamentos (p. ej. "San Luis" en Antioquia y Tolima) se
desambiguan por departamento cuando está disponible; si no, quedan `no_resoluble` con
`ambiguo_homonimo=True`, nunca se adivina uno de los dos al azar.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz, process

UMBRAL_DIFUSO_DEFECTO = 85.0


@dataclass(frozen=True)
class EntradaDivipola:
    cod_dpto: str
    cod_mpio: str
    departamento: str
    municipio: str


@dataclass
class ResultadoMatchTerritorio:
    departamento_original: str | None
    municipio_original: str | None
    cod_dpto: str | None
    cod_mpio: str | None
    metodo: str  # exacto | normalizado | difuso | no_resoluble
    confianza: float
    ambiguo_homonimo: bool = False


def normalizar_texto(valor: str) -> str:
    """Mayúsculas, sin tildes, sin puntuación y sin espacios: unifica "BOGOTÁ, D. C." y
    "Bogota D.C." en la misma clave, al precio de no poder distinguir homónimos solo por nombre
    (para eso se usa el departamento).
    """
    texto = valor.strip().upper().replace(".", "").replace(",", "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return "".join(texto.split())


def _indexar(divipola: list[EntradaDivipola]) -> dict:
    por_municipio: dict[str, list[EntradaDivipola]] = defaultdict(list)
    for entrada in divipola:
        por_municipio[normalizar_texto(entrada.municipio)].append(entrada)
    return {"entradas": divipola, "por_municipio": por_municipio}


def _es_exacto(entrada: EntradaDivipola, departamento: str | None, municipio: str) -> bool:
    coincide_mpio = entrada.municipio == municipio
    coincide_dpto = departamento is None or entrada.departamento == departamento
    return coincide_mpio and coincide_dpto


def emparejar_territorio(
    departamento: str | None,
    municipio: str | None,
    divipola: list[EntradaDivipola],
    umbral_difuso: float = UMBRAL_DIFUSO_DEFECTO,
) -> ResultadoMatchTerritorio:
    resultado_vacio = ResultadoMatchTerritorio(
        departamento_original=departamento,
        municipio_original=municipio,
        cod_dpto=None,
        cod_mpio=None,
        metodo="no_resoluble",
        confianza=0.0,
    )
    if not municipio:
        return resultado_vacio

    indice = _indexar(divipola)
    mpio_n = normalizar_texto(municipio)
    dpto_n = normalizar_texto(departamento) if departamento else None

    candidatos = indice["por_municipio"].get(mpio_n, [])
    if len(candidatos) == 1:
        entrada = candidatos[0]
        metodo = "exacto" if _es_exacto(entrada, departamento, municipio) else "normalizado"
        return ResultadoMatchTerritorio(
            departamento_original=departamento,
            municipio_original=municipio,
            cod_dpto=entrada.cod_dpto,
            cod_mpio=entrada.cod_mpio,
            metodo=metodo,
            confianza=1.0,
        )

    if len(candidatos) > 1:
        if dpto_n:
            coinciden = [c for c in candidatos if normalizar_texto(c.departamento) == dpto_n]
            if len(coinciden) == 1:
                entrada = coinciden[0]
                metodo = "exacto" if _es_exacto(entrada, departamento, municipio) else "normalizado"
                return ResultadoMatchTerritorio(
                    departamento_original=departamento,
                    municipio_original=municipio,
                    cod_dpto=entrada.cod_dpto,
                    cod_mpio=entrada.cod_mpio,
                    metodo=metodo,
                    confianza=1.0,
                )
        return ResultadoMatchTerritorio(
            departamento_original=departamento,
            municipio_original=municipio,
            cod_dpto=None,
            cod_mpio=None,
            metodo="no_resoluble",
            confianza=0.0,
            ambiguo_homonimo=True,
        )

    universo = divipola
    if dpto_n:
        del_mismo_dpto = [e for e in divipola if normalizar_texto(e.departamento) == dpto_n]
        if del_mismo_dpto:
            universo = del_mismo_dpto

    claves = [normalizar_texto(e.municipio) for e in universo]
    mejor = process.extractOne(mpio_n, claves, scorer=fuzz.ratio)
    if mejor is None:
        return resultado_vacio
    _, score, indice_mejor = mejor
    if score >= umbral_difuso:
        entrada = universo[indice_mejor]
        return ResultadoMatchTerritorio(
            departamento_original=departamento,
            municipio_original=municipio,
            cod_dpto=entrada.cod_dpto,
            cod_mpio=entrada.cod_mpio,
            metodo="difuso",
            confianza=round(score / 100, 4),
        )

    return ResultadoMatchTerritorio(
        departamento_original=departamento,
        municipio_original=municipio,
        cod_dpto=None,
        cod_mpio=None,
        metodo="no_resoluble",
        confianza=round(score / 100, 4),
    )
