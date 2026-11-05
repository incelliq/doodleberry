// WP-18 page check: a page photo with two doodles on /doodle gives two puppets to pick from; on the second, the left
// arm left on the body is cut again by one tap (Tap to cut, SAM 2.1), and its drawing requests include pupils and a
// turned view to draw over ghosts; the tail's cut outline is edited by its vertex handles and cut again.  node tools/doodle_page_check.mjs PORT PAGE_PNG
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
(async () => {
  const [port, page_png] = process.argv.slice(2);
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 420, height: 900 } });
  const errors = []; pg.on('pageerror', e => errors.push(String(e)));
  await pg.goto(`http://127.0.0.1:${port}/doodle`);
  await pg.fill('#cname', 'Nib');
  await pg.setInputFiles('#photo', page_png);
  await pg.waitForFunction(() => window.PAGE, null, { timeout: 300000 });
  const chips = await pg.$$eval('[data-pick]', bs => bs.map(b => b.textContent));
  await pg.click('[data-pick="1"]');
  const name = await pg.inputValue('#cname'); const parts = await pg.$$eval('[data-chip]', bs => bs.map(b => b.dataset.chip));
  // tap to cut (WP-18): leave the left arm on the body, then tap its stroke with Tap to cut on
  const arm = await pg.evaluate(() => { const a = window.PAGE.doodles[1].spec.parts.arm_L, far = a.poly.reduce((m, q) => Math.hypot(q[0] - a.pivot[0], q[1] - a.pivot[1]) > Math.hypot(m[0] - a.pivot[0], m[1] - a.pivot[1]) ? q : m, a.pivot);
    return [a.pivot[0] + 0.6 * (far[0] - a.pivot[0]), a.pivot[1] + 0.6 * (far[1] - a.pivot[1])]; });
  await pg.click('[data-chip="arm_L"]');
  const without = await pg.$$eval('[data-chip]', bs => bs.map(b => b.dataset.chip));
  await pg.click('#tapcut'); await pg.selectOption('#tappart', 'arm_L');
  const scr = await pg.evaluate(([x, y]) => { const o = document.getElementById('over'), pt = o.createSVGPoint(); pt.x = x; pt.y = y; const q = pt.matrixTransform(o.getScreenCTM()); return [q.x, q.y]; }, arm);
  await pg.mouse.click(scr[0], scr[1]);
  await pg.waitForFunction(() => window.TAP_RESULT, null, { timeout: 300000 });
  const tapped = await pg.evaluate(() => ({ part: window.TAP_RESULT.part, iou: window.TAP_RESULT.iou, parts: [...document.querySelectorAll('[data-chip]')].map(b => b.dataset.chip) }));
  await pg.click('#tapcut');
  // polygon editing (WP-18): on the tail's cut, double-tap a vertex away (one fewer), double-tap the outline (one
  // more), then drag the vertex farthest from the pivot most of the way to it, so the cut takes less of the drawing
  const toScr = q => pg.evaluate(([x, y]) => { const o = document.getElementById('over'), pt = o.createSVGPoint(); pt.x = x; pt.y = y; const r = pt.matrixTransform(o.getScreenCTM()); return [r.x, r.y]; }, q);
  const tail = () => pg.evaluate(() => ({ poly: spec.parts.tail.poly.map(q => q.slice()), pivot: spec.parts.tail.pivot, r: Math.max(...D.size) / 40 }));
  const before = JSON.stringify((await (await pg.evaluate(async () => (await fetch('/' + D.puppet + '?t=1')).json()))).parts.tail.strokes);
  await pg.evaluate(() => document.getElementById('over').scrollIntoView({ block: 'center' }));
  let t = await tail(); const n0 = t.poly.length, dist = q => Math.hypot(q[0] - t.pivot[0], q[1] - t.pivot[1]);
  const vi = t.poly.findIndex(q => dist(q) > 2.5 * t.r);
  let s_ = await toScr(t.poly[vi]); const hit = await pg.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return e ? e.tagName + (e.dataset.vi !== undefined ? ':' + e.dataset.pk + e.dataset.vi : '') : null; }, s_);
  await pg.mouse.dblclick(s_[0], s_[1]);
  t = await tail(); const n1 = t.poly.length;
  const ei = t.poly.reduce((m, q, i) => { const n = t.poly[(i + 1) % t.poly.length], L = Math.hypot(n[0] - q[0], n[1] - q[1]); return L > m[1] ? [i, L] : m; }, [0, 0])[0];   // the longest edge's middle
  const a = t.poly[ei], c = t.poly[(ei + 1) % t.poly.length]; s_ = await toScr([(a[0] + c[0]) / 2, (a[1] + c[1]) / 2]); await pg.mouse.dblclick(s_[0], s_[1]);
  t = await tail(); const n2 = t.poly.length;
  const fi0 = t.poly.reduce((m, q, i) => dist(q) > dist(t.poly[m]) ? i : m, 0);
  const fi = +(await pg.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return e && e.dataset.vi; }, await toScr(t.poly[fi0])) ?? fi0);   // the handle on top there (close vertices overlap)
  const far = t.poly[fi], to = [far[0] + 0.7 * (t.pivot[0] - far[0]), far[1] + 0.7 * (t.pivot[1] - far[1])];
  const s0 = await toScr(far), s1 = await toScr(to);
  await pg.mouse.move(s0[0], s0[1]); await pg.mouse.down(); for (let k = 1; k <= 8; k++) await pg.mouse.move(s0[0] + (s1[0] - s0[0]) * k / 8, s0[1] + (s1[1] - s0[1]) * k / 8); await pg.mouse.up();
  t = await tail(); const moved = t.poly[fi], edited = { id: await pg.evaluate(() => D.id), hit, n0, n1, n2, moved_to: moved, wanted: to.map(Math.round), poly: t.poly };
  await pg.click('#ok');
  await pg.waitForFunction(() => document.querySelectorAll('#reqs [data-req]').length > 0, null, { timeout: 300000 });
  const reqs = await pg.$eval('#reqs', e => e.textContent);
  edited.strokes_changed = JSON.stringify((await (await pg.evaluate(async () => (await fetch('/' + D.puppet + '?t=2')).json()))).parts.tail.strokes) !== before;
  console.log(JSON.stringify({ chips, picked: name, parts, without_arm: without, tapped, pupils: /pupils/.test(reqs), turn: /three-quarter/.test(reqs), edited, errors }));
  await b.close();
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
