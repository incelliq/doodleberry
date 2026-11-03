// dotLottie QA (WP-23): a .lottie drawn by the dotLottie player (@lottiefiles/dotlottie-web, ThorVG in WebAssembly)
// for each of its animations and themes, at chosen frames.
//   node tools/dotlottie_frames.mjs FILE.lottie OUTDIR FRAMES(0,10,..) [THEMES(a,b|*)]
//   -> OUTDIR/<animation>__<theme or none>__NNNN.png, and prints {manifest, rendered}
import { createRequire } from 'module'; import fs from 'fs'; import http from 'http'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [file, outDir, frameArg, themeArg] = process.argv.slice(2);
const pkg = path.join(root, 'tools/dotlottie/node_modules/@lottiefiles/dotlottie-web/dist');
if (!fs.existsSync(pkg)) { console.error('dotlottie-web not installed: bash tools/setup.sh dotlottie'); process.exit(2); }
fs.mkdirSync(outDir, { recursive: true });
const types = { '.js': 'text/javascript', '.wasm': 'application/wasm', '.html': 'text/html', '.lottie': 'application/zip' };
const page = `<!doctype html><html><body style="margin:0;background:transparent"><canvas id="c"></canvas><script type="module">
import { DotLottie } from '/pkg/index.js'; DotLottie.setWasmUrl('/pkg/dotlottie-player.wasm'); window.DotLottie = DotLottie; window.libReady = true;</script></body></html>`;
const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u === '/') { res.writeHead(200, { 'content-type': 'text/html' }); return res.end(page); }
  const f = u === '/file.lottie' ? path.resolve(file) : u.startsWith('/pkg/') ? path.join(pkg, u.slice(5)) : null;
  if (!f || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
await new Promise(r => srv.listen(0, '127.0.0.1', r));
const b = await chromium.launch(); const p = await b.newPage();
p.on('pageerror', e => console.error('ERR', String(e)));
await p.goto(`http://127.0.0.1:${srv.address().port}/`); await p.waitForFunction(() => window.libReady === true, null, { timeout: 30000 });
const frames = frameArg.split(',').map(Number);
const res = await p.evaluate(async ([frames, themeArg]) => {
  const cv = document.getElementById('c');
  const load = (cfg) => new Promise((ok, bad) => { const d = new DotLottie({ canvas: cv, autoplay: false, loop: false, renderConfig: { devicePixelRatio: 1, autoResize: false }, ...cfg });
    d.addEventListener('load', () => ok(d)); d.addEventListener('loadError', e => bad(new Error('load ' + (e.error || e)))); });
  let d = await load({ src: '/file.lottie' }); const man = d.manifest; d.destroy();
  const anims = man.animations.map(a => a.id), themes = themeArg === '*' ? [null, ...(man.themes || []).map(t => t.id)] : (themeArg ? themeArg.split(',') : [null]);
  const out = [];
  for (const a of anims) for (const th of themes) {
    const d = await load({ src: '/file.lottie', animationId: a, ...(th ? { themeId: th } : {}) });
    const [w, h] = [d.animationSize().width, d.animationSize().height]; cv.width = w; cv.height = h; d.resize();
    if (!th) d.resetTheme(); const active = d.activeThemeId;
    for (const f of frames) { d.setFrame(Math.min(f, d.totalFrames - 1)); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      out.push({ animation: a, theme: th, active, frame: f, png: cv.toDataURL('image/png'), w, h }); }
    d.destroy();
  }
  return { manifest: man, out };
}, [frames, themeArg || '*']);
for (const r of res.out) fs.writeFileSync(path.join(outDir, `${r.animation}__${r.theme || 'none'}__${String(r.frame).padStart(4, '0')}.png`), Buffer.from(r.png.split(',')[1], 'base64'));
await b.close(); srv.close();
console.log(JSON.stringify({ manifest: res.manifest, rendered: res.out.map(r => ({ animation: r.animation, theme: r.theme, active: r.active || null, frame: r.frame, size: [r.w, r.h] })) }));
