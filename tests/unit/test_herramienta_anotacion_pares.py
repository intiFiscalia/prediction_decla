from pathlib import Path

from decla.texto.herramienta_anotacion_pares import (
    DISTINTO,
    MISMO_FENOMENO,
    NO_SEGURO,
    calcular_acuerdo,
    cargar_calificaciones,
    escribir_resumen,
    guardar_calificacion,
    muestrear_pares,
)


def test_muestrear_pares_sin_repetir_pares() -> None:
    pares = muestrear_pares([f"u{i}" for i in range(10)], n_pares=15, semilla=1)
    assert len(pares) == 15
    assert len(set(pares)) == 15
    for a, b in pares:
        assert a != b


def test_muestrear_pares_recorta_al_maximo_posible() -> None:
    pares = muestrear_pares(["u1", "u2", "u3"], n_pares=100, semilla=1)
    assert len(pares) == 3  # máximo posible con 3 elementos: C(3,2) = 3


def test_muestrear_pares_es_deterministico_con_la_misma_semilla() -> None:
    universo = [f"u{i}" for i in range(20)]
    pares_a = muestrear_pares(universo, n_pares=10, semilla=42)
    pares_b = muestrear_pares(universo, n_pares=10, semilla=42)
    assert pares_a == pares_b


def test_guardar_y_cargar_calificaciones(tmp_path: Path) -> None:
    ruta = tmp_path / "calificaciones.csv"
    guardar_calificacion(ruta, "u1", "u2", MISMO_FENOMENO, "ana")
    guardar_calificacion(ruta, "u3", "u4", DISTINTO, "ana")

    calificaciones = cargar_calificaciones(ruta)
    assert len(calificaciones) == 2
    assert calificaciones[0]["calificacion"] == MISMO_FENOMENO
    assert calificaciones[1]["calificador"] == "ana"


def test_cargar_calificaciones_archivo_inexistente_devuelve_vacio(tmp_path: Path) -> None:
    assert cargar_calificaciones(tmp_path / "no_existe.csv") == []


def test_calcular_acuerdo_con_vectores_perfectamente_alineados() -> None:
    calificaciones = [
        {"registro_uid_a": "u1", "registro_uid_b": "u2", "calificacion": MISMO_FENOMENO},
        {"registro_uid_a": "u3", "registro_uid_b": "u4", "calificacion": DISTINTO},
    ]
    vectores = {
        "u1": [1.0, 0.0],
        "u2": [0.99, 0.01],
        "u3": [1.0, 0.0],
        "u4": [0.0, 1.0],
    }
    resumen = calcular_acuerdo(calificaciones, vectores, umbral_similitud=0.5)
    assert resumen.n_pares == 2
    assert resumen.precision_en_umbral == 1.0


def test_calcular_acuerdo_ignora_pares_no_seguro_y_sin_vector() -> None:
    calificaciones = [
        {"registro_uid_a": "u1", "registro_uid_b": "u2", "calificacion": NO_SEGURO},
        {"registro_uid_a": "u3", "registro_uid_b": "u4", "calificacion": MISMO_FENOMENO},
        {"registro_uid_a": "u5", "registro_uid_b": "u6", "calificacion": DISTINTO},
    ]
    vectores = {"u3": [1.0, 0.0], "u4": [0.9, 0.1]}
    resumen = calcular_acuerdo(calificaciones, vectores)
    assert resumen.n_pares == 1
    assert resumen.spearman is None  # menos de 2 pares válidos


def test_calcular_acuerdo_sin_pares_validos() -> None:
    resumen = calcular_acuerdo([], {})
    assert resumen.n_pares == 0
    assert resumen.spearman is None
    assert resumen.precision_en_umbral is None


def test_escribir_resumen(tmp_path: Path) -> None:
    calificaciones = [
        {"registro_uid_a": "u1", "registro_uid_b": "u2", "calificacion": MISMO_FENOMENO},
        {"registro_uid_a": "u3", "registro_uid_b": "u4", "calificacion": DISTINTO},
    ]
    vectores = {"u1": [1.0, 0.0], "u2": [0.9, 0.1], "u3": [1.0, 0.0], "u4": [0.0, 1.0]}
    resumen = calcular_acuerdo(calificaciones, vectores)
    ruta_salida = tmp_path / "pares_calificados.md"
    escribir_resumen(resumen, ruta_salida)

    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "Spearman" in contenido
    assert str(resumen.n_pares) in contenido
