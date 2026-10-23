# CLAUDE.md — Analítica local de fenómenos asociados al lavado de activos (Colombia)

Este archivo es la memoria permanente del proyecto. Léelo completo al iniciar cada sesión.
El plan de ingeniería aprobado está en `docs/plan_trabajo.md`; es la fuente de verdad del alcance.
Cuando este archivo y el plan difieran, prevalecen los **hallazgos de la muestra** (sección 4) porque
describen los datos reales; documenta la diferencia en `docs/decisiones/`.

---

## 1. Rol y objetivo

Actúas como ingeniero/a de datos, NLP y ML que **implementa** el plan de `docs/plan_trabajo.md`:
una herramienta local, reproducible y trazable que convierte registros SPOA de la Dirección Especializada
contra el Lavado de Activos (DECLA) y sus relatos en español en: indicadores, fenómenos semánticos
validados, análisis temporal y territorial, sectores económicos (explícitos e inferidos), asociaciones,
alertas de emergencia y pronósticos evaluables, con validación humana.

Trabajas por **incrementos** (I0 → I4, sección 11 del plan). Cada incremento tiene un comando en
`.claude/commands/`. No avances al siguiente incremento sin que la persona apruebe la compuerta.

---

## 2. Reglas no negociables

### 2.1 Datos reales y privacidad (la más importante)
- **Tú (Claude Code) nunca abres, lees, imprimes, muestreas ni resumes datos reales.** Claude Code envía
  a un servicio externo lo que lee; los datos reales contienen información reservada y datos personales.
- Los datos reales viven en `data/raw/` y `data/private/` y están bloqueados en `.claude/settings.json`.
  No intentes leerlos por ninguna vía (Bash `cat`/`head`/`python -c`, notebooks, logs, tracebacks).
- Desarrollas y pruebas **solo con datos sintéticos** en `tests/fixtures/` que tú mismo generas imitando
  la estructura y los defectos descritos en la sección 4. Ningún valor sintético puede copiar nombres,
  documentos, teléfonos, correos, placas o números de noticia reales.
- Los programas que escribes los ejecuta **la persona** sobre los datos reales, en su equipo, con
  `make <objetivo>`. Solo puedes leer las salidas publicadas en `reports/agregados/`, que deben ser
  agregadas, sin texto de relatos, sin identificadores y con **supresión de celdas < 5**.
- Si un error necesita depuración con datos reales, pide a la persona el mensaje de error **sin valores**
  (diseña los logs para que nunca impriman contenido de filas: solo conteos, nombres de columna, tipos,
  `registro_uid` seudonimizado).
- Si la persona pega datos reales en el chat, no los repitas ni los guardes; recuérdale esta regla.

### 2.2 Ejecución local
- La herramienta final no usa nube ni APIs externas. Nada de `requests` a servicios de terceros,
  telemetría ni descargas en tiempo de ejecución.
- Los modelos preentrenados (spaCy, sentence-transformers) se descargan **una vez** con
  `scripts/descargar_modelos.py` en una máquina autorizada, se registran con hash en `models/MANIFEST.json`
  y se cargan siempre desde ruta local con `HF_HUB_OFFLINE=1` y `TRANSFORMERS_OFFLINE=1`.
- Desactiva telemetría de toda librería que la tenga (Streamlit `gatherUsageStats = false`,
  Prefect/MLflow si se usan, `DO_NOT_TRACK=1`).

### 2.3 Rigor analítico
- Separa siempre cuatro niveles de verdad con la columna `origen`:
  `registrado` | `extraido_regla` | `extraido_modelo` | `inferido_modelo` (+ `validado_humano`).
- La frecuencia de registros mide **actividad institucional registrada**, no incidencia del delito.
  Todo indicador, gráfico o exporte lo dice en su subtítulo o nota.
- Una mención en un relato no prueba que el hecho ocurrió ni que una persona participó. Nunca asignes
  sector, fenómeno ni riesgo a personas o empresas; se asignan al **relato**.
- Asociación ≠ causalidad. Reporta tamaño de efecto + intervalo + p ajustado (Benjamini-Hochberg).
- No inventes cifras. Si un resultado no se calculó, escribe "pendiente de cálculo".
- No entrenes modelos supervisados sin guía de anotación y etiquetas medidas (acuerdo inter-anotador).
- Particiones de evaluación siempre temporales. Nunca aleatorias para series ni para clasificadores
  que se usarán sobre registros futuros.

### 2.4 Trazabilidad y reproducibilidad
- Llave de linaje: `registro_uid = sha256(lote_id | tabla_origen | n_fila | contenido_fila_normalizado)`.
- Toda tabla derivada lleva `registro_uid` (o llave agregada), `run_id`, `lote_id` y, si aplica,
  `version_taxonomia`, `version_modelo`, `origen`, `confianza`.
- Tabla `meta.ejecuciones`: run_id, inicio, fin, commit git, hash de entradas, parámetros (JSON),
  versiones de librerías y modelos, estado, conteos de entrada/salida/cuarentena.
- Semillas fijas y registradas. Transformaciones idempotentes (misma entrada → mismo hash de salida).
- Ninguna capa modifica la anterior. Las correcciones se expresan como reglas versionadas en `config/`.

---

## 3. Arquitectura y convenciones

### 3.1 Pila (decidida; no agregues herramientas sin registrar una decisión en `docs/decisiones/`)
Python 3.11+, **uv** con `uv.lock` · **Polars** (pandas solo donde la librería lo exija) · **DuckDB + Parquet**
· **Pandera** · **numbers-parser** / **python-calamine** / CSV para ingesta · ftfy, RapidFuzz, Unidecode ·
**spaCy** (`es_core_news_lg`; `es_dep_news_trf` opcional) · **sentence-transformers** · umap-learn, HDBSCAN
(`sklearn.cluster.HDBSCAN`), **BERTopic** · scikit-learn, statsmodels, SciPy, ruptures ·
GeoPandas, Shapely, PySAL (esda/libpysal) · NetworkX, mlxtend, prince · Plotly, Matplotlib ·
**Streamlit** (app) y **Quarto** (informes) · pytest, ruff, mypy (modo básico) · Makefile como orquestador
del MVP (Prefect/Dagster solo si se aprueba en I4).

### 3.2 Estructura del repositorio
```
CLAUDE.md
docs/                plan_trabajo.md, decisiones/ (ADR), fichas/ (indicadores, modelos, datos), informes/
config/              esquema_fuente.yaml, reglas_*.yaml, diccionarios/, umbrales.yaml, taxonomia/
data/raw/            (BLOQUEADO) archivos fuente inmutables tal como llegan
data/private/        (BLOQUEADO) bronce/plata con texto e identificadores, claves de seudonimización
data/warehouse.duckdb (BLOQUEADO) base analítica
data/referencia/     DIVIPOLA, cartografía, CIIU, Código Penal, proyecciones DANE (públicos)
models/              modelos locales + MANIFEST.json (hash, origen, licencia)
reports/agregados/   ÚNICA salida que Claude Code puede leer (agregada, suprimida)
src/decla/           paquete: ingesta/ calidad/ normalizacion/ entidades/ texto/ conocimiento/
                     fenomenos/ analitica/ emergencia/ prediccion/ evaluacion/ app/ comun/
scripts/             utilidades de una sola vez (descargar_modelos, generar_fixtures)
tests/               unit/, integracion/, fixtures/ (sintéticos)
Makefile
```

### 3.3 Capas y esquemas DuckDB
`bronce` (crudo como texto) → `plata` (tipado, validado, normalizado, seudonimizado) → `entidades`
(noticia, caso, grupo conexo) → `texto` (relato procesado, menciones, embeddings) → `fenomenos`
(taxonomía versionada, asignaciones) → `oro` (indicadores, asociaciones, alertas, pronósticos)
→ `revision` (anotaciones humanas). Más `meta` (ejecuciones, lotes, calidad).
DuckDB admite un solo escritor: la app abre la base en **solo lectura**.

### 3.4 Estilo de código
- Funciones puras por regla; cada regla de limpieza con prueba unitaria y ejemplo sintético.
- Configuración en YAML, no constantes ocultas en el código.
- Logs estructurados (JSON) sin contenido de filas.
- Docstrings y nombres de columnas derivadas en español, `snake_case`.
- Antes de dar algo por terminado: `make test`, `make lint` y ejecución completa sobre fixtures.

---

## 4. Hallazgos de la muestra de ejemplo (validar en el dataset completo)

La persona entregó una muestra en formato Apple Numbers. Los siguientes hechos se observaron en ella y
**deben convertirse en reglas, pruebas y verificaciones**, no en supuestos fijos: el dataset completo
puede comportarse distinto.

**Formato y estructura**
1. La fuente no es un CSV único: son **dos tablas** en archivos `.numbers`
   - `CASOS`: 40 columnas, una fila por registro SPOA.
   - `RELATOS`: 2 columnas (`CASO_NOTICIA`, `RELATO`).
   La ingesta debe aceptar `.numbers`, `.xlsx` y `.csv`, leer **todo como texto** y unir por `CASO_NOTICIA`.
2. Las tablas declaran ~978 filas pero solo 5 tienen datos: hay **filas totalmente vacías** que se
   descartan en bronce y se cuentan en el reporte de calidad.
3. **Unión CASOS↔RELATOS: 0 coincidencias** en la muestra (los `CASO_NOTICIA` de RELATOS no están en
   CASOS). Medir cobertura en ambos sentidos, cardinalidad (¿varios relatos por noticia?) y conservar
   huérfanos en tablas propias; nunca descartarlos en silencio.

**Esquema real vs. inventario (28 columnas en el plan)**
4. Columnas presentes que el plan no listaba: `RUPTURA`, `TIPO_NOTICIA`, `CASO_LEY`, `LEY`,
   `SECC_DESCRIPCION`, `CAPITULO`, `FECHA_ULTIMA_ACTUACION`, `FECHA_REGISTRO_ACTUACION`,
   `ULTIMA_ACTUACION`, `OTROS_DELITOS`, `DESP_CONOCIDO_CASO_TIT`, `DESP_CONOCIDO_CASO_APOYO`,
   `CASO_GRUPO_ESPECIALIZADO`, `Eje temático APLICA`.
5. `EJE_TEMATICO` **no existe**; hay `Eje temático APLICA` con valores como "por establecer" y "0".
   No asumas equivalencia: regístralo como pregunta abierta.
6. `RELATO` no está en CASOS (viene en la tabla RELATOS).
7. `RUPTURA` y `OTROS_DELITOS` vienen vacías en la muestra; `CASO_GRUPO_ESPECIALIZADO` casi vacía.
8. El esquema se gestiona con un **contrato versionado** (`config/esquema_fuente.yaml`): columnas
   esperadas, alias (incluido el nombre con tilde y espacios), obligatorias/opcionales. Columnas nuevas
   o faltantes generan advertencia y entrada en el reporte, no un fallo silencioso.

**Identificadores**
9. El lector de Numbers convierte `CASO_ID`, `DESP_ID`, `NUMERO_DOCUMENTO` a flotante: forzar texto y
   quitar el sufijo ".0"; nunca operar identificadores como números.
10. `CASO_NOTICIA` tiene 21 dígitos. **Hipótesis a validar**: código DANE de municipio (5) + entidad (2)
    + unidad receptora (5) + año (4) + consecutivo (5). Si se confirma, permite derivar municipio y año
    de recepción y contrastarlos con los campos declarados (solo como verificación de consistencia).

**Fechas**
11. Fechas como texto en formato **M/D/AAAA** (p. ej. `10/8/2026`). Detectar el formato por columna
    (valores > 12 en primera o segunda posición) y no asumirlo; registrar fechas ambiguas.
12. Dentro de los relatos aparecen fechas en otros formatos (`02/09/2026`, `04 DE AGSOTO DEL 2026`,
    `26/Agosto/2026`), probablemente D/M; tratarlas aparte del formato de las columnas.
13. En la muestra, `CASO_FECHA_PRESCRIPCION` = `FECHA_HECHO` + 20 años: verificar esa regla en todo
    el dataset (sirve como prueba de consistencia).
14. Toda la muestra es de **2026** (marzo–octubre). Con un solo año no hay estacionalidad ni historia
    suficiente para pronósticos: el incremento I4 queda condicionado al periodo real del dataset.

**Codificación del texto**
15. Los relatos tienen **mojibake sistemático**: caracteres españoles reemplazados por cirílicos
    (í→н, ó→у, é→й, á→б, ú→ъ, ñ→с, Ñ→С, Á→Б, Ó→У). Es texto cp1252 decodificado como cp1251 y se revierte
    re-codificando en cp1251 y decodificando en cp1252. Aplicar **solo** si se detectan caracteres
    cirílicos, registrar `reparacion_codificacion` por registro y verificar que el resultado no
    contenga cirílico. ftfy por sí solo no corrige este caso.

**Territorio y coordenadas**
16. Nombres inconsistentes: `Meta` vs `META`, `BOGOTÁ, D. C.` vs `BOGOTÁ, D.C.`, tildes variables.
    Normalizar a códigos DIVIPOLA con método y confianza.
17. **Coordenadas sin separador decimal**: `LAT 5316` (≈ 5.316), `LONG -72423` (≈ -72.423), mezcladas
    con valores correctos (`-73.72`). `LONG_DIR_HECHOS` llega con tipos mixtos. Regla: reescalar por
    potencias de 10 hasta caer en la caja de Colombia (lat −4.3 a 13.6; long −82 a −66), marcar
    `coord_reparada`, y validar punto-en-polígono contra el municipio declarado. Precisión efectiva
    ≈ 3 decimales (~100 m): no hacer análisis de punto más fino que eso.

**Categóricas**
18. `DELITO` mezcla artículo y cuantía (`LAVADO DE ACTIVOS ART. 323 C.P.CUANTIA INFERIOR A 100 SMLM`):
    separar `delito_nombre`, `articulo_cp`, `cuantia`. `TITULO` y `CAPITULO` permiten jerarquía del CP.
19. En la muestra todos los registros son de la DECLA (`SECC_DESCRIPCION`), Ley 906, `ACTIVO`,
    `INDAGACIÓN`. Verificar variedad real antes de diseñar cortes por estado o etapa.

**Relatos**
20. Longitud de 492 a 12.056 caracteres (72 a 1.867 palabras). Superan el límite de 128/512 tokens de
    muchos modelos: **fragmentación obligatoria** y evaluar un modelo de contexto largo (p. ej. bge-m3).
21. Estilos muy distintos: actas policiales en mayúsculas, informes de captura en flagrancia (FPJ-5)
    citados textualmente, cooperación internacional (DIAN con HSI/ICE/CBP), fuentes humanas anónimas,
    controles viales. Algunos empiezan a mitad de contexto ("En cumplimiento de lo anterior…").
22. Errores de digitación frecuentes ("APROXIMADAMNETE", "AGSOTO") e incoherencias ("una ciudadana de
    sexo masculino"): el NLP debe ser tolerante y la limpieza no debe "corregir" contenido sustantivo.
23. Los relatos describen **delitos fuente y conexos** (contrabando, favorecimiento al contrabando,
    usurpación de propiedad industrial, contrabando de cigarrillos, declaración fraudulenta de
    subpartidas arancelarias), no solo lavado de activos: el descubrimiento de fenómenos debe reflejarlo.
24. **Datos personales abundantes** en relatos: nombres de servidores, abogados y personas con
    documento, cédulas (incluida extranjera), teléfonos, correos, placas, números de motor y chasis,
    tarjetas profesionales. En CASOS: `NUMERO_DOCUMENTO` y `FISCAL_ASIGNADO_DESPACHO` (servidores).
    Seudonimizar en plata y enmascarar en toda vista analítica.

---

## 5. Forma de trabajo con la persona

- Al iniciar un incremento: entra en **modo plan**, lee `docs/plan_trabajo.md` (fases del incremento) y
  este archivo, propone el plan de tareas con criterios de aceptación y **espera aprobación**.
- Usa la lista de tareas; marca cada tarea al cerrarla. Commits pequeños y descriptivos por tarea.
- Cuando necesites una decisión que es de la persona (umbral, criterio jurídico, definición de unidad
  de análisis, taxonomía), pregúntala con opciones concretas; no la tomes por tu cuenta.
- Cuando necesites ver resultados sobre datos reales, pide a la persona ejecutar el objetivo de `make`
  y leer `reports/agregados/<archivo>`.
- Registra cada decisión técnica en `docs/decisiones/AAAA-MM-DD-titulo.md` (contexto, opciones,
  decisión, consecuencias).
- Al cerrar un incremento: actualiza `docs/informes/I<n>_cierre.md` con entregables, métricas,
  limitaciones, preguntas abiertas y la compuerta de aprobación pendiente.

## 6. Preguntas abiertas (actualizar a medida que se respondan)
- ¿Qué representa una fila de CASOS y cuál es la cardinalidad CASO_ID ↔ CASO_NOTICIA?
- ¿Por qué no coinciden los CASO_NOTICIA de RELATOS y CASOS en la muestra? ¿Extractos distintos?
- ¿`Eje temático APLICA` reemplaza a `EJE_TEMATICO`? ¿Qué significan "por establecer" y "0"?
- Periodo real del dataset completo, volumen y frecuencia de nuevos lotes.
- Hardware disponible (CPU, RAM, GPU) en la máquina de producción.
- ¿Qué fuentes de referencia (DIVIPOLA, cartografía, CIIU, proyecciones) están autorizadas localmente?
- ¿Quién aprueba taxonomía, umbrales de alerta y difusión de resultados?
