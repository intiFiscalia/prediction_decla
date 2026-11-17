# 0022 — Código explícito `transporte_de_divisas` para mecanismo

- **Fecha:** 2026-11-13
- **Estado:** aceptada

## Contexto

Durante la anotación manual con `app_anotacion_menciones.py` (ADR 0019/0020), la persona
identificó un fenómeno recurrente que no encaja en ninguno de los 13 códigos existentes:
personas capturadas transportando grandes cantidades de dinero en efectivo sin poder acreditar
documentalmente el origen de esos recursos. Es distinto de `fraccionamiento_consignaciones`
(no hay consignaciones bancarias fraccionadas, sino dinero físico en tránsito) y de
`giros_casas_cambio` (no hay giro ni casa de cambio involucrados).

## Decisión

1. Nuevo código `transporte_de_divisas` en `config/categorias_menciones.yaml` (categoría
   `mecanismo`), con definición en prosa para el zero-shot.
2. Expresiones literales añadidas a `config/diccionarios/mecanismos_expresiones.yaml` (capa
   explícita, ADR 0018): "transporte de dinero en efectivo", "transportando dinero en
   efectivo", "sin justificar el origen del dinero", "sin acreditar el origen de los
   recursos" — semilla inicial sin validar contra una muestra real, igual que el resto del
   diccionario.
3. Nombre legible agregado a `MECANISMOS` en `src/decla/app/legibilidad.py`.

## Consecuencias

- `tests/unit/test_zero_shot.py` pasa de esperar 13 a 14 códigos en el vocabulario de
  mecanismo.
- `tests/fixtures/verdad.parquet` **no tiene** todavía narrativas sintéticas plantadas para
  este código (igual que `lavado_activos_sin_detalle`, ADR 0021): no es necesario para que el
  código funcione, solo para evaluar recall con verdad de terreno sintética.
- Las expresiones literales nuevas no están validadas contra el corpus real; revisar y ampliar
  tras la próxima ronda de anotación.
