from pathlib import Path

from decla.conocimiento.herramienta_anotacion_menciones import (
    CONFIRMADA,
    RECHAZADA,
    CandidatoMencion,
    calcular_metricas_por_categoria,
    cargar_calificaciones_menciones,
    escribir_resumen,
    guardar_calificacion_mencion,
    muestrear_menciones_estratificado_activo,
)


def test_muestrear_reparte_entre_categorias() -> None:
    candidatos = [
        CandidatoMencion(f"m{i}", "monto" if i < 10 else "lugar", confianza=i / 10)
        for i in range(20)
    ]
    seleccionados = muestrear_menciones_estratificado_activo(candidatos, n_total=6)
    categorias_seleccionadas = {c.categoria for c in candidatos if c.mencion_id in seleccionados}
    assert categorias_seleccionadas == {"monto", "lugar"}


def test_muestrear_prioriza_menor_confianza_dentro_de_categoria() -> None:
    candidatos = [
        CandidatoMencion("alta", "monto", confianza=0.95),
        CandidatoMencion("baja", "monto", confianza=0.1),
        CandidatoMencion("media", "monto", confianza=0.5),
    ]
    seleccionados = muestrear_menciones_estratificado_activo(candidatos, n_total=1)
    assert seleccionados == ["baja"]


def test_muestrear_sin_candidatos_devuelve_vacio() -> None:
    assert muestrear_menciones_estratificado_activo([], n_total=10) == []


def test_guardar_y_cargar_calificaciones(tmp_path: Path) -> None:
    ruta = tmp_path / "calificaciones.csv"
    guardar_calificacion_mencion(ruta, "m1", "monto", CONFIRMADA, "ana")
    guardar_calificacion_mencion(
        ruta, "m2", "sector", RECHAZADA, "ana", categoria_corregida="sector", valor_corregido="6614"
    )

    calificaciones = cargar_calificaciones_menciones(ruta)
    assert len(calificaciones) == 2
    assert calificaciones[0]["decision"] == CONFIRMADA
    assert calificaciones[1]["valor_corregido"] == "6614"


def test_calcular_metricas_por_categoria() -> None:
    calificaciones = [
        {"categoria": "monto", "decision": CONFIRMADA},
        {"categoria": "monto", "decision": CONFIRMADA},
        {"categoria": "monto", "decision": RECHAZADA},
        {"categoria": "sector", "decision": RECHAZADA},
    ]
    metricas = calcular_metricas_por_categoria(calificaciones)
    por_nombre = {m.categoria: m for m in metricas}
    assert por_nombre["monto"].n == 3
    assert por_nombre["monto"].n_confirmadas == 2
    assert por_nombre["monto"].precision_aproximada == round(2 / 3, 4)
    assert por_nombre["sector"].precision_aproximada == 0.0


def test_escribir_resumen(tmp_path: Path) -> None:
    calificaciones = [
        {"categoria": "monto", "decision": CONFIRMADA},
        {"categoria": "monto", "decision": RECHAZADA},
    ]
    metricas = calcular_metricas_por_categoria(calificaciones)
    ruta_salida = tmp_path / "resumen.md"
    escribir_resumen(metricas, ruta_salida)
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "monto" in contenido
    assert "0.5" in contenido
