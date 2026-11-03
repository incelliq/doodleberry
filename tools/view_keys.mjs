// The camera the SVG player uses at each frame of a shot (auto camera, float drift), as camera keys for the bake (WP-14).
//   node tools/view_keys.mjs PAGE.html SHOT START FPS FRAMES > keys.json
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [page, shot, start, fps, frames] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage();
await p.goto('file://' + path.resolve(page) + `?shot=${shot}&captions=0`);
await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const ts = Array.from({ length: +frames }, (_, i) => +start + i / +fps);
const vs = await p.evaluate(ts => window.viewsAt(ts), ts);
console.log(JSON.stringify(ts.map((t, i) => [+t.toFixed(5), vs[i].map(v => +v.toFixed(3))])));
await b.close();
