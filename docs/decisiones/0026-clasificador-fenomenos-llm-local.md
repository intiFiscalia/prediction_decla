# 0026 — Clasificador de fenómenos con LLM local en cascada con el clasificador sklearn

- **Fecha:** 2026-11-17
- **Estado:** superada por ADR 0027 (2026-11-17) en el punto 2 (cascada) y el punto 6 (no
  descartar el clasificador sklearn). El modelo elegido, el linaje distinto y el punto 5 (Claude
  Code sin leer relatos reales) siguen vigentes — ver ADR 0027 para el detalle de qué cambió y
  por qué.

## Contexto

ADR 0024 construyó un clasificador supervisado (regresión logística sobre embeddings de relato)
que necesita 50-100 relatos anotados por código + kappa de Cohen ≥0.6 antes de poder entrenar
(`decla.fenomenos.clasificador.exigir_cobertura_minima`). Ese modelo lineal, aun entrenado, tiene
un techo: no razona sobre el relato completo para resolver los "casos límite" que la propia guía
de anotación exige distinguir (`docs/fichas/guia_anotacion_fenomenos.md` — p. ej. "una empresa
mencionada solo como lugar de trabajo" vs. "una empresa usada para mover activos"). Un vector de
embedding + un hiperplano lineal no capturan ese tipo de razonamiento contextual tan bien como un
modelo de lenguaje generativo.

La persona pidió (2026-11-17) usar un LLM para lograr ese nivel de detalle, con una condición no
negociable: **debe ser local** — nunca relatos reales hacia una API en la nube (rompería
"herramienta local", CLAUDE.md §1, y la razón de ser de todo el diseño de seudonimización y
enmascarado del proyecto). También pidió explícitamente no usar una opción pequeña: el modelo
elegido debe ser el de mejor calidad que el hardware real soporte, no un recorte por comodidad.

Restricción física verificada (medida real, no estimada): Qwen2.5-14B-Instruct-4bit vía `mlx-lm`
tarda ~38 segundos por relato en generar una clasificación (código + evidencia + confianza) en
este hardware (Apple M5, 16GB RAM, sin GPU CUDA — ADR 0001; carga del modelo ~7s adicionales, una
sola vez por sesión). Con millones de registros reales, correr ese modelo sobre cada fila
tomaría más de un año de cómputo secuencial — inviable incluso como lote anual (CLAUDE.md §5.2:
los datos llegan por lote, no en vivo, pero "inviable" sigue siendo inviable). Esto obliga a no
usar el LLM como el clasificador que toca cada fila, sino a diseñar dónde su costo se paga.

## Decisión

1. **Modelo: Qwen2.5-14B-Instruct, cuantizado a 4-bit, servido con `mlx-lm`** (framework de Apple
   para Apple Silicon — la única vía de inferencia generativa viable en este hardware sin GPU
   CUDA). Ocupa ~8-9GB de RAM unificada; es la opción de mayor calidad que cabe en los 16GB
   disponibles. Se agrega como nuevo `tipo: mlx-lm` en `config/modelos.yaml` y
   `scripts/descargar_modelos.py`, siguiendo el mismo patrón de hash y manifiesto
   (`models/MANIFEST.json`) que los modelos de embeddings ya instalados. Nueva dependencia
   (`mlx-lm`, `mlx`) en un extra nuevo de `pyproject.toml` (`fenomenos_llm`), incluida en
   `scripts/preparar_wheelhouse.sh` — cambio de pila que esta ADR registra explícitamente
   (CLAUDE.md §3.1).
2. **Arquitectura en cascada, no reemplazo**: el clasificador rápido ya existente (sklearn sobre
   embeddings, ADR 0024) sigue corriendo sobre el 100% de los registros — es prácticamente gratis
   a escala de millones de filas. El LLM se usa en dos roles, nunca como el paso que toca cada
   fila:
   - **Asistente de anotación**: sugiere códigos (con el mismo criterio de "caso límite" de la
     guía) para que el analista humano confirme/corrija en `make anotar-fenomenos`, en lugar de
     (o junto con) la sugerencia cruda del borrador de clustering — acelera llegar al piloto de
     50-100/código con una sugerencia de partida de mejor calidad. El analista sigue siendo quien
     decide; esto no cambia el punto 6 de ADR 0024.
   - **Escalamiento por baja confianza**: en producción, los relatos donde el clasificador rápido
     ya marcó `no_clasificado` (ningún código superó `confianza_minima` — la señal que
     `decla.fenomenos.pipeline_clasificador` ya escribe hoy en `fenomenos.
     asignacion_fenomeno_modelo`) se reclasifican con el LLM. No se agrega un umbral numérico
     nuevo sin calibrar: se reutiliza la compuerta de confianza que el clasificador rápido ya
     tiene (CLAUDE.md §2.3 — no inventar un umbral sin evidencia cuando uno ya calibrado resuelve
     lo mismo). Así el volumen completo se cubre en minutos y el razonamiento más caro se gasta
     solo donde el modelo rápido no resuelve con seguridad.
3. **Linaje distinto**: las predicciones del LLM se escriben en
   `fenomenos.asignacion_fenomeno_modelo` con `origen="inferido_modelo_llm"` (nuevo valor,
   distinto de `"inferido_modelo"` del clasificador sklearn) y
   `version_modelo="clasificador_fenomenos_llm-qwen2.5-14b-v1-<run_id corto>"` — mismo esquema de
   columnas que ya usa `scripts/promover_clasificador_fenomenos.py`, que no necesita cambios para
   aceptarlas (filtra por código válido de taxonomía y copia columnas, es agnóstico al origen).
4. **Determinismo exigido** (CLAUDE.md §2.4): `temperature=0.0` y semilla fija documentada en el
   código; misma entrada y mismo hash de modelo deben producir la misma salida. Se documenta la
   versión exacta del modelo descargado (hash SHA-256 del directorio, igual que los demás
   modelos) junto al `run_id` de cada ejecución.
5. **Claude Code sigue sin leer relatos reales**: diseña y ajusta el prompt únicamente con
   ejemplos sintéticos (mismo criterio que toda la documentación de anotación existente),
   construye y mantiene el código del pipeline, y revisa solo las métricas agregadas en
   `reports/agregados/i4/` (precisión/recall/kappa por código, distribución de confianza) para
   decidir si un código necesita mejor prompt. Esto es independiente de que la restricción de
   archivo sobre `data/raw` se haya removido de CLAUDE.md §3.2: es una práctica de diseño del
   pipeline, no solo un permiso de herramienta.
6. **No se descarta el clasificador sklearn**: sigue siendo el que cubre el volumen completo; el
   LLM no lo sustituye, lo complementa. Si en el futuro el volumen de escalamiento resulta
   demasiado alto (umbral mal calibrado, o el clasificador rápido degrada), se revisa el umbral o
   se considera escalar el clasificador rápido mismo por la ruta ya aprobada en
   `plan_trabajo.md §7.3` (SetFit antes de afinar un modelo en español) — no es una decisión que
   esta ADR tome por adelantado.

## Consecuencias

- Nueva dependencia pesada (`mlx-lm`/`mlx`, ~8-9GB de modelo descargado) — exclusiva de Apple
  Silicon; si el proyecto migra de hardware en el futuro, este componente necesita revisión.
- El piloto de anotación de ADR 0024 (50-100/código, doble anotación ≥20%, kappa≥0.6) sigue
  siendo obligatorio antes de confiar en cualquier clasificador — el LLM mejora la sugerencia de
  partida, no elimina la validación humana.
- La fracción de relatos que escala al LLM depende directamente de qué tan bien calibrado esté
  `clasificador_fenomeno.confianza_minima` (hoy `pendiente_de_calibrar`, ADR 0024) — si ese
  umbral queda muy estricto, casi todo escala y se pierde la ventaja de velocidad de la cascada;
  se revisa junto con esa calibración, con evidencia real, no por adelantado.
- `docs/manual_operacion.md` se actualiza con el nuevo paso en el orden de comandos.
