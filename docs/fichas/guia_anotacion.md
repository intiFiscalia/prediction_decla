# Guía de anotación — menciones y sectores (Bloque 2B)

Esta guía la usa un analista para calificar `texto.menciones` con
`app_anotacion_menciones.py`. Todos los ejemplos de esta guía son **sintéticos** (inventados para
ilustrar, nunca relatos reales): Claude Code los escribe porque nunca lee relatos reales
(CLAUDE.md §2.1).

## Qué se califica

Para cada mención candidata (una fila de `texto.menciones`), el analista decide:
- **Confirmar**: la categoría y el valor son correctos y el fragmento de evidencia respalda la
  mención.
- **Rechazar**: la categoría o el valor están mal, o el fragmento no respalda la mención (falso
  positivo de la regla/modelo).
- **Corregir**: la categoría general es correcta pero el valor normalizado no (p. ej. "sector" sí
  aplica, pero el código CIIU asignado no es el correcto); se anota el valor correcto si se sabe.

## Categorías y casos límite

### `articulo_penal`
- **Confirmar:** "Art. 323 C.P." → `valor_normalizado="323"`.
- **Caso límite:** "el artículo 15 del reglamento interno" — NO es un artículo del Código Penal;
  rechazar aunque la regla haya hecho match (coincide el patrón "artículo N" pero no es penal).

### `monto`
- **Confirmar:** "$50.000.000" o "cincuenta millones de pesos".
- **Caso límite:** "el radicado 2024-00123" no es un monto aunque tenga dígitos; si la regla lo
  capturó por error, rechazar.

### `fecha`
- **Confirmar:** cualquier fecha bien formada, en cifras o con mes en texto (incluso con errores
  de digitación como "04 DE AGSOTO DEL 2026").
- **Caso límite:** una fecha mencionada como ejemplo hipotético ("si esto hubiera pasado el 10 de
  enero") sigue siendo una mención de fecha válida; la polaridad (hipotética) se califica aparte,
  no se rechaza la mención.

### `institucion`
- **Confirmar:** "la DIAN confirmó..." → `valor_normalizado="DIAN"`.
- **Caso límite:** "Fiscalía" sola, sin más contexto, dentro de un acta policial de rutina —
  sigue siendo una mención válida de institución (el relato SPOA siempre menciona a la Fiscalía
  como entidad registradora); no se rechaza solo por ser "obvia" o repetitiva.

### `lugar`
- **Confirmar:** cualquier municipio/departamento reconocido por el gazetteer DIVIPOLA.
- **Caso límite:** un municipio mencionado como punto de comparación o error de redacción ("como
  en Medellín, pero esto fue en Cali") — ambos lugares son menciones válidas; no se intenta
  decidir cuál es "el lugar de los hechos" en esta capa (eso ya está en `plata.registros_limpios`
  con otro método, I1).

### `sector`
- **Confirmar:** el código CIIU asignado describe razonablemente la actividad económica
  mencionada o inferida en el relato.
- **Rechazar / corregir:** el código asignado no tiene relación con lo descrito, o el relato no
  da ninguna pista de sector económico (en ese caso el valor correcto suele ser
  `"indeterminado"`, no un código forzado).
- **Nunca** se asocia un sector a una persona o empresa específica, solo al relato. Si una
  anotación intenta vincular sector con una persona, se marca como error de la herramienta, no
  del analista.

### `mecanismo`
- **Confirmar:** el relato describe de forma razonable el mecanismo asignado (p. ej.
  `fraccionamiento_consignaciones`: varias consignaciones pequeñas para evitar reportes).
- **Caso límite:** un relato puede describir más de un mecanismo a la vez (p. ej. empresa fachada
  **y** testaferrato); el clasificador zero-shot de esta versión solo asigna el mejor candidato
  (no es multietiqueta todavía) — si el relato describe varios, confirma el que mejor corresponda
  al fragmento evaluado y anota en comentarios que hay otro mecanismo presente, para la siguiente
  versión.
- **`no_clasificado` es un resultado legítimo**, no un error: si el relato no describe ningún
  mecanismo con claridad, confirmar que quede sin clasificar es la respuesta correcta.

## Polaridad (afirmada / negada / hipotética / atribuida)

- **Negada:** "no se halló evidencia de que el inmueble fuera comprado con dinero ilícito" → la
  mención de "inmueble"/"compra" queda `negada`.
- **Hipotética:** "presuntamente el dinero habría salido de una casa de cambio" → `hipotetica`.
- **Atribuida:** "según manifiesta el testigo, el oro se vendía en la plaza" → `atribuida`.
- **Caso límite:** si hay negación e hipótesis en la misma ventana ("no se logró establecer si
  presuntamente..."), la regla prioriza `negada` (CLAUDE.md: el hecho no se confirma, eso es lo
  que más importa para no sobre-contar).

## Ejemplos sintéticos de referencia

> "SIENDO LAS 10:00 HORAS SE RECIBIÓ INFORME DE LA DIAN SOBRE UNA CASA DE CAMBIO UBICADA EN
> CÚCUTA QUE PRESUNTAMENTE FRACCIONABA CONSIGNACIONES DE HASTA $9.000.000 PARA EVITAR REPORTES A
> LA UIAF. NO SE HALLÓ EVIDENCIA DE VÍNCULOS CON EL ARTÍCULO 323 C.P. EN ESTA ETAPA."

Menciones esperadas en este ejemplo:
- `institucion`: DIAN (afirmada), UIAF (afirmada).
- `lugar`: Cúcuta (afirmada).
- `sector`: casa de cambio → código CIIU 6614 (explícito, confianza 1.0).
- `mecanismo`: fraccionamiento_consignaciones (hipotética — "presuntamente").
- `monto`: $9.000.000 (hipotética, dentro de la misma ventana de "presuntamente").
- `articulo_penal`: 323 (negada — "no se halló evidencia... en el artículo 323").

## Acuerdo entre anotadores

Si dos analistas califican la misma muestra, se calcula kappa de Cohen (o alfa de Krippendorff si
hay más de dos) por categoría, no global: una categoría puede tener buen acuerdo y otra no. Las
categorías con kappa bajo (< 0,6) se revisan: puede ser que la definición de esta guía necesite un
ejemplo más claro, no necesariamente que el extractor esté mal.
