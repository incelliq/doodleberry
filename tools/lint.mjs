// Visual lint for a film from its player page: node tools/lint.mjs films/NAME/build/player.html [step] -> JSON on stdout
import { createRequire } from 'module'; import path from 'path';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 400, height: 400 } });
await p.goto('file://' + path.resolve(process.argv[2])); await p.waitForFunction(() => window.ready);
console.log(JSON.stringify(await p.evaluate(step => window.LINT(step), +(process.argv[3] || 3)))); await b.close();
