"""Evalúa el clasificador LLM (ADR 0027) contra la anotación humana confirmada — la métrica que
Claude Code lee para decidir si el prompt necesita otra iteración. No hay pesos que ajustar
(Qwen2.5-14B se usa por prompting, no se afina en este hardware): el ciclo de "reentrenamiento"
que pide la persona es error → ajustar criterios/ejemplos en `herramienta_anotacion_fenomeno.
DESCRIPCION_CODIGO` → `make clasificar-fenomenos-llm FORZAR=1` → volver a medir aquí.

Funciones puras, probadas con calificaciones y predicciones sintéticas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sklearn.metrics import f1_score, precision_score, recall_score

from decla.fenomenos.herramienta_anotacion_fenomeno import codigos_efectivos


@dataclass(frozen=True)
class MetricasLLMPorCodigo:
    codigo: str
    precision: float
    exhaustividad: float
    f1: float
    n_positivos_anotados: int


def evaluar_llm_contra_anotacion(
    calificaciones: list[dict[str, str]],
    predicciones_por_registro: dict[str, list[str]],
    codigos: list[str],
) -> list[MetricasLLMPorCodigo]:
    """`calificaciones` son filas de `cargar_calificaciones_fenomeno` (la verdad humana);
    `predicciones_por_registro` es `registro_uid -> códigos que predijo el LLM`. Solo evalúa
    sobre `registro_uid` presentes en ambos — si el LLM todavía no procesó un relato ya anotado,
    no cuenta como error, cuenta como dato faltante (quien llama decide si lo reporta aparte)."""
    verdad_por_registro = {fila["registro_uid"]: codigos_efectivos(fila) for fila in calificaciones}
    registros_comunes = sorted(set(verdad_por_registro) & set(predicciones_por_registro))

    metricas: list[MetricasLLMPorCodigo] = []
    for codigo in codigos:
        y_real = [1 if codigo in verdad_por_registro[uid] else 0 for uid in registros_comunes]
        y_pred = [
            1 if codigo in predicciones_por_registro[uid] else 0 for uid in registros_comunes
        ]
        metricas.append(
            MetricasLLMPorCodigo(
                codigo=codigo,
                precision=round(float(precision_score(y_real, y_pred, zero_division=0)), 4),
                exhaustividad=round(float(recall_score(y_real, y_pred, zero_division=0)), 4),
                f1=round(float(f1_score(y_real, y_pred, zero_division=0)), 4),
                n_positivos_anotados=sum(y_real),
            )
        )
    return metricas


def escribir_metricas_llm(metricas: list[MetricasLLMPorCodigo], ruta_salida: Path) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Clasificador LLM de fenómenos — precisión contra anotación humana (ADR 0027)",
        "",
        "| código | precisión | exhaustividad | F1 | positivos anotados |",
        "|---|---|---|---|---|",
    ]
    for m in metricas:
        lineas.append(
            f"| {m.codigo} | {m.precision} | {m.exhaustividad} | {m.f1} | "
            f"{m.n_positivos_anotados} |"
        )
    ruta_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
