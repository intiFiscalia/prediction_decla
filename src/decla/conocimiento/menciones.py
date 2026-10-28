"""Esquema de `texto.menciones` (plan_trabajo.md §6.3; Fase 5, Bloque 2B).

`coincidencias_a_menciones` convierte las `Coincidencia` que ya produce
`decla.texto.patrones_regex` (2A) en filas de menciones, en vez de re-extraer el mismo patrón:
solo las categorías analíticamente relevantes para Fase 5 se convierten (artículo penal, monto,
fecha, subpartida arancelaria). Placa/cédula/NIT/teléfono/correo/motor/chasis quedan solo como
identificadores para enmascaramiento (plan §6.1 paso 5: "para enmascarar"), no como menciones.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from decla.texto.negacion import AFIRMADA
from decla.texto.patrones_regex import Coincidencia

ORIGEN_EXPLICITO_REGLA = "explicito_regla"
ORIGEN_EXPLICITO_MODELO = "explicito_modelo"
ORIGEN_INFERIDO_MODELO = "inferido_modelo"
ORIGEN_VALIDADO_HUMANO = "validado_humano"

ESTADO_PENDIENTE = "pendiente"
ESTADO_CONFIRMADA = "confirmada"
ESTADO_RECHAZADA = "rechazada"

EXTRACTOR_PATRONES_REGEX = "patrones_regex"
VERSION_EXTRACTOR_PATRONES_REGEX = "1"

CATEGORIAS_DESDE_PATRONES: dict[str, tuple[str, str | None]] = {
    "articulo_penal": ("articulo_penal", None),
    "monto": ("monto", None),
    "fecha_texto": ("fecha", None),
    "subpartida": ("bien", "subpartida_arancelaria"),
}


@dataclass(frozen=True)
class Mencion:
    mencion_id: str
    registro_uid: str
    run_id: str
    categoria: str
    subcategoria: str | None
    valor_normalizado: str | None
    texto_evidencia: str
    inicio: int
    fin: int
    segmento: str
    origen: str
    polaridad: str
    confianza: float
    extractor: str
    version_extractor: str
    estado_revision: str = ESTADO_PENDIENTE
    revisor: str | None = None
    fecha_revision: date | None = None


def calcular_mencion_id(
    registro_uid: str,
    categoria: str,
    subcategoria: str | None,
    inicio: int,
    fin: int,
    extractor: str,
) -> str:
    clave = f"{registro_uid}|{categoria}|{subcategoria}|{inicio}|{fin}|{extractor}"
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def coincidencias_a_menciones(
    coincidencias: list[Coincidencia],
    registro_uid: str,
    run_id: str,
    segmento: str,
    polaridad_por_coincidencia: dict[int, str] | None = None,
) -> list[Mencion]:
    """`polaridad_por_coincidencia` mapea el índice de la coincidencia (en `coincidencias`) a su
    polaridad ya calculada (decla.texto.negacion.clasificar_polaridad); si no se da, se asume
    `AFIRMADA` para todas (sin ventana de negación disponible).
    """
    polaridades = polaridad_por_coincidencia or {}
    menciones = []
    for i, coincidencia in enumerate(coincidencias):
        mapeo = CATEGORIAS_DESDE_PATRONES.get(coincidencia.categoria)
        if mapeo is None:
            continue
        categoria, subcategoria = mapeo
        menciones.append(
            Mencion(
                mencion_id=calcular_mencion_id(
                    registro_uid,
                    categoria,
                    subcategoria,
                    coincidencia.inicio,
                    coincidencia.fin,
                    EXTRACTOR_PATRONES_REGEX,
                ),
                registro_uid=registro_uid,
                run_id=run_id,
                categoria=categoria,
                subcategoria=subcategoria,
                valor_normalizado=coincidencia.valor_normalizado,
                texto_evidencia=coincidencia.texto_evidencia,
                inicio=coincidencia.inicio,
                fin=coincidencia.fin,
                segmento=segmento,
                origen=ORIGEN_EXPLICITO_REGLA,
                polaridad=polaridades.get(i, AFIRMADA),
                confianza=1.0,
                extractor=EXTRACTOR_PATRONES_REGEX,
                version_extractor=VERSION_EXTRACTOR_PATRONES_REGEX,
            )
        )
    return menciones
