from pathlib import Path

from decla.conocimiento.herramienta_anotacion_menciones import (
    CONFIRMADA,
    CORREGIDA,
    RECHAZADA,
    CandidatoMecanismoNuevo,
    CandidatoMencion,
    calcular_metricas_por_categoria,
    calcular_precision_por_umbral,
    cargar_calificaciones_menciones,
    escribir_resumen,
    guardar_calificacion_mencion,
    identificar_candidatos_mecanismo_nuevo,
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
        ruta,
        "m2",
        "sector",
        RECHAZADA,
        "ana",
        categoria_corregida="sector",
        valor_corregido="6614",
        notas="lingotes sin origen documentado -> mineria_ilegal_oro (inferencia, no literal)",
    )

    calificaciones = cargar_calificaciones_menciones(ruta)
    assert len(calificaciones) == 2
    assert calificaciones[0]["decision"] == CONFIRMADA
    assert calificaciones[0]["notas"] == ""
    assert calificaciones[1]["valor_corregido"] == "6614"
    assert "mineria_ilegal_oro" in calificaciones[1]["notas"]


def test_guardar_calificacion_migra_csv_viejo_sin_columna_notas(tmp_path: Path) -> None:
    ruta = tmp_path / "calificaciones.csv"
    ruta.write_text("mencion_id,categoria,decision,categoria_corregida,valor_corregido,calificador\n"
                     "m0,monto,confirmada,,,ana\n", encoding="utf-8")

    guardar_calificacion_mencion(ruta, "m1", "monto", CONFIRMADA, "ana", notas="nota nueva")

    calificaciones = cargar_calificaciones_menciones(ruta)
    assert len(calificaciones) == 2
    assert calificaciones[0]["mencion_id"] == "m0"
    assert calificaciones[0]["notas"] == ""
    assert calificaciones[1]["notas"] == "nota nueva"


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


def test_calcular_precision_por_umbral_separa_aciertos_de_errores() -> None:
    calificaciones = [
        {"mencion_id": "m1", "categoria": "mecanismo", "decision": CONFIRMADA},
        {"mencion_id": "m2", "categoria": "mecanismo", "decision": RECHAZADA},
        {"mencion_id": "m3", "categoria": "mecanismo", "decision": CONFIRMADA},
        {"mencion_id": "otra_categoria", "categoria": "sector", "decision": CONFIRMADA},
    ]
    confianza_por_mencion = {"m1": 0.95, "m2": 0.80, "m3": 0.60}

    metricas = calcular_precision_por_umbral(
        calificaciones, confianza_por_mencion, "mecanismo", [0.5, 0.85]
    )
    por_umbral = {m.umbral_candidato: m for m in metricas}

    # En 0.5 entran las 3 (m1, m2, m3): 2 confirmadas de 3.
    assert por_umbral[0.5].n_evaluadas == 3
    assert por_umbral[0.5].precision_aproximada == round(2 / 3, 4)
    # En 0.85 solo entra m1 (0.95 >= 0.85): 1 confirmada de 1.
    assert por_umbral[0.85].n_evaluadas == 1
    assert por_umbral[0.85].precision_aproximada == 1.0


def test_calcular_precision_por_umbral_sin_evaluadas_devuelve_none() -> None:
    calificaciones = [{"mencion_id": "m1", "categoria": "mecanismo", "decision": CONFIRMADA}]
    metricas = calcular_precision_por_umbral(calificaciones, {"m1": 0.5}, "mecanismo", [0.9])
    assert metricas[0].n_evaluadas == 0
    assert metricas[0].precision_aproximada is None


def test_identificar_candidatos_mecanismo_nuevo_ignora_codigos_conocidos() -> None:
    codigos_conocidos = {"compra_ganado", "mineria_ilegal_oro"}
    calificaciones = [
        {
            "decision": CORREGIDA,
            "categoria": "mecanismo",
            "categoria_corregida": "",
            "valor_corregido": "mineria_ilegal_oro",
        },
        {
            "decision": CORREGIDA,
            "categoria": "mecanismo",
            "categoria_corregida": "",
            "valor_corregido": "trata_personas",
        },
        {
            "decision": CORREGIDA,
            "categoria": "mecanismo",
            "categoria_corregida": "",
            "valor_corregido": "trata_personas",
        },
        {
            "decision": CONFIRMADA,
            "categoria": "mecanismo",
            "categoria_corregida": "",
            "valor_corregido": "apuestas_ilegales",
        },
        {
            "decision": CORREGIDA,
            "categoria": "sector",
            "categoria_corregida": "",
            "valor_corregido": "9900",
        },
    ]
    candidatos = identificar_candidatos_mecanismo_nuevo(calificaciones, codigos_conocidos)
    assert candidatos == [CandidatoMecanismoNuevo("trata_personas", 2)]


def test_identificar_candidatos_mecanismo_nuevo_sin_candidatos_devuelve_vacio() -> None:
    calificaciones = [
        {
            "decision": CORREGIDA,
            "categoria": "mecanismo",
            "categoria_corregida": "",
            "valor_corregido": "compra_ganado",
        }
    ]
    assert identificar_candidatos_mecanismo_nuevo(calificaciones, {"compra_ganado"}) == []


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
