# 0024 — Construye la herramienta de anotación y el clasificador de fenómenos; el entrenamiento real sigue bloqueado por falta de etiquetas

- **Fecha:** 2026-11-13
- **Estado:** aceptada

## Contexto

`reports/agregados/i4/viabilidad.md` y `docs/informes/I4_cierre.md` (2026-11-05) cerraron
"Clasificación temática de relatos (fenómeno)" como **no viable todavía**: 0 relatos anotados por
fenómeno, y CLAUDE.md §2.3 prohíbe entrenar un modelo supervisado sin guía de anotación y
etiquetas medidas (kappa entre anotadores). El veredicto fue explícito: "requiere que un analista
anote ≥ 50-100 relatos por clase antes de construir código de entrenamiento — es trabajo de la
persona, no de ingeniería".

La persona pidió (2026-11-13) un sistema que infiera fenómenos sobre relatos, que un analista
corrija por un flujo de revisión, y que esa retroalimentación alimente un reentrenamiento que
reclasifique los relatos. Es exactamente la pieza que el veredicto de I4 dejó pendiente — pero la
causa (cero etiquetas) no desaparece porque se pida construir la pieza: solo desaparece cuando el
analista anota.

Mismo patrón que ADR 0016 con los pronósticos: se separa "construir la herramienta" de "ejecutar
el entrenamiento sobre datos reales", y solo lo primero se hace ahora.

## Decisión

1. **Guía de anotación a nivel de relato** (`docs/fichas/guia_anotacion_fenomenos.md`): define
   los 3 códigos de `config/taxonomia/v1.0.yaml`, más `ruido_administrativo` (coherente con los
   grupos ya marcados `artefacto`/`descartar` en esa misma taxonomía — no es una clase nueva
   inventada, es la etiqueta explícita que le faltaba a una decisión humana ya tomada) y
   `no_clasificado`. Multietiqueta: un relato puede llevar más de un código. Ejemplos
   sintéticos únicamente (CLAUDE.md §2.1).
2. **Herramienta de anotación por relato** (`decla.fenomenos.herramienta_anotacion_fenomeno`,
   funciones puras probadas con fixtures sintéticos) y su interfaz Streamlit
   (`app_anotacion_fenomeno.py`, `make anotar-fenomenos`): mismo patrón que
   `app_anotacion_menciones.py`. Calcula cobertura por código y, si hay doble anotación, kappa de
   Cohen por código (no global) — igual que exige `guia_anotacion.md` para menciones.
3. **Clasificador entrenable** (`decla.fenomenos.clasificador`): regresión logística multietiqueta
   sobre los embeddings de relato ya calculados (`data/embeddings/<lote_id>/`), con una función de
   compuerta (`verificar_cobertura_minima`) que **rechaza entrenar** si algún código no alcanza el
   mínimo de ejemplos confirmados (`config/umbrales.yaml: clasificador_fenomeno.
   minimo_ejemplos_por_codigo`, 50 por defecto, el piso que pidió el veredicto de I4). Probado
   solo con vectores y etiquetas sintéticos.
4. **Punto de entrada** `decla.fenomenos.pipeline_clasificador` (`make entrenar-clasificador-
   fenomenos`): lee `data/private/anotacion_fenomenos/calificaciones.csv` (nunca la lee Claude
   Code) y los embeddings reales, verifica la compuerta del punto 3, entrena, evalúa con partición
   **temporal** (nunca aleatoria) y escribe `fenomenos.asignacion_fenomeno_modelo` (tabla nueva,
   `origen="inferido_modelo"`, `confianza`, `version_modelo`) — **nunca sobrescribe**
   `fenomenos.asignacion_fenomeno` (la de clustering, Fase 6, §2.4).
5. **"Dinámico" significa por lote, no en vivo**: cada corrida de `entrenar-clasificador-
   fenomenos` es una ejecución nueva con su `run_id` en `meta.ejecuciones`; no hay reentrenamiento
   automático al guardar una calificación individual (rompería reproducibilidad, §2.4).
6. **El entrenamiento real sigue bloqueado** hasta que la compuerta del punto 3 pase: la persona
   debe anotar (piloto de 50, doble anotación en ≥20 %, kappa ≥0,6 por código) antes de que
   `make entrenar-clasificador-fenomenos` produzca un modelo real. Esto no es negociable por
   CLAUDE.md §2.3 y esta ADR no lo cambia.

## Consecuencias

- `reports/agregados/i4/viabilidad.md` y `docs/informes/I4_cierre.md` pasan de "no viable
  todavía" a "infraestructura lista, entrenamiento pendiente de anotación humana" — se actualizan
  junto con esta ADR.
- Si la persona no anota, el sistema queda exactamente como hoy: `fenomenos.asignacion_fenomeno`
  (membresía de clustering, probabilidad fija en 1.0) sigue siendo la única asignación de
  fenómeno disponible.
- `config/taxonomia/v1.0.yaml` no cambia de contenido; `ruido_administrativo` es una etiqueta de
  la guía de anotación, no un fenómeno nuevo en la taxonomía congelada.
