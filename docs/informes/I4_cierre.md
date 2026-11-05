# Cierre de I4 — Atípicos, evaluación consolidada y operación de lotes (acotado)

- **Fecha:** 2026-11-05
- **Estado:** construido y probado contra fixtures sintéticos. Pendiente de que la persona
  corra `make prediccion`, `make evaluar` y `make lote` sobre datos reales y confirme
  resultados (igual que I1–I3, Claude Code no toca `data/raw/`, `data/private/` ni
  `data/warehouse.duckdb` directamente).

## Alcance decidido (ver `reports/agregados/i4/viabilidad.md`)

Dos piezas de la Fase 9 del plan **no son viables con el dataset real** y se documentan como
tales, no se implementan:

- **Pronóstico de frecuencia por fenómeno/territorio**: necesita ≥36 meses de historia; el
  dataset real tiene 10 (ene–oct 2026, I2 §4-bis).
- **Clasificación temática de relatos**: necesita relatos anotados por fenómeno (≥50-100 por
  clase, con kappa medido) para entrenar un clasificador supervisado; no existen (CLAUDE.md §2.3
  prohíbe entrenar sin esa guía). Es trabajo de anotación de un analista, no de ingeniería.

Lo viable y construido: **detección de atípicos**, **evaluación consolidada** y **operación de
lotes**, con varias simplificaciones deliberadas frente al enunciado completo de Fase 12
(documentadas en el plan aprobado y en `docs/manual_operacion.md`): sin MLflow/Evidently/
Prefect/Dagster (alternativas que el propio plan ofrece), sin champion/challenger (un solo
modelo), `make lote` sin recálculo incremental automático aguas abajo (un solo lote real
procesado hasta ahora, sin base para diseñarlo bien).

## Entregables (bloques 4A–4D)

- **4A** (`decla.prediccion`): detección de atípicos con dos rankings independientes
  (Isolation Forest sobre variables estructuradas; distancia coseno al centroide de fenómeno más
  cercano en embeddings) — nunca combinados en un score, para no inventar un peso relativo sin
  base estadística. Ficha de modelo en `docs/fichas/modelos/isolation_forest_atipicos.md`.
- **4B** (`decla.evaluacion`, `make evaluar`): `config/metricas_componentes.yaml` consolida las
  métricas ya medidas en I0-I3 citando su ADR/informe fuente (nunca inventa un número); el
  pipeline añade lo recalculable en vivo (retroprueba sintética de emergencia, resumen de
  atípicos/alertas, fenómenos vigentes) en `reports/agregados/evaluacion/v1.md`.
- **4C** (`decla.ingesta.lote`, `decla.comun.deriva`, `make lote`): valida esquema, clasifica
  nuevo/repetido/modificado por `CASO_NOTICIA` (nunca por `registro_uid`, que cambia entre lotes
  por diseño), guarda historia de cambios en `meta.historico_cambios`, calcula deriva PSI.
- **4D**: página "Salud del sistema" en `decla.app.main` (último lote, calidad, deriva, resumen
  de evaluación, alertas abiertas — sigue sin login, ADR 0015); `docs/manual_operacion.md`; este
  cierre.
- 462 pruebas (unitarias + integración), ruff y mypy verdes.

## Hallazgo real de ingeniería durante la construcción (no de datos)

`plata.registros_limpios` (origen CASOS) y `texto.relato_procesado` (origen RELATOS) tienen cada
uno su propio `registro_uid` — son hashes distintos por diseño (CLAUDE.md §2.4: el hash incluye
la tabla de origen), no la misma llave. La matriz estructurada de atípicos vive en
`plata.registros_limpios`; los embeddings, en `texto.relato_procesado`. Unir las dos por
`registro_uid` directamente habría fallado en silencio (ningún match) — se usa `caso_notica`
(ADR 0002, llave de negocio estable), el mismo patrón ya establecido en los módulos de I3.
Cubierto con una prueba de integración dedicada a esa unión (`test_atipicos.py`).

## Hallazgo documentado, no de código: síntoma de sector inferido cambió de dirección

Al construir `config/metricas_componentes.yaml` (4B) se encontró que el riesgo de ADR 0010
(2026-10-28: 0 % de menciones de sector quedaban "indeterminado", sospechosamente alto) ya no
describe el estado actual: la corrida real de I3 (2026-11-05) dio 95,09 % indeterminado. El
síntoma cambió de dirección — probablemente por la mejora de segmentación de ADR 0012 entre
ambas fechas — pero **sigue sin validación humana en ningún extremo**. Documentado en el YAML,
no investigado más a fondo (fuera del alcance de I4).

## Limitaciones conocidas

- **Atípicos sin precisión@k medida**: no supervisado, sin revisión de analista todavía sobre el
  top-k de cada ranking (ficha de modelo lo declara explícitamente).
- **Evaluación consolidada mezcla cifras duras y "pendiente_de_cifra_formal"**: varios
  componentes (reglas de extracción, taller de taxonomía, retroprueba de emergencia) solo
  quedaron documentados cualitativamente en su momento — no se inventa un número ahora para
  completar la tabla; queda como trabajo futuro medir y publicar esas cifras formalmente.
- **`make lote` no probado contra un segundo archivo CASOS real**: solo contra fixtures
  sintéticos — no hay todavía un segundo lote real con el que validar el diseño de
  clasificación/deriva en producción.
- **Respaldo cifrado sigue bloqueado** (ADR 0007, pendiente de la oficina jurídica).
- **Pronósticos y clasificador temático siguen no viables** — se reabren cuando haya ≥36 meses
  de historia o un analista anote una muestra de relatos por fenómeno.

## Siguiente paso (lo ejecuta la persona)

1. `make prediccion LOTE_ID=<el-lote-id-de-make-nlp>` (atípicos sobre datos reales).
2. `make evaluar` (ensambla la evaluación consolidada con los valores reales de arriba).
3. `make app` → página "Salud del sistema" → confirmar que carga sin error.
4. Cuando llegue un archivo CASOS nuevo real: `make lote ARCHIVO=... LOTE_ID=...` y reportar el
   resultado (clasificación + deriva) para validar el diseño contra un caso real por primera vez.

## Compuerta

**Parcialmente evaluable sin datos reales.** Se cumple ya: los dos problemas no viables de
Fase 9 quedan documentados como tales, sin implementarse (criterio explícito del plan). Pendiente
de datos reales: que los atípicos y la evaluación consolidada corran sobre `data/warehouse.duckdb`
real y la persona confirme que los resultados son razonables; "tres lotes consecutivos sin
intervención manual" no se puede evaluar todavía con un solo lote real procesado en todo el
proyecto.
