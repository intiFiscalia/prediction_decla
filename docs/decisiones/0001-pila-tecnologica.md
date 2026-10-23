# 0001 — Pila tecnológica y supuestos del incremento de arranque

- **Fecha:** 2026-10-23
- **Estado:** aceptada

## Contexto

El arranque (`/00-arranque`) necesitaba fijar tres cosas que CLAUDE.md §3.1 deja como "pila decidida"
pero que dependen del equipo real: el intérprete y gestor de paquetes, el comportamiento de
`numbers-parser` para generar fixtures, y si se permiten servicios adicionales más allá de
DuckDB + Parquet + Makefile. El hardware confirmado por la persona es un Apple M5 con 16 GB de RAM,
sin GPU CUDA.

## Opciones consideradas

**Intérprete y gestor de paquetes.** La máquina solo tenía Python 3.14 del sistema (`/Library/
Frameworks/Python.framework`) y no tenía `uv` instalado. Python 3.14 es demasiado nuevo para confiar
en que todas las ruedas de la pila (torch, spaCy, GeoPandas, PySAL) tengan builds disponibles.
Alternativas: (a) usar Python 3.14 del sistema con pip/venv; (b) instalar `uv` vía Homebrew y que
`uv` gestione su propio Python 3.11 aislado.

**numbers-parser para generar fixtures `.numbers`.** CLAUDE.md pide imitar los tres formatos de
origen (`.numbers`, `.xlsx`, `.csv`). `numbers-parser` es una librería de solo lectura: no ofrece
API de escritura de archivos `.numbers`. Alternativas: (a) construir el paquete `.numbers` a mano
(es un bundle zip con protobufs internos de Apple, no documentado públicamente, alto riesgo de
fragilidad); (b) omitir `.numbers` en los fixtures y dejarlo documentado como limitación.

**Servicios adicionales (PostgreSQL, Label Studio, Prefect).** Pendiente de respuesta explícita de
la persona; no se necesitan en este incremento.

**Determinismo de los fixtures `.xlsx`.** `openpyxl` estampa el campo `modified` de
`docProps/core.xml` con la hora real al guardar (`openpyxl/writer/excel.py`, no controlable vía
`workbook.properties`), y el contenedor ZIP registra una fecha por archivo con resolución de
segundos. Esto rompe la reproducibilidad exigida ("misma semilla → mismo hash") aunque el contenido
de las celdas sea idéntico. Alternativas: (a) aceptar que los `.xlsx` no sean reproducibles byte a
byte y verificar solo el contenido; (b) reescribir el ZIP después de guardar, con fechas fijas y
parcheando `docProps/core.xml`.

## Decisión

1. Se instala `uv` vía Homebrew (`brew install uv`) y se usa `uv python install 3.11` +
   `uv python pin 3.11` para fijar un intérprete 3.11 aislado del Python 3.14 del sistema, sin tocar
   la instalación global. Es la combinación que CLAUDE.md §3.1 ya exige ("Python 3.11+, uv con
   uv.lock") y evita arriesgar compatibilidad de paquetes con una versión de Python demasiado nueva.
2. `scripts/generar_fixtures.py` **no genera `.numbers`**. Genera `.csv` y `.xlsx`, que son los
   formatos que de todas formas debe soportar la ingesta real (CLAUDE.md §4.1). Queda registrado
   como limitación conocida, no como brecha silenciosa.
3. Se asume por ahora que no se instalan servicios adicionales (DuckDB + Parquet + Makefile, como
   recomienda el plan por defecto); queda como pregunta abierta en CLAUDE.md §6 / sección 12 del plan
   para decidir antes de I2 (anotación) e I4 (orquestación programada).
4. Para los `.xlsx` sintéticos se reescribe el ZIP después de `libro.save()`
   (`scripts/generar_fixtures.py::_hacer_xlsx_deterministico`): se fija `date_time=(2026,1,1,0,0,0)`
   en cada entrada y se parchea `docProps/core.xml` para que `modified` sea un valor constante. Se
   verificó que con esto los cinco artefactos (`casos_sinteticos.csv/.xlsx`,
   `relatos_sinteticos.csv/.xlsx`, `verdad.parquet`) son byte-idénticos entre ejecuciones con la
   misma semilla.
5. Como no hay GPU CUDA y la RAM es limitada (16 GB), el modelo de embeddings por defecto para
   pruebas y desarrollo es `paraphrase-multilingual-mpnet-base-v2` (ligero, CPU). `BAAI/bge-m3` y
   `es_dep_news_trf` se descargan como candidatos de comparación (Fase 4 del plan) pero no se asumen
   como los que se usarán en producción; esa elección se hace con la prueba de 200–300 pares
   anotados que describe la sección 5.2 del plan, no en este incremento.

## Consecuencias

- El repositorio queda atado a Python 3.11 vía `.python-version` y `uv.lock`, independientemente de
  qué Python tenga el sistema por defecto; cualquier persona que clone el repo y corra
  `uv sync` obtiene el mismo intérprete.
- Cuando se copien los archivos `.numbers` reales a `data/raw/` (fuera del alcance de Claude Code),
  la ingesta (I1) deberá probarse contra ellos directamente, no contra un fixture sintético
  equivalente; el lector debe soportar `.numbers` aunque los fixtures no lo cubran.
- Si más adelante se decide sí instalar servicios (Postgres, Label Studio, Prefect), esta decisión
  debe revisarse y registrarse en un ADR nuevo, no editarse retroactivamente.
