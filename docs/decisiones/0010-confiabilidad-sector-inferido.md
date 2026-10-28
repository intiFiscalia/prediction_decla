# 0010 — Confiabilidad del sector CIIU inferido (Bloque 2B)

- **Fecha:** 2026-10-28
- **Estado:** riesgo documentado, **sin validar con anotación real** — no bloquea el cierre de
  2B porque la persona decidió priorizar el tiempo disponible, pero sí bloquea usar
  `texto.menciones` con `categoria='sector'` y `origen='inferido_modelo'` como insumo confiable
  de indicadores (I3) o de descubrimiento de fenómenos (2C) hasta que se resuelva.

## Contexto

`decla.conocimiento.sectores.clasificar_sector_inferido` asigna un código CIIU por similitud de
embeddings contra las ~500 descripciones de `data/referencia/ciiu.csv`, con un umbral de
confianza mínima (0,85) y de margen entre el top-1 y el top-2 (0,01) — recalibrados a mano
(ver `config/umbrales.yaml`) tras observar que los valores iniciales (0,5 / 0,1) rechazaban
incluso casos sintéticos inequívocos ("extracción de oro").

## Hallazgo sobre datos reales (2026-10-28, 346 relatos en alcance, `make conocimiento`)

De 346 relatos: 11 con sector explícito (diccionario), **335 inferidos, 0 indeterminados**
(`n_sector_indeterminado=0`). En la calibración manual con 4 oraciones sintéticas (ver ADR 0005
y el historial de desarrollo), incluso casos de contenido claramente delictivo-económico
("compra de ganado", "transporte de combustible de contrabando") quedaban indeterminados por
margen insuficiente. Que el 100 % de 335 relatos reales supere ambos umbrales simultáneamente es
estadísticamente sospechoso: sugiere que el clasificador no está genuinamente discriminando
sector por sector, sino convergiendo hacia uno o pocos códigos "por defecto".

**Hipótesis de trabajo (no confirmada — Claude Code no puede leer relatos reales para
verificarla):** la misma limitación ya documentada en el ADR 0005. Como la segmentación
`contexto_denuncia`/`descripcion_hecho` solo se activa en 4,9 % de los relatos reales
(`n_con_contexto_denuncia=17/346`, `make nlp`), el texto que se vectoriza para "sector" sigue
siendo, en el 95 % de los casos, el relato casi completo — incluyendo el lenguaje institucional
y procesal repetido entre noticias (encabezados de acta, fórmulas de la Fiscalía) que no tiene
relación con el sector económico real. Si ese lenguaje compartido domina el vector, los 335
relatos podrían estar convergiendo hacia el mismo puñado de códigos CIIU "más genéricos" con
confianza artificialmente alta, en vez de reflejar el sector real descrito en cada caso.

## Decisión

Se documenta el riesgo y **no se bloquea el commit ni el avance a 2C** (decisión de la persona,
2026-10-28, dado el tiempo disponible). En su lugar:

1. `texto.menciones` con `categoria='sector'` y `origen='inferido_modelo'` se marca como **no
   validado**: cualquier indicador o descubrimiento de fenómenos (2C, I3) que use esta columna
   debe decirlo explícitamente ("sector inferido, sin validar con anotación humana —
   CLAUDE.md §2.3: no presentar inferencia de modelo como hecho confirmado").
2. La validación pendiente es la misma herramienta ya construida para la mini-compuerta 2B
   (`app_anotacion_menciones.py`, muestreo estratificado + activo de 50-100 menciones reales):
   cuando haya tiempo, calificar específicamente menciones de `categoria='sector'` revela si la
   hipótesis de arriba es correcta (si la mayoría de "sector" calificadas se rechazan, confirma
   el sesgo de plantilla) o si el miedo era infundado (si la mayoría se confirman, el hallazgo
   de "0 % indeterminado" era solo una característica del catálogo CIIU, no un defecto).
3. No se reentrena ni se re-calibra el umbral hoy sin esa evidencia (CLAUDE.md: "no inventes
   cifras" — ya se recalibró una vez a mano con 4 ejemplos sintéticos; una segunda recalibración
   a ciegas no sería mejor que la primera).

## Consecuencias

- 2C (descubrimiento de fenómenos) no debe usar `categoria='sector'` para describir
  automáticamente los grupos sin la advertencia de esta ADR.
- Si en el futuro se mejora la segmentación `contexto_denuncia`/`descripcion_hecho` (ver
  ADR 0005), conviene repetir esta clasificación de sector usando `embeddings_segmento` en vez
  de `embeddings_relato` — hoy son casi idénticos por el mismo problema de segmentación, así que
  no se ganaría nada repitiéndolo antes de ese arreglo.
