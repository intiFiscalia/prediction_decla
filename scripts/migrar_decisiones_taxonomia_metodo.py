"""Utilidad de una sola vez: antes de que `fenomenos.grupos_descubiertos` empiece a incluir
fichas de NMF y aglomerativo (no solo HDBSCAN), todo `grupo_id` pasa a llevar el prefijo del
método (`hdbscan_0`, `nmf_3`, ...) para no colisionar entre métodos que reusan los mismos
números de etiqueta.

Las decisiones ya guardadas en `revision.decisiones_taxonomia` (del taller sobre los 2 grupos de
HDBSCAN, ADR 0013) quedaron con `grupo_id` sin prefijo ("0", "1"). Este script las reescribe a
"hdbscan_0"/"hdbscan_1" para que sigan emparejando con la tabla nueva. Idempotente: solo toca
filas cuyo `grupo_id` sea puramente numérico; si ya están prefijadas, no hace nada.

Uso:
    uv run python scripts/migrar_decisiones_taxonomia_metodo.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"

if __name__ == "__main__":
    con = duckdb.connect(str(RUTA_DUCKDB), read_only=False)
    con.execute("CREATE SCHEMA IF NOT EXISTS revision")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS revision.decisiones_taxonomia (
            grupo_id VARCHAR,
            decision VARCHAR,
            nombre_nuevo VARCHAR,
            grupo_fusion_destino VARCHAR,
            calificador VARCHAR,
            fecha TIMESTAMP
        )
        """
    )
    antes = (
        con.sql(
            "SELECT count(*) AS n FROM revision.decisiones_taxonomia "
            "WHERE grupo_id SIMILAR TO '[0-9]+'"
        )
        .pl()["n"]
        .item()
    )
    con.execute(
        "UPDATE revision.decisiones_taxonomia "
        "SET grupo_id = 'hdbscan_' || grupo_id "
        "WHERE grupo_id SIMILAR TO '[0-9]+'"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS revision.resultados_intrusion ("
        "    grupo_id VARCHAR, acierto BOOLEAN, calificador VARCHAR, fecha TIMESTAMP"
        ")"
    )
    con.execute(
        "UPDATE revision.resultados_intrusion "
        "SET grupo_id = 'hdbscan_' || grupo_id "
        "WHERE grupo_id SIMILAR TO '[0-9]+'"
    )
    con.close()
    print(f"Filas de decisiones_taxonomia migradas (grupo_id numérico -> hdbscan_<n>): {antes}")
