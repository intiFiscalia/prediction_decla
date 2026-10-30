# Cierre de I2 — Texto, conocimiento y descubrimiento de fenómenos

- **Fecha:** 2026-10-28 (actualizado 2026-10-30 tras el taller de revisión, ADR 0012 y ADR 0013)
- **Estado:** **cerrado.** Los tres bloques (2A, 2B, 2C) están construidos, probados y
  commiteados. El taller de revisión humana ya ocurrió (ADR 0013) y produjo
  `config/taxonomia/v1.0.yaml` (1 fenómeno aprobado, "lavado_de_activos"; 1 grupo excluido como
  artefacto) — el criterio que faltaba para la compuerta completa.

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

## Limitaciones conocidas (ya no bloquean el cierre; algunas sí limitan el alcance hacia adelante)

- **Segmentación contexto/hecho mejorada (ADR 0012), no perfecta.** Cobertura real subió de
  4,9 % a 15,0 % con el método de densidad administrativa. El taller confirmó el efecto: el
  grupo con más cobertura de segmentación mostró términos de contenido real (lavado, dinero,
  delito); el grupo con menos cobertura (`dominancia_plantilla=0,96`) se marcó artefacto. Seguir
  subiendo esa cobertura queda como trabajo futuro opcional, no bloqueante.
- **Taxonomía v1.0 mínima:** 1 solo fenómeno aprobado (`lavado_de_activos`), 1 grupo excluido
  (ADR 0013). HDBSCAN solo encontró 2 grupos en esta corrida, mientras NMF y aglomerativo
  encontraron 5 cada uno — es probable que el fenómeno aprobado mezcle varios mecanismos
  distintos (contrabando, testaferros, cripto, etc.) que ningún método separó todavía. El taller
  no pidió dividirlo esta vez; queda como candidato a revisar en una próxima ronda.
- **`definicion` y `delitos_relacionados` quedan pendientes de redacción/cálculo** en
  `config/taxonomia/v1.0.yaml` (ADR 0013) — la app de revisión no captura definición en texto, y
  el cálculo agregado de delitos relacionados por grupo no está conectado todavía.
- **Clasificador multietiqueta y conteo con incertidumbre (plan §7.3-§7.4) siguen sin
  construirse.** Ya existe la taxonomía aprobada que los habilita, pero con una sola clase real
  el clasificador sería binario de facto (`lavado_de_activos` vs. `no_clasificado`) — vale la
  pena decidir con la persona si se construye ya o se espera a tener más fenómenos aprobados.
- `embeddings_segmento` ya difiere más de `embeddings_relato` que antes (15 % vs. 4,9 % de
  cobertura), pero sigue sin evaluarse si vale la pena recalcular agrupamiento por segmento vs.
  por relato completo con el nuevo nivel de cobertura.

## Compuerta

**Se cumple el criterio de taxonomía v1.0 aprobada** (plan_trabajo.md, compuerta I2): el taller
de revisión ocurrió (ADR 0013), produjo `config/taxonomia/v1.0.yaml`, y los demás criterios
verificables sin taller (precisión de reglas, funcionamiento de punta a punta, estabilidad
publicada) ya se cumplían. **I2 queda cerrado.**

**Siguiente paso:** decidir con la persona si se construye el clasificador multietiqueta y el
conteo con incertidumbre (plan §7.3-§7.4) sobre esta taxonomía mínima, o si se pasa directo a I3
(análisis estadístico, territorial y de asociaciones) y se vuelve a fenómenos cuando haya más
mecanismos aprobados.
