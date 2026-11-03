// One film frame drawn large for print (WP-23): the player page at a film time, at a device scale factor, so the
// vector drawing is drawn at print resolution rather than enlarged from a video frame.
//   node tools/still.mjs URL TIME DSF OUT.png [transparent]   (transparent: for a page that draws no background, castonly=1)
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, time, dsf, out, transparent] = process.argv.slice(2);
const b = await chromium.launch();
const probe = await b.newPage(); await probe.goto(url); await probe.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const { w, h } = await probe.evaluate(() => ({ w: window.FILM.width, h: window.FILM.height })); await probe.close();
const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: +dsf });
p.on('pageerror', e => console.log('ERR', String(e)));
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
await p.evaluate(t => window.frameAtTime(t), +time);
await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
await p.screenshot({ path: out, omitBackground: transparent === 'transparent' });
await b.close();
console.log(JSON.stringify({ width: Math.round(w * dsf), height: Math.round(h * dsf) }));
