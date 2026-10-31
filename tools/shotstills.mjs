// Contact sheet of a shot-listed film: one still per shot at given fractions.
//   node tools/shotstills.mjs FILM_DIR OUT_PNG [fractions=0.75] [--cols 6]
import { createRequire } from 'module';
import path from 'path';
import fs from 'fs';
import { spawnSync } from 'child_process';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const [film, out, fr = '0.75'] = process.argv.slice(2);
const fracs = fr.split(',').map(Number);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
const errs = [];
page.on('pageerror', e => errs.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
await page.goto('file://' + path.resolve(film, 'index.html'));
await page.waitForFunction(() => window.FILM && window.FILM.ready === true, null, { timeout: 20000 }).catch(() => {});
if (errs.length) { console.log(errs.join('\n')); process.exit(1); }
const shots = await page.evaluate(() => window.SHOT_TIMES);
const tmp = fs.mkdtempSync('/tmp/claude-0/-home-user-chalklore-infra/1e07a64a-ba11-5ff4-ad45-442a8e19b6a1/scratchpad/ss-');
let k = 0;
for (const s of shots) for (const q of fracs) {
  const f = Math.round((s.t0 + (s.t1 - s.t0) * q) * 30);
  await page.evaluate(f => window.renderFrame(f), f);
  const p = path.join(tmp, `s${String(k++).padStart(3, '0')}.png`);
  await page.screenshot({ path: p });
  console.log(k - 1, s.shot, s.line, (f / 30).toFixed(2));
}
if (errs.length) console.log('ERRORS:\n' + errs.join('\n'));
await browser.close();
const cols = 6, rows = Math.ceil(k / cols);
spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', '1', '-i', path.join(tmp, 's%03d.png'), '-vf', `scale=270:480,tile=${cols}x${rows}`, '-frames:v', '1', out], { stdio: 'inherit' });
console.log('sheet', out, 'dir', tmp);
