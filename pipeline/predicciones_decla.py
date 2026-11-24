"""Predicciones adicionales de DECLA (sección 7, parte 3 únicamente).
Uso: python3 -I predicciones_decla.py <ruta_excel> <carpeta_salida> [nombre_archivo]
DECLA no tiene campos de trámite/entrada ni decisión fiscal, así que no se calculan aquí la
probabilidad de generar caso ni el tiempo hasta el cierre (Kaplan-Meier): cada fila de DECLA ya es un
caso SPOA abierto. Solo se calcula la composición esperada de fenómenos (ver CLAUDE.md "DECLA").
"""
import sys, os, json, math, unicodedata, re
import numpy as np, pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
CODE_META = [{"label": "predicciones_decla.py", "value": open(os.path.join(HERE, "predicciones_decla.py"), encoding="utf-8").read(), "type": "code", "lang": "python"}]
INPUT_NAME = sys.argv[3] if len(sys.argv) > 3 else "DECLA_2024_2026.xlsx"
INPUT_META = {"label": "Input", "value": f"{INPUT_NAME} + hechos.json y etiquetas.json de pipeline_decla.py"}

def clean(v):
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating, float)): return None if math.isnan(v) else round(float(v), 6)
    return v
def dump(name, rows, extra=None):
    rows = [{k: clean(v) for k, v in r.items()} for r in rows]
    json.dump({"rows": rows, "meta": CODE_META + [INPUT_META] + (extra or [])}, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, allow_nan=False)
    print(name, len(rows))
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))

H = pd.DataFrame(json.load(open(os.path.join(OUT, "hechos.json")))["rows"])
E = pd.DataFrame(json.load(open(os.path.join(OUT, "etiquetas.json")))["rows"])
FEN = E[(E.nivel == "fenómeno") & (E.confianza >= 0.5)]

# ---------------- Composición esperada de fenómenos ----------------
cal_m = pd.DataFrame(json.load(open(os.path.join(OUT, "calidad.json")))["rows"])
comp = cal_m[cal_m.estado == "completo"].mes.tolist()
ult12, prev = comp[-12:], comp[:-12]
def shares(meses):
    ids = set(H[H.mes.isin(meses)].rid); n = len(ids)
    f = FEN[FEN.rid.isin(ids)].groupby("item").rid.nunique()
    return f, n
f1, n1 = shares(ult12); f0, n0 = shares(prev)
compo = []
for item in f1.sort_values(ascending=False).index[:10]:
    k = int(f1[item]); lo, hi = wilson(k, n1); k0 = int(f0.get(item, 0))
    compo.append({"fenomeno": item, "relatos_12m": k, "pct_12m": k / n1, "ic_inf": lo, "ic_sup": hi,
                  "relatos_previos": k0, "pct_previo": k0 / n0 if n0 else None, "cambio_pp": (k / n1 - k0 / n0) if n0 else None})
dump("pred_composicion.json", compo, [{"label": "Periodos", "value": f"Recientes: {ult12[0]} a {ult12[-1]} ({n1} relatos). Anteriores: {prev[0]} a {prev[-1]} ({n0} relatos), sin meses incompletos."}])
print("composición calculada:", len(compo), "fenómenos")
