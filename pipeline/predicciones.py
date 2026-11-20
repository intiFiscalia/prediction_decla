"""Predicciones adicionales del GIC (sección 9).
Uso: python3 -I predicciones.py <ruta_excel> <carpeta_salida>   (después de pipeline.py, que deja hechos.json y etiquetas.json)
1) Probabilidad de que un relato 'genere caso en especializadas' (TF-IDF del relato + campos de entrada, regresión logística).
2) Tiempo hasta el cierre del trámite (Kaplan–Meier por tipo de entrada, con relatos abiertos como censurados).
3) Composición esperada de fenómenos (últimos 12 meses completos, IC de Wilson).
"""
import sys, os, json, math, unicodedata, re
import numpy as np, pandas as pd
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, KFold, cross_val_predict
from sklearn.metrics import roc_auc_score, brier_score_loss

SRC, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
CODE_META = [{"label": "predicciones.py", "value": open(os.path.join(HERE, "predicciones.py"), encoding="utf-8").read(), "type": "code", "lang": "python"}]
INPUT_NAME = sys.argv[3] if len(sys.argv) > 3 else "DatosAn_lisisReumenGIC.xlsx"
INPUT_META = {"label": "Input", "value": f"{INPUT_NAME} + hechos.json y etiquetas.json de pipeline.py"}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()
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

df = pd.read_excel(SRC).sort_values(["FechaIngreso", "IdEntrada"], kind="mergesort").reset_index(drop=True)  # mismo orden que pipeline.py
H = pd.DataFrame(json.load(open(os.path.join(OUT, "hechos.json")))["rows"])
E = pd.DataFrame(json.load(open(os.path.join(OUT, "etiquetas.json")))["rows"])
assert len(H) == len(df) and (H.mes.values == df.FechaIngreso.dt.strftime("%Y-%m").values).all()
FEN = E[(E.nivel == "fenómeno") & (E.confianza >= 0.5)]
fen_principal = FEN.sort_values("confianza", ascending=False).drop_duplicates("rid").set_index("rid")["item"]
H["fenomeno_principal"] = H.rid.map(fen_principal).fillna("Sin fenómeno identificado")

# ---------------- 1) Probabilidad de generar caso ----------------
PEND = {"Análisis Jurídico", "Sin decisión registrada"}
H["pendiente"] = H.decision.isin(PEND).astype(int)
cols = ["tipo_entrada", "entidad_remite", "tematica", "canal", "tipo_remitente"]
Xs = csr_matrix(pd.get_dummies(H[cols].fillna("NA")).values.astype(float))
tf = TfidfVectorizer(preprocessor=norm, min_df=3, ngram_range=(1, 2), sublinear_tf=True, max_features=20000)
Xt = tf.fit_transform(df.ResumenHechos.fillna(""))
X = hstack([Xt, Xs]).tocsr()
tr = H.pendiente.values == 0
y = H.genera_caso.values
skf = StratifiedKFold(5, shuffle=True, random_state=1)
clf = LogisticRegression(max_iter=3000, C=2.0)
p_cv = cross_val_predict(clf, X[tr], y[tr], cv=skf, method="predict_proba")[:, 1]
p_cv_s = cross_val_predict(LogisticRegression(max_iter=3000, C=1.0), Xs[tr], y[tr], cv=skf, method="predict_proba")[:, 1]
base = y[tr].mean()
auc, auc_s = roc_auc_score(y[tr], p_cv), roc_auc_score(y[tr], p_cv_s)
clf.fit(X[tr], y[tr])
p_pend = clf.predict_proba(X[~tr])[:, 1]

ev = [{"medida": "Relatos con decisión final usados", "valor": int(tr.sum()), "tipo": "n"},
      {"medida": "Tasa real de 'genera caso'", "valor": float(base), "tipo": "pct"},
      {"medida": "AUC solo con campos de entrada", "valor": round(auc_s, 3), "tipo": "auc"},
      {"medida": "AUC con campos + texto del relato", "valor": round(auc, 3), "tipo": "auc"},
      {"medida": "Error cuadrático (Brier) del modelo", "valor": round(brier_score_loss(y[tr], p_cv), 3), "tipo": "dec"},
      {"medida": "Error cuadrático (Brier) usando siempre la tasa promedio", "valor": round(brier_score_loss(y[tr], np.full(tr.sum(), base)), 3), "tipo": "dec"}]
for r_ in ev: r_["de_100"] = round(r_["valor"] * 100) if r_["tipo"] == "auc" else None
dump("pred_caso_eval.json", ev, [{"label": "Validación", "value": "Predicción fuera de muestra, 5 particiones estratificadas"}])

# calibración por quintiles de probabilidad predicha
q = pd.qcut(p_cv, 5, labels=False, duplicates="drop")
cal = []
for k in sorted(set(q)):
    m = q == k; n = int(m.sum()); obs = float(y[tr][m].mean()); lo, hi = wilson(int(y[tr][m].sum()), n)
    cal.append({"grupo": f"Quintil {k + 1}", "orden": int(k + 1), "prob_predicha": float(p_cv[m].mean()), "tasa_real": obs, "ic_inf": lo, "ic_sup": hi, "relatos": n})
dump("pred_caso_calibracion.json", cal)

# tasas observadas por rasgo (lo que explica la probabilidad, en términos sencillos)
Ht = H[tr].copy()
rasgos = []
for dim, col in [("Tipo de entrada", "tipo_entrada"), ("Entidad remitente", "entidad_remite"), ("Fenómeno principal", "fenomeno_principal"), ("Canal", "canal")]:
    for cat, g in Ht.groupby(col):
        if len(g) < 10: continue
        k = int(g.genera_caso.sum()); lo, hi = wilson(k, len(g))
        rasgos.append({"dimension": dim, "categoria": cat, "relatos": len(g), "tasa": k / len(g), "ic_inf": lo, "ic_sup": hi, "diferencia": k / len(g) - base})
dump("pred_caso_rasgos.json", rasgos)

# ---------------- 2) Tiempo hasta el cierre (Kaplan–Meier) ----------------
corte = df.FechaIngreso.max()
recep = df.FechaRecepcionAjust
cierre = pd.to_datetime(df.FechaCierreAjust, format="%Y/%m/%d %H:%M:%S.%f", errors="coerce")
dur = np.where(cierre.notna(), (cierre - recep).dt.total_seconds() / 86400, (corte - recep).dt.total_seconds() / 86400)
evento = cierre.notna().values.astype(int)
H["dur"] = np.maximum(dur, 0); H["evento"] = evento
tipos = H.tipo_entrada.value_counts()
H["grupo_t"] = H.tipo_entrada.where(H.tipo_entrada.isin(tipos[tipos >= 30].index), "Otros tipos")

def km(t, e):
    t = np.asarray(t); e = np.asarray(e); o = np.argsort(t); t, e = t[o], e[o]
    S, n, pts = 1.0, len(t), [(0.0, 1.0)]
    for tt in np.unique(t[e == 1]):
        at = (t >= tt).sum(); d = ((t == tt) & (e == 1)).sum()
        S *= 1 - d / at; pts.append((float(tt), float(S)))
    return pts
def quant(pts, s):  # primer tiempo con S <= s
    for tt, S in pts:
        if S <= s: return tt
    return None
def S_at(pts, x):
    v = 1.0
    for tt, S in pts:
        if tt <= x: v = S
        else: break
    return v

curvas, resumen, KM = [], [], {}
for g, d in list(H.groupby("grupo_t")) + [("Todos los relatos", H)]:
    pts = km(d.dur, d.evento); KM[g] = pts
    resumen.append({"grupo": g, "relatos": len(d), "cerrados": int(d.evento.sum()), "abiertos": int((1 - d.evento).sum()),
                    "dias_p25": quant(pts, 0.75), "mediana_dias": quant(pts, 0.5), "dias_p75": quant(pts, 0.25), "dias_p90": quant(pts, 0.10),
                    "pct_cerrado_30": 1 - S_at(pts, 30), "pct_cerrado_90": 1 - S_at(pts, 90)})
    # curva reducida a pasos de 5 días hasta 365
    for x in range(0, 366, 5):
        curvas.append({"grupo": g, "dias": x, "pct_cerrado": 1 - S_at(pts, x)})
dump("pred_tiempo.json", resumen, [{"label": "Método", "value": f"Kaplan–Meier; relatos abiertos censurados en la fecha de corte {corte:%Y-%m-%d}"}])
dump("pred_tiempo_curvas.json", curvas)

# validación: mediana del grupo vs mediana global, sobre relatos cerrados (5 particiones)
cer = H[H.evento == 1].reset_index(drop=True)
err_g, err_0 = [], []
for a, b in KFold(5, shuffle=True, random_state=1).split(cer):
    trn, tst = cer.iloc[a], cer.iloc[b]
    med_g = trn.groupby("grupo_t").dur.median(); med0 = trn.dur.median()
    err_g += list(abs(tst.dur - tst.grupo_t.map(med_g).fillna(med0))); err_0 += list(abs(tst.dur - med0))
dump("pred_tiempo_eval.json", [{"metodo": "Mediana de su tipo de entrada", "error_mediano_dias": float(np.median(err_g)), "error_promedio_dias": float(np.mean(err_g))},
                               {"metodo": "Mediana de todos los relatos (referencia)", "error_mediano_dias": float(np.median(err_0)), "error_promedio_dias": float(np.mean(err_0))}])

# ---------------- Relatos abiertos o sin decisión: predicción individual ----------------
pend_idx = np.where(~tr)[0]
pp = dict(zip(pend_idx, p_pend))
abiertos = []
for i, r in H.iterrows():
    if r.evento != 0: continue  # solo relatos con trámite abierto (sin fecha de cierre)
    pts = KM[r.grupo_t]; el = float(r.dur)
    s0 = S_at(pts, el); tq = quant(pts, s0 / 2) if s0 > 0 else None
    restante = None if tq is None else max(0.0, tq - el)
    abiertos.append({"id_entrada": df.IdEntrada[i], "mes_ingreso": r.mes, "tipo_entrada": r.tipo_entrada, "entidad_remite": r.entidad_remite,
                     "fenomeno_principal": r.fenomeno_principal, "estado_tramite": r.estado_tramite, "decision_actual": r.decision,
                     "prob_genera_caso": float(pp[i]) if i in pp else None,
                     "dias_transcurridos": round(el, 0),
                     "dias_restantes_estimados": None if restante is None else round(restante, 0),
                     "sin_estimacion": "más allá de lo observado" if restante is None else ""})
abiertos.sort(key=lambda a: (a["prob_genera_caso"] is None, -(a["prob_genera_caso"] or 0), -a["dias_transcurridos"]))
dump("pred_abiertos.json", abiertos, [{"label": "Nota", "value": "Relatos con trámite abierto en la fecha de corte. Probabilidad solo para los que aún no tienen decisión final. Días restantes: mediana condicional Kaplan–Meier de su tipo de entrada."}])

# ---------------- 3) Composición esperada de fenómenos ----------------
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
print("AUC", round(auc_s, 3), round(auc, 3), "pendientes", int((~tr).sum()), "abiertos", int((H.evento == 0).sum()))
