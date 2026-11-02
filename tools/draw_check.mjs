// Studio drawing page check (WP-35): with `python -m dbe serve PORT` running and an empty level LEVEL (level.new),
// draw three drawings with the pen (onion skin on), one stroke with a MyPaint brush, set the sheet on twos, play,
// and report what the level holds.
//   node tools/draw_check.mjs PORT LEVEL OUT_DIR
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [port, level, out] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
p.on('dialog', d => d.accept());
await p.goto(`http://127.0.0.1:${port}/draw?level=${level}`);
await p.waitForFunction(() => window.DRAW_READY === true, null, { timeout: 60000 });
const box = async () => p.$eval('#cv', c => { const r = c.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
async function stroke(pts) { const r = await box(); await p.mouse.move(r.x + pts[0][0] * r.w, r.y + pts[0][1] * r.h); await p.mouse.down();
  for (const [u, v] of pts.slice(1)) await p.mouse.move(r.x + u * r.w, r.y + v * r.h, { steps: 3 }); await p.mouse.up(); }
const ball = (cx) => Array.from({ length: 25 }, (_, i) => [cx + 0.1 * Math.cos(i / 24 * 2 * Math.PI), 0.5 + 0.1 * Math.sin(i / 24 * 2 * Math.PI)]);
await stroke(ball(0.25)); await p.click('#save'); await p.waitForFunction(() => document.getElementById('msg').textContent.startsWith('saved'));
const onion = [];
for (const cx of [0.5, 0.75]) {
  await p.click('#add'); await p.waitForFunction(() => document.getElementById('msg').textContent.startsWith('new drawing'));
  onion.push(await p.$eval('#skin', c => { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 10) n++; return n; }));
  await stroke(ball(cx)); await p.click('#save'); await p.waitForFunction(() => document.getElementById('msg').textContent.startsWith('saved'));
}
// one brush stroke (libmypaint) across the last drawing
await p.click('[data-tool="brush"]'); await stroke([[0.1, 0.85], [0.5, 0.8], [0.9, 0.85]]);
await p.waitForTimeout(1500); await p.click('#save'); await p.waitForFunction(() => document.getElementById('msg').textContent.startsWith('saved'));
await p.click('[data-time="2"]'); await p.waitForTimeout(800);
await p.click('#play'); await p.waitForTimeout(700); await p.screenshot({ path: out + '/draw_play.png' }); await p.click('#play');
await p.screenshot({ path: out + '/draw_page.png' });
const lv = await p.evaluate(async lvl => (await (await fetch('/api/level.get', { method: 'POST', body: JSON.stringify({ name: lvl }) })).json()).result, level);
console.log(JSON.stringify({ cells: lv.cells, drawings: Object.fromEntries(Object.entries(lv.drawings).map(([k, v]) => [k, v.map(s => [s.x, s.y, s.w, s.h])])), onion, errs }));
await b.close();
