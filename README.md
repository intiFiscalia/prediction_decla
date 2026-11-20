# GIC · Reporte de fenómenos criminales

Convierte el Excel de relatos del Grupo de Información Criminal (GIC) en un reporte de 8 secciones (indicadores,
fenómenos, territorio, sectores, red, alertas, predicciones y organizaciones), idéntico al tablero publicado en
Claude. El resultado es un único archivo `reporte/dist/reporte.html` que se abre sin conexión, con doble clic.

> Todas las cifras miden **actividad institucional registrada** (relatos que llegaron al GIC), no la incidencia
> real del delito.

## Requisitos

- Python 3.13 (probado con 3.13). Otras versiones 3.11+ funcionan, pero para obtener *exactamente* las mismas cifras
  use las versiones fijadas en `requirements.txt`.
- Un navegador moderno para abrir el reporte.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (cmd.exe):**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

> En macOS/Linux el comando suele ser `python3`; en Windows, `py` o `python`. El resto de comandos de este README
> (`python run.py ...`) funciona igual en los tres entornos una vez activado el entorno virtual (`.venv`); si su
> `python` no apunta a Python 3, use `python3` (Mac/Linux) o `py` (Windows) en su lugar.

## Uso

1. Ponga el Excel en `data/` (hay uno incluido: `DatosAn_lisisReumenGICLavado_V1.xlsx`). Si en `data/` hay un solo
   `.xlsx`, se usa ese; si hay varios, indique cuál en `ARCHIVO_ENTRADA` del `.env`.
2. Revise `.env` (incluido). `.env.example` es la plantilla sin secretos.
3. Ejecute:

```bash
python run.py              # procesa y arma el reporte (≈1 minuto)
python run.py --verificar  # además confirma que el resultado es idéntico al publicado
```

4. Abra `reporte/dist/reporte.html`.

### ¿Da el mismo resultado?

Sí, para el mismo Excel. `python run.py --verificar` compara las 22 tablas generadas en `out/` contra la huella del
resultado publicado (`tests/referencia.json`) y debe terminar con:

```
Las 22 tablas coinciden exactamente con el resultado publicado.
```

Todo el proceso es determinista: semillas fijas, relatos ordenados por fecha e Id antes de analizar (el orden de las
filas del Excel no importa), sin llamadas a servicios externos. Si cambia el Excel, `--verificar` mostrará tablas
`DISTINTO`: es lo esperado. Si el cambio es intencional y quiere fijarlo como nueva referencia:
`python tests/verificar.py out --crear`.

El Excel debe tener las mismas columnas que el original (49), en especial `ResumenHechos`, `TematicaPriorizada`,
`LugarDeLosHechos`, `FechaIngreso`, `FechaRecepcionAjust`, `FechaCierreAjust`, `DecisionFiscalUGIC`, `ETAPA`,
`DELITO`, `GrupoEstructura`, `Estructura`, `EntidadRemite` e `IdEntrada`.

## Estructura

```
data/                     Excel de entrada (contiene datos personales: manéjelo según su política)
pipeline/
  pipeline.py             bronce→plata→entidades→fenómenos→oro: territorio DIVIPOLA, taxonomía, sectores CIIU,
                          asociaciones (Fisher + Benjamini–Hochberg), red, alertas EARS/CUSUM, pronósticos
  taxonomia.py            taxonomía versionada de fenómenos, mecanismos, bienes, sectores y organizaciones
  divipola.py             departamentos y municipios DIVIPOLA (con coordenadas de cabeceras)
  predicciones.py         probabilidad de generar caso, tiempo hasta el cierre (Kaplan–Meier), composición
assets/dptos_geo.json     límites departamentales simplificados (MGN DANE 2018)
reporte/
  src/                    código de la página (el mismo del tablero publicado)
  dash_shim.js            entorno local que reemplaza al del tablero de Claude
  vendor/d3.v7.min.js     d3 v7 (licencia ISC)
  build_report.py         arma reporte/dist/reporte.html con todo incrustado
tests/
  verificar.py            compara out/ con tests/referencia.json
  referencia.json         huellas del resultado publicado
  probar_reporte.mjs      prueba el HTML en un navegador simulado (Node + jsdom)
out/                      tablas generadas (JSON); cada una lleva su código en "meta"
```

## Textos fijos que dependen de los datos

Algunas frases del reporte describen la base actual y no se recalculan solas (están en `reporte/src/index.html`):
el nombre del archivo y el rango de fechas en «Fuente, método y limitaciones», el vacío de registro de
jul–ago 2025, los «23 meses completos», la fecha de corte 10-nov-2026 y el «79 % en indagación». Si cambia de
base, revíselas.

## Probar el HTML (opcional)

```bash
npm install jsdom
node tests/probar_reporte.mjs reporte/dist/reporte.html
```

Debe abrir las 8 pestañas y terminar con `errores: 0 []`.
