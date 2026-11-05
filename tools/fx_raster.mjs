// Rasterize motion-effect drawings for Synfig (WP-14): node tools/fx_raster.mjs JOBS.json
// JOBS: {"size": [W, H], "items": [{"svg": markup in world coordinates, "box": [x, y, w, h], "out": "file.png"}]}
// Each item is drawn by Chromium exactly as the player draws it, cropped to its box, transparent around it.
import { createRequire } from 'module'; import fs from 'fs';
const { chromium } = createRequire(import.meta.url)('playwright');
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 64, height: 64 } });
for (const it of jobs.items) {
  const [x, y, w, h] = it.box.map(v => Math.round(v));
  await p.setViewportSize({ width: Math.max(1, w), height: Math.max(1, h) });
  await p.setContent(`<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="${x} ${y} ${w} ${h}" style="display:block">${it.svg}</svg></body></html>`);
  await p.screenshot({ path: it.out, omitBackground: true });
}
await b.close();
console.log(JSON.stringify({ rasters: jobs.items.length }));
