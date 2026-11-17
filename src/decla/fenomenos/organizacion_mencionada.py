"""Organización criminal mencionada explícitamente en el relato (ADR 0028) — extraída por el
mismo LLM que clasifica fenómenos (`clasificador_llm.clasificar_relato`), en el mismo paso, sin
llamadas adicionales. Es un campo abierto: no existe una taxonomía cerrada de organizaciones
criminales en este proyecto. Mismo patrón de gobernanza que mecanismos/fenómenos nuevos (ADR
0020/0024): se cuenta como candidato por nombre crudo, nunca se normaliza ni se usa en
indicadores oficiales sin que un humano decida cómo tratar variantes del mismo nombre ("FARC" vs
"Farc-EP" vs errores de transcripción).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CANDIDATOS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "candidatos_organizacion_criminal.csv"
)


@dataclass(frozen=True)
class CandidatoOrganizacion:
    nombre_crudo: str
    n_relatos: int


def identificar_candidatos_organizacion(
    filas: list[dict[str, str]],
) -> list[CandidatoOrganizacion]:
    """`filas` son filas de `fenomenos.organizacion_mencion_modelo` (registro_uid,
    organizacion_nombre_crudo, ...). Cuenta relatos distintos por nombre tal como lo extrajo el
    LLM — nunca normaliza variantes automáticamente, eso es una decisión humana en un taller de
    revisión (mismo criterio que candidatos de mecanismo/fenómeno nuevo)."""
    registros_por_nombre: dict[str, set[str]] = defaultdict(set)
    for fila in filas:
        registros_por_nombre[fila["organizacion_nombre_crudo"]].add(fila["registro_uid"])
    return sorted(
        (
            CandidatoOrganizacion(nombre, len(uids))
            for nombre, uids in registros_por_nombre.items()
        ),
        key=lambda c: (-c.n_relatos, c.nombre_crudo),
    )


def escribir_candidatos_organizacion(
    candidatos: list[CandidatoOrganizacion], ruta_salida: Path = RUTA_CANDIDATOS_DEFECTO
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["nombre_crudo", "n_relatos"])
        for candidato in candidatos:
            escritor.writerow([candidato.nombre_crudo, candidato.n_relatos])
