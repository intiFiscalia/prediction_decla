"""Orquestador del Bloque 2C (plan_trabajo.md §7.1; Fase 6).

Corre representación → reducción UMAP → agrupamiento (HDBSCAN como método principal, más 3
contrastes: k-means, NMF, aglomerativo) → ficha por grupo de HDBSCAN, NMF y aglomerativo (k-means
no se ficha: en datos reales encontró los mismos 2 grupos que HDBSCAN, sin aportar estructura
nueva) → escribe `fenomenos.grupos_descubiertos` + `config/taxonomia/v0.1-borrador.yaml`. El
nombre "borrador" es deliberado: la v1.0 exige el taller de revisión humana (plan_trabajo.md
§7.2) que esta sesión no puede simular ("no presentes grupos no revisados como fenómenos").

`grupo_id` siempre lleva el prefijo del método (`hdbscan_0`, `nmf_3`, `agglomerative_2`, ...)
porque los tres métodos reusan los mismos números de etiqueta — sin prefijo colisionarían.

HDBSCAN y los 3 contrastes se seleccionan por estabilidad entre su propio barrido de
hiperparámetros (`decla.fenomenos.estabilidad`), no solo por su métrica interna — excepto
k-means, que ya tiene su propio criterio establecido (silueta) para elegir k.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import yaml

from decla.comun.configuracion import cargar_yaml
from decla.comun.duckdb_io import escribir_tabla_polars
from decla.fenomenos.agrupamiento import (
    RUIDO,
    ResultadoAgrupamiento,
    agrupar_agglomerative,
    agrupar_hdbscan,
    agrupar_nmf,
    construir_tfidf,
    elegir_kmeans_por_silueta,
)
from decla.fenomenos.estabilidad import ResumenEstabilidad, evaluar_estabilidad_bootstrap
from decla.fenomenos.ficha_grupo import (
    FichaGrupo,
    calcular_c_tfidf,
    distribucion_metadata,
    indicador_dominancia_plantilla,
    indicador_dominancia_unidad,
    menciones_dominantes,
    seleccionar_medoides_y_bordes,
)
from decla.fenomenos.reduccion import reducir_dimension
from decla.fenomenos.representacion import (
    cargar_embeddings_segmento,
    construir_matriz,
    construir_vector_menciones,
)
from decla.texto.pipeline_spacy import analizar

RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
RUTA_CONFIG_FENOMENOS = RAIZ_PROYECTO / "config" / "fenomenos.yaml"
RUTA_CATEGORIAS_MENCIONES = RAIZ_PROYECTO / "config" / "categorias_menciones.yaml"
RUTA_TAXONOMIA_BORRADOR = RAIZ_PROYECTO / "config" / "taxonomia" / "v0.1-borrador.yaml"
RUTA_EMBEDDINGS_DEFECTO = RAIZ_PROYECTO / "data" / "embeddings"


def _categorias_menciones() -> list[str]:
    contenido = cargar_yaml(RUTA_CATEGORIAS_MENCIONES)
    return [categoria["nombre"] for categoria in contenido["categorias"]]


def _lemas_relevantes(texto: str) -> str:
    if not texto:
        return ""
    doc = analizar(texto)
    return " ".join(token.lemma_.lower() for token in doc if token.is_alpha and not token.is_stop)


@dataclass
class ResumenFenomenos:
    n_relatos: int
    n_grupos_hdbscan: int
    pct_ruido_hdbscan: float
    parametros_hdbscan: dict[str, Any]
    estabilidad_hdbscan: ResumenEstabilidad
    n_grupos_kmeans: int
    parametros_kmeans: dict[str, Any]
    estabilidad_kmeans: ResumenEstabilidad
    n_grupos_nmf: int
    parametros_nmf: dict[str, Any]
    estabilidad_nmf: ResumenEstabilidad
    n_grupos_agglomerative: int
    parametros_agglomerative: dict[str, Any]
    estabilidad_agglomerative: ResumenEstabilidad


def _seleccionar_hdbscan_por_estabilidad(
    matriz: Any,
    barrido_mcs: list[int],
    barrido_ms: list[int],
    config_estabilidad: dict[str, Any],
    semilla: int,
) -> tuple[ResultadoAgrupamiento, ResumenEstabilidad]:
    mejor: ResultadoAgrupamiento | None = None
    mejor_resumen: ResumenEstabilidad | None = None
    mejor_degenerado: ResultadoAgrupamiento | None = None
    for tamano_minimo in barrido_mcs:
        for muestras_minimas in barrido_ms:
            if muestras_minimas > tamano_minimo:
                continue
            candidato = agrupar_hdbscan(matriz, tamano_minimo, muestras_minimas)
            etiquetas_sin_ruido = set(candidato.etiquetas.tolist()) - {RUIDO}
            if len(etiquetas_sin_ruido) < 2:
                # Resultado degenerado (todo ruido, o un solo grupo real): una partición
                # constante obtiene ARI/NMI = 1.0 trivialmente entre corridas de bootstrap
                # (siempre es "lo mismo" porque no varía), lo que la haría ganar la selección
                # por estabilidad sin aportar ninguna estructura real. Se descarta antes de
                # competir, no se corrige después.
                if mejor_degenerado is None:
                    mejor_degenerado = candidato
                continue

            def _agrupar(
                m: Any, _s: int, mcs: int = tamano_minimo, ms: int = muestras_minimas
            ) -> ResultadoAgrupamiento:
                return agrupar_hdbscan(m, mcs, ms)

            resumen = evaluar_estabilidad_bootstrap(
                matriz,
                _agrupar,
                config_estabilidad["n_corridas_bootstrap"],
                config_estabilidad["fraccion_submuestra"],
                semilla,
            )
            if mejor_resumen is None or resumen.ari_promedio > mejor_resumen.ari_promedio:
                mejor, mejor_resumen = candidato, resumen

    if mejor is None or mejor_resumen is None:
        # Todo el barrido fue degenerado (ningún (mcs, ms) encontró >= 2 grupos reales): se
        # devuelve el resultado degenerado tal cual, con estabilidad en 0 para que quede visible
        # que no hubo selección real, en vez de fallar o fingir una estabilidad que no se midió.
        assert mejor_degenerado is not None
        return mejor_degenerado, ResumenEstabilidad(0.0, 0.0, 0, 1.0)
    return mejor, mejor_resumen


def _seleccionar_nmf_por_estabilidad(
    matriz_tfidf: Any,
    barrido_n_componentes: list[int],
    config_estabilidad: dict[str, Any],
    semilla: int,
) -> tuple[ResultadoAgrupamiento, ResumenEstabilidad]:
    mejor: ResultadoAgrupamiento | None = None
    mejor_resumen: ResumenEstabilidad | None = None
    for n_componentes in barrido_n_componentes:
        candidato = agrupar_nmf(matriz_tfidf, n_componentes, semilla)

        def _agrupar(m: Any, s: int, n: int = n_componentes) -> ResultadoAgrupamiento:
            return agrupar_nmf(m, n, s)

        resumen = evaluar_estabilidad_bootstrap(
            matriz_tfidf,
            _agrupar,
            config_estabilidad["n_corridas_bootstrap"],
            config_estabilidad["fraccion_submuestra"],
            semilla,
        )
        if mejor_resumen is None or resumen.ari_promedio > mejor_resumen.ari_promedio:
            mejor, mejor_resumen = candidato, resumen
    assert mejor is not None and mejor_resumen is not None
    return mejor, mejor_resumen


def _seleccionar_agglomerative_por_estabilidad(
    matriz: Any,
    barrido_n_clusters: list[int],
    linkage: str,
    metrica: str,
    config_estabilidad: dict[str, Any],
    semilla: int,
) -> tuple[ResultadoAgrupamiento, ResumenEstabilidad]:
    mejor: ResultadoAgrupamiento | None = None
    mejor_resumen: ResumenEstabilidad | None = None
    for n_clusters in barrido_n_clusters:
        candidato = agrupar_agglomerative(matriz, n_clusters, linkage, metrica)

        def _agrupar(m: Any, _s: int, n: int = n_clusters) -> ResultadoAgrupamiento:
            return agrupar_agglomerative(m, n, linkage, metrica)

        resumen = evaluar_estabilidad_bootstrap(
            matriz,
            _agrupar,
            config_estabilidad["n_corridas_bootstrap"],
            config_estabilidad["fraccion_submuestra"],
            semilla,
        )
        if mejor_resumen is None or resumen.ari_promedio > mejor_resumen.ari_promedio:
            mejor, mejor_resumen = candidato, resumen
    assert mejor is not None and mejor_resumen is not None
    return mejor, mejor_resumen


def _codigo_grupo(metodo: str, etiqueta: Any) -> str:
    return f"{metodo}_{int(etiqueta)}"


def _grupos_por_etiqueta(
    registros_uid: list[str],
    etiquetas: Any,
    metodo: str,
    excluir_ruido: bool = False,
) -> dict[str, list[str]]:
    """Agrupa `registros_uid` por el código `{metodo}_{etiqueta}` (nunca por el entero crudo:
    HDBSCAN, NMF y aglomerativo reusan los mismos números de etiqueta y colisionarían). Solo
    HDBSCAN produce ruido (`RUIDO = -1`, `agrupamiento.agrupar_hdbscan`); NMF (argmax de pesos) y
    aglomerativo (sklearn `AgglomerativeClustering`) asignan todos los puntos a un grupo.
    """
    grupos: dict[str, list[str]] = {}
    for uid, etiqueta in zip(registros_uid, etiquetas, strict=True):
        if excluir_ruido and int(etiqueta) == RUIDO:
            continue
        grupos.setdefault(_codigo_grupo(metodo, etiqueta), []).append(uid)
    return grupos


def _construir_ficha(
    codigo: str,
    metodo: str,
    registros_del_grupo: list[str],
    datos_por_registro: dict[str, dict[str, Any]],
    vectores_por_registro: dict[str, list[float]],
    menciones_por_registro: dict[str, list[dict[str, Any]]],
) -> FichaGrupo:
    lemas_grupo = " ".join(datos_por_registro[uid]["lemas"] for uid in registros_del_grupo)
    terminos = calcular_c_tfidf({codigo: lemas_grupo}, top_n=15)[codigo]

    menciones_grupo = [
        mencion for uid in registros_del_grupo for mencion in menciones_por_registro.get(uid, [])
    ]

    vectores_grupo = {uid: vectores_por_registro[uid] for uid in registros_del_grupo}
    medoides, bordes = seleccionar_medoides_y_bordes(vectores_grupo)

    return FichaGrupo(
        grupo_id=codigo,
        metodo=metodo,
        n_miembros=len(registros_del_grupo),
        terminos_c_tfidf=terminos,
        menciones_dominantes=menciones_dominantes(menciones_grupo),
        distribucion_delito=distribucion_metadata(
            [datos_por_registro[uid] for uid in registros_del_grupo], "delito_nombre"
        ),
        distribucion_titulo_cp=distribucion_metadata(
            [datos_por_registro[uid] for uid in registros_del_grupo], "titulo"
        ),
        distribucion_unidad=distribucion_metadata(
            [datos_por_registro[uid] for uid in registros_del_grupo], "desp_id"
        ),
        distribucion_departamento=distribucion_metadata(
            [datos_por_registro[uid] for uid in registros_del_grupo], "cod_dpto_hechos"
        ),
        distribucion_anio=distribucion_metadata(
            [datos_por_registro[uid] for uid in registros_del_grupo], "anio_iso_creacion"
        ),
        medoides=medoides,
        bordes=bordes,
        dominancia_plantilla=indicador_dominancia_plantilla(
            [datos_por_registro[uid]["metodo_segmentacion"] for uid in registros_del_grupo]
        ),
        dominancia_unidad=indicador_dominancia_unidad(
            [str(datos_por_registro[uid]["desp_id"]) for uid in registros_del_grupo]
        ),
    )


def procesar_fenomenos(
    conexion: duckdb.DuckDBPyConnection,
    lote_id: str,
    run_id: str,
    ruta_embeddings_datos: Path = RUTA_EMBEDDINGS_DEFECTO,
    ruta_taxonomia_borrador: Path = RUTA_TAXONOMIA_BORRADOR,
) -> ResumenFenomenos:
    config = cargar_yaml(RUTA_CONFIG_FENOMENOS)
    semilla = config["semilla"]
    config_estabilidad = config["estabilidad"]

    embeddings_segmento = cargar_embeddings_segmento(
        ruta_embeddings_datos / lote_id / "segmento.parquet"
    )
    categorias = _categorias_menciones()
    vector_menciones = construir_vector_menciones(conexion, categorias)
    matriz_principal = construir_matriz(embeddings_segmento, vector_menciones, len(categorias))

    reducida = reducir_dimension(
        matriz_principal.matriz,
        config["umap"]["n_componentes_agrupar"],
        config["umap"]["n_vecinos"],
        config["umap"]["metrica"],
        semilla,
    )
    vectores_reducidos = dict(zip(matriz_principal.registros_uid, reducida.tolist(), strict=True))

    hdbscan_resultado, estabilidad_hdbscan = _seleccionar_hdbscan_por_estabilidad(
        reducida,
        config["hdbscan"]["min_cluster_size_barrido"],
        config["hdbscan"]["min_samples_barrido"],
        config_estabilidad,
        semilla,
    )

    kmeans_resultado = elegir_kmeans_por_silueta(
        reducida, config["kmeans"]["k_minimo"], config["kmeans"]["k_maximo"], semilla
    )
    estabilidad_kmeans = evaluar_estabilidad_bootstrap(
        reducida,
        lambda m, s: elegir_kmeans_por_silueta(
            m, config["kmeans"]["k_minimo"], config["kmeans"]["k_maximo"], s
        ),
        config_estabilidad["n_corridas_bootstrap"],
        config_estabilidad["fraccion_submuestra"],
        semilla,
    )

    datos_filas = (
        conexion.sql(
            "SELECT rp.registro_uid, rp.descripcion_hecho_enmascarada, rp.metodo_segmentacion, "
            "       r.delito_nombre, r.cod_dpto_hechos, r.anio_iso_creacion, r.desp_id, d.titulo "
            "FROM texto.relato_procesado rp "
            "JOIN plata.registros_limpios r ON rp.caso_notica = r.caso_notica "
            "LEFT JOIN plata.dim_delito d "
            "  ON r.delito_nombre = d.delito_nombre AND r.articulo_cp = d.articulo_cp"
        )
        .pl()
        .to_dicts()
    )

    datos_por_registro: dict[str, dict[str, Any]] = {}
    for fila in datos_filas:
        uid = fila["registro_uid"]
        if uid not in matriz_principal.registros_uid:
            continue
        datos_por_registro[uid] = {
            **fila,
            "lemas": _lemas_relevantes(fila.get("descripcion_hecho_enmascarada") or ""),
        }

    menciones_filas = (
        conexion.sql("SELECT registro_uid, categoria, valor_normalizado FROM texto.menciones")
        .pl()
        .to_dicts()
    )
    menciones_por_registro: dict[str, list[dict[str, Any]]] = {}
    for mencion in menciones_filas:
        menciones_por_registro.setdefault(mencion["registro_uid"], []).append(mencion)

    textos_tfidf = [
        datos_por_registro.get(uid, {}).get("lemas", "") for uid in matriz_principal.registros_uid
    ]
    matriz_tfidf = construir_tfidf(textos_tfidf, config["nmf"]["max_features_tfidf"])
    nmf_resultado, estabilidad_nmf = _seleccionar_nmf_por_estabilidad(
        matriz_tfidf, config["nmf"]["n_componentes_barrido"], config_estabilidad, semilla
    )

    agglomerative_resultado, estabilidad_agglomerative = _seleccionar_agglomerative_por_estabilidad(
        reducida,
        config["agglomerative"]["n_clusters_barrido"],
        config["agglomerative"]["linkage"],
        config["agglomerative"]["metrica"],
        config_estabilidad,
        semilla,
    )

    # HDBSCAN es el método principal (único con selección por estabilidad propia más barrido de
    # hiperparámetros); NMF y aglomerativo son los contrastes que en datos reales encontraron más
    # estructura (5 grupos cada uno) y por eso también se llevan ficha completa al taller. K-means
    # no se incluye aquí: con 2 grupos (igual que HDBSCAN) no aporta nada nuevo que revisar.
    resultados_con_ficha = [
        ("hdbscan", hdbscan_resultado, True),
        ("nmf", nmf_resultado, False),
        ("agglomerative", agglomerative_resultado, False),
    ]

    fichas: list[FichaGrupo] = []
    filas_asignacion: list[dict[str, Any]] = []
    for metodo, resultado, excluir_ruido in resultados_con_ficha:
        grupos_metodo = _grupos_por_etiqueta(
            matriz_principal.registros_uid, resultado.etiquetas, metodo, excluir_ruido
        )
        fichas.extend(
            _construir_ficha(
                codigo,
                metodo,
                registros,
                datos_por_registro,
                vectores_reducidos,
                menciones_por_registro,
            )
            for codigo, registros in grupos_metodo.items()
        )
        filas_asignacion.extend(
            {
                "registro_uid": uid,
                "grupo_id": _codigo_grupo(metodo, etiqueta),
                "metodo": metodo,
                "run_id": run_id,
            }
            for uid, etiqueta in zip(
                matriz_principal.registros_uid, resultado.etiquetas, strict=True
            )
            if not (excluir_ruido and int(etiqueta) == RUIDO)
        )

    filas_grupos = [
        {
            "grupo_id": ficha.grupo_id,
            "metodo": ficha.metodo,
            "run_id": run_id,
            "n_miembros": ficha.n_miembros,
            "terminos_c_tfidf": ", ".join(t for t, _ in ficha.terminos_c_tfidf[:10]),
            "medoides": ", ".join(ficha.medoides),
            "bordes": ", ".join(ficha.bordes),
            "dominancia_plantilla": ficha.dominancia_plantilla,
            "dominancia_unidad": ficha.dominancia_unidad,
        }
        for ficha in fichas
    ]
    escribir_tabla_polars(conexion, "fenomenos", "grupos_descubiertos", filas_grupos)
    escribir_tabla_polars(conexion, "fenomenos", "grupo_asignacion_borrador", filas_asignacion)

    _escribir_taxonomia_borrador(fichas, ruta_taxonomia_borrador)

    n_ruido = sum(1 for e in hdbscan_resultado.etiquetas if e == -1)
    n_grupos_hdbscan = sum(1 for ficha in fichas if ficha.metodo == "hdbscan")
    return ResumenFenomenos(
        n_relatos=len(matriz_principal.registros_uid),
        n_grupos_hdbscan=n_grupos_hdbscan,
        pct_ruido_hdbscan=round(n_ruido / len(hdbscan_resultado.etiquetas), 4)
        if len(hdbscan_resultado.etiquetas)
        else 0.0,
        parametros_hdbscan=hdbscan_resultado.parametros,
        estabilidad_hdbscan=estabilidad_hdbscan,
        n_grupos_kmeans=len(set(kmeans_resultado.etiquetas.tolist())),
        parametros_kmeans=kmeans_resultado.parametros,
        estabilidad_kmeans=estabilidad_kmeans,
        n_grupos_nmf=len(set(nmf_resultado.etiquetas.tolist())),
        parametros_nmf=nmf_resultado.parametros,
        estabilidad_nmf=estabilidad_nmf,
        n_grupos_agglomerative=len(set(agglomerative_resultado.etiquetas.tolist())),
        parametros_agglomerative=agglomerative_resultado.parametros,
        estabilidad_agglomerative=estabilidad_agglomerative,
    )


def _escribir_taxonomia_borrador(
    fichas: list[FichaGrupo], ruta_salida: Path = RUTA_TAXONOMIA_BORRADOR
) -> None:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    contenido = {
        "version": "0.1-borrador",
        "nota": (
            "Borrador automático, NO es la taxonomía v1.0 (plan_trabajo.md §7.2 exige el taller "
            "de revisión humana antes de congelar una versión). No presentar como fenómenos "
            "validados."
        ),
        "grupos": [
            {
                "codigo": ficha.grupo_id,
                "metodo": ficha.metodo,
                "n_miembros": ficha.n_miembros,
                "terminos_dominantes": [t for t, _ in ficha.terminos_c_tfidf[:10]],
                "menciones_dominantes": [
                    {"categoria": c, "valor": v, "proporcion": p}
                    for c, v, p in ficha.menciones_dominantes[:5]
                ],
                "dominancia_plantilla": ficha.dominancia_plantilla,
                "dominancia_unidad": ficha.dominancia_unidad,
                "estado": "pendiente_revision",
            }
            for ficha in fichas
        ],
    }
    ruta_salida.write_text(
        yaml.safe_dump(contenido, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
