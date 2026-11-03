// WP-31: the business page with a rehearsal's numbers and without measured ones, at desktop and phone widths.
//   node tools/business_check.mjs PORT -> {synthetic: {...}, measured: {...}}
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const port = process.argv[2], out = {};
const b = await chromium.launch();
for (const [k, q] of [['synthetic', '?synthetic=1'], ['measured', '']]) {
  for (const w of [1280, 390]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } }); const errors = [];
    p.on('pageerror', e => errors.push(String(e)));
    await p.goto(`http://127.0.0.1:${port}/business${q}`); await p.waitForFunction(() => window.BUSINESS_READY === true, null, { timeout: 30000 });
    out[`${k}_${w}`] = await p.evaluate(() => ({ tiles: document.querySelectorAll('.tile').length, effectRows: document.querySelectorAll('.card table tr').length,
      rehearsal: /Rehearsal/.test(document.body.innerText), empty: /No measured posts yet/.test(document.body.innerText),
      sideScroll: document.documentElement.scrollWidth > window.innerWidth + 1 }));
    if (process.env.BUSINESS_SHOT && k === 'synthetic') await p.screenshot({ path: `${process.env.BUSINESS_SHOT}_${w}.png`, fullPage: true });
    out[`${k}_${w}`].errors = errors; await p.close();
  }
}
await b.close();
console.log(JSON.stringify(out));
