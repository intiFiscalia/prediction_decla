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
   este corpus).
6. **Primera ronda de nombrado (2026-11-03) produjo nombres duplicados entre métodos** y tuvo que
   deshacerse — ver "Episodio: nombres duplicados" más abajo. El resultado final de este ADR es
   el de la segunda ronda, después de corregirlo.

## Episodio: nombres duplicados entre métodos (detectado y corregido el mismo día)

Al nombrar los 7 grupos aprobados sin nombre, varios pares de grupos de métodos distintos
compartían vocabulario dominante casi idéntico (p. ej. `hdbscan_0`, `nmf_0` y `agglomerative_1`
los tres con `persona, lavado, activo, delito, policía...`). Se les puso el **mismo nombre** a
los pares que compartían vocabulario, razonando que probablemente era el mismo fenómeno
redescubierto por métodos distintos. Eso fue correcto como lectura semántica, pero **incompleto
como instrucción**: `construir_taxonomia_v1` no fusiona por nombre — cada `grupo_id` con
`aprobar` se vuelve un `codigo` propio, y cuando el nombre colisiona solo le añade un sufijo
(`_2`, `_3`) para no pisar el YAML. Resultado intermedio: 8 "fenómenos aprobados", 3 de ellos con
el mismo `nombre` pero `codigo` distinto (`lavado_de_activos`/`_2`/`_3`). Como
`fenomenos.grupo_asignacion_borrador` asigna cada relato una vez **por método**, un mismo relato
puede quedar asignado simultáneamente a `lavado_de_activos` (hdbscan) y a `lavado_de_activos_2`
(nmf) — sumar esos códigos en un indicador de I3 lo habría contado hasta 3 veces.

**Corrección:** para cada nombre duplicado se eligió un único código canónico con una regla
explícita (no arbitraria): HDBSCAN (método principal) gana si participa; si no, gana NMF sobre
aglomerativo (ya documentado arriba: NMF separó con más nitidez en la prueba de intrusión). Los
códigos no canónicos se volvieron a abrir en el taller y se marcaron `descartar` (con motivo
"duplicado de un fenómeno ya aprobado", no "artefacto" — la diferencia queda solo en este ADR,
`revision.decisiones_taxonomia` no tiene un motivo específico para duplicados todavía).

## Resultado final (`config/taxonomia/v1.0.yaml` recongelado, segunda ronda)

**Aprobados (4):**

| código | nombre | n_miembros | dominancia_plantilla | origen |
|---|---|---|---|---|
| `lavado_de_activos` | Lavado de activos | 293 | 0,8294 | hdbscan_0 |
| `lavado_de_activos_a_traves_de_empresas` | Lavado de activos a través de empresas | 65 | 0,8615 | nmf_4 |
| `incautacion_y_conteo_de_efectivo` | Incautación y conteo de efectivo | 84 | 0,8810 | nmf_2 |
| `organizacion_criminal` | Organización criminal | 45 | 0,6444 | nmf_3 |

**Excluidos (8):** `hdbscan_1` (artefacto), `nmf_1` (descartar), `agglomerative_2` (artefacto),
`agglomerative_3` (descartar), `nmf_0` (descartar, duplicado de `lavado_de_activos`),
`agglomerative_1` (descartar, duplicado de `lavado_de_activos`), `agglomerative_4` (descartar,
duplicado de `lavado_de_activos_a_traves_de_empresas`), `agglomerative_0` (descartar, duplicado
de `incautacion_y_conteo_de_efectivo`).

## Limitaciones conocidas, no resueltas aquí

- **Dominancia de plantilla alta en 3 de 4 aprobados** (0,83 a 0,88 — el umbral de advertencia de
  la app es 0,7; solo `organizacion_criminal` queda debajo, en 0,64). El calificador confirmó
  explícitamente que revisó esta señal antes de aprobar. Queda documentado como riesgo abierto:
  estos fenómenos podrían reflejar estilo de redacción institucional compartido más que
  mecanismos totalmente distintos entre sí.
- **Aglomerativo mostró menor nitidez semántica que NMF en la prueba de intrusión** (observación
  cualitativa del calificador). No se descartó el método en general por esto, pero fue el
  criterio de desempate usado en el episodio de duplicados — es una señal a favor de preferir
  NMF sobre aglomerativo si hay que elegir uno como segundo método de referencia.
- **`revision.decisiones_taxonomia` no distingue "descartar por artefacto" de "descartar por
  duplicado de otro método"** — ambos quedan con `decision = "descartar"`. Si en el futuro se
  quiere auditar cuántos descartes fueron por redundancia entre métodos (señal de que los
  métodos convergen) vs. por ruido real, haría falta un motivo más granular en el esquema.
- **`definicion` y `delitos_relacionados` de los 4 fenómenos siguen `"pendiente_de_redaccion_por_
  analista"` / `"pendiente_de_calculo"`** (igual que en ADR 0013) — la app no captura definición
  en texto.

## Consecuencias

- `docs/informes/I2_cierre.md` se actualiza con los conteos finales (4 aprobados, 8 excluidos).
- I2 sigue cerrado (la compuerta ya se cumplió en ADR 0013); este ADR documenta una ampliación y
  corrección posterior de la misma taxonomía v1.0, no una reapertura de la compuerta.
- El clasificador multietiqueta (plan §7.3), si se construye, parte de 4 clases reales con
  nombre y definición parcial, sin riesgo de doble conteo entre códigos.
