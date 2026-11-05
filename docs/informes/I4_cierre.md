# Cierre de I4 — Atípicos, evaluación consolidada, operación de lotes y pronósticos

- **Fecha:** 2026-11-05 (actualizado el mismo día: ADR 0016 reabrió pronósticos; `make
  prediccion` ya corrió sobre datos reales, dos bugs reales encontrados y corregidos en el
  proceso — ver más abajo)
- **Estado:** construido, probado contra fixtures sintéticos, y **`make prediccion` corrido
  sobre datos reales** (346 relatos, 120 series fenómeno×departamento). Pendiente de que la
  persona corra `make evaluar` y `make lote` sobre datos reales (igual que I1–I3, Claude Code no
  toca `data/raw/`, `data/private/` ni `data/warehouse.duckdb` directamente).

## Alcance decidido (ver `reports/agregados/i4/viabilidad.md`, ADR 0016)

**Una pieza de la Fase 9 sigue sin ser viable**, por falta de etiquetas (no de historia):

- **Clasificación temática de relatos**: necesita relatos anotados por fenómeno (≥50-100 por
  clase, con kappa medido) para entrenar un clasificador supervisado; no existen (CLAUDE.md §2.3
  prohíbe entrenar sin esa guía). Es trabajo de anotación de un analista, no de ingeniería.

**Pronóstico de frecuencia por fenómeno/territorio se reabrió (ADR 0016, 2026-11-05):** el
umbral de ≥36 meses que lo bloqueaba lo fijó la planeación inicial sin conocer que los datos
llegan por entregas anuales — nunca se iban a acumular 36 meses continuos. La persona decidió
construirlo con la historia disponible (10 meses), con modelo ingenuo obligatorio de referencia,
sin estacionalidad (menos de 12 meses) e intervalos anchos declarados explícitamente. Ver
Bloque 4E abajo.

Lo demás viable y construido: **detección de atípicos**, **evaluación consolidada** y
**operación de lotes**, con varias simplificaciones deliberadas frente al enunciado completo de
Fase 12 (documentadas en el plan aprobado y en `docs/manual_operacion.md`): sin MLflow/Evidently/
Prefect/Dagster (alternativas que el propio plan ofrece), sin champion/challenger (un solo
modelo), `make lote` sin recálculo incremental automático aguas abajo (un solo lote real
procesado hasta ahora, sin base para diseñarlo bien).

## Entregables (bloques 4A–4E)

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
  de evaluación, alertas abiertas — sigue sin login, ADR 0015); `docs/manual_operacion.md`.
- **4E** (`decla.prediccion.pronosticos`, ADR 0016): pronósticos de frecuencia por fenómeno con
  modelo ingenuo obligatorio, ETS con tendencia (sin estacionalidad) y Poisson/NB con tendencia y
  *offset* (reusa `decla.emergencia.linea_base.construir_series_fenomeno_territorio`, no la
  duplica); *rolling origin* con MASE/WAPE frente al ingenuo. `make prediccion` ahora corre
  atípicos y pronósticos juntos. No tiene página propia en la app todavía (fuera de alcance de
  este bloque, posible extensión futura).
- 475 pruebas (unitarias + integración), ruff y mypy verdes.

## Resultados reales de pronósticos (`make prediccion`, 2026-11-05)

120 series fenómeno×departamento evaluadas, 687 filas en `oro.pronosticos`. `valor_punto` en el
rango [0, 23,57] (promedio 0,88) — acotado y sin negativos tras los dos arreglos de abajo. De
las 10 filas con el valor pronosticado más alto, **solo 1** tiene `supera_ingenuo=True`
(`organizacion_criminal` × departamento 66, ETS, MASE=0,80); las otras 9 tienen MASE > 1 (peor
que el ingenuo). Esto es exactamente lo que ADR 0016 anticipaba: con 10 meses de historia, la
mayoría de métodos más complejos todavía no le ganan a "repetir el último valor" — el sistema lo
reporta honestamente (`supera_ingenuo=False`) en vez de ocultarlo o maquillarlo.

## Dos bugs reales encontrados y corregidos al correr sobre datos reales (no en fixtures)

Los 475 tests contra fixtures sintéticos pasaban en verde, pero ninguno reprodujo estos dos
problemas porque las series sintéticas no tenían el patrón real (muy dispersas, con picos
aislados en departamentos de bajo volumen) — otro recordatorio de por qué el protocolo del
proyecto exige correr sobre datos reales antes de cerrar una compuerta:

1. **Extrapolación sin freno por casi-separación**: series mayormente en cero con un pico
   reciente aislado (el patrón más común en fenómeno×departamento) hacían que el GLM Poisson/NB
   ajustara una pendiente patológica; extrapolarla 3 pasos, incluso amortiguada, daba
   pronósticos de hasta ~72 000 millones. Corregido acotando la pendiente a
   `PENDIENTE_MAXIMA_ABSOLUTA = ln(3)` antes de amortiguar (Gardner 1985) — el ajuste en el
   último periodo observado no se toca, solo la extrapolación más allá de él.
2. **Conteo negativo**: Holt (ETS) es aditivo y no restringe a valores no negativos — una serie
   con tendencia decreciente puede cruzar cero y seguir bajando. `min(valor_punto)` real llegó a
   -1,69 antes del fix. Corregido recortando a 0 el punto y las simulaciones (antes de calcular
   los percentiles de los intervalos).

Ambos quedaron cubiertos con pruebas de regresión que reproducen el caso exacto
(`test_pronostico_poisson_nb_tendencia_con_pico_aislado_no_explota`,
`test_pronostico_ets_tendencia_nunca_es_negativo`).

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
- **Clasificador temático sigue no viable** — se reabre cuando un analista anote una muestra de
  relatos por fenómeno.
- **Pronósticos con pocos orígenes de *rolling origin*** (10 meses de historia real): el MASE/
  WAPE que se calculen serán estadísticamente débiles hasta acumular más entregas anuales — se
  reportan igual, con `n_origenes_backtest` siempre visible, nunca se disfraza de validación
  robusta (ADR 0016).
- **Offset futuro de los pronósticos Poisson/NB es un supuesto, no un dato**: se asume que el
  volumen total del territorio en los periodos futuros es igual al del último periodo observado
  — documentado en el código (`decla.prediccion.pronosticos`), no oculto.

## Siguiente paso (lo ejecuta la persona)

1. ~~`make prediccion LOTE_ID=...`~~ — hecho (2026-11-05), resultados arriba.
2. `make evaluar` (ensambla la evaluación consolidada con los valores reales de arriba).
3. `make app` → página "Salud del sistema" → confirmar que carga sin error.
4. Cuando llegue un archivo CASOS nuevo real: `make lote ARCHIVO=... LOTE_ID=...` y reportar el
   resultado (clasificación + deriva) para validar el diseño contra un caso real por primera vez.
5. Decidir con la persona si los pronósticos actuales (casi ninguno supera al ingenuo todavía)
   se publican con esa advertencia explícita, o se esperan más entregas anuales antes de usarlos
   para algo operativo — el código no fuerza una respuesta, solo la mide.

## Compuerta

**Pronósticos: evaluado sobre datos reales.** Se cumple: construido, sin errores (tras corregir
los dos bugs de arriba), con `supera_ingenuo` calculado por serie (criterio exacto de la
compuerta del plan) — hoy mayormente `False`, lo cual es un resultado honesto, no una falla del
código. Clasificación temática: documentada como no viable, sin implementarse. **Atípicos y
evaluación consolidada**: pendientes de que la persona corra `make evaluar` y confirme. **Lotes**:
"tres lotes consecutivos sin intervención manual" no se puede evaluar todavía con un solo lote
real procesado en todo el proyecto.
