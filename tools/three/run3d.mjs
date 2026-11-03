// Render any frame-pure page (SVG player or three.js) to MP4.
//   node run3d.mjs page.html out.mp4 [workers]
// Speed (plan 0.1): one browser process per worker on contiguous frame ranges; identical frames are detected by hashing the
// stage SVG and linked instead of re-captured; Chrome's fast PNG capture; libx264 -tune animation.
// The viewport follows window.FILM (so 16:9 and 9:16 both work).
// Plate mode (WP-15): when the page offers a static plate (window.platePrepare: the SVG player, for a shot whose set is
// the same on every frame), frames are captured on a transparent background without the set and laid over the plate
// by ffmpeg; encoding frames without a full page of paper grain is much cheaper. DBE_PLATE=0 turns it off.
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
const plate = process.env.DBE_PLATE === '0' ? null : await probe.evaluate(() => window.platePrepare ? window.platePrepare() : null);
const platePng = plate ? path.join(dir, 'plate.png') : null;
if (plate) fs.writeFileSync(platePng, Buffer.from(plate.png.split(',')[1], 'base64'));
await probe.close();
const seen = new Map(); let reused = 0, waitedMs = 0; const KEYS = new Array(info.total).fill(null);   // per frame: its markup key (WP-19 film.diff)
const name = f => path.join(dir, `f${String(f).padStart(5, '0')}.png`);
const chunk = Math.ceil(info.total / nw);
await Promise.all(Array.from({ length: nw }, async (_, w) => {
  const a = w * chunk, z = Math.min(info.total, a + chunk); if (a >= z) return;
  const bw = w === 0 ? b : await chromium.launch({ args: ARGS });   // one browser process per worker: pages in one process share its renderer
  const p = await bw.newPage({ viewport: { width: info.w, height: info.h } });
  p.on('pageerror', e => console.log('ERR', String(e)));
  await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  const cdp = await p.context().newCDPSession(p);
  if (plate) {   // this page draws without the set too, on a transparent background
    const k = await p.evaluate(() => window.platePrepare().then(r => r && r.key));
    if (k !== plate.key) throw new Error('plate differs between workers');
    await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  }
  for (let f = a; f < z; f++) {
    // render, then hash the SVG stage (null for canvas/WebGL pages, which are never deduped)
    const key = await p.evaluate(async f => {
      await window.renderFrame(f);   // a frame with images (WP-42 plates) resolves once they have decoded
      const st = document.getElementById('stage'); if (!st || st.tagName.toLowerCase() !== 'svg' || document.querySelector('canvas')) return null;
      const s = st.innerHTML.replace(/blob:[^"]+/g, 'blob');   // cached layers name their content (data-k); blob URLs differ by run
      let h1 = 0x811c9dc5 | 0, h2 = 0;
      for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = (h2 * 31 + c) | 0; }
      return `${s.length}:${h1 >>> 0}:${h2 >>> 0}`;
    }, f);
    KEYS[f] = key;
    if (key && seen.has(key) && process.env.DBE_DEDUPE !== '0') {   // DBE_DEDUPE=0 captures every frame (to check the reuse is exact)
      const src = seen.get(key);
      // the source may still be in flight in another worker; wait briefly for it to exist
      const tw = Date.now(); for (let k = 0; k < 200 && !fs.existsSync(src); k++) await new Promise(r => setTimeout(r, 25)); waitedMs += Date.now() - tw;
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
console.log(`${info.total} frames (${reused} reused) in ${secs.toFixed(1)} s, ${(secs * 1000 / Math.max(1, info.total)).toFixed(0)} ms/frame, ${nw} workers${plate ? ', over a static plate' : ''}${waitedMs > 100 ? `, ${(waitedMs / 1000).toFixed(1)} s waiting on other workers` : ''}`);
// the frames' markup keys next to the video: two renders whose keys match at a frame drew the same picture there
fs.writeFileSync(out + '.keys.json', JSON.stringify({ frames: KEYS, plate: plate ? plate.key : null }));
const enc = ['-c:v', 'libx264', '-tune', 'animation', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', out];
if (plate) spawnSync('ffmpeg', ['-v', 'error', '-y', '-loop', '1', '-framerate', String(info.fps), '-i', platePng, '-framerate', String(info.fps), '-i', path.join(dir, 'f%05d.png'),
  '-filter_complex', '[0:v]format=rgba[p];[1:v]format=rgba[f];[p][f]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]', '-map', '[v]', '-r', String(info.fps), ...enc], { stdio: 'inherit' });
else spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(info.fps), '-i', path.join(dir, 'f%05d.png'), ...enc], { stdio: 'inherit' });
if (process.env.DBE_KEEP_FRAMES) fs.renameSync(dir, process.env.DBE_KEEP_FRAMES); else fs.rmSync(dir, { recursive: true });   // DBE_KEEP_FRAMES=dir keeps the PNGs (tests)
