// Shot player: renders any frame of a shots.json film in the browser (the SVG renderer, background plates for the
// other renderers, and the interactive web export). Query: ?shot=<id> (render that shot) | ?bg=1 (set only) | none (whole film); bubbles=0 leaves speech bubbles out (comics draw their own).
(function () {
  const S = window.SHOTS, T = window.TIMING || {}, PUP = window.PUPPETS || {}, LIB = (window.CLIPLIB || {}).humanoid || { clips: {}, presets: {} };
  const q = new URLSearchParams(location.search);
  const W = (S.size || [1080, 1920])[0], H = (S.size || [1080, 1920])[1], FPS = S.fps || 30;
  const stage = document.getElementById('stage');
  stage.setAttribute('viewBox', `0 0 ${W} ${H}`); stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const words = (T.lines || []).flatMap(l => l.words.map(w => ({ ...w, speaker: l.speaker })));
  const shotAt = t => S.shots.reduce((a, s) => (t >= s.start ? s : a), S.shots[0]);
  const placeAt = (pl, t) => Acting.placeAt(pl, t);   // {x, y, s, flip}, keyed, or {path} (WP-11 walks along a path)

  function captions(t, style) {
    const w = words.filter(v => v.start <= t + 0.05 && v.end + 0.2 > t);
    if (!w.length) return '';
    const text = w.slice(-3).map(v => v.text.replace(/[.,?!]$/, '')).join(' ').toUpperCase();
    const size = 84, pw = Math.min(980, text.length * size * 0.58 + 80);
    return `<g transform="translate(${W / 2} ${H - 300})"><rect x="${-pw / 2}" y="${-size * 0.95}" width="${pw}" height="${size * 1.25}" rx="${size * 0.62}" fill="#1a0f08" fill-opacity="0.82"/>` +
      `<text x="0" y="0" font-size="${size}" font-weight="700" text-anchor="middle" fill="#fff" stroke="#24160e" stroke-width="12" paint-order="stroke" stroke-linejoin="round">${text}</text></g>`;
  }
  // ---------- doodle style: boil, ink overlays, speech bubbles ----------
  const SCRIPT = window.SCRIPT || {};
  const libFor = p => (window.CLIPLIB || {})[p.template] || LIB;
  // a shot's palette variant (WP-16: night, sick, cold, warm) recolours its characters; recoloured once per puppet and variant
  const VARIANTS = {};
  const puppetFor = (path, v) => { const p = PUP[path]; if (!p || !v || !(window.PALETTE_VARIANTS || {})[v]) return p;
    const k = path + '|' + v; return VARIANTS[k] || (VARIANTS[k] = Puppet.recolour(p, window.PALETTE_VARIANTS[v])); };
  const hash = (a, b) => { let h = (a * 374761393 + b * 668265263) | 0; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // ---------- writing systems (WP-25): a rounded font per script after the Latin ones; direction; widths ----------
  const SFONTS = window.SCRIPT_FONTS || [], XF = SFONTS.map(f => `'${f.family}'`).join(',') || "'Noto Sans Sinhala'";
  const LANG = S.lang || 'en', RTLF = S.dir === 'rtl', LOCALE = S.locale || null;   // RTLF: the film reads right to left
  const reOf = fs => fs.length ? new RegExp('[' + fs.map(f => f.ranges).join('') + ']') : /(?!)/;
  const RTL_RE = reOf(SFONTS.filter(f => f.rtl)), NOSPACE_RE = reOf(SFONTS.filter(f => f.nospace)), WIDE_RE = /[\u1100-\u11ff\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]/;
  // scripts whose letters change shape with their neighbours or stack marks: never drawn a letter at a time
  const COMPLEX_RE = reOf(SFONTS.filter(f => !/greek|hangul|han/.test(f.script)));
  // width in Latin letters (the unit the layout code was written in, half the font size each): Latin text keeps its old
  // estimate (one per letter); other scripts are measured in the fonts they are drawn in, once their fonts have loaded
  const MEASURE = document.createElement('canvas').getContext('2d'), EMCACHE = new Map();
  const em = str => {
    str = String(str);
    if (!COMPLEX_RE.test(str) && !WIDE_RE.test(str) && !RTL_RE.test(str)) return [...str].length;
    if (!EMCACHE.has(str)) { MEASURE.font = `100px ${HAND}`; EMCACHE.set(str, MEASURE.measureText(str).width / 50); }
    return EMCACHE.get(str);
  };
  const SEG_G = Intl.Segmenter ? new Intl.Segmenter(LANG, { granularity: 'grapheme' }) : null, SEG_W = Intl.Segmenter ? new Intl.Segmenter(LANG, { granularity: 'word' }) : null;
  const graphemes = str => SEG_G ? [...SEG_G.segment(String(str))].map(x => x.segment) : [...String(str)];
  const nospace = str => NOSPACE_RE.test(str);
  const tokens = str => nospace(str) && SEG_W ? [...SEG_W.segment(String(str))].map(x => x.segment).filter(x => x.trim()) : String(str).split(/\s+/);
  const INK = '#181e26', HAND = `'Patrick Hand','Fredoka',${XF},sans-serif`;
  // ---------- static-layer cache (WP-15) ----------
  // A set whose markup does not change (a paper page with its grain filter, say) is rasterized once and every frame
  // shows that image: filters such as full-frame grain cost the browser ~0.5 s a frame in software, the image almost
  // nothing. Only where the set is drawn 1:1 (no camera move, float or depth planes: a scaled raster would soften),
  // and only self-contained markup (no text, which needs the page's fonts; no external images). The image is a blob
  // URL, so the frame's markup stays short; it is a pure function of the set's markup, so frames stay pure.
  const RASTER = new Map(), PENDING = [];
  const strHash = str => { let h1 = 0x811c9dc5 | 0, h2 = 0; for (let i = 0; i < str.length; i++) { const c = str.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = (h2 * 31 + c) | 0; } return `${str.length}:${h1 >>> 0}:${h2 >>> 0}`; };
  const rasterOk = (sh, m) => q.get('rastercache') !== '0' && !sh.camera && !sh.camera_auto && !(sh.style || {}).float && !sh.comp && !/<text|<foreignObject|href="(?!data:|#)/.test(m);
  function rasterize(m) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${m}</svg>`;
    return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg); })
      .then(im => { const c = document.createElement('canvas'); c.width = W; c.height = H; c.getContext('2d').drawImage(im, 0, 0); return new Promise(r => c.toBlob(r, 'image/png')); })
      .then(b => URL.createObjectURL(b));
  }
  // Plate mode (WP-15): when a shot's set is the same on every frame, the renderer asks for it once as a plate
  // (window.platePrepare), the page then draws frames without it on a transparent background, and the frames are laid
  // over the plate when encoding. PNG-encoding a full frame of paper grain is most of a frame's cost; the frames
  // without it compress in a fraction of the time.
  const PLATE = { on: false };
  window.platePrepare = async () => {
    if (bgOnly || castOnly || q.get('rastercache') === '0' || !window.FRAMES) return null;
    let key = null, markup = null;
    for (let f = 0; f < window.FRAMES; f++) {
      const t = toFilm(toCut(t0) + f / FPS), sh = only || shotAt(t), st = sh.style || {}, tq = st.step ? Math.floor(t * st.step + 1e-6) / st.step : t;
      const m = ((window.SETS || {})[sh.set || 'plain'] || window.SETS.plain).draw(tq, sh.set_opts || {}, W, H);
      if (!rasterOk(sh, m)) return null;
      const k = strHash(m); if (key === null) { key = k; markup = m; } else if (k !== key) return null;
    }
    const url = await rasterize(markup); const blob = await (await fetch(url)).blob();
    const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
    PLATE.on = true; document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent';
    return { png: b64, key };
  };
  function staticLayer(sh, m) {
    if (!m || !rasterOk(sh, m)) return m;
    const k = strHash(m), r = RASTER.get(k);
    if (r && r.url) return `<image data-k="${k}" href="${r.url}" x="0" y="0" width="${W}" height="${H}"/>`;   // data-k: what it shows (blob URLs differ by run)
    if (!r) { const e = { url: null }; e.p = rasterize(m).then(u => { e.url = u; }, () => { e.url = null; e.failed = true; }); RASTER.set(k, e); }
    if (!RASTER.get(k).failed) PENDING.push(RASTER.get(k).p);
    return m;
  }
  // WP-15 boil only while moving ("boil": {"while_moving": true}): the line boil's phase advances on a boil step only if
  // a character moved during it (root or any part, beyond `still` degrees or px), so still drawings hold still; on a
  // still step the phase is that of the last moving one (looked for over at most 2 s back). Poses here leave out
  // springs (cheap, and a spring only follows motion already counted). BOILK: this frame's phase, set by frameAt
  let BOILK = null;
  const boilStep = (st, t) => Math.floor(t * ((st.boil || {}).fps || 12) + 1e-6);
  function castMotion(sh, t0, t1) {
    let m = 0;
    for (const c of sh.cast || []) {
      const p = puppetFor(c.puppet, sh.palette_variant); if (!p) continue;
      const L = libFor(p), tl = { ...(c.timeline || {}), springs: false, blink: false };
      if (tl.visemes_from) { tl.visemes = (T.visemes || {})[tl.visemes_from] || []; delete tl.visemes_from; }
      const pl = c.place || { x: W / 2, y: H * 0.8 }, [x0, y0] = placeAt(pl, t0), [x1, y1] = placeAt(pl, t1);
      const a0 = Acting.evaluate(p, tl, t0, L.clips, L.presets).angles || {}, a1 = Acting.evaluate(p, tl, t1, L.clips, L.presets).angles || {};
      m = Math.max(m, Math.hypot(x1 - x0, y1 - y0));
      for (const k of new Set([...Object.keys(a0), ...Object.keys(a1)])) m = Math.max(m, Math.abs((a1[k] || 0) - (a0[k] || 0)));
    }
    return m;
  }
  function boilPhase(sh, st, t) {
    const b = st.boil || {}, fps = b.fps || 12, n = b.frames || 8, k = boilStep(st, t);
    if (!b.while_moving) return k % n;
    for (let j = k; j > k - 2 * fps; j--) if (castMotion(sh, (j - 1) / fps, j / fps) > (b.still ?? 0.5)) return j % n;
    return 0;
  }
  const boilId = (st, t) => `boil-${BOILK != null ? BOILK : boilStep(st, t) % ((st.boil || {}).frames || 8)}`;
  function boilDefs(st, t) {
    const b = st.boil; if (!b) return '';
    const k = BOILK != null ? BOILK : boilStep(st, t) % (b.frames || 8);
    // the region needs only room for the displacement (scale/2 = 2.5 px at the default 5); a tight region is ~25% less
    // work for the browser (WP-15), and the noise is in user space, so the pixels inside are the same
    const m = Math.max(0.5, Math.min(10, (b.amount ?? 5) * 0.6));
    // the id carries the boil phase (as filter ids carry the frame tag): with one fixed id Chrome painted the same
    // boil differently depending on the frames before it (WP-15); within a step the markup still repeats exactly
    return `<defs><filter id="boil-${k}" x="-${m}%" y="-${m}%" width="${100 + 2 * m}%" height="${100 + 2 * m}%"><feTurbulence type="fractalNoise" baseFrequency="${b.freq || 0.022}" numOctaves="2" seed="${k + 1}"/>` +
      `<feDisplacementMap in="SourceGraphic" scale="${b.amount ?? 5}" xChannelSelector="R" yChannelSelector="G"/></filter></defs>`;
  }
  function overlay(o, t) {
    if (o.type === 'sign') { const fs = o.size || 56, w = em(o.text) * fs * 0.52 + 50, h = fs * 1.5, x = o.x, y = o.y;
      return `<g stroke="${INK}" stroke-width="4" stroke-linecap="round" fill="none"><path d="M${x - w * 0.32} ${y - h * 1.1} L${x - w * 0.28} ${y}"/><path d="M${x + w * 0.32} ${y - h * 1.1} L${x + w * 0.28} ${y}"/>` +
        `<rect x="${x - w / 2}" y="${y}" width="${w}" height="${h}" rx="6" fill="#f6f5ef"/></g><text x="${x}" y="${y + h * 0.7}" font-family="${HAND}" font-size="${fs}" text-anchor="middle" fill="${INK}">${esc(o.text)}</text>`; }
    if (o.type === 'text') return `<text x="${o.x}" y="${o.y}" font-family="${HAND}" font-size="${o.size || 58}" text-anchor="middle" fill="${o.color || '#707a84'}">${esc(o.text)}</text>`;
    if (o.type === 'kinetic') return kinetic(o, t);
    return explainer(o, t);
  }

  // a word's width in its own font (a canvas measures it as the page will draw it; the fonts are loaded before frames)
  const _tw = {}, _tctx = document.createElement('canvas').getContext('2d');
  const textWidth = (str, font) => { const k = font + '|' + str; if (_tw[k] == null) { _tctx.font = font; _tw[k] = _tctx.measureText(str).width; } return _tw[k]; };
  // WP-15 kinetic typography: {type: "kinetic", text, x, y, size, line: "l2" | start + every, style: "pop" | "rise" |
  // "slide", width, color, accent: [word indexes]}: each word arrives as it is spoken (the line's own word times, by
  // position; without a line, every `every` s from start), over 0.25 s; wrapped into centred rows of at most `width`
  // px; a pure function of t
  function kinetic(o, t) {
    const fs = o.size || 72, ws = tokens(o.text), maxW = o.width || W * 0.8, gap = fs * 0.3, wOf = w => textWidth(w, `700 ${fs}px ${BODY}`);
    const ln = o.line && (T.lines || []).find(l => l.id === o.line), lw = ln ? (ln.words || []) : [];
    const at = i => lw.length ? (lw[Math.min(i, lw.length - 1)].start + (i >= lw.length ? (i - lw.length + 1) * (o.every || 0.3) : 0)) : (o.start ?? 0) + i * (o.every || 0.3);
    const rows = []; let cur = [], cw = 0;
    ws.forEach((w, i) => { const ww = wOf(w); if (cur.length && cw + gap + ww > maxW) { rows.push([cur, cw]); cur = []; cw = 0; } cur.push([w, i, ww]); cw += (cur.length > 1 ? gap : 0) + ww; });
    if (cur.length) rows.push([cur, cw]);
    let out = '';
    rows.forEach(([row, rw], r) => {
      let x = o.x - rw / 2; const y = o.y + r * fs * 1.25;
      const order = RTLF ? [...row].reverse() : row;
      for (const [w, i, ww] of order) {
        const u = ease((t - at(i)) / 0.25);
        if (u > 0) {
          const cx = x + ww / 2, st = o.style || 'pop';
          const tr = st === 'rise' ? `translate(0 ${((1 - u) * fs * 0.6).toFixed(2)})` : st === 'slide' ? `translate(${((1 - u) * -fs).toFixed(2)} 0)` : `translate(${cx.toFixed(2)} ${y.toFixed(2)}) scale(${(0.6 + 0.4 * u).toFixed(3)}) translate(${(-cx).toFixed(2)} ${(-y).toFixed(2)})`;
          const col = (o.accent || []).includes(i) ? (o.accent_color || BP.highlight || '#e8590c') : (o.color || INK);
          out += `<text x="${cx.toFixed(2)}" y="${y.toFixed(2)}" font-family="${BODY}" font-weight="700" font-size="${fs}" text-anchor="middle" fill="${col}" opacity="${u.toFixed(3)}" transform="${tr}">${esc(w)}</text>`;
        }
        x += ww + gap;
      }
    });
    return `<g class="kinetic">${out}</g>`;
  }

  // ---------- explainer scene library (plan 1.13): every element is a pure function of t ----------
  const BODY = `'Fredoka',${XF},sans-serif`, MONO = `'Atkinson Mono',${XF},monospace`;
  // a left-aligned line in a box [x0, x1]: from the right in a right-to-left film
  const lead = (x0, x1, pad) => RTLF ? `x="${x1 - pad}" text-anchor="end"` : `x="${x0 + pad}"`, trail = (x0, x1, pad) => RTLF ? `x="${x0 + pad}"` : `x="${x1 - pad}" text-anchor="end"`;
  // brand defaults (films that set "brand": true get window.BRAND); explicit overlay values always win
  const BR = window.BRAND || null, BP = (BR && BR.palette) || {};
  const brandColor = (v, d) => v || (BR ? d : undefined);
  const ease = u => (u = Math.min(1, Math.max(0, u)), u * u * (3 - 2 * u));
  const since = (o, t) => t - (o.start ?? 0);
  const fmt = (v, d = 0) => Number(v).toLocaleString(LOCALE || 'en-US', { minimumFractionDigits: d, maximumFractionDigits: d });   // digits and separators of the film's locale (WP-25)
  const dataOf = o => o.data || (o.data_from ? String(o.data_from).split('.').reduce((a, k) => (a || {})[k], window.DATA || {}) : []) || [];
  const plate = (x, y, w, h, fill = '#fbfaf5') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${fill}" stroke="${INK}" stroke-width="3"/>`;
  function wrapText(text, maxChars) {   // by width (wide CJK letters count double); scripts without spaces break at words found by the segmenter
    const out = [], sep = nospace(text) ? '' : ' '; let cur = '';
    for (const w of tokens(text)) { const nx = cur ? cur + sep + w : w; if (em(nx) > maxChars && cur) { out.push(cur); cur = w; } else cur = nx; }
    if (cur) out.push(cur); return out; }
  function explainer(o, t) {
    const u = ease(since(o, t) / 0.35), slide = (1 - u) * 40, op = u.toFixed(3);
    const fsT = o.title_size || (H > W ? 64 : 56), fsB = o.size || (H > W ? 42 : 36);
    if (o.type === 'card') { // a definition card: term in bold, plain-language meaning below
      const w = o.w || (H > W ? 860 : 900), lines = wrapText(o.body || '', Math.floor(w / (fsB * 0.52)));
      const h = fsT * 1.6 + lines.length * fsB * 1.25 + 40, x = o.x ?? (W - w) / 2, y = (o.y ?? H * 0.2) + slide;
      return `<g opacity="${op}">${plate(x, y, w, h)}<text ${lead(x, x + w, 36)} y="${y + fsT * 1.15}" font-family="${BODY}" font-weight="700" font-size="${fsT}" fill="${o.color || BP.primary || '#1a62c2'}">${esc(o.title || '')}</text>` +
        lines.map((l, i) => `<text ${lead(x, x + w, 36)} y="${y + fsT * 1.6 + 20 + (i + 0.8) * fsB * 1.25}" font-family="${BODY}" font-size="${fsB}" fill="${INK}">${esc(l)}</text>`).join('') + `</g>`;
    }
    if (o.type === 'counter') { // a number that counts up to its value, with its label
      const v = (o.from ?? 0) + ((o.to ?? 0) - (o.from ?? 0)) * ease(since(o, t) / (o.duration ?? 1.2)), fs = o.size || (H > W ? 150 : 120);
      return `<g opacity="${op}"><text x="${o.x ?? W / 2}" y="${o.y ?? H * 0.4}" text-anchor="middle" font-family="${BODY}" font-weight="700" font-size="${fs}" fill="${o.color || INK}">${esc((o.prefix || '') + fmt(v, o.decimals || 0) + (o.suffix || ''))}</text>` +
        (o.label ? `<text x="${o.x ?? W / 2}" y="${(o.y ?? H * 0.4) + fsB * 1.6}" text-anchor="middle" font-family="${BODY}" font-size="${fsB}" fill="#4a4e57">${esc(o.label)}</text>` : '') + `</g>`;
    }
    if (o.type === 'console') { // typed terminal lines; lines starting with "!" are output in the error colour
      const fs = o.size || (H > W ? 34 : 30), w = o.w || (H > W ? 900 : 1100), lh = fs * 1.4, x = o.x ?? (W - w) / 2, y = o.y ?? H * 0.3, cps = o.cps || 28;
      let budget = Math.max(0, since(o, t)) * cps, rowsOut = '';
      (o.lines || []).forEach((ln, i) => { const isOut = ln.startsWith('!') || ln.startsWith('>'); const txt = isOut ? ln.slice(1) : ln;
        const n = isOut ? (budget > 0 ? txt.length : 0) : Math.min(txt.length, Math.floor(budget)); budget -= isOut ? 0 : txt.length + 6;
        if (n > 0 || (!isOut && budget > -6)) rowsOut += `<text x="${x + 28}" y="${y + 44 + (i + 0.7) * lh}" font-family="${MONO}" font-size="${fs}" fill="${ln.startsWith('!') ? '#b8560f' : isOut ? '#9fb0c0' : '#e8ecef'}"${ln.startsWith('!') ? ' font-weight="700"' : ''}>${esc((isOut ? '' : '$ ') + txt.slice(0, n))}</text>`; });
      return `<g opacity="${op}"><rect x="${x}" y="${y}" width="${w}" height="${44 + (o.lines || []).length * lh + 24}" rx="12" fill="#1d201a"/>` +
        `<circle cx="${x + 26}" cy="${y + 22}" r="7" fill="#e0584a"/><circle cx="${x + 48}" cy="${y + 22}" r="7" fill="#e8b33a"/><circle cx="${x + 70}" cy="${y + 22}" r="7" fill="#5aae5a"/>${rowsOut}</g>`;
    }
    if (o.type === 'bars') { // a bar chart from data ([[label, value], ...] or data_from: "key.path" in data.json)
      const data = dataOf(o), w = o.w || (H > W ? 900 : 1300), h = o.h || (H > W ? 700 : 560), x = o.x ?? (W - w) / 2, y = o.y ?? H * 0.25;
      const max = o.max || Math.max(...data.map(d => d[1]), 1), n = data.length || 1, bw = w / n * 0.62, g = ease(since(o, t) / (o.duration ?? 1.0));
      let svg = `<g opacity="${op}"><path d="M${x} ${y + h} L${x + w} ${y + h}" stroke="${INK}" stroke-width="3"/>`;
      data.forEach(([lab, v], i) => { const bh = (v / max) * (h - 90) * g, bx = x + ((RTLF ? n - 1 - i : i) + 0.19) * (w / n);   // WP-25: a right-to-left film reads its bars from the right
        svg += `<rect x="${bx}" y="${y + h - bh}" width="${bw}" height="${bh}" fill="${(o.colors || [])[i] || o.color || '#1a62c2'}" stroke="${INK}" stroke-width="2"/>` +
          `<text x="${bx + bw / 2}" y="${y + h + fsB * 1.1}" text-anchor="middle" font-family="${BODY}" font-size="${fsB * 0.8}" fill="${INK}">${esc(lab)}</text>` +
          (g > 0.98 ? `<text x="${bx + bw / 2}" y="${y + h - bh - 14}" text-anchor="middle" font-family="${BODY}" font-weight="700" font-size="${fsB * 0.8}" fill="${INK}">${esc((o.prefix || '') + fmt(v, o.decimals || 0) + (o.unit || ''))}</text>` : ''); });
      return svg + (o.title ? `<text ${lead(x, x + w, 12)} y="${y - 20}" font-family="${BODY}" font-weight="700" font-size="${fsB}" fill="${INK}">${esc(o.title)}</text>` : '') + `</g>`;
    }
    if (o.type === 'plate') { // WP-16: an anatomy plate (Servier Medical Art, CC BY 4.0) on a card, labels with leader lines, its credit below
      const P = (window.PLATES || {})[o.plate]; if (!P) return '';
      const w = o.w || (H > W ? 560 : 520), h = w * P.size[1] / P.size[0], x = o.x ?? (W - w) / 2, y = o.y ?? H * 0.2;
      let svg = `<g opacity="${op}"><rect x="${x - 24}" y="${y - 24}" width="${w + 48}" height="${h + 48}" rx="18" fill="#fffdf6" stroke="${INK}" stroke-width="4"/>` +
        `<image href="${P.file}" x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="none"/>`;
      for (const L of o.labels || []) {
        const a = L.start == null ? 1 : Math.max(0, Math.min(1, (t - L.start) / 0.35)); if (a <= 0) continue;
        const px = x + L.at[0] * w, py = y + L.at[1] * h, right = (L.side || (L.at[0] > 0.5 ? 'right' : 'left')) === 'right';
        const fs = L.size || fsB * 0.8, tw = em(L.text) * fs * 0.56 + 10, m = W * 0.04;   // the label stays inside the frame: its leader shortens or crosses the card
        const lx = right ? Math.min(x + w + 40, W - m - tw) : Math.max(x - 40, m + tw);
        svg += `<g opacity="${a.toFixed(3)}"><path d="M${px} ${py} L${lx} ${py}" stroke="${INK}" stroke-width="3"/><circle cx="${px}" cy="${py}" r="7" fill="${INK}"/>` +
          `<text x="${lx + (right ? 10 : -10)}" y="${py + fs * 0.35}" text-anchor="${right ? 'start' : 'end'}" font-family="${BODY}" font-weight="700" font-size="${fs}" fill="${INK}" stroke="#fffdf6" stroke-width="${fs * 0.2}" paint-order="stroke">${esc(L.text)}</text></g>`;
      }
      return svg + `<text x="${x + w / 2}" y="${y + h + 48 + 30}" text-anchor="middle" font-family="${MONO}" font-size="${H > W ? 24 : 20}" fill="#4a4e57">${esc(o.credit || 'Servier Medical Art, CC BY 4.0')}</text></g>`;
    }
    if (o.type === 'quote') {
      const w = o.w || (H > W ? 880 : 1200), lines = wrapText(o.text || '', Math.floor(w / (fsB * 0.5))), x = o.x ?? (W - w) / 2, y = (o.y ?? H * 0.25) + slide, h = lines.length * fsB * 1.3 + (o.by ? fsB * 1.6 : 0) + 60;
      return `<g opacity="${op}">${plate(x, y, w, h, '#fffdf4')}` + lines.map((l, i) => `<text ${lead(x, x + w, 40)} y="${y + 50 + (i + 0.6) * fsB * 1.3}" font-family="${BODY}" font-size="${fsB}" font-style="italic" fill="${INK}">${esc((i ? '' : '“') + l + (i === lines.length - 1 ? '”' : ''))}</text>`).join('') +
        (o.by ? `<text ${trail(x, x + w, 40)} y="${y + h - 30}" font-family="${MONO}" font-size="${Math.max(H > W ? 30 : 24, fsB * 0.7)}" fill="#4a4e57">${esc('— ' + o.by)}</text>` : '') + `</g>`;
    }
    if (o.type === 'citation') { // small mono source line on a soft plate (inside the safe area by default)
      const fs = o.size || (H > W ? 30 : 24), w = em(o.text) * fs * 0.6 + 40, x0 = o.x ?? (H > W ? 64 : W * 0.05), x = RTLF ? W - x0 - w : x0, y = o.y ?? (H > W ? 1490 : H * 0.88);
      return `<g opacity="${op}"><rect x="${x}" y="${y}" width="${w}" height="${fs * 1.7}" rx="8" fill="#f4f3ee" fill-opacity="0.92"/><text ${lead(x, x + w, 20)} y="${y + fs * 1.15}" font-family="${MONO}" font-size="${fs}" fill="#4a4e57">${esc(o.text)}</text></g>`;
    }
    if (o.type === 'wordmark') {
      const fs = o.size || (H > W ? 40 : 34), x = o.x ?? (H > W ? 80 : W * 0.05 + 12), y = o.y ?? (H > W ? 262 : H * 0.1);  // inset: glyph bearings stay inside the safe area
      const wmk = (BR && BR.wordmark) || {};
      return `<text x="${x}" y="${y}" font-family="${BODY}" font-weight="700" font-size="${fs}" fill="${o.color || BP.ink || INK}">${esc(o.text || wmk.text || '')}<tspan fill="${o.accent || BP[(BR || {}).wordmark_accent] || '#1a62c2'}">${esc(o.accent_text ?? wmk.accent_text ?? '')}</tspan></text>`;
    }
    if (window.KIT && KIT[o.type]) return KIT[o.type](o, t, { W, H, visemes: T.visemes || {}, pointOf: (tg, tt) => worldOf(tg, tt, CASTS) });  // explainer kit 2 (dbe/player/kit.js)
    return '';
  }
  // rows for a bubble: explicit \n wins, else greedy wrap
  function rows(text, max) { if (text.includes('\n')) return text.split('\n'); return wrapText(text, max); }
  // boxes other elements occupy (signs, text overlays), so bubbles can avoid them
  const overlayBox = o => o.type === 'sign' ? (() => { const fs = o.size || 56, w = em(o.text) * fs * 0.52 + 50; return [o.x - w / 2, o.y - fs * 1.6, o.x + w / 2, o.y + fs * 1.6]; })()
    : o.type === 'text' ? [o.x - o.text.length * (o.size || 58) * 0.27, o.y - (o.size || 58), o.x + o.text.length * (o.size || 58) * 0.27, o.y + 10] : null;
  let AVOID = [];
  const hits = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  function bubble(b, anchor, t, idx) {
    const step = 1 / 12, f = Math.floor(t / step), f0 = Math.floor(b.t0 / step), f1 = Math.floor(b.t1 / step);
    if (f < f0 || f > f1) return '';
    const i = f - f0, j = f1 - f, pop = i === 0 ? 0.55 : i === 1 ? 1.12 : j === 0 ? 0.5 : j === 1 ? 0.85 : 1;
    const style = b.style || 'say', base = ({ say: 72, shout: 118, whisper: 50, thought: 64 }[style] || 72) * Math.min(1, H / 1920 * 1.4);  // landscape: smaller type, still >= the 16:9 minimum
    const R = rows(b.text, { say: 13, shout: 9, whisper: 18, thought: 14 }[style] || 13), lh = base * 1.08;
    const bw = Math.max(...R.map(r => em(r))) * base * 0.5, bh = lh * R.length;
    let rx = (bw / 2 + 60) * pop, ry = (bh / 2 + 46) * pop; if (style === 'shout') { rx *= 1.2; ry *= 1.3; }
    // placement: above the speaker toward the frame centre, then the other side, then higher or lower, avoiding
    // signs, overlays and earlier bubbles; inside the platform-safe area where possible
    const SAFE = H > W ? [64, 200, 960] : [W * 0.05, H * 0.05, W * 0.95];  // platform-safe text area (9:16 rail and top bar; 16:9 title-safe)
    const side = anchor[0] < W / 2 ? 1 : -1, clampX = x => Math.min(Math.max(x, rx + SAFE[0] + 6), SAFE[2] - rx - 6), clampY = y => Math.max(y, ry + SAFE[1] + 10);
    const cands = [];
    const u = H / 1920 * (H > W ? 1 : 1.6);
    for (const dy of [0, -80, 60, -160].map(v => v * u)) for (const dx of [90, -90, 230, -230, 330, -330, 0].map(v => v * (H > W ? 1 : 2))) cands.push([clampX(anchor[0] + dx * side), clampY(anchor[1] - 70 - ry + dy)]);
    const overlap = (a, r) => Math.max(0, Math.min(a[2], r[2]) - Math.max(a[0], r[0])) * Math.max(0, Math.min(a[3], r[3]) - Math.max(a[1], r[1]));
    const cost = ([x, y], k) => AVOID.reduce((acc, r) => acc + overlap([x - rx, y - ry, x + rx, y + ry], r), 0) + k * 40;  // prefer earlier (closer) spots
    let [cx, cy] = cands.map((c, k) => [c, cost(c, k)]).sort((a, b) => a[1] - b[1])[0][0];
    AVOID.push([cx - rx, cy - ry, cx + rx, cy + ry]); BUBBLES.push([cx - rx, cy - ry, cx + rx, cy + ry]);
    const n = 64, pts = [], k = Math.floor(t * 12) % 8;
    for (let q = 0; q < n; q++) { const th = 2 * Math.PI * q / n;
      let r = 1 + 0.018 * (Math.sin(3 * th + 6.28 * hash(k, idx)) + Math.sin(5 * th + 6.28 * hash(k + 9, idx)) + 0.6 * Math.sin(9 * th + 6.28 * hash(k + 17, idx)));
      if (style === 'shout') r *= q % 4 < 2 ? 1 : 0.8;
      if (style === 'thought') r *= 1 + 0.09 * Math.abs(Math.sin(5 * th));   // a cloud: round bumps all the way round
      pts.push([cx + rx * r * Math.cos(th), cy + ry * r * Math.sin(th), th]); }
    if (style === 'thought') {   // a thought trails off to the thinker in three shrinking puffs (WP-17)
      KINDS.push('thought');
      const [tx, ty] = [anchor[0], anchor[1] - 18], dots = [0.3, 0.55, 0.78].map((u, q) => { const ex = cx + (tx - cx) * u, ey = cy + ry * (1 - u) * 0.9 + (ty - cy) * u * 0.9; return `<circle cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" r="${(26 - q * 7) * pop}" fill="#f6f5ef" stroke="${INK}" stroke-width="4"/>`; }).join('');
      const dc = 'M' + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L') + ' Z';
      var thinkSvg = dots + `<path d="${dc}" fill="#f6f5ef" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
    } else KINDS.push(style);
    // tail: replace a few outline points with a spike to the speaker
    const [tx, ty] = [anchor[0], anchor[1] - 18], ang = (Math.atan2((ty - cy) / ry, (tx - cx) / rx) + 2 * Math.PI) % (2 * Math.PI), i0 = Math.round(ang / (2 * Math.PI) * n) % n;
    const path = []; for (let q = 0; q < n; q++) { const d = (q - i0 + n) % n; if (d === n - 3) path.push(pts[q], [tx, ty, 0]); else if (d > n - 3 || d < 3) continue; else path.push(pts[q]); }
    const dstr = 'M' + path.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L') + ' Z';
    let svg = style === 'thought' ? thinkSvg : `<path d="${dstr}" fill="#f6f5ef" stroke="${INK}" stroke-width="${style === 'whisper' ? 4 : 5}" stroke-linejoin="round"${style === 'whisper' ? ' stroke-dasharray="12 12"' : ''}/>`;
    // typewriter: voiced lines reveal word by word as spoken; silent ones letter by letter
    // voiced: word by word as spoken; custom bubble text: letters spread over the spoken line; silent: typed out
    const total = graphemes(R.join('')).length;
    // typed letters pause on punctuation (WP-17): a comma holds four letters' time, a full stop, ! or ? eight
    const gsAll = graphemes(R.join('')), wt = gsAll.map((g, q) => 1 + (q > 0 && /[,;:]/.test(gsAll[q - 1]) ? 4 : 0) + (q > 0 && /[.!?…]/.test(gsAll[q - 1]) && !/[.!?…]/.test(g) ? 8 : 0));
    const typed = units => { let acc = 0, k = 0; for (; k < wt.length; k++) { acc += wt[k]; if (acc > units + 1e-9) break; } return k; };
    const W_ALL = wt.reduce((a, v) => a + v, 0);
    const shown = b.words ? b.words.filter(w => w.start <= t).length
      : b.speak ? typed(W_ALL * Math.min(1, Math.max(0, (t - b.speak[0]) / Math.max(0.2, b.speak[1] - b.speak[0]))))
      : typed(Math.max(0, t - b.t0 - 0.2) / (b.slow ? 0.42 : 0.05)) + (pop < 1 && i > 1 ? 99 : 0);
    let left = shown, tspans = '';
    R.forEach((row, ri) => { let txt = row;
      if (b.words) { const ws = tokens(row), sep = nospace(row) ? '' : ' '; txt = ws.slice(0, Math.max(0, left)).join(sep); left -= ws.length; }
      else { const gs = graphemes(row); txt = gs.slice(0, Math.max(0, left)).join(''); left -= gs.length; }   // whole letters (a vowel sign never hangs alone)
      const y = cy - bh / 2 + lh * (ri + 0.78) * pop;
      if (style === 'shout' && !COMPLEX_RE.test(txt)) [...txt].forEach((ch, ci) => { const jx = (hash(k * 31 + ci, idx) - 0.5) * 8, jy = (hash(k * 17 + ci, idx + 3) - 0.5) * 10;
        tspans += `<text x="${(cx - txt.length * base * 0.27 + ci * base * 0.54 + jx).toFixed(1)}" y="${(y + jy).toFixed(1)}" font-size="${base * pop}">${esc(ch)}</text>`; });
      else tspans += `<text x="${cx}" y="${y.toFixed(1)}" font-size="${base * pop}" text-anchor="middle"${style === 'whisper' ? ' fill="#59636d"' : ''}>${esc(txt)}</text>`; });
    return svg + `<g font-family="${HAND}" fill="${INK}">${tspans}</g>`;
  }
  let BUBBLES = [], VIEW = [0, 0, 1], KINDS = [];   // for visual lint: bubble boxes and the camera of the last frame drawn; the kinds drawn (WP-17)
  // a narration box (WP-17): a narrator nobody on screen speaks for, in a caption box at the top of the safe area,
  // typed out with the same punctuation pauses, word by word as voiced (or spread over the line in a sound-off cut)
  function narrationBox(ln, t, idx) {
    const t0 = ln.start - 0.12, t1 = ln.end + 0.6; if (t < t0 || t > t1) return '';
    const base = 58 * Math.min(1, H / 1920 * 1.4), R = rows(ln.text, 24), lh = base * 1.15;
    const SAFE = H > W ? [64, 200, 960] : [W * 0.05, H * 0.05, W * 0.95], bw = Math.min(SAFE[2] - SAFE[0], Math.max(...R.map(r => em(r))) * base * 0.5 + 70), bh = lh * R.length + 44;
    const x0 = (SAFE[0] + SAFE[2]) / 2 - bw / 2, y0 = SAFE[1] + 16;
    AVOID.push([x0, y0, x0 + bw, y0 + bh]); BUBBLES.push([x0, y0, x0 + bw, y0 + bh]); KINDS.push('narrate');
    const gsAll = graphemes(R.join('')), wt = gsAll.map((g, q) => 1 + (q > 0 && /[,;:]/.test(gsAll[q - 1]) ? 4 : 0) + (q > 0 && /[.!?…]/.test(gsAll[q - 1]) && !/[.!?…]/.test(g) ? 8 : 0));
    const W_ALL = wt.reduce((a, v) => a + v, 0), u = W_ALL * Math.min(1, Math.max(0, (t - ln.start) / Math.max(0.2, ln.end - ln.start)));
    let acc = 0, left = 0; for (; left < wt.length; left++) { acc += wt[left]; if (acc > u + 1e-9) break; }
    let out = `<rect x="${x0.toFixed(1)}" y="${y0.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="10" fill="#fff3c4" stroke="${INK}" stroke-width="4"/>`;
    R.forEach((row, ri) => { const gs = graphemes(row), txt = gs.slice(0, Math.max(0, left)).join(''); left -= gs.length;
      out += `<text x="${(x0 + 30).toFixed(1)}" y="${(y0 + 22 + lh * (ri + 0.8)).toFixed(1)}" font-size="${base}">${esc(txt)}</text>`; });
    return `<g font-family="${HAND}" fill="${INK}">${out}</g>`;
  }
  // bubbles are laid out in screen space, after the camera, so a zoomed or moving shot never pushes them out of frame
  function bubblesFor(sh, t, headsWorld, view) {
    const [vx, vy, vz] = view || [W / 2, H / 2, 1], toS = ([x, y]) => [W / 2 + (x - vx) * vz, H / 2 + (y - vy) * vz];
    const heads = {}; for (const [k, a] of Object.entries(headsWorld)) heads[k] = toS(a);
    const out = []; let idx = 0; BUBBLES = []; KINDS = []; window.BUBBLE_KINDS = KINDS;
    AVOID = (sh.overlays || []).filter(o => (o.start == null || t >= o.start) && (o.end == null || t <= o.end)).map(overlayBox).filter(Boolean)
      .map(r => [...toS([r[0], r[1]]), ...toS([r[2], r[3]])]);
    const hw = 150 * H / 1920 * (H > W ? 1 : 1.5) * vz;
    for (const a of Object.values(heads)) AVOID.push([a[0] - hw, a[1] - 10, a[0] + hw, a[1] + H * 0.22 * vz]);  // keep bubbles off the characters' heads and bodies
    if (sh.bubbles !== false) for (const ln of T.lines || []) { // voiced lines become bubbles for speakers in the shot
      const who = heads[ln.speaker]; if (!who || !sh.bubbles) continue;
      const sl = (SCRIPT.lines || []).find(l => l.id === ln.id) || {};
      if (sl.style === 'narration') continue;   // a narration box, below
      out.push(bubble({ t0: ln.start - 0.12, t1: ln.end + 0.5, text: sl.bubble || ln.text, style: sl.style, words: sl.bubble ? null : ln.words, speak: [ln.start, ln.end] }, who, t, idx++));
    }
    for (const b of (sh.extra_bubbles || [])) if (heads[b.who]) out.push(bubble({ ...b, t0: b.start, t1: b.end }, heads[b.who], t, 50 + idx++));  // silent bubbles
    // narrators nobody on screen speaks for (in a cut with narration boxes), and any line styled "narration"
    for (const ln of T.lines || []) { const sl = (SCRIPT.lines || []).find(l => l.id === ln.id) || {};
      if ((S.narration_boxes && !heads[ln.speaker]) || sl.style === 'narration') out.push(narrationBox({ ...ln, text: sl.bubble || ln.text }, t, 80 + idx++)); }
    return out.join('');
  }

  // ---------- constraints and props (plan 1.2) ----------
  // a target is [x, y] in the frame, or {cast: i, part: "hand_R", at: [x, y]} (a point on another character)
  let CASTS = [], PCTX = { at: () => null, poseAt: () => null, fps: 30 };
  function worldOf(tg, t, casts) {
    if (!tg) return null;
    if (Array.isArray(tg)) return tg;
    const c = casts[tg.cast]; if (!c) return null;
    return Puppet.pointOf(c.p, tg.part, tg.at || null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip });
  }
  function toLocal(p, w, x, y, s, flip) {  // frame point -> the puppet's artboard space (inverse of its root transform)
    if (!w) return null;
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    return [(w[0] - x) / (s * flip) + hip[0], (w[1] - y) / s + (p.ground ?? p.artboard[1])];
  }
  // props (attach keys, ballistic flights, drops, baked physics tracks; squash, stretch and smears) live in
  // dbe/player/props.js, shared with fx.js and the Node solvers. Here: where an attach target is at any time.
  function propCtx(sh, casts, tq, set) {
    const memo = {};
    const poseAt = (ci, tt) => { const cc = casts[ci]; if (!cc) return null;
      if (Math.abs(tt - tq) < 1e-9) return cc;
      const key = ci + ':' + tt.toFixed(4); let st2 = memo[key];
      if (!st2) { const [x2, y2, s2, f2] = placeAt(cc.c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tt); const tl2 = { ...cc.tl }; delete tl2.lookat;
        const tl3 = Acting.resolveTargets(tl2, tt, w => toLocal(cc.p, w, x2, y2, s2, f2), () => null);
        st2 = memo[key] = { p: cc.p, x: x2, y: y2, s: s2, flip: f2, pose: Acting.evaluate(cc.p, tl3, tt, cc.L.clips, cc.L.presets) }; }
      return st2; };
    return { fps: FPS, poseAt,
      at: (tg, tt) => { if (!tg) return null; if (Array.isArray(tg)) return tg; const c = poseAt(tg.cast, tt); if (!c) return null;
        return Puppet.pointOf(c.p, tg.part, tg.at || null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip }); } };
  }

  // ---------- camera grammar (plan 2.6): "camera_auto": true | {"zoom": 1.5, "punch": 0.06, "handheld": 0.4, "ease": 0.6} ----------
  // Speaker framing during each line (medium shot), a two-shot otherwise, eased between; punch-ins on emphasised words
  // (long or stressed); seeded handheld drift; clamped so the frame never leaves the set; heads kept above captions.
  function autoCam(sh, t, casts) {
    const o = sh.camera_auto === true ? {} : sh.camera_auto, zMax = o.zoom ?? 1.45, ease = o.ease ?? 0.6;
    const byName = {}; casts.forEach(cc => { if (cc.c.speaker) byName[cc.c.speaker] = cc; });
    const box = list => { let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      for (const cc of list) { const h = cc.p.artboard[1] * cc.s * 0.95, w = cc.p.artboard[0] * cc.s * 0.6; x0 = Math.min(x0, cc.x - w / 2); x1 = Math.max(x1, cc.x + w / 2); y0 = Math.min(y0, cc.y - h); y1 = Math.max(y1, cc.y); }
      return [x0, y0, x1, y1]; };
    const frameFor = (list, single) => { if (!list.length) return [W / 2, H / 2, 1];
      const [x0, y0, x1, y1] = box(list), frac = single ? (o.medium ?? 0.62) : 1;   // singles: a medium shot, head to waist
      const bw = (x1 - x0) * 1.25, bh = (y1 - y0) * frac * 1.15;
      const z = Math.min(single ? (sh.bubbles ? (o.zoom_bubble ?? 1.5) : (o.zoom_single ?? 1.9)) : zMax, Math.max(1, Math.min(W / bw, H * 0.82 / bh)));
      // with speech bubbles a single keeps the head top at ~31% of the frame, leaving the bubble room above it
      if (single && sh.bubbles) return [(x0 + x1) / 2, y0 + (H / 2 - H * (H > W ? 0.31 : 0.36)) / z, z];
      return [(x0 + x1) / 2, y0 + bh * 0.46 + (H / z) * 0.08, z]; };   // heads high, room below for captions
    const wide = frameFor(casts);
    const lines = (T.lines || []).filter(l => byName[l.speaker] && l.end > sh.start - 0.5 && l.start < sh.end + 0.5);
    // target per instant: the speaker while a line plays (and 0.3 s before), else the two-shot
    // camera beats (WP-10): during a gag's stare the camera holds on who reacts and pushes in slowly ({t0, t1, who, zoom})
    const beats = (o.beats || []).filter(b => byName[b.who]);
    const target = tt => { const b = beats.find(b => tt >= b.t0 && tt <= b.t1);
      if (b) { const f = frameFor([byName[b.who]], true), u = Math.min(1, Math.max(0, (tt - b.t0) / Math.max(0.01, b.t1 - b.t0))); return [f[0], f[1], f[2] * (1 + ((b.zoom ?? 1.3) - 1) * u * u * (3 - 2 * u))]; }
      const l = lines.find(l => tt >= l.start - 0.3 && tt <= l.end + 0.2); return l && casts.length > 1 ? frameFor([byName[l.speaker]], true) : wide; };
    // ease: blend from the previous target over `ease` seconds after each change (pure: derived from the schedule)
    let cur = target(t); const changes = [];
    for (const l of lines) changes.push(l.start - 0.3, l.end + 0.2);
    for (const b of beats) changes.push(b.t0, b.t1);
    changes.sort((a, b) => a - b);
    const last = changes.filter(c => c <= t).pop();
    if (last != null && t - last < ease) { const prev = target(last - 0.01), u = (t - last) / ease, e = u * u * (3 - 2 * u); cur = cur.map((v, i) => prev[i] + (v - prev[i]) * e); }
    let [cx, cy, z] = cur;
    // punch-in on emphasised words (long words in the current line), 0.06 zoom over 0.35 s
    const punch = o.punch ?? 0.05;
    if (punch) for (const l of lines) for (const w of l.words || []) { const len = w.end - w.start, letters = w.text.replace(/\W/g, '').length || 1;
      if (len / letters > 0.085 || /!$/.test(w.text)) { const d = t - w.start; if (d > -0.05 && d < 0.6) z *= 1 + punch * Math.sin(Math.PI * Math.min(1, Math.max(0, (d + 0.05) / 0.65))); } }
    // handheld drift: sum of incommensurate sines (seeded by the shot id)
    const hh = o.handheld ?? 0; if (hh) { const sd = (sh.id || 's').length * 1.7; cx += hh * 9 * (Math.sin(t * 0.71 + sd) + 0.5 * Math.sin(t * 1.93 + sd * 2)); cy += hh * 7 * (Math.sin(t * 0.83 + sd * 3) + 0.5 * Math.sin(t * 2.31 + sd)); }
    const hw = W / (2 * z), hhh = H / (2 * z);
    cx = Math.min(W - hw, Math.max(hw, cx)); cy = Math.min(H - hhh, Math.max(hhh, cy));
    return [cx, cy, z];
  }

  function frameAt(t, bgOnly) {
    const sh = only || shotAt(t), st = sh.style || {};   // a shot render keeps its shot through its handles (WP-15)
    const tq = st.step ? Math.floor(t * st.step + 1e-6) / st.step : t;   // animate on 12s/24s like hand-drawn work
    const set = (window.SETS || {})[sh.set || 'plain'] || window.SETS.plain;
    BOILK = st.boil && st.boil.while_moving ? boilPhase(sh, st, t) : null;
    let world = castOnly || PLATE.on ? '' : staticLayer(sh, set.draw(tq, sh.set_opts || {}, W, H)), ink = '';   // plate mode: the set comes from the plate   // castonly=1: the characters alone (WP-14 renderer parity)
    if (sh.underlays && !bgOnly && !castOnly) world += sh.underlays.filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join('');
    const heads = {}, casts = []; CASTS = casts;
    const planeInk = {}, onPlane = c => sh.comp && c.plane && c.plane !== 'stage' && !bgOnly;   // WP-36: cast members on depth planes
    for (const c of sh.cast || []) {
      const p = puppetFor(c.puppet, sh.palette_variant); if (!p) continue;
      if (bgOnly) { // the set plate for other renderers keeps each character's ground shadow
        const [x, y, s] = placeAt(c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tq);
        if (st.shadow !== false) world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`; continue;
      }
      const tl = { ...(c.timeline || {}) }, L = libFor(p);
      if (tl.visemes_from) { tl.visemes = (T.visemes || {})[tl.visemes_from] || []; delete tl.visemes_from; }
      if (c.place && c.place.path && tl.pins && tl.travel == null) tl.travel = { path: c.place.path };   // planted feet on a path walk
      const [x, y, s, flip] = placeAt(c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tq);
      // pass 1: targets on other characters wait until everyone has a pose (WP-11: handshakes, eye contact)
      const loc = w => toLocal(p, w, x, y, s, flip);
      const tl1 = Acting.resolveTargets(tl, tq, loc, () => null);
      const pose = Acting.evaluate(p, tl1, tq, L.clips, L.presets);
      casts.push({ p, x, y, s, flip, pose, c, tl, L, loc, cross: Acting.crossRefs(tl) });
    }
    if (!bgOnly) {   // pass 2: characters that reach for or look at someone, against everyone's first-pass pose
      const first = casts.map(cc => ({ ...cc }));
      for (const cc of casts) if (cc.cross) cc.pose = Acting.evaluate(cc.p, Acting.resolveTargets(cc.tl, tq, cc.loc, (tg, tt) => worldOf(tg, tt, first)), tq, cc.L.clips, cc.L.presets);
    }
    for (const cc of bgOnly ? [] : casts) {
      const { p, x, y, s, flip, pose, c } = cc;
      const shadow = st.shadow !== false && !castOnly ? `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>` : '';
      const drawn = Puppet.render(p, x, y, { ...pose, s, flip, ...(st.toon ? { toon: st.toon === true ? {} : st.toon } : {}) });
      if (onPlane(c)) planeInk[c.plane] = (planeInk[c.plane] || '') + shadow + drawn;
      else { world += shadow; ink += drawn; }
      if (c.speaker) heads[c.speaker] = Puppet.pointOf(p, 'head', (p.anchors || {}).bubble || null, x, y, { ...pose, s, flip });
    }
    const pctx = PCTX = propCtx(sh, casts, tq, set);
    if (!bgOnly && !castOnly) ink += (sh.props || []).map(pr => PROPS.svg(pr, tq, pctx)).join('');
    if (!bgOnly && !castOnly && sh.fx && window.FX) {  // motion effects from the motion itself (dbe/player/fx.js)
      const pointAt = (ci, part, tt) => { if (tt < (sh.start || 0)) return null; const c = pctx.poseAt(ci, tt); if (!c) return null;
        return Puppet.pointOf(c.p, part, null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip }); };
      ink += FX.render(sh, tq, { casts, pointAt, propPos: (pr, tt, info) => PROPS.pos(pr, tt, pctx, info), pctx });
    }
    if (!bgOnly && !castOnly) { ink += (sh.overlays || []).filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join(''); }
    world += st.boil && !castOnly ? `<g filter="url(#${boilId(st, t)})">${ink}</g>` : ink;   // parity frames compare geometry, without the boil
    let svg = boilDefs(st, t) + world;
    if (st.float && !sh.camera) { const a = tq * 2 * Math.PI / 20, z = 1.012 + 0.008 * Math.sin(a * 0.7);   // slow orbit and breath (no dead frames)
      svg = boilDefs(st, t) + `<g transform="translate(${W / 2 + 6 * Math.cos(a)} ${H / 2 + 6 * Math.sin(a)}) scale(${z.toFixed(4)}) translate(${-W / 2} ${-H / 2})">${world}</g>`; }
    VIEW = [W / 2, H / 2, 1];
    if (st.float && !sh.camera) { const a = tq * 2 * Math.PI / 20; VIEW = [W / 2 - 6 * Math.cos(a), H / 2 - 6 * Math.sin(a), 1.012 + 0.008 * Math.sin(a * 0.7)]; }
    if (sh.camera_auto && !sh.camera && !bgOnly) { const [cx, cy, z] = autoCam(sh, tq, casts); VIEW = [cx, cy, z];   // camera grammar (plan 2.6)
      svg = boilDefs(st, t) + `<g transform="translate(${W / 2} ${H / 2}) scale(${z.toFixed(4)}) translate(${(-cx).toFixed(2)} ${(-cy).toFixed(2)})">${world}</g>`; }
    if (sh.camera) { const [cx, cy, z] = Acting.sampleKeys(sh.camera, tq) || [W / 2, H / 2, 1]; VIEW = [cx, cy, z]; svg = boilDefs(st, t) + `<g transform="translate(${W / 2} ${H / 2}) scale(${z}) translate(${-cx} ${-cy})">${world}</g>`; }
    if (sh.comp && window.COMP && !bgOnly) {   // WP-36: depth planes with parallax and depth of field, per-plane nodes
      const view = sh.camera ? (Acting.sampleKeys(sh.camera, tq) || [W / 2, H / 2, 1]) : sh.camera_auto ? autoCam(sh, tq, casts) : [W / 2, H / 2, 1];
      VIEW = view;
      svg = boilDefs(st, t) + COMP.compose(sh, { W, H, t: tq, view, stage: world, planeInk, tag: Math.round(t * FPS),
        drawSet: (name, opts, tt) => ((window.SETS || {})[name] || window.SETS.plain).draw(tt, opts, W, H), overlay }); }
    { const [vx, vy, vz] = VIEW || [W / 2, H / 2, 1]; window.HEADS = Object.fromEntries(Object.entries(heads).map(([k, a]) => [k, [W / 2 + (a[0] - vx) * vz, H / 2 + (a[1] - vy) * vz]])); }   // where each speaker's head is on screen (comics, WP-30)
    if (!bgOnly && !castOnly && q.get('bubbles') !== '0') { const bub = bubblesFor(sh, tq, heads, VIEW); if (bub) svg += st.boil ? `<g filter="url(#${boilId(st, t)})">${bub}</g>` : bub; }
    // shot renders leave captions to the film-level pass (dbe/captions.py); the live web player draws them itself
    if (!bgOnly && !castOnly && !only && q.get('captions') !== '0' && sh.captions !== false && S.captions !== false) svg += captions(t);
    return svg;
  }
  const only = q.get('shot') ? S.shots.find(s => s.id === q.get('shot')) : null;
  const bgOnly = q.get('bg') === '1';
  const castOnly = q.get('castonly') === '1';
  if (castOnly) { document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent'; }
  // ?pre=&post= (seconds): handles before and after a shot, rendered for transitions made at assembly (WP-15)
  const t0 = only ? only.start - (+q.get('pre') || 0) : 0, t1 = only ? only.end + (+q.get('post') || 0) : S.shots[S.shots.length - 1].end;
  window.FILMTIME = { start: t0, end: t1, fps: FPS };
  // a frame with images (WP-42 plates) is ready only when they have loaded and decoded, so a render never captures a
  // half-loaded frame: the returned promise resolves then (renderers await it)
  window.frameAtTime = t => {
    stage.innerHTML = frameAt(t, bgOnly); bidi();
    if (PENDING.length) {   // a static layer was rasterized for the first time: draw the frame again with its image
      const ps = PENDING.splice(0);
      return Promise.all(ps).then(() => { stage.innerHTML = frameAt(t, bgOnly); bidi(); PENDING.length = 0; return settle(); });
    }
    return settle();
  };
  // right-to-left text keeps its place and reads correctly (WP-25): direction rtl, with its anchor flipped to the same
  // side (under rtl, "start" is the right end); only films that hold such text pay for the pass
  const ALLTXT = JSON.stringify(S) + JSON.stringify(window.SCRIPT || {}) + JSON.stringify(window.DATA || {}) + JSON.stringify(T.lines || []);
  const HAS_RTL = RTL_RE.test(ALLTXT);
  function bidi() {
    if (!HAS_RTL) return;
    for (const el of stage.querySelectorAll('text')) {
      if (!RTL_RE.test(el.textContent)) continue;
      const a = getComputedStyle(el).textAnchor || 'start'; el.setAttribute('direction', 'rtl');
      el.setAttribute('text-anchor', a === 'start' ? 'end' : a === 'end' ? 'start' : a);
    }
  }
  function settle() {
    // every image, data: URIs too (raster puppet parts): one not yet decoded would be captured missing (WP-15 found
    // reused and re-captured frames differing by this); decoding an image the page already holds is quick
    const imgs = [...new Set([...stage.querySelectorAll('image')].map(im => im.getAttribute('href')).filter(Boolean))];
    if (!imgs.length) return;
    return Promise.all(imgs.map(src => { const im = new Image(); im.src = src; return im.decode().catch(() => null); }))
      .then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  }
  // the camera this player frames each moment with (auto camera, float drift): other renderers bake it as camera keys (WP-14)
  window.viewsAt = ts => ts.map(t => { frameAt(t, false); return VIEW.slice(); });
  // time warp (plan 2.13, the sound-off cut): shots.json "timewarp": [[cut time, film time], ...] knots, increasing;
  // the cut is rendered on its own clock and each frame shows the film at the warped time (lines held for reading)
  const WK = S.timewarp && S.timewarp.length > 1 ? S.timewarp : null;
  const lerpK = (k, i, j, v) => { if (v <= k[0][i]) return k[0][j] + (v - k[0][i]); for (let n = 1; n < k.length; n++) if (v <= k[n][i]) { const a = k[n - 1], b = k[n]; return a[j] + (b[j] - a[j]) * (v - a[i]) / ((b[i] - a[i]) || 1); } return k[k.length - 1][j] + (v - k[k.length - 1][i]); };
  const toFilm = tc => WK ? lerpK(WK, 0, 1, tc) : tc, toCut = tf => WK ? lerpK(WK, 1, 0, tf) : tf;
  window.TIMEWARP = { toFilm, toCut };
  // WP-15 sub-frame motion blur: ?sub=N&shutter=s makes the page N times as many frames, frame f's sample k at
  // f + ((k + 0.5) / N - 0.5) * s (centred on the frame, spread over s of its interval: 0.5 is a 180-degree shutter);
  // shot.render averages each group of N back into one frame
  const SUB = Math.max(1, Math.round(+q.get('sub') || 1)), SHUT = q.get('shutter') != null ? +q.get('shutter') : 0.5;
  window.renderFrame = SUB === 1 ? f => window.frameAtTime(toFilm(toCut(t0) + f / FPS))
    : g => { const f = Math.floor(g / SUB), k = g - f * SUB; return window.frameAtTime(toFilm(toCut(t0) + (f + ((k + 0.5) / SUB - 0.5) * SHUT) / FPS)); };
  window.FRAMES = Math.round((toCut(t1) - toCut(t0)) * FPS) * SUB;
  // ---------- foley events (plan 2.7): footsteps on contacts, thuds on landings, swishes on fast moves, pops on catches ----------
  // Returns [{t, type, gain, pan}] for the whole film, computed from the same poses the frames show.
  function foleyEvents() {
    const ev = [], dt = 1 / FPS, pan = x => Math.max(-0.8, Math.min(0.8, (x / W) * 2 - 1));
    const prev = {};
    for (const sh of S.shots) {
      for (let t = sh.start; t < sh.end; t += dt) {
        frameAt(t, false);   // sets CASTS for this instant
        CASTS.forEach((cc, ci) => {
          const key = sh.id + ':' + ci, pv = prev[key] || {};
          const hip = Puppet.pointOf(cc.p, cc.p.parts.hip ? 'hip' : Object.keys(cc.p.parts)[0], null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip });
          const hands = ['hand_R', 'hand_L'].filter(h => cc.p.parts[h]).map(h => Puppet.pointOf(cc.p, h, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip }));
          // footsteps: a foot's contact turning on
          for (const f of ['foot_L', 'foot_R']) { const on = !!(cc.pose.contacts && cc.pose.contacts[f]);
            if (on && pv[f] === false) ev.push({ t: +t.toFixed(3), type: 'step', gain: 0.8, pan: pan(cc.x) }); pv[f] = on; }
          // landing: hips falling then stopping (the dust test of fx.js)
          if (pv.hipY != null && pv.vy != null) { const vy = hip[1] - pv.hipY; if (pv.vy > 3 * cc.s && vy < pv.vy * 0.35 && (pv.fall || 0) > 12 * cc.s) ev.push({ t: +t.toFixed(3), type: 'thud', gain: 1, pan: pan(cc.x) });
            pv.fall = vy > 0.5 ? (pv.fall || 0) + vy : 0; pv.vy = vy; } else if (pv.hipY != null) pv.vy = hip[1] - pv.hipY;
          // hop: hips leaving the ground fast (a boing per hop by default; "foley": {"hop": "swish" | false})
          const hopSnd = (S.foley && S.foley.hop !== undefined) ? S.foley.hop : 'boing';
          if (hopSnd && pv.hipY != null) { const vy = hip[1] - pv.hipY, up = vy < -5 * cc.s;
            if (up && !pv.up && (pv.still || 0) >= 3) ev.push({ t: +t.toFixed(3), type: hopSnd, gain: hopSnd === 'boing' ? 0.55 : 0.8, pan: pan(cc.x) });
            pv.up = up; pv.still = vy > -1.5 * cc.s ? (pv.still || 0) + 1 : (up ? pv.still : 0); }   // still = frames since the hips last rose
          pv.hipY = hip[1];
          // swish: a hand crossing 1400 px/s (once per fast move)
          hands.forEach((h, i) => { const k = 'h' + i; if (pv[k]) { const v = Math.hypot(h[0] - pv[k][0], h[1] - pv[k][1]) / dt, fast = v > 1400 * Math.max(0.6, cc.s);
            if (fast && !pv[k + 'f']) ev.push({ t: +t.toFixed(3), type: 'swish', gain: Math.min(1.2, v / 2000), pan: pan(h[0]) }); pv[k + 'f'] = fast; } pv[k] = h; });
          prev[key] = pv;
        });
      }
      // pen-scratch ambience while kit drawings draw themselves (shots' underlays and overlays of type "draw")
      if (!S.foley || S.foley.scratch !== false) for (const o of [...(sh.underlays || []), ...(sh.overlays || [])]) if (o.type === 'draw' && o.sound !== false) {
        const n = (o.paths || [o.path]).length, dur = typeof o.until === 'number' ? Math.max(0.05, o.until - (o.start ?? 0)) : (typeof o.duration === 'number' ? o.duration : 1.2);
        const stag = o.stagger ?? dur / Math.max(1, n), len = Math.min(sh.end - (o.start ?? 0), dur + stag * (n - 1));
        if (len > 0.15) ev.push({ t: +(o.start ?? 0).toFixed(3), type: 'scratch', dur: +len.toFixed(3), gain: 1, pan: pan(o.x ?? W / 2) }); }
      // catches and drops: a prop arriving at the end of its travel, bounces of drops
      for (const pr of sh.props || []) { const keys = pr.attach || [];
        for (let k = 1; k < keys.length; k++) { const spec = keys[k][1] || {};
          if (spec.drop) { const info = {}; PROPS.pos(pr, sh.end, PCTX, info); (info.bounces || []).forEach(([bt, bx], i) => ev.push({ t: +bt.toFixed(3), type: 'thud', gain: Math.max(0.3, 0.9 - i * 0.25), pan: pan(bx) })); continue; }
          const arrive = spec.arrive != null ? spec.arrive : keys[k][0] + (pr.travel ?? 0.35); const pos = PROPS.pos(pr, arrive, PCTX);
          if (arrive < sh.end) ev.push({ t: +arrive.toFixed(3), type: 'pop_small', gain: 0.9, pan: pan(pos ? pos[0] : W / 2) }); } }
    }
    return ev.sort((a, b) => a.t - b.t);
  }
  window.FOLEY = foleyEvents;

  // ---------- visual lint (plan 2.8): problems in the picture, with frame ranges ----------
  // off-screen limbs and heads, bubbles over faces, faces under the caption band, arms locked straight by IK,
  // silhouettes tangent to the frame edge or to each other, props passing through someone who is not holding them.
  function visualLint(step = 3) {
    const hits = [], dt = 1 / FPS;
    const scr = ([x, y]) => [W / 2 + (x - VIEW[0]) * VIEW[2], H / 2 + (y - VIEW[1]) * VIEW[2]];
    const capTop = H - (H > W ? 420 : 260);   // where burned-in captions sit
    for (const sh of S.shots) {
      for (let f = Math.ceil(sh.start * FPS); f < sh.end * FPS; f += step) {
        const t = f / FPS; frameAt(t, false);
        const faces = [];
        CASTS.forEach((cc, ci) => {
          const P = (part, at) => cc.p.parts[part] ? scr(Puppet.pointOf(cc.p, part, at || null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip })) : null;
          const k = cc.s * VIEW[2], name = cc.c.speaker || cc.p.name || 'cast ' + ci;
          // head box (around the head pivot, up to the bubble anchor)
          const hb = cc.p.anchors && cc.p.anchors.bubble ? P('head', cc.p.anchors.bubble) : null, hp = P('head');
          if (hp) { const top = hb ? hb[1] : hp[1] - 180 * k; faces.push({ ci, name, box: [hp[0] - 85 * k, top, hp[0] + 85 * k, hp[1] + 20 * k] }); }
          // off-screen, only for someone who is in the shot (their body is on screen): a head cut by the frame is an error;
          // a hand leaving the frame is a warning; feet out of frame only matter in a wide shot (z near 1), where nothing should be cropped
          const out = q => q && (q[0] < -10 || q[0] > W + 10 || q[1] < -10 || q[1] > H + 10), body = P('body') || P('hip');
          if (body && !out(body)) {
            const hd = P('head'); if (hd && (out(hd) || hd[1] - 150 * k < -10)) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'error', who: name, msg: 'the head is cut by the frame' });
            for (const part of ['hand_R', 'hand_L']) if (out(P(part))) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'warn', who: name, msg: `${part} leaves the frame` });
            if (VIEW[2] < 1.05) for (const part of ['foot_R', 'foot_L']) if (out(P(part))) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'warn', who: name, msg: `${part} is cropped in a wide shot` });
          }
          // IK over-extension: the arm is straight while an IK target is set for it
          for (const side of ['R', 'L']) { const ik = (cc.tl.ik || {})['arm_' + side]; if (!ik) continue;
            const a = P('upperarm_' + side), b = P('forearm_' + side), c = P('hand_' + side); if (!a || !b || !c) continue;
            const full = Math.hypot(b[0] - a[0], b[1] - a[1]) + Math.hypot(c[0] - b[0], c[1] - b[1]), reach = Math.hypot(c[0] - a[0], c[1] - a[1]);
            if (reach > full * 0.997) hits.push({ f, shot: sh.id, check: 'ik overextended', level: 'warn', who: name, msg: `arm_${side} is locked straight: its target is out of reach` }); }
        });
        // bubbles over faces (any face but the speaker's own anchor region below the bubble)
        for (const bb of BUBBLES) for (const fc of faces) { const ix = Math.min(bb[2], fc.box[2]) - Math.max(bb[0], fc.box[0]), iy = Math.min(bb[3], fc.box[3]) - Math.max(bb[1], fc.box[1]);
          if (ix > 12 && iy > 12 && ix * iy > 0.12 * (fc.box[2] - fc.box[0]) * (fc.box[3] - fc.box[1])) hits.push({ f, shot: sh.id, check: 'bubble over face', level: 'error', who: fc.name, msg: 'a speech bubble covers the face' }); }
        // faces under the caption band (captions on)
        if (S.captions !== false) for (const fc of faces) if (Math.min(fc.box[3], H) - Math.max(fc.box[1], capTop) > 0.3 * (fc.box[3] - fc.box[1])) hits.push({ f, shot: sh.id, check: 'face under captions', level: 'warn', who: fc.name, msg: 'the face sits where captions are burned in' });
        // tangents: a silhouette edge within 6 px of the frame edge, or two characters' boxes almost touching
        const boxes = CASTS.map((cc, ci) => { const pts = ['head', 'hand_R', 'hand_L', 'foot_R', 'foot_L', 'arm_R', 'arm_L', 'body'].filter(p => cc.p.parts[p]).map(p => scr(Puppet.pointOf(cc.p, p, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip })));
          if (!pts.length) return null; const pad = 30 * cc.s * VIEW[2]; return [Math.min(...pts.map(q => q[0])) - pad, Math.min(...pts.map(q => q[1])) - pad, Math.max(...pts.map(q => q[0])) + pad, Math.max(...pts.map(q => q[1])) + pad, cc.c.speaker || cc.p.name || 'cast ' + ci]; });
        boxes.forEach(b => { if (b && ((b[0] > 0 && b[0] < 6) || (b[2] < W && b[2] > W - 6))) hits.push({ f, shot: sh.id, check: 'tangent', level: 'info', who: b[4], msg: 'the silhouette just touches the frame edge (move it in or crop it clearly)' }); });
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) { const a = boxes[i], b = boxes[j]; if (!a || !b) continue;
          const gap = Math.max(b[0] - a[2], a[0] - b[2]); if (gap > -4 && gap < 4 && Math.min(a[3], b[3]) > Math.max(a[1], b[1])) hits.push({ f, shot: sh.id, check: 'tangent', level: 'info', who: a[4] + ' / ' + b[4], msg: 'two characters just touch: overlap them clearly or separate them' }); }
        // props through bodies: a prop inside a head that is not its current parent
        for (const pr of sh.props || []) { const pos0 = PROPS.pos(pr, t, PCTX); if (!pos0) continue; const pos = scr(pos0), r = (pr.r || 34) * VIEW[2];
          const keys = pr.attach || []; let kk = 0; while (kk + 1 < keys.length && keys[kk + 1][0] <= t) kk++; const holder = (keys[kk] && keys[kk][1] || {}).cast;
          for (const fc of faces) if (fc.ci !== holder && pos[0] > fc.box[0] - r * 0.5 && pos[0] < fc.box[2] + r * 0.5 && pos[1] > fc.box[1] && pos[1] < fc.box[3]) hits.push({ f, shot: sh.id, check: 'prop through body', level: 'warn', who: fc.name, msg: `prop ${pr.id || ''} passes through the head` }); }
      }
    }
    // group consecutive frames of the same problem into ranges
    const runs = [], key = h => h.shot + '|' + h.check + '|' + h.who + '|' + h.msg;
    hits.sort((a, b) => key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : a.f - b.f);
    for (const h of hits) { const r = runs[runs.length - 1];
      if (r && key(r) === key(h) && h.f - r.to <= step) r.to = h.f; else runs.push({ ...h, from: h.f, to: h.f }); }
    // one-sample flickers (a camera move passing by) are noise unless they are errors
    return runs.filter(r => r.level === 'error' || r.to > r.from).map(({ f, ...r }) => ({ ...r, t0: +(r.from / FPS).toFixed(2), t1: +(r.to / FPS).toFixed(2) })).sort((a, b) => a.from - b.from);
  }
  window.LINT = visualLint;
  // motion probe (plan 3.4): a part's position on screen over a span, for the review critic's before/after checks
  window.PROBE = (ci, part, t0, t1, fps = FPS) => { const out = [];
    for (let f = Math.ceil(t0 * fps); f <= t1 * fps; f++) { const t = f / fps; frameAt(t, false); const cc = CASTS[ci];
      if (part === '@look') {   // WP-19: the character's gaze in screen terms ([x, y], x > 0 looks right on screen), and where it stands
        const lk = (cc && cc.pose && cc.pose.look) || [0, 0], fl = (cc && cc.flip) || 1;
        out.push([+t.toFixed(3), +(lk[0] * fl).toFixed(3), +(lk[1] || 0).toFixed(3), cc ? +(W / 2 + (cc.x - VIEW[0]) * VIEW[2]).toFixed(1) : null]); continue; }
      if (!cc || !cc.p.parts[part]) { out.push([+t.toFixed(3), null, null]); continue; }
      const q = Puppet.pointOf(cc.p, part, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip });
      out.push([+t.toFixed(3), +(W / 2 + (q[0] - VIEW[0]) * VIEW[2]).toFixed(1), +(H / 2 + (q[1] - VIEW[1]) * VIEW[2]).toFixed(1)]); }
    return out; };
  window.FILM = { width: W, height: H, fps: FPS * SUB, frames: window.FRAMES, ready: false };
  (document.fonts ? Promise.all([document.fonts.load('700 40px Fredoka'), document.fonts.load("40px 'Patrick Hand'"), document.fonts.load("30px 'Atkinson Mono'"), document.fonts.load("40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2"), document.fonts.load("700 40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2"),
    // the fonts of every other writing system the film's text uses (WP-25)
    ...SFONTS.filter(f => f.ranges && reOf([f]).test(ALLTXT)).flatMap(f => [document.fonts.load(`40px '${f.family}'`, f.sample), document.fonts.load(`700 40px '${f.family}'`, f.sample)])]) : Promise.resolve()).then(() => { window.FILM.ready = true; window.ready = true; });
})();
