// Generic-AI-look lint probe (WP-04): over a film's frames, find the visual habits that read as generic
// AI-made graphics: drop shadows, gradient blobs, blur glows, emoji in text, and everything centred.
// Gradients and filters defined by the house set library (sets/*.js) are part of our sets and are not flagged.
//   node tools/ailook.mjs PAGE.html STEP_S ALLOWED_IDS_COMMA > ailook.json
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, step = '1.0', allowed = ''] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('file://' + path.resolve(page) + '?captions=0');
await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]);
await p.setViewportSize({ width: w, height: h });
const out = await p.evaluate(async ([st, allow]) => {
  const ok = new Set(allow.split(',').filter(Boolean).concat(['boil'])), T = window.FILMTIME, W = window.FILM.width, H = window.FILM.height;
  const res = { frames: 0, shadow: [], gradient: [], glow: [], emoji: [], centred: [] };
  const ref = v => { const m = /url\(["']?#([^)"']+)/.exec(v || ''); return m ? m[1] : null; };
  const pict = /\p{Extended_Pictographic}/u;
  for (let t = T.start; t < T.end; t += st) {
    window.frameAtTime(t); res.frames++;
    const root = document.getElementById('stage'), tt = +t.toFixed(2);
    const byId = id => root.querySelector('#' + CSS.escape(id));
    for (const el of root.querySelectorAll('*')) {
      const cs = getComputedStyle(el);
      if ((cs.boxShadow && cs.boxShadow !== 'none') || /drop-shadow/.test(cs.filter || '')) res.shadow.push({ t: tt, el: el.tagName });
      const f = ref(el.getAttribute('filter')) || ref(cs.filter);
      if (f && !ok.has(f)) { const fe = byId(f);
        if (fe && fe.querySelector('feDropShadow')) res.shadow.push({ t: tt, id: f });
        else if (fe && fe.querySelector('feGaussianBlur')) res.glow.push({ t: tt, id: f }); }
      for (const a of ['fill', 'stroke']) { const g = ref(el.getAttribute(a)) || ref(cs[a]);
        if (g && !ok.has(g)) { const ge = byId(g);
          if (ge && /Gradient$/.test(ge.tagName)) { const r = el.getBoundingClientRect(); if (r.width * r.height > 0.03 * W * H) res.gradient.push({ t: tt, id: g, area: +(r.width * r.height / (W * H)).toFixed(3) }); } } }
    }
    const texts = [...root.querySelectorAll('text')].filter(e => e.textContent.trim());
    for (const e of texts) if (pict.test(e.textContent)) res.emoji.push({ t: tt, text: e.textContent.trim().slice(0, 30) });
    if (texts.length >= 3) { const c = texts.filter(e => { const r = e.getBoundingClientRect(); return Math.abs((r.left + r.right) / 2 - W / 2) < 0.02 * W; }).length;
      if (c === texts.length) res.centred.push({ t: tt, n: texts.length }); }
  }
  return res;
}, [+step, allowed]);
console.log(JSON.stringify(out));
await b.close();
