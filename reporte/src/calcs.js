// Campo de fecha que agrupa por mes (selector "Fecha base", solo en DECLA); en GIC siempre es "mes".
G.mesCampo = () => { const b = dash.params().fecha_base; return b ? 'mes_' + b : 'mes'; };

dash.calc('hf', {
  inputs: ['hechos'],
  title: 'Relatos en la selección',
  description: 'Relatos filtrados por periodo (mes de ingreso) y departamento elegidos arriba.',
  fn: (hechos) => {
    const p = dash.params(); const campo = G.mesCampo();
    const d = p.desde || '0000-00', h = p.hasta || '9999-99';
    return hechos.filter((r) => { const m = r[campo] || r.mes; return m >= d && m <= h; }).filter((r) => !p.dpto || r.dpto_cod === p.dpto);
  },
});

dash.calc('kpi', {
  inputs: ['hf'],
  title: 'Indicadores de la selección',
  description: 'Totales y tasas sobre los relatos filtrados.',
  fn: (hf) => {
    const n = hf.length; const campo = G.mesCampo();
    const meses = new Set(hf.map((r) => r[campo] || r.mes)).size;
    const dias = hf.map((r) => r.dias_cierre).filter((v) => v != null).sort((a, b) => a - b);
    const med = dias.length ? (dias.length % 2 ? dias[(dias.length - 1) / 2] : (dias[dias.length / 2 - 1] + dias[dias.length / 2]) / 2) : null;
    const s = (k) => hf.reduce((a, r) => a + (r[k] || 0), 0);
    const tieneGenera = hf.some((r) => r.genera_caso != null);
    return [{
      total: n, meses, prom_mensual: meses ? n / meses : null,
      pct_spoa: n ? s('con_spoa') / n : null, pct_genera: n && tieneGenera ? s('genera_caso') / n : null,
      pct_indagacion: n ? s('indagacion') / n : null, mediana_dias: med,
      desde: hf.reduce((a, r) => (a && a < r.mes ? a : r.mes), null), hasta: hf.reduce((a, r) => (a && a > r.mes ? a : r.mes), null),
    }];
  },
});

dash.calc('serie_mes', {
  inputs: ['hf', 'calidad'],
  title: 'Relatos por mes',
  description: 'Conteo mensual de relatos de la selección, con el estado de completitud de cada mes.',
  fn: (hf, calidad) => {
    const p = dash.params(); const campo = G.mesCampo();
    const c = d3.rollup(hf, (v) => v.length, (r) => r[campo] || r.mes);
    return calidad.filter((m) => m.mes >= (p.desde || '0000') && m.mes <= (p.hasta || '9999'))
      .map((m) => ({ mes: m.mes, relatos: c.get(m.mes) || 0, estado: m.estado }));
  },
});

dash.calc('dist', {
  inputs: ['hf'],
  title: 'Distribución por dimensión',
  description: 'Relatos y porcentaje por categoría de cada dimensión descriptiva.',
  fn: (hf) => {
    const dims = { 'Delito (SPOA)': 'delito', 'Etapa procesal': 'etapa', 'Departamento': 'dpto', 'Entidad remitente': 'entidad_remite',
      'Tipo de entrada': 'tipo_entrada', 'Temática priorizada': 'tematica', 'Decisión fiscal UGIC': 'decision',
      'Estado del trámite': 'estado_tramite', 'Canal de recepción': 'canal', 'País relacionado': 'pais',
      // Dimensiones propias de DECLA (no existen en los relatos de GIC, así que no aparecen en su "Otra dimensión"):
      'Tipo de noticia': 'tipo_noticia', 'Tipo de diligencia': 'tipo_diligencia', 'Competencia del despacho': 'competencia_despacho',
      'Capítulo': 'capitulo', 'Título': 'titulo' };
    const n = hf.length, out = [];
    Object.entries(dims).forEach(([dim, k]) => {
      const c = d3.rollup(hf, (v) => v.length, (r) => r[k] || 'Sin dato');
      [...c].sort((a, b) => b[1] - a[1]).forEach(([cat, v]) => out.push({ dimension: dim, categoria: cat, relatos: v, pct: n ? v / n : 0 }));
    });
    return out;
  },
});

dash.calc('fen_dist', {
  inputs: ['hf', 'etiquetas'],
  title: 'Fenómenos por origen',
  description: 'Relatos por categoría de la taxonomía y origen de la etiqueta, con la confianza mínima elegida.',
  fn: (hf, etiquetas) => {
    const p = dash.params();
    const nivel = p.nivel || 'fenómeno', cmin = +p.conf || 0;
    const ids = new Set(hf.map((r) => r.rid));
    let et = etiquetas.filter((e) => ids.has(e.rid) && e.confianza >= cmin);
    let base = ids.size;
    if (nivel === 'mecanismo' || nivel === 'sector') {
      // Usa es_lavado (todos los relatos de lavado) y no la etiqueta "Lavado de activos" del nivel fenómeno,
      // que ahora solo cubre los relatos donde no se identificó un fenómeno más específico (ver taxonomia.py).
      const la = new Set(hf.filter((r) => r.es_lavado).map((r) => r.rid));
      et = et.filter((e) => la.has(e.rid)); base = la.size;
    }
    et = et.filter((e) => e.nivel === nivel);
    const g = d3.group(et, (e) => e.item);
    return [...g].map(([item, v]) => {
      const o = { item, base, registrado: 0, extraido_regla: 0, extraido_modelo: 0, inferido: 0 };
      v.forEach((e) => { o[e.origen.replace('í', 'i')] += 1; });
      o.relatos = v.length; o.pct_base = base ? v.length / base : 0; o.conf_media = d3.mean(v, (e) => e.confianza);
      return o;
    }).sort((a, b) => b.relatos - a.relatos);
  },
});

dash.calc('origen_kpi', {
  inputs: ['hf', 'etiquetas'],
  title: 'Etiquetas por origen',
  description: 'Número de etiquetas y confianza media por origen, en el nivel y la confianza mínima elegidos.',
  fn: (hf, etiquetas) => {
    const p = dash.params();
    const nivel = p.nivel || 'fenómeno', cmin = +p.conf || 0;
    const ids = new Set(hf.map((r) => r.rid));
    const et = etiquetas.filter((e) => ids.has(e.rid) && e.nivel === nivel && e.confianza >= cmin);
    return ['registrado', 'extraído_regla', 'extraído_modelo', 'inferido'].map((o) => {
      const v = et.filter((e) => e.origen === o);
      return { origen: o, etiquetas: v.length, conf_media: v.length ? d3.mean(v, (e) => e.confianza) : null };
    });
  },
});

dash.calc('terr', {
  inputs: ['hechos', 'territorio', 'etiquetas'],
  title: 'Territorio y cociente de localización',
  description: 'Relatos por departamento (periodo elegido) y cociente de localización del fenómeno elegido.',
  fn: (hechos, territorio, etiquetas) => {
    const p = dash.params(); const campo = G.mesCampo();
    const fen = p.fen_terr || 'Lavado de activos';
    const ids = new Set(hechos.filter((r) => { const m = r[campo] || r.mes; return m >= (p.desde || '0000') && m <= (p.hasta || '9999'); }).map((r) => r.rid));
    const tr = territorio.filter((t) => ids.has(t.rid));
    const conF = new Set(etiquetas.filter((e) => e.nivel === 'fenómeno' && e.item === fen && e.confianza >= 0.5 && ids.has(e.rid)).map((e) => e.rid));
    const conT = new Set(tr.map((t) => t.rid));
    const N = conT.size, NF = [...conT].filter((r) => conF.has(r)).length;
    const g = d3.group(tr, (t) => t.dpto_cod);
    return [...g].map(([cod, v]) => {
      const rel = new Set(v.map((t) => t.rid)); const nf = [...rel].filter((r) => conF.has(r)).length;
      return { dpto_cod: cod, dpto: v[0].dpto, fenomeno: fen, relatos: rel.size, relatos_fen: nf,
        lq: N && NF ? (nf / rel.size) / (NF / N) : null };
    }).sort((a, b) => b.relatos - a.relatos);
  },
});

dash.calc('kpi_terr', {
  inputs: ['hechos'],
  title: 'Cobertura territorial',
  description: 'Proporción de relatos del periodo con territorio identificado y su origen.',
  fn: (hechos) => {
    const p = dash.params(); const campo = G.mesCampo();
    const h = hechos.filter((r) => { const m = r[campo] || r.mes; return m >= (p.desde || '0000') && m <= (p.hasta || '9999'); });
    const con = h.filter((r) => r.dpto_cod);
    return [{ relatos: h.length, con_territorio: con.length, pct_con_territorio: h.length ? con.length / h.length : null,
      pct_registrado: con.length ? con.filter((r) => r.terr_origen === 'registrado').length / con.length : null }];
  },
});

dash.calc('mpios', {
  inputs: ['hechos'],
  title: 'Relatos por municipio',
  description: 'Relatos del periodo por municipio DIVIPOLA identificado, con coordenadas de la cabecera.',
  fn: (hechos) => {
    const p = dash.params(); const campo = G.mesCampo();
    const h = hechos.filter((r) => { const m = r[campo] || r.mes; return r.mpio_cod && m >= (p.desde || '0000') && m <= (p.hasta || '9999'); });
    return [...d3.group(h, (r) => r.mpio_cod)].map(([cod, v]) => ({ mpio_cod: cod, mpio: v[0].mpio, dpto: v[0].dpto, lat: v[0].lat, lon: v[0].lon, relatos: v.length }))
      .sort((a, b) => b.relatos - a.relatos);
  },
});

dash.calc('lq_matriz', {
  inputs: ['hechos', 'territorio', 'etiquetas'],
  title: 'Matriz de cocientes de localización',
  description: 'Cociente de localización por departamento (8+ relatos) y fenómeno principal, en el periodo elegido.',
  fn: (hechos, territorio, etiquetas) => {
    const p = dash.params(); const campo = G.mesCampo();
    const ids = new Set(hechos.filter((r) => { const m = r[campo] || r.mes; return m >= (p.desde || '0000') && m <= (p.hasta || '9999'); }).map((r) => r.rid));
    const tr = territorio.filter((t) => ids.has(t.rid));
    const conT = new Set(tr.map((t) => t.rid));
    const et = etiquetas.filter((e) => e.nivel === 'fenómeno' && e.confianza >= 0.5 && conT.has(e.rid));
    const fenes = [...d3.rollup(et, (v) => v.length, (e) => e.item)].sort((a, b) => b[1] - a[1]).slice(0, 6).map((d) => d[0]);
    const N = conT.size, out = [];
    const byD = d3.group(tr, (t) => t.dpto);
    fenes.forEach((f) => {
      const conF = new Set(et.filter((e) => e.item === f).map((e) => e.rid));
      byD.forEach((v, dpto) => {
        const rel = new Set(v.map((t) => t.rid)); if (rel.size < 8) return;
        const nf = [...rel].filter((r) => conF.has(r)).length;
        out.push({ dpto, fenomeno: f, relatos_dpto: rel.size, relatos: nf, lq: (nf / rel.size) / (conF.size / N) });
      });
    });
    return out;
  },
});

dash.calc('orgs', {
  inputs: ['hf', 'organizaciones', 'etiquetas'],
  title: 'Perfil de organizaciones',
  description: 'Relatos, origen, confianza y perfil (fenómenos, territorios, mecanismos) por organización identificada.',
  fn: (hf, organizaciones, etiquetas) => {
    const byId = new Map(hf.map((r) => [r.rid, r]));
    const og = organizaciones.filter((o) => byId.has(o.rid) && o.item !== 'Organización mencionada sin nombre');
    const etR = d3.group(etiquetas.filter((e) => byId.has(e.rid) && e.confianza >= 0.5), (e) => e.rid);
    const top = (arr, k) => [...d3.rollup(arr, (v) => v.length, (x) => x)].sort((a, b) => b[1] - a[1]).slice(0, k).map(([x, n]) => `${x} (${n})`).join('; ');
    return [...d3.group(og, (o) => o.item)].map(([org, v]) => {
      const rids = [...new Set(v.map((o) => o.rid))];
      const hs = rids.map((r) => byId.get(r));
      const lab = rids.flatMap((r) => etR.get(r) || []);
      const meses = hs.map((h) => h.mes).sort();
      return { organizacion: org, tipologia: v[0].tipologia, relatos: rids.length,
        registrado: v.filter((o) => o.origen === 'registrado').length, extraido_regla: v.filter((o) => o.origen === 'extraído_regla').length,
        conf_media: d3.mean(v, (o) => o.confianza), pct_genera: d3.mean(hs, (h) => h.genera_caso),
        fenomenos: top(lab.filter((e) => e.nivel === 'fenómeno').map((e) => e.item), 3),
        territorios: top(hs.filter((h) => h.dpto_cod).map((h) => h.dpto), 3) || 'Sin territorio identificado',
        mecanismos: top(lab.filter((e) => e.nivel === 'mecanismo').map((e) => e.item), 3) || '—',
        periodo: meses[0] === meses[meses.length - 1] ? meses[0] : `${meses[0]} a ${meses[meses.length - 1]}` };
    }).sort((a, b) => b.relatos - a.relatos || a.organizacion.localeCompare(b.organizacion));
  },
});

dash.calc('org_kpi', {
  inputs: ['hf', 'organizaciones'],
  title: 'Indicadores de organizaciones',
  description: 'Relatos con organización nombrada, organizaciones distintas, vínculo transnacional y concentración.',
  fn: (hf, organizaciones) => {
    const byId = new Map(hf.map((r) => [r.rid, r]));
    const genericas = ['Organización mencionada sin nombre', 'GDO/GDCO (sin nombre registrado)', 'Disidencias FARC (sin especificar)', 'Carteles mexicanos (sin especificar)'];
    const og = organizaciones.filter((o) => byId.has(o.rid) && o.item !== 'Organización mencionada sin nombre');
    const rids = [...new Set(og.map((o) => o.rid))];
    const n = hf.length;
    const porRid = d3.group(og, (o) => o.rid);
    const trans = rids.filter((r) => byId.get(r).extranjero === 1 || porRid.get(r).some((o) => o.tipologia === 'Transnacional')).length;
    const soloRelato = rids.filter((r) => porRid.get(r).every((o) => o.origen !== 'registrado')).length;
    const cnt = [...d3.rollup(og, (v) => new Set(v.map((o) => o.rid)).size, (o) => o.item)].sort((a, b) => b[1] - a[1]);
    const top3 = new Set(og.filter((o) => cnt.slice(0, 3).some(([k]) => k === o.item)).map((o) => o.rid)).size;
    return [{ relatos_nombrada: rids.length, pct_nombrada: n ? rids.length / n : null,
      orgs_distintas: new Set(og.map((o) => o.item).filter((k) => !genericas.includes(k))).size,
      pct_transnacional: rids.length ? trans / rids.length : null, pct_solo_relato: rids.length ? soloRelato / rids.length : null,
      pct_top3: rids.length ? top3 / rids.length : null }];
  },
});

dash.calc('org_tipo', {
  inputs: ['hf', 'organizaciones'],
  title: 'Organizaciones por tipología',
  description: 'Relatos con organización nombrada por tipología de la organización.',
  fn: (hf, organizaciones) => {
    const ids = new Set(hf.map((r) => r.rid));
    const og = organizaciones.filter((o) => ids.has(o.rid) && o.item !== 'Organización mencionada sin nombre');
    return [...d3.group(og, (o) => o.tipologia)].map(([t, v]) => ({ tipologia: t, relatos: new Set(v.map((o) => o.rid)).size, organizaciones: new Set(v.map((o) => o.item)).size }))
      .sort((a, b) => b.relatos - a.relatos);
  },
});

dash.calc('org_mes', {
  inputs: ['hf', 'organizaciones', 'calidad'],
  title: 'Relatos con organización por mes',
  description: 'Relatos de la selección con al menos una organización nombrada, por mes de ingreso.',
  fn: (hf, organizaciones, calidad) => {
    const p = dash.params(); const campo = G.mesCampo();
    const ids = new Set(hf.map((r) => r.rid));
    const mes = new Map(hf.map((r) => [r.rid, r[campo] || r.mes]));
    const rids = new Set(organizaciones.filter((o) => ids.has(o.rid) && o.item !== 'Organización mencionada sin nombre').map((o) => o.rid));
    const c = d3.rollup([...rids], (v) => v.length, (r) => mes.get(r));
    return calidad.filter((m) => m.mes >= (p.desde || '0000') && m.mes <= (p.hasta || '9999')).map((m) => ({ mes: m.mes, relatos: c.get(m.mes) || 0, estado: m.estado }));
  },
});
