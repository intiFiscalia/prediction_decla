import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROYECTO / "scripts"))

from evaluar_embeddings_fixtures import cargar_relatos_etiquetados, escribir_informe  # noqa: E402

from decla.texto.comparacion_modelos import ResultadoComparacionModelo  # noqa: E402


def test_cargar_relatos_etiquetados_sobre_fixtures() -> None:
    relatos = cargar_relatos_etiquetados()
    assert len(relatos) > 0
    primero = relatos[0]
    assert primero.registro_uid
    assert primero.texto
    assert primero.fenomeno_plantado


def test_escribir_informe_genera_markdown_con_tabla(tmp_path: Path) -> None:
    resultados = [
        ResultadoComparacionModelo("modelo-x", "media", 0.85, 5, 100),
        ResultadoComparacionModelo("modelo-y", "media", 0.72, 5, 100),
    ]
    ruta_salida = tmp_path / "embeddings.md"
    tiempos = {"modelo-x": 12.3, "modelo-y": 8.1}
    escribir_informe(resultados, tiempos, ram_mb=512.0, ruta_salida=ruta_salida)

    contenido = ruta_salida.read_text(encoding="utf-8")
    assert "modelo-x" in contenido
    assert "0.85" in contenido
    assert "12.3" in contenido
    assert "Precisión@k" in contenido
