# 0005 — Modelo de embeddings candidato para RELATO

- **Fecha:** 2026-10-23
- **Estado:** propuesta — **pendiente de la prueba de pares anotados (Fase 4)**

## Contexto

plan_trabajo.md §5.2 exige elegir el modelo con una prueba local (200–300 pares de relatos
anotados por analistas como "mismo fenómeno / distinto"), no por preferencia a priori. Lo que sí
se puede fijar ahora, sin esa prueba, son las restricciones de entorno: hardware (ADR 0001, Apple
M5, 16 GB RAM, sin GPU CUDA) y longitud de relato (CLAUDE.md §4.20: 492–12.056 caracteres, 72–1.867
palabras en la muestra, lo que supera el límite de 128/512 tokens de varios modelos).

## Opciones consideradas (config/modelos.yaml)

1. **`paraphrase-multilingual-mpnet-base-v2`.** Ligero, estable en CPU; trunca relatos largos
   (límite ~128 tokens por defecto) — exige fragmentar el relato antes de vectorizar.
2. **`intfloat/multilingual-e5-base`.** Admite 512 tokens; sigue exigiendo fragmentación para los
   relatos más largos de la muestra.
3. **`BAAI/bge-m3`.** Contexto largo (hasta 8.192 tokens): podría vectorizar relatos completos sin
   fragmentar, pero es ~2 GB y lento sin GPU; en una máquina de 16 GB sin GPU esto es un costo real
   de tiempo de cómputo, no solo de disco.

## Decisión

**Pendiente de la prueba de similitud anotada (Fase 4).** Recomendación provisional para esa
prueba, dado el hardware: usar `paraphrase-multilingual-mpnet-base-v2` como línea base (CPU,
rápido) y comparar contra `bge-m3` específicamente para medir si el contexto largo compensa el
costo de cómputo en relatos que hoy se fragmentarían con los otros dos modelos. `e5-base` queda
como candidato intermedio si la fragmentación de mpnet-base-v2 degrada la similitud de forma
medible.

## Consecuencias

- Fragmentar relatos (si se usa un modelo de contexto corto) exige decidir cómo combinar los
  vectores de los fragmentos (promedio, máximo) antes de agrupar fenómenos (Fase 6): esa decisión
  se documenta en un ADR nuevo cuando se tome, no aquí.
- Cambiar de modelo después de calcular embeddings para todo el dataset implica recalcular todos
  los vectores versionados (`version_modelo` en el contrato de capas, CLAUDE.md §2.4): no es un
  cambio trivial una vez I2 esté en producción.
