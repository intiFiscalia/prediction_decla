// Sección 9: Predicciones adicionales
(function () {
  const P = () => dash.params();
  const ev = (i) => dash.data('pc_eval').data[i].valor;
  const k = (i, fmt) => (el) => G.text(el, ['pc_eval'], () => fmt(ev(i)));
  const k100 = (i) => (el) => G.text(el, ['pc_eval'], () => G.int(dash.data('pc_eval').data[i].de_100));
  dash.draw('pc_auc', k100(3));
  dash.draw('pc_auc_s', k100(2));
  dash.draw('pc_base', k(1, G.pct0));
  dash.draw('pc_n', k(0, G.int));

  dash.draw('pc_cal', (el) => {
    if (!G.ready(el, ['pc_cal'])) return;
    const rows = dash.data('pc_cal').data;
    const w = G.width(el), h = 240, m = { t: 14, r: 10, b: 40, l: 40 };
    const svg = G.svg(el, w, h, 'Probabilidad predicha frente a tasa real por grupo');
    const x = d3.scaleBand().domain(rows.map((r) => r.grupo)).range([m.l, w - m.r]).padding(0.3);
    const y = d3.scaleLinear().domain([0, 1]).range([h - m.b, m.t]);
    svg.append('g').attr('class', 'grid').selectAll('line').data([0, 0.25, 0.5, 0.75, 1]).join('line').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y).attr('y2', y);
    svg.append('g').attr('class', 'axis').selectAll('text').data([0, 0.25, 0.5, 0.75, 1]).join('text').attr('x', m.l - 6).attr('y', (d) => y(d) + 4).attr('text-anchor', 'end').text(G.pct0);
    const bw = x.bandwidth() / 2;
    const tip = G.tip(el);
    rows.forEach((r) => {
      const x0 = x(r.grupo);
      svg.append('rect').attr('x', x0).attr('width', bw - 2).attr('y', y(r.prob_predicha)).attr('height', y(0) - y(r.prob_predicha)).attr('rx', 2).style('fill', 'var(--cds-chart-muted)');
      svg.append('rect').attr('x', x0 + bw).attr('width', bw - 2).attr('y', y(r.tasa_real)).attr('height', y(0) - y(r.tasa_real)).attr('rx', 2).style('fill', G.oc[0]);
      svg.append('line').attr('x1', x0 + bw * 1.5 - 1).attr('x2', x0 + bw * 1.5 - 1).attr('y1', y(r.ic_inf)).attr('y2', y(r.ic_sup)).style('stroke', 'var(--color-fg)');
      svg.append('text').attr('x', x0 + x.bandwidth() / 2).attr('y', h - 22).attr('text-anchor', 'middle').text(r.grupo.replace('Quintil ', 'Grupo '));
      svg.append('text').attr('x', x0 + bw * 1.5).attr('y', y(r.tasa_real) - 4).attr('text-anchor', 'middle').attr('class', 'lbl').text(G.pct0(r.tasa_real));
      svg.append('rect').attr('x', x0).attr('width', x.bandwidth()).attr('y', m.t).attr('height', h - m.b - m.t).style('fill', 'transparent')
        .on('pointermove', (ev2) => tip.show(ev2, [`${r.grupo.replace('Quintil ', 'Grupo ')} (${G.int(r.relatos)} relatos)`, `El modelo predijo en promedio ${G.pct0(r.prob_predicha)}`, `En realidad generó caso el ${G.pct0(r.tasa_real)} (IC95 ${G.pct0(r.ic_inf)}–${G.pct0(r.ic_sup)})`]))
        .on('pointerleave', () => tip.hide());
    });
    svg.append('text').attr('x', m.l).attr('y', h - 4).text('Del grupo con menor probabilidad predicha (1) al de mayor (5)');
  });

  document.querySelectorAll('#sel-rasgo').forEach((sel) => {
    sel.value = P().rasgo || 'Tipo de entrada';
    sel.addEventListener('change', () => dash.setParams({ rasgo: sel.value }));
  });
  dash.draw('pc_rasgos', (el) => {
    if (!G.ready(el, ['pc_rasgos', 'pc_eval'])) return;
    const dim = P().rasgo || 'Tipo de entrada', base = ev(1);
    const rows = dash.data('pc_rasgos').data.filter((r) => r.dimension === dim).sort((a, b) => b.tasa - a.tasa);
    const w = G.width(el), rowH = 24, top = 20, h = top + rows.length * rowH + 26;
    const svg = G.svg(el, w, h, `Tasa de generar caso por ${dim}`);
    const lw = Math.min(w * 0.45, G.measure(svg, rows.map((r) => r.categoria)) + 10);
    const x = d3.scaleLinear().domain([0, 1]).range([lw, w - 60]);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { svg.append('line').attr('class', 'g').attr('x1', x(t)).attr('x2', x(t)).attr('y1', top - 4).attr('y2', h - 22).style('stroke', 'var(--cds-chart-grid)'); svg.append('text').attr('x', x(t)).attr('y', h - 6).attr('text-anchor', 'middle').text(G.pct0(t)); });
    svg.append('line').attr('x1', x(base)).attr('x2', x(base)).attr('y1', top - 10).attr('y2', h - 22).style('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 3');
    svg.append('text').attr('x', x(base) + 4).attr('y', top - 8).text(`promedio ${G.pct0(base)}`);
    const tip = G.tip(el);
    rows.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2;
      svg.append('text').attr('class', 'lbl').attr('x', lw - 6).attr('y', y + 4).attr('text-anchor', 'end').text(G.trunc(r.categoria, lw));
      svg.append('line').attr('x1', x(r.ic_inf)).attr('x2', x(r.ic_sup)).attr('y1', y).attr('y2', y).style('stroke', G.oc[0]).attr('stroke-width', 1.5);
      svg.append('circle').attr('cx', x(r.tasa)).attr('cy', y).attr('r', 5).style('fill', G.oc[0]);
      svg.append('text').attr('x', x(r.ic_sup) + 6).attr('y', y + 4).text(`${G.pct0(r.tasa)} (${G.int(r.relatos)})`);
      svg.append('rect').attr('x', 0).attr('y', y - rowH / 2).attr('width', w).attr('height', rowH).style('fill', 'transparent')
        .on('pointermove', (e) => tip.show(e, [r.categoria, `Generó caso el ${G.pct0(r.tasa)} de ${G.int(r.relatos)} relatos`, `IC95 ${G.pct0(r.ic_inf)}–${G.pct0(r.ic_sup)}`, `${r.diferencia >= 0 ? '+' : '−'}${G.int(Math.round(Math.abs(r.diferencia) * 100))} puntos frente al promedio`]))
        .on('pointerleave', () => tip.hide());
    });
  });

  dash.draw('pt_curvas', (el) => {
    if (!G.ready(el, ['pt_curvas'])) return;
    const rows = dash.data('pt_curvas').data;
    const grupos = [...new Set(rows.map((r) => r.grupo))];
    const w = G.width(el), h = 280, m = { t: 12, r: 12, b: 30, l: 42 };
    const svg = G.svg(el, w, h, 'Porcentaje de relatos cerrados según días desde la recepción');
    const x = d3.scaleLinear().domain([0, 365]).range([m.l, w - m.r]);
    const y = d3.scaleLinear().domain([0, 1]).range([h - m.b, m.t]);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { svg.append('line').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--cds-chart-grid)'); svg.append('text').attr('x', m.l - 6).attr('y', y(t) + 4).attr('text-anchor', 'end').text(G.pct0(t)); });
    [0, 30, 90, 180, 270, 365].forEach((t) => svg.append('text').attr('x', x(t)).attr('y', h - 10).attr('text-anchor', 'middle').text(`${t} d`));
    const col = (g, i) => (g === 'Todos los relatos' ? 'var(--color-fg)' : (dash.colors || G.oc)[i % (dash.colors || G.oc).length]);
    grupos.forEach((g, i) => {
      const pts = rows.filter((r) => r.grupo === g);
      svg.append('path').datum(pts).attr('d', d3.line().x((p) => x(p.dias)).y((p) => y(p.pct_cerrado)).curve(d3.curveStepAfter))
        .style('fill', 'none').style('stroke', col(g, i)).attr('stroke-width', g === 'Todos los relatos' ? 2.5 : 1.5).attr('stroke-dasharray', g === 'Todos los relatos' ? '5 3' : null);
    });
    const lg = d3.select(el).append('div').attr('class', 'gic-legend');
    grupos.forEach((g, i) => { const s = lg.append('span'); s.append('i').attr('class', 'sw').style('background', col(g, i)); s.append('span').text(g); });
    const tip = G.tip(el);
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', w - m.l - m.r).attr('height', h - m.t - m.b).style('fill', 'transparent')
      .on('pointermove', (e) => {
        const [px] = d3.pointer(e); const d = Math.max(0, Math.min(365, Math.round(x.invert(px) / 5) * 5));
        tip.show(e, [`A los ${d} días ya se había cerrado:`, ...grupos.map((g) => `${g}: ${G.pct0((rows.find((r) => r.grupo === g && r.dias === d) || {}).pct_cerrado || 0)}`)]);
      }).on('pointerleave', () => tip.hide());
  });

  const dias = (v) => (v == null ? 'más de lo observado' : G.int(Math.round(v)));
  dash.draw('pt_tabla', (tb) => {
    if (!G.ready(tb, ['pt_resumen'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('pt_resumen').data.forEach((r) => {
      const tr = document.createElement('tr');
      G.td(tr, r.grupo); G.td(tr, G.int(r.relatos), 1); G.td(tr, dias(r.mediana_dias), 1);
      G.td(tr, `${dias(r.dias_p25)} a ${dias(r.dias_p75)}`, 1); G.td(tr, G.pct0(r.pct_cerrado_30), 1); G.td(tr, G.pct0(r.pct_cerrado_90), 1); G.td(tr, G.int(r.abiertos), 1);
      tb.appendChild(tr);
    });
  });
  const te = (i, f) => (el) => G.text(el, ['pt_eval'], () => G.d1(dash.data('pt_eval').data[i][f]));
  dash.draw('pt_err_g', te(0, 'error_mediano_dias'));
  dash.draw('pt_err_0', te(1, 'error_mediano_dias'));

  dash.draw('pa_tabla', (tb) => {
    if (!G.ready(tb, ['p_abiertos'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('p_abiertos').data.forEach((r) => {
      const tr = document.createElement('tr');
      G.td(tr, r.id_entrada); G.td(tr, G.mesLargo(r.mes_ingreso)); G.td(tr, r.tipo_entrada); G.td(tr, r.entidad_remite); G.td(tr, r.fenomeno_principal);
      G.td(tr, r.decision_actual);
      G.td(tr, r.prob_genera_caso == null ? 'ya decidido' : G.pct0(r.prob_genera_caso), 1);
      G.td(tr, G.int(r.dias_transcurridos), 1);
      G.td(tr, r.dias_restantes_estimados == null ? 'sin estimación (ya supera lo observado)' : G.int(r.dias_restantes_estimados), 1);
      tb.appendChild(tr);
    });
  });

  dash.draw('p_compo', (el) => {
    if (!G.ready(el, ['p_compo'])) return;
    const rows = dash.data('p_compo').data;
    const w = G.width(el), rowH = 26, top = 8, h = top + rows.length * rowH + 26;
    const svg = G.svg(el, w, h, 'Proporción esperada de relatos por fenómeno');
    const lw = Math.min(w * 0.45, G.measure(svg, rows.map((r) => r.fenomeno)) + 10);
    const x = d3.scaleLinear().domain([0, 1]).range([lw, w - 120]);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { svg.append('line').attr('x1', x(t)).attr('x2', x(t)).attr('y1', top).attr('y2', h - 22).style('stroke', 'var(--cds-chart-grid)'); svg.append('text').attr('x', x(t)).attr('y', h - 6).attr('text-anchor', 'middle').text(G.pct0(t)); });
    const tip = G.tip(el);
    rows.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2;
      svg.append('text').attr('class', 'lbl').attr('x', lw - 6).attr('y', y + 4).attr('text-anchor', 'end').text(G.trunc(r.fenomeno, lw));
      svg.append('rect').attr('x', x(0)).attr('y', y - 7).attr('height', 14).attr('width', x(r.pct_12m) - x(0)).attr('rx', 2).style('fill', G.oc[0]).attr('opacity', 0.85);
      svg.append('line').attr('x1', x(r.ic_inf)).attr('x2', x(r.ic_sup)).attr('y1', y).attr('y2', y).style('stroke', 'var(--color-fg)');
      if (r.pct_previo != null) svg.append('path').attr('d', d3.symbol().type(d3.symbolDiamond).size(50)()).attr('transform', `translate(${x(r.pct_previo)},${y})`).style('fill', 'var(--color-fg-muted)');
      const c = r.cambio_pp == null ? '' : ` (${r.cambio_pp >= 0 ? '+' : '−'}${G.int(Math.round(Math.abs(r.cambio_pp) * 100))} pp)`;
      svg.append('text').attr('x', x(Math.max(r.ic_sup, r.pct_previo || 0)) + 6).attr('y', y + 4).text(`${G.pct0(r.pct_12m)}${c}`);
      svg.append('rect').attr('x', 0).attr('y', y - rowH / 2).attr('width', w).attr('height', rowH).style('fill', 'transparent')
        .on('pointermove', (e) => tip.show(e, [r.fenomeno, `Últimos 12 meses: ${G.pct0(r.pct_12m)} de los relatos (${G.int(r.relatos_12m)})`, `Rango 95 %: ${G.pct0(r.ic_inf)}–${G.pct0(r.ic_sup)}`, `Periodo anterior: ${G.pct0(r.pct_previo)}${c}`]))
        .on('pointerleave', () => tip.hide());
    });
  });
})();
