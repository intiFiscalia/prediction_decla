"""Detección de registros atípicos (plan_trabajo.md §8.4, Fase 9; I4, Bloque 4A).

Dos señales independientes, nunca combinadas en un solo score: promediar una escala de anomalía
estructural (Isolation Forest) con una de distancia semántica (coseno a un centroide de fenómeno)
sin una base estadística para el peso relativo sería inventar una cifra (CLAUDE.md "no inventes
cifras"). Cada señal produce su propio ranking; el analista revisa el top-k de cada uno.

**Uso declarado: calidad de datos y casos inusuales, nunca señal de responsabilidad** (plan,
tarea 4; CLAUDE.md §2.3 — ninguna salida de este módulo se asigna a una persona o empresa, solo
al registro).
"""

from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import IsolationForest

COLUMNAS_CATEGORICAS = ["delito_nombre", "cod_dpto_hechos", "estado_norm", "etapa_norm"]
COLUMNAS_NUMERICAS = ["dias_hecho_denuncia", "dias_denuncia_creacion", "dias_creacion_asignacion"]


def construir_matriz_estructurada(conexion: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    columnas = ", ".join(["caso_notica", *COLUMNAS_CATEGORICAS, *COLUMNAS_NUMERICAS])
    return conexion.sql(f"SELECT {columnas} FROM plata.registros_limpios").pl()


def codificar_para_modelo(matriz: pl.DataFrame) -> tuple[list[str], np.ndarray]:
    """One-hot para categóricas (con una categoría "faltante" explícita, no imputada) y la
    mediana de la columna para numéricas ausentes (documentado: no se descartan filas con
    rezagos faltantes, son legítimamente casos sin esa actuación todavía, ADR 0008)."""
    datos = matriz.to_pandas()
    ids = datos["caso_notica"].tolist()

    categoricas = datos[COLUMNAS_CATEGORICAS].astype(str).fillna("(faltante)")
    dummies = pd.get_dummies(categoricas, prefix=COLUMNAS_CATEGORICAS)

    numericas = datos[COLUMNAS_NUMERICAS].apply(pd.to_numeric, errors="coerce")
    numericas = numericas.fillna(numericas.median(numeric_only=True))

    matriz_final = pd.concat([dummies, numericas], axis=1).to_numpy(dtype=float)
    return ids, matriz_final


def calcular_puntajes_isolation_forest(
    matriz: np.ndarray, semilla: int, n_estimadores: int = 200
) -> np.ndarray:
    """Mayor puntaje = más atípico (se invierte el signo de `score_samples`, donde sklearn usa
    la convención contraria: menor = más anómalo)."""
    modelo = IsolationForest(n_estimators=n_estimadores, random_state=semilla)
    modelo.fit(matriz)
    return -modelo.score_samples(matriz)


def construir_centroides_por_fenomeno(
    conexion: duckdb.DuckDBPyConnection, embeddings_por_uid: dict[str, list[float]]
) -> dict[str, np.ndarray]:
    asignacion = conexion.sql(
        "SELECT registro_uid, codigo_fenomeno FROM fenomenos.asignacion_fenomeno"
    ).pl()
    centroides: dict[str, np.ndarray] = {}
    for (codigo,), grupo in asignacion.group_by(["codigo_fenomeno"]):
        vectores = [
            embeddings_por_uid[uid]
            for uid in grupo["registro_uid"].to_list()
            if uid in embeddings_por_uid
        ]
        if vectores:
            centroides[codigo] = np.mean(np.array(vectores), axis=0)
    return centroides


def distancia_centroide_mas_cercano(
    vector: list[float], centroides_por_fenomeno: dict[str, np.ndarray]
) -> tuple[str | None, float]:
    """Distancia coseno (0 = idéntico, 1 = ortogonal) al centroide de fenómeno más cercano."""
    if not centroides_por_fenomeno:
        return None, float("nan")
    v = np.array(vector, dtype=float)
    norma_v = np.linalg.norm(v)
    mejor_fenomeno: str | None = None
    mejor_distancia = float("inf")
    for fenomeno, centroide in centroides_por_fenomeno.items():
        norma_c = np.linalg.norm(centroide)
        if norma_v == 0 or norma_c == 0:
            continue
        distancia = 1 - float(np.dot(v, centroide) / (norma_v * norma_c))
        if distancia < mejor_distancia:
            mejor_fenomeno, mejor_distancia = fenomeno, distancia
    return mejor_fenomeno, mejor_distancia


def calcular_rangos(valores: list[float]) -> list[int]:
    """Rango 1 = más atípico (valor más alto). Sin librerías de por medio, para que el orden sea
    explícito y fácil de auditar."""
    orden = sorted(range(len(valores)), key=lambda i: valores[i], reverse=True)
    rangos = [0] * len(valores)
    for posicion, indice in enumerate(orden, start=1):
        rangos[indice] = posicion
    return rangos


def construir_tabla_atipicos(
    conexion: duckdb.DuckDBPyConnection,
    embeddings_por_uid: dict[str, list[float]],
    run_id: str,
    semilla: int = 20260101,
) -> list[dict[str, Any]]:
    matriz = construir_matriz_estructurada(conexion)
    if matriz.height == 0:
        return []

    ids, matriz_numerica = codificar_para_modelo(matriz)
    puntajes_if = calcular_puntajes_isolation_forest(matriz_numerica, semilla)
    rangos_if = calcular_rangos(puntajes_if.tolist())

    # El registro_uid de plata.registros_limpios (origen CASOS) y el de texto.relato_procesado
    # (origen RELATOS) son hashes distintos por diseño (CLAUDE.md §2.4: el hash incluye la tabla
    # de origen) — caso_notica es la única llave que comparten ambas tablas (mismo patrón que
    # decla.fenomenos.orquestador y los módulos de I3).
    registro_uid_por_caso = dict(
        conexion.sql("SELECT caso_notica, registro_uid FROM texto.relato_procesado")
        .pl()
        .iter_rows()
    )

    centroides = construir_centroides_por_fenomeno(conexion, embeddings_por_uid)
    distancias: list[float] = []
    fenomenos_cercanos: list[str | None] = []
    for caso in ids:
        registro_uid_relato = registro_uid_por_caso.get(caso)
        uid_de_caso = (
            embeddings_por_uid.get(registro_uid_relato) if registro_uid_relato else None
        )
        if uid_de_caso is None:
            fenomenos_cercanos.append(None)
            distancias.append(float("nan"))
            continue
        fenomeno, distancia = distancia_centroide_mas_cercano(uid_de_caso, centroides)
        fenomenos_cercanos.append(fenomeno)
        distancias.append(distancia)
    rangos_distancia = calcular_rangos(
        [d if not np.isnan(d) else -1.0 for d in distancias]
    )

    return [
        {
            "caso_notica": ids[i],
            "puntaje_isolation_forest": round(float(puntajes_if[i]), 6),
            "rank_isolation_forest": rangos_if[i],
            "distancia_centroide": round(distancias[i], 6) if not np.isnan(distancias[i]) else None,
            "fenomeno_mas_cercano": fenomenos_cercanos[i],
            "rank_distancia_centroide": rangos_distancia[i],
            "run_id": run_id,
        }
        for i in range(len(ids))
    ]
