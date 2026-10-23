from pathlib import Path

import pytest

from decla.ingesta.lectores import leer_csv, leer_tabla, leer_xlsx

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_leer_csv_cuenta_y_excluye_filas_vacias(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.csv"
    ruta.write_text("A,B,C\n1,2,3\n\n,,\n4,5,6\n", encoding="utf-8")
    tabla = leer_csv(ruta)
    assert tabla.columnas == ["A", "B", "C"]
    assert tabla.n_filas_datos == 2
    assert tabla.n_filas_vacias == 2
    assert tabla.n_filas_total == 4
    assert tabla.fila_origen == [2, 5]


def test_leer_csv_detecta_separador_punto_y_coma(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.csv"
    ruta.write_text("A;B;C\n1;2;3\n4;5;6\n", encoding="utf-8")
    tabla = leer_csv(ruta)
    assert tabla.columnas == ["A", "B", "C"]
    assert tabla.filas[0] == {"A": "1", "B": "2", "C": "3"}
    assert any("separador detectado" in a for a in tabla.advertencias)


def test_leer_csv_detecta_codificacion_cp1252(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.csv"
    ruta.write_bytes("NOMBRE\nJOSÉ ñAÑEZ\n".encode("cp1252"))
    tabla = leer_csv(ruta)
    assert any("cp1252" in a for a in tabla.advertencias)
    assert tabla.filas[0]["NOMBRE"] == "JOSÉ ñAÑEZ"


def test_leer_csv_fila_con_menos_celdas_se_rellena_con_none(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.csv"
    ruta.write_text("A,B,C\n1,2\n", encoding="utf-8")
    tabla = leer_csv(ruta)
    assert tabla.filas[0] == {"A": "1", "B": "2", "C": None}


def test_leer_csv_fila_con_mas_celdas_se_trunca_y_advierte(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.csv"
    ruta.write_text("A,B\n1,2,3\n", encoding="utf-8")
    tabla = leer_csv(ruta)
    assert tabla.filas[0] == {"A": "1", "B": "2"}
    assert any("más celdas" not in a and "celdas para" in a for a in tabla.advertencias)


def test_leer_csv_fixture_real_conserva_defectos_de_id() -> None:
    tabla = leer_csv(RAIZ_FIXTURES / "casos_sinteticos.csv")
    assert len(tabla.columnas) == 40
    assert tabla.n_filas_vacias > 0
    ids_con_punto0 = [
        f["CASO_ID"] for f in tabla.filas if f["CASO_ID"] and f["CASO_ID"].endswith(".0")
    ]
    assert ids_con_punto0, "el lector no debe reparar el defecto '.0', solo observarlo"


def test_leer_xlsx_fixture_real_conserva_tipos_mixtos() -> None:
    tabla = leer_xlsx(RAIZ_FIXTURES / "casos_sinteticos.xlsx")
    assert len(tabla.columnas) == 40
    caso_noticia = [f["CASO_NOTICIA"] for f in tabla.filas if f["CASO_NOTICIA"]]
    # Alguna fila debe mostrar el defecto de precisión de float64 en un entero de 21 dígitos,
    # o el sufijo ".0" de una celda numérica: ambos son evidencia de lectura mixta de tipos.
    assert any(("e+" in v) or (".0" in v) for v in caso_noticia)


def test_leer_tabla_extension_no_soportada(tmp_path: Path) -> None:
    ruta = tmp_path / "prueba.txt"
    ruta.write_text("contenido")
    with pytest.raises(ValueError, match="no soportada"):
        leer_tabla(ruta)


def test_leer_tabla_despacha_por_extension() -> None:
    tabla = leer_tabla(RAIZ_FIXTURES / "relatos_sinteticos.csv")
    assert tabla.columnas == ["CASO_NOTICIA", "RELATO"]
