// Entorno local que reproduce la API `dash` del tablero publicado en Claude, para abrir el reporte
// sin conexión (doble clic en reporte.html). Lee los datos incrustados por build_report.py.
(function () {
  const DATA = JSON.parse(document.getElementById('gic-data').textContent);
  const DEFAULTS = JSON.parse(document.getElementById('gic-params').textContent);
  let params = { ...DEFAULTS };
  const calcs = {}, draws = {}, onDatas = [];
  let cache = {};

  function value(id) {
    if (id in DATA) return DATA[id];
    if (!(id in calcs)) throw new Error('Fuente desconocida: ' + id);
    if (!(id in cache)) cache[id] = calcs[id].fn(...calcs[id].inputs.map(value));
    return cache[id];
  }
  const visible = (el) => !el.closest('[hidden]');
  let pending = false;
  function render() {
    pending = false; cache = {};
    onDatas.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });
    document.querySelectorAll('[data-draw]').forEach((el) => {
      const fn = draws[el.dataset.draw];
      if (!fn || !visible(el)) return;
      try { fn(el); } catch (e) { console.error('Error en', el.dataset.draw, e); }
    });
  }
  const schedule = () => { if (!pending) { pending = true; requestAnimationFrame(render); } };

  window.dash = {
    colors: ['#2f6fb0', '#3a9e8f', '#c2862b', '#9a6bb8', '#b5546b', '#5b8c3a'],
    calc: (id, o) => { calcs[id] = o; },
    loader: () => {},
    data: (id) => { try { const d = value(id); return { status: 'ok', data: d, columns: Array.isArray(d) && d[0] ? Object.keys(d[0]) : [] }; } catch (e) { console.error(e); return { status: 'error', data: [], message: String(e) }; } },
    draw: (name, fn) => { if (typeof fn === 'function') draws[name] = fn; else if (fn && fn.update) draws[name] = (el) => fn.update(el, fn.mount ? fn.mount(el) : null); else if (!fn) schedule(); },
    onData: (fn) => { onDatas.push(fn); },
    params: () => params,
    setParams: (p) => { params = { ...params, ...p }; schedule(); },
    resetParams: () => { params = { ...DEFAULTS }; schedule(); },
    refresh: () => schedule(),
    setLink: (id) => { try { history.replaceState(null, '', '#' + id); } catch (e) { /* file:// en algunos navegadores */ } },
  };
  window.claude = { use: () => Promise.reject(new Error('No disponible en el reporte local')) };

  // Redibujar al cambiar de pestaña (atributo hidden), al imprimir y al cambiar el ancho.
  new MutationObserver(schedule).observe(document.body, { attributes: true, subtree: true, attributeFilter: ['hidden'] });
  window.addEventListener('resize', schedule);
  window.addEventListener('beforeprint', () => { cache = {}; render(); });
  window.addEventListener('load', render);
  document.addEventListener('DOMContentLoaded', schedule);
})();
