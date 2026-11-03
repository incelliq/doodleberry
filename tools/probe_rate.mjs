// Render-rate probe (WP-20): how fast a shot's frames are captured when rendered as run3d.mjs renders them (one
// browser per worker, static plate on when the page offers one), measured on a few sample frames per worker after a
// warm-up. Prints JSON {ms_per_frame (wall time per captured frame, all workers together), ms_single, frames_total,
// plate, workers, samples}.   node tools/probe_rate.mjs PAGE_URL [WORKERS] [SAMPLES_PER_WORKER]
import { createRequire } from 'module'; import fs from 'fs'; import os from 'os'; import path from 'path'; import { spawnSync } from 'child_process';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, nwArg = '4', nsArg = '2'] = process.argv.slice(2);
const nw = +nwArg, ns = +nsArg;
const ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'];
const probe = await chromium.launch({ args: ARGS });
const info = await (async () => { const p = await probe.newPage(); await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const i = await p.evaluate(() => ({ total: window.FRAMES, w: (window.FILM || {}).width || 1080, h: (window.FILM || {}).height || 1920 })); await p.close(); return i; })();
const tStart = Date.now();
const workers = await Promise.all(Array.from({ length: nw }, async (_, w) => {
  const b = w === 0 ? probe : await chromium.launch({ args: ARGS });
  const p = await b.newPage({ viewport: { width: info.w, height: info.h } }); await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const cdp = await p.context().newCDPSession(p);
  const plr = await p.evaluate(() => window.platePrepare ? window.platePrepare().then(r => r && r.png) : null), pl = plr && plr.length, plate = !!pl;
  if (plate) await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  const sizes = [];   // PNG bytes per frame (and the plate's): how detailed the frames are, which is what encoding costs
  const pngs = [];
  const shot = async f => { await p.evaluate(async f => { await window.renderFrame(f); }, f); await p.evaluate(() => new Promise(r => requestAnimationFrame(() => r()))); const s = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true }); sizes.push(s.data.length * 3 / 4); pngs.push(s.data); };
  // a reused frame costs drawing and hashing its markup, not a capture
  const reuse = async f => { await p.evaluate(async f => { await window.renderFrame(f); const s = document.getElementById('stage').innerHTML; let h = 0; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return h; }, f); };
  await shot(Math.floor(info.total * (w + 0.5) / nw));   // warm-up
  sizes.length = 0; pngs.length = 0;
  return { b, shot, reuse, plate, sizes, pngs, platePng: plr, plateBytes: pl ? pl * 3 / 4 : 0 };
}));
const startup = Date.now() - tStart;   // browsers launched, pages loaded, plates made, one frame each drawn
// the sample frames, spread through the shot; every worker captures ns of them at once, as in a real render
const t0 = Date.now(); let single = 0;
await Promise.all(workers.map(async (wk, w) => { for (let k = 0; k < ns; k++) { const f = Math.min(info.total - 1, Math.floor(info.total * (w * ns + k + 0.5) / (nw * ns))); const t = Date.now(); await wk.shot(f); single += Date.now() - t; } }));
const wall = Date.now() - t0;
const t1 = Date.now();
await Promise.all(workers.map(async (wk, w) => { for (let k = 0; k < ns; k++) await wk.reuse(Math.min(info.total - 1, Math.floor(info.total * (w * ns + k + 0.25) / (nw * ns)))); }));
const wallReuse = Date.now() - t1;
const sz = workers.flatMap(w => w.sizes);
// encoding: the sample frames as run3d.mjs encodes them (over the plate when there is one), timed per frame; a second,
// one-frame encode is taken off so ffmpeg's start-up is not counted
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'probe-')); const all = workers.flatMap(w => w.pngs);
all.forEach((d, i) => fs.writeFileSync(path.join(tmp, `f${String(i).padStart(5, '0')}.png`), Buffer.from(d, 'base64')));
const enc = ['-c:v', 'libx264', '-tune', 'animation', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p'];
const runEnc = n => { let args;
  if (workers[0].platePng) { fs.writeFileSync(path.join(tmp, 'plate.png'), Buffer.from(workers[0].platePng.split(',')[1], 'base64'));
    args = ['-v', 'error', '-y', '-loop', '1', '-framerate', '30', '-i', path.join(tmp, 'plate.png'), '-framerate', '30', '-i', path.join(tmp, 'f%05d.png'), '-frames:v', String(n),
      '-filter_complex', '[0:v]format=rgba[p];[1:v]format=rgba[f];[p][f]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]', '-map', '[v]', ...enc, path.join(tmp, 'o.mp4')]; }
  else args = ['-v', 'error', '-y', '-framerate', '30', '-i', path.join(tmp, 'f%05d.png'), '-frames:v', String(n), ...enc, path.join(tmp, 'o.mp4')];
  const t = Date.now(); spawnSync('ffmpeg', args); return Date.now() - t; };
const e1 = runEnc(1), eN = runEnc(all.length);
fs.rmSync(tmp, { recursive: true });
console.log(JSON.stringify({ ms_per_frame: Math.round(wall / (nw * ns)), ms_reuse: Math.round(wallReuse / (nw * ns)), ms_single: Math.round(single / (nw * ns)), frames_total: info.total, plate: workers[0].plate,
  ms_startup: startup, ms_encode: Math.max(1, Math.round((eN - e1) / Math.max(1, all.length - 1))), png_kb: Math.round(sz.reduce((a, b) => a + b, 0) / Math.max(1, sz.length) / 1024), plate_kb: Math.round(workers[0].plateBytes / 1024), workers: nw, samples: nw * ns }));
await Promise.all(workers.map(w => w.b.close()));
