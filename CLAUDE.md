# CLAUDE.md — contexto del proyecto GIC

Este archivo da a Claude (o a cualquier asistente) el contexto y las reglas con que se construyó el proyecto, para editarlo sin romper lo que ya funciona. Léalo completo antes de cambiar algo.

## 1. Qué es y de dónde viene

- Reporte analítico de los relatos que llegan al **Grupo de Información Criminal (GIC)** de la Fiscalía, construido a
  partir del Excel `DatosAn_lisisReumenGICLavado_V1.xlsx` (598 relatos, ingreso 26-sep-2024 a 10-nov-2026, 49 columnas).
- Existe un tablero publicado en Claude (artefacto de tipo *Data*, «GIC · Reporte de fenómenos criminales») con la
  misma página. Este proyecto lo reproduce fuera de Claude: `reporte/src/` es el mismo código de página y
  `reporte/dash_shim.js` emula el entorno `dash` del tablero.
- Regla del usuario: **«apégate al plan de la solicitud»**. El plan original pedía las páginas 1–8; después se
  añadió la 9 (predicciones) y la 10 (fenómenos del lavado). El 2026-11-19 el usuario pidió simplificar la
  interfaz: la 9 se fusionó dentro de la 7 (ambas son «predicción») y la 10 se absorbió en la 2 (ver más abajo),
  así que hoy quedan 8 páginas:
  1. Indicadores descriptivos: conteos y tasas por periodo, territorio, delito y etapa procesal, siempre con el
     recordatorio de que miden **actividad institucional registrada, no incidencia real del delito**.
  2. Fenómenos semánticos: distribución por fenómeno (taxonomía versionada; lavado por sector/mecanismo), con
     **origen** (registrado / extraído_regla / extraído_modelo / inferido) y **confianza** visibles. Incluye los
     fenómenos de «delito fuente» del lavado (narcotráfico, corrupción, captación, etc. — ver sección 4).
  3. Territorio: mapas departamental y municipal normalizados contra **DIVIPOLA**, con cocientes de localización.
  4. Sectores económicos: asociación fenómeno↔sector **CIIU** con tamaño de efecto (OR), IC95 y p ajustado
     **Benjamini–Hochberg**; nunca «solo correlación».
  5. Red de asociaciones: co-ocurrencias (actividad, mecanismo, bien, lugar) con NetworkX y reglas de asociación.
  6. Emergencia/alertas: **EARS/CUSUM** sobre línea base Poisson/binomial negativa, con **tasa de falsas alarmas**;
     siempre «señal para revisión», nunca alarma definitiva.
  7. Predicciones: pronóstico de cuántos relatos llegarán (**modelo ingenuo de referencia obligatorio**, intervalos
     amplios, poca historia — **ADR 0016**) junto con las «otras predicciones»: probabilidad de generar caso,
     tiempo hasta el cierre, relatos abiertos y composición futura de fenómenos. Reescrita en lenguaje sencillo a
     pedido del usuario.
  8. Organizaciones criminales identificadas.
- El plan mayor del usuario es una app Streamlit sobre DuckDB (tablas «oro», autenticación, exportación); este
  proyecto es la versión de reporte y no la incluye.

### DECLA (segunda fuente, agregada 2026-11-23)

- Segunda fuente del mismo reporte: `DECLA_2024_2026.xlsx`, con **otra estructura**, no una variante de la de
  GIC. Dos hojas: `Hoja1` (1.929 casos SPOA **ya abiertos**, 40 columnas legales/procesales: `ESTADO`, `ETAPA`,
  `DELITO`, `CAPITULO`, `TITULO`, `DEPARTAMENTO_HECHOS`/`MUNICIPIO_HECHOS`, `COMPETENCIA_DESPACHO`,
  `TIPO_NOTICIA`, `TIPO_DILIGENCIA`, fechas `CASO_FECHA_DENUNCIA`/`FECHA_CREACION`/`FECHA_HECHO`, etc.) y
  `Relato` (`CASO_NOTICIA`, `RELATO`). Se unen 1 a 1 por `CASO_NOTICIA` (verificado: sin huérfanos en ningún
  lado). `RELATO` es el equivalente de `ResumenHechos` de GIC.
- DECLA **no tiene** los campos de trámite/entrada del GIC (`TipoEntrada`, `EntidadRemite`, `CanalRecepción`,
  `DecisionFiscalUGIC`, fechas de trámite): cada fila ya es un caso SPOA formalmente abierto, no un relato de
  intake que puede o no derivar en caso. Por eso varias piezas del reporte **no aplican y se omiten con una
  nota**, en vez de inventar un sustituto (ver más abajo).
- Pipeline paralelo, nunca importa ni modifica `pipeline.py`/`predicciones.py`: `pipeline/pipeline_decla.py` y
  `pipeline/predicciones_decla.py`. Reutilizan `taxonomia.py` (patrones sobre el relato, sectores CIIU,
  organizaciones) y `divipola.py` tal cual. Producen el mismo esquema de archivos JSON que ya consume
  `reporte/build_report.py`, para no tocar el frontend salvo lo estrictamente necesario.
- **Fecha base = `FECHA_CREACION`** (decisión del usuario, 2026-11-23): es la única fecha limpia y acotada
  2024-01→2026-11 (igual que el nombre del archivo); `CASO_FECHA_DENUNCIA` tiene una cola del 13% de los casos
  hasta 2008. `FECHA_CREACION` es el orden base (`rid`), define la ventana de meses/calidad del reporte, y es
  la única fecha que usan las páginas 4–7 (que, como ya pasa con `desde`/`hasta`/`dpto`, se calculan una sola
  vez sobre el total). En la interfaz, un selector "Fecha base" (solo visible con esta fuente, en `index.html`
  junto a los demás filtros) deja agrupar por mes en las páginas 1, 2, 3 y 8 usando `FECHA_CREACION`,
  `CASO_FECHA_DENUNCIA` o `FECHA_HECHO`; un caso cuya fecha alterna cae fuera de la ventana 2024-01→2026-11
  simplemente no aparece en esa serie mensual (sigue contando en los totales y en las demás páginas).
- **Fenómenos (página 2):** la fuente "registrado" viene de `DELITO`/`CAPITULO`/`TITULO`
  (`delito_a_fenomeno()` en `pipeline_decla.py`), no de una temática priorizada manual. Decisión del usuario:
  solo mapea a categorías que **ya existen** en `taxonomia.FENOMENOS` (no se agregan categorías nuevas sin
  pedirlo, porque tocar `taxonomia.py` también cambiaría el resultado de GIC). Los campos manuales parciales
  "Eje temático APLICA" / `CASO_GRUPO_ESPECIALIZADO` no se usan todavía.
- **Partes omitidas (con nota "No aplica"/"No disponible para esta fuente" en la interfaz, no un número
  inventado):** página 1, KPIs "Generan caso en especializadas" y "Días hasta cierre"; página 7, las
  secciones de probabilidad de generar caso, tiempo hasta el cierre (Kaplan-Meier) y la tabla de relatos
  abiertos. La composición esperada de fenómenos (también en la página 7) sí se calcula igual. La serie de
  alertas/pronósticos "por entidad remitente" tampoco existe en DECLA y se omite (sin sustituto).
- **Territorio:** usa `DEPARTAMENTO_HECHOS`/`MUNICIPIO_HECHOS` (columnas ya estructuradas) contra
  `divipola.py` por nombre — más simple y con mejor cobertura (≈98,6%) que el parseo de texto libre de GIC. No
  se usan `LAT_DIR_HECHOS`/`LONG_DIR_HECHOS` (coordenadas exactas del caso): quedan como posible mejora futura
  (mapa con el punto exacto en vez de la cabecera municipal), no implementada.
- **Hallazgo pendiente de decisión (no implementado):** ≈8,7% de los casos de DECLA son de falsificación o
  tráfico de moneda falsificada (`DELITO`/`CAPITULO`), categoría que no existe hoy en `taxonomia.FENOMENOS`;
  quedan sin fenómeno "registrado" (algunos sí salen por reglas sobre el relato). Es candidato a una futura
  categoría "Falsificación de moneda", pendiente de que el usuario lo pida (cambiaría también el resultado de
  GIC).

## 2. Cómo correr y verificar

```bash
pip install -r requirements.txt

# Fuente GIC (relatos de intake, data/GIC/*.xlsx) -> out/gic/ y reporte/dist/reporte_gic.html
python run.py --fuente gic --verificar      # debe decir: Las 22 tablas coinciden exactamente con el resultado publicado.

# Fuente DECLA (casos SPOA ya abiertos, data/DECLA/*.xlsx) -> out/decla/ y reporte/dist/reporte_decla.html
python run.py --fuente decla --verificar    # debe decir: Las 15 tablas coinciden exactamente con el resultado publicado.
```

`--fuente` por defecto es `gic` (compatibilidad con invocaciones antiguas). Cada fuente tiene su propia
carpeta de datos (`data/GIC/`, `data/DECLA/` — exactamente un `.xlsx` en cada una, o indique
`ARCHIVO_ENTRADA` en `.env`), su propia carpeta de salida (`out/gic/`, `out/decla/`) y su propio HTML
(`reporte/dist/reporte_gic.html`, `reporte/dist/reporte_decla.html`); no se pisan entre sí.

`run.py` ejecuta, en orden: pipeline → predicciones → `reporte/build_report.py <out> <dest> <fuente>`. Para
GIC: `pipeline/pipeline.py` → `pipeline/predicciones.py` (sin cambios respecto a antes de DECLA). Para DECLA:
`pipeline/pipeline_decla.py` → `pipeline/predicciones_decla.py` (ver subsección "DECLA" arriba). Cada script
recibe `<excel> <carpeta_out> <nombre_archivo>`. Los scripts de predicciones leen `hechos.json`,
`etiquetas.json` y `calidad.json` (GIC también `organizaciones.json`) del paso anterior. La verificación de
reproducibilidad de DECLA usa `tests/referencia_decla.json` (`tests/verificar.py <out> --ref <ruta>`), igual
mecanismo que la de GIC pero en otro archivo.

**Contrato de reproducibilidad:** con el mismo Excel, las 22 tablas de `out/gic/` deben coincidir con
`tests/referencia.json`, y las 15 de `out/decla/` con `tests/referencia_decla.json` (huella SHA-256 de las
filas, sin el campo `meta`). Para mantenerlo:
- No cambie semillas (`RNG = default_rng(20261118)`, `RNG_SUB = default_rng(777)` para series de subgrupo,
  `random_state=7`/`1` en validación cruzada) ni el orden de los bucles que consumen números aleatorios.
  `pipeline_decla.py`/`predicciones_decla.py` usan las mismas semillas, por consistencia.
- Los relatos se ordenan por `FechaIngreso`, `IdEntrada` (GIC) o `FECHA_CREACION`, `CASO_NOTICIA` (DECLA), orden
  estable en los scripts de cada fuente; `rid` es la posición 1..N en ese orden. No cambie eso o todo se
  desalinea.
- Las versiones de `requirements.txt` están fijadas a propósito.
- Si un cambio *debe* mover cifras, dígaselo al usuario con el valor anterior y el nuevo, y solo entonces
  regenere la referencia: `python tests/verificar.py out/gic --crear` (GIC) o
  `python tests/verificar.py out/decla --ref tests/referencia_decla.json --crear` (DECLA).

## 3. Datos y privacidad

- El Excel contiene nombres, cédulas y textos sensibles. **Ninguna tabla de `out/` incluye el texto de
  `ResumenHechos`, nombres ni documentos.** La única excepción acordada es `IdEntrada` en `pred_abiertos.json`
  (código interno para ubicar el caso), que el usuario puede pedir quitar.
- Los nombres de organizaciones criminales (Clan del Golfo, ELN, etc.) sí se muestran: son públicos.
- Calidad conocida de la base: sep-2024 y nov-2026 son meses parciales; jul-2025 (2 relatos) y ago-2025 (0) son un
  posible vacío de registro; sep-2025 se marca «posterior a vacío: posible rezago acumulado»; oct-2026 tiene solo 6
  relatos (posible carga incompleta).
- `DecisionFiscalUGIC = "SIN ESPECIFICAR"` se trata igual que vacío («Sin decisión registrada»).
- `LugarDeLosHechos` viene como «Municipio, Departamento, Colombia» (o «SIN DETERMINAR»). Un municipio solo se
  acepta si coincide con su departamento. Los municipios que no están en `divipola.py` cuentan para su departamento,
  pero no aparecen como punto en el mapa. Si el campo no sirve, se buscan municipios no ambiguos en el relato
  (origen extraído_regla, confianza 0,6).
- DECLA sigue la misma regla de privacidad: `pipeline_decla.py` no exporta el texto de `RELATO`, ni
  `NUMERO_DOCUMENTO` ni `FISCAL_ASIGNADO_DESPACHO` (presentes en el Excel pero nunca leídos hacia `out/`).

## 4. Decisiones de método (no cambiar sin pedirlo)

- **Taxonomía v1.0** (`taxonomia.py`): fenómenos, mecanismos de lavado, bienes, sectores CIIU por palabras clave y
  códigos CIIU explícitos (confianza 0,9), organizaciones. Confianza de regla = `min(0,9; 0,55 + 0,15·(aciertos−1))`.
- **Origen:** registrado (temática/delito SPOA, 1,0) > extraído_regla > extraído_modelo (TF-IDF + regresión
  logística por fenómeno, p ≥ 0,6, predicción fuera de muestra) > inferido (0,5–0,55). Si una etiqueta llega por
  varias vías, se conserva la más fuerte.
- **Sectores:** Fisher bilateral, OR con corrección de Haldane e IC95 de Woolf, BH sobre todos los pares
  (fenómenos con ≥10 relatos, sectores con ≥5). Mensaje: co-mención, no causalidad.
- **Red:** nodos con ≥4 relatos; aristas con ≥3 relatos y lift ≥1,2; comunidades por modularidad voraz; posiciones
  `spring_layout(seed=7)`.
- **Alertas:** línea base de 6 meses con 2 de guarda (≥4 meses válidos); umbral cuantil 99 % Poisson/NB; CUSUM
  k=0,5, h=4; tasa de falsas alarmas con 1.000 simulaciones bajo no cambio.
- **Pronósticos:** ingenuo (obligatorio), media móvil 6 meses, suavizado exponencial simple; intervalos 80/95 % por
  simulación con residuos y binomial negativa; validación con origen móvil (6 orígenes, horizontes 1–3, MAE y MASE).
  En la página, el método «auto» usa el de menor MAE. Series: total, 7 fenómenos principales, 4 departamentos y
  4 entidades.
- **Predicciones (sección 7, «otras predicciones»):** regresión logística con TF-IDF + campos de entrada, entrenada solo con relatos con
  decisión final (AUC ≈ 0,71 con texto, 0,67 sin texto); Kaplan–Meier por tipo de entrada con abiertos censurados;
  composición = últimos 12 meses completos vs. anteriores, IC de Wilson.
- **«Lavado de activos» como fenómeno residual (fusionado a la sección 2 el 2026-11-19, `taxonomia.py` +
  `pipeline.py`):** casi todos los relatos ya traen `DELITO`/`TematicaPriorizada` = «lavado de activos», así que esa
  etiqueta por sí sola no distingue casos. `FENOMENOS_LAVADO_EXTRA` (en `taxonomia.py`) son patrones de texto
  adicionales —antes vivían aparte, en lo que fue la sección «Fenómenos del lavado de activos»— que `pipeline.py`
  aplica **solo** a los relatos cuyo único fenómeno es «Lavado de activos», para intentar asignarles un fenómeno
  ya existente en `FENOMENOS` (p. ej. narcotráfico, corrupción, captación). Si encuentran algo, ese fenómeno se
  suma con origen `extraído_regla` y la etiqueta «Lavado de activos» se retira de ese relato (es la categoría
  residual: lo que no se pudo segregar). `hechos.json` guarda `es_lavado` (el conjunto completo, antes de esa
  poda) porque las vistas «por mecanismo»/«por sector» de la sección 2 deben seguir cubriendo a *todos* los
  relatos de lavado, no solo a los residuales (`reporte/src/calcs.js`, `fen_dist`). No se tocan `MECANISMOS`,
  `BIENES`, `SECTORES` ni `ORGANIZACIONES`. Efecto medido en la base publicada: de 513 relatos de lavado, 348
  quedaron con un fenómeno específico y 165 siguen como «Lavado de activos».
- **Variables del `.env`:** sus valores reemplazan a las variables de entorno del equipo con el mismo nombre.

## 5. La página (`reporte/src/`)

- Escrita para el tablero *Data* de Claude con la regla «un escritor por parte»: todo texto fijo va en
  `index.html`; lo que depende de los datos va en elementos `data-draw="nombre"` guardados vacíos o con «—», que
  llenan los scripts con `dash.draw(nombre, fn)`. Fuera de un dibujo, un script solo escucha eventos y cambia
  `class`, `style`, `hidden`, `value`, `aria-*`.
- Cada cifra lleva `data-source`/`data-field`/`data-row` (o `data-where`) para que el tablero muestre de dónde
  viene. Las tablas: `data-source` + `data-row-key` en `<table>` y `data-field` en cada `<th>`.
- Cálculos que dependen de filtros: `dash.calc(id, {inputs, fn})` en `calcs.js` y `pron.js`; cada `fn` es
  autocontenida (solo usa sus entradas, `d3` y `dash.params()`).
- Filtros globales: `desde`, `hasta` (mes), `dpto` (código DIVIPOLA). Aplican a las secciones 1, 2 y 8; la 3 solo
  usa el periodo; 4–7 se calcularon sobre el total.
- Identificadores de fuentes ↔ archivos: ver `FUENTES` en `reporte/build_report.py` (es el mismo mapeo del tablero).
- Estilo: textos en español de Colombia, números con coma decimal y punto de miles (`G.int`, `G.pct`, `G.d1`…), clases
  con prefijo `gic-`, colores de series de `dash.colors`. Gráficos con tooltip, líneas punto a punto, sin anchos
  fijos (ancho desde `clientWidth`).
- Pestañas: secciones `<section data-sec>` con `hidden`; para imprimir se muestran todas.
- Para probar: `python run.py --fuente gic` / `--fuente decla` y luego
  `node tests/probar_reporte.mjs reporte/dist/reporte_gic.html` (0 errores, ningún «—» sin llenar) y
  `node tests/probar_reporte.mjs reporte/dist/reporte_decla.html` (0 errores; "No aplica"/"No disponible para
  esta fuente" son el resultado esperado en las piezas documentadas como omitidas para DECLA, no un «—»).
- Fuente de datos por fuente: `index.html`/`common.js`/`calcs.js`/`p1.js` leen `dash.params().fuente`
  (`"gic"`/`"decla"`) para mostrar/ocultar el selector "Fecha base", las opciones de "Otra dimensión", las
  notas de "Fuente, método y limitaciones" y los KPIs que no aplican a DECLA. `build_report.py` es quien
  calcula `fuente` y la lista `faltantes` (fuentes de `FUENTES` sin archivo para esa corrida); `dash_shim.js`
  usa `faltantes` para devolver `status:'missing'` en vez de lanzar un error.

## 6. Reglas de trabajo para editar

1. Apéguese al plan y a lo que el usuario pide; no cambie parámetros, gráficos ni textos que no se pidieron.
2. Antes de afirmar una cifra, calcúlela desde `out/` o el Excel; nunca la estime de memoria.
3. Después de cualquier cambio: `python run.py --verificar` y la prueba del HTML. Si alguna cifra cambia, reporte
   al usuario cuál, el valor anterior y el nuevo.
4. Mantenga visibles las advertencias: actividad registrada ≠ incidencia; señales ≠ alarmas; pronósticos con poca
   historia; asociaciones ≠ causalidad; una mención de organización no prueba pertenencia.
5. Lenguaje para usuarios no técnicos: explique qué se mide y cómo leerlo («8 de cada 10 veces», «error promedio en
   relatos por mes») antes que siglas (MAE, AUC).
6. No exporte texto de relatos ni datos personales a `out/` ni al HTML. No ponga secretos en el código: van en `.env`.
7. Si un cambio de datos deja obsoletos los textos fijos (README, «Textos fijos que dependen de los datos»), actualícelos.
8. Sea honesto con las limitaciones: si un método probado no aporta, dígalo en el reporte en vez de ocultarlo.
