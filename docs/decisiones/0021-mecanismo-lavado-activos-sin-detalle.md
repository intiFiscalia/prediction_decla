# 0021 — Código explícito `lavado_activos_sin_detalle` para mecanismo

- **Fecha:** 2026-11-13
- **Estado:** aceptada

## Contexto

Durante la anotación manual con `app_anotacion_menciones.py` (ADR 0019/0020), surgió un caso
recurrente distinto a los dos que ya existían: ni "el modelo acertó un mecanismo" ni "el modelo
se equivocó y hay un mecanismo nuevo que agregar". Hay relatos donde el hecho **sí es lavado de
activos** (es el alcance temático completo del proyecto, CLAUDE.md §5.2), pero el texto no
describe ninguna técnica concreta (no menciona bienes, empresas, testaferros, giros, minería,
contrabando, etc.) — no hay suficiente información para asignar ninguno de los 12 mecanismos
semilla, ni para inventar uno nuevo.

Antes de esta decisión, ese caso quedaba indistinguible de `no_clasificado` (el clasificador no
alcanzó el umbral de confianza): confundía "el relato no tiene suficiente detalle" (hallazgo
real sobre el dato) con "el clasificador falló" (límite de la herramienta). Es precisamente el
síntoma original que motivó todo este trabajo (257/345 relatos genéricos, mensaje de la persona
al abrir este hilo) — la diferencia es que ahora se nombra explícitamente en vez de perderse en
"no_clasificado".

## Decisión

1. Nuevo código `lavado_activos_sin_detalle` en `config/categorias_menciones.yaml` (categoría
   `mecanismo`), con definición en prosa para el zero-shot: "el relato confirma lavado de
   activos pero no describe ninguna técnica u operación concreta".
2. Nombre legible agregado a `MECANISMOS` en `src/decla/app/legibilidad.py`, con nota explícita
   de la diferencia frente a `no_clasificado`.
3. **No se agrega** a `config/diccionarios/mecanismos_expresiones.yaml` (capa explícita de
   coincidencia literal, ADR 0018): no existe una frase literal que indique "ausencia de
   detalle" — solo tiene sentido como código que el modelo zero-shot puede elegir (su definición
   compite con las otras 12 por similitud) o que una persona asigna al corregir una mención en
   `app_anotacion_menciones.py`.
4. **Guía de anotación actualizada**: cuando `valor_normalizado` sea `None`/`no_clasificado` y la
   persona, al leer el relato, concluya que SÍ es lavado de activos pero sin ninguna técnica
   identificable, la acción correcta ya no es "Confirmar" la abstención — es **Corregir** →
   categoría `mecanismo`, valor `lavado_activos_sin_detalle`.

## Consecuencias

- `tests/unit/test_zero_shot.py` pasa de esperar 12 a 13 códigos en el vocabulario de mecanismo.
- `tests/fixtures/verdad.parquet` (generado por `scripts/generar_fixtures.py`) **no tiene**
  todavía narrativas sintéticas plantadas para este código: queda pendiente si se quiere medir
  recall sobre él con fixtures sintéticos. No es necesario para que el código funcione (el
  zero-shot ya lo compara como cualquier otro), solo para evaluarlo con verdad de terreno
  sintética.
- Al recorrer `make conocimiento` sobre datos reales tras este cambio, es esperable que una
  fracción de lo que hoy es `no_clasificado` (o de lo que el modelo asignaba erróneamente a un
  mecanismo específico por falta de alternativa genérica) se mueva a
  `lavado_activos_sin_detalle` — hay que volver a correr `make diagnostico-umbral` para ver el
  efecto en la distribución de confianza por categoría.
