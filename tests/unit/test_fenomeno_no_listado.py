from pathlib import Path

from decla.fenomenos.fenomeno_no_listado import (
    CandidatoFenomenoLLM,
    escribir_candidatos_fenomeno_llm,
    identificar_candidatos_fenomeno_llm,
)


def test_identificar_candidatos_fenomeno_llm_cuenta_relatos_distintos() -> None:
    filas = [
        {"registro_uid": "r1", "texto_crudo": "hallazgo de esmeraldas sin documentación"},
        {"registro_uid": "r2", "texto_crudo": "hallazgo de esmeraldas sin documentación"},
        {"registro_uid": "r3", "texto_crudo": "transporte de joyas sin declarar"},
    ]
    candidatos = identificar_candidatos_fenomeno_llm(filas)
    assert candidatos == [
        CandidatoFenomenoLLM("hallazgo de esmeraldas sin documentación", 2),
        CandidatoFenomenoLLM("transporte de joyas sin declarar", 1),
    ]


def test_identificar_candidatos_fenomeno_llm_sin_filas_devuelve_vacio() -> None:
    assert identificar_candidatos_fenomeno_llm([]) == []


def test_escribir_candidatos_fenomeno_llm(tmp_path: Path) -> None:
    ruta = tmp_path / "candidatos.csv"
    escribir_candidatos_fenomeno_llm(
        [CandidatoFenomenoLLM("hallazgo de esmeraldas sin documentación", 5)], ruta
    )
    contenido = ruta.read_text(encoding="utf-8")
    assert "hallazgo de esmeraldas sin documentación,5" in contenido
