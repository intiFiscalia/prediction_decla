// Sección 3: Territorio
(function () {
  const P = () => dash.params();
  dash.draw('sel_fen_terr', (sel) => {
    const e = dash.data('etiquetas');
    const opts = e.status === 'ok'
      ? [...d3.rollup(e.data.filter((x) => x.nivel === 'fenómeno'), (v) => new Set(v.map((x) => x.rid)).size, (x) => x.item)].sort((a, b) => b[1] - a[1]).map(([k]) => [k, k])
      : [['Lavado de activos', 'Lavado de activos']];
    G.setSel(sel, opts, P().fen_terr || 'Lavado de activos');
    sel.onchange = () => dash.setParams({ fen_terr: sel.value });
  });
  dash.draw('terr_cob', (el) => G.text(el, ['kpi_terr'], () => G.pct(dash.data('kpi_terr').data[0].pct_con_territorio || 0)));
  dash.draw('terr_reg', (el) => G.text(el, ['kpi_terr'], () => G.pct(dash.data('kpi_terr').data[0].pct_registrado || 0)));

  const base = (el, fc) => {
    const w = G.width(el), h = Math.round(Math.min(560, Math.max(360, w * 1.15)));
    const main = { type: 'FeatureCollection', features: fc.features.filter((f) => f.properties.dpto_cod !== '88') };
    const proj = d3.geoMercator().fitExtent([[6, 6], [w - 6, h - 40]], main);
    return { w, h, proj, path: d3.geoPath(proj), main };
  };

  dash.draw('terr_mapa', (el) => {
    if (!G.ready(el, ['terr', 'geo'])) return;
    const fc = dash.data('geo').data, rows = dash.data('terr').data;
    const met = P().metrica || 'relatos';
    const by = new Map(rows.map((r) => [r.dpto_cod, r]));
    const { w, h, path, main } = base(el, fc);
    const svg = G.svg(el, w, h, 'Mapa departamental de relatos registrados');
    const tip = G.tip(el);
    const vmax = d3.max(rows, (r) => r[met] || 0) || 1;
    const lqLog = (v) => Math.min(1, Math.abs(Math.log2(v || 1)) / 2);
    svg.append('g').selectAll('path').data(main.features).join('path').attr('d', path)
      .style('stroke', 'var(--color-border-line)').attr('stroke-width', 0.7)
      .style('fill', (f) => { const r = by.get(f.properties.dpto_cod); if (!r || r.relatos === 0) return 'var(--color-panel)'; if (met === 'lq') return r.lq == null ? 'var(--color-panel)' : r.lq >= 1 ? G.oc[0] : G.oc[2]; return G.oc[0]; })
      .attr('fill-opacity', (f) => { const r = by.get(f.properties.dpto_cod); if (!r || r.relatos === 0) return 1; if (met === 'lq') return r.lq == null ? 1 : 0.12 + 0.85 * lqLog(r.lq); return 0.12 + 0.85 * Math.sqrt((r[met] || 0) / vmax); })
      .on('pointermove', (ev, f) => {
        const r = by.get(f.properties.dpto_cod);
        tip.show(ev, r ? [r.dpto, `${G.int(r.relatos)} relatos con territorio`, `${G.int(r.relatos_fen)} de ${r.fenomeno}`, `CL = ${r.lq == null ? '—' : G.d2(r.lq)}${r.relatos < 5 ? ' (inestable, < 5 relatos)' : ''}`] : [f.properties.nombre, 'Sin relatos en el periodo']);
      }).on('pointerleave', () => tip.hide());
    const lg = svg.append('g').attr('transform', `translate(8,${h - 24})`);
    if (met === 'lq') {
      [[0.25, G.oc[2]], [0.5, G.oc[2]], [1, G.oc[0]], [2, G.oc[0]], [4, G.oc[0]]].forEach(([v, c], i) => {
        lg.append('rect').attr('x', i * 46).attr('width', 44).attr('height', 8).style('fill', c).attr('fill-opacity', v === 1 ? 0.12 : 0.12 + 0.85 * lqLog(v));
        lg.append('text').attr('x', i * 46).attr('y', 20).text('CL ' + G.d2(v).replace(',00', ''));
      });
    } else {
      [0, 0.25, 0.5, 1].forEach((q, i) => {
        lg.append('rect').attr('x', i * 46).attr('width', 44).attr('height', 8).style('fill', G.oc[0]).attr('fill-opacity', 0.12 + 0.85 * Math.sqrt(q));
        lg.append('text').attr('x', i * 46).attr('y', 20).text(G.int(Math.round(q * vmax)));
      });
    }
  });

  dash.draw('terr_mpio', (el) => {
    if (!G.ready(el, ['mpios', 'geo'])) return;
    const fc = dash.data('geo').data, rows = dash.data('mpios').data;
    const { w, h, proj, path, main } = base(el, fc);
    const svg = G.svg(el, w, h, 'Relatos por municipio');
    const tip = G.tip(el);
    svg.append('g').selectAll('path').data(main.features).join('path').attr('d', path).style('fill', 'var(--color-panel)').style('stroke', 'var(--color-border-line)').attr('stroke-width', 0.7);
    const r = d3.scaleSqrt().domain([0, d3.max(rows, (d) => d.relatos) || 1]).range([0, Math.min(26, w / 18)]);
    const pts = rows.filter((d) => d.lat != null && d.mpio_cod.slice(0, 2) !== '88');
    svg.append('g').selectAll('circle').data(pts).join('circle')
      .attr('cx', (d) => proj([d.lon, d.lat])[0]).attr('cy', (d) => proj([d.lon, d.lat])[1]).attr('r', (d) => Math.max(2.5, r(d.relatos)))
      .style('fill', G.oc[0]).attr('fill-opacity', 0.55).style('stroke', G.oc[0])
      .on('pointermove', (ev, d) => tip.show(ev, [`${d.mpio} (${d.mpio_cod})`, d.dpto, `${G.int(d.relatos)} relatos`])).on('pointerleave', () => tip.hide());
    svg.append('g').selectAll('text').data(pts.slice(0, 6)).join('text').attr('class', 'lbl')
      .attr('x', (d) => proj([d.lon, d.lat])[0] + Math.max(2.5, r(d.relatos)) + 3).attr('y', (d) => proj([d.lon, d.lat])[1] + 4)
      .text((d) => `${d.mpio} ${G.int(d.relatos)}`);
  });

  dash.draw('terr_lq', (el) => {
    if (!G.ready(el, ['lq_matriz'])) return;
    const rows = dash.data('lq_matriz').data;
    el.replaceChildren();
    if (!rows.length) { const p = document.createElement('p'); p.className = 'gic-note'; p.textContent = 'Ningún departamento tiene 8 o más relatos en el periodo.'; el.appendChild(p); return; }
    const fenes = [...new Set(rows.map((r) => r.fenomeno))];
    const dptos = [...d3.rollup(rows, (v) => v[0].relatos_dpto, (r) => r.dpto)].sort((a, b) => b[1] - a[1]);
    const t = document.createElement('table'); t.className = 'gic-table gic-heat';
    const hr = document.createElement('tr');
    const th0 = document.createElement('th'); th0.textContent = 'Departamento (relatos)'; hr.appendChild(th0);
    fenes.forEach((f) => { const th = document.createElement('th'); th.textContent = f; hr.appendChild(th); });
    const thead = document.createElement('thead'); thead.appendChild(hr); t.appendChild(thead);
    const tb = document.createElement('tbody');
    dptos.forEach(([d, n]) => {
      const tr = document.createElement('tr');
      G.td(tr, `${d} (${G.int(n)})`);
      fenes.forEach((f) => {
        const r = rows.find((x) => x.dpto === d && x.fenomeno === f);
        const td = G.td(tr, r ? '' : '—', 1);
        if (r) {
          const wh = `dpto=${encodeURIComponent(d)}&fenomeno=${encodeURIComponent(f)}`;
          const a1 = document.createElement('span'); a1.textContent = G.d2(r.lq); Object.assign(a1.dataset, { source: 'lq_matriz', field: 'lq', where: wh });
          const a2 = document.createElement('span'); a2.textContent = G.int(r.relatos); Object.assign(a2.dataset, { source: 'lq_matriz', field: 'relatos', where: wh });
          td.append(a1, ' (', a2, ')');
          const a = Math.min(1, Math.abs(Math.log2(r.lq || 0.25)) / 2);
          td.style.background = `color-mix(in srgb, ${r.lq >= 1 ? G.oc[0] : G.oc[2]} ${Math.round(a * 45)}%, transparent)`;
          if (r.relatos < 5) td.style.opacity = '0.6';
        }
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb); el.appendChild(t);
  });
})();
