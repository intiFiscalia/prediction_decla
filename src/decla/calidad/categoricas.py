"""Catálogos, frecuencias y parseo de categóricas (CLAUDE.md §4.18, §4.19; Fase 1.6).

`DELITO` mezcla nombre, artículo y cuantía en un solo texto libre: se separa por regex, con
el % no-parseable reportado explícitamente (no se oculta lo que no calza con el patrón esperado).
Toda frecuencia agrupa los valores con conteo menor al umbral como "otros (<umbral)" antes de
publicarse, consistente con la supresión de celdas pequeñas de `comun.supresion`.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import polars as pl

UMBRAL_OTROS_DEFECTO = 5

_PATRON_DELITO = re.compile(
    r"^(?P<nombre>.+?)\s+ART\.?\s*(?P<articulo>\d+(?:-\d+)?)\s*C\.?\s*P\.?\s*(?P<cuantia>.*)$",
    re.IGNORECASE,
)


@dataclass
class DelitoParseado:
    texto_original: str | None
    nombre: str | None
    articulo: str | None
    cuantia: str | None
    parseable: bool


def parsear_delito(valor: str | None) -> DelitoParseado:
    if not valor:
        return DelitoParseado(valor, None, None, None, parseable=False)
    coincidencia = _PATRON_DELITO.match(valor.strip())
    if not coincidencia:
        return DelitoParseado(valor, None, None, None, parseable=False)
    return DelitoParseado(
        texto_original=valor,
        nombre=coincidencia.group("nombre").strip(),
        articulo=coincidencia.group("articulo").strip(),
        cuantia=coincidencia.group("cuantia").strip() or None,
        parseable=True,
    )


@dataclass
class EntradaCatalogo:
    valor: str
    conteo: int


@dataclass
class ResumenCatalogo:
    columna: str
    n_total: int
    n_vacios: int
    n_valores_distintos: int
    principales: list[EntradaCatalogo] = field(default_factory=list)
    otros_conteo: int = 0
    otros_valores_distintos: int = 0


def catalogo_frecuencias(
    columna: str, valores: list[str | None], umbral_otros: int = UMBRAL_OTROS_DEFECTO
) -> ResumenCatalogo:
    no_nulos = [v for v in valores if v is not None]
    conteo = Counter(no_nulos)
    principales: list[EntradaCatalogo] = []
    otros_conteo = 0
    otros_distintos = 0
    for valor, n in conteo.most_common():
        if n < umbral_otros:
            otros_conteo += n
            otros_distintos += 1
        else:
            principales.append(EntradaCatalogo(valor, n))

    return ResumenCatalogo(
        columna=columna,
        n_total=len(no_nulos),
        n_vacios=len(valores) - len(no_nulos),
        n_valores_distintos=len(conteo),
        principales=principales,
        otros_conteo=otros_conteo,
        otros_valores_distintos=otros_distintos,
    )


def faltantes_por_anio_departamento(
    filas: list[dict[str, str | None]],
    columna: str,
    columna_fecha: str,
    columna_departamento: str,
) -> pl.DataFrame:
    """% de `columna` faltante, agrupado por año (de `columna_fecha`, formato M/D/AAAA) y
    `columna_departamento`: los faltantes no son aleatorios si se concentran en periodos o
    unidades concretas (CLAUDE.md §4, Fase 1.4).
    """
    df = pl.DataFrame(filas, schema={c: pl.Utf8 for c in filas[0]} if filas else None)
    df = df.with_columns(
        pl.col(columna_fecha).str.split("/").list.get(2).alias("_anio"),
        pl.col(columna).is_null().alias("_faltante"),
    )
    return (
        df.group_by(["_anio", columna_departamento])
        .agg(pl.len().alias("n_filas"), pl.col("_faltante").sum().alias("n_faltantes"))
        .with_columns(
            (pl.col("n_faltantes") / pl.col("n_filas") * 100).round(2).alias("pct_faltante")
        )
        .sort(["_anio", columna_departamento])
    )
