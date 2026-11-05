"""Punto de entrada de `make evaluar` (plan_trabajo.md §9, Fase 10 completa; I4, Bloque 4B).

Ensambla `reports/agregados/evaluacion/v<version>.md` combinando dos fuentes:
1. **Histórico** (`config/metricas_componentes.yaml`): componentes cuya métrica se midió una
   vez y quedó documentada en un ADR/informe de cierre — no se recalculan aquí (serían cifras
   nuevas sin que haya pasado nada que las cambie; CLAUDE.md "no inventes cifras").
2. **Vivo**: lo que sí tiene sentido recalcular cada vez que corre — la retroprueba sintética de
   emergencia (reproducible, semilla fija), el resumen de `oro.atipicos` y `oro.alertas` si ya
   existen, y los fenómenos vigentes de `config/taxonomia/v1.0.yaml`.

Lee `data/warehouse.duckdb` en **solo lectura** — nunca escribe en la base real.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import duckdb
import yaml

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import conectar
from decla.emergencia.retroprueba import ejecutar_retroprueba

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_DUCKDB_DEFECTO = RAIZ_PROYECTO / "data" / "warehouse.duckdb"
RUTA_METRICAS_DEFECTO = RAIZ_PROYECTO / "config" / "metricas_componentes.yaml"
RUTA_TAXONOMIA_DEFECTO = RAIZ_PROYECTO / "config" / "taxonomia" / "v1.0.yaml"
RUTA_SALIDA_DEFECTO = RAIZ_PROYECTO / "reports" / "agregados" / "evaluacion" / "v1.md"


def _consultar_si_existe(
    conexion: duckdb.DuckDBPyConnection, consulta: str
) -> list[dict[str, Any]]:
    try:
        return conexion.sql(consulta).pl().to_dicts()
    except duckdb.CatalogException:
        return []


def calcular_resumen_vivo(
    conexion: duckdb.DuckDBPyConnection, ruta_taxonomia: Path
) -> dict[str, Any]:
    retroprueba = ejecutar_retroprueba()  # parámetros/semilla por defecto, documentados ahí

    atipicos = _consultar_si_existe(conexion, "SELECT count(*) AS n_registros FROM oro.atipicos")
    alertas_por_estado = _consultar_si_existe(
        conexion, "SELECT estado, count(*) AS n FROM oro.alertas GROUP BY estado"
    )

    fenomenos_vigentes: list[str] = []
    if ruta_taxonomia.exists():
        taxonomia = yaml.safe_load(ruta_taxonomia.read_text(encoding="utf-8")) or {}
        fenomenos_vigentes = [f["codigo"] for f in taxonomia.get("fenomenos", [])]

    return {
        "retroprueba_emergencia": {
            "tasa_falsas_alarmas": retroprueba.tasa_falsas_alarmas,
            "sensibilidad": retroprueba.sensibilidad,
            "tiempo_a_deteccion_medio": retroprueba.tiempo_a_deteccion_medio,
        },
        "atipicos_n_registros": atipicos[0]["n_registros"] if atipicos else None,
        "alertas_por_estado": alertas_por_estado,
        "fenomenos_vigentes": fenomenos_vigentes,
    }


def _construir_markdown(componentes_historicos: list[dict[str, Any]], vivo: dict[str, Any]) -> str:
    partes = [
        "# Evaluación consolidada (plan_trabajo.md §9, Fase 10)",
        "",
        "Toda cifra de este informe mide actividad institucional registrada, no incidencia real "
        "del delito. Ningún componente marcado \"pendiente_de_cifra_formal\" se presenta como si "
        "cumpliera el umbral — es una brecha documentada, no oculta.",
        "",
        "## Componentes históricos (medidos una vez, ver fuente)",
        "",
        "| Componente | Métrica | Valor | Umbral | Estado | Fuente |",
        "|---|---|---|---|---|---|",
    ]
    for c in componentes_historicos:
        partes.append(
            f"| {c['nombre']} | {c['metrica']} | {c['valor']} | {c['umbral']} | "
            f"{c['estado']} | {c['fuente']} |"
        )

    retro = vivo["retroprueba_emergencia"]
    n_atipicos = vivo["atipicos_n_registros"]
    texto_atipicos = (
        f"{n_atipicos} registros evaluados" if n_atipicos is not None else "sin correr todavía"
    )
    texto_alertas = vivo["alertas_por_estado"] or "sin correr todavía (`make emergencia`)"
    texto_fenomenos = ", ".join(vivo["fenomenos_vigentes"]) or "sin congelar todavía"

    partes += [
        "",
        "## Componentes vivos (recalculados en esta corrida)",
        "",
        f"- **Retroprueba sintética de emergencia** (`decla.emergencia.retroprueba`, "
        f"reproducible, no sobre datos reales): tasa de falsas alarmas = "
        f"{retro['tasa_falsas_alarmas']}, sensibilidad = {retro['sensibilidad']}, "
        f"tiempo a detección medio = {retro['tiempo_a_deteccion_medio']}.",
        f"- **Atípicos** (`oro.atipicos`, `make prediccion`): {texto_atipicos}. Precisión@k "
        f"pendiente de revisión por un analista (ver ficha de modelo).",
        f"- **Alertas reales** (`oro.alertas`): {texto_alertas}.",
        f"- **Fenómenos vigentes** (`config/taxonomia/v1.0.yaml`): {texto_fenomenos}.",
    ]
    return "\n".join(partes)


def ejecutar_evaluacion(
    ruta_duckdb: Path = RUTA_DUCKDB_DEFECTO,
    ruta_metricas: Path = RUTA_METRICAS_DEFECTO,
    ruta_taxonomia: Path = RUTA_TAXONOMIA_DEFECTO,
    ruta_salida: Path = RUTA_SALIDA_DEFECTO,
) -> Path:
    componentes_historicos = cargar_yaml(ruta_metricas)["componentes"]

    conexion = conectar(ruta_duckdb, solo_lectura=True)
    try:
        vivo = calcular_resumen_vivo(conexion, ruta_taxonomia)
    finally:
        conexion.close()

    contenido = _construir_markdown(componentes_historicos, vivo)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(contenido, encoding="utf-8")
    return ruta_salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=RUTA_DUCKDB_DEFECTO)
    parser.add_argument("--metricas", type=Path, default=RUTA_METRICAS_DEFECTO)
    parser.add_argument("--taxonomia", type=Path, default=RUTA_TAXONOMIA_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA_DEFECTO)
    args: Any = parser.parse_args(argv)

    ruta = ejecutar_evaluacion(args.duckdb, args.metricas, args.taxonomia, args.salida)
    print(f"Evaluación consolidada escrita en {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
