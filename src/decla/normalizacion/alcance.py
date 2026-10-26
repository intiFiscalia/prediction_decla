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
