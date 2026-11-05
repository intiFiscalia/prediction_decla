# 0016 — Elimina el umbral de 36 meses para pronósticos; se construye con la historia disponible

- **Fecha:** 2026-11-05
- **Estado:** aceptada

## Contexto

`docs/plan_trabajo.md` §8.4 y §11 condicionaban los pronósticos de frecuencia por fenómeno
(Fase 9, I4) a "≥36 meses de historia estable". `reports/agregados/i4/viabilidad.md` y
`docs/informes/I4_cierre.md` usaron ese umbral para declarar los pronósticos **no viables** con
el dataset real (10 meses, ene–oct 2026) y no se implementó esa pieza.

La persona aclaró (2026-11-05) que esa cifra de 36 meses la fijó la planeación inicial del
proyecto (redactada por una sesión anterior de Claude Code interpretando una regla genérica de
pronóstico de series de tiempo), **no una decisión suya ni un requisito real de la operación**.
El dato llega por **entregas anuales**: no hay un flujo continuo del que vayan a acumularse 36
meses seguidos de la forma que el plan imaginaba — insistir en ese umbral bloquea
permanentemente una pieza del plan que la persona sí quiere tener, aunque sea con limitaciones.

## Decisión

1. **Se elimina el umbral mínimo de historia para pronósticos** de `docs/plan_trabajo.md`
   (§8.4, fila de "Pronóstico de frecuencia por fenómeno"; §11, fila de I4) y de `CLAUDE.md`.
   No se sustituye por otro número fijo (p. ej. 12 o 24 meses): la persona decidió construir
   **ya**, con lo que haya en cada momento, no esperar a un umbral nuevo.
2. **Se construyen pronósticos con la historia real disponible** (hoy 10 meses), con estas
   garantías no negociables, siempre visibles en cada salida (nunca solo en la documentación):
   - **Modelo ingenuo obligatorio como referencia** (plan §9: último valor u media estacional) —
     cualquier modelo más complejo se reporta junto a este, nunca solo.
   - **Sin término de estacionalidad con menos de 12 meses de historia** (no hay ni un ciclo
     anual completo que estimar) — los modelos usan tendencia, igual que ya hace la línea base
     de emergencia (`decla.emergencia.linea_base`, I3).
   - **Intervalos de confianza explícitamente anchos** y la razón ("poca historia") en el mismo
     reporte que muestra el pronóstico — CLAUDE.md "no inventes cifras" aplica también a no
     *esconder* la incertidumbre real detrás de un intervalo que parezca más preciso de lo que
     los datos permiten.
   - *Rolling origin* con tantos orígenes como la historia permita (con 10 meses, pocos — se
     reporta cuántos, no se simulan orígenes que no existen).
3. **Reabre la Fase 9 de I4** ("Pronóstico de frecuencia por fenómeno"): pasa de "no viable,
   documentado" a "viable con limitaciones documentadas, en construcción" — nuevo bloque de
   trabajo (ver plan de implementación aparte).

## Consecuencias

- `reports/agregados/i4/viabilidad.md` y `docs/informes/I4_cierre.md` quedan desactualizados en
  este punto — se corrigen junto con la construcción del nuevo bloque.
- Cada entrega anual nueva mejora el pronóstico (más historia, eventualmente estacionalidad
  estimable) sin que el código tenga que cambiar — el umbral ya no es un bloqueo binario, es una
  property que se reporta (`n_meses_historia`) y mejora con el tiempo.
- "Cambio esperado de actividad por territorio" (misma fila de datos requeridos en el plan) queda
  sujeto a la misma corrección, por extensión.
- No cambia nada sobre **clasificación temática de relatos** (sigue bloqueada por falta de
  anotación, un problema distinto — de etiquetas, no de historia temporal).
