// node dumpcues.mjs URL OUT.json : writes window.CUES from a served film page
import { createRequire } from 'module'; import fs from 'fs';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const [url, out] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
const cues = await p.evaluate(() => window.CUES); fs.writeFileSync(out, JSON.stringify(cues, null, 1)); console.log('cues', cues.length);
await b.close();
