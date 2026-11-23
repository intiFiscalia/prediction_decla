// Secciones 6 (Alertas) y 7 (Pronósticos)
(function () {
  const P = () => dash.params();
  dash.draw('sel_serie_al', (sel) => {
    const f = dash.data('alertas_far');
    G.setSel(sel, f.status === 'ok' ? f.data.map((r) => [r.serie, r.serie]) : [], P().serie_alerta || 'Total de relatos');
    sel.onchange = () => dash.setParams({ serie_alerta: sel.value });
  });
  dash.draw('al_chart', (el) => {
    if (!G.ready(el, ['alertas'])) return;
    const s = P().serie_alerta || 'Total de relatos';
    const rows = dash.data('alertas').data.filter((r) => r.serie === s);
    const ms = rows.map((r) => r.mes);
    G.ts(el, {
      months: ms, aria: `Serie mensual y señales de ${s}`, ymax: d3.max(rows, (r) => Math.max(r.observado, r.umbral_99 || 0)) * 1.15 || 5,
      shade: rows.filter((r) => r.calidad !== 'ok').map((r) => r.mes),
      lines: [
        { color: 'var(--cds-chart-status-critical)', dash: '2 3', width: 1.5, step: false, points: rows.map((r) => ({ mes: r.mes, v: r.umbral_99, gap: r.umbral_99 == null })) },
        { color: 'var(--cds-chart-reference)', dash: '5 4', width: 1.5, points: rows.map((r) => ({ mes: r.mes, v: r.esperado, gap: r.esperado == null })) },
        { color: 'var(--color-fg)', width: 2, dots: true, points: rows.map((r) => ({ mes: r.mes, v: r.observado })) },
      ],
      marks: [...rows.filter((r) => r.senal_ears).map((r) => ({ mes: r.mes, v: r.observado, shape: 'tri' })),
        ...rows.filter((r) => r.senal_cusum).map((r) => ({ mes: r.mes, v: r.observado, shape: 'square' }))],
      tip: (m) => { const r = rows.find((x) => x.mes === m); return [G.mesLargo(m), `Observado ${G.int(r.observado)}`, r.evaluado ? `Esperado ${G.d1(r.esperado)} · umbral ${G.int(r.umbral_99)}` : 'Sin línea base suficiente', r.evaluado ? `P(≥ obs.) ${G.p(r.p_cola)} · CUSUM ${G.d2(r.cusum)}` : '', (r.senal_ears ? 'Señal EARS. ' : '') + (r.senal_cusum ? 'Señal CUSUM. ' : '') + (r.calidad !== 'ok' ? 'Calidad: ' + r.calidad : '')].filter(Boolean); },
    });
  });
  dash.draw('al_far', (tb) => {
    if (!G.ready(tb, ['alertas_far'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('alertas_far').data.forEach((r) => {
      const tr = document.createElement('tr');
      G.td(tr, r.serie); G.td(tr, G.d1(r.media_mensual), 1); G.td(tr, r.dispersion); G.td(tr, G.pct(r.far_ears), 1); G.td(tr, G.d2(r.falsas_por_anio_ears), 1);
      G.td(tr, G.pct(r.far_cusum), 1); G.td(tr, G.d2(r.falsas_por_anio_cusum), 1); G.td(tr, G.int(r.senales_ears), 1); G.td(tr, G.int(r.senales_cusum), 1);
      tb.appendChild(tr);
    });
  });
  dash.draw('al_lista', (tb) => {
    if (!G.ready(tb, ['alertas'], { tag: 'tr' })) return;
    tb.replaceChildren();
    const s = P().serie_alerta || 'Total de relatos';
    const rows = dash.data('alertas').data.filter((r) => r.serie === s && (r.senal_ears || r.senal_cusum));
    if (!rows.length) return G.emptyRow(tb, 8, 'Sin señales en esta serie.');
    rows.forEach((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = G.key(r.serie, r.mes);
      const senal = [r.senal_ears ? '▲ EARS' : '', r.senal_cusum ? '■ CUSUM' : ''].filter(Boolean).join(' y ');
      G.td(tr, G.mesLargo(r.mes)); G.td(tr, senal); G.td(tr, G.int(r.observado), 1); G.td(tr, G.d1(r.esperado), 1);
      G.td(tr, G.int(r.umbral_99), 1); G.td(tr, G.p(r.p_cola), 1); G.td(tr, G.d2(r.cusum), 1); G.td(tr, r.calidad);
      tb.appendChild(tr);
    });
  });

})();
