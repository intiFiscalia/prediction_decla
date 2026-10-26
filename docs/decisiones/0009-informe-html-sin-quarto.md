# 0009 — Informe reproducible de I1: Python/HTML en vez de Quarto

- **Fecha:** 2026-10-26
- **Estado:** aceptada

## Contexto

plan_trabajo.md (Fase 11) permite "Quarto o Jupyter" para el primer informe reproducible.
`quarto` no está instalado en esta máquina (no existe en PATH) y CLAUDE.md §3.1 lista Quarto
como parte de la pila decidida para informes, pero no exige que sea el único mecanismo desde
el primer incremento.

## Opciones consideradas

1. **Instalar Quarto** (vía Homebrew) y escribir `.qmd` que se renderizan a HTML.
2. **Python puro**, reutilizando el patrón ya validado en `decla.calidad.diagnostico` (I0):
   matplotlib para gráficos/mapas + ensamblado manual de HTML, sin motor de renderizado nuevo.

## Decisión

Para I1, **Python puro** (`decla.analitica.descriptiva::ejecutar_informe`): genera
`informe.html` ensamblando las tablas de los indicadores (vía pandas `to_html`) y las imágenes
de los mapas (matplotlib), igual que ya hace `decla.calidad.diagnostico` para el informe de I0.
No se instala Quarto todavía.

## Consecuencias

- `make informe` hoy ejecuta lo mismo que `make analitica-descriptiva` (ver comentario en el
  `Makefile`): no hay una etapa de "solo renderizar" separada de "calcular". Si en un
  incremento futuro el cálculo se vuelve costoso, se separa cálculo (escribe CSVs/Parquet) de
  render (lee esos archivos y ensambla HTML) sin tocar la lógica de los indicadores.
- Migrar a Quarto más adelante (p. ej. para informes narrativos de I2+ con texto interpretativo
  junto a gráficos) es compatible: los CSVs que ya se exportan a `reports/i1/` servirían de
  insumo a un `.qmd`, sin recalcular nada.
- Si se decide instalar Quarto, debe desactivarse su telemetría (CLAUDE.md §2.2), igual que se
  hizo con Streamlit en el ADR 0001.
