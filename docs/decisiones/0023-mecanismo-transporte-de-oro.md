# 0023 — Código explícito `transporte_de_oro` para mecanismo

- **Fecha:** 2026-11-13
- **Estado:** aceptada

## Contexto

Siguiendo el mismo patrón de ADR 0022 (`transporte_de_divisas`), la persona identificó un
fenómeno análogo pero en especie distinta: personas capturadas transportando grandes
cantidades de oro sin poder acreditar documentalmente su origen. Es distinto de
`transporte_de_divisas` (moneda/efectivo en pesos o divisas) y de `mineria_ilegal_oro` (no hay
extracción ni explotación, solo transporte de oro ya obtenido sin trazabilidad).

## Decisión

1. Nuevo código `transporte_de_oro` en `config/categorias_menciones.yaml` (categoría
   `mecanismo`), con definición en prosa para el zero-shot.
2. Expresiones literales añadidas a `config/diccionarios/mecanismos_expresiones.yaml` (capa
   explícita, ADR 0018): "transporte de oro", "transportando oro", "sin justificar el origen
   del oro", "sin acreditar el origen del oro" — semilla inicial sin validar contra una muestra
   real, igual que el resto del diccionario.
3. Nombre legible agregado a `MECANISMOS` en `src/decla/app/legibilidad.py`.

## Consecuencias

- `tests/unit/test_zero_shot.py` pasa de esperar 14 a 15 códigos en el vocabulario de
  mecanismo.
- `tests/fixtures/verdad.parquet` **no tiene** todavía narrativas sintéticas plantadas para
  este código (igual que `lavado_activos_sin_detalle` y `transporte_de_divisas`): no es
  necesario para que el código funcione, solo para evaluar recall con verdad de terreno
  sintética.
- Las expresiones literales nuevas no están validadas contra el corpus real; revisar y ampliar
  tras la próxima ronda de anotación.
- `ind_mecanismo` (ya exportado en `make analitica` desde la corrección de esta misma sesión)
  mostrará `transporte_de_oro` como código separado una vez el modelo lo asigne.
