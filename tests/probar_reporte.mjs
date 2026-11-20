// Prueba el reporte HTML en un navegador simulado: abre las 8 pestañas y cuenta gráficos, filas y errores.
// Requiere Node 18+ y jsdom:  npm install jsdom   ->   node tests/probar_reporte.mjs reporte/dist/reporte.html
import { JSDOM, VirtualConsole } from 'jsdom';
import fs from 'fs';
const vc = new VirtualConsole(); const errs = [];
vc.on('error', (e) => errs.push(String(e))); vc.on('jsdomError', (e) => errs.push(String(e.message || e)));
const dom = new JSDOM(fs.readFileSync(process.argv[2], 'utf8'), { runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w) { w.SVGElement.prototype.getComputedTextLength = function () { return (this.textContent || '').length * 6; }; } });
const w = dom.window, d = w.document;
await new Promise((r) => setTimeout(r, 800));
const t = (s) => d.querySelector(s)?.textContent.replace(/\s+/g, ' ').trim();
console.log('lede:', t('.gic-lede'));
for (const id of ['indicadores','fenomenos','territorio','sectores','red','alertas','predicciones','organizaciones']) {
  d.querySelector(`[data-tab="${id}"]`).click(); await new Promise((r) => setTimeout(r, 300));
  const sec = d.getElementById(id);
  console.log(id, 'svg', sec.querySelectorAll('svg').length, 'filas', sec.querySelectorAll('tbody tr').length, 'kpis', [...sec.querySelectorAll('.gic-kv')].map(e=>e.textContent.trim()).join(' | ').slice(0,120), 'guiones', [...sec.querySelectorAll('[data-draw]')].filter(e=>e.textContent.trim()==='—').length);
}
w.dash.setParams({ dpto: '05', desde: '2025-01' }); await new Promise((r) => setTimeout(r, 300));
d.querySelector('[data-tab="indicadores"]').click(); await new Promise((r) => setTimeout(r, 300));
console.log('filtro Antioquia:', t('.gic-lede'));
console.log('errores:', errs.length, errs.slice(0, 5));
