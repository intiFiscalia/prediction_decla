"""Fenómeno relevante que el LLM describe cuando un relato no encaja en ninguno de los 3 códigos
de la taxonomía congelada (ADR 0029) — en vez de forzar el código "más parecido" (fallo real
observado: el modelo quería meter un hallazgo de esmeraldas en
`incautacion_y_conteo_de_efectivo`, que es específicamente dinero en efectivo).

Mismo patrón de gobernanza que mecanismos/fenómenos nuevos y organizaciones mencionadas (ADR
0020/0024/0028): se cuenta como candidato por texto crudo, nunca se agrega solo a la taxonomía
congelada ni se usa en indicadores oficiales — un humano decide en un taller de revisión si
formaliza un código nuevo.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CANDIDATOS_DEFECTO = (
    RAIZ_PROYECTO / "reports" / "agregados" / "i4" / "candidatos_fenomeno_no_listado.csv"
)


@dataclass(frozen=True)
class CandidatoFenomenoLLM:
    texto_crudo: str
    n_relatos: int


def identificar_candidatos_fenomeno_llm(
    filas: list[dict[str, str]],
) -> list[CandidatoFenomenoLLM]:
    """`filas` son filas de `fenomenos.fenomeno_no_listado_modelo` (registro_uid, texto_crudo,
    ...). Cuenta relatos distintos por texto tal como lo describió el LLM — nunca agrupa
    variantes de redacción automáticamente, eso es trabajo del taller de revisión."""
    registros_por_texto: dict[str, set[str]] = defaultdict(set)
    for fila in filas:
        registros_por_texto[fila["texto_crudo"]].add(fila["registro_uid"])
    return sorted(
        (
            CandidatoFenomenoLLM(texto, len(uids))
            for texto, uids in registros_por_texto.items()
        ),
        key=lambda c: (-c.n_relatos, c.texto_crudo),
    )


def escribir_candidatos_fenomeno_llm(
    candidatos: list[CandidatoFenomenoLLM], ruta_salida: Path = RUTA_CANDIDATOS_DEFECTO
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["texto_crudo", "n_relatos"])
        for candidato in candidatos:
            escritor.writerow([candidato.texto_crudo, candidato.n_relatos])
