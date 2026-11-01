// Measure every on-screen text element of a film over time: box and rendered font size, in film pixels.
//   node tools/textboxes.mjs PAGE.html STEP_S > boxes.json
// (Film-level burned-in captions are measured separately from their ASS style.)
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, step = '0.5'] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('file://' + path.resolve(page) + '?captions=0');
await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]);
await p.setViewportSize({ width: w, height: h });
const out = await p.evaluate(async st => {
  const res = [], T = window.FILMTIME;
  for (let t = T.start; t < T.end; t += st) {
    window.frameAtTime(t);
    for (const el of document.querySelectorAll('#stage text')) {
      const txt = el.textContent.trim(); if (!txt) continue;
      const r = el.getBoundingClientRect(), m = el.getScreenCTM();
      const fs = parseFloat(getComputedStyle(el).fontSize) * Math.hypot(m.a, m.b);
      res.push({ t: +t.toFixed(2), text: txt.slice(0, 60), x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, px: +fs.toFixed(1) });
    }
  }
  return res;
}, +step);
console.log(JSON.stringify({ size: [w, h], boxes: out }));
await b.close();
