// The compositor in the graph view (WP-36): open a shot's comp as a graph, brighten a grade node and watch the
// preview change, add a blur node to a plane, set the camera's roll, and see a bad expression refused.
//   node tools/graph_comp_check.mjs PORT FILM SHOT
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [port, film, shot] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
const shots = () => p.evaluate(async f => JSON.parse((await (await fetch('/api/film.get', { method: 'POST', body: JSON.stringify({ name: f }) })).json()).result.files['shots.json']), film);
const comp = async () => (await shots()).shots.find(x => x.id === shot).comp;
const waitMsg = async re => { await p.waitForFunction(r => new RegExp(r).test(document.getElementById('msg').textContent), re, { timeout: 60000 }); await p.waitForTimeout(600); };
const out = {};
await p.goto(`http://127.0.0.1:${port}/graph?film=${film}&view=comp:${shot}`);
await p.waitForFunction(() => window.GRAPH_READY && window.COMPGRAPH && document.querySelectorAll('.react-flow__node').length > 0, null, { timeout: 60000 });
const c0 = await comp();
out.boxes = await p.$$eval('.react-flow__node', ns => ns.length); out.want_boxes = c0.planes.length + (c0.nodes || []).length + 2;
out.edges = await p.$$eval('.react-flow__edge', es => es.length);
// a grade node: brightness up, the preview brighter
const gi = (c0.nodes || []).findIndex(n => n.type === 'grade');
await p.click(`.react-flow__node[data-id="nd:${gi}"]`); await p.waitForFunction(() => { const w = document.getElementById('pv'); return w && w.contentWindow && w.contentWindow.ready; }, null, { timeout: 60000 });
await p.waitForTimeout(1500);
const mean = async () => { const buf = await (await p.$('#pvw')).screenshot(); return buf; };
const before = await mean();
await p.fill('#flds input[data-k="brightness"]', '1.8'); await p.click('#csave'); await waitMsg('saved');
await p.waitForFunction(() => { const w = document.getElementById('pv'); return w && w.contentWindow && w.contentWindow.ready; }, null, { timeout: 60000 }); await p.waitForTimeout(1500);
const after = await mean();
out.grade = { stored: (await comp()).nodes[gi].brightness };
require('fs').writeFileSync(process.env.OUT + '/before.png', before); require('fs').writeFileSync(process.env.OUT + '/after.png', after);
// a blur node added to the far plane
const far = c0.planes.slice().sort((a, b) => (b.depth ?? 1) - (a.depth ?? 1))[0].id;
await p.click(`.react-flow__node[data-id="pl:${far}"]`); await p.selectOption('#ntype', 'blur'); await p.click('#nadd'); await waitMsg('added blur');
const c1 = await comp(); out.added = { nodes: (c1.nodes || []).length, last: c1.nodes[c1.nodes.length - 1], boxes: await p.$$eval('.react-flow__node', ns => ns.length) };
// the camera: a roll
await p.click('.react-flow__node[data-id="cam"]'); await p.fill('#newk', 'roll'); await p.fill('#newv', '5'); await p.click('#csave'); await waitMsg('saved camera');
out.roll = (await comp()).roll;
// a bad expression is refused and nothing is written
await p.click('.react-flow__node[data-id="cam"]'); await p.fill('#flds input[data-k="roll"]', '"=constructor"'); await p.click('#csave');
await p.waitForFunction(() => /not allowed|unknown name/.test(document.getElementById('msg').textContent), null, { timeout: 30000 });
out.refused = { msg: await p.$eval('#msg', e => e.textContent), roll_still: (await comp()).roll };
out.errs = errs.filter(e => !/comp expression/.test(e));
console.log(JSON.stringify(out));
await b.close();
