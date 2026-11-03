// Drive an interactive web film (WP-30) in Chromium: the panel lists every line and chapter; a tap on a line seeks to
// it; playing through a question stops after it and asks; the answer button resumes; no page errors.
//   node tools/interactive_check.mjs URL   -> prints {lines, chapters, sources, tap, pause, resume, errors}
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const url = process.argv[2];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
const errors = []; p.on('pageerror', e => errors.push(String(e)));
await p.goto(url); await p.waitForFunction(() => window.ready === true && window.IFILM, null, { timeout: 60000 });
const D = await p.evaluate(() => window.INTERACTIVE);
const out = { lines: await p.locator('.ln').count(), chapters: await p.locator('.ch').count(), sources: await p.locator('#srcs a').count(), errors };
const k = Math.min(1, D.lines.length - 1);
await p.locator('.ln').nth(k).click(); await p.waitForTimeout(150);
let st = await p.evaluate(() => window.IFILM.state());
out.tap = { line: D.lines[k].id, t: +st.t.toFixed(2), start: D.lines[k].start, ok: st.t >= D.lines[k].start - 0.01 && st.t < D.lines[k].start + 0.5 };
await p.evaluate(() => window.IFILM.pause());
if (D.pauses.length) {
  const q = D.pauses[0];
  await p.evaluate(t => { window.IFILM.seek(t - 0.4); window.IFILM.play(); }, q.t);
  await p.waitForFunction(() => window.IFILM.state().asking, null, { timeout: 5000 }).catch(() => {});
  st = await p.evaluate(() => window.IFILM.state());
  out.pause = { at: q.t, t: +st.t.toFixed(2), asking: st.asking, playing: st.playing, ok: st.asking && !st.playing && Math.abs(st.t - q.t) < 0.01 };
  await p.click('#go'); await p.waitForTimeout(400);
  st = await p.evaluate(() => window.IFILM.state());
  out.resume = { t: +st.t.toFixed(2), playing: st.playing, ok: !st.asking && st.t > q.t };
  await p.evaluate(() => window.IFILM.pause());
}
await p.screenshot({ path: url.replace('file://', '').replace('index.html', 'screenshot.png') });
await b.close();
console.log(JSON.stringify(out));
