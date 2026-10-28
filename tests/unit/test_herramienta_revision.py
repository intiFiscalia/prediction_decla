import duckdb

from decla.fenomenos.herramienta_revision import (
    APROBAR,
    FUSIONAR,
    calcular_tasa_intrusion,
    cargar_decisiones,
    cargar_resultados_intrusion,
    generar_caso_intrusion,
    guardar_decision,
    registrar_resultado_intrusion,
)


def test_guardar_y_cargar_decisiones() -> None:
    conexion = duckdb.connect(":memory:")
    guardar_decision(conexion, "0", APROBAR, "ana")
    guardar_decision(conexion, "1", FUSIONAR, "ana", grupo_fusion_destino="0")

    decisiones = cargar_decisiones(conexion)
    assert len(decisiones) == 2
    assert decisiones[0]["decision"] == APROBAR
    assert decisiones[1]["grupo_fusion_destino"] == "0"
    conexion.close()


def test_generar_caso_intrusion_devuelve_seis_registros() -> None:
    caso = generar_caso_intrusion(
        "0", [f"g0_{i}" for i in range(5)], ["g1_0", "g1_1"], semilla=1
    )
    assert caso is not None
    assert len(caso.registros_uid_mostrados) == 6
    assert caso.registros_uid_mostrados[caso.indice_intruso] in {"g1_0", "g1_1"}


def test_generar_caso_intrusion_es_deterministico() -> None:
    kwargs = {
        "grupo_id": "0",
        "registros_del_grupo": [f"g0_{i}" for i in range(5)],
        "registros_de_otro_grupo": ["g1_0", "g1_1"],
        "semilla": 42,
    }
    caso_a = generar_caso_intrusion(**kwargs)
    caso_b = generar_caso_intrusion(**kwargs)
    assert caso_a == caso_b


def test_generar_caso_intrusion_grupo_muy_chico_devuelve_none() -> None:
    caso = generar_caso_intrusion("0", ["g0_0", "g0_1"], ["g1_0"], semilla=1)
    assert caso is None


def test_generar_caso_intrusion_sin_otro_grupo_devuelve_none() -> None:
    caso = generar_caso_intrusion("0", [f"g0_{i}" for i in range(5)], [], semilla=1)
    assert caso is None


def test_registrar_y_calcular_tasa_intrusion() -> None:
    conexion = duckdb.connect(":memory:")
    registrar_resultado_intrusion(conexion, "0", True, "ana")
    registrar_resultado_intrusion(conexion, "1", True, "ana")
    registrar_resultado_intrusion(conexion, "2", False, "ana")

    resultados = cargar_resultados_intrusion(conexion)
    assert calcular_tasa_intrusion(resultados) == round(2 / 3, 4)
    conexion.close()


def test_calcular_tasa_intrusion_vacio() -> None:
    assert calcular_tasa_intrusion([]) == 0.0
