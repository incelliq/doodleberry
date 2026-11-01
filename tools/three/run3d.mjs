// node run3d.mjs page.html out.mp4 [workers]
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import { spawnSync } from 'child_process';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, out, nw = '4'] = process.argv.slice(2);
const dir = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), 'fr-'));
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
const t0 = Date.now(); let total = 0;
await Promise.all(Array.from({ length: +nw }, async (_, w) => {
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('pageerror', e => console.log('ERR', String(e)));
  await p.goto(/^(https?|file):/.test(page) ? page : 'file://' + path.resolve(page)); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  total = await p.evaluate(() => window.FRAMES);
  for (let f = w; f < total; f += +nw) { await p.evaluate(f => window.renderFrame(f), f); fs.writeFileSync(path.join(dir, `f${String(f).padStart(5, '0')}.png`), await p.screenshot({ type: 'png' })); }
}));
await b.close();
console.log(`${total} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', '30', '-i', path.join(dir, 'f%05d.png'), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', out], { stdio: 'inherit' });
fs.rmSync(dir, { recursive: true });
