// Foley events for a film from its player page: node tools/foley.mjs films/NAME/build/player.html -> JSON list on stdout
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const page = path.resolve(process.argv[2]);
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 400, height: 400 } });
await p.goto('file://' + page); await p.waitForFunction(() => window.ready);
const ev = await p.evaluate(() => window.FOLEY());
console.log(JSON.stringify(ev)); await b.close();
