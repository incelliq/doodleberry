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
if ((D.branches || []).length) {   // a branch: it stops and asks; the second choice plays its shots, then on to where they meet
  const br = D.branches[0], c = br.choices[1];
  await p.evaluate(t => { window.IFILM.seek(t - 0.4); window.IFILM.play(); }, br.at);
  await p.waitForFunction(() => window.IFILM.state().choosing, null, { timeout: 5000 }).catch(() => {});
  st = await p.evaluate(() => window.IFILM.state());
  const asked = { t: +st.t.toFixed(2), choosing: st.choosing, buttons: await p.locator('#cho button').count() };
  await p.locator('#cho button').nth(1).click(); await p.waitForTimeout(100);
  st = await p.evaluate(() => window.IFILM.state());
  const jumped = { t: +st.t.toFixed(2), ok: st.t >= c.start - 0.01 && st.t < c.start + 0.3 };
  await p.evaluate(t => { window.IFILM.pause(); }, 0);
  await p.evaluate(e => { const s = window.IFILM.state(); window.IFILM.seek(e - 0.3); }, c.end);
  // seeking inside the chosen branch keeps it chosen; play on to its end
  await p.evaluate(() => window.IFILM.play());
  await p.waitForFunction(th => window.IFILM.state().t >= th, br.then, { timeout: 5000 }).catch(() => {});
  st = await p.evaluate(() => window.IFILM.state());
  const met = { t: +st.t.toFixed(2), then: br.then, ok: st.t >= br.then - 0.01 && st.t < br.then + 0.5 && !(st.t >= br.choices[0].start && st.t < br.choices[0].end) };
  out.branch = { at: br.at, asked, jumped, met, path: st.path, ok: Math.abs(asked.t - br.at) < 0.01 && asked.choosing && asked.buttons === br.choices.length && jumped.ok && met.ok && st.path.length === 1 && st.path[0].choice === c.label };
  await p.evaluate(() => window.IFILM.pause());
}
await p.screenshot({ path: url.replace('file://', '').replace('index.html', 'screenshot.png') });
await b.close();
console.log(JSON.stringify(out));
