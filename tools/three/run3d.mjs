// Render any frame-pure page (SVG player or three.js) to MP4.
//   node run3d.mjs page.html out.mp4 [workers]
// Speed (plan 0.1): one browser process per worker on contiguous frame ranges; identical frames are detected by hashing the
// stage SVG and linked instead of re-captured; Chrome's fast PNG capture; libx264 -tune animation.
// The viewport follows window.FILM (so 16:9 and 9:16 both work).
import { createRequire } from 'module'; import fs from 'fs'; import os from 'os'; import path from 'path'; import { spawnSync } from 'child_process';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, out, nwArg] = process.argv.slice(2);
const nw = +(nwArg || Math.max(1, os.cpus().length));
const dir = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), 'fr-'));
const ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'];
const b = await chromium.launch({ args: ARGS });
const url = /^(https?|file):/.test(page) ? page : 'file://' + path.resolve(page);
const t0 = Date.now();
// probe size and frame count once
const probe = await b.newPage(); await probe.goto(url); await probe.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const info = await probe.evaluate(() => ({ total: window.FRAMES, w: (window.FILM || {}).width || 1080, h: (window.FILM || {}).height || 1920, fps: (window.FILM || {}).fps || 30 }));
await probe.close();
const seen = new Map(); let reused = 0;
const name = f => path.join(dir, `f${String(f).padStart(5, '0')}.png`);
const chunk = Math.ceil(info.total / nw);
await Promise.all(Array.from({ length: nw }, async (_, w) => {
  const a = w * chunk, z = Math.min(info.total, a + chunk); if (a >= z) return;
  const bw = w === 0 ? b : await chromium.launch({ args: ARGS });   // one browser process per worker: pages in one process share its renderer
  const p = await bw.newPage({ viewport: { width: info.w, height: info.h } });
  p.on('pageerror', e => console.log('ERR', String(e)));
  await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const cdp = await p.context().newCDPSession(p);
  for (let f = a; f < z; f++) {
    // render, then hash the SVG stage (null for canvas/WebGL pages, which are never deduped)
    const key = await p.evaluate(f => {
      window.renderFrame(f);
      const st = document.getElementById('stage'); if (!st || st.tagName.toLowerCase() !== 'svg' || document.querySelector('canvas')) return null;
      const s = st.innerHTML; let h1 = 0x811c9dc5 | 0, h2 = 0;
      for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = (h2 * 31 + c) | 0; }
      return `${s.length}:${h1 >>> 0}:${h2 >>> 0}`;
    }, f);
    if (key && seen.has(key)) {
      const src = seen.get(key);
      // the source may still be in flight in another worker; wait briefly for it to exist
      for (let k = 0; k < 200 && !fs.existsSync(src); k++) await new Promise(r => setTimeout(r, 25));
      if (fs.existsSync(src)) { fs.linkSync(src, name(f)); reused++; continue; }
    }
    if (key) seen.set(key, name(f));
    await p.evaluate(() => new Promise(r => requestAnimationFrame(() => r())));
    const shot = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
    fs.writeFileSync(name(f), Buffer.from(shot.data, 'base64'));
  }
  if (bw !== b) await bw.close();
}));
await b.close();
const secs = (Date.now() - t0) / 1000;
console.log(`${info.total} frames (${reused} reused) in ${secs.toFixed(1)} s, ${(secs * 1000 / Math.max(1, info.total)).toFixed(0)} ms/frame, ${nw} workers`);
spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(info.fps), '-i', path.join(dir, 'f%05d.png'), '-c:v', 'libx264', '-tune', 'animation', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', out], { stdio: 'inherit' });
fs.rmSync(dir, { recursive: true });
