// Frames for a comic or storybook (WP-30): the player page at each film time, without speech bubbles or captions,
// with where each speaker's head is on screen, in one browser session.
//   node tools/comic_frames.mjs URL TIMES.json OUTDIR DSF   -> prints [{t, png, heads: {speaker: [x, y]}}] (heads in frame pixels)
import { createRequire } from 'module';
import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const fs = createRequire(import.meta.url)('fs');
const [url, timesPath, outDir, dsf] = process.argv.slice(2);
const times = JSON.parse(fs.readFileSync(timesPath, 'utf8'));
const b = await chromium.launch();
const probe = await b.newPage(); await probe.goto(url); await probe.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const { w, h } = await probe.evaluate(() => ({ w: window.FILM.width, h: window.FILM.height })); await probe.close();
const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: +dsf });
p.on('pageerror', e => console.error('ERR', String(e)));
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const out = [];
for (const [i, t] of times.entries()) {
  const heads = await p.evaluate(t => { window.frameAtTime(t); return window.HEADS || {}; }, t);
  await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  const png = path.join(outDir, `p${String(i).padStart(3, '0')}.png`);
  await p.screenshot({ path: png });
  out.push({ t, png, heads });
}
await b.close();
console.log(JSON.stringify({ width: w, height: h, frames: out }));
