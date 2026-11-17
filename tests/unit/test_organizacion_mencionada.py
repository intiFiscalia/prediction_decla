from pathlib import Path

from decla.fenomenos.organizacion_mencionada import (
    CandidatoOrganizacion,
    escribir_candidatos_organizacion,
    identificar_candidatos_organizacion,
)


def test_identificar_candidatos_organizacion_cuenta_relatos_distintos() -> None:
    filas = [
        {"registro_uid": "r1", "organizacion_nombre_crudo": "grupo armado FARK"},
        {"registro_uid": "r2", "organizacion_nombre_crudo": "grupo armado FARK"},
        {"registro_uid": "r3", "organizacion_nombre_crudo": "Clan X"},
    ]
    candidatos = identificar_candidatos_organizacion(filas)
    assert candidatos == [
        CandidatoOrganizacion("grupo armado FARK", 2),
        CandidatoOrganizacion("Clan X", 1),
    ]


def test_identificar_candidatos_organizacion_no_duplica_por_fila_repetida() -> None:
    filas = [
        {"registro_uid": "r1", "organizacion_nombre_crudo": "Clan X"},
        {"registro_uid": "r1", "organizacion_nombre_crudo": "Clan X"},
    ]
    candidatos = identificar_candidatos_organizacion(filas)
    assert candidatos == [CandidatoOrganizacion("Clan X", 1)]


def test_identificar_candidatos_organizacion_sin_filas_devuelve_vacio() -> None:
    assert identificar_candidatos_organizacion([]) == []


def test_escribir_candidatos_organizacion(tmp_path: Path) -> None:
    ruta = tmp_path / "candidatos.csv"
    escribir_candidatos_organizacion([CandidatoOrganizacion("Clan X", 3)], ruta)
    contenido = ruta.read_text(encoding="utf-8")
    assert "Clan X,3" in contenido
