from pathlib import Path

from decla.fenomenos.herramienta_anotacion_fenomeno import (
    CONFIRMADA,
    CORREGIDA,
    NO_CLASIFICADO,
    CandidatoFenomenoNuevo,
    CandidatoRelato,
    agrupar_calificaciones_por_calificador,
    calcular_cobertura_por_codigo,
    calcular_kappa_por_codigo,
    cargar_calificaciones_fenomeno,
    codigos_efectivos,
    construir_candidatos_desde_borrador,
    escribir_candidatos_fenomeno_nuevo,
    escribir_resumen,
    guardar_calificacion_fenomeno,
    identificar_candidatos_fenomeno_nuevo,
    muestrear_relatos_estratificado,
)


def test_muestrear_reparte_entre_estratos() -> None:
    candidatos = [
        CandidatoRelato(f"r{i}", ("fenomeno_a",) if i < 10 else ("fenomeno_b",))
        for i in range(20)
    ]
    seleccionados = muestrear_relatos_estratificado(candidatos, n_total=6)
    por_id = {c.registro_uid: c for c in candidatos}
    estratos_seleccionados = {por_id[uid].codigos_sugeridos for uid in seleccionados}
    assert estratos_seleccionados == {("fenomeno_a",), ("fenomeno_b",)}


def test_muestrear_sin_candidatos_devuelve_vacio() -> None:
    assert muestrear_relatos_estratificado([], n_total=10) == []


def test_guardar_y_cargar_calificaciones(tmp_path: Path) -> None:
    ruta = tmp_path / "calificaciones.csv"
    guardar_calificacion_fenomeno(ruta, "r1", ["organizacion_criminal"], CONFIRMADA, "ana")
    guardar_calificacion_fenomeno(
        ruta,
        "r2",
        ["organizacion_criminal"],
        CORREGIDA,
        "ana",
        codigos_corregidos=["ruido_administrativo"],
        notas="es un oficio de solicitud, no un hecho",
    )

    calificaciones = cargar_calificaciones_fenomeno(ruta)
    assert len(calificaciones) == 2
    assert calificaciones[0]["decision"] == CONFIRMADA
    assert calificaciones[1]["codigos_corregidos"] == "ruido_administrativo"


def test_codigos_efectivos_usa_corregidos_si_hay_correccion() -> None:
    fila = {
        "decision": CORREGIDA,
        "codigos_sugeridos": "organizacion_criminal",
        "codigos_corregidos": "",
    }
    assert codigos_efectivos(fila) == [NO_CLASIFICADO]


def test_codigos_efectivos_usa_sugeridos_si_se_confirma() -> None:
    fila = {
        "decision": CONFIRMADA,
        "codigos_sugeridos": "organizacion_criminal;ruido_administrativo",
        "codigos_corregidos": "",
    }
    assert codigos_efectivos(fila) == ["organizacion_criminal", "ruido_administrativo"]


def test_calcular_cobertura_por_codigo() -> None:
    calificaciones = [
        {"decision": CONFIRMADA, "codigos_sugeridos": "organizacion_criminal",
         "codigos_corregidos": ""},
        {"decision": CORREGIDA, "codigos_sugeridos": "organizacion_criminal",
         "codigos_corregidos": "ruido_administrativo"},
        {"decision": CORREGIDA, "codigos_sugeridos": "organizacion_criminal",
         "codigos_corregidos": ""},
    ]
    cobertura = calcular_cobertura_por_codigo(
        calificaciones, ["organizacion_criminal", "ruido_administrativo", NO_CLASIFICADO]
    )
    assert cobertura == {
        "organizacion_criminal": 1,
        "ruido_administrativo": 1,
        NO_CLASIFICADO: 1,
    }


def test_calcular_kappa_por_codigo_acuerdo_perfecto() -> None:
    calificaciones_a = [
        {"registro_uid": "r1", "decision": CONFIRMADA, "codigos_sugeridos": "a",
         "codigos_corregidos": ""},
        {"registro_uid": "r2", "decision": CONFIRMADA, "codigos_sugeridos": "b",
         "codigos_corregidos": ""},
        {"registro_uid": "r3", "decision": CONFIRMADA, "codigos_sugeridos": "a",
         "codigos_corregidos": ""},
        {"registro_uid": "r4", "decision": CONFIRMADA, "codigos_sugeridos": "b",
         "codigos_corregidos": ""},
    ]
    calificaciones_b = [dict(fila) for fila in calificaciones_a]

    kappa = calcular_kappa_por_codigo(calificaciones_a, calificaciones_b, ["a", "b"])
    assert kappa["a"] == 1.0
    assert kappa["b"] == 1.0


def test_calcular_kappa_por_codigo_sin_solapamiento_devuelve_none() -> None:
    calificaciones_a = [
        {"registro_uid": "r1", "decision": CONFIRMADA, "codigos_sugeridos": "a",
         "codigos_corregidos": ""}
    ]
    calificaciones_b = [
        {"registro_uid": "r2", "decision": CONFIRMADA, "codigos_sugeridos": "a",
         "codigos_corregidos": ""}
    ]
    kappa = calcular_kappa_por_codigo(calificaciones_a, calificaciones_b, ["a"])
    assert kappa["a"] is None


def test_agrupar_calificaciones_por_calificador() -> None:
    calificaciones = [
        {"registro_uid": "r1", "calificador": "ana"},
        {"registro_uid": "r2", "calificador": "ana"},
        {"registro_uid": "r1", "calificador": "beto"},
    ]
    agrupadas = agrupar_calificaciones_por_calificador(calificaciones)
    assert set(agrupadas) == {"ana", "beto"}
    assert len(agrupadas["ana"]) == 2
    assert len(agrupadas["beto"]) == 1


def test_escribir_resumen_incluye_cobertura_de_doble_anotacion(tmp_path: Path) -> None:
    ruta_salida = tmp_path / "resumen.md"
    escribir_resumen(
        {"a": 60},
        minimo_por_codigo=50,
        n_relatos_doble_anotados=5,
        n_relatos_totales=50,
        ruta_salida=ruta_salida,
    )
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "Relatos con doble anotación: 5/50 (10.0 %)" in contenido
    assert "20 % (no)" in contenido


def test_construir_candidatos_desde_borrador_agrupa_por_registro() -> None:
    filas = [
        {"registro_uid": "r1", "codigo_fenomeno": "a"},
        {"registro_uid": "r1", "codigo_fenomeno": "b"},
        {"registro_uid": "r2", "codigo_fenomeno": "a"},
    ]
    candidatos = construir_candidatos_desde_borrador(filas)
    por_id = {c.registro_uid: c.codigos_sugeridos for c in candidatos}
    assert por_id["r1"] == ("a", "b")
    assert por_id["r2"] == ("a",)


def test_escribir_resumen_marca_si_alcanza_el_minimo(tmp_path: Path) -> None:
    ruta_salida = tmp_path / "resumen.md"
    escribir_resumen({"a": 10, "b": 60}, minimo_por_codigo=50, ruta_salida=ruta_salida)
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "| a | 10 | no |" in contenido


def test_identificar_candidatos_fenomeno_nuevo_ignora_codigos_conocidos() -> None:
    codigos_conocidos = {"organizacion_criminal", NO_CLASIFICADO}
    calificaciones = [
        {"decision": CORREGIDA, "codigos_corregidos": "trafico_de_combustible"},
        {"decision": CORREGIDA, "codigos_corregidos": "trafico_de_combustible"},
        {"decision": CORREGIDA, "codigos_corregidos": "organizacion_criminal"},
        {"decision": CONFIRMADA, "codigos_corregidos": "mineria_ilegal"},
    ]
    candidatos = identificar_candidatos_fenomeno_nuevo(calificaciones, codigos_conocidos)
    assert candidatos == [CandidatoFenomenoNuevo("trafico_de_combustible", 2)]


def test_identificar_candidatos_fenomeno_nuevo_sin_candidatos_devuelve_vacio() -> None:
    calificaciones = [{"decision": CORREGIDA, "codigos_corregidos": "organizacion_criminal"}]
    assert identificar_candidatos_fenomeno_nuevo(calificaciones, {"organizacion_criminal"}) == []


def test_escribir_candidatos_fenomeno_nuevo(tmp_path: Path) -> None:
    ruta_salida = tmp_path / "candidatos.csv"
    escribir_candidatos_fenomeno_nuevo(
        [CandidatoFenomenoNuevo("trafico_de_combustible", 2)], ruta_salida=ruta_salida
    )
    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "trafico_de_combustible,2" in contenido
