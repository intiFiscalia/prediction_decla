# Ficha de modelo — Isolation Forest para registros atípicos

- **Propósito:** señalar registros estructuralmente inusuales (variables categóricas/numéricas
  de `plata.registros_limpios`) y relatos semánticamente alejados de todos los centroides de
  fenómeno conocidos. Apoya calidad de datos y revisión de casos inusuales.
- **Uso explícitamente prohibido:** señal de responsabilidad, riesgo o sospecha sobre una
  persona, empresa o funcionario. Ningún campo de `oro.atipicos` se cruza con identificadores de
  personas; el puntaje se asigna al registro (`caso_notica`), nunca a alguien (CLAUDE.md §2.3).
- **Datos de entrada:** `delito_nombre`, `cod_dpto_hechos`, `estado_norm`, `etapa_norm` (one-hot,
  categoría "(faltante)" explícita, nunca imputada como una categoría real),
  `dias_hecho_denuncia`/`dias_denuncia_creacion`/`dias_creacion_asignacion` (mediana si faltan —
  documentado, no silencioso). Por separado: embeddings de relato (media) del lote más reciente
  de `make nlp`, para la distancia a centroides de fenómeno (`fenomenos.asignacion_fenomeno`).
- **Modelo y parámetros:** `sklearn.ensemble.IsolationForest`, `n_estimators=200`, semilla fija
  `20260101` (registrada en código, `decla.prediccion.atipicos`), sin ajuste de hiperparámetros
  más allá de ese valor por defecto — no hay conjunto de validación etiquetado para ajustarlo
  (sería inventar una búsqueda de hiperparámetros sin criterio real de éxito).
- **Salida:** dos rankings independientes en `oro.atipicos` (`rank_isolation_forest`,
  `rank_distancia_centroide`) — **nunca combinados en un solo score**: promediar dos escalas sin
  una base estadística para el peso relativo sería inventar una cifra (CLAUDE.md "no inventes
  cifras").
- **Métricas:** no supervisado, sin etiquetas de "atípico real" para medir precisión/
  exhaustividad. `precisión@k` (plan §9) **pendiente de revisión por un analista** sobre el
  top-k de cada ranking — no se reporta un número sin esa revisión.
- **Limitaciones conocidas:**
  - Con 346 relatos reales en alcance, el one-hot de categóricas con muchos niveles (delito,
    departamento) puede dejar columnas casi vacías; el modelo es sensible a eso.
  - La distancia a centroide depende de la taxonomía v1.0 vigente (4 fenómenos) y de qué
    partición (HDBSCAN o NMF) originó cada código — ver ADR 0015.
  - No se revalida con cada lote nuevo automáticamente; corre bajo `make prediccion` a demanda.
- **Responsable:** persona que opera el repositorio (sin un equipo de ciencia de datos separado
  todavía — ver preguntas abiertas de CLAUDE.md §6 sobre quién aprueba difusión de resultados).
- **Versión:** v1, 2026-11 (I4, Bloque 4A).
