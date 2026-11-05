// WP-15 media in every renderer: the characters' frames from another renderer (transparent PNGs) drawn through the
// player's own medium filter (pencil, crayon, marker, watercolour), read from dbe/player/player.js so there is one
// definition. Each PNG is rewritten in place, at W x H when given (the filter works in film pixels, so a renderer's
// half-size frames are scaled up first).   node tools/media_frames.mjs DIR MEDIUM [PATTERN] [W H]
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [dir, medium, pattern, Ws, Hs] = process.argv.slice(2);
const src = fs.readFileSync(path.join(root, 'dbe/player/player.js'), 'utf8');
const m = src.match(/const MEDIA = (\{[\s\S]*?\n  \});/);
if (!m) { console.error('no MEDIA in player.js'); process.exit(2); }
const MEDIA = new Function(`return ${m[1]};`)();
if (!MEDIA[medium]) { console.error(`unknown medium ${medium}`); process.exit(2); }
const re = new RegExp(pattern || '\\.png$');
const files = fs.readdirSync(dir).filter(f => re.test(f)).sort();
const b = await chromium.launch(); const p = await b.newPage();
let n = 0;
for (const f of files) {
  const fp = path.join(dir, f), data = 'data:image/png;base64,' + fs.readFileSync(fp).toString('base64');
  const [w, h] = Ws && Hs ? [+Ws, +Hs] : await p.evaluate(u => new Promise(res => { const i = new Image(); i.onload = () => res([i.naturalWidth, i.naturalHeight]); i.src = u; }), data);
  await p.setViewportSize({ width: w, height: h });
  await p.setContent(`<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" style="display:block">` +
    `<defs><filter id="medium-${medium}" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">${MEDIA[medium]}</filter></defs>` +
    `<g filter="url(#medium-${medium})"><image href="${data}" x="0" y="0" width="${w}" height="${h}" preserveAspectRatio="none"/></g></svg></body></html>`);
  await p.evaluate(() => new Promise(r => { const i = document.querySelector('image'); if (i.complete !== false) requestAnimationFrame(() => requestAnimationFrame(r)); else i.addEventListener('load', () => requestAnimationFrame(r)); }));
  await p.screenshot({ path: fp, omitBackground: true }); n++;
}
await b.close(); console.log(JSON.stringify({ frames: n, medium }));
