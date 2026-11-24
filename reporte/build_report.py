"""Arma reporte/dist/reporte.html: un solo archivo, sin conexión, con las 10 secciones del tablero.
Incrusta d3, los estilos, el entorno local (dash_shim.js), los datos de out/ y el código de las páginas.
Uso: python3 reporte/build_report.py [carpeta_out] [archivo_salida]
"""
import sys, os, re, json

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "out")
DEST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(RAIZ, "reporte", "dist", "reporte.html")
FUENTE = sys.argv[3] if len(sys.argv) > 3 else "gic"
SRC = os.path.join(RAIZ, "reporte", "src")

# Identificador de cada fuente en el tablero -> archivo generado por el pipeline (mismo mapeo que el tablero publicado)
FUENTES = {
    "hechos": "hechos.json", "etiquetas": "etiquetas.json", "organizaciones": "organizaciones.json",
    "territorio": "territorio_dptos.json", "modelo": "modelo_meta.json", "asociaciones": "asociaciones.json",
    "red_nodos": "red_nodos.json", "red_aristas": "red_aristas.json", "reglas": "reglas.json",
    "alertas": "alertas.json", "alertas_far": "alertas_far.json", "pronosticos": "pronosticos.json",
    "pronosticos_eval": "pronosticos_eval.json", "calidad": "calidad.json", "geo": "dptos_geo.json",
    "pc_eval": "pred_caso_eval.json", "pc_cal": "pred_caso_calibracion.json", "pc_rasgos": "pred_caso_rasgos.json",
    "pt_resumen": "pred_tiempo.json", "pt_curvas": "pred_tiempo_curvas.json", "pt_eval": "pred_tiempo_eval.json",
    "p_abiertos": "pred_abiertos.json", "p_compo": "pred_composicion.json",
}

def leer(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

datos, faltantes = {}, []
for k, f in FUENTES.items():
    ruta = os.path.join(OUT, f)
    if not os.path.exists(ruta):
        ruta = os.path.join(RAIZ, "assets", f)  # el mapa base vive en assets/
    if not os.path.exists(ruta):
        faltantes.append(k)  # fuentes sin equivalente en esta fuente de datos (p. ej. "otras predicciones" de DECLA)
        continue
    j = json.loads(leer(ruta))
    datos[k] = j["rows"] if isinstance(j, dict) and "rows" in j else j

meses = [m["mes"] for m in datos["calidad"]]
params = {"desde": meses[0], "hasta": meses[-1], "dpto": "", "conf": "0.5", "nivel": "fenómeno",
          "dim": "Entidad remitente" if FUENTE == "gic" else "Tipo de noticia",
          "fen_terr": "Lavado de activos", "metrica": "relatos_fen", "fen_sector": "Captación masiva e ilegal",
          "serie_alerta": "Total de relatos", "serie_pron": "Total de relatos", "modelo_pron": "auto",
          "fuente": FUENTE, "faltantes": faltantes}

html = leer(os.path.join(SRC, "index.html"))

html = html.replace('<meta name="dash-one-writer">\n', "")
html = html.replace('<link rel="stylesheet" href="app.css">', "")
scripts = re.findall(r'<script src="([^"]+)"></script>', html)
html = re.sub(r'<script src="[^"]+"></script>\n?', "", html)

def seguro(js):  # evita que un "</script>" dentro del código o los datos cierre la etiqueta
    return js.replace("</script", "<\\/script")

TOKENS = """
:root { --color-fg:#1f2328; --color-fg-muted:#5b6470; --color-bg:#ffffff; --color-panel:#f6f7f9; --color-border-line:#dfe3e8;
  --color-ok:#2e7d32; --color-warn:#c77700; --color-bad:#c62828;
  --font-anthropic-sans: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; --font-anthropic-serif: Georgia, "Times New Roman", serif;
  --cds-font-size-caption:12px; --cds-font-size-body:14px; --cds-font-size-heading:20px; --cds-font-size-title:28px; --cds-font-weight-medium:600;
  --cds-gap-xs:4px; --cds-gap-sm:8px; --cds-gap-md:12px; --cds-gap-lg:20px; --cds-gap-xl:32px;
  --cds-pad-xs:4px; --cds-pad-sm:8px; --cds-pad-md:12px; --cds-pad-lg:16px; --cds-pad-xl:24px; --cds-radius:8px;
  --cds-chart-muted:#b8c0ca; --cds-chart-status-critical:#c62828; --cds-chart-grid:#eceff3; --cds-chart-axis:#c9ced6; --cds-chart-reference:#8a93a0;
  --cds-text-secondary:#5b6470; --cds-surface-popover:#ffffff; --cds-border:#dfe3e8; --cds-shadow-popover:0 4px 16px rgba(0,0,0,.12); }
@media (prefers-color-scheme: dark) { :root { --color-fg:#e6e8eb; --color-fg-muted:#a3abb6; --color-bg:#16181b; --color-panel:#1f2226;
  --color-border-line:#33373d; --cds-chart-grid:#2a2e33; --cds-chart-axis:#3c4148; --cds-text-secondary:#a3abb6; --cds-surface-popover:#22262b; --cds-border:#33373d; } }
body { margin:0; background:var(--color-bg); color:var(--color-fg); }
#dash-root { max-width:1280px; margin:0 auto; padding:24px; font-family:var(--font-anthropic-sans); font-size:var(--cds-font-size-body); }
.dash-select { font:inherit; font-size:var(--cds-font-size-caption); color:var(--color-fg); background-color:var(--color-panel); border:1px solid var(--color-border-line); border-radius:6px; padding:6px 8px; }
.dash-skeleton { background:var(--color-panel); border-radius:var(--cds-radius); min-height:40px; }
@media print { #dash-root { max-width:none; padding:0; } }
"""

partes = [
    "<!DOCTYPE html>\n<html lang=\"es\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
    "<title>Reporte de fenómenos criminales</title>",
    f"<style>{TOKENS}\n{leer(os.path.join(SRC, 'app.css'))}</style></head><body>",
    f'<div id="dash-root">{html}</div>',
    f'<script id="gic-data" type="application/json">{seguro(json.dumps(datos, ensure_ascii=False))}</script>',
    f'<script id="gic-params" type="application/json">{json.dumps(params, ensure_ascii=False)}</script>',
    f"<script>{seguro(leer(os.path.join(RAIZ, 'reporte', 'vendor', 'd3.v7.min.js')))}</script>",
    f"<script>{seguro(leer(os.path.join(RAIZ, 'reporte', 'dash_shim.js')))}</script>",
]
for s in scripts:
    partes.append(f"<script>{seguro(leer(os.path.join(SRC, s)))}</script>")
partes.append("</body></html>")
os.makedirs(os.path.dirname(DEST), exist_ok=True)
with open(DEST, "w", encoding="utf-8") as f:
    f.write("\n".join(partes))
print(f"Reporte: {DEST} ({os.path.getsize(DEST) // 1024} KB)")
