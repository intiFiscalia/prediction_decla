# 0025 — Cómo las predicciones del clasificador de fenómenos llegan al dashboard

- **Fecha:** 2026-11-17
- **Estado:** aceptada

## Contexto

ADR 0024 construyó la herramienta de anotación, el clasificador y su entrenamiento, pero dejó
las predicciones en una tabla nueva (`fenomenos.asignacion_fenomeno_modelo`), separada
deliberadamente de `fenomenos.asignacion_fenomeno` (la que ya leen `decla.analitica.indicadores`,
`decla.analitica.asociaciones`, `decla.prediccion.atipicos` y la app de consulta). Entrenar el
modelo no hacía que esos reportes cambiaran — faltaba decidir cómo se conectan.

La persona pidió una guía de punto a punto para que, una vez anotado y entrenado, el resto sea
"cargar datos, usar comandos, ver el dashboard" — sin pasos manuales de ingeniería pendientes.

## Decisión

1. **`fenomenos.asignacion_fenomeno` ya se reconstruye desde cero en cada `make analitica`**
   (`decla.fenomenos.asignacion.construir_asignacion_fenomeno`, `modo="reemplazar"`): no es una
   capa protegida tipo bronce/plata, es un derivado que ya se recalcula por diseño. Por eso
   agregar las filas del modelo ahí no viola CLAUDE.md §2.4 ("ninguna capa modifica la
   anterior") — es la tabla correcta para que indicadores/asociaciones/atípicos/app las vean sin
   tocar código de esas cuatro partes.
2. **Promoción explícita y separada** (`scripts/promover_clasificador_fenomenos.py`, `make
   promover-clasificador-fenomenos VERSION_MODELO=<...>`): copia (`INSERT`, nunca reemplaza) las
   filas de una `version_modelo` específica hacia `fenomenos.asignacion_fenomeno`, con
   `metodo_origen="clasificador_fenomenos:<version_modelo>"` y `probabilidad` igual a la
   confianza real del modelo (ya no fija en 1.0 — cierra el comentario pendiente en
   `asignacion.py` y `indicadores.ind_fenomenos`: "eso es Fase 9/I4"). Exige `--confirmar`: la
   persona revisa antes `reports/agregados/i4/clasificador_fenomenos_metricas.md` (F1/precisión/
   exhaustividad por código, partición temporal) y decide código por código si promueve.
3. **Solo se promueven códigos de la taxonomía congelada** (`lavado_de_activos_a_traves_de_
   empresas`, `incautacion_y_conteo_de_efectivo`, `organizacion_criminal`). `ruido_administrativo`
   y `no_clasificado` son clases de la herramienta de anotación, no fenómenos — nunca entran a
   `fenomenos.asignacion_fenomeno` (contaminarían conteos, asociaciones y centroides de
   atípicos con una clase que no es un fenómeno de lavado de activos).
4. **Orden obligatorio**: `make analitica` reconstruye la tabla desde cero cada vez que corre, así
   que `make promover-clasificador-fenomenos` va DESPUÉS de `make analitica` y ANTES de `make
   emergencia`/`make prediccion`/`make app`, cada vez. Si se repite `make analitica` después de
   promover, hay que promover de nuevo — es manual a propósito, para que nunca se promueva una
   versión de modelo sin que alguien lo decida en esa corrida específica.
5. **Multi-método, no reemplazo**: un relato puede terminar con `codigo_fenomeno` repetido desde
   clustering (HDBSCAN/NMF, `probabilidad=1.0`) y desde el modelo (`probabilidad` real) —
   consistente con el patrón ya documentado en `asignacion.py` de que un mismo relato puede caer
   bajo más de un método. Los indicadores ya toleran esto (cuentan por `codigo_fenomeno`, no
   asumen una sola fuente).

## Consecuencias

- `docs/manual_operacion.md` documenta la secuencia completa, de datos nuevos a dashboard.
- `indicadores.ind_fenomenos` deja de ser exacto en su comentario "probabilidad hoy es 1.0"
  después de la primera promoción — se corrige el docstring en esta misma ADR.
- Si en el futuro se decide que el modelo debe *reemplazar* (no sumarse a) la membresía de
  clustering para los fenómenos que ya tiene buena cobertura, eso es una decisión nueva —
  esta ADR no la toma por adelantado.
