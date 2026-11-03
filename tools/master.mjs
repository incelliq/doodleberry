// Render a film's master passes from the SVG player (WP-37): every frame at `scale` times the film size (2: 4K for a
// 1080x1920 film), at `fps` (the film's own, or higher: frames are pure functions of time), one PNG per pass:
//   beauty  the film as it plays
//   line    the ink alone, as visible (fills painted white, images off), un-composited from white into alpha later
//   fill    the flat colour alone (strokes off), on transparency
//   matte   the characters alone (cast-only), on transparency: its alpha is the matte
//   node tools/master.mjs PAGE.html OUT_DIR SCALE FPS PASSES [START END]
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, outDir, scaleS, fpsS, passesS, startS, endS] = process.argv.slice(2);
const scale = +scaleS || 2, passes = (passesS || 'beauty').split(',');
const CSS = {
  // fills painted white (so lines hidden behind a fill stay hidden), on white; the ink becomes alpha in dbe/master.py
  line: 'html,body{background:#fff!important} #stage *{fill:#fff!important} #stage image{display:none!important}',
  fill: 'html,body{background:transparent!important} #stage *{stroke:none!important}',
  matte: 'html,body{background:transparent!important}',
};
fs.mkdirSync(outDir, { recursive: true });
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
for (const pass of passes) {
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: scale });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(page) + (pass === 'matte' ? '?castonly=1&captions=0' : '?captions=0'));
  await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]);
  await p.setViewportSize({ width: w, height: h });
  if (CSS[pass]) await p.addStyleTag({ content: CSS[pass] });
  const [t0, t1] = await p.evaluate(() => [window.FILMTIME.start, window.FILMTIME.end]);
  const fps = +fpsS || (await p.evaluate(() => window.FILM.fps)) || 30;
  const a = startS ? +startS : t0, z = endS ? +endS : t1, n = Math.round((z - a) * fps);
  fs.mkdirSync(path.join(outDir, pass), { recursive: true });
  for (let f = 0; f < n; f++) {
    await p.evaluate(tt => window.frameAtTime(tt), a + f / fps);
    await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    await p.screenshot({ path: path.join(outDir, pass, `f_${String(f).padStart(5, '0')}.png`), omitBackground: pass === 'matte' || pass === 'fill' });
  }
  if (errs.length) { console.error(`${pass}: page errors: ` + errs.join(' | ')); process.exitCode = 2; }
  console.log(JSON.stringify({ pass, frames: n, fps, size: [w * scale, h * scale] }));
  await ctx.close();
}
await b.close();
