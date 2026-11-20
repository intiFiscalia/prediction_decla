// Filtros, pestañas, impresión; secciones 1 (Indicadores) y 2 (Fenómenos)
(function () {
  const P = () => dash.params();
  const meses = () => dash.data('calidad').data.map((m) => m.mes);

  dash.draw('f_desde', (sel) => {
    if (dash.data('calidad').status !== 'ok') return;
    G.setSel(sel, meses().map((m) => [m, G.mesLargo(m)]), P().desde || meses()[0]);
    sel.onchange = () => dash.setParams({ desde: sel.value });
  });
  dash.draw('f_hasta', (sel) => {
    if (dash.data('calidad').status !== 'ok') return;
    const ms = meses();
    G.setSel(sel, ms.map((m) => [m, G.mesLargo(m)]), P().hasta || ms[ms.length - 1]);
    sel.onchange = () => dash.setParams({ hasta: sel.value });
  });
  dash.draw('f_dpto', (sel) => {
    const h = dash.data('hechos');
    const opts = [['', 'Todos los territorios']];
    if (h.status === 'ok') {
      [...d3.rollup(h.data.filter((r) => r.dpto_cod), (v) => v[0].dpto, (r) => r.dpto_cod)].sort((a, b) => a[1].localeCompare(b[1])).forEach(([c, n]) => opts.push([c, n]));
    }
    G.setSel(sel, opts, P().dpto || '');
    sel.onchange = () => dash.setParams({ dpto: sel.value || '' });
  });
  document.querySelectorAll('#f-reset').forEach((b) => b.addEventListener('click', () => dash.resetParams()));

  dash.draw('rango_txt', (el) => G.text(el, ['kpi'], () => {
    const k = dash.data('kpi').data[0];
    return k.desde ? `${G.mesLargo(k.desde)} a ${G.mesLargo(k.hasta)}` + (P().dpto ? ' en el territorio elegido' : '') : 'periodo sin relatos';
  }));

  // Pestañas
  const tabs = [...document.querySelectorAll('.gic-tabs [data-tab]')];
  const secs = [...document.querySelectorAll('[data-sec]')];
  function open(id) {
    if (!secs.some((s) => s.id === id)) id = 'indicadores';
    secs.forEach((s) => { s.hidden = s.id !== id; });
    tabs.forEach((t) => t.setAttribute('aria-selected', t.dataset.tab === id ? 'true' : 'false'));
    dash.setLink(id);
  }
  tabs.forEach((t) => t.addEventListener('click', () => open(t.dataset.tab)));
  open((location.hash || '').slice(1) || 'indicadores');
  let abierta = null;
  window.addEventListener('beforeprint', () => { if (abierta == null) abierta = (secs.find((s) => !s.hidden) || {}).id; secs.forEach((s) => { s.hidden = false; }); });
  window.addEventListener('afterprint', () => { if (abierta) open(abierta); abierta = null; });

  // Selects locales que usan parámetros
  const bindSel = (id, name, def) => document.querySelectorAll('#' + id).forEach((sel) => {
    sel.value = String(P()[name] ?? def);
    sel.addEventListener('change', () => dash.setParams({ [name]: sel.value }));
  });
  bindSel('sel-nivel', 'nivel', 'fenómeno');
  bindSel('sel-conf', 'conf', '0.5');
  bindSel('sel-metrica', 'metrica', 'relatos');
  bindSel('sel-modelo', 'modelo_pron', 'auto');
  bindSel('sel-dim', 'dim', 'Entidad remitente');
  dash.onData(() => {
    [['sel-nivel', 'nivel', 'fenómeno'], ['sel-conf', 'conf', '0.5'], ['sel-metrica', 'metrica', 'relatos'], ['sel-modelo', 'modelo_pron', 'auto'], ['sel-dim', 'dim', 'Entidad remitente']]
      .forEach(([id, n, d]) => document.querySelectorAll('#' + id).forEach((s) => { if (document.activeElement !== s) s.value = String(P()[n] ?? d); }));
  });

  // KPIs
  const k = (f, fmt) => (el) => G.text(el, ['kpi'], () => { const v = dash.data('kpi').data[0][f]; return v == null ? '—' : fmt(v); });
  dash.draw('k_total', k('total', G.int));
  dash.draw('k_total_lede', k('total', G.int));
  dash.draw('k_prom', k('prom_mensual', G.d1));
  dash.draw('k_meses', k('meses', G.int));
  dash.draw('k_spoa', k('pct_spoa', G.pct));
  dash.draw('k_spoa_lede', k('pct_spoa', G.pct));
  dash.draw('k_genera', k('pct_genera', G.pct));
  dash.draw('k_indag', k('pct_indagacion', G.pct));
  dash.draw('k_dias', k('mediana_dias', (v) => G.d1(v)));

  dash.draw('ind_serie', (el) => {
    if (!G.ready(el, ['serie_mes'])) return;
    const rows = dash.data('serie_mes').data;
    const ms = rows.map((r) => r.mes);
    G.ts(el, {
      months: ms, ymax: d3.max(rows, (r) => r.relatos) || 5, aria: 'Relatos registrados por mes de ingreso',
      bars: [{ color: G.oc[0], points: rows.map((r) => ({ mes: r.mes, v: r.relatos, dim: r.estado !== 'completo' })) }],
      tip: (m) => { const r = rows.find((x) => x.mes === m); return [G.mesLargo(m), `${G.int(r.relatos)} relatos`, r.estado]; },
    });
  });

  const distChart = (dim, maxRows) => (el) => {
    if (!G.ready(el, ['dist'])) return;
    const rows = dash.data('dist').data.filter((r) => r.dimension === dim).slice(0, maxRows);
    G.hbar(el, rows, { label: (r) => r.categoria, value: 'relatos', end: (r) => `${G.int(r.relatos)} · ${G.pct(r.pct)}`,
      tip: (r) => [r.categoria, `${G.int(r.relatos)} relatos`, `${G.pct(r.pct)} de la selección`], aria: `Relatos por ${dim}` });
  };
  dash.draw('ind_delito', distChart('Delito (SPOA)', 10));
  dash.draw('ind_etapa', distChart('Etapa procesal', 10));
  dash.draw('ind_dpto', distChart('Departamento', 12));
  dash.draw('ind_otra', (el) => distChart(P().dim || 'Entidad remitente', 12)(el));

  // Sección 2
  dash.draw('fen_origen', (el) => {
    if (!G.ready(el, ['origen_kpi'])) return;
    el.replaceChildren();
    dash.data('origen_kpi').data.forEach((r, i) => {
      const c = document.createElement('div'); c.className = 'gic-card';
      const a = document.createElement('div'); a.className = 'gic-kl'; a.textContent = `Etiquetas ${r.origen}`;
      const b = document.createElement('div'); b.className = 'gic-kv'; b.textContent = G.int(r.etiquetas);
      b.dataset.source = 'origen_kpi'; b.dataset.field = 'etiquetas'; b.dataset.row = String(i);
      const s = document.createElement('div'); s.className = 'gic-ks';
      const sp = document.createElement('span'); sp.textContent = r.conf_media == null ? '—' : G.d2(r.conf_media);
      sp.dataset.source = 'origen_kpi'; sp.dataset.field = 'conf_media'; sp.dataset.row = String(i);
      s.append('Confianza media ', sp);
      c.style.borderTop = `3px solid ${G.oc[i]}`;
      c.append(a, b, s); el.appendChild(c);
    });
  });
  dash.draw('fen_base', (el) => G.text(el, ['fen_dist'], () => { const d = dash.data('fen_dist').data; return d.length ? G.int(d[0].base) : '0'; }));
  dash.draw('fen_chart', (el) => {
    if (!G.ready(el, ['fen_dist'])) return;
    const rows = dash.data('fen_dist').data;
    G.hbar(el, rows, { label: (r) => r.item, keys: G.ORIGK, colors: G.oc, max: d3.max(rows, (r) => r.relatos),
      end: (r) => `${G.pct(r.pct_base)} · c=${G.d2(r.conf_media)}`, aria: 'Relatos por categoría y origen',
      tip: (r, k) => [r.item, `${G.int(r.relatos)} relatos (${G.pct(r.pct_base)} de la base)`, `${G.ORIG[G.ORIGK.indexOf(k)]}: ${G.int(r[k])}`, `Confianza media ${G.d2(r.conf_media)}`] });
  });
  dash.draw('fen_modelo', (tb) => {
    if (!G.ready(tb, ['modelo'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('modelo').data.forEach((r) => {
      const tr = document.createElement('tr');
      G.td(tr, r.fenomeno); G.td(tr, G.int(r.positivos_registrados), 1); G.td(tr, G.d2(r.precision_cv), 1); G.td(tr, G.d2(r.sensibilidad_cv), 1); G.td(tr, G.int(r.etiquetas_aportadas), 1);
      tb.appendChild(tr);
    });
  });
})();
