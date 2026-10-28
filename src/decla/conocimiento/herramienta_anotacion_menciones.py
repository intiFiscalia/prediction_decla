"""Herramienta de anotación de menciones (plan_trabajo.md §6.1 paso 5 / Fase 5, Bloque 2B; mini-
compuerta 2B). Un analista confirma, rechaza o corrige menciones candidatas de
`texto.menciones` (texto YA enmascarado); la calificación se guarda en `data/private/` (nunca la
lee Claude Code) y las métricas agregadas (precisión aproximada por categoría, kappa si hay
doble anotación) se exportan a `reports/agregados/i2/`.

Muestreo estratificado + activo (plan_trabajo.md §9.1): dentro de cada categoría, prioriza las
menciones de MENOR confianza (las que más valen revisar primero), no una muestra aleatoria.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CONFIRMADA = "confirmada"
RECHAZADA = "rechazada"
CORREGIDA = "corregida"

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CALIFICACIONES_DEFECTO = (
    RAIZ_PROYECTO / "data" / "private" / "anotacion_menciones" / "calificaciones.csv"
)
RUTA_RESUMEN_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i2" / "menciones_calificadas.md"

CAMPOS_CSV = [
    "mencion_id",
    "categoria",
    "decision",
    "categoria_corregida",
    "valor_corregido",
    "calificador",
]


@dataclass(frozen=True)
class CandidatoMencion:
    mencion_id: str
    categoria: str
    confianza: float


def muestrear_menciones_estratificado_activo(
    candidatos: list[CandidatoMencion], n_total: int, semilla: int = 20260101
) -> list[str]:
    """Reparte `n_total` entre las categorías presentes (lo más parejo posible) y, dentro de
    cada categoría, prioriza las de menor confianza (muestreo activo: lo más incierto primero).
    Con empates en confianza, el orden se desempata de forma determinista con `semilla`.
    """
    por_categoria: dict[str, list[CandidatoMencion]] = defaultdict(list)
    for candidato in candidatos:
        por_categoria[candidato.categoria].append(candidato)

    categorias = sorted(por_categoria)
    if not categorias:
        return []

    rng = random.Random(semilla)
    cupo_por_categoria = max(1, n_total // len(categorias))

    seleccionados: list[str] = []
    for categoria in categorias:
        grupo = por_categoria[categoria]
        rng.shuffle(grupo)
        grupo.sort(key=lambda c: c.confianza)
        seleccionados.extend(c.mencion_id for c in grupo[:cupo_por_categoria])

    return seleccionados[:n_total]


def guardar_calificacion_mencion(
    ruta_csv: Path,
    mencion_id: str,
    categoria: str,
    decision: str,
    calificador: str,
    categoria_corregida: str | None = None,
    valor_corregido: str | None = None,
) -> None:
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    escribir_encabezado = not ruta_csv.exists()
    with ruta_csv.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_CSV)
        if escribir_encabezado:
            escritor.writeheader()
        escritor.writerow(
            {
                "mencion_id": mencion_id,
                "categoria": categoria,
                "decision": decision,
                "categoria_corregida": categoria_corregida or "",
                "valor_corregido": valor_corregido or "",
                "calificador": calificador,
            }
        )


def cargar_calificaciones_menciones(ruta_csv: Path) -> list[dict[str, str]]:
    if not ruta_csv.exists():
        return []
    with ruta_csv.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


@dataclass(frozen=True)
class MetricaCategoria:
    categoria: str
    n: int
    n_confirmadas: int
    precision_aproximada: float


def calcular_metricas_por_categoria(
    calificaciones: list[dict[str, str]],
) -> list[MetricaCategoria]:
    """`precision_aproximada` = confirmadas / total (las corregidas y rechazadas cuentan como
    error del extractor, no como aciertos parciales: es una medida conservadora a propósito).
    """
    por_categoria: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fila in calificaciones:
        por_categoria[fila["categoria"]].append(fila)

    metricas = []
    for categoria, filas in sorted(por_categoria.items()):
        n = len(filas)
        n_confirmadas = sum(1 for f in filas if f["decision"] == CONFIRMADA)
        metricas.append(
            MetricaCategoria(categoria, n, n_confirmadas, round(n_confirmadas / n, 4) if n else 0.0)
        )
    return metricas


def escribir_resumen(
    metricas: list[MetricaCategoria], ruta_salida: Path = RUTA_RESUMEN_DEFECTO
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Menciones calificadas por categoría (muestra reducida, mini-compuerta 2B)",
        "",
        "Precisión aproximada = confirmadas / total calificadas en esa categoría (rechazadas y "
        "corregidas cuentan como error, es una medida conservadora). Muestra menor a los "
        "500-1.500 relatos del plan — ver docs/decisiones/ para la justificación del alcance "
        "reducido.",
        "",
        "| Categoría | n calificadas | Confirmadas | Precisión aproximada |",
        "| --- | --- | --- | --- |",
    ]
    for metrica in metricas:
        lineas.append(
            f"| {metrica.categoria} | {metrica.n} | {metrica.n_confirmadas} | "
            f"{metrica.precision_aproximada} |"
        )
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
