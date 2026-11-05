// Review on a phone (WP-19): the Studio served to the network with a key; an emulated iPhone 13 opens the review
// room by the link, scrubs the bar with a tap and a drag, and pins a note from the box at the bottom of the screen.
//   node tools/review_phone_check.mjs BASE_URL KEY FILM      (BASE_URL: http://<this machine's address>:<port>)
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium, devices } = require('playwright');
const [base, key, film] = process.argv.slice(2);
const out = {};   // (the key itself is checked from another address by the test: dbe/commands.py _reviewphone_test)
const b = await chromium.launch(); const ctx = await b.newContext({ ...devices['iPhone 13'] }); const p = await ctx.newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${base}/review?film=${film}&key=${key}`);
await p.waitForFunction(() => document.querySelector('#notes') && document.querySelector('#notes').children.length > 0 && document.querySelector('#bar .head'), null, { timeout: 60000 });
await p.waitForTimeout(3500);   // (the video, or the live player where the render cannot play)
out.layout = await p.evaluate(() => {
  const vw = innerWidth, vh = innerHeight, box = id => { const e = document.getElementById(id); const r = e.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, h: r.height, w: r.width, shown: !e.hidden }; };
  const pic = !document.getElementById('vid').hidden ? box('vid') : box('pv');
  return { viewport: [vw, vh], h_scroll: document.documentElement.scrollWidth > vw + 1, picture_h_share: +(pic.h / vh).toFixed(2), composer: box('composer'), bar_h: box('bar').h,
           text_font_px: parseFloat(getComputedStyle(document.getElementById('text')).fontSize) };
});
const frameNo = () => p.evaluate(() => +document.getElementById('fr').textContent.match(/frame (\d+)/)[1]);
const len = await p.evaluate(() => length), fps = await p.evaluate(() => fps);
const bar = await (await p.$('#bar')).boundingBox();
await p.touchscreen.tap(bar.x + 0.3 * bar.width, bar.y + bar.height / 2); await p.waitForTimeout(400);
out.tap = { frame: await frameNo(), want: Math.round(0.3 * len * fps) };
await p.mouse.move(bar.x + 0.3 * bar.width, bar.y + bar.height / 2); await p.mouse.down();
for (let k = 1; k <= 6; k++) await p.mouse.move(bar.x + (0.3 + 0.3 * k / 6) * bar.width, bar.y + bar.height / 2);
await p.mouse.up(); await p.waitForTimeout(400);
out.drag = { frame: await frameNo(), want: Math.round(0.6 * len * fps) };
await p.tap('#fwd'); await p.waitForTimeout(300); out.step = { frame: await frameNo() };
const before = await p.evaluate(() => R.notes.length);
await p.tap('#text'); await p.fill('#text', 'phone check: hold the wave longer'); await p.tap('#add');
await p.waitForFunction(n => R.notes.length > n, before, { timeout: 30000 });
out.pinned = await p.evaluate(() => { const n = R.notes[R.notes.length - 1]; return { id: n.id, frame: n.frame, text: n.text }; });
await p.screenshot({ path: process.env.SHOT || '/dev/null' }).catch(() => {});
out.errs = errs;
console.log(JSON.stringify(out));
await b.close();
