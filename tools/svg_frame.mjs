// A film frame as a standalone SVG, or a stretch of frames as one animated SVG (WP-23).
//   node tools/svg_frame.mjs URL OUT.svg still TIME
//   node tools/svg_frame.mjs URL OUT.svg anim START END FPS
// The player draws every frame as SVG; this keeps that markup and makes it standalone: blob images (rasterized static
// layers) become data URIs, the fonts its text uses are embedded as data URIs, and each text element carries its
// computed font. The animated form holds each frame as a group shown for 1/FPS s (SMIL, discrete, looping), with ids
// prefixed per frame so their definitions cannot clash, and images that repeat exactly stored once (<use>).
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const [url, out, mode, ...rest] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage();
await p.goto(url); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const pageDir = path.dirname(new URL(url).pathname);

async function grab(t) {
  await p.evaluate(t => window.frameAtTime(t), t);
  return await p.evaluate(async () => {
    const st = document.getElementById('stage');
    for (const im of st.querySelectorAll('image')) {   // blob: URLs live only in this page
      const h = im.getAttribute('href') || im.getAttribute('xlink:href') || '';
      if (!h.startsWith('blob:')) continue;
      const bl = await (await fetch(h)).blob();
      const du = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(bl); });
      im.removeAttribute('xlink:href'); im.setAttribute('href', du);
    }
    const fams = new Set();
    for (const el of st.querySelectorAll('text, tspan')) {
      const cs = getComputedStyle(el);
      el.setAttribute('font-family', cs.fontFamily); el.setAttribute('font-weight', cs.fontWeight);
      for (const f of cs.fontFamily.split(',')) fams.add(f.trim().replace(/^["']|["']$/g, ''));
    }
    const faces = [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } })
      .filter(r => r.type === 5 && fams.has((r.style.getPropertyValue('font-family') || '').trim().replace(/^["']|["']$/g, ''))).map(r => r.cssText);
    // the film's own size (the stage element carries none): the SVG is the frame, 1:1
    return { inner: st.innerHTML, w: window.FILM.width, h: window.FILM.height, vb: st.getAttribute('viewBox') || `0 0 ${window.FILM.width} ${window.FILM.height}`, faces };
  });
}

function embedFaces(faces) {   // url("../../../engine/fonts/...") -> data URI
  return faces.map(css => css.replace(/url\("([^"]+)"\)/g, (m, u) => {
    if (u.startsWith('data:')) return m;
    const f = u.startsWith('file://') ? new URL(u).pathname : path.resolve(pageDir, u);
    if (!fs.existsSync(f)) return m;
    const ext = path.extname(f).slice(1).toLowerCase(), mime = { woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', otf: 'font/otf' }[ext] || 'application/octet-stream';
    return `url("data:${mime};base64,${fs.readFileSync(f).toString('base64')}")`;
  })).join('\n');
}

const head = (w, h, vb) => `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${w}" height="${h}" viewBox="${vb || `0 0 ${w} ${h}`}">`;
if (mode === 'still') {
  const g = await grab(+rest[0]);
  fs.writeFileSync(out, `${head(g.w, g.h, g.vb)}<style>${embedFaces(g.faces)}</style>${g.inner}</svg>`);
  console.log(JSON.stringify({ out, bytes: fs.statSync(out).size, fonts: g.faces.length }));
} else {
  const [t0, t1, fps] = rest.map(Number); const n = Math.max(1, Math.round((t1 - t0) * fps)), dur = n / fps;
  const faces = new Set(), imgs = new Map(); let defs = '', body = '', w, h, vb;
  for (let k = 0; k < n; k++) {
    const g = await grab(t0 + k / fps); w = g.w; h = g.h; vb = g.vb; g.faces.forEach(f => faces.add(f));
    let s = g.inner.replace(/\bid="([^"]+)"/g, (m, id) => `id="f${k}_${id}"`)
      .replace(/url\(#([^)]+)\)/g, (m, id) => `url(#f${k}_${id})`)
      .replace(/(xlink:)?href="#([^"]+)"/g, (m, x, id) => `${x || ''}href="#f${k}_${id}"`);
    s = s.replace(/<image\b[^>]*?(\/>|>\s*<\/image>)/g, tag => {   // an image repeated exactly is stored once (the browser writes <image ...></image>)
      if (tag.length < 2000) return tag;
      if (!imgs.has(tag)) { const id = `img${imgs.size}`; imgs.set(tag, id); defs += tag.replace('<image', `<image id="${id}"`); }
      return `<use href="#${imgs.get(tag)}"/>`;
    });
    const kt = [0, k / n, (k + 1) / n, 1].map(v => +v.toFixed(6));
    const vals = k === 0 ? 'inline;none;none' : k === n - 1 ? 'none;inline;inline' : 'none;inline;none';
    const times = k === 0 ? `0;${kt[2]};1` : k === n - 1 ? `0;${kt[1]};1` : `0;${kt[1]};${kt[2]}`;
    body += `<g display="${k === 0 ? 'inline' : 'none'}"><animate attributeName="display" values="${vals}" keyTimes="${times}" dur="${dur}s" calcMode="discrete" repeatCount="indefinite"/>${s}</g>`;
  }
  fs.writeFileSync(out, `${head(w, h, vb)}<style>${embedFaces([...faces])}</style><defs>${defs}</defs>${body}</svg>`);
  console.log(JSON.stringify({ out, bytes: fs.statSync(out).size, frames: n, fps, shared_images: imgs.size }));
}
await b.close();
