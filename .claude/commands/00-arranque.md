---
description: Prepara el repositorio, el entorno fuera de línea y los datos sintéticos de prueba
---

# Incremento de arranque — repositorio, entorno y fixtures sintéticos

Notas adicionales de la persona (pueden estar vacías): $ARGUMENTS

## Contexto
Lee completos `CLAUDE.md` y `docs/plan_trabajo.md` (secciones 2, 3, 5 y Fase 2). Este arranque deja
listo el esqueleto sobre el que se construirán los incrementos I0–I4. No se toca ningún dato real.

## Primero: plan
Entra en modo plan. Presenta la lista de tareas con criterios de aceptación y espera mi aprobación
antes de crear archivos.

## Tareas
1. **Repositorio y entorno**
   - Estructura de carpetas exactamente como en `CLAUDE.md` §3.2, con `__init__.py` y un `README.md`
     breve por carpeta que diga qué contiene y quién puede leerla.
   - `pyproject.toml` gestionado con uv, Python 3.11+, dependencias agrupadas en extras:
     `base` (polars, duckdb, pyarrow, pandera, numbers-parser, python-calamine, ftfy, rapidfuzz,
     unidecode, pyyaml, structlog), `nlp` (spacy, sentence-transformers, torch CPU, datasketch),
     `fenomenos` (umap-learn, bertopic, scikit-learn), `analitica` (statsmodels, scipy, ruptures,
     geopandas, shapely, esda, libpysal, networkx, mlxtend, prince), `app` (streamlit, plotly),
     `dev` (pytest, ruff, mypy, hypothesis). Fija versiones en `uv.lock`.
   - `.gitignore` que excluya `data/raw`, `data/private`, `*.duckdb`, `models/*` (salvo MANIFEST),
     `.env`, `reports/` salvo `reports/agregados/.gitkeep`.
   - `Makefile` con objetivos vacíos pero documentados: `instalar`, `test`, `lint`, `fixtures`,
     `diagnostico`, `etl`, `nlp`, `fenomenos`, `analitica`, `emergencia`, `prediccion`, `app`,
     `informe`. Cada objetivo escribe en `meta.ejecuciones`.
2. **Instalación fuera de línea**
   - `scripts/preparar_wheelhouse.sh`: descarga todas las ruedas a `wheelhouse/` en una máquina con
     internet; `make instalar` instala solo desde `wheelhouse/` (`--no-index`).
   - `scripts/descargar_modelos.py`: descarga a `models/` los candidatos de spaCy y sentence-transformers
     listados en `config/modelos.yaml` (al menos `es_core_news_lg`,
     `paraphrase-multilingual-mpnet-base-v2`, `intfloat/multilingual-e5-base`, `BAAI/bge-m3`), calcula
     hash SHA-256 y escribe `models/MANIFEST.json` (nombre, versión, licencia, hash, fecha).
   - `src/decla/comun/entorno.py`: fija `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`,
     verifica hashes del MANIFEST al cargar un modelo y falla si alguno no coincide.
   - `.streamlit/config.toml` con `gatherUsageStats = false` y servidor solo en la red local.
3. **Utilidades comunes** (`src/decla/comun/`)
   - Configuración desde YAML, logger JSON que **rechaza** imprimir valores de filas (solo conteos,
     columnas, tipos, ids seudonimizados), conexión DuckDB (lectura/escritura vs. solo lectura),
     registro de ejecución (`run_id`, commit, hashes, parámetros, versiones) como gestor de contexto.
   - Función de supresión estadística para todo lo que se escribe en `reports/agregados/`
     (celdas < 5 → "<5", sin texto libre, sin identificadores) y prueba que lo garantice.
4. **Generador de fixtures sintéticos** (`scripts/generar_fixtures.py` → `tests/fixtures/`)
   Debe reproducir la estructura y **todos los defectos** de `CLAUDE.md` §4 con valores inventados:
   - Dos archivos por formato (`.csv`, `.xlsx` y, si numbers-parser permite escribir, `.numbers`):
     CASOS con las 40 columnas reales (incluida `Eje temático APLICA` con tilde y espacios) y RELATOS.
   - 300–500 registros sintéticos, varios años (2021–2026) para poder probar series, con filas vacías
     intercaladas, duplicados exactos y parciales, noticias con varios delitos, relatos huérfanos y
     casos sin relato, `CASO_NOTICIA` de 21 dígitos coherentes con la hipótesis de estructura
     (y algunos incoherentes), IDs que el lector convertiría a flotante.
   - Fechas M/D/AAAA, algunas inválidas, futuras o con orden ilógico; prescripción = hecho + 20 años
     salvo excepciones deliberadas.
   - Departamentos/municipios con variantes de mayúsculas, tildes, "D. C."/"D.C.", homónimos.
   - Coordenadas correctas, sin separador decimal, invertidas, fuera de Colombia, centroides y vacías.
   - `DELITO` con artículo y cuantía pegados; varios títulos del Código Penal (lavado art. 323,
     contrabando arts. 319–320, enriquecimiento ilícito, testaferrato art. 326, concierto para
     delinquir, etc.).
   - Relatos sintéticos de 60 a 2.000 palabras, en 8–10 estilos (acta policial en mayúsculas,
     informe FPJ-5 citado, cooperación internacional, fuente anónima, control vial, denuncia de
     entidad financiera/UIAF, informe DIAN), describiendo 10–12 fenómenos plantados con vocabulario
     variado (contrabando de mercancías y combustibles, subfacturación y subpartidas falsas,
     fraccionamiento de consignaciones, empresas fachada, testaferros, compra de inmuebles y ganado,
     minería ilegal de oro, giros y casas de cambio, criptoactivos, captación ilegal), negaciones
     ("no se halló"), hipótesis ("presuntamente"), errores de digitación y datos personales
     **ficticios** (nombres, cédulas, teléfonos, correos, placas) para probar el enmascaramiento.
   - Aplica mojibake cp1252→cp1251 a ~70 % de los relatos.
   - Guarda la "verdad de terreno" sintética (`tests/fixtures/verdad.parquet`: fenómeno plantado,
     sector, menciones esperadas) para medir componentes de NLP en pruebas.
   - Semilla fija; regenerar produce archivos idénticos.
5. **Calidad del repositorio**: ruff, mypy básico, pytest con una prueba de humo; `make test` verde.

## Entregables
Repositorio inicial con commit, `make instalar` y `make fixtures` funcionando, `models/MANIFEST.json`
(si la descarga está autorizada en esta máquina; si no, el script listo y probado en seco), y
`docs/decisiones/0001-pila-tecnologica.md`.

## Criterios de aceptación
- `make fixtures && make test` pasa en una máquina sin internet (después de instalar desde wheelhouse).
- Ningún archivo de `tests/fixtures/` contiene un valor copiado de datos reales.
- Una prueba demuestra que el logger no imprime valores de filas y que la supresión funciona.

## Al terminar
Resume en 5 líneas qué quedó listo y pídeme: (1) copiar los archivos reales a `data/raw/`, (2) copiar
DIVIPOLA, cartografía municipal, CIIU Rev. 4 A.C. y proyecciones de población DANE a
`data/referencia/`, (3) confirmar hardware disponible. Luego sugiere ejecutar `/01-i0-diagnostico`.
