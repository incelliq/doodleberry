// Drives the live page (WP-12) for python -m dbe test '{"film":"live"}'.
//   node tools/live/check.mjs URL solve FRAMES.json   -> per frame, LIVE.solve's angles for the given landmarks
//   node tools/live/check.mjs URL camera Y4M FRAMES_N -> the page on a fake webcam playing Y4M: its smoothed angles
//                                                        after FRAMES_N detections, and how long a frame takes
import { createRequire } from 'module'; import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, mode, file, nArg] = process.argv.slice(2);
const args = mode === 'camera' ? ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${file}`] : [];
const b = await chromium.launch({ args }); const p = await b.newPage(); const logs = [];
p.on('pageerror', e => logs.push(String(e)));
const t0 = Date.now();
await p.goto(url + (mode === 'camera' ? '&autostart=1' : ''));
await p.waitForFunction(() => window.LIVE && (window.LIVE.ready || window.LIVE.error), null, { timeout: 180000 });
const out = { load_s: (Date.now() - t0) / 1000, error: await p.evaluate(() => window.LIVE.error || null), logs };
if (!out.error && mode === 'solve') {
  const take = JSON.parse(fs.readFileSync(file, 'utf8'));
  out.angles = await p.evaluate(([fr, W, H]) => { LIVE.reset(); return fr.map(f => f.pose ? LIVE.solve(f.pose, W, H).angles : {}); }, [take.frames, ...take.size]);
} else if (!out.error) {
  const n = +nArg || 30;
  await p.waitForFunction(n => window.LIVE.detected >= n, n, { timeout: 300000 });
  out.live = await p.evaluate(() => ({ angles: LIVE.angles, raw: LIVE.raw, history: LIVE.history, lm: LIVE.lm, size: LIVE.size, frames: LIVE.frames, detected: LIVE.detected,
    ms: LIVE.ms.reduce((a, b) => a + b, 0) / LIVE.ms.length, svg: document.getElementById('char').innerHTML.length }));
}
console.log(JSON.stringify(out));
await b.close();
