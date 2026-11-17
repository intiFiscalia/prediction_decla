# 0029 — Candidato de fenómeno no listado (LLM) y robustez adicional de parseo

- **Fecha:** 2026-11-17
- **Estado:** aceptada

## Contexto

Al correr `make clasificar-fenomenos-llm` sobre los 346 relatos reales (ADR 0027), aparecieron
dos problemas reales que ADR 0026/0027/0028 no cubrían:

1. **El modelo intentaba forzar códigos que no aplican.** Un relato describía un hallazgo de
   esmeraldas sin documentación de legalidad de transporte/comercialización. El modelo dudó entre
   `incautacion_y_conteo_de_efectivo` (que es específicamente dinero en efectivo, no piedras
   preciosas) y dejarlo sin clasificar, y terminó devolviendo dos intentos de JSON en la misma
   respuesta. La persona confirmó: esto no debe forzarse en un código existente ni ampliar el
   significado de `incautacion_y_conteo_de_efectivo` — debe quedar como candidato nuevo, igual
   criterio que mecanismos/fenómenos nuevos (ADR 0020/0024), y el relato queda `no_clasificado`
   hoy (resultado legítimo, no un error).
2. **Fallos de parseo adicionales encontrados en la corrida real:** el modelo escribió
   `"confida"` en vez de `"confianza"` en al menos un caso — un nombre de llave mal escrito que
   tumbaba todo el relato (incluyendo el `codigos` que sí se había parseado bien).

## Decisión

1. **Campo abierto `fenomeno_no_listado`** en el prompt y en `ResultadoClasificacionLLM`: si el
   relato describe algo relevante para lavado de activos que no encaja en los 3 códigos de la
   taxonomía congelada, el LLM lo describe en una frase corta en vez de forzar el código "más
   parecido". El prompt incluye el caso de las esmeraldas como ejemplo explícito de qué NO hacer
   (forzarlo en `incautacion_y_conteo_de_efectivo`).
2. **Mismo patrón de gobernanza que organización mencionada (ADR 0028) y mecanismos/fenómenos
   nuevos (ADR 0020/0024):** `fenomenos.fenomeno_no_listado_modelo` (registro_uid, texto_crudo,
   confianza, origen, version_modelo, run_id) guarda el texto crudo. `make
   resumen-fenomenos-no-listados` cuenta relatos distintos por texto y escribe
   `reports/agregados/i4/candidatos_fenomeno_no_listado.csv` — reporte de candidatos, nunca un
   código nuevo automático. Formalizar un código (p. ej. "incautación de bienes de alto valor
   distintos a efectivo") es un taller de revisión humana, no una decisión de esta ADR.
3. **`confianza` ausente o con nombre de llave distinto ya no descarta todo el relato.**
   `clasificador_llm.parsear_respuesta_llm` usa `0.0` (el valor más cauteloso) cuando la llave
   `confianza` falta, y conserva `codigos`/`evidencia` que sí se parsearon bien. Un valor
   *presente* pero inválido o fuera de rango `[0,1]` sigue siendo un fallo real (se rechaza, se
   reintenta en la siguiente corrida incremental) — la tolerancia es solo para la llave ausente,
   no para un valor realmente corrupto.
4. **Refactor de apoyo:** `tabla_existe` (antes `_tabla_existe`, privada y duplicada) se movió a
   `decla.comun.duckdb_io` como utilidad compartida; `_escribir_fila_opcional` en
   `pipeline_clasificador_llm.py` evita repetir el patrón "reemplazar solo la primera vez,
   agregar después" en las tres tablas secundarias (organización, fenómeno no listado).

## Consecuencias

- `ejecutar_clasificacion_llm` devuelve ahora `(version_modelo, n_ok, n_filas, n_organizaciones,
  n_no_listados, registros_fallidos)` — quien lea el valor de retorno en código futuro debe
  actualizar la firma.
- El reporte de candidatos de fenómeno no listado es, junto con el de organizaciones (ADR 0028),
  la señal principal para que la persona decida futuras ampliaciones de la taxonomía — con
  evidencia real del corpus, no por adelantado.
- Estos arreglos se descubrieron corriendo sobre datos reales, no en pruebas sintéticas —
  consistente con el patrón del proyecto de calibrar con evidencia real cuando aparece, sin
  inventar casos hipotéticos de antemano.
