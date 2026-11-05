// WP-37 linear light: a compositor shot's planes rendered one by one on transparency (the player's ?compplane=ID), with
// each plane's blend mode and opacity per frame, so dbe/master.py can composite them in linear light (the browser
// composites in sRGB). "@top" is what the player draws over every plane (the speech bubbles).
//   node tools/comp_planes.mjs PAGE.html OUT_DIR SCALE FPS SHOT START END PLANE[,PLANE...]
//   -> OUT_DIR/<plane>/f_NNNNN.png (NNNNN: the film frame) and OUT_DIR/<plane>/info.json {frame: {mode, opacity, depth}}
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const [page, outDir, scaleS, fpsS, shot, startS, endS, planesS] = process.argv.slice(2);
const scale = +scaleS || 1, fps = +fpsS || 30, planes = planesS.split(',');
const f0 = Math.round(+startS * fps), f1 = Math.round(+endS * fps);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
for (const pl of planes) {
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: scale });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e)));
  await p.goto('file://' + path.resolve(page) + `?shot=${encodeURIComponent(shot)}&captions=0&compplane=${encodeURIComponent(pl)}`);
  await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]); await p.setViewportSize({ width: w, height: h });
  const dir = path.join(outDir, pl.replace(/[^\w@-]/g, '_')); fs.mkdirSync(dir, { recursive: true }); const info = {};
  for (let f = f0; f < f1; f++) {
    await p.evaluate(tt => window.frameAtTime(tt), f / fps);
    await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    info[f] = await p.evaluate(id => ((window.COMPINFO || {}).blends || {})[id] || null, pl);
    await p.screenshot({ path: path.join(dir, `f_${String(f).padStart(5, '0')}.png`), omitBackground: true });
  }
  fs.writeFileSync(path.join(dir, 'info.json'), JSON.stringify(info));
  if (errs.length) { console.error(`${pl}: page errors: ` + errs.join(' | ')); process.exitCode = 2; }
  await ctx.close();
}
await b.close(); console.log(JSON.stringify({ planes, frames: f1 - f0 }));
