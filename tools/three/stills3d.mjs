// node stills3d.mjs URL OUT.jpg t1,t2,...   (renders frames at the given seconds into a contact sheet)
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import os from 'os'; import { spawnSync } from 'child_process';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [url, out, ts] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 }).catch(() => {});
if (errs.length) { console.log(errs.join('\n')); }
const dir = fs.mkdtempSync(path.join(path.dirname(path.resolve(out)), 'st-')); let k = 0;
for (const t of ts.split(',').map(Number)) { await p.evaluate(f => window.renderFrame(f), Math.round(t * 30)); fs.writeFileSync(path.join(dir, `s${String(k++).padStart(3, '0')}.png`), await p.screenshot({ type: 'png' })); }
await b.close();
spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', '1', '-i', path.join(dir, 's%03d.png'), '-vf', `scale=270:480,tile=${Math.min(k, 6)}x${Math.ceil(k / 6)}`, '-frames:v', '1', out], { stdio: 'inherit' });
fs.rmSync(dir, { recursive: true }); console.log('ok', k, errs.length ? 'ERRORS' : '');
