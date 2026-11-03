// Model sheet (plan 1.4): one page showing a puppet in key poses and views, and every expression close up.
// Used by the Rig Canvas (Sheet button) and by `python -m dbe puppet.sheet` (tools/sheet.mjs). Exposes `Sheet`.
//   Sheet.build(puppet, clipLib) -> SVG string (1800 x 1100)
(function (root) {
  const W = 1800, H = 1100, esc = s => String(s).replace(/[<&]/g, '');
  function figure(p, pose, cx, baseY, s) { return Puppet.render(p, cx, baseY, { s, ...pose }); }
  function headCell(p, pose, x, y, w, h, label) {
    const hp = (p.parts.head && p.parts.head.pivot) || [p.artboard[0] / 2, 300];
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    // render the puppet at its artboard origin and window the head region
    const vb = [hp[0] - 120, hp[1] - 190, 240, 230];
    return `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="#fffdf7" stroke="#d8cfc0"/>` +
      `<svg x="${x + 4}" y="${y + 4}" width="${w - 8}" height="${h - 30}" viewBox="${vb.join(' ')}">${Puppet.render(p, hip[0], p.ground ?? p.artboard[1], { s: 1, ...pose })}</svg>` +
      `<text x="${x + w / 2}" y="${y + h - 9}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="15" fill="#5a4a3a">${esc(label)}</text></g>`;
  }
  function build(p, lib) {
    const L = lib || { clips: {}, presets: {} };
    let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="#f6f1e6"/>`;
    s += `<text x="40" y="58" font-family="Fredoka,sans-serif" font-size="40" font-weight="700" fill="#24160e">${esc(p.name || 'Character')}</text>` +
      `<text x="40" y="88" font-family="Fredoka,sans-serif" font-size="18" fill="#7a6a5a">model sheet · template ${esc(p.template)} · ${Object.keys(p.parts).length} parts</text>`;
    // row 1: poses and views
    const poses = [['rest', {}]];
    if (L.clips.wave_R) poses.push(['wave', Acting.evaluate(p, { clips: [{ clip: 'wave_R', start: 0 }] }, 0.6, L.clips, L.presets)]);
    else if (L.clips.wave_L) poses.push(['wave', Acting.evaluate(p, { clips: [{ clip: 'wave_L', start: 0 }] }, 0.6, L.clips, L.presets)]);
    if (p.controls && p.controls.turn) { poses.push(['turn left', Acting.evaluate(p, { controls: { turn: [[0, -1]] }, blink: false }, 0, L.clips, L.presets)]);
      poses.push(['turn right', Acting.evaluate(p, { controls: { turn: [[0, 1]] }, blink: false }, 0, L.clips, L.presets)]); }
    for (const v of Object.keys(p.views || {})) poses.push([v + ' view', { view: v }]);
    const n = Math.min(poses.length, 5), colW = (W - 80) / Math.max(4, n), sc = Math.min(0.62, 560 / p.artboard[1]);
    poses.slice(0, 5).forEach(([label, pose], i) => {
      const cx = 40 + colW * (i + 0.5), base = 120 + p.artboard[1] * sc;
      s += `<line x1="${cx - colW * 0.4}" y1="${base}" x2="${cx + colW * 0.4}" y2="${base}" stroke="#d8cfc0" stroke-width="2"/>` + figure(p, { blink: 0, ...pose }, cx, base, sc) +
        `<text x="${cx}" y="${base + 30}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="18" fill="#5a4a3a">${esc(label)}</text>`;
    });
    // rows 2-3: expressions
    const cells = [];
    const sw = p.swaps || {};
    for (const k of Object.keys((sw.mouth || {}).shapes || {})) cells.push(['mouth ' + k, { mouth: k }]);
    for (const k of Object.keys((sw.brows || {}).shapes || {})) if (k !== 'neutral') cells.push(['brows ' + k, { brows: k }]);
    for (const k of ['half', 'closed']) if (sw.eyes && sw.eyes.shapes[k]) cells.push(['eyes ' + k, { eyes: k }]);
    if (sw.pupils) cells.push(['look left', { look: [-1, 0] }], ['look up', { look: [0.3, -1] }]);
    const cw = 160, ch = 170, perRow = Math.floor((W - 80) / (cw + 12)), y0 = H - 2 * (ch + 14) - 20;
    cells.slice(0, perRow * 2).forEach(([label, pose], i) => { const r = Math.floor(i / perRow), c = i % perRow; s += headCell(p, { blink: 0, ...pose }, 40 + c * (cw + 12), y0 + r * (ch + 14), cw, ch, label); });
    return s + '</svg>';
  }
  // ---------- boards (WP-18) ----------
  // Sheet.board(puppet, kind, clipLib) -> SVG string. kind:
  //   mouth        the mouth chart: every mouth shape side by side in close-up, each over an onion skin of the closed
  //                mouth (tinted blue), so size, placement and line weight can be compared at a glance
  //   expressions  brows, eyes, gaze and the emotions the template knows, each over an onion of the neutral face
  //   turnaround   the drawn view and every other view (and the views mirrored, for the other side) at one scale on
  //                one ground line, with height lines from the front view (top of head, eyes, chin, hips, knees,
  //                ground) drawn across them all, so a view that is off model shows at once
  const ONION = '<filter id="sheet-onion" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="0 0 0 0 0.23  0 0 0 0 0.43  0 0 0 0 0.66  0 0 0 0.6 0"/></filter>';
  function onionCell(p, pose, base, x, y, w, h, label, ghostSwaps) {
    const hp = (p.parts.head && p.parts.head.pivot) || [p.artboard[0] / 2, 300], hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    const hb = headBox(p), vb = hb ? [hb[0] - 0.12 * (hb[2] - hb[0]), hb[1] - 0.12 * (hb[3] - hb[1]), 1.24 * (hb[2] - hb[0]), 1.24 * (hb[3] - hb[1])] : [hp[0] - 120, hp[1] - 190, 240, 230];
    const at = (pz, q = p) => Puppet.render(q, hip[0], p.ground ?? p.artboard[1], { s: 1, ...pz });
    // the ghost is only the compared drawings (the closed mouth, or the neutral face), not the whole head
    const ghost = { ...p, parts: Object.fromEntries(Object.entries(p.parts).map(([id, pt]) => [id, { ...pt, strokes: [] }])),
      swaps: Object.fromEntries(Object.entries(p.swaps || {}).filter(([id]) => ghostSwaps.has(id))) };
    return `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="#fffdf7" stroke="#d8cfc0"/>` +
      `<svg x="${x + 4}" y="${y + 4}" width="${w - 8}" height="${h - 30}" viewBox="${vb.map(v => v.toFixed(1)).join(' ')}">${at(pose)}${base ? `<g filter="url(#sheet-onion)">${at(base, ghost)}</g>` : ''}</svg>` +
      `<text x="${x + w / 2}" y="${y + h - 9}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="15" fill="#5a4a3a">${esc(label)}</text></g>`;
  }
  // boxes are measured on the rendered drawing (getBBox), so any path data and raster parts count exactly
  function flat(p, view) {   // the puppet with a view's overrides applied (as Puppet.render does)
    const v = (p.views || {})[view]; if (!v) return p;
    const parts = {}, swaps = {};
    for (const [id, pt] of Object.entries(p.parts)) parts[id] = { ...pt, ...((v.parts || {})[id] || {}) };
    for (const [id, sw] of Object.entries(p.swaps || {})) { const o = (v.swaps || {})[id] || {}; swaps[id] = { ...sw, ...o, shapes: { ...sw.shapes, ...(o.shapes || {}) } }; }
    return { ...p, parts, swaps, views: {} };
  }
  function domBox(p, keepParts, keepSwaps) {
    if (typeof document === 'undefined' || !document.body) return null;
    const parts = {}, swaps = {};
    for (const [id, pt] of Object.entries(p.parts)) parts[id] = keepParts.has(id) ? pt : { ...pt, strokes: [] };
    for (const [id, sw] of Object.entries(p.swaps || {})) if (keepSwaps.has(id)) swaps[id] = sw;
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    const ns = 'http://www.w3.org/2000/svg', el = document.createElementNS(ns, 'svg');
    el.setAttribute('width', '1'); el.setAttribute('height', '1'); el.style.cssText = 'position:absolute;left:-9999px;top:0';
    el.innerHTML = Puppet.render({ ...p, parts, swaps }, hip[0], p.ground ?? p.artboard[1], { s: 1, blink: 0 });
    document.body.appendChild(el); const b = el.getBBox(); el.remove();
    return b.width || b.height ? [b.x, b.y, b.x + b.width, b.y + b.height] : null;
  }
  function headTree(p) {   // the head and the parts that hang from it (hair, ears, a hat)
    const out = new Set(['head']); let grew = true;
    while (grew) { grew = false; for (const [id, pt] of Object.entries(p.parts)) if (!out.has(id) && out.has(pt.parent)) { out.add(id); grew = true; } }
    return out;
  }
  const FACE = new Set(['eyes', 'pupils', 'mouth', 'brows']);
  function headBox(p, view) { return p.parts.head ? domBox(flat(p, view), headTree(p), FACE) : null; }
  function heights(p, view) {   // the landmarks of a view, in artboard units (rest pose)
    const v = (p.views || {})[view] || {}, part = id => ({ ...(p.parts[id] || {}), ...((v.parts || {})[id] || {}) });
    const hb = headBox(p, view), eb = (p.swaps || {}).eyes ? domBox(flat(p, view), new Set(), new Set(['eyes'])) : null;
    const out = {};
    if (hb) out['top of head'] = hb[1];
    if (eb) out.eyes = (eb[1] + eb[3]) / 2;
    if (p.parts.head) out.chin = part('head').pivot[1];
    if (p.parts.hip) out.hips = part('hip').pivot[1];
    const knee = p.parts.shin_L || p.parts.shin_R; if (knee) out.knees = knee.pivot[1];
    out.ground = p.ground;
    return out;
  }
  function board(p, kind, lib) {
    const L = lib || { clips: {}, presets: {} }, sw = p.swaps || {};
    let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>${ONION}</defs><rect width="${W}" height="${H}" fill="#f6f1e6"/>`;
    const title = { mouth: 'mouth chart', expressions: 'expressions', turnaround: 'turnaround' }[kind] || kind;
    s += `<text x="40" y="58" font-family="Fredoka,sans-serif" font-size="40" font-weight="700" fill="#24160e">${esc(p.name || 'Character')} · ${esc(title)}</text>`;
    if (kind === 'turnaround') {
      const views = [['front', '']].concat(Object.keys(p.views || {}).map(v => [v.replace(/_/g, ' '), v]));
      const cols = views.concat(views.filter(([, v]) => v).map(([l, v]) => [l + ' (other side)', v, true]));
      const n = cols.length, colW = (W - 80) / Math.max(3, n), sc = Math.min(0.85, 820 / p.artboard[1], colW / p.artboard[0] * 0.95);
      const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground], base = 140 + p.ground * sc;
      const toY = y => base - (p.ground - y) * sc, H0 = heights(p, '');
      s += `<text x="40" y="88" font-family="Fredoka,sans-serif" font-size="18" fill="#7a6a5a">height lines from the front view; every view stands on the same ground at the same scale</text>`;
      for (const [k, y] of Object.entries(H0)) s += `<line x1="40" x2="${W - 40}" y1="${toY(y).toFixed(1)}" y2="${toY(y).toFixed(1)}" stroke="#e8743a" stroke-width="1.5" stroke-dasharray="${k === 'ground' ? '' : '8 6'}" opacity="0.8"/>` +
        `<text x="${W - 44}" y="${(toY(y) - 5).toFixed(1)}" text-anchor="end" font-family="Fredoka,sans-serif" font-size="14" fill="#e8743a">${esc(k)}</text>`;
      cols.forEach(([label, v, flip], i) => {
        const cx = 40 + colW * (i + 0.5);
        s += figure(p, { blink: 0, view: v || undefined, flip: flip ? -1 : 1 }, cx, base, sc) +
          `<text x="${cx}" y="${base + 34}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="18" fill="#5a4a3a">${esc(label)}</text>`;
      });
      return s + '</svg>';
    }
    const cells = []; let neutral = { mouth: 'closed' };
    if (kind === 'mouth') {
      const m = sw.mouth || {}, order = [...(m.talk || []), ...Object.keys(m.shapes || {}).filter(k => !(m.talk || []).includes(k))];
      for (const k of order) if ((m.shapes || {})[k]) cells.push(['mouth ' + k, { mouth: k }]);
      neutral = { mouth: (m.shapes || {}).closed ? 'closed' : order[0] };
    } else {
      for (const k of Object.keys((sw.brows || {}).shapes || {})) if (k !== 'neutral') cells.push(['brows ' + k, { brows: k }]);
      for (const k of ['half', 'closed']) if (sw.eyes && sw.eyes.shapes[k]) cells.push(['eyes ' + k, { eyes: k }]);
      if (sw.pupils) cells.push(['look left', { look: [-1, 0] }], ['look right', { look: [1, 0] }], ['look up', { look: [0.3, -1] }]);
      for (const e of ['happy', 'sad', 'angry', 'surprised', 'worried']) {
        const pose = Acting.evaluate(p, { emotion: [[0, e]], blink: false }, 0, L.clips, L.presets);
        cells.push([e, { mouth: pose.mouth, brows: pose.brows, eyes: pose.eyes }]);
      }
    }
    s += `<text x="40" y="88" font-family="Fredoka,sans-serif" font-size="18" fill="#7a6a5a">${cells.length} drawings; the blue ghost is the ${kind === 'mouth' ? 'closed mouth' : 'neutral face'}</text>`;
    const cw = 250, ch = 260, perRow = Math.floor((W - 80) / (cw + 14));
    cells.forEach(([label, pose], i) => { const r = Math.floor(i / perRow), c = i % perRow;
      s += onionCell(p, { blink: 0, ...pose }, { blink: 0, ...neutral }, 40 + c * (cw + 14), 120 + r * (ch + 16), cw, ch, label, kind === 'mouth' ? new Set(['mouth']) : FACE); });
    return s + '</svg>';
  }
  root.Sheet = { build, board, heights };
})(typeof window !== 'undefined' ? window : globalThis);
