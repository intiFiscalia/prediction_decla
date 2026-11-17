# CLAUDE.md — Analítica local DECLA (Colombia)

## 1. Propósito y fuentes de verdad

Implementas, como ingeniero/a de datos, NLP y ML, una herramienta **local** para analizar registros SPOA y relatos en español del ámbito de la Dirección Especializada contra el Lavado de Activos. El resultado incluye indicadores, fenómenos semánticos, análisis temporal y territorial, sectores económicos, asociaciones, alertas y pronósticos evaluables.

- Alcance, fases I0–I4 y criterios de aceptación: `docs/plan_trabajo.md` (**fuente de verdad del plan**).
- Reglas permanentes de trabajo, privacidad y arquitectura: este archivo.
- Hechos observados en los datos: §5 y diagnósticos agregados en `reports/agregados/diagnostico/`.
- Decisiones técnicas aprobadas: `docs/decisiones/`.
- Si hay contradicción: respeta el plan para el alcance; respeta los diagnósticos completos para describir los datos reales. No conviertas hallazgos de una muestra en reglas generales. Documenta discrepancias o decisiones nuevas en `docs/decisiones/`.

**Gestión de contexto:** no releas indiscriminadamente todo el repositorio. Consulta el plan, decisiones, fichas e informes solo cuando sean pertinentes para la tarea actual. No reproduzcas este archivo en tus respuestas.

## 2. Reglas no negociables

### 2.0 optimizacion de tokens

- Para ejecutar una funcionalidad nueva: empieza con /clear.
- Para una corrección independiente: empieza con /clear.
- Una tarea extensa que necesita continuidad: utiliza /compact.
- Utiliza un subagente para analizar cuando se necesite analizar todo el proyecto o hacer investigaciones.
- entrega respuestas breves y tecnicas de no mas de 300 palabras.
- No expliques codigo obvio y evita explicaciones innecesarias.
- Solo inspecciona archivos relevantes para el trabajo a realizar.
- Do not load large logs, datasets or unnecessary documentation.
- Report only relevant findings and changes.
- Modify the minimum number of files.
- Execute only relevant tests.
- Do not run redundant validations.
- Return concise summaries from subagents.
- no realices interacciones con el repositorio.

### 2.3 Rigor analítico y jurídico

- Distingue el origen de cada resultado mediante `origen`: `registrado`, `extraido_regla`, `extraido_modelo`, `inferido_modelo`; registra además `validado_humano` cuando aplique.
- La frecuencia de registros representa **actividad institucional registrada**, no incidencia del delito. Indícalo en subtítulos, notas y exportaciones.
- Las menciones de un relato no prueban que un hecho ocurrió ni que una persona participó. Los fenómenos, sectores y riesgos se asignan al **relato**, nunca a personas o empresas.
- Asociación no implica causalidad. Reporta tamaño de efecto, intervalo de confianza y valor p ajustado (Benjamini–Hochberg), cuando corresponda.
- Usa particiones temporales para evaluación de datos futuros. No uses particiones aleatorias para series temporales ni clasificadores destinados a registros futuros.

### 2.4 Linaje y reproducibilidad

- Identificador de linaje: `registro_uid = sha256(lote_id | tabla_origen | n_fila | contenido_fila_normalizado)`.
- Toda tabla derivada conserva `registro_uid` o llave agregada, `run_id`, `lote_id` y, cuando aplique, `version_taxonomia`, `version_modelo`, `origen` y `confianza`.
- Registra en `meta.ejecuciones`: run_id, inicio/fin, commit Git, hash de entradas, parámetros, versiones de librerías/modelos, estado y conteos de entrada/salida/cuarentena.
- Fija y registra semillas. Las transformaciones deben ser idempotentes: misma entrada y parámetros producen la misma salida.
- Ninguna capa modifica la anterior. Las correcciones se implementan como reglas versionadas en `config/`.

## 3. Arquitectura y convenciones

### 3.1 Stack aprobado

Python 3.11+ y `uv` (`uv.lock`); Polars (pandas solo si una librería lo exige); DuckDB + Parquet; Pandera; `numbers-parser`, `python-calamine` y CSV para ingesta; ftfy, RapidFuzz y Unidecode; spaCy (`es_core_news_lg`, `es_dep_news_trf` opcional); sentence-transformers; `mlx`/`mlx-lm` (LLM generativo local en Apple Silicon, ADR 0026); umap-learn, HDBSCAN (`sklearn.cluster.HDBSCAN`), BERTopic; scikit-learn, statsmodels, SciPy, ruptures; GeoPandas, Shapely, PySAL; NetworkX, mlxtend, prince; Plotly, Matplotlib; Streamlit; Quarto; pytest, ruff y mypy (modo básico). Makefile orquesta el MVP. Prefect/Dagster solo si se aprueba en I4.

No agregues ni sustituyas tecnologías por iniciativa propia: registra primero una decisión.

### 3.2 Estructura relevante

- `docs/`: plan, decisiones ADR, fichas e informes.
- `config/`: contratos de datos, reglas, diccionarios, umbrales y taxonomías versionadas.
- `data/raw/`, `data/private/`, `data/warehouse.duckdb`
- `data/referencia/`: fuentes públicas autorizadas localmente (por ejemplo, DIVIPOLA).
- `models/`: modelos locales y `MANIFEST.json` con hash, origen y licencia.
- `reports/agregados/`: única zona de resultados que Claude puede leer, sujeta a §2.1.
- `src/decla/`: ingesta, calidad, normalización, entidades, texto, conocimiento, fenómenos, analítica, emergencia, predicción, evaluación, app y utilidades comunes.
- `tests/`: pruebas unitarias, integración y fixtures sintéticos.
- `scripts/`, `Makefile`: utilidades y orquestación.

### 3.3 Capas de datos

`bronce` (crudo como texto) → `plata` (tipado, validado, normalizado y seudonimizado) → `entidades` → `texto` → `fenomenos` → `oro` (indicadores, asociaciones, alertas y pronósticos) → `revision` (anotación humana). `meta` almacena ejecuciones, lotes y calidad.

DuckDB admite un solo escritor. La aplicación abre la base en **solo lectura**.

### 3.4 Estilo y calidad

- Funciones pequeñas y puras por regla; cada regla de limpieza tiene prueba unitaria y fixture sintético.
- Nombres de columnas derivadas y docstrings en español; `snake_case`.
- Antes de cerrar una tarea, ejecuta las pruebas y validaciones pertinentes. Para cierre de incremento, ejecuta `make test`, `make lint` 

## 4. Forma de trabajo

1. **Al iniciar un incremento:** consulta la fase correspondiente de `docs/plan_trabajo.md` y los ADR/fichas pertinentes. Presenta un plan breve con tareas, archivos previstos y criterios de aceptación. Espera aprobación antes de implementar.
2. Trabaja por incrementos I0–I4 y respeta las compuertas de aprobación. No avances de incremento sin autorización.
3. Para tareas acotadas, inspecciona solo los archivos necesarios. No explores ni leas el repositorio completo sin una razón concreta.
4. Reutiliza código existente; modifica el mínimo de archivos. No hagas refactorizaciones ajenas al objetivo.
5. Si falta una decisión de negocio, jurídica o analítica (umbral, unidad de análisis, taxonomía, interpretación), pregunta con opciones concretas; no la inventes.
7. Registra decisiones técnicas en `docs/decisiones/AAAA-MM-DD-titulo.md` (contexto, opciones, decisión y consecuencias).
8. Al cerrar un incremento, crea/actualiza `docs/informes/I<n>_cierre.md` con entregables, pruebas, métricas disponibles, limitaciones, preguntas abiertas y estado de la compuerta.
9. Mantén las respuestas concisas: archivos cambiados, decisiones relevantes y resultado. No imprimas logs completos ni expliques código obvio.

## 5. Hallazgos confirmados del diagnóstico I0

**Base:** diagnóstico ejecutado el 2026-10-23 sobre 978 filas de CASOS y 978 de RELATOS, en CSV. Los hallazgos siguientes describen ese corte; valida cambios en nuevos lotes. Los diagnósticos detallados están en `reports/agregados/diagnostico/`.

### 5.1 Estructura e identificadores

- Grano confirmado: una fila = una noticia criminal. 978 `CASO_ID` únicos = 978 `CASO_NOTICIA` únicos; sin filas vacías ni duplicados exactos/parciales.
- CASOS↔RELATOS: unión 1:1, 100 % de cobertura en ambos sentidos, sin huérfanos.
- `CASO_NOTICIA` tiene 21 dígitos. Estructura validada: municipio DIVIPOLA (5) + entidad (2) + unidad (5) + año (4) + consecutivo (5). El año embebido coincide con `FECHA_CREACION` en 99,8 %.
- El esquema se controla mediante `config/esquema_fuente.yaml`. Ingesta `.numbers`, `.xlsx` y `.csv`; lee inicialmente como texto. Mantén identificadores como texto y normaliza sufijo `.0` cuando provenga de lectores que convierten a flotante.
- Columnas adicionales identificadas: `UNID_DESCRIPCION` y `eje tmeatico APLICA`. La columna `EJE_TEMATICO` no existe. No equipares nombres ni interpretes valores sin regla aprobada.
- `DELITO` pudo separarse en nombre/artículo/cuantía en 96,2 % (941/978); quedan 37 valores por revisar para ampliar reglas.

### 5.2 Fechas, territorio y calidad

- El dataset cubre enero–octubre de 2026 (10 meses). El umbral original de 36 meses para pronósticos (plan §8.4) lo fijó la planeación inicial sin conocer el ciclo real de entrega (datos anuales): nunca se va a acumular esa historia continua. Decisión (ADR 0016): se construyen pronósticos con la historia disponible, con modelo ingenuo obligatorio de referencia y advertencia explícita de intervalos amplios y sin estacionalidad estimable con menos de 12 meses — nunca oculta.
- No uses `FECHA_HECHO + 20 años` como regla de prescripción: solo 19,12 % cumple exactamente; el plazo varía según delito/artículo.
- Normalización territorial contra DIVIPOLA: 38,2 % coincidencia exacta; 49,6 % tras normalización; 12,2 % (119 filas) no resueltas en ese corte. No inventes asignaciones; conserva método, confianza y pendientes de revisión.
- Coordenadas: 95,4 % correctas, 4,5 % vacías, 0,1 % requirió reescalado; sin coordenadas invertidas o fuera de Colombia en el diagnóstico. Precisión efectiva aproximada de 3 decimales; no infieras precisión espacial mayor.
- `ESTADO` y `ETAPA` tienen variedad real. `RUPTURA` vacía en 88,3 %; `CASO_GRUPO_ESPECIALIZADO` en 28,3 %; `OTROS_DELITOS` en 92,4 %.
- `SECC_DESCRIPCION`: 64 % Delitos Fiscales y 35 % Lavado de Activos. **Alcance aprobado:** solo «Dirección Especializada contra el Lavado de Activos» (347 filas en el corte I0). Excluye Delitos Fiscales en plata/entidades de I1, nunca en bronce.
- `eje tmeatico APLICA`: 72,0 % `"0"`, 8,5 % `"por establecer"` y valores temáticos minoritarios. Su significado requiere interpretación aprobada; no asumas que `"0"` equivale a «no aplica».
- 90 pares de relatos casi idénticos entre noticias distintas (MinHash); pendiente determinar si son plantillas o hechos relacionados.

### 5.3 Texto y privacidad

- No se confirmó mojibake cirílico sistemático en el dataset completo. No apliques reparación de codificación de forma general; detecta y prueba cualquier caso antes de corregir.
- Los relatos presentan longitudes y estilos heterogéneos, errores de digitación y documentos citados. La fragmentación y la limpieza deben preservar el contenido sustantivo; no «corrijas» interpretaciones jurídicas o fácticas.
- Los relatos contienen datos personales abundantes. Seudonimiza en plata y enmascara en toda vista analítica. No expongas texto ni identificadores en logs, reportes o interfaces.

### 5.4 Hallazgos de muestra que NO son reglas del dataset completo

Una muestra pequeña anterior sugirió: cero coincidencias CASOS↔RELATOS, filas vacías, mojibake cirílico sistemático, coordenadas muy corruptas y prescripción = fecha del hecho + 20 años. El diagnóstico completo refutó esas generalizaciones. **No implementes esas hipótesis como reglas.** Consulta el diagnóstico agregado si necesitas el detalle histórico.

## 6. Preguntas y pendientes conocidos

Consulta `docs/plan_trabajo.md`, `docs/decisiones/` y los reportes antes de reabrir asuntos ya resueltos.

- Frecuencia de recepción de nuevos lotes.
- Autorización/disponibilidad local de cartografía, CIIU Rev. 4 A.C., proyecciones DANE y catálogo del Código Penal.
- Responsable de aprobar taxonomías, umbrales de alerta y difusión de resultados.
- Significado de `UNID_DESCRIPCION`.
- Interpretación de `"0"` y `"por establecer"` en `eje tmeatico APLICA`.
- Revisión de los 119 registros territoriales no resueltos.
- Revisión de los 37 valores de `DELITO` que no siguieron el patrón de separación.
- Naturaleza de los 90 pares de relatos casi idénticos.

Contexto de infraestructura conocido: Apple M5, 16 GB RAM, sin GPU CUDA (ADR 0001). DIVIPOLA está disponible en `data/referencia/divipola.csv`; no inspecciones datos restringidos para verificarlo.
