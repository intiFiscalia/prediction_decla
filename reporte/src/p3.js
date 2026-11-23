// Secciones 4 (Sectores) y 5 (Red)
(function () {
  const P = () => dash.params();
  dash.draw('sel_fen_sector', (sel) => {
    const a = dash.data('asociaciones');
    const opts = a.status === 'ok' ? [...new Set(a.data.map((r) => r.fenomeno))].sort().map((k) => [k, k]) : [];
    G.setSel(sel, opts, P().fen_sector || 'Captación masiva e ilegal');
    sel.onchange = () => dash.setParams({ fen_sector: sel.value });
  });

  dash.draw('sec_forest', (el) => {
    if (!G.ready(el, ['asociaciones'])) return;
    const fen = P().fen_sector || 'Captación masiva e ilegal';
    const rows = dash.data('asociaciones').data.filter((r) => r.fenomeno === fen).sort((a, b) => b.or - a.or);
    const w = G.width(el), rowH = 24, top = 22, h = top + rows.length * rowH + 30;
    const svg = G.svg(el, w, h, `Razón de momios por sector para ${fen}`);
    const lw = Math.min(w * 0.42, G.measure(svg, rows.map((r) => r.sector)) + 10);
    const ew = G.measure(svg, rows.map((r) => `OR ${G.d2(r.or)} · q ${G.p(r.q_bh)}`)) + 10;
    const lo = d3.min(rows, (r) => r.ic_inf) || 0.1, hi = d3.max(rows, (r) => r.ic_sup) || 10;
    const x = d3.scaleLog().domain([Math.min(0.05, lo), Math.max(20, hi)]).range([lw, Math.max(lw + 60, w - ew)]).clamp(true);
    const ticks = [0.05, 0.1, 0.25, 0.5, 1, 2, 4, 10, 25, 50, 100, 200].filter((t) => t >= x.domain()[0] && t <= x.domain()[1]);
    svg.append('g').attr('class', 'grid').selectAll('line').data(ticks).join('line').attr('x1', x).attr('x2', x).attr('y1', top - 6).attr('y2', h - 24);
    svg.append('g').attr('class', 'axis').selectAll('text').data(ticks).join('text').attr('x', x).attr('y', h - 8).attr('text-anchor', 'middle').text((t) => String(t).replace('.', ','));
    svg.append('line').attr('x1', x(1)).attr('x2', x(1)).attr('y1', top - 10).attr('y2', h - 24).style('stroke', 'var(--cds-chart-reference)').attr('stroke-width', 1.5);
    svg.append('text').attr('x', x(1) + 4).attr('y', top - 10).text('OR = 1');
    const tip = G.tip(el);
    rows.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2;
      const sig = r.q_bh < 0.05;
      svg.append('text').attr('class', 'lbl').attr('x', lw - 6).attr('y', y + 4).attr('text-anchor', 'end').text(G.trunc(r.sector, lw));
      svg.append('line').attr('x1', x(r.ic_inf)).attr('x2', x(r.ic_sup)).attr('y1', y).attr('y2', y).style('stroke', G.oc[0]).attr('stroke-width', 1.5);
      svg.append('circle').attr('cx', x(r.or)).attr('cy', y).attr('r', 5).style('fill', sig ? G.oc[0] : 'var(--color-bg)').style('stroke', G.oc[0]).attr('stroke-width', 1.5);
      svg.append('text').attr('x', x.range()[1] + 6).attr('y', y + 4).text(`OR ${G.d2(r.or)} · q ${G.p(r.q_bh)}`);
      svg.append('rect').attr('x', 0).attr('y', y - rowH / 2).attr('width', w).attr('height', rowH).style('fill', 'transparent')
        .on('pointermove', (ev) => tip.show(ev, [`${r.fenomeno} × ${r.sector}`, `${G.int(r.n_ambos)} relatos con ambos (esperado ${G.d2(r.esperado)})`,
          `OR ${G.d2(r.or)} (IC95 ${G.d2(r.ic_inf)}–${G.d2(r.ic_sup)})`, `p = ${G.p(r.p)} · q (BH) = ${G.p(r.q_bh)}`, r.significativo]))
        .on('pointerleave', () => tip.hide());
    });
  });

  dash.draw('sec_tabla', (tb) => {
    if (!G.ready(tb, ['asociaciones'], { tag: 'tr' })) return;
    tb.replaceChildren();
    const rows = dash.data('asociaciones').data.filter((r) => r.q_bh < 0.05);
    if (!rows.length) return G.emptyRow(tb, 9, 'Ningún par supera la corrección por comparaciones múltiples.');
    rows.forEach((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = G.key(r.fenomeno, r.sector);
      G.td(tr, r.fenomeno); G.td(tr, r.sector); G.td(tr, G.int(r.n_ambos), 1); G.td(tr, G.d2(r.esperado), 1); G.td(tr, G.d2(r.or), 1);
      G.td(tr, G.d2(r.ic_inf), 1); G.td(tr, G.d2(r.ic_sup), 1); G.td(tr, G.p(r.p), 1); G.td(tr, G.p(r.q_bh), 1);
      tb.appendChild(tr);
    });
  });

  dash.draw('red_grafo', (el) => {
    if (!G.ready(el, ['red_nodos', 'red_aristas'])) return;
    const nodes = dash.data('red_nodos').data, edges = dash.data('red_aristas').data;
    const w = G.width(el), h = Math.round(Math.max(460, Math.min(720, w * 0.75)));
    const svg = G.svg(el, w, h, 'Red de co-ocurrencias entre actividad, mecanismo, bien y lugar');
    svg.style('cursor', 'grab');
    const pad = 60;
    const x = d3.scaleLinear().domain(d3.extent(nodes, (n) => n.x)).range([pad, w - pad]);
    const y = d3.scaleLinear().domain(d3.extent(nodes, (n) => n.y)).range([30, h - 30]);
    const by = new Map(nodes.map((n) => [n.id, n]));
    const r = d3.scaleSqrt().domain([0, d3.max(nodes, (n) => n.n)]).range([3, Math.min(22, w / 40)]);
    const sw = d3.scaleLinear().domain([3, d3.max(edges, (e) => e.n) || 3]).range([0.6, 5]);
    const tip = G.tip(el);
    const layer = svg.append('g');
    const eg = layer.append('g').selectAll('line').data(edges).join('line')
      .attr('x1', (e) => x(by.get(e.source).x)).attr('y1', (e) => y(by.get(e.source).y)).attr('x2', (e) => x(by.get(e.target).x)).attr('y2', (e) => y(by.get(e.target).y))
      .style('stroke', 'var(--cds-chart-axis)').attr('stroke-width', (e) => sw(e.n)).attr('stroke-opacity', 0.45);
    const ng = layer.append('g').selectAll('circle').data(nodes).join('circle').attr('cx', (n) => x(n.x)).attr('cy', (n) => y(n.y)).attr('r', (n) => r(n.n))
      .style('fill', (n) => G.tc[n.tipo]).style('stroke', 'var(--color-bg)').attr('stroke-width', 1);
    const big = nodes.slice().sort((a, b) => b.n - a.n).slice(0, Math.max(8, Math.floor(w / 60)));
    const lab = layer.append('g').selectAll('text').data(big).join('text').attr('class', 'lbl').attr('x', (n) => x(n.x) + r(n.n) + 3).attr('y', (n) => y(n.y) + 4)
      .text((n) => n.label.replace(/^[A-Z] · /, ''));
    ng.on('pointermove', (ev, n) => {
      const nb = new Set([n.id]); edges.forEach((e) => { if (e.source === n.id) nb.add(e.target); if (e.target === n.id) nb.add(e.source); });
      ng.attr('opacity', (m) => (nb.has(m.id) ? 1 : 0.15)); eg.attr('stroke-opacity', (e) => (e.source === n.id || e.target === n.id ? 0.9 : 0.05)); lab.attr('opacity', (m) => (nb.has(m.id) ? 1 : 0.2));
      const top3 = edges.filter((e) => e.source === n.id || e.target === n.id).sort((a, b) => b.n - a.n).slice(0, 3)
        .map((e) => `${by.get(e.source === n.id ? e.target : e.source).label}: ${G.int(e.n)} (lift ${G.d2(e.lift)})`);
      tip.show(ev, [`${n.label} · ${n.tipo}`, `${G.int(n.n)} relatos · grado ${n.grado} · comunidad ${n.comunidad}`, `Intermediación ${G.d3(n.intermediacion)}`, ...top3]);
    }).on('pointerleave', () => { ng.attr('opacity', 1); eg.attr('stroke-opacity', 0.45); lab.attr('opacity', 1); tip.hide(); });

    const zoom = d3.zoom().scaleExtent([1, 10]).translateExtent([[0, 0], [w, h]])
      .on('zoom', (ev) => layer.attr('transform', ev.transform))
      .on('start', () => svg.style('cursor', 'grabbing')).on('end', () => svg.style('cursor', 'grab'));
    svg.call(zoom).on('dblclick.zoom', null).on('dblclick', () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity));
    const bar = d3.select(el).append('div').attr('class', 'gic-legend');
    bar.append('span').text('Rueda o pellizco: acercar · Arrastrar: mover · Doble clic: restablecer');
    bar.append('button').attr('type', 'button').attr('class', 'gic-btn').text('Restablecer zoom')
      .on('click', () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity));
  });

  dash.draw('red_reglas', (tb) => {
    if (!G.ready(tb, ['reglas'], { tag: 'tr' })) return;
    tb.replaceChildren();
    const seen = new Set();
    dash.data('reglas').data.filter((r) => { const k = r.antecedente + '|' + r.consecuente; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 20).forEach((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = G.key(r.antecedente, r.consecuente);
      G.td(tr, `${r.antecedente} (${r.tipo_a})`); G.td(tr, `${r.consecuente} (${r.tipo_c})`); G.td(tr, G.int(r.n), 1); G.td(tr, G.pct(r.soporte), 1); G.td(tr, G.pct(r.confianza), 1); G.td(tr, G.d2(r.lift), 1);
      tb.appendChild(tr);
    });
  });
})();
