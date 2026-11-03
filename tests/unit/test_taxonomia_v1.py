from datetime import datetime

from decla.fenomenos.taxonomia_v1 import construir_taxonomia_v1, resolver_decisiones

GRUPOS = [
    {
        "grupo_id": "0",
        "n_miembros": 293,
        "terminos_c_tfidf": "lavado, activo, dinero, delito",
        "medoides": "uid_a, uid_b",
        "dominancia_plantilla": 0.83,
        "dominancia_unidad": 0.1,
    },
    {
        "grupo_id": "1",
        "n_miembros": 53,
        "terminos_c_tfidf": "direccion, oficio, solicitud",
        "medoides": "uid_c",
        "dominancia_plantilla": 0.96,
        "dominancia_unidad": 0.25,
    },
]


def _decision(grupo_id: str, decision: str, fecha: str, nombre_nuevo: str | None = None) -> dict:
    return {
        "grupo_id": grupo_id,
        "decision": decision,
        "nombre_nuevo": nombre_nuevo,
        "grupo_fusion_destino": None,
        "calificador": "ANALISTA1",
        "fecha": datetime.fromisoformat(fecha),
    }


def test_resolver_decisiones_toma_la_mas_reciente_por_grupo() -> None:
    decisiones = [
        _decision("0", "artefacto", "2026-10-30T10:54:11"),
        _decision("0", "fusionar", "2026-10-30T10:54:22"),
        _decision("0", "aprobar", "2026-10-30T16:13:10"),
        _decision("0", "renombrar", "2026-10-30T16:22:13", nombre_nuevo="Lavado de activos"),
    ]
    resueltas = resolver_decisiones(decisiones)
    assert resueltas["0"].decision_final == "aprobar"
    assert resueltas["0"].nombre_final == "Lavado de activos"


def test_resolver_decisiones_estado_y_nombre_son_ejes_independientes() -> None:
    """Un `renombrar` anterior al `aprobar` final sigue siendo el nombre vigente: no hace falta
    volver a renombrar después de aprobar."""
    decisiones = [
        _decision("1", "renombrar", "2026-10-30T09:00:00", nombre_nuevo="Primer intento"),
        _decision("1", "aprobar", "2026-10-30T09:05:00"),
    ]
    resueltas = resolver_decisiones(decisiones)
    assert resueltas["1"].decision_final == "aprobar"
    assert resueltas["1"].nombre_final == "Primer intento"


def test_construir_taxonomia_v1_incluye_solo_aprobados_con_nombre() -> None:
    decisiones = [
        _decision("0", "artefacto", "2026-10-30T10:54:11"),
        _decision("0", "fusionar", "2026-10-30T10:54:22"),
        _decision("1", "dividir", "2026-10-30T10:54:17"),
        _decision("1", "fusionar", "2026-10-30T10:54:24"),
        _decision("0", "aprobar", "2026-10-30T16:13:10"),
        _decision("1", "artefacto", "2026-10-30T16:13:58"),
        _decision("0", "renombrar", "2026-10-30T16:22:13", nombre_nuevo="Lavado de activos"),
    ]
    resultado = construir_taxonomia_v1(decisiones, GRUPOS)

    assert len(resultado.fenomenos) == 1
    fenomeno = resultado.fenomenos[0]
    assert fenomeno["nombre"] == "Lavado de activos"
    assert fenomeno["codigo"] == "lavado_de_activos"
    assert fenomeno["n_miembros"] == 293
    assert fenomeno["terminos_dominantes"] == ["lavado", "activo", "dinero", "delito"]
    assert fenomeno["ids_ejemplo"] == ["uid_a", "uid_b"]
    assert fenomeno["definicion"] == "pendiente_de_redaccion_por_analista"
    assert fenomeno["grupo_id_origen"] == "0"
    assert fenomeno["metodo_origen"] == "0"  # sin prefijo de método en este fixture antiguo

    assert len(resultado.excluidos) == 1
    assert resultado.excluidos[0]["grupo_id"] == "1"
    assert resultado.excluidos[0]["motivo"] == "artefacto"

    assert resultado.pendientes == []
    assert resultado.sin_decision == []


def test_construir_taxonomia_v1_grupo_sin_nombre_usa_respaldo() -> None:
    decisiones = [_decision("0", "aprobar", "2026-10-30T16:13:10")]
    resultado = construir_taxonomia_v1(decisiones, [GRUPOS[0]])
    assert resultado.fenomenos[0]["nombre"] == "Grupo 0 (sin nombre asignado)"
    assert resultado.fenomenos[0]["codigo"] == "grupo_0_sin_nombre_asignado"


def test_construir_taxonomia_v1_dividir_y_fusionar_quedan_pendientes_no_se_adivinan() -> None:
    decisiones = [_decision("0", "dividir", "2026-10-30T10:00:00")]
    resultado = construir_taxonomia_v1(decisiones, [GRUPOS[0]])
    assert resultado.fenomenos == []
    assert resultado.excluidos == []
    assert len(resultado.pendientes) == 1
    assert resultado.pendientes[0]["decision"] == "dividir"


def test_construir_taxonomia_v1_grupo_sin_decision_queda_listado() -> None:
    resultado = construir_taxonomia_v1([], [GRUPOS[0]])
    assert resultado.sin_decision == ["0"]


def test_construir_taxonomia_v1_extrae_metodo_origen_de_grupo_id_prefijado() -> None:
    """Desde ADR 0014, `grupo_id` real siempre lleva el prefijo del método (`nmf_4`,
    `agglomerative_1`, ...). `metodo_origen` es todo lo anterior al último `_`."""
    grupo = {**GRUPOS[0], "grupo_id": "nmf_4"}
    decisiones = [_decision("nmf_4", "aprobar", "2026-11-03T09:37:52", nombre_nuevo="Empresas")]
    resultado = construir_taxonomia_v1(decisiones, [grupo])
    assert resultado.fenomenos[0]["grupo_id_origen"] == "nmf_4"
    assert resultado.fenomenos[0]["metodo_origen"] == "nmf"


def test_construir_taxonomia_v1_codigos_duplicados_se_desambiguan() -> None:
    grupos = [
        {**GRUPOS[0], "grupo_id": "0"},
        {**GRUPOS[0], "grupo_id": "2"},
    ]
    decisiones = [
        _decision("0", "aprobar", "2026-10-30T16:00:00", nombre_nuevo="Lavado"),
        _decision("2", "aprobar", "2026-10-30T16:00:00", nombre_nuevo="Lavado"),
    ]
    resultado = construir_taxonomia_v1(decisiones, grupos)
    codigos = {f["codigo"] for f in resultado.fenomenos}
    assert len(codigos) == 2
