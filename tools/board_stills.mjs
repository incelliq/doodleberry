// Storyboard stills (plan 3.2): node tools/board_stills.mjs PAGE.html OUT_DIR WIDTH t1 t2 ...
// Writes OUT_DIR/still_<i>.png at WIDTH px wide (the film's aspect), without captions (the storyboard notes carry the lines).
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, out, width, ...times] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('file://' + path.resolve(page) + '?captions=0');   // the notes carry the lines
await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
const [w, h] = await p.evaluate(() => [window.FILM.width, window.FILM.height]); await p.setViewportSize({ width: w, height: h });
const k = +width / w;
for (let i = 0; i < times.length; i++) {
  await p.evaluate(t => window.frameAtTime(t), +times[i]);
  await p.screenshot({ path: path.join(out, `still_${i}.png`), clip: { x: 0, y: 0, width: w, height: h }, scale: 'css' });
}
console.log(JSON.stringify({ size: [w, h], stills: times.length, scale: k }));
await b.close();
