// Review room page check (plan 3.4): with `python -m dbe serve 8771` running, open review-demo, seek to 10.4 s and pin
// "hold the scratch head longer" (frame 312). Then `python -m dbe review.fix` closes it.
//   node tools/review_check.mjs OUT_DIR
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1300, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto('http://127.0.0.1:8771/review?film=review-demo'); await p.waitForSelector('.note'); await p.waitForTimeout(1500);
await p.waitForTimeout(3500); await p.evaluate(() => seek(10.4)); await p.waitForTimeout(800);
await p.fill('#text', 'hold the scratch head longer'); await p.click('#add'); await p.waitForTimeout(800);
await p.screenshot({ path: process.argv[2] + '/review_page.png' });
console.log(JSON.stringify({ notes: await p.$$eval('.note', n => n.length), msg: await p.$eval('#msg', e => e.textContent), errs })); await b.close();
