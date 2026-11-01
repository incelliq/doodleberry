// Render stills of a player page at given times (seconds within the page's span).
//   node tools/stills.mjs PAGE.html "shot=s1" OUT_PREFIX t1 t2 ...   -> OUT_PREFIX_<t>.png
// Viewport follows the film size (window.FILM). Used by golden tests, QA and critic packets.
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, query, out, ...ts] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto('file://' + path.resolve(page) + (query ? '?' + query : ''));
await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]);
await p.setViewportSize({ width: w, height: h });
const t0 = await p.evaluate(() => window.FILMTIME.start);
for (const t of ts) {
  await p.evaluate(tt => window.frameAtTime(tt), t0 + +t);
  await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  await p.screenshot({ path: `${out}_${t}.png` });
}
if (errs.length) { console.error('page errors: ' + errs.join(' | ')); process.exitCode = 2; }
await b.close();
