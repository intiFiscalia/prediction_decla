"""Prueba estática (plan_trabajo.md §9, Fase 10: "que las vistas no expongan texto sin
enmascarar"): nunca se importa ni ejecuta `decla.app.main` (llama a `main()` a nivel de módulo y
abriría `data/warehouse.duckdb` real — CLAUDE.md §2.1, Claude Code nunca toca esa base). En vez
de eso, se analiza el código fuente como texto en busca de las columnas sin enmascarar que
`decla.texto.orquestador` escribe en `texto.relato_procesado`
(`relato_normalizado`, `contexto_denuncia`, `descripcion_hecho` sin el sufijo `_enmascarada`,
`relato_enmascarado` de nivel de relato completo en vez del de segmento). Si alguna aparece en el
código de la app, es una fuga potencial de texto original.
"""

from __future__ import annotations

import re
from pathlib import Path

RUTA_APP = Path(__file__).resolve().parents[2] / "src" / "decla" / "app" / "main.py"

COLUMNAS_SIN_ENMASCARAR = [
    "relato_normalizado",
    "contexto_denuncia",
    "relato_enmascarado",  # válido solo como *columna de contexto*, no se usa en la app todavía
]


def _codigo_fuente() -> str:
    return RUTA_APP.read_text(encoding="utf-8")


def test_app_no_referencia_columnas_sin_enmascarar() -> None:
    codigo = _codigo_fuente()
    for columna in COLUMNAS_SIN_ENMASCARAR:
        assert columna not in codigo, f"La app referencia una columna sin enmascarar: {columna}"


def test_app_descripcion_hecho_solo_se_usa_con_sufijo_enmascarada() -> None:
    codigo = _codigo_fuente()
    # Cualquier aparición de "descripcion_hecho" debe venir seguida de "_enmascarada" (nunca la
    # columna sin máscara, que comparte el mismo prefijo literal).
    for coincidencia in re.finditer(r"descripcion_hecho(_\w+)?", codigo):
        sufijo = coincidencia.group(1)
        assert sufijo == "_enmascarada", (
            f"Uso de columna de descripción del hecho sin enmascarar: {coincidencia.group(0)!r}"
        )


def test_app_no_abre_la_base_en_escritura() -> None:
    codigo = _codigo_fuente()
    assert "solo_lectura=False" not in codigo
