# 0013 — Resultado del taller de revisión: taxonomía v1.0 congelada

- **Fecha:** 2026-10-30
- **Estado:** aceptada

## Contexto

ADR 0011 dejó explícitamente pendiente el taller de revisión humana (plan_trabajo.md §7.2) sobre
los 2 grupos reales que produjo `make fenomenos` tras la mejora de segmentación (ADR 0012). Sin
taxonomía v1.0 aprobada, I2 no cierra su compuerta completa y no se puede avanzar a I3 ni construir
el clasificador de fenómenos (plan §7.3).

## Qué se hizo

La persona (calificador registrado como "INPC" en los primeros intentos, luego sin iniciales en
los clics finales) usó `app_revision_fenomenos.py` sobre los 2 grupos reales:

- **Fichas de grupo:** varios clics de prueba al inicio (artefacto/dividir/fusionar en ambos
  grupos, en 13 segundos — exploración de la interfaz, no decisión final). Decisión final
  (la más reciente por `grupo_id`, criterio explícito de `resolver_decisiones` en
  `taxonomia_v1.py`): grupo 0 → **aprobar** + renombrar a "Lavado de activos"; grupo 1 →
  **artefacto**.
- **Prueba de intrusión:** grupo 0 con varias semillas, aciertos consistentes (incluida una
  observación cualitativa: en el grupo 1, el intruso se distinguía por ser el único relato con un
  hecho delictivo real frente a 5 solicitudes de información/investigación sin hecho — confirma
  independientemente que el grupo 1 es una categoría procesal, no un fenómeno criminal).

## Decisión

1. **Nuevo módulo `src/decla/fenomenos/taxonomia_v1.py`** (`resolver_decisiones`,
   `construir_taxonomia_v1`, `escribir_taxonomia_v1`) y utilidad
   `scripts/congelar_taxonomia_v1.py`: congelan `config/taxonomia/v1.0.yaml` a partir de
   `revision.decisiones_taxonomia` + `fenomenos.grupos_descubiertos`.
2. **Regla de resolución:** para cada `grupo_id`, solo cuenta la decisión de estado
   (aprobar/artefacto/descartar/dividir/fusionar) **más reciente** por fecha — así los clics de
   prueba no contaminan el resultado sin tener que borrar el historial de auditoría. El nombre
   (`renombrar`) es un eje independiente: puede fijarse antes o después del aprobar.
3. **`dividir` y `fusionar` no se resuelven solos:** quedan en una lista `pendientes` explícita en
   el YAML en vez de adivinar cómo partir o combinar grupos — eso requeriría recalcular el
   agrupamiento o decidir manualmente qué ids van a cada lado, ninguno de los dos es código de
   esta ronda.
4. **`v1.0.yaml` solo guarda `ids_ejemplo` (registro_uid, ya seudonimizados) y texto agregado
   (términos c-TF-IDF, nombre, indicadores numéricos) — nunca texto de relato.** A diferencia de
   `v0.1-borrador.yaml` (gitignored, tiene medoides/bordes de texto enmascarado real), v1.0 **sí
   se puede versionar en git**, consistente con plan_trabajo.md §7.2 ("ejemplos sintéticos o
   ids").

## Resultado (`config/taxonomia/v1.0.yaml`)

| código | nombre | n_miembros | dominancia_plantilla | estado |
|---|---|---|---|---|
| `lavado_de_activos` | Lavado de activos | 293 | 0,8294 | aprobado |

Excluido: grupo `1` (53 relatos, `dominancia_plantilla=0,96`) — motivo `artefacto`.

## Limitaciones conocidas, no resueltas aquí

- **`definicion` y `delitos_relacionados` quedan como `"pendiente_de_redaccion_por_analista"` /
  `"pendiente_de_calculo"`.** La app de revisión no tiene un campo de texto para la definición del
  fenómeno (solo nombre); escribirla es trabajo de un analista, no algo que este código deba
  inventar (CLAUDE.md: "no inventes cifras"). `delitos_relacionados` sí es calculable
  agregadamente desde `plata`/`entidades` (distribución de `DELITO` por grupo), pero no está
  conectado todavía — queda como tarea de código futura, no de contenido.
- **Un solo fenómeno aprobado es una taxonomía mínima**, no la granularidad que el plan espera
  (plan §7 anticipa varios mecanismos: contrabando, testaferros, cripto, etc.). HDBSCAN solo
  encontró 2 grupos en esta corrida; NMF y aglomerativo encontraron 5 cada uno (ADR 0012) — el
  grupo aprobado podría mezclar varios mecanismos que ningún método separó todavía. No se fuerza
  una división sin que el taller la pida explícitamente (no ocurrió esta vez).
- El campo `calificador` quedó vacío (`''`) en los clics finales — el analista no volvió a
  escribir sus iniciales en la barra lateral tras la primera sesión. No bloquea nada, pero vale la
  pena pedirlo la próxima vez para la trazabilidad completa.

## Consecuencias

- Con `config/taxonomia/v1.0.yaml` existente, la compuerta de I2 queda cumplida en el criterio que
  faltaba (`docs/informes/I2_cierre.md` se actualiza). Puede avanzarse al clasificador
  multietiqueta (plan §7.3) y al conteo con incertidumbre (§7.4), o directamente a I3 — a decidir
  con la persona.
- El clasificador, cuando se construya, solo tiene **una clase real** (`lavado_de_activos`) más
  `no_clasificado`: es un clasificador binario de facto hasta que haya más fenómenos aprobados.
