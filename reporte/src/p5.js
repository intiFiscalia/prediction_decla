// Sección 8: Organizaciones criminales
(function () {
  const k = (f, fmt) => (el) => G.text(el, ['org_kpi'], () => { const v = dash.data('org_kpi').data[0][f]; return v == null ? '—' : fmt(v); });
  dash.draw('o_rel', k('relatos_nombrada', G.int));
  dash.draw('o_pct', k('pct_nombrada', G.pct));
  dash.draw('o_dist', k('orgs_distintas', G.int));
  dash.draw('o_trans', k('pct_transnacional', G.pct0));
  dash.draw('o_regla', k('pct_solo_relato', G.pct0));
  dash.draw('o_top3', k('pct_top3', G.pct0));

  dash.draw('org_bar', (el) => {
    if (!G.ready(el, ['orgs'])) return;
    const rows = dash.data('orgs').data;
    G.hbar(el, rows, { label: (r) => r.organizacion, keys: ['registrado', 'extraido_regla'], colors: [G.oc[0], G.oc[1]], aria: 'Relatos por organización',
      end: (r) => `${G.int(r.relatos)} · c=${G.d2(r.conf_media)}`,
      tip: (r) => [r.organizacion, r.tipologia, `${G.int(r.relatos)} relatos`, `registrado ${G.int(r.registrado)} · extraído_regla ${G.int(r.extraido_regla)}`, `Confianza media ${G.d2(r.conf_media)}`] });
  });
  dash.draw('org_tipo', (el) => {
    if (!G.ready(el, ['org_tipo'])) return;
    G.hbar(el, dash.data('org_tipo').data, { label: (r) => r.tipologia, value: 'relatos', colors: [G.oc[3]], aria: 'Relatos por tipología',
      end: (r) => `${G.int(r.relatos)} · ${G.int(r.organizaciones)} org.`, tip: (r) => [r.tipologia, `${G.int(r.relatos)} relatos`, `${G.int(r.organizaciones)} organizaciones o categorías`] });
  });
  dash.draw('org_mes', (el) => {
    if (!G.ready(el, ['org_mes'])) return;
    const rows = dash.data('org_mes').data;
    G.ts(el, { months: rows.map((r) => r.mes), ymax: Math.max(3, d3.max(rows, (r) => r.relatos)), aria: 'Relatos con organización nombrada por mes',
      bars: [{ color: G.oc[3], points: rows.map((r) => ({ mes: r.mes, v: r.relatos, dim: r.estado !== 'completo' })) }],
      tip: (m) => { const r = rows.find((x) => x.mes === m); return [G.mesLargo(m), `${G.int(r.relatos)} relatos con organización`, r.estado]; } });
  });
  dash.draw('org_tabla', (tb) => {
    if (!G.ready(tb, ['orgs'], { tag: 'tr' })) return;
    tb.replaceChildren();
    const rows = dash.data('orgs').data;
    if (!rows.length) return G.emptyRow(tb, 9, 'Sin organizaciones nombradas en la selección.');
    rows.forEach((r) => {
      const tr = document.createElement('tr');
      G.td(tr, r.organizacion); G.td(tr, r.tipologia); G.td(tr, G.int(r.relatos), 1); G.td(tr, G.d2(r.conf_media), 1); G.td(tr, G.pct0(r.pct_genera), 1);
      G.td(tr, r.fenomenos); G.td(tr, r.territorios); G.td(tr, r.mecanismos); G.td(tr, r.periodo);
      tb.appendChild(tr);
    });
  });
})();
