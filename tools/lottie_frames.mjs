// Lottie frames in lottie-web (WP-23 Lottie QA): render chosen frames of a Lottie JSON (or .tgs) to transparent PNGs.
//   node tools/lottie_frames.mjs ANIMATION.json|.tgs OUT_DIR F,F,...
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import zlib from 'zlib';
const { chromium } = createRequire(import.meta.url)('playwright');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [src, out, list] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
let raw = fs.readFileSync(src); if (src.endsWith('.tgs')) raw = zlib.gunzipSync(raw);
const anim = JSON.parse(raw.toString());
const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: anim.w, height: anim.h } });
await pg.setContent(`<html><body style="margin:0;background:transparent"><div id="a" style="width:${anim.w}px;height:${anim.h}px"></div></body></html>`);
await pg.addScriptTag({ path: path.join(root, 'engine/vendor/lottie/lottie.min.js') });
await pg.evaluate(a => new Promise(res => { window.ANIM = lottie.loadAnimation({ container: document.getElementById('a'), renderer: 'svg', loop: false, autoplay: false, animationData: a }); window.ANIM.addEventListener('DOMLoaded', res); }), anim);
for (const f of list.split(',').map(Number)) {
  await pg.evaluate(f => window.ANIM.goToAndStop(f, true), f);
  await (await pg.$('#a')).screenshot({ path: path.join(out, `lw${String(f).padStart(4, '0')}.png`), omitBackground: true });
}
await b.close(); console.log(JSON.stringify({ frames: list.split(',').length, w: anim.w, h: anim.h, fr: anim.fr }));
