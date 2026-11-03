// Frame keys without capturing (WP-26, E14): what tools/three/run3d.mjs writes for each frame it renders (the plate's
// key and a hash of the SVG stage's markup), computed for chosen frames only, so a signed recipe can be checked
// against a fresh re-make of those frames.
//   node tools/frame_keys.mjs PAGE_URL FRAMES(3,40,...) -> {plate, keys: {frame: key}}
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, frameArg] = process.argv.slice(2);
const b = await chromium.launch(); const p = await b.newPage();
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const plate = process.env.DBE_PLATE === '0' ? null : await p.evaluate(() => window.platePrepare ? window.platePrepare().then(r => r && r.key) : null);
const keys = {};
for (const f of frameArg.split(',').map(Number)) {
  keys[f] = await p.evaluate(async f => {
    await window.renderFrame(f);
    const st = document.getElementById('stage'); if (!st || st.tagName.toLowerCase() !== 'svg' || document.querySelector('canvas')) return null;
    const s = st.innerHTML.replace(/blob:[^"]+/g, 'blob');
    let h1 = 0x811c9dc5 | 0, h2 = 0;
    for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = (h2 * 31 + c) | 0; }
    return `${s.length}:${h1 >>> 0}:${h2 >>> 0}`;
  }, f);
}
await b.close();
console.log(JSON.stringify({ plate, keys }));
