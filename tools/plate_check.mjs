// Plate-mode check (WP-15): the same frames of a shot drawn normally and drawn without the set on a transparent
// background, plus the plate itself, saved as PNGs for the test to lay over each other and compare.
//   node tools/plate_check.mjs PLAYER_URL OUT_DIR F,F,...
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [url, out, list] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
const frames = list.split(',').map(Number);
const ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'];
const b = await chromium.launch({ args: ARGS }); const res = {};
for (const mode of ['normal', 'plate']) {
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } }); await p.goto(url); await p.waitForFunction(() => window.ready === true);
  const cdp = await p.context().newCDPSession(p);
  if (mode === 'plate') {
    const r = await p.evaluate(() => window.platePrepare()); res.plate = !!r;
    if (!r) { console.log(JSON.stringify(res)); process.exit(0); }
    fs.writeFileSync(path.join(out, 'plate.png'), Buffer.from(r.png.split(',')[1], 'base64'));
    await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  }
  for (const f of frames) {
    await p.evaluate(async f => { await window.renderFrame(f); }, f);
    await p.evaluate(() => new Promise(r => requestAnimationFrame(() => r())));
    const s = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
    fs.writeFileSync(path.join(out, `${mode}_${f}.png`), Buffer.from(s.data, 'base64'));
  }
  await p.close();
}
await b.close(); console.log(JSON.stringify(res));
