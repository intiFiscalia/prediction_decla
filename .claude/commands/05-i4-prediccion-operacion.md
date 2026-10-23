---
description: I4 — Modelos predictivos (Fase 9), evaluación consolidada (Fase 10) y operación continua (Fase 12)
---

# I4 — Predicción, evaluación y operación

Notas adicionales de la persona: $ARGUMENTS

## Contexto
Lee `CLAUDE.md`, los cierres de I0–I3 y `docs/plan_trabajo.md` §8.4, §9, Fases 9, 10 y 12.
La muestra inicial cubría solo 2026; **antes de construir pronósticos verifica viabilidad** con el
diagnóstico de I0 (meses con datos, estabilidad del registro, conteos por celda).

## Primero: viabilidad y plan
1. Genera `reports/agregados/i4/viabilidad.md`: para cada problema de la tabla §8.4 (frecuencia por
   fenómeno, cambio por territorio, incrementos tempranos, clasificación temática, atípicos), indica
   meses de historia, conteo medio por celda, cambios estructurales detectados, etiquetas disponibles y
   veredicto: viable / viable solo a nivel agregado / no viable (con qué falta).
2. Modo plan solo con los problemas viables; espera aprobación.

## Tareas
1. **Preparación de variables con corte temporal estricto**: las variables de cada punto de predicción
   usan solo registros con **fecha de registro** anterior al corte; taxonomía, parámetros de
   normalización y vectorizadores se congelan antes del periodo de evaluación; últimos periodos con
   rezago se excluyen o se corrigen (nowcasting de I3). Prueba automática anti-fuga.
2. **Pronóstico de frecuencia** (si es viable): modelos ingenuos (último valor, media estacional) como
   referencia obligatoria; ETS, Poisson/NB con estacionalidad, SARIMAX; StatsForecast para muchas
   series; HierarchicalForecast para reconciliar municipio→departamento→nacional. Validación rolling
   origin con ≥ 6 orígenes; MASE, WAPE y cobertura de intervalos 80/95 %. Tabla `oro.pronosticos` con
   intervalos, modelo, versión, fecha de corte.
3. **Clasificación temática**: consolida el clasificador de I2 con partición temporal, calibración
   (curva y ECE), F1 por clase, umbral de "no clasificado" y aprendizaje activo para nuevas etiquetas.
4. **Atípicos**: Isolation Forest/LOF sobre variables estructuradas + distancia a centroides en
   embeddings; top-k por lote a la cola de revisión; precisión@k según analistas. Uso declarado:
   calidad de datos y casos inusuales, **nunca** señal de responsabilidad.
5. **Registro de modelos**: MLflow local (o registro propio en DuckDB si MLflow no se aprueba);
   ficha de modelo por versión en `docs/fichas/modelos/` (propósito, datos, métricas, limitaciones,
   usos no permitidos, responsable).
6. **Evaluación consolidada** (Fase 10, tabla §9): `make evaluar` produce
   `reports/agregados/evaluacion/<version>.md` con todas las métricas de todos los componentes,
   comparadas con los umbrales de `config/umbrales.yaml`, y errores estratificados por año,
   departamento y unidad para detectar sesgos.
7. **Operación** (Fase 12):
   - `make lote ARCHIVO=...`: valida esquema y perfil del lote frente al histórico, detecta registros
     nuevos, modificados (cambio de ESTADO/ETAPA/ULTIMA_ACTUACION) y repetidos por llave y hash,
     guarda historia de cambios (dimensión lentamente cambiante tipo 2), recalcula solo lo dependiente.
   - Monitoreo de deriva de datos y predicciones (PSI, KS, distancia entre distribuciones de embeddings;
     Evidently local si se aprueba) con umbrales que disparan revisión o reentrenamiento.
   - Champion/challenger para modelos.
   - Ciclo trimestral de revisión de taxonomía; versionado semántico (v1.x cambios menores, v2.0 cambio
     de significado) con tabla de equivalencias para mantener comparables las series.
   - Respaldo cifrado y prueba de restauración documentada.
   - Si las ejecuciones programadas lo justifican, ADR para Prefect o Dagster con servidor local y
     telemetría desactivada; si no, cron + Makefile.
   - Tablero "salud del sistema" en la app (último lote, calidad, deriva, métricas, alertas abiertas).
8. **Documentación final**: `docs/manual_operacion.md` (ingesta de lotes, recuperación ante fallos,
   rotación de claves de seudonimización, gestión de roles), notas de versión.

## Criterios de aceptación (compuerta I4)
- Cada modelo en uso supera al ingenuo en ≥ 2 orígenes y sus intervalos tienen cobertura empírica
  cercana a la nominal; los no viables quedan documentados como tales, sin implementarse.
- Todos los componentes en uso tienen métricas publicadas y umbrales acordados.
- Tres lotes consecutivos procesados sin intervención manual fuera de la revisión prevista.

## No hagas
No predigas nada sobre personas, empresas, despachos o funcionarios. No predigas ESTADO/ETAPA de un caso
salvo aprobación expresa y fechas de transición fiables. No uses particiones aleatorias.
