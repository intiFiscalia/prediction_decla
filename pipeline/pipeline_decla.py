"""Pipeline DECLA: bronce (Excel, hojas Hoja1+Relato) -> plata -> entidades -> fenómenos -> oro.
Uso: python3 -I pipeline_decla.py <ruta_excel> <carpeta_salida> [nombre_archivo]
Espejo de pipeline.py (GIC) para una fuente con otra estructura: DECLA no tiene campos de
trámite/entrada del GIC (TipoEntrada, EntidadRemite, CanalRecepción, DecisionFiscalUGIC); cada fila
ya es un caso SPOA abierto (Hoja1), con el texto del relato en la hoja Relato (unión 1 a 1 por
CASO_NOTICIA). No se exportan nombres, documentos ni el texto de RELATO.
Ver CLAUDE.md "DECLA" para las decisiones de método (fecha base, qué se omite y por qué).
"""
import sys, os, re, json, unicodedata, itertools, math
import numpy as np, pandas as pd
from scipy import stats
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxonomia as T
import divipola as D

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
CODE_META = [{"label": f, "value": open(os.path.join(HERE, f), encoding="utf-8").read(), "type": "code", "lang": "python"}
             for f in ("pipeline_decla.py", "taxonomia.py", "divipola.py")]
INPUT_NAME = sys.argv[3] if len(sys.argv) > 3 else "DECLA_2024_2026.xlsx"
INPUT_META = {"label": "Input", "value": f"{INPUT_NAME} (1.929 casos × 40 columnas + hoja Relato)"}
RNG = np.random.default_rng(20261118)

def norm(s):
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()

def clean(v):
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating, float)):
        return None if (v is None or math.isnan(v)) else round(float(v), 6)
    if isinstance(v, (np.bool_,)): return bool(v)
    if v is pd.NaT: return None
    return v

def dump(name, rows, extra_meta=None):
    rows = [{k: clean(v) for k, v in r.items()} for r in rows]
    meta = CODE_META + [INPUT_META] + (extra_meta or [])
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "meta": meta}, f, ensure_ascii=False, allow_nan=False)
    print(name, len(rows))

# ---------------- Bronce -> Plata ----------------
h1 = pd.read_excel(SRC, sheet_name="Hoja1")
rel = pd.read_excel(SRC, sheet_name="Relato")
df = h1.merge(rel, on="CASO_NOTICIA", how="left", validate="one_to_one")
assert df["RELATO"].notna().all(), "CASO_NOTICIA sin relato: revisar unión Hoja1/Relato"
df = df.sort_values(["FECHA_CREACION", "CASO_NOTICIA"], kind="mergesort").reset_index(drop=True)  # orden estable; FECHA_CREACION es la fecha base (ver CLAUDE.md)
df["rid"] = np.arange(1, len(df) + 1)
df["mes"] = df["FECHA_CREACION"].dt.strftime("%Y-%m")
df["mes_denuncia"] = df["CASO_FECHA_DENUNCIA"].dt.strftime("%Y-%m")
df["mes_hecho"] = df["FECHA_HECHO"].dt.strftime("%Y-%m")
txt = df["RELATO"].map(norm)

def delito_grupo(s):
    n = norm(s)
    if not n: return "Sin caso SPOA asociado"
    if "lavado de activos" in n:
        if "superior" in n: return "Lavado de activos (cuantía > 100 SMLMV)"
        if "inferior" in n: return "Lavado de activos (cuantía < 100 SMLMV)"
        return "Lavado de activos (sin cuantía)"
    if "captacion" in n: return "Captación masiva y habitual"
    if "enriquecimiento" in n: return "Enriquecimiento ilícito"
    if "falsificacion de moneda" in n or "moneda falsificada" in n: return "Falsificación de moneda"
    if "contrabando" in n: return "Contrabando"
    if "concierto" in n: return "Concierto para delinquir"
    if "estupefacientes" in n: return "Tráfico de estupefacientes"
    if any(k in n for k in ("peculado", "interes indebido")): return "Contra la administración pública"
    return "Otros delitos"

# DELITO/CAPITULO/TITULO -> fenómeno de la taxonomía (fuente "registrado"). Solo mapea a categorías que
# ya existen en taxonomia.FENOMENOS (decisión del usuario: no se agregan categorías nuevas en esta
# versión). Los casos de falsificación/tráfico de moneda falsificada (≈8,7% de DECLA) no tienen
# categoría hoy y quedan sin fenómeno "registrado" (sí pueden salir por reglas sobre el relato).
def delito_a_fenomeno(delito, capitulo, titulo):
    d, c = norm(delito), norm(capitulo)
    if "lavado de activos" in d or "lavado de activos" in c: return "Lavado de activos"
    if "captacion masiva" in d or "sistema financiero" in c: return "Captación masiva e ilegal"
    if "estafa" in d or c == "de la estafa": return "Estafa y fraude"
    if "enriquecimiento ilicito" in d or "enriquecimiento ilicito" in c: return "Enriquecimiento ilícito"
    if "concierto para delinquir" in d or "concierto" in c: return "Crimen organizado / concierto"
    if "estupefaciente" in c or "narcotrafic" in d: return "Narcotráfico"
    if "contrabando" in d: return "Contrabando"
    if "extorsion" in d: return "Extorsión"
    if "trata de personas" in d: return "Trata y tráfico de personas"
    if "mineria ilegal" in d or "explotacion ilicita" in d: return "Delitos ambientales y minería ilegal"
    if "trafico de armas" in d or "porte de armas" in d: return "Tráfico de armas"
    if "hurto" in d: return "Hurto"
    return None

# ---------------- Territorio (DIVIPOLA, columnas ya estructuradas) ----------------
MUNI_PAT = {c: re.compile(r"\b(" + "|".join(p) + r")\b") for c, (_, p, _, _) in D.MUNICIPIOS.items()}
DPTO_POR_NOMBRE = {norm(n): c for c, (n, _) in D.DEPARTAMENTOS.items()}
DPTO_POR_NOMBRE.update({"bogota, d. c.": "11", "bogota d.c.": "11", "bogota, d.c.": "11",
                        "san andres, providencia y santa catalina": "88"})

def territorio(dpto_hecho, mpio_hecho):
    dn = norm(dpto_hecho)
    dp = DPTO_POR_NOMBRE.get(dn)
    if not dp:
        for c, (_, pats) in D.DEPARTAMENTOS.items():
            if any(re.search(r"\b" + p + r"\b", dn) for p in pats):
                dp = c; break
    if not dp:
        return [], None, None
    out = [("dpto", dp)]
    mn = norm(mpio_hecho)
    if mn:
        for c, pat in MUNI_PAT.items():
            if c[:2] == dp and pat.search(mn):
                out.insert(0, ("mpio", c)); break
    return out, "registrado", 1.0

terr_rows, rec_terr = [], {}
for i, r in df.iterrows():
    found, origen, conf = territorio(r["DEPARTAMENTO_HECHOS"], r["MUNICIPIO_HECHOS"])
    mp = [c for t, c in found if t == "mpio"]
    dp = sorted(set([c[:2] for c in mp] + [c for t, c in found if t == "dpto"]))
    principal = mp[0][:2] if mp else (dp[0] if dp else None)
    rec_terr[r["rid"]] = (principal, mp[0] if mp else None, origen, conf, dp)
    for c in dp:
        terr_rows.append({"rid": r["rid"], "dpto_cod": c, "dpto": D.DEPARTAMENTOS[c][0], "origen": origen, "confianza": conf})

# ---------------- Entidades y fenómenos ----------------
def hits(patterns, t):
    return sum(1 for p in patterns if re.search(p, t))

def conf_regla(h):
    return round(min(0.9, 0.55 + 0.15 * (h - 1)), 2)

labels = {}  # rid -> {(nivel, item): (origen, conf)}
PRIOR = {"registrado": 4, "extraído_regla": 3, "extraído_modelo": 2, "inferido": 1}
def add(rid, nivel, item, origen, conf):
    d = labels.setdefault(rid, {})
    k = (nivel, item)
    if k not in d or PRIOR[origen] > PRIOR[d[k][0]] or (origen == d[k][0] and conf > d[k][1]):
        d[k] = (origen, conf)

for i, r in df.iterrows():
    rid, t = r["rid"], txt[i]
    fen_reg = delito_a_fenomeno(r["DELITO"], r["CAPITULO"], r["TITULO"])
    if fen_reg:
        add(rid, "fenómeno", fen_reg, "registrado", 1.0)
    for f, pats in T.FENOMENOS.items():
        h = hits(pats, t)
        if h: add(rid, "fenómeno", f, "extraído_regla", conf_regla(h))
    for m, pats in T.MECANISMOS.items():
        h = hits(pats, t)
        if h: add(rid, "mecanismo", m, "extraído_regla", conf_regla(h))
    for b, pats in T.BIENES.items():
        h = hits(pats, t)
        if h: add(rid, "bien", b, "extraído_regla", conf_regla(h))
    for cod in re.findall(r"(?:ciiu|codigo|actividad economica(?: principal)?(?: es)?|actividad)\D{0,12}(\d{4})\b", t):
        s = T.ciiu_seccion(cod)
        if s:
            nombre = T.SECTORES[s][0] if s in T.SECTORES else T.SECCION_NOMBRE_EXTRA[s]
            add(rid, "sector", f"{s} · {nombre}", "extraído_regla", 0.9)
    for s, (nombre, pats) in T.SECTORES.items():
        h = hits(pats, t)
        if h: add(rid, "sector", f"{s} · {nombre}", "extraído_regla", conf_regla(h) - 0.05)
    # organizaciones: sin fuente "registrado" (DECLA no tiene GrupoEstructura/Estructura), solo relato
    named = False
    for pat, nm, tp in T.ORGANIZACIONES:
        if re.search(pat, t):
            add(rid, "organización", nm, "extraído_regla", 0.8); named = True
    if not any(k[0] == "organización" and "Disidencias" in k[1] for k in labels.get(rid, {})):
        if re.search(T.ORG_GENERICA_DISIDENCIA[0], t):
            add(rid, "organización", T.ORG_GENERICA_DISIDENCIA[1], "extraído_regla", 0.7); named = True
        elif re.search(T.ORG_GENERICA_FARC[0], t):
            add(rid, "organización", T.ORG_GENERICA_FARC[1], "extraído_regla", 0.6); named = True
    has_org = any(k[0] == "organización" for k in labels.get(rid, {}))
    if not has_org and re.search(T.ORG_SIN_NOMBRE[0], t):
        add(rid, "organización", T.ORG_SIN_NOMBRE[1], "extraído_regla", 0.55)

ORG_TIPO = {nm: tp for _, nm, tp in T.ORGANIZACIONES}
ORG_TIPO[T.ORG_GENERICA_DISIDENCIA[1]] = T.ORG_GENERICA_DISIDENCIA[2]
ORG_TIPO[T.ORG_GENERICA_FARC[1]] = T.ORG_GENERICA_FARC[2]
ORG_TIPO[T.ORG_SIN_NOMBRE[1]] = T.ORG_SIN_NOMBRE[2]
for rid, d in labels.items():
    orgs = [k for k in d if k[0] == "organización"]
    if ("organización", "GDO/GDCO (sin nombre registrado)") in d and len(orgs) > 1:
        del d[("organización", "GDO/GDCO (sin nombre registrado)")]

# ---- extraído_modelo: clasificador binario por fenómeno (TF-IDF + regresión logística) ----
# Objetivo = fenómeno "registrado" (DELITO/CAPITULO/TITULO, delito_a_fenomeno), igual método que GIC.
UMBRAL_MODELO = 0.6
y = df.apply(lambda r: delito_a_fenomeno(r["DELITO"], r["CAPITULO"], r["TITULO"]), axis=1)
vec = TfidfVectorizer(preprocessor=norm, ngram_range=(1, 2), min_df=2, max_features=20000, sublinear_tf=True)
X = vec.fit_transform(df["RELATO"].fillna(""))
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
modelo_rows = []
for f in [c for c, v in y.value_counts().items() if v >= 8]:
    t_ = (y == f).astype(int).values
    pr = cross_val_predict(LogisticRegression(max_iter=3000, C=4.0, class_weight="balanced"), X, t_, cv=skf, method="predict_proba")[:, 1]
    pred = (pr >= UMBRAL_MODELO).astype(int)
    aportadas = 0
    for i, r in df.iterrows():
        if pred[i] and ("fenómeno", f) not in labels.get(r["rid"], {}):
            add(r["rid"], "fenómeno", f, "extraído_modelo", round(float(pr[i]), 2)); aportadas += 1
    modelo_rows.append({"fenomeno": f, "positivos_registrados": int(t_.sum()),
                        "precision_cv": round(precision_score(t_, pred, zero_division=0), 2),
                        "sensibilidad_cv": round(recall_score(t_, pred), 2), "umbral": UMBRAL_MODELO,
                        "etiquetas_aportadas": aportadas})

# ---- inferido ----
for rid, d in labels.items():
    fen = {k[1] for k in d if k[0] == "fenómeno"}
    mec = [k for k in d if k[0] == "mecanismo"]
    orgs = [k[1] for k in d if k[0] == "organización"]
    if "Lavado de activos" not in fen and len(mec) >= 2:
        add(rid, "fenómeno", "Lavado de activos", "inferido", 0.5)
    tipos = {ORG_TIPO.get(o, "") for o in orgs}
    if any(t_.startswith(("GAO", "Guerrilla")) for t_ in tipos) and "Financiación de grupos armados / terrorismo" not in fen:
        add(rid, "fenómeno", "Financiación de grupos armados / terrorismo", "inferido", 0.5)
    if any(o != T.ORG_SIN_NOMBRE[1] for o in orgs) and "Crimen organizado / concierto" not in fen:
        add(rid, "fenómeno", "Crimen organizado / concierto", "inferido", 0.55)
    if any(o in ("Cartel de Sinaloa", "CJNG", "Carteles mexicanos (sin especificar)", "Cartel del Norte del Valle (histórico)", "Los Choneros / Los Lobos", "Cartel de los Soles") for o in orgs) and "Narcotráfico" not in fen:
        add(rid, "fenómeno", "Narcotráfico", "inferido", 0.5)

# ---- segunda pasada: segregar relatos que solo quedaron en "Lavado de activos" ----
for rid, d in labels.items():
    fen = {k[1] for k in d if k[0] == "fenómeno"}
    if fen == {"Lavado de activos"}:
        t = txt[rid - 1]
        for f, pats in T.FENOMENOS_LAVADO_EXTRA.items():
            h = hits(pats, t)
            if h: add(rid, "fenómeno", f, "extraído_regla", conf_regla(h))

es_lavado = {rid for rid, d in labels.items() if "Lavado de activos" in {k[1] for k in d if k[0] == "fenómeno"}}
for rid, d in labels.items():
    fen = {k[1] for k in d if k[0] == "fenómeno"}
    if "Lavado de activos" in fen and len(fen) > 1:
        del d[("fenómeno", "Lavado de activos")]

# ---------------- Oro: tabla de hechos (sin datos personales) ----------------
meses_all = pd.period_range("2024-01", "2026-11", freq="M").strftime("%Y-%m").tolist()
PARCIAL = {"2024-01": "mes parcial (inicio 03-ene-2024)", "2026-11": "mes parcial (corte 12-nov-2026)"}
cnt_mes = df["mes"].value_counts()
INCOMPLETO = {m for m in meses_all if cnt_mes.get(m, 0) < 5 and m not in PARCIAL}
POST_VACIO = {meses_all[i + 1] for i, m in enumerate(meses_all[:-1]) if m in INCOMPLETO and meses_all[i + 1] not in INCOMPLETO}
def calidad_mes(m):
    if m in INCOMPLETO: return "posible vacío de registro"
    if m in POST_VACIO: return "posterior a vacío: posible rezago acumulado"
    return "ok"

def etapa_fmt(s):
    return str(s).title().replace("De ", "de ") if isinstance(s, str) else None

hechos = []
for i, r in df.iterrows():
    rid = r["rid"]; d = labels.get(rid, {})
    dp, mp, torig, tconf, dps = rec_terr[rid]
    hechos.append({
        "rid": rid, "mes": r["mes"], "mes_creacion": r["mes"],
        "mes_denuncia": r["mes_denuncia"] if isinstance(r["mes_denuncia"], str) else None,
        "mes_hecho": r["mes_hecho"] if isinstance(r["mes_hecho"], str) else None,
        "anio": r["mes"][:4],
        "delito": delito_grupo(r["DELITO"]),
        "etapa": etapa_fmt(r["ETAPA"]), "estado_caso": etapa_fmt(r["ESTADO"]),
        "tipo_noticia": r["TIPO_NOTICIA"], "tipo_diligencia": r["TIPO_DILIGENCIA"],
        "competencia_despacho": r["COMPETENCIA_DESPACHO"], "capitulo": r["CAPITULO"], "titulo": r["TITULO"],
        "con_spoa": 1, "indagacion": 1 if r["ETAPA"] == "INDAGACIÓN" else 0,
        "dpto_cod": dp, "dpto": D.DEPARTAMENTOS[dp][0] if dp else "Sin territorio identificado",
        "mpio_cod": mp, "mpio": D.MUNICIPIOS[mp][0] if mp else None,
        "lat": D.MUNICIPIOS[mp][2] if mp else None, "lon": D.MUNICIPIOS[mp][3] if mp else None,
        "terr_origen": torig or "sin dato", "terr_confianza": tconf,
        "n_fenomenos": sum(1 for k in d if k[0] == "fenómeno"),
        "n_orgs": sum(1 for k in d if k[0] == "organización"),
        "es_lavado": 1 if rid in es_lavado else 0,
    })
H = pd.DataFrame(hechos)
dump("hechos.json", hechos)

etiquetas = []
for rid, d in labels.items():
    h = hechos[rid - 1]
    for (nivel, item), (origen, conf) in d.items():
        etiquetas.append({"rid": rid, "mes": h["mes"], "dpto_cod": h["dpto_cod"], "dpto": h["dpto"], "nivel": nivel,
                          "item": item, "tipologia": ORG_TIPO.get(item) if nivel == "organización" else None,
                          "origen": origen, "confianza": conf})
E = pd.DataFrame(etiquetas)
dump("etiquetas.json", [r for r in etiquetas if r["nivel"] != "organización"],
     [{"label": "Taxonomía", "value": T.TAXONOMIA_VERSION}])
dump("organizaciones.json", [r for r in etiquetas if r["nivel"] == "organización"])
dump("territorio_dptos.json", terr_rows)

dump("modelo_meta.json", modelo_rows, [{"label": "Modelo", "value": "TF-IDF (1-2 gramas, máx. 20.000) + regresión logística balanceada, un clasificador por fenómeno; validación cruzada estratificada 5 particiones; objetivo = fenómeno registrado por DELITO/CAPITULO/TITULO"}, {"label": "Taxonomía", "value": T.TAXONOMIA_VERSION}])

# ---------------- Sectores: asociación fenómeno <-> sector (Fisher + BH) ----------------
CONF_MIN = 0.5
def presentes(nivel):
    s = E[(E.nivel == nivel) & (E.confianza >= CONF_MIN)]
    return {k: set(v) for k, v in s.groupby("item")["rid"]}
FEN, SEC, MEC, BIE = presentes("fenómeno"), presentes("sector"), presentes("mecanismo"), presentes("bien")
N = len(df)
assoc = []
for f, fs in FEN.items():
    if len(fs) < 10: continue
    for s, ss in SEC.items():
        if len(ss) < 5: continue
        a = len(fs & ss); b = len(fs - ss); c = len(ss - fs); d_ = N - a - b - c
        _, p = stats.fisher_exact([[a, b], [c, d_]])
        aa, bb, cc, dd = a + .5, b + .5, c + .5, d_ + .5
        lor = math.log(aa * dd / (bb * cc)); se = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
        assoc.append({"fenomeno": f, "sector": s, "n_ambos": a, "n_fenomeno": len(fs), "n_sector": len(ss),
                      "esperado": round(len(fs) * len(ss) / N, 2), "or": round(math.exp(lor), 3),
                      "ic_inf": round(math.exp(lor - 1.96 * se), 3), "ic_sup": round(math.exp(lor + 1.96 * se), 3),
                      "p": p})
pv = np.array([r["p"] for r in assoc]); m = len(pv)
order = np.argsort(pv); q = np.empty(m); prev = 1.0
for rank, idx in enumerate(order[::-1]):
    k = m - rank
    prev = min(prev, pv[idx] * m / k); q[idx] = prev
for r, qq in zip(assoc, q):
    r["q_bh"] = float(qq); r["p"] = float(r["p"])
    r["significativo"] = "Sí (q < 0,05)" if qq < 0.05 else "No"
    r["direccion"] = "Sobrerrepresentado" if r["or"] > 1 else "Subrepresentado"
assoc.sort(key=lambda r: (r["q_bh"], -abs(math.log(r["or"]))))
dump("asociaciones.json", assoc, [{"label": "Pruebas", "value": f"{m} pares fenómeno×sector; Fisher exacto bilateral; OR con corrección de Haldane y IC95 de Woolf; ajuste Benjamini–Hochberg"}])

# ---------------- Red de co-ocurrencias ----------------
DPTO = {}
for r_ in terr_rows: DPTO.setdefault(r_["dpto"], set()).add(r_["rid"])
grupos = {"actividad": SEC, "mecanismo": MEC, "bien": BIE, "lugar": DPTO}
items = {}
for tipo, dct in grupos.items():
    for k, v in dct.items():
        if len(v) >= 4: items[(tipo, k)] = v
G = nx.Graph(); reglas = []
for (t1, k1), v1 in items.items():
    G.add_node(f"{t1}:{k1}", tipo=t1, label=k1, n=len(v1))
for ((t1, k1), v1), ((t2, k2), v2) in itertools.combinations(items.items(), 2):
    if t1 == t2 == "lugar": continue
    n12 = len(v1 & v2)
    if n12 < 3: continue
    lift = n12 * N / (len(v1) * len(v2))
    for (ta, ka, va), (tb, kb, vb) in (((t1, k1, v1), (t2, k2, v2)), ((t2, k2, v2), (t1, k1, v1))):
        reglas.append({"antecedente": ka, "tipo_a": ta, "consecuente": kb, "tipo_c": tb, "n": n12,
                       "soporte": round(n12 / N, 4), "confianza": round(n12 / len(va), 3), "lift": round(lift, 3)})
    if lift >= 1.2:
        G.add_edge(f"{t1}:{k1}", f"{t2}:{k2}", n=n12, lift=round(lift, 3), jaccard=round(n12 / len(v1 | v2), 3))
G.remove_nodes_from([n_ for n_ in list(G.nodes) if G.degree(n_) == 0])
comms = nx.algorithms.community.greedy_modularity_communities(G, weight="n")
comm = {n_: i + 1 for i, c in enumerate(comms) for n_ in c}
btw = nx.betweenness_centrality(G, weight=None)
pos = nx.spring_layout(G, seed=7, weight="n", k=1.4 / math.sqrt(max(G.number_of_nodes(), 1)), iterations=300)
nodos = [{"id": n_, "label": a["label"], "tipo": a["tipo"], "n": a["n"], "grado": G.degree(n_), "comunidad": comm[n_],
          "intermediacion": round(btw[n_], 4), "x": round(float(pos[n_][0]), 4), "y": round(float(pos[n_][1]), 4)} for n_, a in G.nodes(data=True)]
aristas = [{"source": u, "target": v, "n": a["n"], "lift": a["lift"], "jaccard": a["jaccard"]} for u, v, a in G.edges(data=True)]
dump("red_nodos.json", nodos, [{"label": "Red", "value": f"{G.number_of_nodes()} nodos, {G.number_of_edges()} aristas (co-ocurrencia ≥3 relatos y lift ≥1,2); comunidades por modularidad voraz"}])
dump("red_aristas.json", aristas)
reglas.sort(key=lambda r: (-r["lift"], -r["n"]))
dump("reglas.json", [r for r in reglas if r["n"] >= 5 and r["lift"] > 1][:150])

# ---------------- Series mensuales (sobre FECHA_CREACION, igual que el orden base) ----------------
serie_meses = [m_ for m_ in meses_all if m_ not in PARCIAL]
top_fen = [f for f, v in sorted(FEN.items(), key=lambda kv: -len(kv[1])) if len(v) >= 25][:7]
series = {"Total de relatos": H.groupby("mes").size()}
for f in top_fen:
    series[f] = H[H.rid.isin(FEN[f])].groupby("mes").size()
BASE_SERIES = set(series)
# Sin serie por "entidad remitente": ese campo no existe en DECLA (se omite, no se inventa sustituto).
for d_ in H[H.dpto_cod.notna()].dpto.value_counts().index[:4]:
    series[f"Territorio: {d_}"] = H[H.dpto == d_].groupby("mes").size()
RNG_SUB = np.random.default_rng(777)
series = {k: np.array([int(v.get(m_, 0)) for m_ in serie_meses]) for k, v in series.items()}
valid = np.array([m_ not in INCOMPLETO for m_ in serie_meses])

def nb_params(mu, var):
    if var <= mu * 1.05 or mu <= 0: return None
    return mu ** 2 / (var - mu)
def upper_tail(y, mu, r):
    if r is None: return float(stats.poisson.sf(y - 1, mu))
    p = r / (r + mu); return float(stats.nbinom.sf(y - 1, r, p))
def q99(mu, r):
    if r is None: return float(stats.poisson.ppf(0.99, mu))
    return float(stats.nbinom.ppf(0.99, r, r / (r + mu)))

def detectar(y, valid, ret=False):
    L = len(y); S = 0.0; out = []
    for t in range(L):
        base = [y[j] for j in range(max(0, t - 8), t - 2) if valid[j]]
        rec = {"esperado": None, "umbral": None, "p_cola": None, "cusum": None, "ears": 0, "cus": 0, "evaluado": 0}
        if valid[t] and len(base) >= 4:
            mu = max(float(np.mean(base)), 0.5); var = float(np.var(base, ddof=1)); r = nb_params(mu, var)
            sd = math.sqrt(mu + (mu ** 2 / r if r else 0))
            thr = q99(mu, r); pc = upper_tail(int(y[t]), mu, r)
            z = (y[t] - mu) / sd; S = max(0.0, S + z - 0.5)
            rec.update(esperado=round(mu, 2), umbral=thr, p_cola=round(pc, 4), cusum=round(S, 2), evaluado=1,
                       ears=int(y[t] > thr), cus=int(S > 4))
            if S > 4: S = 0.0
        out.append(rec)
    return out

alert_rows, far_rows = [], []
for nombre, y_ in series.items():
    res = detectar(y_, valid)
    for m_, yy, rr in zip(serie_meses, y_, res):
        alert_rows.append({"serie": nombre, "mes": m_, "observado": int(yy), "esperado": rr["esperado"], "umbral_99": rr["umbral"],
                           "p_cola": rr["p_cola"], "cusum": rr["cusum"], "senal_ears": rr["ears"], "senal_cusum": rr["cus"],
                           "evaluado": rr["evaluado"], "calidad": calidad_mes(m_)})
    yv = y_[valid]; mu = float(yv.mean()); var = float(yv.var(ddof=1)); r = nb_params(mu, var)
    fe = fc = ev = 0
    G_ = RNG if nombre in BASE_SERIES else RNG_SUB
    for _ in range(1000):
        sim = G_.poisson(mu, len(y_)) if r is None else G_.negative_binomial(r, r / (r + mu), len(y_))
        rs = detectar(sim, valid)
        fe += sum(x["ears"] for x in rs); fc += sum(x["cus"] for x in rs); ev += sum(x["evaluado"] for x in rs)
    far_rows.append({"serie": nombre, "media_mensual": round(mu, 2), "dispersion": "Poisson" if r is None else f"NB (r={r:.1f})",
                     "far_ears": round(fe / ev, 4), "far_cusum": round(fc / ev, 4),
                     "falsas_por_anio_ears": round(12 * fe / ev, 2), "falsas_por_anio_cusum": round(12 * fc / ev, 2),
                     "senales_ears": int(sum(x["ears"] for x in res)), "senales_cusum": int(sum(x["cus"] for x in res)),
                     "meses_evaluados": int(sum(x["evaluado"] for x in res))})
dump("alertas.json", alert_rows, [{"label": "Método", "value": "EARS tipo C2 (línea base 6 meses con 2 de guarda) contra cuantil 99% Poisson/binomial negativa; CUSUM k=0,5, h=4 sobre residuos estandarizados."}])
dump("alertas_far.json", far_rows)

# ---------------- Pronósticos ----------------
HZ = 6
fut = pd.period_range("2026-11", periods=HZ, freq="M").strftime("%Y-%m").tolist()
def ses_fit(y):
    best = None
    for a in np.linspace(0.05, 0.95, 19):
        l = y[0]; sse = 0; res = []
        for t in range(1, len(y)):
            e = y[t] - l; sse += e * e; res.append(e); l = l + a * e
        if best is None or sse < best[0]: best = (sse, a, l, res)
    return best[1], best[2], np.array(best[3])
def point(model, y):
    if model == "Ingenuo (último valor)": return float(y[-1])
    if model == "Media móvil 6 meses": return float(np.mean(y[-6:]))
    a, l, _ = ses_fit(y); return float(l)
MODELOS = ["Ingenuo (último valor)", "Media móvil 6 meses", "Suavizado exponencial simple"]
fc_rows, ev_rows = [], []
for nombre, y_ in series.items():
    yv = y_[valid].astype(float)
    mu = yv.mean(); var = yv.var(ddof=1); r = nb_params(mu, var)
    resid = {m_: [] for m_ in MODELOS}
    for t in range(6, len(yv)):
        for m_ in MODELOS: resid[m_].append(yv[t] - point(m_, yv[:t]))
    mae = {m_: [] for m_ in MODELOS}
    for o in range(len(yv) - 6, len(yv)):
        for h in range(1, 4):
            if o + h - 1 < len(yv):
                for m_ in MODELOS: mae[m_].append(abs(yv[o + h - 1] - point(m_, yv[:o])))
    mae_n = np.mean(mae[MODELOS[0]])
    for m_ in MODELOS:
        ev_rows.append({"serie": nombre, "modelo": m_, "mae": round(float(np.mean(mae[m_])), 2),
                        "mase_vs_ingenuo": round(float(np.mean(mae[m_]) / mae_n), 3) if mae_n > 0 else None})
    for m_, yy in zip(serie_meses, y_):
        fc_rows.append({"serie": nombre, "mes": m_, "tipo": "Observado", "modelo": "Observado", "valor": int(yy),
                        "inf80": None, "sup80": None, "inf95": None, "sup95": None,
                        "calidad": calidad_mes(m_)})
    G_ = RNG if nombre in BASE_SERIES else RNG_SUB
    for m_ in MODELOS:
        p0 = point(m_, yv); e = np.array(resid[m_])
        for h, fm in enumerate(fut, start=1):
            mu_b = np.maximum(0.2, p0 + G_.choice(e, 4000) * math.sqrt(h))
            sims = G_.poisson(mu_b) if r is None else G_.negative_binomial(r, r / (r + mu_b))
            qs = np.percentile(sims, [2.5, 10, 90, 97.5])
            fc_rows.append({"serie": nombre, "mes": fm, "tipo": "Pronóstico", "modelo": m_, "valor": round(p0, 2),
                            "inf80": float(qs[1]), "sup80": float(qs[2]), "inf95": float(qs[0]), "sup95": float(qs[3]), "calidad": "ok"})
dump("pronosticos.json", fc_rows, [{"label": "Historia", "value": f"{int(valid.sum())} meses completos válidos ({serie_meses[0]} a {serie_meses[-1]}); meses excluidos por posible vacío de registro: {', '.join(sorted(INCOMPLETO)) or 'ninguno'}; sin estacionalidad estimada (ADR 0016)."}])
dump("pronosticos_eval.json", ev_rows)

dump("calidad.json", [{"mes": m_, "relatos": int(cnt_mes.get(m_, 0)),
                       "estado": PARCIAL.get(m_) or ("completo" if calidad_mes(m_) == "ok" else calidad_mes(m_))} for m_ in meses_all])
print("incompletos", INCOMPLETO, "top", top_fen)
