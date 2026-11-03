// Graph page check (WP-20): with `python -m dbe serve PORT` running, open /graph for FILM, click NODE and report
// what the page shows (the node's state and why), then press Re-make and report the progress seen and the result.
//   node tools/graph_check.mjs PORT FILM NODE [cook]
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
const [port, film, node, cook] = process.argv.slice(2);
const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1300, height: 900 } });
const errors = []; pg.on('pageerror', e => errors.push(String(e)));
await pg.goto(`http://127.0.0.1:${port}/graph?film=${film}`);
await pg.waitForFunction(() => window.GRAPH_READY, null, { timeout: 120000 });
await pg.waitForSelector(`.react-flow__node[data-id="${node}"]`, { timeout: 30000 });
const boxes = await pg.$$eval('.react-flow__node', els => els.length);
await pg.click(`.react-flow__node[data-id="${node}"]`);
const sel = await pg.evaluate(() => window.GRAPH_SELECTED);
const why = await pg.textContent('#info');
let cooked = null, progressSeen = [];
if (cook) {
  await pg.click('#cook');
  const t0 = Date.now();
  while (Date.now() - t0 < 1800000) {
    await pg.waitForTimeout(1500);
    const w = await pg.evaluate(() => { const i = document.querySelector('#bar i'); return i ? i.style.width : null; });
    if (w) progressSeen.push(w);
    if (await pg.evaluate(() => !!window.COOK_RESULT)) break;
  }
  cooked = await pg.evaluate(() => window.COOK_RESULT && { status: window.COOK_RESULT.status, made: (window.COOK_RESULT.result || {}).made, events: (window.COOK_RESULT.events || []).map(e => e.stage + (e.shot ? ':' + e.shot : '') + (e.state ? ':' + e.state : '')) });
}
const afterNode = await pg.evaluate(n => window.GRAPH.nodes.find(x => x.id === n) || {}, node), after = afterNode.state, afterWhy = afterNode.why;
console.log(JSON.stringify({ boxes, state: sel && sel.state, why: (sel && sel.why) || [], text: why.slice(0, 300), progress: [...new Set(progressSeen)].slice(-6), cooked, after, afterWhy, errors }));
await b.close();
