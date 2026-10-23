# Plan de ingeniería – Herramienta local de analítica de fenómenos asociados al lavado de activos en Colombia

Versión aprobada: 21 de octubre de 2026

## 1. Resumen ejecutivo

Se propone una plataforma analítica local, en Python, organizada en capas (bronce → plata → oro) sobre DuckDB y archivos Parquet, que convierte el CSV de noticias criminales en indicadores, fenómenos semánticos validados, alertas de emergencia y pronósticos evaluables. Toda salida conserva el vínculo con el registro original (CASO\_ID, CASO\_NOTICIA, hash de fila y versión del lote).

**Qué resuelve.** Hoy el CSV mezcla variables procesales estructuradas con un relato libre. La herramienta separa tres niveles de verdad: (1) **hechos registrados** (lo que dice el sistema de información), (2) **atributos extraídos del texto** (lo que el relato menciona, con evidencia literal y confianza) y (3) **inferencias de modelo** (agrupaciones, sectores inferidos, alertas, pronósticos), siempre marcadas como tales.

**Componentes centrales.**

- **Diagnóstico y ETL reproducible:** validación del inventario existente, cardinalidad de identificadores, normalización territorial contra DIVIPOLA (DANE), control de fechas y unidad de análisis explícita (registro, noticia criminal, caso, grupo conexo).
- **Motor NLP en español:** limpieza conservadora, reglas y diccionarios colombianos (artículos del Código Penal, entidades como DIAN, POLFA, UIAF, municipios), NER con spaCy, y representaciones vectoriales con modelos *sentence-transformers* multilingües ejecutados localmente.
- **Capa de conocimiento:** tabla de *menciones* (actividad, mecanismo, bien, sector, lugar, fecha, artículo penal) con fragmento de evidencia, método de extracción, confianza y bandera explícito/inferido.
- **Descubrimiento de fenómenos:** embeddings + UMAP + HDBSCAN (vía BERTopic o ensamblado propio), consolidado por analistas en una **taxonomía versionada** de fenómenos; después, un clasificador supervisado para asignar nuevos relatos.
- **Análisis estadístico, territorial y temporal:** indicadores normalizados, tasas, mapas departamentales y municipales, asociaciones (chi-cuadrado, V de Cramér, razones de tasas, reglas de asociación, redes de co-ocurrencia) con corrección por comparaciones múltiples.
- **Detección de emergencia:** modelos de conteo con línea base (Poisson/binomial negativa), CUSUM/EARS, detección de deriva semántica y de nuevas combinaciones, con reglas de persistencia para controlar falsos positivos.
- **Predicción acotada:** pronóstico de conteos por fenómeno y territorio agregado, clasificación temática de relatos y detección de atípicos, todo con validación temporal (*rolling origin*).
- **Consulta y validación humana:** aplicación Streamlit local con autenticación, filtros por territorio y periodo, relatos representativos y cola de revisión que realimenta la taxonomía y las etiquetas.

**Principios.** Procesamiento 100 % local y sin APIs externas; datos personales seudonimizados en las capas analíticas; auditoría de cada ejecución; ninguna salida se presenta como prueba, responsabilidad ni causalidad. La frecuencia de relatos mide **actividad registrada por la institución**, no la incidencia real del delito.

**Decisiones que pueden tomarse ya:** arquitectura por capas, DuckDB + Parquet, Polars/pandas, Pandera, spaCy, sentence-transformers, scikit-learn, statsmodels, GeoPandas, Streamlit y un orquestador ligero. **Decisiones que dependen de los datos:** el modelo de embeddings definitivo, el uso de GPU, la granularidad temporal (semanal o mensual), la viabilidad de pronósticos municipales y la necesidad de un orquestador más robusto (Prefect o Dagster).

## 2. Arquitectura conceptual de extremo a extremo

La solución se organiza en siete capas desacopladas que se comunican solo mediante tablas versionadas; cualquier técnica nueva se agrega como módulo que lee de una capa y escribe en la siguiente, sin reconstruir las demás.

| Capa | Propósito | Contenido principal | Tecnología base |
| --- | --- | --- | --- |
| 0. Ingesta (bronce) | Conservar el CSV tal como llegó | Archivo original inmutable, hash SHA-256, metadatos del lote, tabla `raw_registros` con todas las columnas como texto | Sistema de archivos cifrado, DuckDB/Parquet |
| 1. Calidad y normalización (plata) | Datos tipados, validados y normalizados sin perder el original | `registros_limpios`, `dim_territorio` (DIVIPOLA), `dim_delito`, `dim_despacho`, `dim_tiempo`, `reporte_calidad` | Polars, Pandera, DuckDB |
| 2. Entidades analíticas | Definir la unidad de análisis | `noticia_criminal`, `caso`, `grupo_conexo`, puentes registro↔noticia↔caso | DuckDB SQL |
| 3. Texto y conocimiento | Representar el relato y extraer menciones | `relato_procesado`, `menciones` (evidencia + confianza), `embeddings` (vectores versionados), `diccionarios` | spaCy, sentence-transformers, reglas propias |
| 4. Fenómenos | Descubrir, consolidar y asignar fenómenos | `taxonomia_fenomenos` (versionada), `asignacion_fenomeno` (registro, fenómeno, probabilidad, método) | UMAP, HDBSCAN, BERTopic, scikit-learn |
| 5. Analítica (oro) | Indicadores, asociaciones, alertas, pronósticos | `ind_*`, `asociaciones`, `alertas`, `pronosticos`, `atipicos` | statsmodels, SciPy, GeoPandas, NetworkX |
| 6. Consulta y validación | Exploración, revisión humana y exportación | App local, cola de revisión, `anotaciones`, exportes | Streamlit, Plotly, DuckDB |

**Capas transversales.**

- **Metadatos y linaje:** tabla `ejecuciones` (id, fecha, versión de código por *commit* git, versión de datos por hash, parámetros, versiones de modelos, duración, resultado). Toda tabla derivada lleva `run_id` y `lote_id`.
- **Seguridad:** roles (administrador de datos, analista, revisor, consulta), seudonimización de NUMERO\_DOCUMENTO y FISCAL\_ASIGNADO\_DESPACHO en capas ≥ 2, bitácora de accesos, cifrado en reposo.
- **Registro de modelos:** carpeta de modelos versionados con su ficha (datos de entrenamiento, métricas, fecha, responsable) gestionada con MLflow local o un registro propio en DuckDB.

**Principios de diseño.**

1. **Inmutabilidad hacia abajo:** ninguna capa modifica la anterior; las correcciones se expresan como reglas versionadas.
2. **Llave de trazabilidad única:** `registro_uid` = hash(lote\_id, número de fila, contenido de la fila). Se usa porque CASO\_ID o CASO\_NOTICIA podrían no ser únicos.
3. **Separación de niveles de verdad:** columnas `origen` ∈ {registrado, extraído\_regla, extraído\_modelo, inferido} y `confianza` en toda salida derivada del texto.
4. **Reproducibilidad:** entornos fijados (uv o conda con *lockfile*), semillas aleatorias registradas, modelos preentrenados descargados una sola vez a un repositorio interno con su hash.
5. **Ejecución por lotes incremental:** cada CSV nuevo se procesa como lote; los artefactos dependientes se recalculan según un grafo de dependencias.

## 3. Diagrama del flujo de datos y componentes

```text
[Bronce · ingesta]  copia inmutable, hash, lote_id, registro_uid
        ↓
[Plata · validación y normalización]  Pandera, cuarentena, fechas, DIVIPOLA, catálogos, seudonimización
        ↓
[Entidades analíticas]  noticia criminal, caso, grupo conexo, puentes al registro
        ↓
[Texto y conocimiento (RELATO)]  reglas, spaCy, menciones con evidencia, embeddings
        ↓
[Fenómenos]  UMAP + HDBSCAN, taxonomía versionada, clasificador multietiqueta   ←──┐
        ↓                                                                         │ revisión humana
[Analítica (oro)]  indicadores, territorio, asociaciones, alertas, pronósticos      │ realimenta taxonomía
        ↓                                                                         │ y etiquetas
[Consulta y validación humana]  app Streamlit local, cola de revisión, exportes ──┘

Transversal a todas las capas: linaje (run_id, código, hash, versiones) · seguridad (roles, cifrado, bitácora) · modelos (registro, fichas)
```

Los datos bajan de bronce a consulta y cada capa solo lee de la anterior; la revisión humana en la app devuelve etiquetas y decisiones a la capa de fenómenos, que es la variable que articula indicadores, emergencia y predicción. Linaje, seguridad y registro de modelos aplican a todas las capas.

**Contrato entre capas.** Cada salida incluye `registro_uid` (o la llave agregada correspondiente), `run_id`, `lote_id` y, cuando aplica, `version_taxonomia`, `version_modelo`, `origen` y `confianza`. Un módulo nuevo (por ejemplo, otro extractor o un detector de anomalías distinto) solo necesita leer y escribir tablas que respeten este contrato.

## 4. Plan de trabajo detallado por fases

Cada fase se describe con los diez elementos solicitados. Las fases 1–3 son la base obligatoria; ningún modelo se entrena antes de cerrar la Fase 1.

### Fase 1. Diagnóstico y preparación de los datos

- **Objetivo:** conocer la composición real del CSV y fijar la unidad de análisis antes de cualquier modelo.
- **Actividades:**
  1. Contrastar el inventario existente con el archivo: columnas, tipos declarados vs. observados, codificación (UTF-8/Latin-1), separador, comillas y saltos de línea dentro de RELATO.
  2. Cardinalidad de identificadores: unicidad de CASO\_ID, CASO\_NOTICIA y del par; relación 1:1, 1:N o N:M; filas duplicadas exactas y duplicados parciales (misma noticia con distinto DELITO, DESPACHO o fecha). Esto define si una fila es «noticia × delito», «noticia × diligencia» u otra cosa.
  3. Consistencia temporal: rango de cada fecha, fechas futuras o anteriores a un umbral, orden lógico esperado (FECHA\_HECHO ≤ CASO\_FECHA\_DENUNCIA ≤ FECHA\_CREACION/CASO\_FECHA\_REG\_NC ≤ FECHA\_ASIGNACION; prescripción posterior al hecho), fechas por defecto (01/01/1900, 1/1 del año).
  4. Faltantes: porcentaje por columna, por año y por departamento (los faltantes no son aleatorios si se concentran en periodos o unidades).
  5. Territorio: cotejo de DEPARTAMENTO/MUNICIPIO\_HECHOS y \_UNIDAD contra DIVIPOLA; variantes ortográficas, tildes, «Bogotá D.C.», municipios homónimos en distintos departamentos; coordenadas fuera de Colombia, invertidas (lat/long), con precisión truncada o repetidas en el centroide municipal; coherencia punto–municipio declarado.
  6. Campos categóricos: catálogo de valores de ESTADO, ETAPA, EJE\_TEMATICO, TIPO\_DILIGENCIA, DELITO, COMPETENCIA\_DESPACHO; variantes que deben unificarse; composición por delito (qué proporción corresponde realmente a lavado de activos, art. 323, y qué a delitos fuente o conexos).
  7. Evaluación de RELATO: longitud (caracteres, palabras), vacíos, textos plantilla repetidos, relatos idénticos entre registros distintos, truncamiento en un máximo fijo, presencia de datos personales (nombres, cédulas, placas, teléfonos), idioma, mayúsculas sostenidas, errores de codificación (Ã±, Ã©).
  8. Estabilidad del registro en el tiempo: cambios de catálogo, aparición/desaparición de categorías, saltos en volumen que sugieran cambios de sistema o de práctica.
  9. Lectura dirigida de una muestra estratificada de 200–400 relatos (por año, departamento, delito, longitud) para construir el primer glosario y las hipótesis de fenómenos.
- **Problema que resuelve:** evita contar mal (duplicados, cardinalidad), localizar mal (territorio) y modelar artefactos de registro como fenómenos.
- **Técnicas:** perfilado de datos, pruebas de unicidad, análisis de cardinalidad, coincidencia difusa de nombres (distancia Jaro-Winkler/Levenshtein), validación espacial punto-en-polígono, detección de cambios estructurales en conteos.
- **Librerías:** Polars o pandas; DuckDB (SQL exploratorio); ydata-profiling (perfil inicial, opcional); RapidFuzz (normalización de nombres); GeoPandas + Shapely (validación de coordenadas); ftfy (reparación de codificación).
- **Entradas:** CSV original, inventario de datos existente, DIVIPOLA vigente y cartografía oficial (DANE/IGAC) descargadas previamente a la red local, Código Penal (títulos y artículos).
- **Artefactos:** informe de diagnóstico; matriz de calidad por columna; diccionario de datos ampliado (inventario + hallazgos); tabla de mapeo territorial; decisión documentada de unidad de análisis; muestra anotada inicial; registro de supuestos.
- **Criterio de terminación:** cardinalidad explicada y aprobada; 100 % de valores territoriales mapeados o marcados «no resoluble»; reglas de fechas inválidas definidas; perfil de RELATO publicado; supuestos firmados por el responsable de datos.
- **Dependencias:** ninguna previa; habilita todas las demás.
- **Riesgos y decisiones pendientes:** que una fila no represente un caso (necesidad de deduplicación jerárquica); que DIVIPOLA no esté disponible localmente; definir umbrales de fecha válida; definir quién decide sobre registros ambiguos.

### Fase 2. Arquitectura de la solución local

- **Objetivo:** definir almacenamiento, módulos, orquestación, versionado y seguridad acordes al hardware disponible.
- **Actividades:** inventario de hardware (CPU, RAM, GPU, disco); elección de motor de almacenamiento; estructura de repositorio (paquetes por capa); convención de tablas y esquemas; diseño de `ejecuciones` y linaje; elección de orquestador; política de entornos; repositorio interno de modelos preentrenados y paquetes (espejo PyPI o *wheelhouse*); modelo de roles y cifrado.
- **Problema que resuelve:** evita una herramienta monolítica e irreproducible y asegura que nada salga de la red.
- **Técnicas:** arquitectura *medallion* (bronce/plata/oro), diseño dimensional ligero, DAG de tareas, versionado de datos por hash.
- **Librerías y herramientas:** DuckDB + Parquet (alternativas: PostgreSQL/PostGIS si hay concurrencia multiusuario de escritura); orquestación con un DAG propio en Python + Makefile/Taskfile en el MVP, Prefect (servidor local) o Dagster si crecen las tareas programadas; DVC (opcional) para versionar datos; MLflow local para modelos; git; uv o conda.
- **Entradas:** resultado de Fase 1 (volumen, longitud de relatos), restricciones de seguridad institucionales.
- **Artefactos:** documento de arquitectura; esquema de tablas; plantilla de repositorio; matriz de roles; procedimiento de instalación fuera de línea.
- **Criterio de terminación:** entorno instalable sin internet en la máquina destino; prueba de humo que carga el CSV en bronce y registra la ejecución.
- **Dependencias:** Fase 1 (volumen y tamaño de texto).
- **Riesgos:** ausencia de GPU (afecta embeddings grandes); una sola máquina como punto único de falla (copias de respaldo cifradas); DuckDB admite un solo proceso escritor (la app debe abrir en solo lectura).

### Fase 3. Construcción del pipeline ETL

- **Objetivo:** pasar de CSV a tablas tipadas, validadas y normalizadas, preservando el original.
- **Actividades:**
  1. Ingesta: copia inmutable, hash, `lote_id`, carga como texto a `raw_registros` con `registro_uid` y número de fila.
  2. Validación de esquema con Pandera: presencia y orden de columnas, tipos convertibles, dominios conocidos; las filas que fallan van a cuarentena con el motivo, no se descartan.
  3. Limpieza controlada: espacios, mayúsculas, tildes en campos categóricos (manteniendo la versión original en una columna `_orig`), reparación de codificación, conversión de fechas con banderas `fecha_valida`, `fecha_imputada`.
  4. Normalización: territorio → códigos DIVIPOLA (`cod_dpto`, `cod_mpio`, `metodo_mapeo`, `confianza_mapeo`); DELITO → artículo y título del Código Penal (`dim_delito`); catálogos de ESTADO/ETAPA unificados.
  5. Derivados: tiempos (hecho→denuncia, denuncia→asignación, días a prescripción), año/mes/semana ISO, misma unidad que territorio de hechos (sí/no), calidad de coordenada (exacta, centroide, fuera de municipio, faltante).
  6. Entidades analíticas: tablas `noticia_criminal` y `caso`; grupos conexos a partir de NO\_CASOS\_CONEXOS y, si existe, de relaciones explícitas entre noticias (componentes conexos de grafo).
  7. Seudonimización: NUMERO\_DOCUMENTO y FISCAL\_ASIGNADO\_DESPACHO → token HMAC con clave guardada fuera del repositorio.
  8. Carga en plata y emisión de `reporte_calidad` del lote.
- **Problema que resuelve:** ofrece una base única, limpia y trazable para todos los análisis.
- **Técnicas:** ELT dentro de DuckDB, validación declarativa, transformaciones idempotentes, pruebas unitarias de reglas.
- **Librerías:** Polars (o pandas), DuckDB, Pandera, ftfy, RapidFuzz, Unidecode, pytest.
- **Entradas:** CSV, mapeos de Fase 1, DIVIPOLA, catálogo del Código Penal.
- **Artefactos:** tablas plata, cuarentena, reporte de calidad, pruebas automatizadas.
- **Criterio de terminación:** reejecutar con el mismo CSV produce tablas idénticas (mismo hash); conteos conciliados (filas entrada = plata + cuarentena); cobertura de pruebas en reglas de normalización.
- **Dependencias:** Fases 1 y 2.
- **Riesgos:** reglas de normalización que ocultan errores (por eso se conserva `_orig`); mapeos ambiguos de municipios homónimos sin departamento.

### Fase 4. Procesamiento de lenguaje natural en español

- **Objetivo:** dejar cada RELATO en una representación limpia, segmentada, con entidades básicas y vectores semánticos. El detalle técnico está en la sección 6.
- **Actividades:** normalización conservadora (sin eliminar tildes ni números en el texto que se analiza); segmentación en oraciones; tokenización y lematización con spaCy; detección de patrones por reglas (artículos penales, montos, fechas, placas, entidades institucionales); NER (personas, organizaciones, lugares); enmascaramiento de datos personales para las vistas analíticas; cálculo de embeddings por relato y por fragmento; detección de relatos duplicados o casi duplicados.
- **Problema que resuelve:** el texto libre no es comparable entre registros; esta fase lo vuelve consultable y comparable semánticamente.
- **Técnicas por tipo:** *reglas* (regex, EntityRuler, PhraseMatcher, gazetteers DIVIPOLA y de instituciones); *modelos preentrenados* (spaCy `es_core_news_lg` o `es_dep_news_trf`, sentence-transformers multilingües); *requiere entrenamiento o validación con etiquetas* (NER de conceptos propios del dominio, clasificador de mecanismos, sector inferido).
- **Librerías:** spaCy, sentence-transformers (PyTorch), datasketch (MinHash para casi-duplicados), FAISS o hnswlib (búsqueda vectorial, solo si el volumen lo exige), Presidio (opcional para detección de datos personales con reglas en español).
- **Entradas:** `registros_limpios.RELATO`, diccionarios iniciales de Fase 1.
- **Artefactos:** `relato_procesado`, `menciones` de primer nivel, `embeddings` con versión del modelo, índice de casi-duplicados.
- **Criterio de terminación:** 100 % de relatos procesados o con motivo de exclusión; precisión de reglas ≥ 0,9 en muestra revisada; comparación documentada de al menos dos modelos de embeddings en una tarea de similitud anotada.
- **Dependencias:** Fase 3.
- **Riesgos:** relatos plantilla que dominan la similitud; modelos de NER generales que fallan con siglas y nombres colombianos; costo de cómputo de modelos *transformer* sin GPU.

### Fase 5. Extracción y estructuración del conocimiento

- **Objetivo:** convertir cada relato en atributos analíticos con evidencia y confianza: actividades, mecanismos, bienes, entidades, lugares, referencias temporales, montos, delitos citados y sectores económicos.
- **Actividades:** definir el **esquema de menciones** y las categorías iniciales (sección 6); construir diccionarios y patrones por categoría (ej.: mecanismos de lavado como fraccionamiento, empresas fachada, testaferros, contrabando técnico, sobrefacturación, compra de bienes de alto valor, giros, criptoactivos); vincular lugares mencionados a DIVIPOLA; normalizar fechas relativas («el día de ayer») al marco de la fecha de denuncia solo cuando sea inequívoco; mapear actividades a CIIU Rev. 4 A.C. (DANE); anotar una muestra de 500–1.500 relatos para medir precisión/cobertura y entrenar extractores supervisados donde las reglas no alcancen.
- **Problema que resuelve:** permite contar y relacionar conceptos («cuántos relatos describen contrabando de combustibles en La Guajira») sin depender de coincidencias literales ni de la lectura manual completa.
- **Técnicas:** extracción por reglas + gazetteers; clasificación de fragmentos por similitud con definiciones semilla (*zero-shot* por embeddings); clasificación supervisada multietiqueta (regresión logística sobre embeddings o SetFit); detección de negación e hipótesis («no se encontró», «presuntamente») con reglas tipo NegEx adaptadas al español.
- **Librerías:** spaCy (Matcher, EntityRuler, SpanCategorizer), sentence-transformers, SetFit (opcional), scikit-learn, Label Studio o Doccano en instalación local para anotación.
- **Entradas:** salidas de Fase 4, taxonomía CIIU, glosario de dominio, lista de artículos del Código Penal.
- **Artefactos:** tabla `menciones`; diccionarios versionados; guía de anotación; conjunto anotado con acuerdo inter-anotador; ficha de cada extractor con métricas.
- **Criterio de terminación:** cada categoría con precisión y exhaustividad medidas en datos reservados; kappa de Cohen ≥ 0,6 entre anotadores en las categorías que se usarán para indicadores; separación explícita explícito/inferido en el 100 % de las menciones de sector.
- **Dependencias:** Fase 4; insumo para Fases 6–9.
- **Riesgos:** confundir mención con hecho; sesgo de los diccionarios hacia vocabulario conocido (mitigado con la Fase 6, que descubre lo no previsto); carga de anotación para analistas.

### Fase 6. Descubrimiento y caracterización de fenómenos

- **Objetivo:** identificar, sin etiquetas previas, grupos de relatos que describen fenómenos comparables y consolidarlos en una taxonomía interpretable. Detalle en la sección 7.
- **Actividades:** construir vectores por relato (embedding del texto enmascarado + opcionalmente indicadores de menciones); reducción con UMAP; agrupamiento con HDBSCAN; descripción de cada grupo con términos c-TF-IDF, menciones dominantes y relatos medoides; comparación con alternativas (k-means, LDA/NMF, agrupamiento jerárquico); talleres de revisión con analistas para nombrar, fusionar, dividir o descartar grupos; definición formal de cada fenómeno (criterio de inclusión y exclusión, ejemplos positivos y negativos); entrenamiento de un clasificador que asigne relatos a la taxonomía aprobada.
- **Problema que resuelve:** detecta fenómenos descritos con palabras distintas y produce categorías estables para contar y monitorear.
- **Técnicas:** modelado de temas neuronal (BERTopic), agrupamiento por densidad, temas jerárquicos, estabilidad por *bootstrap*, clasificación supervisada sobre embeddings.
- **Librerías:** BERTopic, umap-learn, hdbscan (o `sklearn.cluster.HDBSCAN`), scikit-learn, Gensim (LDA de referencia).
- **Entradas:** embeddings, menciones, metadatos estructurados (solo para describir, no para agrupar en la primera iteración).
- **Artefactos:** `taxonomia_fenomenos` v1 (código, nombre, definición, nivel jerárquico, estado), `asignacion_fenomeno`, informe de estabilidad, actas de validación.
- **Criterio de terminación:** ≥ 80 % de los relatos de la muestra de validación asignados a un fenómeno que el revisor considera correcto; estabilidad de grupos (ARI ≥ 0,7 entre corridas con distinta semilla o submuestra) en los fenómenos aprobados; proporción de «ruido» documentada.
- **Dependencias:** Fases 4 y 5.
- **Riesgos:** grupos que reflejan la plantilla de la unidad que redacta y no el fenómeno; sensibilidad a hiperparámetros; taxonomía que cambia con cada corrida (por eso se congela por versión).

### Fase 7. Análisis estadístico, temporal y geoespacial

- **Objetivo:** producir los indicadores y análisis descriptivos e inferenciales que responden los bloques A, B, D y G. Detalle en la sección 8.
- **Actividades:** catálogo de indicadores con ficha técnica; series por periodo con fecha de referencia explícita; distribución territorial con tasas (por 100.000 habitantes con proyecciones DANE, y por participación dentro del total del territorio); cocientes de localización; mapas coropléticos y de puntos con calidad de coordenada; análisis de flujo unidad↔hechos; asociaciones bivariadas y multivariadas; autocorrelación espacial; análisis de redes de co-ocurrencia.
- **Problema que resuelve:** convierte registros y fenómenos en medidas comparables entre territorios y periodos, controlando por volumen general.
- **Técnicas:** estadística descriptiva, tablas de contingencia, chi-cuadrado / exacta de Fisher, V de Cramér, PMI, razones de tasas con intervalos, regresión de Poisson/binomial negativa con efectos fijos, análisis de correspondencias múltiples, Moran I / LISA, estimación de densidad por kernel.
- **Librerías:** DuckDB (agregaciones), statsmodels, SciPy, prince (ACM), PySAL (esda, libpysal), GeoPandas, NetworkX, mlxtend (reglas de asociación).
- **Entradas:** plata, menciones, asignación de fenómenos, cartografía y proyecciones de población.
- **Artefactos:** tablas `ind_*`, `asociaciones`, mapas, fichas de indicadores, informe analítico base.
- **Criterio de terminación:** cada indicador con ficha, fórmula, unidad, denominador y limitaciones; reproducible desde la app; asociaciones reportadas con tamaño de efecto, intervalo y p ajustado.
- **Dependencias:** Fases 3, 5 y 6.
- **Riesgos:** confundir actividad institucional con incidencia; denominadores poblacionales inapropiados para delitos económicos; celdas con conteos muy bajos.

### Fase 8. Detección de tendencias y fenómenos emergentes

- **Objetivo:** señalar fenómenos, combinaciones o territorios cuya actividad registrada crece por encima de lo esperado, con control de falsos positivos.
- **Actividades:** definir la línea base por fenómeno × territorio agregado × periodo; modelar el conteo esperado ajustado por el volumen total de registros y la estacionalidad; aplicar detectores (CUSUM, EARS, Farrington flexible, prueba de razón de tasas); detectar términos y combinaciones nuevas; medir deriva semántica de cada fenómeno; aplicar reglas de persistencia y tamaño mínimo; enviar alertas a revisión.
- **Problema que resuelve:** permite la identificación temprana de cambios y separa tendencias reales de ruido o cambios de registro.
- **Técnicas:** modelos de conteo con *offset*, control estadístico de procesos, *scan statistics* espacio-temporales, BERTopic dinámico (*topics over time*), divergencia de Jensen-Shannon entre distribuciones de vocabulario, novedad por distancia a centroides históricos, corrección de Benjamini-Hochberg.
- **Librerías:** statsmodels, SciPy, ruptures (puntos de cambio), BERTopic, scikit-learn; `surveillance` de R solo si se acepta R localmente (alternativa: implementación propia de Farrington en Python).
- **Entradas:** series de Fase 7, embeddings y menciones con fecha.
- **Artefactos:** tabla `alertas` (tipo, fenómeno, territorio, periodo, magnitud, p, persistencia, estado de revisión), panel de emergencia.
- **Criterio de terminación:** tasa de falsas alarmas estimada en retroprueba histórica; reglas de emergencia aprobadas por analistas; ≥ 1 ciclo completo de alerta → revisión → decisión registrada.
- **Dependencias:** Fases 6 y 7.
- **Riesgos:** cambios de catálogo o de sistema que imitan emergencias; pocos periodos históricos; fecha de referencia mal elegida (fecha del hecho vs. fecha de registro con rezago).

### Fase 9. Modelos predictivos

- **Objetivo:** construir solo las predicciones que los datos sostienen, con variable objetivo, horizonte y evaluación definidos. Detalle y matriz de viabilidad en la sección 8.
- **Actividades:** prueba de viabilidad por problema (longitud de serie, conteos por celda, estabilidad del registro); construcción de variables con corte temporal estricto; modelos de referencia ingenuos (último valor, media estacional); modelos candidatos; validación con origen móvil; calibración; fichas de modelo.
- **Problema que resuelve:** anticipa volumen de actividad por fenómeno, clasifica relatos nuevos y señala registros atípicos, con incertidumbre cuantificada.
- **Técnicas:** regresión de Poisson/binomial negativa con rezagos y estacionalidad, ETS, SARIMAX, modelos jerárquicos con reconciliación, *gradient boosting* sobre series agregadas, regresión logística/SetFit para clasificación temática, Isolation Forest/LOF para atípicos.
- **Librerías:** statsmodels, StatsForecast y HierarchicalForecast (Nixtla, locales), scikit-learn, LightGBM, SetFit.
- **Entradas:** series de Fase 7, taxonomía y etiquetas validadas de Fases 6 y 10.
- **Artefactos:** modelos versionados, `pronosticos` con intervalos, fichas de modelo, informe de retroprueba.
- **Criterio de terminación:** cada modelo supera al modelo ingenuo en la métrica acordada en ≥ 2 orígenes de validación; intervalos con cobertura empírica cercana a la nominal.
- **Dependencias:** Fases 6, 7 y 10 (etiquetas).
- **Riesgos:** fuga de información temporal; poca historia; cambios de registro; uso indebido de predicciones como señalamiento de personas (prohibido por diseño: no se modelan individuos).

### Fase 10. Evaluación y validación analítica

- **Objetivo:** medir objetivamente la calidad de cada componente y documentar sus límites. Detalle en la sección 9.
- **Actividades:** protocolo de anotación y revisión; conjuntos de prueba reservados por componente; métricas por componente; revisión de alertas por analistas; registro de falsos positivos y negativos; pruebas de reproducibilidad; fichas de limitaciones.
- **Problema que resuelve:** evita confiar en salidas no verificadas.
- **Técnicas:** precisión/exhaustividad/F1, acuerdo inter-anotador, intrusión de palabras y de relatos, ARI/NMI, retroprueba de alertas, MASE/WAPE/cobertura de intervalos, análisis de errores estratificado por territorio y año.
- **Librerías:** scikit-learn (métricas), Label Studio local, Great Expectations o Pandera (pruebas de datos), pytest.
- **Entradas:** salidas de Fases 4–9, anotaciones.
- **Artefactos:** informe de evaluación por versión, fichas de modelo y de datos, bitácora de revisiones.
- **Criterio de terminación:** todos los componentes en uso tienen métricas publicadas y umbrales mínimos acordados.
- **Dependencias:** transversal; se ejecuta en paralelo a 4–9 y bloquea su paso a producción.
- **Riesgos:** disponibilidad de analistas para anotar; métricas buenas en promedio y malas en territorios pequeños.

### Fase 11. Consulta y presentación de resultados

- **Objetivo:** permitir a analistas consultar, filtrar, comparar, leer evidencia y validar resultados sin escribir código.
- **Actividades:** empezar con informes reproducibles (Quarto/Jupyter → HTML local) y consultas SQL guardadas; luego una app Streamlit multipágina: indicadores, fenómenos, territorio, emergencia, pronósticos, buscador semántico de relatos y cola de revisión; exportación a CSV/Excel/PDF con marca de versión y advertencias.
- **Problema que resuelve:** acerca la analítica a quienes toman decisiones y cierra el ciclo de validación humana.
- **Técnicas:** visualización exploratoria, búsqueda semántica por similitud, *drill-down* de indicador a relato.
- **Librerías:** Streamlit, Plotly, Folium o pydeck (mapas), Quarto, streamlit-authenticator o autenticación por proxy inverso institucional.
- **Entradas:** tablas oro, embeddings, menciones.
- **Artefactos:** aplicación local, manual de uso, plantillas de informe.
- **Criterio de terminación:** analistas completan tareas de prueba (p. ej., «fenómeno predominante en Casanare 2024 y tres relatos ejemplo») sin asistencia; accesos auditados.
- **Dependencias:** Fases 7–10.
- **Riesgos:** exposición de relatos con datos personales; lectura de pronósticos como hechos (se mitiga con avisos y etiquetas de nivel de verdad en cada vista).

### Fase 12. Operación y mejora continua

- **Objetivo:** incorporar nuevos CSV y mantener la calidad de datos, modelos y taxonomías en el tiempo.
- **Actividades:** procedimiento de ingesta de lotes (validación de esquema, detección de registros nuevos, modificados y repetidos por llave y hash); recálculo incremental según DAG; monitoreo de calidad (comparación del perfil del lote vs. histórico); monitoreo de deriva de datos y de predicciones; reentrenamiento programado o por umbral; ciclo trimestral de revisión de taxonomía; versionado semántico de taxonomía (v1.2 → v2.0 cuando cambia el significado de un fenómeno) con tabla de equivalencias para mantener comparabilidad de series; copias de respaldo y prueba de restauración.
- **Problema que resuelve:** evita que la herramienta se degrade silenciosamente o que las series se rompan al cambiar categorías.
- **Técnicas:** pruebas de deriva (PSI, KS, distancia entre distribuciones de embeddings), monitoreo de métricas en lotes revisados, *champion/challenger*.
- **Librerías:** Evidently (local), MLflow, Prefect/Dagster si hay ejecución programada, DuckDB.
- **Entradas:** nuevos CSV, retroalimentación de analistas.
- **Artefactos:** bitácora de lotes, tablero de salud del sistema, notas de versión.
- **Criterio de terminación:** es continuo; se considera estable cuando tres lotes consecutivos se procesan sin intervención manual fuera de la revisión prevista.
- **Dependencias:** todas.
- **Riesgos:** el CSV nuevo puede ser un extracto completo (no incremental) con registros que cambiaron de estado; hay que decidir si se guarda historia de cambios (dimensión lentamente cambiante).

## 5. Matriz comparativa de librerías y tecnologías

La pila recomendada para el MVP tiene 12 componentes; el resto queda como alternativa condicionada a volumen o necesidad. Los consumos son órdenes de magnitud para planificar, no mediciones: deben confirmarse con el volumen real en la Fase 2.

### 5.1 Librerías de Python

| Función | Recomendado | Alternativa | Propósito y ventajas | Limitaciones | Recursos aproximados |
| --- | --- | --- | --- | --- | --- |
| Manipulación de datos | Polars | pandas | Polars: rápido, multihilo, evaluación diferida, poco uso de memoria. pandas: ecosistema universal (GeoPandas, statsmodels) | Polars requiere convertir a pandas para algunas librerías; pandas es más lento con millones de filas | Polars ≈ 2–3× el tamaño de los datos en RAM; pandas ≈ 5–10× |
| Validación de datos | Pandera | Great Expectations | Esquemas declarativos en código, compatibles con Polars y pandas, pruebas unitarias simples | GE es más completo en reportes pero más pesado de configurar | Bajo |
| Texto: base | spaCy 3.x + `es_core_news_lg` | Stanza (Stanford) | Tokenización, lematización, dependencias, NER, Matcher y EntityRuler para reglas; rápido en CPU | NER entrenado en prensa/Wikipedia: falla con siglas y nombres colombianos; no garantiza semántica | `lg` ≈ 0,5–1 GB RAM; miles de relatos por minuto en CPU |
| Texto: transformer | `es_dep_news_trf` | RoBERTa-BNE (MarIA, PlanTL) vía Hugging Face | Mejor análisis sintáctico; base para afinar NER propio | Más lento; conviene GPU | GPU de 6–8 GB recomendada |
| Reparación y normalización | ftfy, Unidecode, RapidFuzz | jellyfish | Corrigen codificación, generan claves sin tildes y emparejan nombres territoriales | Requieren revisión de los emparejamientos ambiguos | Bajo |
| Embeddings | sentence-transformers | Hugging Face Transformers directo | Interfaz simple para vectores de oraciones, carga local de modelos | El modelo elegido determina la calidad; no todos manejan bien el español jurídico | Ver 5.2 |
| Búsqueda vectorial | NumPy (fuerza bruta) o DuckDB `vss` | FAISS, hnswlib | Hasta \~10^5–10^6 relatos basta producto matricial; FAISS si crece | Índices aproximados añaden parámetros | 768 dims × 1 M × 4 bytes ≈ 3 GB |
| Reducción de dimensión | umap-learn | PCA (scikit-learn), PaCMAP | UMAP preserva estructura local, ideal antes de HDBSCAN | Estocástico; sensible a `n_neighbors` | Minutos para 10^5 documentos en CPU |
| Agrupamiento | HDBSCAN (`sklearn.cluster.HDBSCAN` o `hdbscan`) | k-means, aglomerativo | No exige número de grupos, marca ruido, soporta densidades variables | Puede dejar mucho ruido; sensible a `min_cluster_size` | Moderado |
| Modelado de temas | BERTopic | NMF/LDA (scikit-learn, Gensim) | Integra embeddings + UMAP + HDBSCAN + c-TF-IDF, temas dinámicos y jerárquicos, modular | Puede producir temas de plantilla; depende de la calidad del embedding | Igual que sus componentes |
| Anotación | Label Studio (local) | Doccano, Argilla | Interfaz para etiquetar relatos, fragmentos y revisar grupos | Servicio adicional que mantener | Bajo |
| Clasificación de texto | scikit-learn (regresión logística sobre embeddings) | SetFit, afinamiento de RoBERTa-BNE | Pocos datos etiquetados, interpretable, rápido | El afinamiento completo exige más etiquetas y GPU | Bajo (SetFit: moderado) |
| Estadística | SciPy, statsmodels | pingouin | Pruebas, GLM Poisson/NB, ETS, SARIMAX, corrección múltiple | statsmodels es lento para miles de series | Bajo |
| Series masivas | StatsForecast, HierarchicalForecast | Darts, sktime | Miles de series rápidas, reconciliación jerárquica (departamento → nacional) | Curva de aprendizaje | Bajo-moderado |
| ML tabular | scikit-learn, LightGBM | XGBoost | Atípicos, *boosting* para conteos agregados | Riesgo de sobreajuste con poca historia | Bajo |
| Puntos de cambio | ruptures | Implementación CUSUM propia | Detecta cambios estructurales en series | Elegir penalización | Bajo |
| Geoespacial | GeoPandas, Shapely, PySAL (esda) | Folium/pydeck para mapas web | Uniones espaciales, validación de coordenadas, Moran/LISA | Requiere cartografía oficial local | Bajo-moderado |
| Redes | NetworkX | igraph | Co-ocurrencias, componentes de casos conexos, centralidad | NetworkX lento en grafos muy grandes | Bajo |
| Asociación | mlxtend (Apriori/FP-Growth), prince (ACM) | — | Reglas entre fenómeno, sector, territorio; mapas de correspondencias | Explosión combinatoria si no se filtra | Moderado |
| Visualización | Plotly, Matplotlib | Altair | Plotly interactivo en app; Matplotlib para informes estáticos | — | Bajo |
| Interfaz | Streamlit | Panel, Dash; Quarto para informes | Rápido de construir, Python puro | Autenticación básica; rendimiento con muchos usuarios | Bajo |
| Deriva y monitoreo | Evidently | Pruebas propias con SciPy | Informes de deriva de datos y modelos sin nube | Algunas funciones avanzadas son de la versión de pago | Bajo |

### 5.2 Modelos preentrenados de embeddings (candidatos a comparar, no a asumir)

| Modelo candidato | Tipo | A favor | En contra |
| --- | --- | --- | --- |
| `paraphrase-multilingual-mpnet-base-v2` | Multilingüe, 768 dims | Estable, ampliamente usado, rápido en CPU | Entrenado sobre paráfrasis generales; textos de hasta \~128 tokens por defecto (relatos largos se truncan) |
| `intfloat/multilingual-e5-base` / `-large` | Multilingüe, 768/1024 dims | Buen desempeño en recuperación; admite 512 tokens | `large` exige GPU para volúmenes grandes; requiere prefijos «query:»/«passage:» |
| `BAAI/bge-m3` | Multilingüe, 1024 dims | Contexto largo (hasta 8.192 tokens), útil si los relatos son extensos | Más pesado (\~2 GB); lento sin GPU |
| Modelos españoles (p. ej., derivados de RoBERTa-BNE afinados para similitud) | Español | Vocabulario español | Menor madurez; verificar licencia y calidad |

La elección se hace con una prueba local: 200–300 pares de relatos anotados por analistas como «mismo fenómeno / distinto», midiendo correlación de Spearman y precisión@k en búsqueda. Opcionalmente, adaptación de dominio con aprendizaje contrastivo sobre pares validados.

### 5.3 Almacenamiento y orquestación

| Componente | Opción | Cuándo elegirla | Limitación |
| --- | --- | --- | --- |
| Almacenamiento analítico | **DuckDB + Parquet** (recomendado) | Un servidor, análisis por lotes, consultas SQL rápidas, sin servicio que administrar | Un solo escritor concurrente |
| Almacenamiento multiusuario | PostgreSQL + PostGIS + pgvector | Varios usuarios escriben a la vez (anotaciones), roles finos en BD | Requiere administración |
| Orquestación MVP | DAG propio en Python + Makefile/Taskfile | Pocas tareas manuales por lote | Sin interfaz ni reintentos |
| Orquestación madura | Prefect (servidor local) o Dagster | Ejecuciones programadas, reintentos, linaje de activos (Dagster) | Servicio adicional; desactivar telemetría |
| Versionado de modelos | MLflow local | Varios modelos y experimentos | Servicio adicional |
| Versionado de datos | Hash + tabla de lotes; DVC opcional | Cuando hay muchos lotes y artefactos grandes | DVC añade complejidad |

**Criterio general:** no se incorpora una herramienta si DuckDB + Python simple resuelve la necesidad con el volumen real. Los servicios adicionales (PostgreSQL, Prefect, MLflow, Label Studio) entran solo cuando un problema concreto lo justifica.

## 6. Diseño del procesamiento de RELATO y de la extracción semántica

El relato se procesa en dos vías paralelas sobre el mismo texto: una **vía simbólica** (reglas, diccionarios, NER) que produce menciones auditables con evidencia literal, y una **vía semántica** (embeddings) que captura similitud de significado aunque cambien las palabras. Ninguna de las dos sustituye a la otra.

### 6.1 Etapas del procesamiento

1. **Texto fuente inmutable:** se conserva RELATO original; todo procesamiento trabaja sobre copias con desplazamientos de caracteres (*offsets*) que permiten volver al original.
2. **Normalización conservadora:** reparar codificación, unificar espacios y comillas, separar palabras pegadas por saltos de línea, convertir mayúsculas sostenidas a forma natural solo para el análisis lingüístico. No se eliminan tildes, números ni signos en el texto que va a NER y embeddings.
3. **Separación de estructura:** detectar encabezados de plantilla («siendo las…», «funcionario adscrito a…», «refiere tener conocimiento») y marcarlos como segmento **contexto de denuncia** frente al segmento **descripción del hecho**. Esto evita que los grupos se formen por la plantilla de cada unidad.
4. **Segmentación y análisis lingüístico:** oraciones, tokens, lemas, dependencias (spaCy). La lematización se usa para diccionarios y c-TF-IDF, no para embeddings.
5. **Reglas y gazetteers:** artículos penales («Art. 323 C.P.», «artículo 320»), montos («$50.000.000», «cincuenta millones de pesos», «USD»), fechas y horas, placas, NIT/cédulas (para enmascarar), instituciones (DIAN, POLFA, UIAF, CTI, SIJIN, DIJIN, Fiscalía, Supersociedades), municipios y departamentos con DIVIPOLA, bienes (inmuebles, vehículos, ganado, oro, combustibles, divisas, mercancías).
6. **NER general + ajuste:** spaCy para PER, ORG, LOC; una capa EntityRuler corrige siglas y nombres locales; si la precisión es insuficiente, se afina un NER con ejemplos anotados.
7. **Enmascaramiento:** nombres de personas, documentos, teléfonos y direcciones se reemplazan por marcadores tipados (\[PERSONA\], \[DOC\]) en la versión analítica. El original solo es visible con permiso específico.
8. **Negación, hipótesis y atribución:** marcar si la mención está negada («no se halló»), es hipotética o presunta («presuntamente», «al parecer»), o atribuida a una fuente («según el denunciante»). Se usan reglas de ventana y dependencias.
9. **Embeddings:** un vector por segmento de descripción del hecho (y uno por relato completo); relatos más largos que el límite del modelo se dividen en fragmentos y se promedian o se toma el máximo, decisión que se evalúa en la Fase 4.
10. **Casi-duplicados:** MinHash/LSH y similitud coseno alta para marcar relatos repetidos (el mismo hecho registrado varias veces) y no inflar fenómenos.

### 6.2 Reglas, modelos preentrenados y modelos entrenados

| Tarea | Solo reglas | Modelo preentrenado | Requiere etiquetas propias |
| --- | --- | --- | --- |
| Artículos penales, montos, fechas, placas, documentos | Sí | — | Solo para validar |
| Municipios y departamentos | Sí (gazetteer DIVIPOLA + desambiguación por contexto) | Apoyo NER LOC | Validación |
| Instituciones y siglas | Sí | — | Validación |
| Personas y organizaciones | Parcial | Sí (spaCy) | Afinamiento si precisión < umbral |
| Actividades y mecanismos explícitos | Diccionario semilla | Similitud con definiciones | Sí, clasificador multietiqueta |
| Sector económico explícito | Diccionario CIIU + sinónimos | — | Validación |
| Sector económico inferido | No | Similitud zero-shot | Sí, obligatorio antes de usarlo en indicadores |
| Similitud entre relatos | No | Sí (sentence-transformers) | Pares anotados para elegir modelo |
| Fenómenos | No | Agrupamiento no supervisado | Sí, para el clasificador posterior |
| Negación e hipótesis | Sí (reglas adaptadas) | — | Validación |

### 6.3 Esquema de la tabla de menciones

Cada extracción es una fila independiente, de modo que un relato puede tener muchas menciones y cada una conserva su evidencia.

| Campo | Contenido |
| --- | --- |
| `mencion_id`, `registro_uid`, `run_id` | Trazabilidad con el registro original y la ejecución |
| `categoria`, `subcategoria` | Ej.: mecanismo / fraccionamiento; bien / inmueble; sector / CIIU 4661 |
| `valor_normalizado` | Código o etiqueta estándar (DIVIPOLA, CIIU, artículo penal, monto en COP) |
| `texto_evidencia`, `inicio`, `fin` | Fragmento literal y su posición en el relato |
| `segmento` | Contexto de denuncia o descripción del hecho |
| `origen` | `explicito_regla`, `explicito_modelo`, `inferido_modelo`, `validado_humano` |
| `polaridad` | Afirmada, negada, hipotética, atribuida |
| `confianza` | Probabilidad calibrada o puntaje de regla (1,0 para coincidencia exacta validada) |
| `extractor`, `version_extractor` | Qué regla o modelo la produjo |
| `estado_revision` | Pendiente, confirmada, rechazada (con revisor y fecha) |

### 6.4 Sectores económicos: explícito, inferido e incierto

- **Taxonomía:** CIIU Rev. 4 adaptada para Colombia (DANE), descargada y almacenada localmente, con validación previa de su vigencia. Se trabaja a nivel de sección (letra) o división (2 dígitos) para analítica; clase (4 dígitos) solo cuando la evidencia es explícita.
- **Explícito:** el relato nombra la actividad o el tipo de negocio («casa de cambio», «estación de servicio», «exportadora de oro», «concesionario»). Diccionario de expresiones colombianas → código CIIU, con evidencia literal.
- **Inferido:** el relato describe bienes o transacciones sin nombrar el sector («compraba cabezas de ganado y las revendía», «giros desde el exterior a varias personas»). Se calcula similitud entre el fragmento y descripciones CIIU enriquecidas con ejemplos; se asignan las k mejores categorías con probabilidad calibrada y se marca `inferido_modelo`.
- **Incertidumbre:** si la probabilidad máxima es baja o la diferencia entre las dos primeras categorías es pequeña, se registra «sector indeterminado» en lugar de forzar una etiqueta. Los indicadores muestran por separado sector explícito, inferido de alta confianza y no determinado.
- **Protección contra atribuciones indebidas:** el sector se asigna al **relato**, nunca a una persona o empresa. Ninguna vista combina nombre de persona/empresa con sector inferido. Toda mención negada o hipotética se excluye de los conteos por defecto.

## 7. Metodología para descubrir, clasificar y monitorear fenómenos criminales

Un **fenómeno** se define como un patrón de hechos descrito de forma comparable en varios relatos (por ejemplo, «contrabando de mercancías almacenadas en bodegas urbanas» o «uso de terceros para fraccionar consignaciones»), aprobado por analistas con una definición escrita. El proceso pasa de descubrimiento no supervisado a clasificación supervisada en cuatro etapas.

### 7.1 Etapa A – Descubrimiento

1. **Representación:** embedding del segmento de descripción del hecho, enmascarado. En una variante se concatena un vector de menciones (mecanismos, bienes, sectores explícitos) para comparar.
2. **Reducción:** UMAP a 5–15 dimensiones (métrica coseno) para agrupar; a 2 dimensiones solo para visualizar.
3. **Agrupamiento:** HDBSCAN con barrido de `min_cluster_size` y `min_samples`. Se eligen parámetros por estabilidad y por revisión, no solo por métricas internas.
4. **Descripción automática de cada grupo:** términos c-TF-IDF sobre lemas, menciones más frecuentes con su proporción, distribución por DELITO, EJE\_TEMATICO, territorio y año, y 5–10 relatos medoides (los más cercanos al centro) más 3–5 relatos del borde.
5. **Alternativas de contraste:** NMF o LDA sobre TF-IDF (útil como línea base interpretable), k-means sobre embeddings con k fijado por silueta, y agrupamiento jerárquico aglomerativo para ver la estructura padre-hijo.
6. **Jerarquía:** BERTopic jerárquico o aglomerativo sobre centroides para proponer macrofenómenos (p. ej., «contrabando», «captación ilegal», «corrupción con recursos públicos») y subfenómenos.

### 7.2 Etapa B – Consolidación en una taxonomía

- **Talleres de revisión:** dos o más analistas revisan cada grupo con sus medoides, bordes y estadísticas. Acciones posibles: aprobar, renombrar, fusionar, dividir, marcar como artefacto (plantilla o duplicados) o descartar.
- **Ficha de fenómeno:** código estable, nombre, definición, criterios de inclusión y exclusión, ejemplos positivos y negativos, menciones típicas, delitos relacionados, nivel jerárquico y versión.
- **Validación de coherencia:** prueba de intrusión (el revisor recibe 5 relatos de un grupo y 1 de otro e identifica el intruso; tasa de acierto alta = grupo coherente); acuerdo entre revisores sobre la asignación de una muestra.
- **Congelamiento:** la taxonomía aprobada se versiona (v1.0). Las series y los indicadores siempre indican la versión de taxonomía usada.

### 7.3 Etapa C – Clasificación y asignación

- Con los relatos validados como ejemplos se entrena un **clasificador multietiqueta** (un relato puede describir más de un fenómeno): regresión logística sobre embeddings como base; SetFit si hay pocos ejemplos por clase; afinamiento de un modelo español solo si las anteriores no alcanzan el umbral.
- Salida por relato: fenómeno(s), probabilidad calibrada, método y versión. Por debajo de un umbral se asigna «no clasificado», que es un resultado legítimo y se monitorea.
- **Búsqueda semántica:** para cada fenómeno, el analista puede recuperar relatos similares a un ejemplo o a una descripción en lenguaje natural, lo que apoya tanto la revisión como la anotación activa (se priorizan para etiquetar los relatos de menor confianza).

### 7.4 Medición de frecuencia y del fenómeno más recurrente

- **Unidades:** se reporta el conteo en tres unidades, siempre explícitas: registros, noticias criminales únicas y grupos conexos. El fenómeno más recurrente se determina en noticias únicas (para no contar el mismo hecho varias veces).
- **Conteo con incertidumbre:** suma de probabilidades (conteo esperado) además del conteo por umbral; con muestra validada se estima la precisión por fenómeno y se corrige el conteo (estimación de prevalencia ajustada por error de clasificación), con intervalo de confianza.
- **Ranking robusto:** el «fenómeno más recurrente» se acepta solo si su posición se mantiene al variar umbral, modelo de embeddings y semilla, y si la diferencia con el segundo supera el intervalo de incertidumbre.
- **Siempre como actividad registrada:** el ranking describe lo que la institución registró, no la prevalencia real del delito.

### 7.5 Etapa D – Monitoreo

- **Fenómenos conocidos:** series por fenómeno con los detectores de la sección 8.5.
- **Fenómenos nuevos:** cada lote, los relatos «no clasificados» o lejanos a todos los centroides se reagrupan; si forman un grupo denso, persistente y con relatos de varias unidades, se propone como candidato a fenómeno.
- **Deriva interna:** cambio del centroide y del vocabulario c-TF-IDF de un fenómeno a lo largo del tiempo (BERTopic *topics over time*); un cambio fuerte se revisa porque puede indicar un nuevo modus operandi o un error de clasificación.
- **Actualización de taxonomía:** trimestral o por umbral de candidatos; los cambios generan tabla de equivalencias entre versiones para conservar la comparabilidad histórica.

## 8. Diseño de indicadores, análisis territorial, correlaciones y predicciones

Todo indicador declara su unidad (registro, noticia, caso, grupo conexo), su fecha de referencia (hecho, denuncia, registro o asignación), su numerador, su denominador y la versión de taxonomía. Sin esos cinco elementos no se publica.

### 8.1 Indicadores (bloque A)

| Familia | Indicadores | Uso |
| --- | --- | --- |
| Volumen | Registros, noticias únicas, casos, grupos conexos; razón registros/noticia | Saber cuánto hay realmente y cuánto se infla por duplicación |
| Composición | % por delito, eje temático, etapa, estado; % art. 323 vs. delitos fuente | Caracterizar el universo |
| Fenómenos | Noticias por fenómeno (conteo y conteo ajustado), participación, % no clasificado | Fenómenos predominantes |
| Territorio | Noticias por departamento/municipio de hechos; tasa por 100.000 hab.; cociente de localización (participación del fenómeno en el territorio ÷ participación nacional) | Especialización territorial |
| Tiempo | Serie mensual/trimestral; variación interanual; tendencia; rezago hecho→denuncia y denuncia→asignación | Evolución y oportunidad |
| Procesales | Distribución por etapa según antigüedad; % cerca de prescripción | Contexto procesal (no eficacia, sin datos de resultado) |
| Conexidad | % con casos conexos; tamaño de grupos; fenómenos con más conexidad | Complejidad y estructura |
| Economía | Noticias con sector explícito; con sector inferido de alta confianza; por sección CIIU | Sectores mencionados |
| Calidad | % fechas inválidas, % territorio no resoluble, % coordenadas válidas, longitud media del relato | Confianza en los demás indicadores |

### 8.2 Análisis territorial (bloque D)

- **Dos geografías distintas:** lugar de los hechos (dónde se describe el fenómeno) y lugar de la unidad (dónde se gestiona). Se analizan por separado y en una matriz origen–destino (hechos × unidad) representada como mapa de flujos y tabla. Una alta proporción de hechos fuera del departamento de la unidad puede reflejar competencias especializadas, no movilidad del delito.
- **Predominio:** fenómeno con mayor participación por territorio, con prueba de que supera al segundo y con tamaño mínimo de muestra; en municipios con pocos registros se usa suavizado bayesiano empírico (contracción hacia la media departamental) para evitar rankings dominados por azar.
- **Común vs. específico:** cociente de localización con intervalo; prueba de proporciones; agrupamiento de territorios según su perfil de fenómenos (distancia de Hellinger entre distribuciones) para identificar regiones con perfiles similares.
- **Autocorrelación espacial:** Moran global y LISA a nivel municipal para detectar zonas de concentración; solo con cobertura geográfica suficiente.
- **Coordenadas:** se clasifican por calidad; los análisis de puntos (densidad, distancias) usan solo coordenadas validadas dentro del municipio declarado, y se reporta qué fracción se excluyó. Si las coordenadas son mayoritariamente centroides, el análisis se hace a nivel municipal, no de punto.
- **Evolución territorial:** series por departamento y mapas por periodo con la misma escala; comparaciones con prueba de razón de tasas.

### 8.3 Correlaciones y relaciones entre variables (bloque G)

| Pregunta | Método | Condición de uso | Lo que NO permite afirmar |
| --- | --- | --- | --- |
| ¿Fenómeno y delito registrado están asociados? | Tabla de contingencia, chi-cuadrado o Fisher, V de Cramér, residuos estandarizados | Frecuencias esperadas ≥ 5 o prueba exacta | Que el fenómeno cause el delito |
| ¿Qué combinaciones fenómeno–sector–territorio se repiten? | Reglas de asociación (soporte, confianza, *lift*), PMI | Soporte mínimo; filtrar reglas redundantes | Que la combinación sea un modus operandi probado |
| ¿Cómo se estructuran conjuntamente muchas categorías? | Análisis de correspondencias múltiples | Categorías con frecuencia suficiente | Relaciones individuales entre casos |
| ¿Cambia la composición entre periodos o territorios? | Razón de tasas, regresión de Poisson/binomial negativa con efectos fijos de territorio y periodo y *offset* de volumen total | Series sin cambios de registro sin modelar | Que el cambio refleje la incidencia real |
| ¿Qué conceptos aparecen juntos en los relatos? | Red de co-ocurrencia de menciones ponderada por PMI; detección de comunidades (Louvain) | Excluir menciones negadas; umbral de co-ocurrencia | Relaciones entre personas (no se construyen redes de individuos) |
| ¿Cómo se agrupan los casos conexos? | Grafo de conexidad, componentes, distribución de fenómenos por componente | Requiere identificar la relación entre noticias conexas (verificar en Fase 1) | Vínculo entre personas |
| ¿Etapa o estado dependen del fenómeno? | Tablas cruzadas estratificadas por antigüedad; análisis de supervivencia (Kaplan-Meier) del tiempo a cambio de etapa si hay fechas de transición | Controlar antigüedad del caso | Eficacia de la investigación |

**Reglas comunes:** tamaño de efecto e intervalo antes que p; corrección de Benjamini-Hochberg cuando se prueban muchas combinaciones; separación explícita entre *asociación estadística*, *relación temporal* (precedencia), *coincidencia territorial* y *causalidad* (no se afirma causalidad con estos datos observacionales sin un diseño que la justifique).

### 8.4 Predicciones y pronósticos (bloque H)

| Problema | Variable objetivo | Datos requeridos | Horizonte | Modelos candidatos | Evaluación | Viabilidad y verificaciones previas |
| --- | --- | --- | --- | --- | --- | --- |
| Pronóstico de frecuencia por fenómeno | Noticias por fenómeno y mes (nacional o departamental) | ≥ 36 meses de historia estable; taxonomía congelada | 1–6 meses | Ingenuo estacional, ETS, Poisson/NB con estacionalidad, SARIMAX, reconciliación jerárquica | *Rolling origin*; MASE, WAPE, cobertura de intervalos | Alta a nivel nacional/departamental si hay historia; baja a nivel municipal (conteos escasos). Verificar rezago de registro en los últimos meses |
| Cambio esperado de actividad por territorio | Conteo total o por macrofenómeno por departamento y trimestre | Igual al anterior | 1–2 trimestres | Modelos jerárquicos, *gradient boosting* sobre rezagos | Igual al anterior | Media; depende de la estabilidad de las unidades que registran |
| Identificación temprana de incrementos | Exceso sobre lo esperado (alerta sí/no) | Serie y línea base | Periodo actual | CUSUM, EARS, Farrington, *scan statistics* | Retroprueba con eventos conocidos o simulados; tasa de falsas alarmas; tiempo a detección | Alta como sistema de vigilancia, siempre con revisión humana |
| Clasificación temática de relatos | Fenómeno(s) de la taxonomía validada | Relatos anotados (≥ 50–100 por clase) | Inmediato (cada nuevo relato) | Regresión logística sobre embeddings, SetFit, RoBERTa-BNE afinado | F1 macro y por clase en conjunto reservado posterior en el tiempo; calibración | Alta, condicionada a la anotación |
| Detección de registros atípicos | Puntaje de atipicidad (sin etiqueta) | Variables estructuradas + embeddings | Inmediato | Isolation Forest, LOF, distancia a centroides | Revisión de una muestra del top-k por analistas; precisión@k | Media; útil para calidad de datos y casos inusuales, no como señal de culpabilidad |

**Prevención de fuga de información:** las variables de cada punto de predicción se construyen solo con registros cuya fecha de registro (no de hecho) es anterior al corte; la taxonomía, los embeddings ajustados y los parámetros de normalización se recalculan en cada ventana de entrenamiento o se congelan antes del periodo de evaluación; los últimos meses con registro incompleto se excluyen o se modelan con corrección de rezago (*nowcasting*). La partición es siempre temporal, nunca aleatoria.

**Qué no se predice:** comportamiento, riesgo o responsabilidad de personas, empresas o funcionarios. ESTADO o ETAPA futura de un caso solo se evaluaría si existieran fechas de transición fiables y un uso aprobado; no se incluye en el alcance inicial.

### 8.5 Detección de fenómenos emergentes (bloque E)

Un aumento se trata como señal solo si supera lo esperado **después** de descontar el crecimiento general de registros, la estacionalidad y los cambios conocidos de registro.

1. **Línea base ajustada:** para cada serie fenómeno × territorio agregado, un modelo Poisson o binomial negativo con tendencia, estacionalidad y *offset* del total de noticias del territorio en el periodo. Así un aumento general de denuncias no dispara alertas por sí solo.
2. **Detectores complementarios:** CUSUM sobre residuos estandarizados (cambios sostenidos), EARS/Farrington (excesos puntuales), prueba de razón de tasas reciente vs. histórica, y puntos de cambio (ruptures) para diferenciar un cambio de nivel de un pico.
3. **Novedad combinatoria:** nuevas parejas o tríos (fenómeno, sector, territorio, mecanismo) que no aparecían en el periodo base, o cuyo *lift* aumentó significativamente; se exige soporte mínimo.
4. **Novedad semántica:** relatos alejados de todos los centroides históricos que forman un grupo denso nuevo; términos con crecimiento de frecuencia relativa anómalo (prueba log-likelihood entre ventana reciente y base); divergencia de Jensen-Shannon del vocabulario de cada fenómeno entre periodos.
5. **Filtro de artefactos:** antes de alertar se verifica si el aumento se concentra en una sola unidad o despacho, en un solo día de carga, en relatos casi duplicados o coincide con un cambio de catálogo. Si es así, se etiqueta como posible artefacto de registro.

**Condiciones para declarar un fenómeno emergente** (todas deben cumplirse):

- Exceso estadísticamente significativo tras corrección por comparaciones múltiples (Benjamini-Hochberg, FDR ≤ 10 %).
- Persistencia en al menos 2–3 periodos consecutivos (ajustable según la granularidad).
- Tamaño mínimo absoluto (p. ej., ≥ 5–10 noticias en el periodo) para no confundir rareza con emergencia.
- Presencia en más de una unidad o despacho registrador.
- Validación por un analista que lee los relatos de soporte.

Un fenómeno **poco frecuente** pero estable no es emergente; uno **nuevo** con pocos casos queda como «candidato en observación» hasta cumplir las condiciones.

## 9. Estrategia de evaluación y validación

Cada componente pasa a uso analítico solo con métricas medidas sobre datos reservados y revisadas por analistas; los umbrales propuestos son puntos de partida a ratificar con el equipo.

| Componente | Qué se mide | Métricas | Muestra de evaluación | Umbral inicial propuesto |
| --- | --- | --- | --- | --- |
| ETL y calidad | Conciliación y reproducibilidad | Filas entrada = salida + cuarentena; hash idéntico en reejecución; reglas Pandera | 100 % de cada lote | Sin diferencias |
| Normalización territorial | Correcta asignación DIVIPOLA | Precisión del mapeo; % no resoluble | 300 valores únicos revisados | Precisión ≥ 0,98 |
| Reglas de extracción | Menciones correctas y completas | Precisión, exhaustividad, F1 por categoría | 300–500 relatos anotados | Precisión ≥ 0,9 |
| NER y extractores supervisados | Entidades y conceptos de dominio | F1 por entidad (coincidencia exacta y parcial) | Conjunto reservado, posterior en el tiempo | F1 ≥ 0,8 en categorías usadas en indicadores |
| Negación e hipótesis | Polaridad correcta | Precisión/exhaustividad de «negada» | 200 menciones | ≥ 0,85 |
| Sector inferido | Categoría CIIU correcta | Precisión@1, precisión@3, calibración (ECE) | 300 relatos con sector anotado | Precisión@1 ≥ 0,7 para mostrarse como «alta confianza» |
| Embeddings | Similitud acorde a analistas | Spearman con juicios de similitud; precisión@k en búsqueda | 200–300 pares | Elegir el mejor de ≥ 2 modelos |
| Grupos de fenómenos | Coherencia y estabilidad | Prueba de intrusión, acuerdo entre revisores, ARI/NMI entre corridas, % ruido | 10–20 relatos por grupo | Intrusión ≥ 80 %; ARI ≥ 0,7 |
| Clasificador de fenómenos | Asignación correcta | F1 macro y por clase, matriz de confusión, calibración | Conjunto temporal reservado | F1 macro ≥ 0,75 y ninguna clase < 0,6 sin advertencia |
| Indicadores | Exactitud y utilidad | Recalculo independiente en SQL; revisión de fichas; encuesta de utilidad a analistas | Todos | Diferencia 0 en recalculo |
| Alertas | Precisión de las señales | Precisión de alertas revisadas, falsas alarmas por periodo, tiempo a detección | Retroprueba histórica + alertas reales | Definir con analistas (p. ej., ≤ 1 falsa alarma por fenómeno por año) |
| Pronósticos | Error y calibración | MASE, WAPE, cobertura de intervalos 80/95 %, comparación con ingenuo | *Rolling origin* con ≥ 6 orígenes | MASE < 1 frente a ingenuo estacional |
| Atípicos | Utilidad del top-k | Precisión@k según revisión | Top 50 por lote | Definir con analistas |

### 9.1 Protocolo de anotación y validación humana

- **Guía de anotación** con definiciones, ejemplos límite y reglas de desempate; piloto con 50 relatos, ajuste de guía y luego anotación doble de al menos 20 % de la muestra para medir acuerdo (kappa de Cohen o alfa de Krippendorff).
- **Muestreo estratificado** por año, departamento, delito y longitud del relato, más muestreo activo de relatos con baja confianza para mejorar modelos con menos esfuerzo.
- **Cola de revisión** en la app: alertas, grupos nuevos, sectores inferidos y atípicos se confirman o rechazan, con motivo. Cada decisión queda en `anotaciones` y alimenta reentrenamientos.
- **Revisión de errores:** análisis trimestral de falsos positivos y negativos estratificado por territorio, año y unidad, para detectar sesgos (p. ej., un modelo que funciona peor en relatos de cierta región).

### 9.2 Reproducibilidad y documentación

- Toda cifra publicada se puede regenerar a partir de `run_id`: versión de código, hash del lote, versiones de diccionarios, modelo y taxonomía.
- **Fichas de modelo** (propósito, datos, métricas, limitaciones, usos no permitidos) y **fichas de datos** (cobertura, sesgos conocidos, periodo) por versión.
- Registro explícito de limitaciones visible en la app junto a cada resultado.

## 10. Riesgos técnicos, analíticos, operativos y de seguridad

Los riesgos más altos no son técnicos sino analíticos: leer actividad institucional como incidencia criminal y leer menciones o inferencias como hechos.

| Tipo | Riesgo | Impacto | Probabilidad | Mitigación |
| --- | --- | --- | --- | --- |
| Analítico | Sesgo de denuncia y de registro: los datos reflejan dónde y qué registra la institución | Alto | Alta | Toda salida se rotula «actividad registrada»; offsets de volumen; comparación con fuentes externas solo como contexto |
| Analítico | Cambios de procedimientos o catálogos que crean tendencias falsas | Alto | Media | Detección de cambios estructurales en Fase 1; filtro de artefactos en alertas; bitácora de cambios conocidos |
| Analítico | Conteos inflados por duplicados o unidad de análisis equivocada | Alto | Media | Cardinalidad validada; tres unidades de conteo; casi-duplicados |
| Analítico | Grupos que reflejan plantillas de redacción y no fenómenos | Medio | Alta | Separar contexto de denuncia; revisión por analistas; prueba con relatos de distintas unidades |
| Analítico | Rezago de registro en los últimos meses (cola incompleta) | Medio | Alta | Excluir o *nowcasting*; marcar periodos provisionales |
| Analítico | Correlaciones presentadas como causas | Alto | Media | Lenguaje controlado en la app; ficha de interpretación; revisión antes de difusión |
| Analítico | Pocas observaciones por municipio | Medio | Alta | Agregación, suavizado bayesiano empírico, tamaños mínimos |
| Técnico | Modelos de lenguaje generales que no entienden jerga colombiana o jurídica | Medio | Alta | Diccionarios propios, evaluación local, adaptación de dominio |
| Técnico | Falta de GPU o RAM | Medio | Media | Modelos base en CPU, procesamiento por lotes, embeddings calculados una vez y reutilizados |
| Técnico | Dependencias que intentan conectarse a internet (descargas de modelos, telemetría) | Alto | Media | Instalación fuera de línea, variables de entorno de modo *offline*, telemetría desactivada, cortafuegos de salida |
| Técnico | Inestabilidad de UMAP/HDBSCAN entre corridas | Medio | Alta | Semillas fijas, pruebas de estabilidad, taxonomía congelada y clasificador supervisado |
| Operativo | Poca disponibilidad de analistas para anotar y revisar | Alto | Alta | Aprendizaje activo; sesiones cortas; priorizar categorías de mayor valor |
| Operativo | Dependencia de una sola persona o máquina | Medio | Media | Documentación, repositorio, respaldos cifrados y prueba de restauración |
| Operativo | Nuevos CSV con esquema o semántica distinta | Medio | Media | Validación de esquema y de perfil por lote; cuarentena |
| Seguridad | Exposición de datos personales y de investigaciones en curso | Muy alto | Media | Seudonimización, enmascaramiento, roles, cifrado en reposo, bitácora de accesos, exportes controlados, red segmentada |
| Seguridad / ético | Uso de salidas para señalar personas o empresas | Muy alto | Baja-media | No se modelan individuos; sector asignado al relato; avisos de uso; revisión humana obligatoria; política de usos permitidos |
| Legal | Tratamiento de datos personales sensibles y reserva de la investigación | Alto | Media | Validar con la oficina jurídica el marco aplicable (Ley 1581 de 2012 y reserva sumarial); minimización; acta de autorización del tratamiento |

## 11. Hoja de ruta priorizada

Se proponen cinco incrementos; cada uno entrega valor usable y una compuerta de aprobación antes del siguiente. Las duraciones son estimaciones para un equipo de 2–3 personas técnicas con acceso parcial a analistas y deben recalibrarse tras la Fase 1.

| Incremento | Fases | Entregables | Depende de | Compuerta para avanzar | Duración estimada |
| --- | --- | --- | --- | --- | --- |
| I0. Diagnóstico | 1, 2 | Informe de diagnóstico, decisión de unidad de análisis, mapeo territorial, documento de arquitectura, entorno fuera de línea | Acceso al CSV, inventario, DIVIPOLA local, respuestas a preguntas (\*) | Cardinalidad explicada y supuestos aprobados | 3–5 semanas |
| I1. Base confiable e indicadores descriptivos | 3, parte de 7, parte de 11 | Pipeline bronce→plata→oro, reporte de calidad, indicadores del bloque A, mapas departamentales, informe Quarto reproducible | I0 | Conteos conciliados y revisados por analistas | 4–6 semanas |
| I2. Texto y descubrimiento | 4, 5, 6, parte de 10 | Relatos procesados, menciones con evidencia, embeddings evaluados, buscador semántico, taxonomía v1.0 de fenómenos, guía y conjunto anotado | I1; horas de analistas | Taxonomía aprobada; métricas de extracción y coherencia en umbral | 8–12 semanas |
| I3. Análisis relacional y emergencia | 7 (completa), 8, 11 (app) | Asociaciones, cocientes de localización, red de co-ocurrencias, sectores CIIU, alertas con retroprueba, app Streamlit con cola de revisión | I2 | Tasa de falsas alarmas aceptada; primer ciclo de revisión de alertas completado | 6–8 semanas |
| I4. Predicción y operación | 9, 10 (completa), 12 | Clasificador de fenómenos, pronósticos con intervalos, detección de atípicos, fichas de modelo, procedimiento de lotes, monitoreo de deriva | I3; ≥ 36 meses de historia para pronósticos | Modelos superan al ingenuo; tres lotes procesados sin intervención | 6–10 semanas |

**Prioridades.** Primero la exactitud del conteo (I0–I1), porque todos los análisis posteriores heredan sus errores. Segundo la taxonomía validada (I2), porque es la variable que articula fenómenos, territorio, emergencia y predicción. La predicción va al final porque exige historia estable, categorías congeladas y etiquetas.

**Victorias tempranas** dentro de I1–I2: el informe de calidad (suele revelar problemas desconocidos del registro), los indicadores descriptivos por territorio y el buscador semántico de relatos, útil para analistas aunque la taxonomía aún no esté cerrada.

**Camino crítico:** disponibilidad de analistas para anotar y aprobar la taxonomía. Si no hay tiempo de analistas, el plan se limita a I0, I1 y un descubrimiento exploratorio sin indicadores por fenómeno.

## 12. Preguntas críticas pendientes antes de implementar

Las respuestas a estas preguntas fijan las decisiones abiertas del plan; las marcadas con (\*) bloquean el inicio de la Fase 3.

**Datos y unidad de análisis**

1. (\*) ¿Cuántas filas tiene el CSV, cuál es la fecha inicial y final, y cuántos valores únicos tienen CASO\_ID y CASO\_NOTICIA?
2. (\*) ¿Qué representa una fila según el sistema fuente: una noticia, una noticia × delito, una diligencia, una asignación a despacho?
3. ¿NO\_CASOS\_CONEXOS es solo un conteo o existe otra tabla que identifique cuáles son los casos conexos?
4. ¿El CSV es una extracción completa o incremental? ¿Llegarán actualizaciones de registros existentes (cambios de ESTADO/ETAPA)?
5. ¿Qué criterio se usó para seleccionar los registros (solo art. 323, eje temático, delitos fuente)? Esto define el sesgo de selección y el alcance de cualquier conclusión.
6. ¿Hubo cambios conocidos de sistema, catálogos o procedimientos de registro durante el periodo?

**Relatos**

7. ¿Cuál es la longitud típica y máxima de RELATO? ¿Está truncado por el sistema?
8. ¿Quién redacta los relatos (denunciante, policía judicial, funcionario de recepción)? ¿Existen plantillas por unidad?
9. ¿Los relatos contienen nombres y documentos de personas? ¿Hay autorización para procesarlos o deben enmascararse desde la ingesta?

**Infraestructura y seguridad**

10. (\*) ¿Qué hardware está disponible (núcleos de CPU, RAM, GPU y su memoria, disco) y qué sistema operativo?
11. ¿Se permite instalar servicios (PostgreSQL, Label Studio, Prefect) o solo aplicaciones de usuario?
12. ¿Cómo se transfieren paquetes de Python y modelos preentrenados a la red local (espejo interno, medio físico aprobado)?
13. ¿Cuántos usuarios usarán la herramienta, con qué roles, y existe un directorio institucional (LDAP/Active Directory) para autenticación?
14. ¿Qué exige la oficina jurídica sobre tratamiento de datos personales, reserva y conservación de bitácoras?

**Fuentes de referencia**

15. ¿Hay copia local autorizada de DIVIPOLA, cartografía DANE/IGAC, proyecciones de población y CIIU Rev. 4 A.C.? ¿Qué versión debe usarse?

**Uso analítico**

16. ¿Qué decisiones concretas apoyará la herramienta (priorización temática, informes periódicos, alertas regionales)? Esto define la granularidad temporal y territorial de los indicadores.
17. ¿Cuántas horas mensuales de analistas pueden dedicarse a anotar y revisar? Sin este tiempo, las fases 5, 6 y 9 no pueden validarse.
18. ¿Quién aprueba la taxonomía de fenómenos y los criterios de emergencia?

**Decisiones que dependen de las respuestas**

| Decisión | Depende de |
| --- | --- |
| Modelo de embeddings (base vs. large vs. contexto largo) | Hardware (10), longitud de relatos (7) |
| DuckDB solo vs. PostgreSQL | Usuarios concurrentes (13), servicios permitidos (11) |
| Granularidad temporal (semana, mes, trimestre) | Volumen (1), uso (16) |
| Pronóstico municipal o solo departamental | Volumen por municipio (1) |
| Orquestador ligero vs. Prefect/Dagster | Frecuencia de lotes (4), servicios permitidos (11) |
| Afinamiento de modelos supervisados | Horas de anotación (17), GPU (10) |
| Alcance de inferencias sobre lavado de activos vs. delitos fuente | Criterio de selección (5) |
