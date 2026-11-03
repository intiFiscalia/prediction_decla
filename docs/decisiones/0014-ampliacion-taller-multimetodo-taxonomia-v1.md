# 0014 — Ampliación del taller a 3 métodos y recongelamiento de taxonomía v1.0

- **Fecha:** 2026-11-03
- **Estado:** aceptada

## Contexto

ADR 0013 cerró la compuerta de I2 con una taxonomía mínima: 1 fenómeno aprobado
(`lavado_de_activos`), 1 excluido. Esa ADR ya señalaba el riesgo: HDBSCAN (método principal) solo
encontró 2 grupos en la corrida real, mientras NMF y aglomerativo encontraban 5 cada uno (ADR
0012) — estructura más fina que el taller nunca llegó a revisar porque `procesar_fenomenos` solo
fichaba el grupo de HDBSCAN. El plan (§7) anticipa varios mecanismos (contrabando, testaferros,
cripto, etc.), no uno solo, así que valía la pena presentarle al taller la estructura de los
contrastes antes de aceptar una taxonomía de un solo fenómeno como definitiva.

## Decisión

1. **`procesar_fenomenos` ahora construye ficha completa para HDBSCAN, NMF y aglomerativo** (no
   solo el principal). k-means se deja fuera: en datos reales encontró los mismos 2 grupos que
   HDBSCAN, sin aportar estructura nueva que revisar.
2. **`grupo_id` lleva prefijo de método** (`hdbscan_0`, `nmf_3`, `agglomerative_2`) porque los
   tres métodos reusan los mismos números de etiqueta y colisionarían sin el prefijo.
   `fenomenos.grupos_descubiertos` y `fenomenos.grupo_asignacion_borrador` ganan la columna
   `metodo`.
3. **Migración de una sola vez** (`scripts/migrar_decisiones_taxonomia_metodo.py`): las 2
   decisiones ya guardadas en `revision.decisiones_taxonomia` bajo `grupo_id` sin prefijo ("0",
   "1") se reescriben a `hdbscan_0`/`hdbscan_1` para seguir emparejando con la tabla nueva.
   Idempotente (solo toca `grupo_id` puramente numérico).
4. **La app de revisión (`app_revision_fenomenos.py`) agrupa "Fichas de grupo" por método**, y la
   prueba de intrusión solo compara dentro de un mismo método (mezclar métodos no mide lo mismo,
   cada uno particiona el corpus completo a su manera).
5. **El taller se repitió sobre las 12 fichas totales en datos reales** (2 HDBSCAN + 5 NMF + 5
   agglomerative; k-means excluido). Nota: en fixtures sintéticos de prueba NMF y aglomerativo
   habían producido 15 y 20 grupos respectivamente — en datos reales produjeron 5 cada uno; el
   número depende del corpus, no es una constante del método. El calificador (INPC) confirmó las
   2 decisiones previas de HDBSCAN sin cambios (`hdbscan_0`→aprobar/"Lavado de activos",
   `hdbscan_1`→artefacto) y decidió sobre los 10 grupos nuevos de NMF y aglomerativo. Probó
   intrusión en NMF (acertó casi todas) y en aglomerativo (los relatos "eran similares" entre
   grupos — señal cualitativa de que aglomerativo separa con menos nitidez semántica que NMF en
   este corpus, documentada aquí, no accionada todavía).

## Resultado (`config/taxonomia/v1.0.yaml` recongelado)

**Aprobados (8):**

| código | nombre | n_miembros | dominancia_plantilla |
|---|---|---|---|
| `lavado_de_activos` | Lavado de activos | 293 | 0,8294 |
| `grupo_nmf_0_sin_nombre_asignado` | *(sin nombre)* | 98 | 0,8469 |
| `grupo_nmf_2_sin_nombre_asignado` | *(sin nombre)* | 84 | 0,8810 |
| `grupo_nmf_3_sin_nombre_asignado` | *(sin nombre)* | 45 | 0,6444 |
| `grupo_nmf_4_sin_nombre_asignado` | *(sin nombre)* | 65 | 0,8615 |
| `grupo_agglomerative_0_sin_nombre_asignado` | *(sin nombre)* | 72 | 0,7500 |
| `grupo_agglomerative_1_sin_nombre_asignado` | *(sin nombre)* | 113 | 0,8319 |
| `grupo_agglomerative_4_sin_nombre_asignado` | *(sin nombre)* | 57 | 0,8772 |

**Excluidos (4):** `hdbscan_1` (artefacto), `nmf_1` (descartar), `agglomerative_2` (artefacto),
`agglomerative_3` (descartar).

## Limitaciones conocidas, no resueltas aquí

- **7 de 8 fenómenos aprobados quedaron sin nombre** (`"Grupo X (sin nombre asignado)"` en
  `nombre`, `grupo_x_sin_nombre_asignado` en `codigo`). El calificador decidió explícitamente
  posponer el nombrado (sesión del 2026-11-03) en vez de inventarlo sin revisar los relatos con
  más calma. El `codigo` que queda grabado hereda el `grupo_id` crudo del algoritmo — no es
  estable entre corridas futuras (plan §7.2 exige "código estable"); renombrar y recongelar no es
  destructivo, puede repetirse cuando el analista tenga los nombres.
- **Dominancia de plantilla alta en 7 de 8 aprobados** (0,64 a 0,88 — el umbral de advertencia de
  la app es 0,7). El calificador confirmó explícitamente que revisó esta señal antes de aprobar
  (no es un descuido). Queda documentado como riesgo abierto: varios de estos fenómenos podrían
  reflejar estilo de redacción institucional compartido más que mecanismos criminales distintos
  entre sí — los términos dominantes de varios grupos se superponen fuertemente
  (`persona, lavado, activo, delito, policía, información, empresa`). Dos grupos sí muestran
  vocabulario más diferenciado: `nmf_2`/`agglomerative_0` (conteo de efectivo: `dinero, pesos,
  color, billete`) y `nmf_3` (inteligencia/fuente: `moneda, fuente, alias, criminal,
  organización`).
- **Aglomerativo mostró menor nitidez semántica que NMF en la prueba de intrusión** (observación
  cualitativa del calificador: relatos de distintos grupos de aglomerativo "eran similares"). No
  se descartó el método por esto, pero es una señal a favor de NMF como segundo método de
  referencia si hay que elegir uno.
- El clasificador multietiqueta (plan §7.3) ahora tiene 8 clases reales en vez de 1 — deja de ser
  binario de facto — pero 7 sin nombre ni definición: probablemente conviene nombrarlas antes de
  entrenar, para que las métricas por clase sean legibles.

## Consecuencias

- `docs/informes/I2_cierre.md` se actualiza con los nuevos conteos y limitaciones.
- I2 sigue cerrado (la compuerta ya se cumplió en ADR 0013); este ADR documenta una ampliación
  posterior de la misma taxonomía v1.0, no una reapertura de la compuerta.
- Antes de construir el clasificador multietiqueta o avanzar indicadores por fenómeno en I3, vale
  la pena decidir con la persona si se nombran los 7 grupos pendientes primero.
