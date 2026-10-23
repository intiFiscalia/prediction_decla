---
description: I3 — Análisis relacional y territorial completo (Fase 7), emergencia (Fase 8) y aplicación de consulta (Fase 11)
---

# I3 — Asociaciones, territorio, fenómenos emergentes y aplicación local

Notas adicionales de la persona: $ARGUMENTS

## Contexto
Lee `CLAUDE.md`, el cierre de I2 (taxonomía v1.0 y categorías habilitadas) y `docs/plan_trabajo.md`
§8.1–8.5, Fases 7, 8 y 11. Solo usa fenómenos y categorías de menciones **aprobados** en I2.

## Primero: plan
Modo plan; tareas con criterios; espera aprobación.

## Tareas
1. **Indicadores de fenómenos y sectores** (completa §8.1): noticias por fenómeno (conteo y ajustado),
   participación, % no clasificado; sectores explícitos, inferidos de alta confianza e indeterminados
   **en columnas separadas**. Fichas YAML para cada indicador nuevo.
2. **Territorio** (§8.2): fenómeno predominante por departamento/municipio con prueba frente al
   segundo y tamaño mínimo; cociente de localización con intervalo; perfiles territoriales (distancia
   de Hellinger + agrupamiento) para separar patrones comunes y específicos; Moran I y LISA solo si la
   cobertura municipal lo permite (decide con datos y documenta); análisis de puntos solo con
   `calidad_coord` válida, informando la fracción excluida; matriz y mapa de flujos unidad↔hechos.
3. **Asociaciones** (§8.3, tabla de métodos): implementa cada fila con su condición de uso verificada
   en código (frecuencias esperadas, soporte mínimo) y salida estándar en `oro.asociaciones`:
   variables, método, estadístico, tamaño de efecto, IC 95 %, p, p ajustado BH, n, advertencias,
   y texto de interpretación generado con plantilla que distinga asociación, relación temporal,
   coincidencia territorial y causalidad. Incluye ACM (prince), reglas de asociación (mlxtend) con
   filtrado de redundancia, Poisson/binomial negativa con efectos fijos y offset de volumen, red de
   co-ocurrencia de menciones (PMI + Louvain) excluyendo negadas, y grafo de conexidad si I0 confirmó
   cómo se identifican los conexos. **Ninguna red de personas.**
4. **Emergencia** (§8.5) en `src/decla/emergencia/`:
   - Línea base por serie fenómeno × territorio agregado × periodo: Poisson/NB con tendencia,
     estacionalidad (si hay ≥ 2 años) y offset del total del territorio.
   - Detectores: CUSUM sobre residuos, EARS C1–C3, Farrington flexible (implementación propia en
     Python, documentada), razón de tasas reciente vs. base, puntos de cambio (ruptures).
   - Novedad combinatoria (nuevas combinaciones o lift creciente con soporte mínimo) y novedad semántica
     (relatos lejanos a todos los centroides que forman grupo denso; términos con log-likelihood
     anómalo; divergencia Jensen-Shannon del vocabulario por fenómeno; deriva de centroides).
   - Filtro de artefactos: concentración en una unidad/despacho, un día de carga, casi-duplicados o
     cambio de catálogo → etiqueta "posible artefacto de registro".
   - Reglas de declaración en `config/umbrales.yaml`: FDR ≤ 10 %, persistencia ≥ 2–3 periodos, tamaño
     mínimo absoluto, > 1 unidad registradora, validación humana. Estados: candidato en observación,
     alerta, confirmada, descartada (con motivo).
   - Rezago de registro: marca los últimos periodos como provisionales o corrige con nowcasting simple
     (estimado a partir de la distribución histórica de rezagos registro−hecho).
   - **Retroprueba** sobre la historia disponible y sobre fixtures con incrementos plantados: tasa de
     falsas alarmas por fenómeno y año, tiempo a detección, sensibilidad.
5. **Aplicación Streamlit local** (`src/decla/app/`, `make app`), base DuckDB en solo lectura:
   - Autenticación (streamlit-authenticator o cabecera del proxy institucional) y roles: consulta,
     analista, revisor, administrador; bitácora de accesos y exportes en `meta.accesos`.
   - Páginas: Indicadores · Fenómenos (ficha, evolución, relatos representativos enmascarados) ·
     Territorio (mapas, comparación de territorios, flujos) · Asociaciones · Emergencia (alertas y
     cola de revisión) · Buscador semántico · Calidad de datos · Cola de revisión (alertas, grupos
     nuevos, sectores inferidos, atípicos) que escribe en `revision.*`.
   - Filtros globales: periodo, fecha de referencia, departamento, municipio, delito, fenómeno,
     versión de taxonomía. Drill-down indicador → relatos.
   - Cada vista muestra etiqueta de nivel de verdad, fecha de corte, versiones y la nota "actividad
     registrada". Texto de relato solo enmascarado; texto original solo para rol autorizado y con
     registro en bitácora.
   - Exportes CSV/Excel/PDF con marca de versión, `run_id`, advertencias y supresión < 5 cuando el
     rol no es analista.
6. Pruebas: métodos estadísticos contra resultados conocidos (tablas de libro o simulaciones),
   retroprueba reproducible, pruebas de la app (que las vistas no expongan texto sin enmascarar).

## Entregables
`make analitica`, `make emergencia`, `make app`; tablas `oro.*`; informe de retroprueba; manual de
uso de la app (`docs/manual_app.md`); `docs/informes/I3_cierre.md`.

## Criterios de aceptación (compuerta I3)
- Asociaciones con tamaño de efecto, IC y p ajustado; ninguna afirmación causal en textos generados.
- Tasa de falsas alarmas de la retroprueba aceptada por analistas; un ciclo completo
  alerta → revisión → decisión registrado.
- Analistas completan sin ayuda tareas de prueba (p. ej., "fenómeno predominante en un departamento
  en un periodo y tres relatos ejemplo") y los accesos quedan auditados.
