# tests/

`unit/`: pruebas unitarias por regla/función pura. `integracion/`: pruebas de extremo a extremo sobre
fixtures (bronce→plata→..., según el incremento). `fixtures/`: datos **sintéticos**, generados por
`scripts/generar_fixtures.py`, que imitan la estructura y los defectos de los datos reales descritos
en `CLAUDE.md` §4. Ningún archivo bajo `fixtures/` proviene de `data/raw/` ni `data/private/`.

Lectura: cualquier colaborador del proyecto, incluido Claude Code.
