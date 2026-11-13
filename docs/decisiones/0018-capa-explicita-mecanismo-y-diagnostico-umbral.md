# 0018 — Capa explícita para mecanismo y diagnóstico de recalibración de umbral zero-shot

- **Fecha:** 2026-11-06
- **Estado:** aceptada

## Contexto

Tras exponer `ind_mecanismo` en la app (ADR 0017), la persona reportó desde la app real que
**333 de ~347 registros** quedan `no_clasificado` en "mecanismo" — casi todo el dataset. La
causa es medible, no una falla de código: `config/umbrales.yaml` fija
`zero_shot_mecanismo.confianza_minima = 0.85`, copiado del mismo valor de `sector_inferido`, y
ambos se calibraron con **4 oraciones sintéticas de desarrollo**, nunca con una muestra real
(el propio archivo lo documenta así). `sector_inferido` ya mostró el mismo síntoma sobre datos
reales (95 % indeterminado, ADR 0010, sin resolver). Además, "mecanismo" nunca tuvo una capa de
coincidencia literal (explícita) como la de "sector" — siempre dependió solo del modelo.

La persona pidió corregir esto con una condición explícita: **el modelo debe seguir pudiendo
sacar los campos, nunca "quemados" a una lista fija** — cualquier mejora no puede cerrar la
puerta a que aparezcan mecanismos nuevos que el diccionario no anticipó.

## Decisión

1. **Capa explícita para mecanismo** (`config/diccionarios/mecanismos_expresiones.yaml`, nuevo;
   `decla.conocimiento.zero_shot.clasificar_mecanismo_explicito`): coincidencia literal contra
   una lista de expresiones → código, probada **antes** del modelo zero-shot, mismo patrón que
   `clasificar_sector_explicito`. Es una **semilla sin validar** (2026-11-06): 34 expresiones
   para los 12 códigos existentes, pendiente de que la persona la revise y amplíe con lo que
   conoce del corpus real — no se trata como verdad de terreno todavía.
   - Si ninguna expresión coincide, el texto **sigue cayendo al modelo zero-shot** exactamente
     igual que antes (nunca se fuerza `no_clasificado` solo porque el diccionario no lo
     anticipó). El modelo sigue siendo la única vía para detectar un mecanismo no listado.
   - Nueva mención queda con `origen='explicito_regla'`, `confianza=1.0`,
     `extractor='diccionario_mecanismo'`, `texto_evidencia` = la frase literal encontrada (antes
     era siempre `texto[:200]`, sin relación con la evidencia real).
2. **Diagnóstico de recalibración** (`decla.conocimiento.diagnostico_umbral`, nuevo; `make
   diagnostico-umbral`): agrega, por categoría (`sector`, `mecanismo`), los percentiles de
   `confianza` de las menciones `inferido_modelo` (el valor real de similitud top-1 ya se
   guardaba incluso para las que quedaron `no_clasificado` — no hace falta recalcular nada) y
   una tabla de sensibilidad (cuántas pasarían el umbral en varios candidatos de
   `confianza_minima`). Solo estadísticos agregados, con supresión de celdas < 5
   (`decla.comun.supresion`); nunca texto ni `registro_uid` individual.
3. **No se tocó el umbral todavía.** Recalibrar `confianza_minima` sin ver la distribución real
   habría sido adivinar de nuevo (el mismo error que llevó a 0.85). Se decide con la persona
   después de correr `make conocimiento` (para que la capa explícita nueva también alimente las
   menciones reales) y `make diagnostico-umbral` sobre datos reales.

## Consecuencias

- Requiere que la persona corra `make conocimiento` otra vez sobre datos reales (recalcula
  `texto.menciones` con la capa explícita nueva) y luego `make diagnostico-umbral`, antes de que
  se pueda proponer un `confianza_minima` recalibrado con evidencia.
- El mismo patrón (capa explícita + diagnóstico de distribución) es extensible a
  `sector_inferido`, que tiene el mismo síntoma documentado (ADR 0010) — no se tocó en esta
  ronda porque el pedido concreto fue sobre "mecanismo"; queda como extensión natural.
- El diccionario de `mecanismos_expresiones.yaml` es una semilla, no una lista cerrada: cualquier
  expresión nueva que la persona confirme al revisar resultados reales se agrega como una fila
  más, sin tocar código.
