# 0005 — Modelo de embeddings candidato para RELATO

- **Fecha:** 2026-10-23 (actualizado 2026-10-26 con resultados de fixtures)
- **Estado:** propuesta — **pendiente de la prueba de pares reales anotados (Fase 4)**

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

## Resultados sobre fixtures sintéticas (2026-10-26)

`scripts/evaluar_embeddings_fixtures.py` midió precisión@5 (recuperación del `fenomeno_plantado`
entre los 5 vecinos más cercanos por coseno, agregación por media) sobre los 367 relatos
sintéticos con verdad de terreno (`tests/fixtures/verdad.parquet`,
`reports/agregados/i2/embeddings.md`):

| Modelo | Precisión@5 | Tiempo (s, 367 relatos, CPU) |
| --- | --- | --- |
| `paraphrase-multilingual-mpnet-base-v2` | 0.5523 | 227 |
| `multilingual-e5-base` | 0.5728 | 232 |
| `BAAI/bge-m3` | 0.5938 | 949 |

Los tres superan claramente el azar (1/12 ≈ 0,083 con 12 fenómenos plantados), confirmando que
los tres modelos capturan señal semántica real pese a los estilos de redacción variados y el
mojibake plantado. `bge-m3` tiene la mejor precisión pero tarda ~4,2× más que los otros dos; la
diferencia de precisión entre los tres (0,55–0,59) es pequeña frente a esa diferencia de costo.

## Decisión

**Sigue pendiente de la prueba de pares reales anotados por analistas** (plan_trabajo.md §5.2
exige esa prueba, no solo fixtures sintéticas, antes de fijar el modelo definitivo). Mientras
tanto, `config/embeddings.yaml` usa `paraphrase-multilingual-mpnet-base-v2` como
**placeholder explícito** para que el pipeline de 2A sea ejecutable: es el más rápido y su
precisión en fixtures no es claramente peor que la de `e5-base`. `bge-m3` queda como candidato
fuerte si, al correr la herramienta de anotación de pares reales (`herramienta_anotacion_pares.py`,
`app_anotacion_pares.py`) con analistas, la mejora de precisión resulta grande o si el costo de
tiempo (~1 min por lote de ~350 relatos reales con mpnet/e5-base, ~4 min con bge-m3 por el mismo
volumen, extrapolado de los tiempos de fixtures) no es un problema operativo real — esto se decide
con la persona, no se asume aquí.

## Consecuencias

- Fragmentar relatos (si se usa un modelo de contexto corto) exige decidir cómo combinar los
  vectores de los fragmentos (promedio, máximo) antes de agrupar fenómenos (Fase 6): esa decisión
  se documenta en un ADR nuevo cuando se tome, no aquí.
- Cambiar de modelo después de calcular embeddings para todo el dataset implica recalcular todos
  los vectores versionados (`version_modelo` en el contrato de capas, CLAUDE.md §2.4): no es un
  cambio trivial una vez I2 esté en producción.
