// Frame-by-frame renderer. Loads FILM/index.html, which must define
// window.FILM = {width, height, fps, frames} and window.renderFrame(f), then
// pipes PNG screenshots into ffmpeg from N parallel browser workers.
//
//   node render.mjs FILM_DIR [--from S] [--to S] [--workers N] [--out file.mp4]
//                            [--still F,F,...] [--dump-cues]
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

// Use the project's playwright if installed, else the machine's global one.
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const film = path.resolve(args[0]);
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i < 0 ? d : args[i + 1]; };
const flag = k => args.includes(`--${k}`);
const build = path.join(film, 'build');
fs.mkdirSync(build, { recursive: true });

async function openPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => { console.error('page error:', e.message); process.exit(1); });
  await page.goto('file://' + path.join(film, 'index.html'));
  await page.waitForFunction(() => window.FILM && window.FILM.ready === true);
  await page.evaluate(() => document.fonts.ready);
  const meta = await page.evaluate(() => ({ ...window.FILM }));
  await page.setViewportSize({ width: meta.width, height: meta.height });
  return { page, meta };
}

async function shot(page, f) {
  await page.evaluate(f => window.renderFrame(f), f);
  return page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide' });
}

function ffmpeg(outFile, fps) {
  const p = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps),
    '-c:v', 'png', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14',
    '-pix_fmt', 'yuv420p', '-tune', 'animation', outFile], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => p.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg ' + c)))));
  return { p, done };
}

async function main() {
  const browser = await chromium.launch();
  const { page, meta } = await openPage(browser);

  if (flag('dump-cues')) {
    const cues = await page.evaluate(() => window.CUES || []);
    fs.writeFileSync(path.join(build, 'cues.json'), JSON.stringify(cues, null, 1));
    console.log(`cues: ${cues.length}`);
    await browser.close();
    return;
  }

  if (opt('still')) {
    for (const f of opt('still').split(',').map(Number)) {
      fs.writeFileSync(path.join(build, `still-${String(f).padStart(4, '0')}.png`), await shot(page, f));
    }
    await browser.close();
    return;
  }

  const fps = meta.fps;
  const f0 = Math.round(Number(opt('from', 0)) * fps);
  const f1 = Math.min(meta.frames, Math.round(Number(opt('to', meta.frames / fps)) * fps));
  const workers = Number(opt('workers', 4));
  const out = path.resolve(opt('out', path.join(build, 'picture.mp4')));
  const per = Math.ceil((f1 - f0) / workers);
  const t0 = Date.now();
  let doneFrames = 0;

  const pages = [page];
  for (let i = 1; i < workers; i++) pages.push((await openPage(browser)).page);

  const segs = await Promise.all(pages.map(async (pg, i) => {
    const a = f0 + i * per, b = Math.min(f1, a + per);
    const seg = path.join(build, `seg-${i}.mp4`);
    if (a >= b) return null;
    const { p, done } = ffmpeg(seg, fps);
    for (let f = a; f < b; f++) {
      const png = await shot(pg, f);
      if (!p.stdin.write(png)) await new Promise(r => p.stdin.once('drain', r));
      if (++doneFrames % 60 === 0) process.stdout.write(`\r${doneFrames}/${f1 - f0} frames`);
    }
    p.stdin.end();
    await done;
    return seg;
  }));
  await browser.close();

  const list = path.join(build, 'segs.txt');
  fs.writeFileSync(list, segs.filter(Boolean).map(s => `file '${s}'`).join('\n'));
  await new Promise((res, rej) => spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0',
    '-i', list, '-c', 'copy', out], { stdio: 'inherit' }).on('close', c => (c ? rej(c) : res())));
  segs.filter(Boolean).forEach(s => fs.unlinkSync(s));
  console.log(`\n${f1 - f0} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s -> ${out}`);
}

main().catch(e => { console.error(e); process.exit(1); });
