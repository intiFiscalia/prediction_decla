# Guía de anotación — fenómenos por relato (ADR 0024)

Esta guía la usa un analista para calificar el **relato completo** con
`app_anotacion_fenomeno.py`. Todos los ejemplos son **sintéticos** (inventados para ilustrar,
nunca relatos reales): Claude Code los escribe porque nunca lee relatos reales (CLAUDE.md §2.1).

Esta guía es distinta de `guia_anotacion.md` (menciones puntuales dentro del relato, Bloque 2B).
Aquí la unidad calificada es el relato entero, y puede llevar **más de un código a la vez**
(multietiqueta, plan_trabajo.md §7.3).

## Qué se califica

Para cada relato candidato, el analista ve el código o códigos que el borrador de clustering
(`fenomenos.grupo_asignacion_borrador` vía `fenomenos.asignacion_fenomeno`) le asignó y decide:
- **Confirmar**: el código (o los códigos) asignado describe razonablemente lo que cuenta el
  relato.
- **Corregir**: marca el conjunto de códigos correcto (puede ser vacío → `no_clasificado`, o
  incluir `ruido_administrativo`, o ser distinto al sugerido).
- **Notas**: por qué, sobre todo cuando la corrección no es una lectura literal (igual criterio
  que `guia_anotacion.md`: sin esto se pierde el razonamiento detrás de cada corrección).

## Códigos (taxonomía v1.0 + dos clases de anotación)

### `lavado_de_activos_a_traves_de_empresas`
- **Confirmar:** el relato describe activos movidos o justificados a través de una o más
  empresas (facturación, aportes societarios, compras a nombre de la empresa) como parte del
  hecho investigado.
- **Caso límite:** una empresa mencionada solo como lugar de trabajo de una persona, sin que el
  relato la vincule al movimiento de activos, no basta para confirmar este código.

### `incautacion_y_conteo_de_efectivo`
- **Confirmar:** el relato describe el hallazgo, incautación o conteo de dinero en efectivo
  (billetes, moneda) como parte del procedimiento narrado.
- **Caso límite:** una cifra de dinero mencionada solo como referencia (p. ej. el monto de una
  demanda civil citada de fondo) sin incautación o conteo real, no confirma este código.

### `organizacion_criminal`
- **Confirmar:** el relato describe una estructura con roles diferenciados (cabecillas, alias,
  logística) operando de forma coordinada, no solo una persona actuando sola.
- **Caso límite:** dos personas mencionadas sin descripción de estructura u organización entre
  ellas no alcanza para confirmar este código.

### `ruido_administrativo`
- **Qué es:** relatos que son, en sustancia, trámite institucional y no narran un hecho
  investigativo propio: solicitudes de información a otra entidad, cartas de remisión, oficios de
  traslado de competencia, acuses de recibo. Coincide con los grupos que el taller de taxonomía ya
  marcó `artefacto`/`descartar` en `config/taxonomia/v1.0.yaml` (p. ej. `hdbscan_0`, `hdbscan_1`,
  `agglomerative_2`): esta etiqueta le da nombre explícito a esa decisión humana ya tomada, no es
  una clase nueva.
- **Confirmar:** "Mediante oficio No. XXXX se solicita a la entidad Y información sobre el
  proceso Z, de conformidad con el artículo 1." — ningún hecho propio, solo la solicitud.
- **Caso límite:** si el oficio narra además el hecho investigado (no solo pide información),
  confirma el fenómeno que corresponda **y** marca que hay contenido administrativo mezclado en
  notas, no `ruido_administrativo` solo.

### `no_clasificado`
- **Resultado legítimo**, igual que en `guia_anotacion.md`: si el relato no describe con claridad
  ninguno de los fenómenos de la taxonomía congelada ni es ruido administrativo, confirmar que
  quede sin clasificar es la respuesta correcta — no fuerces un código solo porque el borrador
  sugirió uno.

## Cuando ninguno de los códigos encaja: "otro, especifica"

La app trae un campo de texto libre junto a las casillas. Si el relato describe con claridad un
fenómeno que **no es** ninguno de los 3 de la taxonomía ni ruido administrativo, escribe ahí el
nombre que le darías (snake_case, como los códigos existentes). No se agrega solo a la taxonomía
ni a la lista de casillas: queda contado en `reports/agregados/i4/candidatos_fenomeno_nuevo.csv`
(mismo criterio que los mecanismos nuevos de menciones, ADR 0020) para que un taller de revisión
decida si lo formaliza. Si no estás seguro de si es un fenómeno distinto o una variante de uno ya
aprobado, confirma el existente y explica la duda en "Notas" — no multipliques candidatos por
cada variante de redacción.

## Multietiqueta — cómo decidir cuándo es más de uno

- **Confirmar varios:** el relato describe, con evidencia clara para cada uno, más de un
  fenómeno (p. ej. incautación de efectivo **y** descripción de organización criminal detrás del
  hallazgo).
- **Caso límite:** no multipliques códigos por generosidad — cada código confirmado necesita su
  propio fragmento de evidencia dentro del relato, no una inferencia encadenada desde otro código.

## Ejemplo sintético de referencia

> "SEGÚN INFORME DE POLICÍA JUDICIAL, EN DILIGENCIA DE REGISTRO SE HALLARON $45.000.000 EN
> EFECTIVO OCULTOS EN UN VEHÍCULO. LOS INVESTIGADORES INDICAN QUE EL DINERO SERÍA PRODUCTO DE
> APORTES DE SOCIOS DE LA EMPRESA XYZ S.A.S., USADA PARA JUSTIFICAR EL ORIGEN DE LOS RECURSOS."

Códigos esperados: `incautacion_y_conteo_de_efectivo` (hallazgo y conteo descritos) y
`lavado_de_activos_a_traves_de_empresas` (la empresa como vehículo para justificar origen).
`organizacion_criminal` NO se confirma: no hay descripción de estructura ni roles.

> "POR MEDIO DEL PRESENTE OFICIO SE SOLICITA A LA DIRECCIÓN DE IMPUESTOS INFORMACIÓN TRIBUTARIA
> DEL INVESTIGADO, DE CONFORMIDAD CON EL ARTÍCULO 15 DE LA LEY X. SE SOLICITA RESPUESTA EN UN
> TÉRMINO DE 10 DÍAS."

Código esperado: `ruido_administrativo` (ningún hecho propio, solo la solicitud).

## Acuerdo entre anotadores

Kappa de Cohen **por código** (no global, igual criterio que `guia_anotacion.md`): un código
puede tener buen acuerdo y otro no. Piloto mínimo antes de construir cualquier clasificador
entrenado (CLAUDE.md §2.3, ADR 0024): 50 relatos, doble anotación en ≥20 % de esa muestra, kappa
≥0,6 por código. Un código con kappa bajo se revisa primero en la guía (ejemplo más claro) antes
de asumir que el extractor está mal.
