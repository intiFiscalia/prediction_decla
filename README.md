# decla — Analítica local de fenómenos asociados al lavado de activos

Herramienta local, reproducible y trazable para la Dirección Especializada contra el Lavado de
Activos (DECLA). Ver `CLAUDE.md` (reglas del proyecto) y `docs/plan_trabajo.md` (plan de ingeniería
aprobado, fuente de verdad del alcance).

Este repositorio se construye por incrementos (`/00-arranque`, `/01-i0-diagnostico`, ...). Ningún
dato real se versiona ni lo procesa Claude Code directamente: `data/raw/` y `data/private/` están
bloqueados; el desarrollo usa fixtures sintéticos en `tests/fixtures/`.

## Arranque rápido
```
make instalar   # instala dependencias desde wheelhouse/ (sin red)
make fixtures   # genera datos sintéticos reproducibles
make test       # pruebas unitarias e integración
make lint       # ruff + mypy
```
