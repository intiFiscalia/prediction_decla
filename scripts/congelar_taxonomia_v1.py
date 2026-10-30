"""Utilidad de una sola vez: congela `config/taxonomia/v1.0.yaml` a partir de las decisiones
del taller de revisión humana (`revision.decisiones_taxonomia`, plan_trabajo.md §7.2) sobre
`fenomenos.grupos_descubiertos`. Solo lectura sobre DuckDB; no corre al mismo tiempo que otro
proceso escriba la base (ver `decla.comun.duckdb_io`).

Uso:
    uv run python scripts/congelar_taxonomia_v1.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from decla.fenomenos.taxonomia_v1 import construir_taxonomia_v1, escribir_taxonomia_v1

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DUCKDB = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_SALIDA = RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml"

if __name__ == "__main__":
    con = duckdb.connect(str(RUTA_DUCKDB), read_only=True)
    decisiones = con.sql("SELECT * FROM revision.decisiones_taxonomia").pl().to_dicts()
    grupos = con.sql("SELECT * FROM fenomenos.grupos_descubiertos").pl().to_dicts()
    con.close()

    resultado = construir_taxonomia_v1(decisiones, grupos)
    escribir_taxonomia_v1(resultado, RUTA_SALIDA)

    print(f"Escrito: {RUTA_SALIDA}")
    print(f"  Fenómenos aprobados: {len(resultado.fenomenos)}")
    for f in resultado.fenomenos:
        print(f"    - {f['codigo']} ({f['nombre']}): n_miembros={f['n_miembros']}")
    print(f"  Excluidos (artefacto/descartar): {len(resultado.excluidos)}")
    for e in resultado.excluidos:
        print(f"    - grupo {e['grupo_id']}: {e['motivo']}")
    print(
        f"  Pendientes (dividir/fusionar, sin resolver automáticamente): "
        f"{len(resultado.pendientes)}"
    )
    for p in resultado.pendientes:
        print(f"    - grupo {p['grupo_id']}: {p['decision']}")
    if resultado.sin_decision:
        print(f"  Grupos sin ninguna decisión registrada: {resultado.sin_decision}")
