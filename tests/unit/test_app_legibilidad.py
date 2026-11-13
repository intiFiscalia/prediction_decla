"""Pruebas de la capa de presentación de la app (`decla.app.legibilidad`): no toca datos reales
ni `data/warehouse.duckdb`, solo transforma DataFrames sintéticos en memoria.
"""

from __future__ import annotations

import pandas as pd

from decla.app.legibilidad import (
    agregar_nombres_fenomeno,
    agregar_nombres_mecanismo,
    decodificar_indice_periodo,
    formatear_periodo_alertas,
)


def test_decodificar_indice_periodo_caso_simple() -> None:
    # indice_periodo = año*12 + mes (decla.emergencia.linea_base); 2026*12+9 = 24321.
    assert decodificar_indice_periodo(24321) == "2026-09"


def test_decodificar_indice_periodo_diciembre_no_desborda_al_anio_siguiente() -> None:
    # 2026*12+12 = 24324: el resto 0 debe decodificar a diciembre de 2026, no enero de 2027.
    assert decodificar_indice_periodo(24324) == "2026-12"


def test_formatear_periodo_alertas_decodifica_columna_entera() -> None:
    df = pd.DataFrame({"periodo": [24321], "n": [4]})
    resultado = formatear_periodo_alertas(df)
    assert resultado["periodo"].iloc[0] == "2026-09"


def test_formatear_periodo_alertas_no_toca_columna_ya_formateada_como_texto() -> None:
    df = pd.DataFrame({"periodo": ["2026-09"], "n": [4]})
    resultado = formatear_periodo_alertas(df)
    assert resultado["periodo"].iloc[0] == "2026-09"


def test_agregar_nombres_fenomeno_reemplaza_codigo_por_nombre() -> None:
    taxonomia = {"fenomenos": [{"codigo": "lavado_de_activos", "nombre": "Lavado de activos"}]}
    df = pd.DataFrame({"codigo_fenomeno": ["lavado_de_activos"], "n": [10]})
    resultado = agregar_nombres_fenomeno(df, taxonomia)
    assert resultado["codigo_fenomeno"].iloc[0] == "Lavado de activos"


def test_agregar_nombres_mecanismo_traduce_codigo_conocido_y_deja_desconocido() -> None:
    df = pd.DataFrame({"mecanismo": ["compra_ganado", "un_codigo_nuevo"], "n": [3, 1]})
    resultado = agregar_nombres_mecanismo(df)
    assert resultado["mecanismo"].tolist() == ["Compra de ganado", "un_codigo_nuevo"]
