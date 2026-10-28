# Cierre de I2 — Texto, conocimiento y descubrimiento de fenómenos

- **Fecha:** 2026-10-28
- **Estado:** **cerrado parcialmente**. Los tres bloques (2A, 2B, 2C) están construidos,
  probados y commiteados. La compuerta completa de I2 no se cierra todavía porque exige una
  taxonomía v1.0 **aprobada por la persona responsable tras un taller de revisión con
  analistas** (plan_trabajo.md §7.2) — eso es trabajo humano que esta sesión no puede simular ni
  adelantar, no código pendiente.

## Entregables

- **Bloque 2A** (`src/decla/texto/`): normalización conservadora, segmentación
  `contexto_denuncia`/`descripcion_hecho`, patrones por reglas (artículo penal, monto, fecha,
  placa, cédula, NIT, teléfono, correo, motor/chasis, km, subpartida), NER con gazetteers
  (instituciones, DIVIPOLA), enmascaramiento, casi-duplicados (MinHash), embeddings
  (`multilingual-e5-base`, elegido con fixtures + 70 pares reales calificados, ADR 0005),
  buscador semántico, herramienta de anotación de pares (Streamlit).
- **Bloque 2B** (`src/decla/conocimiento/`): tabla `texto.menciones` (plan §6.3), sectores CIIU
  Rev. 4 A.C. (explícito por diccionario + inferido por similitud, `data/referencia/ciiu.csv`,
  499 clases), mecanismos de lavado por zero-shot, herramienta de anotación de menciones
  (Streamlit), guía de anotación (`docs/fichas/guia_anotacion.md`).
- **Bloque 2C** (`src/decla/fenomenos/`): representación (embeddings de segmento + vector de
  menciones), UMAP, agrupamiento (HDBSCAN principal + k-means + NMF + aglomerativo, selección
  por estabilidad), ficha automática por grupo, taxonomía borrador (`v0.1-borrador.yaml`),
  herramienta de revisión con prueba de intrusión (Streamlit).
- `make nlp`, `make conocimiento`, `make fenomenos` funcionando de punta a punta, sobre fixtures
  y sobre los 346 relatos reales en alcance (verificado con `make etl && make nlp &&
  make conocimiento` corridos por la persona).
- 348 pruebas (unitarias + integración), ruff y mypy verdes.
- ADRs: 0005 (modelo de embeddings, aceptada), 0010 (riesgo del sector inferido, documentado sin
  resolver), 0011 (cierre parcial de 2C).

## Decisiones de alcance tomadas durante I2 (con la persona)

1. Meta de anotación de menciones reducida de 500-1.500 (plan) a 50-100 relatos reales, dado el
   tiempo disponible — documentado como alcance menor, ampliable después.
2. Comparación de modelos de embeddings con pares reales: 70 calificados (no los 200-300 del
   plan), suficiente para una decisión informada pero con intervalo de confianza más amplio.
3. Las 3 alternativas completas de agrupamiento (NMF, k-means, jerárquico) se construyeron
   íntegras, no solo un contraste — decisión explícita de la persona.

## Hallazgos reales importantes (no solo teóricos)

- **Segmentación poco efectiva en datos reales:** `contexto_denuncia`/`descripcion_hecho` solo
  se separó en 4,9 % de los 346 relatos reales (17/346). Esto se propaga como riesgo a 2B
  (sector inferido con 0 % "indeterminado" sobre 335 relatos — sospechosamente alto, ADR 0010) y
  a 2C (grupos con baja recuperación de fenómenos plantados en fixtures, ADR 0011): ambos
  síntomas de la misma causa, el vector de entrada sigue dominado por lenguaje institucional
  repetido en lugar del contenido específico del hecho.
- **Bug de rendimiento del entorno:** correr cómputo largo con `run_in_background: true` en el
  sandbox de esta sesión lo hizo ~90× más lento (7290 s vs. 79 s para el mismo cómputo en primer
  plano, mismos resultados). No es un problema del código; se corrigió el método de prueba, no
  el pipeline.
- **Bug real de selección degenerada en HDBSCAN:** la selección por estabilidad podía elegir una
  configuración donde todo el agrupamiento era "ruido", porque una partición constante obtiene
  ARI = 1,0 trivialmente entre corridas de bootstrap. Corregido (ADR 0011).
- **Catálogo CIIU descargado y verificado:** `data/referencia/ciiu.csv` (datos.gov.co, 499
  clases activas, CC BY-SA 4.0), con jerarquía división→sección documentada como tabla fija
  (`config/diccionarios/ciiu_jerarquia.yaml`).

## Limitaciones conocidas (no bloquean lo ya cerrado, sí bloquean I3)

- **Taxonomía v1.0 no existe todavía.** `config/taxonomia/v0.1-borrador.yaml` es un borrador
  automático con `estado: pendiente_revision` en cada grupo — nunca se presenta como fenómenos
  validados (regla explícita del plan).
- **Clasificador multietiqueta y conteo con incertidumbre (plan §7.3-§7.4) no se construyeron.**
  Dependen de la taxonomía aprobada; construirlos antes sería código sin datos reales para
  probarlo. Interfaz esperada documentada en ADR 0011 para cuando el taller ocurra.
- **Sector inferido (2B) y agrupamiento (2C) comparten una limitación sin resolver:** mientras
  la segmentación contexto/hecho no mejore (necesita que un analista lea una muestra real y
  amplíe `config/diccionarios/segmentacion_estructura.yaml`), ambos siguen en riesgo de reflejar
  plantilla institucional en vez de contenido real.
- `embeddings_segmento` casi idéntico a `embeddings_relato` para el 95 % de los relatos reales
  (consecuencia directa del punto anterior): no vale la pena recalcular agrupamiento por
  segmento vs. por relato completo hasta que la segmentación mejore.

## Compuerta

**No se cumple todavía el criterio de taxonomía v1.0 aprobada** (plan_trabajo.md, compuerta I2).
Los demás criterios verificables sin taller (precisión de reglas, funcionamiento de punta a
punta, estabilidad publicada) sí se cumplen para lo que no depende de revisión humana.

**Siguiente paso:** la persona (o un equipo de analistas) corre `app_revision_fenomenos.py` sobre
los grupos reales (ya calculados con `make fenomenos` sobre datos reales), toma las decisiones
del taller (aprobar/renombrar/fusionar/dividir/artefacto/descartar + prueba de intrusión), y con
eso se congela `config/taxonomia/v1.0.yaml`. Solo entonces se retoma este incremento para
construir el clasificador y el conteo con incertidumbre, y se pasa a I3 (análisis estadístico,
territorial y de asociaciones).
