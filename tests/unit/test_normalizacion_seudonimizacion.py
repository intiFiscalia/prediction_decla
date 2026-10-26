from pathlib import Path

from decla.normalizacion.seudonimizacion import obtener_o_crear_clave, seudonimizar


def test_obtener_o_crear_clave_genera_y_persiste(tmp_path: Path) -> None:
    ruta_clave = tmp_path / "claves" / "hmac.key"
    assert not ruta_clave.exists()

    clave1 = obtener_o_crear_clave(ruta_clave)
    assert ruta_clave.exists()
    assert len(clave1) == 32

    clave2 = obtener_o_crear_clave(ruta_clave)
    assert clave1 == clave2  # segunda llamada reutiliza la misma clave


def test_seudonimizar_es_determinista_con_la_misma_clave() -> None:
    clave = b"0" * 32
    assert seudonimizar("123456789", clave) == seudonimizar("123456789", clave)


def test_seudonimizar_cambia_con_clave_distinta() -> None:
    assert seudonimizar("123456789", b"0" * 32) != seudonimizar("123456789", b"1" * 32)


def test_seudonimizar_no_es_reversible_a_simple_vista() -> None:
    token = seudonimizar("123456789", b"0" * 32)
    assert "123456789" not in token


def test_seudonimizar_none() -> None:
    assert seudonimizar(None, b"0" * 32) is None
