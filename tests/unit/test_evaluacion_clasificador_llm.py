from pathlib import Path

from decla.fenomenos.evaluacion_clasificador_llm import (
    escribir_metricas_llm,
    evaluar_llm_contra_anotacion,
)
from decla.fenomenos.herramienta_anotacion_fenomeno import CONFIRMADA, CORREGIDA

CODIGOS = ["organizacion_criminal", "incautacion_y_conteo_de_efectivo"]


def test_evaluar_llm_contra_anotacion_acierto_perfecto() -> None:
    calificaciones = [
        {
            "registro_uid": "r1",
            "decision": CONFIRMADA,
            "codigos_sugeridos": "organizacion_criminal",
            "codigos_corregidos": "",
        },
        {
            "registro_uid": "r2",
            "decision": CORREGIDA,
            "codigos_sugeridos": "organizacion_criminal",
            "codigos_corregidos": "incautacion_y_conteo_de_efectivo",
        },
    ]
    predicciones = {
        "r1": ["organizacion_criminal"],
        "r2": ["incautacion_y_conteo_de_efectivo"],
    }

    metricas = evaluar_llm_contra_anotacion(calificaciones, predicciones, CODIGOS)
    por_codigo = {m.codigo: m for m in metricas}
    assert por_codigo["organizacion_criminal"].precision == 1.0
    assert por_codigo["organizacion_criminal"].exhaustividad == 1.0
    assert por_codigo["incautacion_y_conteo_de_efectivo"].f1 == 1.0


def test_evaluar_llm_contra_anotacion_solo_usa_registros_comunes() -> None:
    calificaciones = [
        {
            "registro_uid": "r1",
            "decision": CONFIRMADA,
            "codigos_sugeridos": "organizacion_criminal",
            "codigos_corregidos": "",
        },
        {
            "registro_uid": "r2",
            "decision": CONFIRMADA,
            "codigos_sugeridos": "organizacion_criminal",
            "codigos_corregidos": "",
        },
    ]
    predicciones = {"r1": []}  # r2 todavía no la procesó el LLM, no debe contar como error.

    metricas = evaluar_llm_contra_anotacion(calificaciones, predicciones, CODIGOS)
    por_codigo = {m.codigo: m for m in metricas}
    assert por_codigo["organizacion_criminal"].n_positivos_anotados == 1
    assert por_codigo["organizacion_criminal"].exhaustividad == 0.0


def test_escribir_metricas_llm(tmp_path: Path) -> None:
    from decla.fenomenos.evaluacion_clasificador_llm import MetricasLLMPorCodigo

    ruta = tmp_path / "metricas.md"
    escribir_metricas_llm(
        [MetricasLLMPorCodigo("organizacion_criminal", 0.8, 0.7, 0.75, 10)], ruta
    )
    contenido = ruta.read_text(encoding="utf-8")
    assert "organizacion_criminal" in contenido
    assert "0.8" in contenido
