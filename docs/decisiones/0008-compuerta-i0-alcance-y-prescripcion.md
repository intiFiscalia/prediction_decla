# 0008 — Compuerta I0: alcance temático y tratamiento de la regla de prescripción

- **Fecha:** 2026-10-23
- **Estado:** aceptada

## Contexto

`make diagnostico` corrió sobre las 978 filas reales de `data/raw/` (2026-10-23). Dos hallazgos
exigían una decisión de la persona en la compuerta de I0, documentada aquí (la decisión de unidad
de análisis queda en el ADR 0002):

1. `SECC_DESCRIPCION` tiene dos secciones reales, no solo DECLA/lavado de activos como sugería la
   muestra de ejemplo: "Dirección Especializada contra los Delitos Fiscales" (627 filas, 64 %) y
   "Dirección Especializada contra el Lavado de Activos" (347 filas, 35 %).
2. La regla "`CASO_FECHA_PRESCRIPCION` = `FECHA_HECHO` + 20 años" (CLAUDE.md §4.13, confirmada
   solo en la muestra pequeña) no se sostiene a escala completa: solo 19.12 % de los 774 casos
   comparables la cumple exactamente, con una desviación mediana de −4018 días (~11 años antes de
   lo esperado) — consistente con que el plazo de prescripción varía por artículo del Código
   Penal, no con un defecto de datos.

## Opciones consideradas

**Alcance temático:**
- (a) Mantener ambas secciones dentro del alcance.
- (b) Limitar el alcance a "Lavado de Activos" (347 filas).
- (c) Diferir la decisión a un responsable institucional.

**Regla de prescripción:**
- (a) Reportar la distribución observada, sin usarla como regla de validación dura en I1.
- (b) Consultar primero a la oficina jurídica el plazo real por artículo antes de construir nada
  relacionado con prescripción.

## Decisión

1. **Alcance: limitar a "Dirección Especializada contra el Lavado de Activos"** (347 de 978
   filas observadas). Las 627 filas de "Delitos Fiscales" quedan **fuera de esta herramienta**.
2. **Prescripción: tratamiento informativo, no normativo.** I1 reporta la distribución de
   `CASO_FECHA_PRESCRIPCION` vs. `FECHA_HECHO` (y por artículo, cuando se separe `DELITO`) como
   indicador descriptivo; no se usa "hecho + 20 años" (ni ningún otro plazo fijo) como regla de
   validación de calidad ni como criterio para filtrar o alertar.

## Consecuencias

- **El filtro de alcance se aplica en la capa de plata/entidades de I1, no en bronce**
  (CLAUDE.md §2.4: "ninguna capa modifica la anterior"; bronce sigue conservando el 100 % de lo
  que llegó en `data/raw/`, incluidas las filas de Delitos Fiscales). El filtro es una regla
  versionada en `config/` (pendiente de crear en I1, p. ej. `config/alcance_tematico.yaml`), no una
  condición oculta en el código.
- El `reporte_calidad` de I1 debe declarar explícitamente cuántas filas se excluyeron por el
  filtro de alcance y por qué, para que nunca parezca una pérdida de datos silenciosa.
- Si más adelante se decide incluir Delitos Fiscales, no hace falta reprocesar bronce: solo
  cambiar la regla de alcance y recalcular plata en adelante.
- Ningún indicador, informe o alerta de este proyecto puede presentar un caso como "prescrito" o
  "vigente" basándose en una regla de fecha fija; cualquier análisis de prescripción real requiere
  el artículo específico y, probablemente, confirmación jurídica (pregunta abierta en CLAUDE.md
  §6).
