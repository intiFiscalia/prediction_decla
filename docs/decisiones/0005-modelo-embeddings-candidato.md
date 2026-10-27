# 0005 — Modelo de embeddings candidato para RELATO

- **Fecha:** 2026-10-23 (actualizada 2026-10-26 con fixtures, cerrada 2026-10-27 con pares reales)
- **Estado:** **aceptada** — `multilingual-e5-base`, con limitaciones documentadas abajo

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

## Resultados sobre pares reales (2026-10-27)

Un analista calificó 70 pares de relatos reales (texto enmascarado, muestreados aleatoriamente de
los 346 en alcance) como "mismo fenómeno" / "distinto" / "no estoy seguro" con
`app_anotacion_pares.py` / `scripts/resumen_pares_calificados.py`. Se comparó la correlación de
Spearman entre esa calificación y la similitud coseno de los vectores (agregación media, relato
completo enmascarado) de los dos modelos más rápidos:

| Modelo | Spearman | Exactitud (umbral 0,5 arbitrario) |
| --- | --- | --- |
| `paraphrase-multilingual-mpnet-base-v2` | 0,2109 | 0,2714 |
| `multilingual-e5-base` | **0,3273** | 0,1857 |

`bge-m3` no se evaluó con pares reales (tarda ~4× más por lote; la persona decidió no esperar
dado el tiempo disponible). La correlación es débil en ambos casos (muy por debajo de lo que
sugerían las fixtures sintéticas, 0,55–0,59 de precisión@5) — ver limitaciones abajo. La
exactitud a umbral 0,5 no es comparable directamente entre modelos (cada uno tiene su propia
escala de similitud); el Spearman, al ser de rango, sí lo es.

## Decisión

**`multilingual-e5-base`**, por mostrar la correlación más alta con el criterio humano (0,33 vs.
0,21 de mpnet) en pares reales, además de precisión@5 ligeramente mejor en fixtures (0,57 vs.
0,55) y admitir más contexto (512 vs. 128 tokens) sin fragmentar tanto. `config/embeddings.yaml`
ya apunta a este modelo.

**Limitación importante, no resuelta:** una correlación de 0,33 es débil, no una validación
fuerte. La hipótesis de trabajo (no confirmada directamente porque Claude Code no puede leer
relatos reales para verificarlo) es que el vector del **relato completo** está dominado por
lenguaje institucional/administrativo repetido entre noticias sin relación con el fenómeno,
porque la segmentación `contexto_denuncia`/`descripcion_hecho` solo se activó en el 4,9% de los
346 relatos reales (17/346, ver `make nlp`) — para el resto, `descripcion_hecho` es el relato
completo, igual de "contaminado" por la plantilla que el relato entero. Antes de confiar en estos
embeddings para agrupar fenómenos en el Bloque 2C, conviene: (a) mejorar la lista de marcadores
de `config/diccionarios/segmentacion_estructura.yaml` con ayuda de un analista que lea una
muestra real, y (b) repetir esta calibración usando los vectores de `embeddings_segmento` (ya se
calculan y guardan) en vez de `embeddings_relato`, una vez que la segmentación separe mejor el
encabezado del hecho.

## Consecuencias

- Fragmentar relatos (si se usa un modelo de contexto corto) exige decidir cómo combinar los
  vectores de los fragmentos (promedio, máximo) antes de agrupar fenómenos (Fase 6): esa decisión
  se documenta en un ADR nuevo cuando se tome, no aquí.
- Cambiar de modelo después de calcular embeddings para todo el dataset implica recalcular todos
  los vectores versionados (`version_modelo` en el contrato de capas, CLAUDE.md §2.4): no es un
  cambio trivial una vez I2 esté en producción.
