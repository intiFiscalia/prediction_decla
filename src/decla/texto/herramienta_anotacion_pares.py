"""Herramienta de anotación de pares de relatos reales (Streamlit local; plan_trabajo.md §6.1
paso 8(b), §5.2; CLAUDE.md §4.20). Un analista califica 200-300 pares de relatos reales
(texto YA enmascarado) como "mismo fenómeno" o "distinto"; la calificación se guarda en
`data/private/` (nunca la lee Claude Code) y el resumen agregado (Spearman, precisión aproximada)
sale a `reports/agregados/i2/`.

Este módulo separa deliberadamente las funciones puras (muestreo, persistencia, cálculo de
acuerdo) de la interfaz Streamlit: las primeras se prueban con pytest sobre datos sintéticos; la
interfaz solo las invoca.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats

MISMO_FENOMENO = "mismo_fenomeno"
DISTINTO = "distinto"
NO_SEGURO = "no_seguro"

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CALIFICACIONES_DEFECTO = (
    RAIZ_PROYECTO / "data" / "private" / "anotacion_pares" / "calificaciones.csv"
)
RUTA_RESUMEN_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "i2" / "pares_calificados.md"

CAMPOS_CSV = ["registro_uid_a", "registro_uid_b", "calificacion", "calificador"]


def muestrear_pares(
    registros_uid: list[str], n_pares: int, semilla: int = 20260101
) -> list[tuple[str, str]]:
    """Pares distintos sin repetición, sin que un mismo par (en cualquier orden) salga dos
    veces. `n_pares` se recorta al máximo de pares posibles si el universo es chico.
    """
    rng = random.Random(semilla)
    universo = sorted(set(registros_uid))
    maximo_posible = len(universo) * (len(universo) - 1) // 2
    n_pares = min(n_pares, maximo_posible)

    pares_vistos: set[tuple[str, str]] = set()
    pares: list[tuple[str, str]] = []
    while len(pares) < n_pares:
        a, b = rng.sample(universo, 2)
        clave = (a, b) if a < b else (b, a)
        if clave in pares_vistos:
            continue
        pares_vistos.add(clave)
        pares.append(clave)
    return pares


def guardar_calificacion(
    ruta_csv: Path,
    registro_uid_a: str,
    registro_uid_b: str,
    calificacion: str,
    calificador: str,
) -> None:
    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    escribir_encabezado = not ruta_csv.exists()
    with ruta_csv.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_CSV)
        if escribir_encabezado:
            escritor.writeheader()
        escritor.writerow(
            {
                "registro_uid_a": registro_uid_a,
                "registro_uid_b": registro_uid_b,
                "calificacion": calificacion,
                "calificador": calificador,
            }
        )


def cargar_calificaciones(ruta_csv: Path) -> list[dict[str, str]]:
    if not ruta_csv.exists():
        return []
    with ruta_csv.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def _similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    norma_a, norma_b = np.linalg.norm(a), np.linalg.norm(b)
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norma_a * norma_b))


@dataclass(frozen=True)
class ResumenAcuerdoPares:
    n_pares: int
    spearman: float | None
    precision_en_umbral: float | None
    umbral_similitud: float


def calcular_acuerdo(
    calificaciones: list[dict[str, str]],
    vectores_por_registro: dict[str, list[float]],
    umbral_similitud: float = 0.5,
) -> ResumenAcuerdoPares:
    """Correlación de Spearman entre similitud coseno y la calificación del analista (1.0 si
    "mismo_fenomeno", 0.0 si "distinto"; se ignoran los pares "no_seguro" y los que no tienen
    vector de ambos lados), más una precisión aproximada: ¿con qué frecuencia "similitud ≥
    umbral" coincide con la calificación del analista? Es un proxy de la precisión@k del plan,
    no una réplica exacta (esta solo usa los pares calificados, no todo el corpus).
    """
    similitudes = []
    etiquetas = []
    for fila in calificaciones:
        if fila["calificacion"] not in (MISMO_FENOMENO, DISTINTO):
            continue
        vector_a = vectores_por_registro.get(fila["registro_uid_a"])
        vector_b = vectores_por_registro.get(fila["registro_uid_b"])
        if vector_a is None or vector_b is None:
            continue
        similitudes.append(_similitud_coseno(np.array(vector_a), np.array(vector_b)))
        etiquetas.append(1.0 if fila["calificacion"] == MISMO_FENOMENO else 0.0)

    if len(similitudes) < 2:
        return ResumenAcuerdoPares(len(similitudes), None, None, umbral_similitud)

    spearman = float(stats.spearmanr(similitudes, etiquetas).statistic)
    predicciones = [1.0 if s >= umbral_similitud else 0.0 for s in similitudes]
    pares_prediccion_etiqueta = zip(predicciones, etiquetas, strict=True)
    precision = sum(1 for p, e in pares_prediccion_etiqueta if p == e) / len(etiquetas)

    return ResumenAcuerdoPares(
        len(similitudes), round(spearman, 4), round(precision, 4), umbral_similitud
    )


def escribir_resumen(
    resumen: ResumenAcuerdoPares, ruta_salida: Path = RUTA_RESUMEN_DEFECTO
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Acuerdo entre analistas y similitud de embeddings (pares reales)",
        "",
        f"- Pares calificados usados: {resumen.n_pares}",
        f"- Correlación de Spearman (similitud vs. calificación): {resumen.spearman}",
        f"- Precisión aproximada con umbral {resumen.umbral_similitud}: "
        f"{resumen.precision_en_umbral}",
        "",
        'Calculado solo sobre los pares que el analista calificó como "mismo fenómeno" o '
        '"distinto" (se excluyen los marcados "no estoy seguro"). No sustituye la precisión@k '
        "sobre fixtures de `scripts/evaluar_embeddings_fixtures.py`.",
    ]
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
