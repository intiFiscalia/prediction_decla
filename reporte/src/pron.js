// Sección 7: Pronósticos, en lenguaje sencillo
dash.calc('pron_resumen', {
  inputs: ['pronosticos', 'pronosticos_eval'],
  title: 'Resumen del pronóstico',
  description: 'Método usado, relatos esperados, rango probable y error frente a repetir el último mes, para la serie elegida.',
  fn: (pronosticos, pronosticos_eval) => {
    const p = dash.params();
    const serie = p.serie_pron || 'Total de relatos', NAIVE = 'Ingenuo (último valor)';
    const ev = pronosticos_eval.filter((r) => r.serie === serie);
    const naive = ev.find((r) => r.modelo === NAIVE) || {};
    const best = ev.filter((r) => r.modelo !== NAIVE).sort((a, b) => a.mae - b.mae)[0] || {};
    const modelo = !p.modelo_pron || p.modelo_pron === 'auto' ? best.modelo : p.modelo_pron;
    const m = ev.find((r) => r.modelo === modelo) || {};
    const fut = pronosticos.filter((r) => r.serie === serie && r.modelo === modelo);
    const obs = pronosticos.filter((r) => r.serie === serie && r.tipo === 'Observado' && r.calidad !== 'posible vacío de registro');
    const ult = obs[obs.length - 1] || {};
    const f0 = fut[0] || {};
    return [{
      serie, modelo, mes_ini: f0.mes, mes_fin: (fut[fut.length - 1] || {}).mes,
      esperado: f0.valor, inf80_1: f0.inf80, sup80_1: f0.sup80,
      ultimo_mes: ult.mes, ultimo_valor: ult.valor,
      prom_6m: obs.length ? d3.mean(obs.slice(-6), (r) => r.valor) : null,
      error_modelo: m.mae, error_ingenuo: naive.mae,
      mejora_pct: m.mae != null && naive.mae ? 1 - m.mae / naive.mae : null,
    }];
  },
});

dash.calc('pron_tabla', {
  inputs: ['pronosticos', 'pronosticos_eval'],
  title: 'Pronóstico mes a mes',
  description: 'Relatos esperados por mes con el método elegido, su rango probable (80 %) y amplio (95 %), y la referencia de repetir el último mes.',
  fn: (pronosticos, pronosticos_eval) => {
    const p = dash.params();
    const serie = p.serie_pron || 'Total de relatos', NAIVE = 'Ingenuo (último valor)';
    const best = pronosticos_eval.filter((r) => r.serie === serie && r.modelo !== NAIVE).sort((a, b) => a.mae - b.mae)[0] || {};
    const modelo = !p.modelo_pron || p.modelo_pron === 'auto' ? best.modelo : p.modelo_pron;
    const f = pronosticos.filter((r) => r.serie === serie && r.tipo === 'Pronóstico');
    const ref = new Map(f.filter((r) => r.modelo === NAIVE).map((r) => [r.mes, r.valor]));
    return f.filter((r) => r.modelo === modelo).map((r) => ({
      mes: r.mes, esperado: Math.round(r.valor), inf80: r.inf80, sup80: r.sup80, inf95: r.inf95, sup95: r.sup95, referencia: ref.get(r.mes),
    }));
  },
});

dash.calc('pron_eval', {
  inputs: ['pronosticos_eval'],
  title: 'Qué tan bien acierta cada método',
  description: 'Error promedio de cada método en los últimos 6 meses conocidos, y cuánto mejora frente a repetir el último mes.',
  fn: (pronosticos_eval) => {
    const p = dash.params();
    const serie = p.serie_pron || 'Total de relatos', NAIVE = 'Ingenuo (último valor)';
    const nombres = { 'Ingenuo (último valor)': 'Repetir el último mes (referencia)', 'Media móvil 6 meses': 'Promedio de los últimos 6 meses',
      'Suavizado exponencial simple': 'Promedio que pesa más los meses recientes' };
    const ev = pronosticos_eval.filter((r) => r.serie === serie);
    const naive = (ev.find((r) => r.modelo === NAIVE) || {}).mae;
    const best = ev.filter((r) => r.modelo !== NAIVE).sort((a, b) => a.mae - b.mae)[0] || {};
    const usado = !p.modelo_pron || p.modelo_pron === 'auto' ? best.modelo : p.modelo_pron;
    return ev.map((r) => ({ modelo: r.modelo, metodo: nombres[r.modelo] || r.modelo, error_promedio: r.mae,
      mejora_vs_referencia: r.modelo === NAIVE || !naive ? null : 1 - r.mae / naive,
      recomendado: r.modelo === best.modelo ? 'Sí' : '', usado: r.modelo === usado ? 'Sí' : '' }));
  },
});

(function () {
  const P = () => dash.params();
  const NAIVE = 'Ingenuo (último valor)';
  const NOMBRE = { 'Media móvil 6 meses': 'el promedio de los últimos 6 meses', 'Suavizado exponencial simple': 'un promedio que pesa más los meses recientes' };
  const R = () => dash.data('pron_resumen').data[0];
  const t = (f) => (el) => G.text(el, ['pron_resumen'], () => f(R()));

  dash.draw('sel_serie_pr', (sel) => {
    const f = dash.data('pronosticos_eval');
    const lbl = (s) => (s === 'Total de relatos' ? 'Todos los relatos' : s.startsWith('Territorio: ') ? `Relatos en ${s.slice(12)}` : s.startsWith('Entidad: ') ? `Relatos enviados por ${s.slice(9)}` : `Relatos de ${s.toLowerCase()}`);
    G.setSel(sel, f.status === 'ok' ? [...new Set(f.data.map((r) => r.serie))].map((s) => [s, lbl(s)]) : [], P().serie_pron || 'Total de relatos');
    sel.onchange = () => dash.setParams({ serie_pron: sel.value });
  });

  dash.draw('pr_esperado', t((r) => G.int(Math.round(r.esperado))));
  dash.draw('pr_inf', t((r) => G.int(r.inf80_1)));
  dash.draw('pr_sup', t((r) => G.int(r.sup80_1)));
  dash.draw('pr_mes1', t((r) => G.mesLargo(r.mes_ini)));
  dash.draw('pr_rango', t((r) => `${G.mesLargo(r.mes_ini)} a ${G.mesLargo(r.mes_fin)}`));
  dash.draw('pr_prom6', t((r) => G.d1(r.prom_6m)));
  dash.draw('pr_ultmes', t((r) => G.mesLargo(r.ultimo_mes)));
  dash.draw('pr_ultval', t((r) => G.int(r.ultimo_valor)));
  dash.draw('pr_metodo', t((r) => NOMBRE[r.modelo] || r.modelo));
  dash.draw('pr_mejora', t((r) => (r.mejora_pct == null ? '—' : G.pct0(Math.abs(r.mejora_pct)))));
  dash.draw('pr_mejora_txt', (el) => {
    if (!G.ready(el, ['pron_resumen'], { text: true })) return;
    el.textContent = (R().mejora_pct || 0) >= 0 ? 'menos' : 'más';
  });
  dash.draw('pr_aviso_peor', (el) => {
    const ok = dash.data('pron_resumen').status === 'ok' && (R().mejora_pct || 0) < 0;
    el.replaceChildren();
    document.querySelectorAll('#pr-peor').forEach((p) => { p.hidden = !ok; });
  });

  dash.draw('pr_chart', (el) => {
    if (!G.ready(el, ['pronosticos', 'pron_resumen'])) return;
    const s = P().serie_pron || 'Total de relatos', mod = R().modelo;
    const rows = dash.data('pronosticos').data.filter((r) => r.serie === s);
    const obs = rows.filter((r) => r.tipo === 'Observado'), fm = rows.filter((r) => r.modelo === mod), fn = rows.filter((r) => r.modelo === NAIVE);
    const ms = [...obs.map((r) => r.mes), ...fm.map((r) => r.mes)];
    const last = obs[obs.length - 1];
    G.ts(el, {
      months: ms, aria: `Relatos registrados por mes y pronóstico de ${s}`, ymax: d3.max([...obs.map((r) => r.valor), ...fm.map((r) => r.sup80)]) * 1.08 || 5,
      shade: obs.filter((r) => r.calidad !== 'ok').map((r) => r.mes), cut: last.mes,
      bands: [{ color: G.oc[2], opacity: 0.25, points: [{ mes: last.mes, lo: last.valor, hi: last.valor }, ...fm.map((r) => ({ mes: r.mes, lo: r.inf80, hi: r.sup80 }))] }],
      lines: [
        { color: 'var(--color-fg)', width: 2, dots: true, points: obs.map((r) => ({ mes: r.mes, v: r.valor })) },
        { color: 'var(--color-fg-muted)', dash: '5 4', width: 1.5, points: [{ mes: last.mes, v: last.valor }, ...fn.map((r) => ({ mes: r.mes, v: r.valor }))] },
        { color: G.oc[2], width: 2.5, points: [{ mes: last.mes, v: last.valor }, ...fm.map((r) => ({ mes: r.mes, v: r.valor }))] },
      ],
      tip: (m) => {
        const o = obs.find((r) => r.mes === m);
        if (o) return [G.mesLargo(m), `${G.int(o.valor)} relatos registrados`, o.calidad !== 'ok' ? 'Ojo: ' + o.calidad : ''].filter(Boolean);
        const a = fm.find((r) => r.mes === m), b = fn.find((r) => r.mes === m);
        return [G.mesLargo(m), `Se esperan unos ${G.int(Math.round(a.valor))} relatos`, `Rango probable: ${G.int(a.inf80)} a ${G.int(a.sup80)}`, `Referencia (repetir el último mes): ${G.int(b.valor)}`];
      },
    });
  });

  dash.draw('pr_tabla', (tb) => {
    if (!G.ready(tb, ['pron_tabla'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('pron_tabla').data.forEach((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = G.key(r.mes);
      G.td(tr, G.mesLargo(r.mes)); G.td(tr, G.int(r.esperado), 1);
      G.td(tr, `${G.int(r.inf80)} a ${G.int(r.sup80)}`, 1); G.td(tr, `${G.int(r.inf95)} a ${G.int(r.sup95)}`, 1); G.td(tr, G.int(r.referencia), 1);
      tb.appendChild(tr);
    });
  });

  dash.draw('pr_eval', (tb) => {
    if (!G.ready(tb, ['pron_eval'], { tag: 'tr' })) return;
    tb.replaceChildren();
    dash.data('pron_eval').data.forEach((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = G.key(r.modelo);
      G.td(tr, r.metodo); G.td(tr, G.d1(r.error_promedio), 1);
      G.td(tr, r.mejora_vs_referencia == null ? '—' : `${G.pct0(Math.abs(r.mejora_vs_referencia))} ${r.mejora_vs_referencia >= 0 ? 'menos' : 'más'} error`, 1);
      G.td(tr, [r.usado ? '✓ usado aquí' : '', r.recomendado ? 'el que menos se equivoca' : ''].filter(Boolean).join(' · '));
      tb.appendChild(tr);
    });
  });
})();
