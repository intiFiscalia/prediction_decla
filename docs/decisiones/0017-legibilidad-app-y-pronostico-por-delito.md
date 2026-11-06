# 0017 — Legibilidad de la app para usuario inexperto y pronóstico por delito (no por fenómeno)

- **Fecha:** 2026-11-06
- **Estado:** aceptada

## Contexto

La persona (usuaria sin formación técnica) reportó que la app era ilegible — códigos DIVIPOLA,
nombres de columna técnicos (`articulo_cp`, `pct`, `n`, `periodo` como entero) — y, más de fondo,
que casi todos los resultados (fenómeno predominante por departamento, tendencia futura) son
triviales porque **todo el dataset es, por alcance, lavado de activos** (CLAUDE.md §5.2): decir
"predomina el lavado de activos" no aporta nada. Lo que interesa es **qué tipo** de lavado — qué
delito tipificado, en qué sector económico, con qué tendencia — no que el fenómeno amplio se
repita.

La persona autorizó explícitamente, vía pregunta con opciones, la vía **rápida**: cruzar con
`delito_nombre`/sector ya extraídos en plata/conocimiento, en vez de reabrir el clustering de
fenómenos (taxonomía v1.0 congelada, ADR 0013/0014) con un nuevo taller de revisión humana. Para
la descripción de "cómo opera" cada fenómeno (campo `definicion` de la taxonomía, hoy
`pendiente_de_redaccion_por_analista` en los 4 fenómenos), autorizó mostrar **patrones
observados en los datos** (términos dominantes del clustering + delito/sector más frecuente)
explícitamente etiquetados como tal, no como una definición jurídica de modus operandi — eso
sigue pendiente de redacción y aprobación por un analista, CLAUDE.md §4.5 ("si falta una decisión
jurídica, no la inventes").

## Decisión

1. **Capa de presentación nueva** (`src/decla/app/legibilidad.py`): nombres DIVIPOLA en vez de
   códigos, nombres de fenómeno en vez de código, traducción de reglas de asociación y términos
   de fórmula GLM, decodificación de `indice_periodo` (bug real: se mostraba como `24321` en vez
   de `2026-09`), tooltips (`st.column_config.Column(help=...)`) y un glosario por página. No
   cambia ningún cálculo — capa puramente de presentación (CLAUDE.md, "ninguna capa modifica la
   anterior").
2. **Gráficos Plotly** (ya en el stack aprobado) en las tablas de ranking de cada página:
   barras horizontales ordenadas de mayor a menor, recortadas a 15 categorías.
3. **Todas las tablas de predominio/ranking se ordenan explícitamente de mayor a menor
   relevancia** (antes dependía del orden de iteración interno, no garantizado).
4. **Nuevo pronóstico por `delito_nombre`×territorio** (`oro.pronosticos_delito`,
   `decla.emergencia.linea_base.construir_series_delito_territorio`,
   `decla.prediccion.orquestador.procesar_pronosticos_delito`), además del existente por
   `codigo_fenomeno`×territorio (que se conserva sin cambios, sigue alimentando
   `decla.emergencia` vía `construir_series_fenomeno_territorio`). Mismo pipeline estadístico
   (ingenuo/ETS/Poisson-NB con tendencia, ADR 0016), corrido por `make prediccion`.
5. **Ranking de "delito en tendencia"** (`decla.analitica.indicadores.ranking_tendencia_delito`):
   compara, por delito×territorio, el método con tendencia que superó el pronóstico ingenuo en
   el backtest (`supera_ingenuo`) contra el propio ingenuo, en el horizonte más lejano
   disponible. Si ningún método supera el ingenuo para una serie, no se reporta nada — no hay
   evidencia de tendencia real distinta del ruido (CLAUDE.md, "no inventes cifras").
6. **"Sector económico predominante" por departamento**
   (`decla.analitica.territorio.predominio_sector_territorial`), con la misma prueba binomial
   frente al segundo sector que ya usa `predominio_territorial`/`predominio_delito_dentro_de_fenomeno`.
7. **Nueva página "Pronósticos"** en la app: ranking de delito en tendencia + gráfico de barras,
   y serie histórica + pronóstico (con banda de intervalo 80%) seleccionable por delito y
   departamento.
8. **"Patrones observados en los datos"** reemplaza la línea de "Definición: pendiente..." en
   cada fenómeno de la página Fenómenos: términos dominantes del clustering + delito/sector más
   frecuente dentro de ese fenómeno, con una advertencia explícita de que no es una definición
   jurídica.

## Consecuencias

- No se reabrió el clustering de fenómenos ni la taxonomía v1.0 congelada — el campo
  `definicion` de cada fenómeno sigue `pendiente_de_redaccion_por_analista`; queda como pendiente
  abierto (§6 de CLAUDE.md) hasta que un analista lo redacte y apruebe.
- `make prediccion` ahora escribe dos tablas (`oro.pronosticos` y `oro.pronosticos_delito`) en
  vez de una; no afecta `oro.atipicos` ni `decla.emergencia` (que sigue leyendo
  `construir_series_fenomeno_territorio`, sin cambios).
- Mismas limitaciones de ADR 0016 (historia <12 meses, sin estacionalidad, intervalos anchos)
  aplican igual de fuerte al pronóstico por delito: con menos relatos por delito que por
  fenómeno, varias series de `oro.pronosticos_delito` pueden no alcanzar el mínimo de 4 periodos
  y no calcularse — se reporta como tal, no se fuerza un ajuste.
