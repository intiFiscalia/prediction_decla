"""Asociaciones (plan_trabajo.md §8.3): una función por fila de la tabla de métodos, cada una
verificando su condición de uso en código antes de calcular. Salida estándar común
(`fila_estandar`) para `oro.asociaciones`: variables, método, estadístico, tamaño de efecto,
IC 95 %, p, p ajustado (Benjamini-Hochberg aplicado una sola vez sobre el conjunto completo de
pruebas, no por función), n, advertencias, interpretación por plantilla.

**Grafo de conexidad: explícitamente no construido.** `entidades.grupo_conexo` (I1) solo tiene el
conteo declarado `NO_CASOS_CONEXOS`, no identifica cuáles son los casos conexos — no hay con qué
construir un grafo real (documentado en `I1_cierre.md` y en el ADR de este bloque). No se simula
con datos que no están.

Ninguna función de este módulo construye ni usa una red de personas (CLAUDE.md, no negociable).
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any

import duckdb
import networkx as nx
import pandas as pd
import polars as pl
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from scipy.stats import chi2_contingency, fisher_exact
from statsmodels.stats.multitest import multipletests

PLANTILLA_INTERPRETACION = (
    "Asociación estadística entre {variables} ({metodo}); no implica relación temporal, "
    "coincidencia territorial garantizada ni causalidad. Mide actividad registrada, no "
    "incidencia real."
)


def fila_estandar(
    variables: str,
    metodo: str,
    estadistico: float | None,
    tamanio_efecto: float | None,
    ic_95: tuple[float, float] | None,
    p: float | None,
    n: int,
    advertencias: str = "",
) -> dict[str, Any]:
    return {
        "variables": variables,
        "metodo": metodo,
        "estadistico": estadistico,
        "tamanio_efecto": tamanio_efecto,
        "ic_95_inf": ic_95[0] if ic_95 else None,
        "ic_95_sup": ic_95[1] if ic_95 else None,
        "p": p,
        "p_ajustado_bh": None,  # se llena en consolidar_con_correccion_multiple
        "n": n,
        "advertencias": advertencias,
        "interpretacion": PLANTILLA_INTERPRETACION.format(variables=variables, metodo=metodo),
    }


def consolidar_con_correccion_multiple(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplica Benjamini-Hochberg (FDR) una sola vez sobre todos los `p` del lote de pruebas que
    se van a publicar juntas — corregir por separado en cada función subestimaría el número real
    de comparaciones (plan §8.3, "corrección de Benjamini-Hochberg cuando se prueban muchas
    combinaciones").
    """
    con_p = [(i, f["p"]) for i, f in enumerate(filas) if f.get("p") is not None]
    if not con_p:
        return filas
    indices, p_valores = zip(*con_p, strict=True)
    _, p_ajustados, _, _ = multipletests(list(p_valores), method="fdr_bh")
    for indice, p_ajustado in zip(indices, p_ajustados, strict=True):
        filas[indice]["p_ajustado_bh"] = round(float(p_ajustado), 4)
    return filas


# --- Fenómeno × delito: chi-cuadrado/Fisher, V de Cramér, residuos estandarizados ------------


def chi2_fenomeno_delito(conexion: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """plan §8.3, fila 1. Frecuencias esperadas < 5 en alguna celda de una tabla 2×2 → Fisher
    exacto en vez de chi-cuadrado (la condición de uso que la tarea pide verificar en código, no
    asumir).
    """
    base = conexion.sql(
        """
        SELECT a.codigo_fenomeno, r.delito_nombre
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE r.delito_nombre IS NOT NULL
        """
    ).pl()
    if base.height == 0:
        return {"calculado": False, "motivo": "sin datos"}

    tabla = pd.crosstab(base["codigo_fenomeno"].to_pandas(), base["delito_nombre"].to_pandas())
    n = int(tabla.to_numpy().sum())
    chi2, p, _, esperadas = chi2_contingency(tabla)

    metodo = "chi2"
    if tabla.shape == (2, 2) and (esperadas < 5).any():
        _, p = fisher_exact(tabla.to_numpy())
        metodo = "fisher_exacto"

    k = min(tabla.shape)
    v_cramer = math.sqrt((chi2 / n) / (k - 1)) if k > 1 and n > 0 else None

    residuos = (tabla.to_numpy() - esperadas) / (esperadas**0.5)
    residuos_df = pl.DataFrame(residuos, schema=[str(c) for c in tabla.columns]).with_columns(
        pl.Series("codigo_fenomeno", tabla.index.tolist())
    )

    return {
        "calculado": True,
        "metodo": metodo,
        "estadistico": round(float(chi2), 4),
        "p": round(float(p), 4),
        "tamanio_efecto_v_cramer": round(v_cramer, 4) if v_cramer is not None else None,
        "n": n,
        "residuos_estandarizados": residuos_df,
    }


# --- Reglas de asociación (fenómeno-sector-territorio) con filtro de redundancia -------------


def _canastas_fenomeno_sector_territorio(conexion: duckdb.DuckDBPyConnection) -> list[list[str]]:
    base = conexion.sql(
        """
        SELECT a.registro_uid, a.codigo_fenomeno,
               m.valor_normalizado AS sector, r.cod_dpto_hechos AS territorio
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        LEFT JOIN texto.menciones m
          ON m.registro_uid = a.registro_uid AND m.categoria = 'sector' AND m.polaridad = 'afirmada'
        """
    ).pl()

    canastas: dict[str, set[str]] = {}
    for fila in base.iter_rows(named=True):
        items = canastas.setdefault(fila["registro_uid"], set())
        items.add(f"fenomeno={fila['codigo_fenomeno']}")
        if fila["sector"] and fila["sector"] != "indeterminado":
            items.add(f"sector={fila['sector']}")
        if fila["territorio"]:
            items.add(f"territorio={fila['territorio']}")
    return [list(items) for items in canastas.values()]


def _regla_es_redundante(regla: pd.Series, todas: pd.DataFrame) -> bool:
    """Una regla es redundante si existe otra con antecedente subconjunto propio, mismo
    consecuente, y confianza/lift no peores — no aporta nada que la regla más simple no diga.
    """
    for _, otra in todas.iterrows():
        if (
            otra["consequents"] == regla["consequents"]
            and otra["antecedents"] < regla["antecedents"]
            and otra["confidence"] >= regla["confidence"]
            and otra["lift"] >= regla["lift"]
        ):
            return True
    return False


def reglas_asociacion_fenomeno_sector_territorio(
    conexion: duckdb.DuckDBPyConnection,
    soporte_minimo: float = 0.05,
    confianza_minima: float = 0.5,
) -> pl.DataFrame:
    """plan §8.3, fila 2 (mlxtend). `soporte_minimo`/`confianza_minima` son los umbrales que la
    tarea exige verificar, no valores escondidos: se exponen como parámetros.
    """
    canastas = _canastas_fenomeno_sector_territorio(conexion)
    if not canastas:
        return pl.DataFrame()

    codificador = TransactionEncoder()
    matriz = codificador.fit(canastas).transform(canastas)
    df_items = pd.DataFrame(matriz, columns=codificador.columns_)

    frecuentes = apriori(df_items, min_support=soporte_minimo, use_colnames=True)
    if frecuentes.empty:
        return pl.DataFrame()

    reglas = association_rules(
        frecuentes,
        num_itemsets=len(frecuentes),
        metric="confidence",
        min_threshold=confianza_minima,
    )
    if reglas.empty:
        return pl.DataFrame()

    reglas = reglas[~reglas.apply(lambda r: _regla_es_redundante(r, reglas), axis=1)]
    reglas["antecedents"] = reglas["antecedents"].apply(lambda s: ", ".join(sorted(s)))
    reglas["consequents"] = reglas["consequents"].apply(lambda s: ", ".join(sorted(s)))
    return pl.from_pandas(
        reglas[["antecedents", "consequents", "support", "confidence", "lift"]]
    ).sort("lift", descending=True)


# --- ACM (análisis de correspondencias múltiples) --------------------------------------------


def acm_categorias(
    conexion: duckdb.DuckDBPyConnection, min_frecuencia: int = 5, n_componentes: int = 2
) -> dict[str, Any]:
    """plan §8.3, fila 3 (prince.MCA) sobre fenómeno/sector/territorio/delito, solo categorías
    con frecuencia suficiente (se descartan las raras antes de ajustar, no después)."""
    base = conexion.sql(
        """
        SELECT a.codigo_fenomeno, r.delito_nombre, r.cod_dpto_hechos,
               coalesce(m.valor_normalizado, 'sin_sector') AS sector
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        LEFT JOIN texto.menciones m
          ON m.registro_uid = a.registro_uid AND m.categoria = 'sector' AND m.polaridad = 'afirmada'
        """
    ).df()
    if base.empty:
        return {"calculado": False, "motivo": "sin datos"}

    for columna in base.columns:
        frecuencias = base[columna].value_counts()
        raras = frecuencias[frecuencias < min_frecuencia].index
        base[columna] = base[columna].where(~base[columna].isin(raras), other="(otros)")

    import prince

    modelo = prince.MCA(n_components=n_componentes, engine="sklearn")
    modelo = modelo.fit(base)
    return {
        "calculado": True,
        "inercia_explicada_pct": [round(float(v) * 100, 2) for v in modelo.percentage_of_variance_],
        "coordenadas_columnas": pl.from_pandas(
            modelo.column_coordinates(base).reset_index().rename(columns={"index": "categoria"})
        ),
        "n": len(base),
    }


# --- Poisson/NB con offset de volumen, efectos fijos de territorio y periodo ----------------


def poisson_o_nb_offset(
    conexion: duckdb.DuckDBPyConnection, columna_territorio: str = "cod_dpto_hechos"
) -> dict[str, Any]:
    """plan §8.3, fila 4. Conteo de noticias por fenómeno × territorio × mes, con offset del
    volumen total de ese territorio-mes (un aumento general de registros no debe disparar un
    "efecto" artificial). Empieza en Poisson; si la razón varianza/media del residuo de Pearson
    indica sobredispersión relevante (>1.5, umbral documentado, no un valor mágico oculto),
    reajusta con binomial negativa.
    """
    base = conexion.sql(
        f"""
        SELECT a.codigo_fenomeno, r.{columna_territorio} AS territorio,
               r.anio_iso_creacion || '-' || lpad(r.mes_creacion::VARCHAR, 2, '0') AS periodo
        FROM fenomenos.asignacion_fenomeno a
        JOIN texto.relato_procesado rp ON a.registro_uid = rp.registro_uid
        JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica
        WHERE r.{columna_territorio} IS NOT NULL AND r.fecha_creacion_valida
        """
    ).pl()
    if base.height == 0:
        return {"calculado": False, "motivo": "sin datos"}

    volumen_territorio_periodo = (
        base.group_by(["territorio", "periodo"]).agg(pl.len().alias("volumen_total"))
    )
    conteo = (
        base.group_by(["codigo_fenomeno", "territorio", "periodo"])
        .agg(pl.len().alias("n"))
        .join(volumen_territorio_periodo, on=["territorio", "periodo"])
    )
    n_niveles_fijos = conteo["territorio"].n_unique() + conteo["periodo"].n_unique()
    pocas_celdas = (
        conteo["territorio"].n_unique() < 2
        or conteo["periodo"].n_unique() < 2
        or conteo.height <= n_niveles_fijos  # menos filas que parámetros de efectos fijos: no
        # hay grados de libertad para estimarlos.
    )
    if pocas_celdas:
        return {
            "calculado": False,
            "motivo": "insuficientes celdas territorio×periodo para efectos fijos de ambos",
        }

    datos = conteo.to_pandas()
    datos["log_offset"] = datos["volumen_total"].apply(lambda v: math.log(v) if v > 0 else 0.0)

    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    formula = "n ~ C(codigo_fenomeno) + C(territorio) + C(periodo)"
    try:
        modelo_poisson = smf.glm(
            formula, data=datos, family=sm.families.Poisson(), offset=datos["log_offset"]
        ).fit()
    except Exception as error:  # modelo no identificable (p. ej. matriz singular) con estos datos
        return {"calculado": False, "motivo": f"modelo no identificable: {error}"}

    residuos_pearson = modelo_poisson.resid_pearson
    sobredispersion = float((residuos_pearson**2).sum() / modelo_poisson.df_resid)

    if sobredispersion > 1.5:
        modelo_final = smf.negativebinomial(
            "n ~ C(codigo_fenomeno) + C(territorio) + C(periodo)",
            data=datos,
            offset=datos["log_offset"],
        ).fit(disp=False)
        metodo = "binomial_negativa"
    else:
        modelo_final = modelo_poisson
        metodo = "poisson"

    return {
        "calculado": True,
        "metodo": metodo,
        "sobredispersion_pearson": round(sobredispersion, 4),
        "n_observaciones": len(datos),
        "parametros": pl.DataFrame(
            {
                "termino": modelo_final.params.index.tolist(),
                "coeficiente": modelo_final.params.values.tolist(),
                "p": modelo_final.pvalues.values.tolist(),
            }
        ),
    }


# --- Red de co-ocurrencia de menciones (PMI + Louvain) ---------------------------------------


def red_coocurrencia_menciones(
    conexion: duckdb.DuckDBPyConnection, umbral_pmi: float = 0.0
) -> dict[str, Any]:
    """plan §8.3, fila 5. Excluye menciones negadas/hipotéticas (solo `polaridad='afirmada'`,
    CLAUDE.md §2.3). Nodo = `categoria:valor_normalizado`; arista si PMI > `umbral_pmi` (0 =
    "aparecen juntos más de lo esperado por azar", el mínimo defendible; subir el umbral exige
    co-ocurrencia más fuerte, no solo más frecuente)."""
    menciones = conexion.sql(
        """
        SELECT registro_uid, categoria || ':' || coalesce(valor_normalizado, subcategoria, '?')
               AS token
        FROM texto.menciones
        WHERE polaridad = 'afirmada'
        """
    ).pl()
    if menciones.height == 0:
        return {"calculado": False, "motivo": "sin menciones"}

    por_registro: dict[str, set[str]] = {}
    for fila in menciones.iter_rows(named=True):
        por_registro.setdefault(fila["registro_uid"], set()).add(fila["token"])

    n_total = len(por_registro)
    conteo_token: dict[str, int] = {}
    conteo_par: dict[tuple[str, str], int] = {}
    for tokens in por_registro.values():
        for t in tokens:
            conteo_token[t] = conteo_token.get(t, 0) + 1
        for a, b in combinations(sorted(tokens), 2):
            conteo_par[(a, b)] = conteo_par.get((a, b), 0) + 1

    grafo = nx.Graph()
    for (a, b), n_ab in conteo_par.items():
        p_a, p_b, p_ab = conteo_token[a] / n_total, conteo_token[b] / n_total, n_ab / n_total
        if p_a == 0 or p_b == 0 or p_ab == 0:
            continue
        pmi = math.log(p_ab / (p_a * p_b))
        if pmi > umbral_pmi:
            grafo.add_edge(a, b, weight=pmi, n_coocurrencias=n_ab)

    if grafo.number_of_nodes() == 0:
        return {"calculado": False, "motivo": "ninguna pareja supera el umbral de PMI"}

    comunidades = nx.algorithms.community.louvain_communities(grafo, weight="weight", seed=20260101)
    comunidad_por_nodo = {
        nodo: i for i, comunidad in enumerate(comunidades) for nodo in comunidad
    }
    return {
        "calculado": True,
        "n_nodos": grafo.number_of_nodes(),
        "n_aristas": grafo.number_of_edges(),
        "n_comunidades": len(comunidades),
        "grafo": grafo,
        "comunidad_por_nodo": comunidad_por_nodo,
    }
