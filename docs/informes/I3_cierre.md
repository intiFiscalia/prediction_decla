# Cierre de I3 — Asociaciones, territorio, emergencia y app local

- **Fecha:** 2026-11-04 (actualizado 2026-11-05: corrida real + confirmación de la persona)
- **Estado:** **cerrado.** Construido, probado contra fixtures sintéticos, corrido de punta a
  punta sobre datos reales (346 relatos en alcance), y la persona confirmó que las 6 páginas de
  la app cargan sin error.

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
- 437 pruebas (unitarias + integración), ruff y mypy verdes.

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

## Resultados reales (`make analitica && make emergencia`, 2026-11-05, 346 relatos en alcance)

Leídos de `reports/agregados/i3/` (agregado y suprimido — única carpeta que Claude Code puede
leer, CLAUDE.md §2.1):

- **`fenomenos.csv`**: `lavado_de_activos` 293 (84,68 %), `incautacion_y_conteo_de_efectivo` 84
  (24,28 %), `lavado_de_activos_a_traves_de_empresas` 65 (18,79 %), `organizacion_criminal` 45
  (13,01 %), `(no_clasificado)` 52 (15,03 %). La suma supera 346 por el solape documentado entre
  particiones (ADR 0015) — esperado, no un error de conteo.
- **`sectores.csv`**: 95,09 % indeterminado, 3,18 % explícito, 1,73 % inferido de alta confianza.
  Plausible para este corpus (relatos de lavado de activos rara vez describen explícitamente
  "qué sector" sin que sea el foco del hecho) — no se investigó más a fondo, queda como
  observación, no como hallazgo que requiera acción.
- **`asociaciones_chi2_fenomeno_delito.csv`**: chi²=157,16, V de Cramér=0,33 (asociación
  moderada), p≈0, n=470. Fenómeno y delito están asociados, consistente con que los fenómenos se
  descubrieron a partir del mismo texto que describe el delito.
- **`asociaciones_reglas.csv`**: todas las reglas con *lift* ≈ 1,0 — ninguna combinación
  sorprendente más allá de la prevalencia de `lavado_de_activos` (84,68 % del corpus domina
  cualquier regla que lo tenga como consecuente).
- **`territorio_predominio.csv`**: `lavado_de_activos` predomina en casi todos los departamentos
  con tamaño suficiente; Bogotá (`11`) tiene el mayor volumen (n=119), consistente con la
  concentración de la unidad que tramita ya documentada en I1.
- **`territorio_calidad_puntos.csv`**: 69,94 % exacta, 25,43 % centroide, 3,76 % faltante — **
  coincide casi exactamente** con lo que I1 ya había medido (69,9/25,4/3,8), buena señal de que
  el pipeline lee correctamente los datos ya normalizados.
- **`make emergencia`**: 49 series fenómeno×territorio evaluadas (de hasta 4×30 posibles — el
  resto se omitió por no tener ninguna ocurrencia, ver corrección de bug abajo), **0 alertas, 0
  candidatos, 1 descartada por posible artefacto**. Plausible con solo 10 meses de historia y
  FDR ≤ 10 % estricto sobre 49 pruebas simultáneas — no es necesariamente un defecto, es
  consistente con la limitación ya documentada (dataset corto, sin estacionalidad).

## Bug real encontrado y corregido al correr sobre datos reales

`make emergencia` crasheaba con `ValueError: the first guess on the deviance function returned a
nan`. Causa: el ajuste Poisson (`ajustar_linea_base`) tiene un problema de frontera real en la
IRLS de `statsmodels` cuando la serie observada es **todo cero** — exactamente lo que pasa en la
mayoría de las ~120 combinaciones fenómeno×territorio posibles (4 fenómenos × ~30 departamentos),
porque la mayoría de los fenómenos nunca ocurrió en la mayoría de los departamentos. Se reprodujo
con un ejemplo mínimo de 2 líneas y se corrigió con dos guardas explícitas (serie totalmente en
cero; fenómeno "emergente" sin historia previa hasta el último periodo) más una red de seguridad
(`try/except`) para cualquier otro patrón degenerado no enumerado a mano. Cubierto con pruebas
que reproducen exactamente ambos casos.

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

## Pasos ejecutados por la persona (2026-11-05)

1. `scripts/congelar_taxonomia_v1.py`, `make analitica`, `make emergencia` — resultados arriba.
2. `make app` — confirmó que las 6 páginas cargan sin error.

## Compuerta

**Aprobada, con dos criterios del plan que quedan abiertos por razones estructurales, no por
código pendiente:**
- ✅ Asociaciones con tamaño de efecto, IC y p ajustado; ninguna afirmación causal.
- ✅ Código corrido de punta a punta sobre datos reales sin errores (tras corregir el bug de
  series en cero) y app confirmada visualmente por la persona.
- ⚠️ "Tasa de falsas alarmas aceptada por la persona": con 0 alertas generadas en esta corrida
  (10 meses de historia, FDR ≤ 10 % estricto) no hay una tasa observable sobre datos reales que
  aprobar todavía. Lo que sí existe y es reproducible: la retroprueba *sintética*
  (`decla.emergencia.retroprueba`) — sirve como validación del detector, no sustituye la
  retroprueba real, que necesita más historia con eventos.
- ⚠️ "Un ciclo alerta→revisión→decisión registrado": no se cumple esta ronda — no hubo ninguna
  alerta que revisar, y la cola de revisión con escritura no se construyó (ADR 0015, decisión de
  alcance explícita). Revisar cuando haya alertas reales que atender.

I3 queda cerrado con estas dos salvedades documentadas, no bloqueantes: son consecuencia del
tamaño del dataset (10 meses) y de la decisión de alcance de la app, no de código faltante.
