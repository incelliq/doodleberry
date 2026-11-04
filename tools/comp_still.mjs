// Compositor stills without a film (WP-42 tests): node tools/comp_still.mjs SPEC.json OUT_DIR
// SPEC: {"size": [w, h], "bg": "#fff", "comp": {...a shot's comp...}, "times": [t, ...]} -> OUT_DIR/c_<i>.png
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const [specPath, out] = process.argv.slice(2); const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..'); const [w, h] = spec.size || [540, 960];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: w, height: h } });
await p.setContent(`<html><body style="margin:0"><svg id="s" xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" style="background:${spec.bg || '#fff'};display:block"></svg></body></html>`);
await p.addScriptTag({ path: path.join(root, 'dbe/player/comp.js') });
fs.mkdirSync(out, { recursive: true });
for (let i = 0; i < spec.times.length; i++) {
  await p.evaluate(([c, t, w, h]) => { document.getElementById('s').innerHTML = COMP.compose({ comp: c }, { W: w, H: h, t, view: [w / 2, h / 2, 1], stage: '', tag: Math.round(t * 30) }); }, [spec.comp, spec.times[i], w, h]);
  await p.screenshot({ path: path.join(out, `c_${i}.png`) });
}
await b.close();
