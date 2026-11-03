// Render-rate probe (WP-20): how fast a shot's frames are captured when rendered as run3d.mjs renders them (one
// browser per worker, static plate on when the page offers one), measured on a few sample frames per worker after a
// warm-up. Prints JSON {ms_per_frame (wall time per captured frame, all workers together), ms_single, frames_total,
// plate, workers, samples}.   node tools/probe_rate.mjs PAGE_URL [WORKERS] [SAMPLES_PER_WORKER]
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, nwArg = '4', nsArg = '2'] = process.argv.slice(2);
const nw = +nwArg, ns = +nsArg;
const ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'];
const probe = await chromium.launch({ args: ARGS });
const info = await (async () => { const p = await probe.newPage(); await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const i = await p.evaluate(() => ({ total: window.FRAMES, w: (window.FILM || {}).width || 1080, h: (window.FILM || {}).height || 1920 })); await p.close(); return i; })();
const workers = await Promise.all(Array.from({ length: nw }, async (_, w) => {
  const b = w === 0 ? probe : await chromium.launch({ args: ARGS });
  const p = await b.newPage({ viewport: { width: info.w, height: info.h } }); await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const cdp = await p.context().newCDPSession(p);
  const plate = await p.evaluate(() => window.platePrepare ? window.platePrepare().then(r => !!r) : false);
  if (plate) await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  const shot = async f => { await p.evaluate(async f => { await window.renderFrame(f); }, f); await p.evaluate(() => new Promise(r => requestAnimationFrame(() => r()))); await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true }); };
  await shot(Math.floor(info.total * (w + 0.5) / nw));   // warm-up
  return { b, shot, plate };
}));
// the sample frames, spread through the shot; every worker captures ns of them at once, as in a real render
const t0 = Date.now(); let single = 0;
await Promise.all(workers.map(async (wk, w) => { for (let k = 0; k < ns; k++) { const f = Math.min(info.total - 1, Math.floor(info.total * (w * ns + k + 0.5) / (nw * ns))); const t = Date.now(); await wk.shot(f); single += Date.now() - t; } }));
const wall = Date.now() - t0;
console.log(JSON.stringify({ ms_per_frame: Math.round(wall / (nw * ns)), ms_single: Math.round(single / (nw * ns)), frames_total: info.total, plate: workers[0].plate, workers: nw, samples: nw * ns }));
await Promise.all(workers.map(w => w.b.close()));
