// Studio timeline check 2 (WP-19): drag the cut after the first shot, add a camera key by double-clicking the camera
// lane, drag it, type its zoom, delete it, drag a line later (the film is re-voiced) and undo that.
//   node tools/timeline_edit_check.mjs PORT FILM
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [port, film] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
const api = (cmd, args) => p.evaluate(async ([c, a]) => (await (await fetch('/api/' + c, { method: 'POST', body: JSON.stringify(a) })).json()).result, [cmd, args]);
const shots = async () => JSON.parse((await api('film.get', { name: film })).files['shots.json']).shots;
const waitMsg = async (re, timeout = 60000) => { await p.waitForFunction(r => new RegExp(r).test(document.getElementById('msg').textContent), re, { timeout }); await p.waitForTimeout(800); };
const drag = async (sel, dx, dy = 0) => { const bb = await (await p.$(sel)).boundingBox(); const x = bb.x + Math.min(bb.width / 2, 12), y = bb.y + bb.height / 2;
  await p.mouse.move(x, y); await p.mouse.down(); for (let k = 1; k <= 6; k++) await p.mouse.move(x + dx * k / 6, y + dy * k / 6); await p.mouse.up(); };
const out = {};
await p.goto(`http://127.0.0.1:${port}/timeline?film=${film}`);
await p.waitForSelector('.cut', { timeout: 60000 }); await p.waitForTimeout(1500);
await p.uncheck('#snap');   // plain frames, so the moves are exact
const pps = await p.evaluate(() => pps);
// 1. the cut after s1, 44 px later
let before = await shots();
await drag('.cut[data-cut="s1"]', 44); await waitMsg('cut after s1 moved');
let after = await shots();
out.cut = { s1_end: [before[0].end, after[0].end], s2_start: [before[1].start, after[1].start], want_dt: +(44 / pps).toFixed(3) };
// 2. a camera key: double-click the camera lane inside s2, drag it 33 px right, set its zoom, then delete it
const T0 = await p.evaluate(() => T); const s2 = T0.shots[1], tAdd = s2.start + 0.4 * (s2.end - s2.start);
const lane = await (await p.$('#camlane')).boundingBox(), tl = await (await p.$('#tl')).boundingBox();
await p.mouse.dblclick(tl.x + 92 + tAdd * pps, lane.y + lane.height / 2); await waitMsg('camera key added');
let cam = (await shots())[1].camera || [];
out.camkey_added = cam;
await drag('.cam[data-shot="s2"]', 33); await waitMsg('camera key moved');
const camT = await p.evaluate(() => T.shots[1].camera.map(k => k.t));
out.camkey_moved = { raw: (await shots())[1].camera, t: camT };
await p.click('.cam[data-shot="s2"]'); await p.fill('#cz', '1.2'); await p.click('#camset'); await waitMsg('camera key 0 of s2 set');
out.camkey_set = (await shots())[1].camera;
// the curve editor: a second key later in s2 (zoom 1.4), then the move from the first eased in, then a handle dragged
const tB = s2.start + 0.85 * (s2.end - s2.start);
await p.mouse.dblclick(tl.x + 92 + tB * pps, lane.y + lane.height / 2); await waitMsg('camera key added');
await p.click('.cam[data-ci="1"][data-shot="s2"]'); await p.fill('#cz', '1.4'); await p.click('#camset'); await waitMsg('camera key 1 of s2 set');
await p.click('.cam[data-ci="0"][data-shot="s2"]'); await p.waitForSelector('#csvg circle');
await p.click('[data-ease="ease in"]'); await waitMsg('camera move from key 0');
out.curve_preset = (await shots())[1].camera[0];
await p.click('.cam[data-ci="0"][data-shot="s2"]'); await p.waitForSelector('#csvg circle');
const h = await (await p.$('#csvg circle[data-h="1"]')).boundingBox();
await p.mouse.move(h.x + h.width / 2, h.y + h.height / 2); await p.mouse.down();
for (let k = 1; k <= 5; k++) await p.mouse.move(h.x + h.width / 2 - 8 * k, h.y + h.height / 2 - 6 * k); await p.mouse.up(); await waitMsg('curve');
out.curve_dragged = (await shots())[1].camera;
out.curve_drawn = await p.evaluate(() => document.getElementById('cname') && document.getElementById('cname').textContent);
await p.click('.cam[data-ci="1"][data-shot="s2"]'); await p.keyboard.press('Delete'); await waitMsg('camera key deleted');
await p.click('.cam[data-ci="0"][data-shot="s2"]'); await p.keyboard.press('Delete'); await waitMsg('camera key deleted');
out.camkey_deleted = (await shots())[1].camera || null;
// 3. drag the last line 40 px later: re-voiced, the line moves and the one before stays
const L0 = await p.evaluate(() => T.lines.map(l => [l.id, l.start]));
const last = L0[L0.length - 1][0];
await drag(`.blk.say[data-line="${last}"]`, 40); await waitMsg('now starts at', 300000);
const L1 = await p.evaluate(() => T.lines.map(l => [l.id, l.start]));
out.line = { moved: last, before: L0, after: L1, want_dt: +(40 / pps).toFixed(3) };
await p.click('#undo'); await waitMsg('undone', 300000);
out.line.undone = await p.evaluate(() => T.lines.map(l => [l.id, l.start]));
out.errs = errs;
console.log(JSON.stringify(out));
await b.close();
