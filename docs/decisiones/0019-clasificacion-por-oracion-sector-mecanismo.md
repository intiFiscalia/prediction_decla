# 0019 — Clasificación zero-shot por oración (sector y mecanismo), no por relato completo

- **Fecha:** 2026-11-06
- **Estado:** aceptada

## Contexto

Tras aplicar la capa explícita de mecanismo (ADR 0018) y correr `make conocimiento` +
`make diagnostico-umbral` sobre los 346 relatos reales, la confianza del zero-shot de
"mecanismo" se agrupó en una banda muy angosta (p10=0.81, p99=0.88) sin separación clara entre
aciertos y ruido — el mismo síntoma documentado sin resolver en el ADR 0010 para `sector`
(0 % "indeterminado" en 335 de 346 casos, sospechosamente alto).

La persona identificó la causa antes de que se propusiera recalibrar el umbral a ciegas: ambas
funciones (`clasificar_fragmento` en `zero_shot.py`, `clasificar_sector_inferido` en
`sectores.py`) embebían el campo `descripcion_hecho_enmascarada` **completo** (agregación MEDIA
de todos sus fragmentos, `decla.texto.embeddings.calcular_embeddings_relato`) y lo comparaban
contra la definición de una sola oración de cada categoría. El log de `make conocimiento`
mostraba relatos de 646 tokens (> 512, el límite del modelo); en un relato de varios párrafos,
una sola oración que describe el mecanismo o sector real ("compró cabezas de ganado...") queda
diluida entre cientos de palabras de trámite genérico (identificación, UIAF, policía, fiscalía).
Eso explica la banda angosta: el modelo mide "¿esto es un relato de delito financiero en
general?", no "¿esta oración describe este mecanismo/sector?". Recalibrar el umbral sin corregir
esto habría sido ajustar un número sobre una señal que no discrimina.

## Decisión

1. **Nueva función** `decla.texto.embeddings.calcular_vectores_oraciones`: embebe cada oración
   del texto por separado (spaCy, sin agrupar como `fragmentar_por_limite`, que sí agrupa
   oraciones hasta el límite de tokens — razonable para el embedding de documento completo
   MEDIA/MAXIMO, pero no para comparar contra un vocabulario de categorías).
2. `decla.conocimiento.zero_shot.elegir_mejor_fragmento` y
   `decla.conocimiento.sectores.elegir_mejor_fragmento_sector` (nuevas, puras): aplican la lógica
   de umbral/margen existente (`elegir_por_similitud` / `elegir_sector_por_similitud`, sin
   cambios) a cada oración y se quedan con la de mayor confianza — una sola oración relevante
   puede ganar aunque el resto del relato no se le parezca a ninguna categoría.
3. `clasificar_fragmento` y `clasificar_sector_inferido` mantienen su firma pública (mínimo
   cambio en `orquestador.py`): por dentro ahora llaman a `calcular_vectores_oraciones` +
   la función "mejor oración" en vez de agregar por MEDIA.
4. `texto_evidencia` para el camino inferido pasa a ser la oración real que ganó la comparación
   (antes era `texto[:200]`, sin relación con la evidencia — mismo defecto que el ADR 0018 ya
   había señalado y corregido para el camino explícito de mecanismo).
5. El vocabulario (definiciones de mecanismo, descripciones CIIU) no cambia: son oraciones
   cortas, así que ya producían un solo fragmento y la agregación MEDIA era equivalente.

## Consecuencias

- Requiere volver a correr `make conocimiento` y `make diagnostico-umbral` sobre datos reales:
  la distribución de confianza de sector y mecanismo debería separarse mejor que antes. Si la
  separación mejora lo suficiente, se decide el `confianza_minima` con esa evidencia; si sigue
  angosta, queda pendiente la muestra etiquetada a mano (alternativa ya discutida con la
  persona) antes de fijar un umbral.
- Resuelve la hipótesis de causa del ADR 0010 (sector) de forma simétrica a mecanismo, sin que
  la persona lo pidiera explícitamente para sector esta ronda — se decidió hacerlo junto por ser
  el mismo defecto de arquitectura, no uno nuevo.
- Costo: una oración corta por llamada al modelo en vez de un fragmento más grande — más
  llamadas a `modelo.encode`, pero cada relato real tiene pocas decenas de oraciones; no se
  midió el impacto en tiempo total de `make conocimiento` sobre datos reales todavía.
- No cambia el comportamiento para textos cortos (una sola oración): los tests existentes de
  extremo a extremo con el modelo real siguen pasando sin modificación de expectativas.

## Seguimiento (mismo día): bug de conteo + calibración con muestra etiquetada

Al correr `make conocimiento`/`make diagnostico-umbral` sobre datos reales tras este cambio, la
banda de confianza de mecanismo mejoró (p10-p99 pasó de 0.81-0.88 a 0.83-0.91, cobertura inferida
de 6 a 128 de 300) pero sin un salto claro que permita fijar `confianza_minima` por inspección.
Se confirma que hace falta evidencia medida (precisión real, no solo percentiles), como ya se
había decidido con la persona.

De paso se encontró y corrigió un bug real en `procesar_conocimiento`: `n_sector_indeterminado`
comparaba `valor_normalizado is None`, pero `sectores.py` usa la cadena `SECTOR_INDETERMINADO`
("indeterminado"), nunca `None`, cuando el sector no supera el umbral — el contador reportaba
0 % indeterminado siempre, independientemente del resultado real (coincide con el "0 % en 335 de
346, sospechosamente alto" que el propio ADR 0010 señaló como riesgo). Las tablas reales
(`texto.menciones`) y los filtros de la app/indicadores ya usaban la cadena correctamente; el
bug solo afectaba el resumen impreso por `make conocimiento`. Corregido comparando contra
`SECTOR_INDETERMINADO` en vez de `None`.

Para calibrar con evidencia medida se reutilizó la herramienta de anotación ya existente
(`app_anotacion_menciones.py`, antes repartía el cupo entre las 8 categorías de
`texto.menciones` por igual): se agregó un filtro de categorías en la barra lateral (por defecto
`sector`+`mecanismo`) para que el presupuesto de etiquetado no se diluya en categorías que no se
están calibrando ahora. Se agregó `calcular_precision_por_umbral`
(`decla.conocimiento.herramienta_anotacion_menciones`, pura, testeada) y el script
`scripts/calibrar_umbral_desde_anotacion.py` (`make calibrar-umbral`): une las calificaciones de
`data/private/` (nunca leídas por Claude Code) con la confianza real de `texto.menciones` y
escribe precisión aproximada por umbral candidato en `reports/agregados/diagnostico/
precision_por_umbral.csv`, con supresión de celdas < 5. Flujo completo:
`make anotar-menciones` → `make calibrar-umbral` → decidir `confianza_minima` con la persona
sobre ese reporte.
