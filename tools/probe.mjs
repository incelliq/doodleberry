// Motion probe (plan 3.4): where a character's part is, in frame pixels, over a time span, from the player page.
//   node tools/probe.mjs PAGE.html CAST_INDEX PART T0 T1 [FPS]  -> JSON [[t, x, y], ...] (camera included)
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, ci, part, t0, t1, fps = '30'] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 400, height: 400 } });
await p.goto('file://' + path.resolve(page) + '?captions=0'); await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
const out = await p.evaluate(([ci, part, t0, t1, fps]) => window.PROBE(+ci, part, +t0, +t1, +fps), [ci, part, t0, t1, fps]);
console.log(JSON.stringify(out)); await b.close();
