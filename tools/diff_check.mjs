// Version diff page check (WP-19): with `python -m dbe serve PORT` running, open /diff for FILM, and report what the
// page marks: the changed spans on the bar, the frame it lands on, and whether stepping lands on changed frames only.
//   node tools/diff_check.mjs PORT FILM
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [port, film] = process.argv.slice(2);
const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1000, height: 900 } });
const errors = []; pg.on('pageerror', e => errors.push(String(e)));
await pg.goto(`http://127.0.0.1:${port}/diff?film=${film}`);
await pg.waitForFunction(() => window.DIFF_READY, null, { timeout: 600000 });
const spans = await pg.$$eval('#bar .chg', els => els.length);
const first = await pg.evaluate(() => window.DIFF_STATE);
const steps = [];
for (let i = 0; i < 3; i++) { await pg.click('#next'); steps.push(await pg.evaluate(() => window.DIFF_STATE)); }
await pg.mouse.click(...(await pg.evaluate(() => { const r = document.getElementById('bar').getBoundingClientRect(); return [r.left + 3, r.top + r.height / 2]; })));
const atStart = await pg.evaluate(() => window.DIFF_STATE);
const summary = await pg.textContent('#summary');
console.log(JSON.stringify({ spans, ranges: await pg.evaluate(() => window.DIFF.ranges.length), first, steps, atStart, summary, strip: await pg.$eval('#strip', e => !e.hidden), errors }));
await b.close();
