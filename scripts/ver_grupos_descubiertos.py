"""Utilidad de una sola vez: imprime en pantalla los campos agregados de
`fenomenos.grupos_descubiertos` (tamaño de grupo, indicadores de dominancia, términos c-TF-IDF)
para que la persona los pegue en el chat. No imprime texto de relatos individuales ni
identificadores (plan_trabajo.md §7; CLAUDE.md §2.1).
"""

from pathlib import Path

import duckdb
import polars as pl

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"

if __name__ == "__main__":
    con = duckdb.connect(str(RUTA_DUCKDB), read_only=True)
    df = con.sql(
        """
        SELECT grupo_id, n_miembros, dominancia_plantilla, dominancia_unidad, terminos_c_tfidf
        FROM fenomenos.grupos_descubiertos
        ORDER BY n_miembros DESC
        """
    ).pl()
    with pl.Config(fmt_str_lengths=200, tbl_width_chars=200):
        print(df)
