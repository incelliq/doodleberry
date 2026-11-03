// Model sheet or a board for a puppet as a PNG: node tools/sheet.mjs PUPPET.json OUT.png [sheet|mouth|expressions|turnaround]
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [pupPath, out, kind = 'sheet'] = process.argv.slice(2);
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1800, height: 1100 } });
await p.setContent(`<html><head><style>@font-face{font-family:'Fredoka';src:url('file://${root}/engine/fonts/Fredoka.ttf')}body{margin:0}</style></head><body><div id="s"></div></body></html>`);
for (const f of ['puppet/loader/puppet.js', 'puppet/loader/acting.js', 'puppet/loader/sheet.js']) await p.addScriptTag({ path: path.join(root, f) });
for (const f of fs.readdirSync(path.join(root, 'puppet/clips')).filter(f => f.endsWith('.js'))) await p.addScriptTag({ path: path.join(root, 'puppet/clips', f) });
const P = JSON.parse(fs.readFileSync(path.resolve(pupPath), 'utf8'));
await p.evaluate(([P, kind]) => { const L = (window.CLIPLIB || {})[P.template] || window.CLIPLIB.humanoid; document.getElementById('s').innerHTML = kind === 'sheet' ? Sheet.build(P, L) : Sheet.board(P, kind, L); }, [P, kind]);
await p.waitForTimeout(200); await (await p.$('#s svg')).screenshot({ path: out }); await b.close();
