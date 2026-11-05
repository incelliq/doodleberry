// Render puppets in given poses to a PNG (loader-level golden tests: bends, controls, views, swaps).
//   node tools/pose_still.mjs SPEC.json OUT.png
// SPEC: {"size": [w, h], "bg": "#f4f3ee", "flush": false, "items": [{"puppet": "path", "x", "y", "pose": {...}, "timeline": {...}, "t": 0}]}
// flush: the picture starts at the image's corner (pixel = unit); without it the page keeps the browser's 8 px body
// margin, as the golden pose frames were made
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [specPath, out] = process.argv.slice(2); const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [w, h] = spec.size || [900, 700];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: w, height: h } });
await p.setContent((spec.flush ? '<style>body{margin:0}</style>' : '') + `<svg id="s" xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" style="background:${spec.bg || '#f4f3ee'}"></svg>`);
for (const f of ['puppet/loader/puppet.js', 'puppet/loader/acting.js']) await p.addScriptTag({ path: path.join(root, f) });
for (const f of fs.readdirSync(path.join(root, 'puppet/clips')).filter(f => f.endsWith('.js'))) await p.addScriptTag({ path: path.join(root, 'puppet/clips', f) });
const items = spec.items.map(it => ({ ...it, puppet: JSON.parse(fs.readFileSync(path.join(root, it.puppet), 'utf8')) }));
await p.evaluate(items => {
  document.getElementById('s').innerHTML = items.map(it => {
    let pose = it.pose || {};
    if (it.timeline) { const L = (window.CLIPLIB || {})[it.puppet.template] || window.CLIPLIB.humanoid; pose = { ...Acting.evaluate(it.puppet, it.timeline, it.t || 0, L.clips, L.presets), ...pose }; }
    return Puppet.render(it.puppet, it.x, it.y, { s: it.s ?? 0.68, ...pose });
  }).join('');
}, items);
await p.screenshot({ path: out }); await b.close();
