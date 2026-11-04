// Drives the Studio channels view (WP-23) for python -m dbe test '{"film":"outputs"}': node tools/channels_check.mjs URL
// -> what the page drew, and the alpha view checked pixel by pixel against the frame's own alpha channel
import { createRequire } from 'module'; const { chromium } = createRequire(import.meta.url)('playwright');
const [url] = process.argv.slice(2); const b = await chromium.launch(); const p = await b.newPage(); const errs = [];
p.on('pageerror', e => errs.push(String(e)));
await p.goto(url); await p.waitForFunction(() => window.CHANNELS && window.CHANNELS.ready, null, { timeout: 60000 });
const out = { drawn: await p.evaluate(() => CHANNELS.drawn), errs };
// the alpha view's pixels equal the source alpha
out.alpha = await p.evaluate(async () => { const c = document.getElementById('view'); const x = c.getContext('2d');
  document.querySelector('[data-m=a]').click(); await new Promise(r => setTimeout(r, 50));
  const shown = x.getImageData(0, 0, c.width, c.height).data;
  const im = new Image(); im.src = CHANNELS.drawn.src; await im.decode(); const k = document.createElement('canvas'); k.width = im.naturalWidth; k.height = im.naturalHeight;
  const kx = k.getContext('2d'); kx.drawImage(im, 0, 0); const src = kx.getImageData(0, 0, k.width, k.height).data;
  let diff = 0; for (let i = 0; i < src.length; i += 4) diff = Math.max(diff, Math.abs(shown[i] - src[i + 3]));
  return { max_diff: diff, mode: CHANNELS.drawn.mode }; });
console.log(JSON.stringify(out)); await b.close();
