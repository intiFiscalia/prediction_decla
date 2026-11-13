"""Filtro de alcance temático (ADR 0008; `config/alcance_tematico.yaml`).

Limita qué filas entran a `plata.registros_limpios`. `bronce` nunca se filtra: conserva el 100 %
de lo que llegó, incluidas las filas fuera de alcance. Toda exclusión se cuenta y se explica,
nunca se descarta en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResultadoFiltroAlcance:
    n_entrada: int
    n_dentro_alcance: int
    n_fuera_alcance: int
    valores_excluidos: dict[str, int] = field(default_factory=dict)


def filtrar_por_alcance(
    filas: list[dict[str, str | None]],
    columna_alcance: str,
    valores_incluidos: set[str],
) -> tuple[list[dict[str, str | None]], ResultadoFiltroAlcance]:
    dentro: list[dict[str, str | None]] = []
    excluidos: dict[str, int] = {}

    for fila in filas:
        valor = fila.get(columna_alcance)
        if valor in valores_incluidos:
            dentro.append(fila)
        else:
            clave = valor or "(vacío)"
            excluidos[clave] = excluidos.get(clave, 0) + 1

    resultado = ResultadoFiltroAlcance(
        n_entrada=len(filas),
        n_dentro_alcance=len(dentro),
        n_fuera_alcance=len(filas) - len(dentro),
        valores_excluidos=excluidos,
    )
    return dentro, resultado


def _ruptura_tiene_valor(valor: str | None) -> bool:
    """`None`, cadena vacía tras `strip()`, o comillas vacías literales (`""`/`''`, artefacto de
    lectura de CSV/Excel reportado por la persona) cuentan como "sin ruptura". Cualquier otro
    contenido cuenta como "con ruptura".
    """
    if valor is None:
        return False
    texto = valor.strip()
    return texto != "" and texto not in {'""', "''"}


@dataclass
class ResultadoFiltroRuptura:
    n_entrada: int
    n_con_ruptura: int
    n_sin_ruptura: int


def filtrar_por_ruptura(
    filas: list[dict[str, str | None]], columna_ruptura: str = "RUPTURA"
) -> tuple[list[dict[str, str | None]], ResultadoFiltroRuptura]:
    """Excluye de `plata.registros_limpios` las filas de CASOS cuyo campo RUPTURA tiene un valor
    real (decisión de la persona, 2026-11-13: ver ADR correspondiente). `bronce` nunca se
    filtra; el `CASO_NOTICIA` de RELATOS correspondiente a una fila excluida aquí cae solo en
    `entidades.relato_huerfano` (`decla.entidades.relato`, ya compara contra el conjunto de
    `CASO_NOTICIA` que sobrevivió a `plata.registros_limpios`) — no se descarta en silencio.
    """
    sin_ruptura = [f for f in filas if not _ruptura_tiene_valor(f.get(columna_ruptura))]
    n_con_ruptura = len(filas) - len(sin_ruptura)
    resultado = ResultadoFiltroRuptura(
        n_entrada=len(filas), n_con_ruptura=n_con_ruptura, n_sin_ruptura=len(sin_ruptura)
    )
    return sin_ruptura, resultado
