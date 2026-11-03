// Studio sound page check (WP-40): with `python -m dbe serve PORT` running, open /sound for FILM, drag the cue of TYPE
// nearest FROM to TO seconds with the mouse, drag across the music lane from A to B seconds and swap it to KIND, press
// Remix, and print what the page reports (the moved cue's onset and frame error, the music span's level).
//   node tools/sound_check.mjs PORT FILM TYPE FROM TO A B KIND
import { createRequire } from 'module'; const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [port, film, type, from, to, a, b, kind] = process.argv.slice(2);
const br = await chromium.launch(); const p = await br.newPage({ viewport: { width: 1280, height: 900 } });
const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
await p.goto(`http://127.0.0.1:${port}/sound?film=${film}`);
await p.waitForFunction(() => window.SOUND && window.SOUND.ready === true, null, { timeout: 60000 });
const geo = async lane => p.evaluate(l => { const ws = window.SOUND.W[l], w = ws.getWrapper().getBoundingClientRect();
  return { left: w.left, top: w.top, width: w.width, height: w.height, dur: ws.getDuration() }; }, lane);
const xOf = (g, t) => g.left + t / g.dur * g.width;
// 1. drag the cue: grab its own marker, move it by the time difference
const cue = await p.evaluate(([ty, f]) => { const rs = window.SOUND.R.sfx.getRegions().filter(r => r.cue && r.cue.type === ty);
  rs.sort((x, y) => Math.abs(x.start - f) - Math.abs(y.start - f)); if (!rs.length) return null;
  const e = rs[0].element.getBoundingClientRect(); return { t: rs[0].start, x: e.left + 1, y: e.top + e.height / 2 }; }, [type, +from]);
if (cue == null) { console.log(JSON.stringify({ error: `no ${type} cue` })); process.exit(1); }
let g = await geo('sfx');
await p.mouse.move(cue.x, cue.y); await p.mouse.down();
await p.mouse.move(cue.x + (+to - cue.t) / g.dur * g.width, cue.y, { steps: 12 }); await p.mouse.up(); await p.waitForTimeout(300);
// 2. drag across the music lane, pick the kind, swap
g = await geo('music');
await p.mouse.move(xOf(g, +a), g.top + g.height / 2); await p.mouse.down();
await p.mouse.move(xOf(g, +b), g.top + g.height / 2, { steps: 12 }); await p.mouse.up(); await p.waitForTimeout(300);
await p.waitForSelector('#mkind'); await p.selectOption('#mkind', kind); await p.click('#mapply');
const pending = await p.evaluate(() => JSON.parse(JSON.stringify(window.SOUND.pending)));
// 3. remix and read the result
await p.click('#remix');
await p.waitForFunction(() => document.getElementById('msg').textContent === 'remixed' || /error|failed/i.test(document.getElementById('msg').textContent), null, { timeout: 600000 });
const res = await p.evaluate(() => window.SOUND_RESULT || null);
const after = await p.evaluate(() => ({ sections: window.SOUND.L.sections, cues: window.SOUND.L.cues.map(c => [c.t, c.type, c.origin]) }));
console.log(JSON.stringify({ cue_from: cue.t, pending, moved: res && res.moved, music: res && res.music, qa: res && res.qa, sections_after: after.sections, errors: errs }));
await br.close();
