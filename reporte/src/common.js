(function () {
  const G = (window.G = {});
  const loc = d3.formatLocale({ decimal: ',', thousands: '.', grouping: [3], currency: ['$', ''] });
  G.int = loc.format(',d');
  G.pct = loc.format('.1%');
  G.pct0 = loc.format('.0%');
  G.d1 = loc.format(',.1f');
  G.d2 = loc.format(',.2f');
  G.d3 = loc.format(',.3f');
  G.p = (v) => (v == null ? '—' : v < 0.001 ? '< 0,001' : loc.format('.3f')(v));
  const MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  G.mes = (m) => (m ? MES[+m.slice(5, 7) - 1] + ' ' + m.slice(2, 4) : '—');
  G.mesLargo = (m) => (m ? MES[+m.slice(5, 7) - 1] + ' ' + m.slice(0, 4) : '—');
  G.ORIG = ['registrado', 'extraído_regla', 'extraído_modelo', 'inferido'];
  G.ORIGK = ['registrado', 'extraido_regla', 'extraido_modelo', 'inferido'];
  const C = dash.colors || [];
  G.oc = [C[0] || '#2f6fb0', C[1] || '#3a9e8f', C[2] || '#c2862b', C[3] || '#9a6bb8'];
  G.tc = { actividad: C[0] || '#2f6fb0', mecanismo: C[2] || '#c2862b', bien: C[1] || '#3a9e8f', lugar: C[4] || '#b5546b' };
  document.querySelectorAll('.gic').forEach((el) => {
    G.oc.forEach((c, i) => el.style.setProperty('--gic-o' + (i + 1), c));
    ['actividad', 'mecanismo', 'bien', 'lugar'].forEach((k, i) => el.style.setProperty('--gic-t' + (i + 1), G.tc[k]));
  });

  // Estado de carga: devuelve true si todo está listo; si no, pinta el estado en el elemento.
  G.ready = (el, ids, opts = {}) => {
    const st = ids.map((id) => dash.data(id).status);
    if (st.every((s) => s === 'ok')) { el.classList.remove('dash-skeleton'); return true; }
    el.replaceChildren();
    if (st.some((s) => s === 'error' || s === 'missing' || s === 'declined')) {
      el.classList.remove('dash-skeleton');
      const msg = dash.params().fuente === 'decla' ? 'No disponible para esta fuente' : 'No se pudo cargar';
      const d = document.createElement(opts.tag || 'div');
      d.className = 'gic-fail'; d.textContent = msg;
      if (opts.tag === 'tr') { const td = document.createElement('td'); td.textContent = msg; d.textContent = ''; d.appendChild(td); }
      el.appendChild(d);
    } else if (opts.text) { el.textContent = '—'; }
    else { el.classList.add('dash-skeleton'); }
    return false;
  };
  G.text = (el, ids, fn) => {
    if (!G.ready(el, ids, { text: true })) return;
    const v = fn();
    el.textContent = v == null ? '—' : v;
  };
  G.width = (el, min = 280) => Math.max(min, el.clientWidth || 600);

  // Oculta/muestra con "display" (no con el atributo "hidden"): dash_shim.js redibuja todo el tablero
  // cuando cambia un atributo "hidden" en el documento, y cada vez que aparece/desaparece un tooltip
  // (p. ej. al pasar el mouse por el grafo de la sección 5) eso recreaba el SVG y reiniciaba el zoom.
  G.tip = (el) => {
    let t = el.querySelector(':scope > .gic-tip');
    if (!t) { t = document.createElement('div'); t.className = 'gic-tip'; t.style.display = 'none'; el.appendChild(t); }
    return {
      show(ev, lines) {
        t.replaceChildren(...lines.map((l, i) => { const d = document.createElement('div'); if (i) d.className = 't2'; d.textContent = l; return d; }));
        t.style.display = '';
        const r = el.getBoundingClientRect();
        let x = ev.clientX - r.left + 12, y = ev.clientY - r.top + 12;
        const w = t.offsetWidth || 200, h = t.offsetHeight || 40;
        if (x + w > r.width) x = Math.max(0, ev.clientX - r.left - w - 12);
        if (y + h > r.height) y = Math.max(0, ev.clientY - r.top - h - 12);
        t.style.left = x + 'px'; t.style.top = y + 'px';
      },
      hide() { t.style.display = 'none'; },
    };
  };
  G.svg = (el, w, h, label) => {
    el.replaceChildren();
    return d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${w} ${h}`).attr('role', 'img').attr('aria-label', label);
  };
  G.measure = (svg, texts) => {
    const g = svg.append('g').attr('opacity', 0);
    let m = 0;
    texts.forEach((t) => { const n = g.append('text').text(t).node(); m = Math.max(m, n.getComputedTextLength() || t.length * 6.2); });
    g.remove();
    return m;
  };

  // Barras horizontales (apiladas opcionales)
  G.hbar = (el, rows, o) => {
    const w = G.width(el);
    const keys = o.keys || [o.value];
    const colors = o.colors || [G.oc[0]];
    const rowH = 22, top = 4, h = top + rows.length * rowH + 6;
    const svg = G.svg(el, w, Math.max(h, 40), o.aria || 'Gráfico de barras');
    if (!rows.length) { svg.append('text').attr('x', 0).attr('y', 20).text('Sin relatos en la selección'); return; }
    const maxLabelW = Math.min(w * 0.45, G.measure(svg, rows.map((r) => o.label(r))) + 8);
    const endTxt = rows.map((r) => (o.end ? o.end(r) : ''));
    const endW = G.measure(svg, endTxt) + 10;
    const total = (r) => keys.reduce((s, k) => s + (+r[k] || 0), 0);
    const x = d3.scaleLinear().domain([0, o.max || d3.max(rows, total) || 1]).range([0, Math.max(30, w - maxLabelW - endW)]);
    const tip = G.tip(el);
    const g = svg.append('g').attr('transform', `translate(${maxLabelW},${top})`);
    rows.forEach((r, i) => {
      const y = i * rowH;
      svg.append('text').attr('class', 'lbl').attr('x', maxLabelW - 6).attr('y', top + y + rowH / 2 + 4).attr('text-anchor', 'end')
        .text(G.trunc(o.label(r), maxLabelW));
      let acc = 0;
      keys.forEach((k, j) => {
        const v = +r[k] || 0; if (!v) return;
        g.append('rect').attr('x', x(acc)).attr('y', y + 3).attr('height', rowH - 6).attr('width', Math.max(1, x(acc + v) - x(acc)))
          .attr('rx', 2).style('fill', colors[j % colors.length])
          .on('pointermove', (ev) => tip.show(ev, o.tip ? o.tip(r, k) : [o.label(r), G.int(v)]))
          .on('pointerleave', () => tip.hide());
        acc += v;
      });
      g.append('text').attr('x', x(acc) + 5).attr('y', y + rowH / 2 + 4).text(endTxt[i]);
    });
  };
  G.trunc = (s, px) => { const n = Math.floor(px / 6.3); return s.length > n ? s.slice(0, Math.max(4, n - 1)) + '…' : s; };

  // Serie temporal: x por meses (punto), varias líneas, bandas y marcas
  G.ts = (el, o) => {
    const w = G.width(el), h = o.h || 260, m = { t: 12, r: 14, b: 28, l: 40 };
    const svg = G.svg(el, w, h, o.aria || 'Serie mensual');
    const months = o.months;
    const x = d3.scalePoint().domain(months).range([m.l, w - m.r]).padding(0.3);
    const ymax = o.ymax || 10;
    const y = d3.scaleLinear().domain([0, ymax]).nice().range([h - m.b, m.t]);
    const yt = y.ticks(5);
    svg.append('g').attr('class', 'grid').selectAll('line').data(yt).join('line').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y).attr('y2', y);
    svg.append('g').attr('class', 'axis').selectAll('text').data(yt).join('text').attr('x', m.l - 6).attr('y', (d) => y(d) + 4).attr('text-anchor', 'end').text((d) => G.int(d));
    const every = Math.ceil(months.length / Math.max(2, Math.floor((w - m.l) / 52)));
    svg.append('g').attr('class', 'axis').selectAll('text').data(months.filter((_, i) => i % every === 0)).join('text')
      .attr('x', (d) => x(d)).attr('y', h - 8).attr('text-anchor', 'middle').text(G.mes);
    const step = x.step();
    (o.shade || []).forEach((mm) => { if (x(mm) != null) svg.append('rect').attr('x', x(mm) - step / 2).attr('width', step).attr('y', m.t).attr('height', h - m.b - m.t).style('fill', 'var(--color-warn)').attr('opacity', 0.15); });
    (o.bands || []).forEach((b) => {
      const pts = b.points.filter((p) => x(p.mes) != null);
      svg.append('path').datum(pts).attr('d', d3.area().x((p) => x(p.mes)).y0((p) => y(p.lo)).y1((p) => y(p.hi))).style('fill', b.color).attr('opacity', b.opacity);
    });
    (o.bars || []).forEach((b) => {
      svg.append('g').selectAll('rect').data(b.points).join('rect').attr('x', (p) => x(p.mes) - step * 0.35).attr('width', step * 0.7)
        .attr('y', (p) => y(p.v)).attr('height', (p) => y(0) - y(p.v)).attr('rx', 2).style('fill', b.color).attr('opacity', (p) => (p.dim ? 0.35 : 1));
    });
    (o.lines || []).forEach((l) => {
      const pts = l.points.filter((p) => x(p.mes) != null && p.v != null);
      const segs = []; let cur = [];
      pts.forEach((p) => { if (p.gap) { if (cur.length) segs.push(cur); cur = []; } else cur.push(p); });
      if (cur.length) segs.push(cur);
      segs.forEach((s) => svg.append('path').datum(s).attr('d', d3.line().x((p) => x(p.mes)).y((p) => y(p.v)).curve(l.step ? d3.curveStepAfter : d3.curveLinear))
        .style('fill', 'none').style('stroke', l.color).attr('stroke-width', l.width || 2).attr('stroke-dasharray', l.dash || null));
      if (l.dots) svg.append('g').selectAll('circle').data(pts.filter((p) => !p.gap)).join('circle').attr('cx', (p) => x(p.mes)).attr('cy', (p) => y(p.v)).attr('r', 2.5).style('fill', l.color);
    });
    (o.marks || []).forEach((mk) => {
      const sym = d3.symbol().type(mk.shape === 'square' ? d3.symbolSquare : d3.symbolTriangle).size(70);
      svg.append('path').attr('d', sym()).attr('transform', `translate(${x(mk.mes)},${y(mk.v) - (mk.shape === 'square' ? 18 : 10)})`).style('fill', 'var(--cds-chart-status-critical)');
    });
    if (o.cut) svg.append('line').attr('x1', x(o.cut) + step / 2).attr('x2', x(o.cut) + step / 2).attr('y1', m.t).attr('y2', h - m.b).style('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '3 3');
    const tip = G.tip(el);
    svg.append('g').selectAll('rect').data(months).join('rect').attr('x', (d) => x(d) - step / 2).attr('width', step).attr('y', m.t).attr('height', h - m.b - m.t)
      .style('fill', 'transparent').on('pointermove', (ev, d) => tip.show(ev, o.tip(d))).on('pointerleave', () => tip.hide());
  };

  G.td = (tr, v, num) => { const td = document.createElement('td'); td.textContent = v == null ? '—' : v; if (num) td.className = 'num'; tr.appendChild(td); return td; };
  G.key = (...a) => a.map((s) => encodeURIComponent(String(s))).join(',');
  G.emptyRow = (tb, n, msg) => { const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = n; td.textContent = msg; tr.appendChild(td); tb.appendChild(tr); };
  G.setSel = (sel, options, value) => {
    sel.replaceChildren(...options.map(([v, l]) => new Option(l, v)));
    sel.value = value;
  };

  // Pie de página: el texto de fuente/método es distinto por fuente; `fuente` no cambia durante la sesión.
  document.querySelectorAll('#notas [data-fuente]').forEach((el) => { el.hidden = el.dataset.fuente !== (dash.params().fuente || 'gic'); });
})();
