import pytest

from decla.comun.registro import (
    CampoNoPermitidoError,
    configurar_logging,
    obtener_logger,
    registrar_evento,
)


def test_registrar_evento_acepta_campos_permitidos(capsys: pytest.CaptureFixture[str]) -> None:
    configurar_logging()
    logger = obtener_logger("prueba")
    registrar_evento(logger, "lote procesado", run_id="abc", n_entrada=120, n_salida=118)
    salida = capsys.readouterr().out
    assert "lote procesado" in salida
    assert "n_entrada" in salida


@pytest.mark.parametrize("campo", ["fila", "valor", "relato", "nombre", "documento", "telefono"])
def test_registrar_evento_rechaza_contenido_de_fila(campo: str) -> None:
    configurar_logging()
    logger = obtener_logger("prueba")
    with pytest.raises(CampoNoPermitidoError):
        registrar_evento(logger, "evento sospechoso", **{campo: "dato sensible sintetico"})
