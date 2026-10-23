from pathlib import Path

import polars as pl

from decla.calidad.muestra import (
    construir_muestra,
    escribir_formulario_anotacion,
    escribir_muestra_html,
)

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _casos_sinteticos() -> list[dict]:
    territorios = [("META", "CONTRABANDO"), ("ANTIOQUIA", "LAVADO DE ACTIVOS")]
    filas = []
    for i in range(20):
        dpto, delito = territorios[i % 2]
        anio = 2024 + (i % 3)
        filas.append(
            {
                "CASO_NOTICIA": f"N{i}",
                "FECHA_CREACION": f"1/1/{anio}",
                "DEPARTAMENTO_HECHOS": dpto,
                "DELITO": delito,
            }
        )
    return filas


def _relatos_sinteticos() -> list[dict]:
    return [
        {"CASO_NOTICIA": f"N{i}", "RELATO": f"relato de prueba numero {i} " * (3 + i % 5)}
        for i in range(20)
    ]


def test_construir_muestra_respeta_limite_n() -> None:
    muestra = construir_muestra(_casos_sinteticos(), _relatos_sinteticos(), n=5, semilla=1)
    assert len(muestra) == 5
    assert len({m.relato_id for m in muestra}) == 5


def test_construir_muestra_cubre_varios_estratos() -> None:
    muestra = construir_muestra(_casos_sinteticos(), _relatos_sinteticos(), n=20, semilla=1)
    departamentos = {m.departamento for m in muestra}
    anios = {m.anio for m in muestra}
    assert len(departamentos) > 1
    assert len(anios) > 1


def test_construir_muestra_enmascara_patrones_personales() -> None:
    casos = _casos_sinteticos()
    relatos = [
        {"CASO_NOTICIA": "N0", "RELATO": "contacto: juan@correo-ficticio.example C.C. 1234567890"}
    ]
    muestra = construir_muestra(casos, relatos, n=1, semilla=1)
    assert len(muestra) == 1
    assert "juan@correo-ficticio.example" not in muestra[0].texto_mostrado
    assert "1234567890" not in muestra[0].texto_mostrado


def test_escribir_muestra_html_y_formulario(tmp_path: Path) -> None:
    muestra = construir_muestra(_casos_sinteticos(), _relatos_sinteticos(), n=5, semilla=1)
    ruta_html = tmp_path / "muestra_lectura" / "muestra.html"
    ruta_csv = tmp_path / "muestra_lectura" / "anotacion.csv"

    escribir_muestra_html(muestra, ruta_html)
    escribir_formulario_anotacion(muestra, ruta_csv)

    assert ruta_html.exists()
    contenido_html = ruta_html.read_text(encoding="utf-8")
    assert "Aviso" in contenido_html
    assert all(m.relato_id in contenido_html for m in muestra)

    df_csv = pl.read_csv(ruta_csv)
    assert df_csv.height == len(muestra)
    assert "fenomeno_anotado" in df_csv.columns


def test_construir_muestra_contra_fixtures_reales() -> None:
    casos_df = pl.read_csv(RAIZ_FIXTURES / "casos_sinteticos.csv", infer_schema_length=0)
    relatos_df = pl.read_csv(RAIZ_FIXTURES / "relatos_sinteticos.csv", infer_schema_length=0)
    filas_casos = casos_df.to_dicts()
    filas_relatos = relatos_df.to_dicts()

    muestra = construir_muestra(filas_casos, filas_relatos, n=30, semilla=1)
    assert 0 < len(muestra) <= 30
