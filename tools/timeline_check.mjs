// Studio timeline check (plan 3.1): with `python -m dbe serve 8771` running, open the timeline for direct-demo,
// drag a gesture of Ravi 60 px right and report the edit. Restore films/direct-demo/shots.json afterwards.
//   node tools/timeline_check.mjs OUT_DIR
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const out = process.argv[2];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
await p.goto('http://127.0.0.1:8771/timeline?film=direct-demo');
await p.waitForSelector('.blk.clip:not(.loop)', { timeout: 60000 });
await p.waitForTimeout(2500);
// pick Ravi's point gesture (hand-placed or directed) and drag it 60 px right
const blk = await p.$('.lane[data-who="ravi"] .blk.clip:not(.loop)');
const info = await blk.evaluate(el => ({ title: el.title, shot: el.dataset.shot, cast: el.dataset.cast, i: el.dataset.i }));
const bb = await blk.boundingBox();
await p.screenshot({ path: out + '/tl_before.png' });
await p.mouse.move(bb.x + 15, bb.y + 12); await p.mouse.down(); await p.mouse.move(bb.x + 45, bb.y + 12, { steps: 4 }); await p.mouse.move(bb.x + 75, bb.y + 12, { steps: 4 }); await p.mouse.up();
await p.waitForFunction(() => document.getElementById('msg').textContent.includes('moved'), null, { timeout: 30000 });
await p.waitForTimeout(1500);
const msgText = await p.$eval('#msg', e => e.textContent);
const frameOk = await p.evaluate(() => { const w = document.getElementById('frame').contentWindow; return !!(w && w.frameAtTime && w.ready); });
await p.screenshot({ path: out + '/tl_after.png' });
console.log(JSON.stringify({ dragged: info, msg: msgText, frameOk, errs }));
await b.close();
