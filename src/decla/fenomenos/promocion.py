"""Promueve las predicciones de `fenomenos.asignacion_fenomeno_modelo` (ADR 0024) hacia
`fenomenos.asignacion_fenomeno` — la tabla que ya consumen `decla.analitica.indicadores`,
`decla.analitica.asociaciones`, `decla.prediccion.atipicos` y la app de consulta (ADR 0025).

Es un paso explícito y separado de `make entrenar-clasificador-fenomenos` (nunca automático):
un analista revisa las métricas en `reports/agregados/i4/clasificador_fenomenos_metricas.md` y
decide, código por código, si el modelo mejora sobre la membresía de clustering antes de
promoverlo. `make analitica` sigue reconstruyendo `fenomenos.asignacion_fenomeno` desde cero en
cada corrida (clustering + taxonomía, `decla.fenomenos.asignacion`); promover es un paso
ADICIONAL que se corre DESPUÉS de `make analitica` y ANTES de `make prediccion`/`make app` — si
se vuelve a correr `make analitica`, hay que promover de nuevo.

Solo se promueven códigos de la taxonomía congelada (`config/taxonomia/v1.0.yaml`):
`ruido_administrativo` y `no_clasificado` son clases de la herramienta de anotación (ADR 0024),
no fenómenos — promoverlas contaminaría los indicadores de fenómeno con una clase que no lo es.
"""

from __future__ import annotations

from typing import Any


def construir_filas_promocion(
    filas_modelo: list[dict[str, Any]],
    codigos_taxonomia: list[str],
    version_taxonomia: str,
) -> list[dict[str, Any]]:
    """`filas_modelo` son filas de `fenomenos.asignacion_fenomeno_modelo` (registro_uid,
    codigo_fenomeno, origen, confianza, version_modelo, run_id). Devuelve filas con el esquema
    de `fenomenos.asignacion_fenomeno` (registro_uid, codigo_fenomeno, metodo_origen,
    probabilidad, version_taxonomia, run_id), listas para `INSERT` — nunca para reemplazar la
    tabla completa (quien llama decide el modo de escritura).
    """
    codigos_validos = set(codigos_taxonomia)
    return [
        {
            "registro_uid": fila["registro_uid"],
            "codigo_fenomeno": fila["codigo_fenomeno"],
            "metodo_origen": f"clasificador_fenomenos:{fila['version_modelo']}",
            "probabilidad": fila["confianza"],
            "version_taxonomia": version_taxonomia,
            "run_id": fila["run_id"],
        }
        for fila in filas_modelo
        if fila["codigo_fenomeno"] in codigos_validos
    ]
