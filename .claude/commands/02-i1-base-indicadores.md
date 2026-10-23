---
description: I1 — Pipeline ETL bronce→plata→entidades (Fase 3) e indicadores descriptivos (parte de Fases 7 y 11)
---

# I1 — Base confiable e indicadores descriptivos

Notas adicionales de la persona: $ARGUMENTS

## Contexto
Lee `CLAUDE.md`, las decisiones aprobadas en I0 (`docs/decisiones/`, `docs/informes/I0_cierre.md`) y
`docs/plan_trabajo.md` Fase 3, Fase 7 (§8.1 indicadores, §8.2 territorio) y Fase 11. Todos los
análisis posteriores heredan los errores de esta capa: prioriza exactitud de conteo sobre velocidad.

## Primero: plan
Modo plan; tareas con criterios de aceptación; espera aprobación.

## Tareas
1. **Bronce** (`src/decla/ingesta/`): copia inmutable a `data/raw/lotes/<lote_id>/`, SHA-256 del archivo,
   registro en `meta.lotes`, carga como texto a `bronce.casos_raw` y `bronce.relatos_raw` con
   `registro_uid`, `lote_id`, `tabla_origen`, `n_fila`.
2. **Validación** (Pandera, `src/decla/calidad/esquemas.py`): esquema por tabla; filas que fallan van a
   `plata.cuarentena` con regla y motivo, nunca se descartan. Conciliación: entrada = plata + cuarentena.
3. **Plata** (`src/decla/normalizacion/`), cada regla en YAML con prueba unitaria:
   - Identificadores como texto sin ".0"; `CASO_NOTICIA` validado (21 dígitos) y descompuesto según la
     hipótesis si I0 la confirmó (`cn_dane`, `cn_entidad`, `cn_unidad`, `cn_anio`, `cn_consecutivo`).
   - Fechas tipadas con formato por columna, banderas `fecha_valida`, `fecha_imputada`, motivo.
   - Reparación de codificación (regla §4.15) con bandera; texto original preservado en bronce.
   - Territorio → `cod_dpto`, `cod_mpio` (DIVIPOLA) para hechos y unidad, con `metodo_mapeo`
     (exacto, normalizado, difuso, manual) y `confianza_mapeo`; tabla de excepciones manuales en
     `config/territorio_manual.yaml`.
   - Coordenadas reparadas con `calidad_coord` ∈ {exacta, reparada_decimal, invertida_corregida,
     centroide, fuera_municipio, fuera_pais, faltante}.
   - `DELITO` → `delito_nombre`, `articulo_cp`, `cuantia`; `dim_delito` con título y capítulo del CP.
   - Catálogos unificados de ESTADO, ETAPA, TIPO_NOTICIA, TIPO_DILIGENCIA, ULTIMA_ACTUACION; columna
     `_orig` para cada campo normalizado.
   - Derivados: días hecho→denuncia, denuncia→registro, registro→asignación, días a prescripción,
     año/mes/semana ISO por cada fecha de referencia, `mismo_dpto_unidad_hechos`, `mismo_mpio`.
   - Seudonimización HMAC-SHA256 de `NUMERO_DOCUMENTO` y `FISCAL_ASIGNADO_DESPACHO` con clave en
     `data/private/claves/` (fuera de git); las vistas analíticas solo ven el token.
4. **Entidades** (`src/decla/entidades/`): `noticia_criminal` (una fila por CASO_NOTICIA con delitos en
   tabla puente), `caso`, `grupo_conexo` (según lo que I0 determinó sobre NO_CASOS_CONEXOS),
   `relato` (unión con RELATOS; huérfanos en `relato_huerfano`), y puentes registro↔noticia↔caso.
5. **Dimensiones**: `dim_territorio` (DIVIPOLA + población DANE por año), `dim_tiempo`, `dim_despacho`
   (con token, sin nombres), `dim_delito`.
6. **Indicadores descriptivos** (`src/decla/analitica/indicadores.py`), cada uno con ficha YAML en
   `docs/fichas/indicadores/` (nombre, fórmula, unidad, fecha de referencia, numerador, denominador,
   limitaciones). Implementa las familias del plan §8.1 que no dependen de NLP: volumen (registros,
   noticias, casos, grupos; razón registros/noticia), composición, territorio (conteo, tasa por
   100.000 hab., cociente de localización por delito), tiempo (serie, variación interanual, rezagos),
   procesales, conexidad y calidad. Fecha de referencia configurable; por defecto la que se aprobó en I0.
   Suavizado bayesiano empírico para tasas municipales con pocos casos.
7. **Mapas** departamentales y municipales (GeoPandas + cartografía local), escala común entre periodos,
   nota de calidad de coordenadas, y matriz origen–destino unidad↔hechos.
8. **Informe reproducible** (Quarto o Jupyter → HTML local) en `reports/` con los indicadores, y una
   versión agregada y suprimida en `reports/agregados/i1/`. Cada gráfico lleva la nota "actividad
   registrada, no incidencia".
9. **Pruebas**: unitarias por regla; integración sobre fixtures comprobando conteos contra la verdad de
   terreno; prueba de idempotencia (dos corridas → mismos hashes de tablas).

## Entregables
`make etl`, `make analitica-descriptiva`, `make informe`; tablas plata/entidades/oro; reporte de
calidad por lote; fichas de indicadores; informe HTML.

## Criterios de aceptación (compuerta I1)
- Conteos conciliados (entrada = plata + cuarentena) y reejecución idéntica.
- Cobertura de pruebas en reglas de normalización ≥ 90 %.
- Analistas revisan el informe y confirman que los conteos por unidad, delito y departamento son
  plausibles frente a lo que conocen (registra su confirmación en `docs/informes/I1_cierre.md`).

## No hagas
Nada de NLP sobre relatos más allá de la reparación de codificación. No inventes denominadores:
si falta población o cartografía, deja el indicador como "pendiente de referencia".

## Al terminar
Pídeme ejecutar `make etl informe`, lee `reports/agregados/i1/`, resume hallazgos y anomalías, y
plantea la compuerta. Sugiere después `/03-i2-texto-fenomenos`.
