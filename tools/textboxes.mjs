// Measure every on-screen text element of a film over time: box and rendered font size, in film pixels. Words that
// are hidden, clipped or covered at the centre of their box are not on screen and are left out.
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
  // the camera's zoom on a word: the scale of the outermost transformed group between it and the stage (the camera
  // group); set text seen in a push-in is background detail cropped by the frame, not text placed to be read
  const camZoom = el => { let a = el.parentNode, top = null;
    while (a && a.id !== 'stage') { if (a.getAttribute && /scale\(/.test(a.getAttribute('transform') || '')) top = a; a = a.parentNode; }
    if (!top) return 1; const m = /scale\(([-\d.]+)/.exec(top.getAttribute('transform')); return m ? Math.abs(+m[1]) : 1; };
  for (let t = T.start; t < T.end; t += st) {
    window.frameAtTime(t);
    for (const el of document.querySelectorAll('#stage text')) {
      const txt = el.textContent.trim(); if (!txt) continue;
      const r = el.getBoundingClientRect(), m = el.getScreenCTM();
      // only words a viewer can see: not hidden, and on top at the centre of their box (clipped or covered text is not)
      const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      const cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;
      if (cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight) {
        const top = document.elementFromPoint(cx, cy);
        if (top && top !== el && !el.contains(top) && !(top.closest && top.closest('text') === el)) {
          const hits = document.elementsFromPoint(cx, cy); if (!hits.slice(0, 3).some(h => h === el || el.contains(h))) continue;
        }
      }
      const fs = parseFloat(getComputedStyle(el).fontSize) * Math.hypot(m.a, m.b);
      res.push({ t: +t.toFixed(2), text: txt.slice(0, 60), x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, px: +fs.toFixed(1), zoom: +camZoom(el).toFixed(3) });
    }
  }
  return res;
}, +step);
console.log(JSON.stringify({ size: [w, h], boxes: out }));
await b.close();
