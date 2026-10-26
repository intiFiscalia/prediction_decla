"""Separación de DELITO y construcción de `dim_delito` (CLAUDE.md §4.18; Fase 3.3)."""

from __future__ import annotations

from dataclasses import dataclass

from decla.calidad.categoricas import parsear_delito


@dataclass
class DelitoNormalizado:
    delito_nombre: str | None
    articulo_cp: str | None
    cuantia: str | None
    parseable: bool
    titulo: str | None
    capitulo: str | None


def normalizar_delito(
    valor_delito: str | None, titulo: str | None, capitulo: str | None
) -> DelitoNormalizado:
    parseado = parsear_delito(valor_delito)
    return DelitoNormalizado(
        delito_nombre=parseado.nombre,
        articulo_cp=parseado.articulo,
        cuantia=parseado.cuantia,
        parseable=parseado.parseable,
        titulo=titulo,
        capitulo=capitulo,
    )


def construir_dim_delito(
    delitos_normalizados: list[DelitoNormalizado],
) -> list[dict[str, str | None]]:
    """Un registro único por (delito_nombre, articulo_cp), en el orden de primera aparición."""
    vistos: dict[tuple[str, str | None], dict[str, str | None]] = {}
    for delito in delitos_normalizados:
        if not delito.delito_nombre:
            continue
        clave = (delito.delito_nombre, delito.articulo_cp)
        if clave not in vistos:
            vistos[clave] = {
                "delito_nombre": delito.delito_nombre,
                "articulo_cp": delito.articulo_cp,
                "titulo": delito.titulo,
                "capitulo": delito.capitulo,
            }
    return list(vistos.values())
