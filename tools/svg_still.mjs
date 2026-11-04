// Rasterize a standalone SVG file in a blank page, at an animation time (seconds) if given: the check for export.svg.
//   node tools/svg_still.mjs FILE.svg OUT.png [TIME]
import { createRequire } from 'module'; import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const [file, out, t] = process.argv.slice(2);
const svg = fs.readFileSync(file, 'utf8'); const m = svg.match(/^<svg[^>]*\bwidth="([\d.]+)" height="([\d.]+)"/);   // the root element's size
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: Math.round(+m[1]), height: Math.round(+m[2]) } });
await p.setContent(`<html><body style="margin:0;background:#fff">${svg}</body></html>`);
await p.evaluate(async t => { await document.fonts.ready; const s = document.querySelector('svg'); if (t != null && s.pauseAnimations) { s.pauseAnimations(); s.setCurrentTime(t); } }, t == null ? null : +t);
await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
await p.screenshot({ path: out }); await b.close();
