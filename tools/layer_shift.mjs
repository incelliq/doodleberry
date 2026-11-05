// Where each parallax set layer's first shape is on screen at given times (WP-15 test `parallax`):
//   node tools/layer_shift.mjs PLAYER.html SHOT t1 t2 ...  -> {depth: [[x, y] per time]}
import { createRequire } from 'module'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const [page, shot, ...ts] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('file://' + path.resolve(page) + `?shot=${shot}&captions=0`); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const out = {};
for (const t of ts) {
  await p.evaluate(tt => window.frameAtTime(window.FILMTIME.start + tt), +t);
  const r = await p.evaluate(() => [...document.querySelectorAll('[data-depth]')].map(g => { const el = g.querySelector('path, rect'); const b = el.getBoundingClientRect(); return [g.dataset.depth, b.x + b.width / 2, b.y + b.height / 2]; }));
  for (const [d, x, y] of r) (out[d] = out[d] || []).push([+x.toFixed(2), +y.toFixed(2)]);
}
console.log(JSON.stringify(out)); await b.close();
