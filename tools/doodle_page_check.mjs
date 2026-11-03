// WP-18 page check: a page photo with two doodles on /doodle gives two puppets to pick from; on the second, the left
// arm left on the body is cut again by one tap (Tap to cut, SAM 2.1), and its drawing requests include pupils and a
// turned view to draw over ghosts.  node tools/doodle_page_check.mjs PORT PAGE_PNG
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
  await pg.click('#ok');
  await pg.waitForFunction(() => document.querySelectorAll('#reqs [data-req]').length > 0, null, { timeout: 300000 });
  const reqs = await pg.$eval('#reqs', e => e.textContent);
  console.log(JSON.stringify({ chips, picked: name, parts, without_arm: without, tapped, pupils: /pupils/.test(reqs), turn: /three-quarter/.test(reqs), errors }));
  await b.close();
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
