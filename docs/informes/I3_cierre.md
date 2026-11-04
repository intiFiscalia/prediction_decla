# Cierre de I3 — Asociaciones, territorio, emergencia y app local

- **Fecha:** 2026-11-04
- **Estado:** **construido y probado contra fixtures sintéticos. Compuerta NO evaluada
  todavía** — falta que la persona corra el pipeline sobre datos reales y confirme los
  resultados (igual que I1/I2, Claude Code nunca abre `data/warehouse.duckdb`).

## Entregables (bloques 3A–3F)

- **3A** (`decla.fenomenos.asignacion`, `decla.analitica.indicadores`): cierra el hueco de
  `fenomenos.asignacion_fenomeno` que el plan define en la Fase 4 y que nunca se había
  construido; dos familias de indicadores nuevas (`ind_fenomenos`, `ind_sectores`) con fichas en
  `docs/fichas/indicadores/`.
- **3B** (`decla.analitica.territorio`, `mapas.generar_mapa_flujos`): perfiles territoriales
  (distancia de Hellinger + agrupamiento), predominio por territorio con prueba binomial frente
  al segundo y tamaño mínimo, Moran I/LISA con gate explícito de cobertura, dispersión de puntos
  válidos.
- **3C** (`decla.analitica.asociaciones`): chi²/Fisher + V de Cramér, reglas de asociación con
  filtro de redundancia, ACM, Poisson/NB con offset, red de co-ocurrencia PMI+Louvain. Grafo de
  conexidad explícitamente no construido (ver limitaciones).
- **3D** (`decla.emergencia`): línea base Poisson/NB sin estacionalidad, CUSUM, EARS,
  Farrington simplificado, puntos de cambio, filtro de artefactos, orquestador con estados
  candidato/alerta/descartada, y retroprueba reproducible con incrementos plantados
  (`decla.emergencia.retroprueba`).
- **3E** (`decla.app.main`): app Streamlit de consulta, sin autenticación ni roles (ADR 0015).
- **3F**: pruebas transversales (chi² contra fórmula cerrada 2×2 con corrección de Yates,
  detectores contra series simuladas con exceso conocido, retroprueba reproducible, prueba
  estática de que la app nunca referencia columnas de texto sin enmascarar), ADR 0015,
  `docs/manual_app.md`, este cierre.
- 433 pruebas (unitarias + integración), ruff y mypy verdes.

## Decisiones de alcance tomadas durante I3 (documentadas en ADR 0015)

1. **App sin autenticación ni roles** — decisión explícita de la persona: hoy la usa una sola
   persona en su propia máquina, nada se expone a la web.
2. **Grafo de conexidad no construido** — `entidades.grupo_conexo` (I1) no identifica cuáles son
   los casos conexos, solo el conteo declarado `NO_CASOS_CONEXOS`.
3. **Novedad semántica reducida**: solo divergencia Jensen-Shannon de vocabulario y deriva de
   centroide (funciones puras). "Relatos no clasificados que forman grupo nuevo denso" requeriría
   volver a correr UMAP+HDBSCAN (Fase 6) sobre ese subconjunto — queda como procedimiento
   documentado, no como código nuevo.
4. **Cola de revisión de alertas no construida** — confirmar/descartar una alerta necesitaría una
   conexión de escritura separada (como `app_revision_fenomenos.py` para la taxonomía); no era el
   foco de este incremento.

## Hallazgo real de ingeniería durante la construcción (no de datos, de diseño estadístico)

Al probar el orquestador de emergencia con picos de 2 periodos consecutivos, el detector no
disparaba ninguna señal. La causa: `ajustar_linea_base` ajustaba la tendencia **incluyendo** el
periodo evaluado (o, en una primera corrección, excluyendo solo el último punto) — con series de
~6-10 periodos, dos periodos anómalos consecutivos se "explican" entre sí en un ajuste de
tendencia lineal, enmascarando el propio exceso que se quiere detectar. Se corrigió comparando la
**ventana reciente agregada** (tamaño = persistencia mínima exigida) contra la tasa de los
periodos base (`decla.emergencia.detectores.p_valor_exceso_ventana_reciente`), que es el p formal
sobre el que se aplica Benjamini-Hochberg. Quedó cubierto con pruebas que replican exactamente
el caso que lo expuso (`test_orquestador_emergencia.py`).

## Limitaciones conocidas (no bloquean el cierre de código; condicionan la validación real)

- **Sin estacionalidad en la línea base**: el dataset real cubre solo ene–oct 2026 (10 meses,
  I2 §4-bis) — menos del año que exige estimar un ciclo anual. La línea base usa solo tendencia.
- **Farrington simplificado, no el algoritmo completo**: reponderación de un solo paso y umbral
  normal sobre la varianza de Poisson, no la transformación 2/3 de Anscombe completa. Con <1 año
  de historia tampoco hay la base multianual para la que Farrington fue diseñado.
- **Un relato puede quedar bajo más de un fenómeno** (ver ADR 0015, punto 1): los indicadores de
  fenómeno lo documentan explícitamente (`pct_participacion` contra el total, no contra la suma).
- **Retroprueba real pendiente**: `decla.emergencia.retroprueba` corre sobre series sintéticas
  con semilla fija, reproducible, pero no sustituye la retroprueba sobre la historia real (que la
  persona debe correr con `make emergencia` y comparar).
- **Moran I/LISA**: muy probable que la cobertura real (346 relatos repartidos en departamentos/
  municipios) no alcance los umbrales mínimos documentados en `decla.analitica.territorio` —
  se sabrá al correr sobre datos reales; el código ya está preparado para reportar "insuficiente
  cobertura" en vez de forzar un número.
- **`config/taxonomia/v1.0.yaml` necesita volver a congelarse** antes de que
  `fenomenos.asignacion_fenomeno` tenga datos: los 4 fenómenos aprobados existentes se congelaron
  antes de que `taxonomia_v1.py` guardara `grupo_id_origen`/`metodo_origen` (Bloque 3A).

## Siguiente paso (lo ejecuta la persona; Claude Code no toca datos reales)

1. `uv run python scripts/congelar_taxonomia_v1.py` (recongela v1.0 con `grupo_id_origen`/
   `metodo_origen` — mismos 4 fenómenos, ahora con trazabilidad).
2. `make analitica` (materializa `fenomenos.asignacion_fenomeno` + indicadores/territorio/
   asociaciones en `oro.*`).
3. `make emergencia`.
4. `make app` y recorrer las 6 páginas.
5. Reportar los resultados de `reports/agregados/i3/` (o lo que imprima cada `make`) para
   validar la compuerta: asociaciones con tamaño de efecto/IC/p ajustado razonables, tasa de
   falsas alarmas de la retroprueba real aceptable, Moran I con su diagnóstico de cobertura real.

## Compuerta

**No evaluada todavía.** Los tres criterios de la compuerta I3 (asociaciones con tamaño de
efecto/IC/p ajustado y sin afirmaciones causales; tasa de falsas alarmas aceptada por la persona;
un ciclo alerta→revisión→decisión registrado) requieren datos reales que Claude Code no puede
generar ni leer directamente. Lo que sí se cumple ya: el código existe, está probado contra
fixtures y simulaciones, y ningún texto sin enmascarar es accesible desde la app.
