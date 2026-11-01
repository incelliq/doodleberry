// Doodleberry puppet loader: renders a .puppet (JSON) as SVG for any pose. No dependencies; works in the
// drawing canvas preview and inside engine scenes (frame functions). Exposes `Puppet`.
//
//   const svg = Puppet.render(puppet, x, y, {
//     s: 1, flip: 1,                       // scale, mirror (-1 faces the other way)
//     angles: { upperarm_R: -40, ... },    // degrees per part, relative to the drawn (rest) pose
//     offset: [dx, dy],                    // root translation in artboard units (e.g. a walk bob)
//     talk: 0..1,                          // picks a mouth from the template's talk set (closed → wide)
//     mouth: 'O',                          // or force a mouth shape (overrides talk)
//     eyes: 'open' | 'half' | 'closed', blink: 0..1, brows: 'worried', look: [-1..1, -1..1],
//     hand_R_pose: 'point',                // swap sets that replace a part
//     palette: { cloth1: '#d23c3c' },      // recolour any palette slot
//   Strokes are vector ({d, fill, stroke, width}) or, from v0.3, raster ({image, x, y, w, h}: e.g. scanned pen ink).
//   });
//
// Origin of (x, y) is the puppet's ground point under the hips (artboard [pivot.hip.x, ground]).
(function (root) {
  const f2 = n => (+n).toFixed(2);

  // 2D affine as [a, b, c, d, e, f] (SVG matrix order)
  const mul = (m, n) => [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1], m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]];
  const rotAbout = (deg, [px, py]) => { const r = (deg * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r); return [c, s, -s, c, px - c * px + s * py, py - s * px - c * py]; };
  const apply = (m, [x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
  const I = [1, 0, 0, 1, 0, 0];

  function colourOf(v, pal) { if (!v) return 'none'; return v[0] === '#' || v === 'none' ? v : pal[v] || '#ff00ff'; }
  function strokesSVG(strokes, pal, m, extra = '') {
    if (!strokes || !strokes.length) return '';
    let s = `<g transform="matrix(${m.map(f2).join(' ')})" ${extra}>`;
    for (const st of strokes) {
      // v0.3 raster part: original ink or paint as an image placed in artboard units
      if (st.image) { s += `<image href="${st.image}" x="${st.x}" y="${st.y}" width="${st.w}" height="${st.h}" preserveAspectRatio="none"${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`; continue; }
      const fill = colourOf(st.fill, pal), line = colourOf(st.stroke, pal);
      s += `<path d="${st.d}" fill="${fill}"${line !== 'none' ? ` stroke="${line}" stroke-width="${st.width || 3}" stroke-linejoin="round" stroke-linecap="round"` : ''}${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`;
    }
    return s + '</g>';
  }

  // world matrices for every part (parents first)
  function matrices(p, pose) {
    const parts = p.parts, M = {};
    const order = Object.keys(parts);
    const done = new Set();
    const visit = id => {
      if (done.has(id)) return; const part = parts[id];
      const par = part.parent && parts[part.parent] ? part.parent : null;
      if (par) visit(par);
      // v0.4: pose.shifts[part] = [dx, dy] moves a part (and its children) in its parent's space before it rotates
      const sh = (pose.shifts && pose.shifts[id]) || null;
      const local = rotAbout((pose.angles && pose.angles[id]) || 0, part.pivot);
      M[id] = mul(par ? M[par] : I, sh ? mul([1, 0, 0, 1, sh[0], sh[1]], local) : local); done.add(id);
    };
    order.forEach(visit);
    return M;
  }

  // v0.2 views: p.views[name] = { parts: {id: {strokes, pivot, z}}, swaps: {id: {shapes: {...}}} } overriding the default view
  const _viewCache = new WeakMap();
  function inView(p, view) {
    if (!view || !p.views || !p.views[view]) return p;
    let c = _viewCache.get(p); if (!c) { c = {}; _viewCache.set(p, c); }
    if (c[view]) return c[view];
    const v = p.views[view], parts = {}, swaps = {};
    for (const [id, part] of Object.entries(p.parts)) parts[id] = { ...part, ...((v.parts || {})[id] || {}) };
    for (const [id, sw] of Object.entries(p.swaps || {})) swaps[id] = { ...sw, ...((v.swaps || {})[id] || {}), shapes: { ...sw.shapes, ...(((v.swaps || {})[id] || {}).shapes || {}) } };
    return (c[view] = { ...p, parts, swaps });
  }
  function render(p, x, y, pose = {}) {
    p = inView(p, pose.view);
    const pal = { ...(p.palette || {}), ...(pose.palette || {}) };
    const M = matrices(p, pose);
    const items = [];
    for (const [id, part] of Object.entries(p.parts)) {
      const replaced = Object.entries(p.swaps || {}).some(([sid, sw]) => sw.replaces === id && pose[sid] && sw.shapes[pose[sid]] && sw.shapes[pose[sid]].length);
      if (!replaced) items.push({ z: (pose.z && pose.z[id] != null) ? pose.z[id] : (part.z ?? 0), svg: strokesSVG(part.strokes, pal, M[id]) });
    }
    for (const [sid, sw] of Object.entries(p.swaps || {})) {
      const m = M[sw.anchor] || I;
      let shape = pose[sid];
      if (sid === 'mouth' && !shape) { const set = sw.talk || ['closed', 'small', 'mid', 'wide'].filter(k => sw.shapes[k] && sw.shapes[k].length); const k = Math.min(set.length - 1, Math.floor(Math.max(0, Math.min(1, pose.talk || 0)) * set.length * 0.999)); shape = set[(pose.talk || 0) < 0.08 ? 0 : Math.max(1, k)]; }
      if (sid === 'eyes' && !shape) shape = (pose.blink || 0) > 0.6 ? 'closed' : (pose.blink || 0) > 0.25 ? 'half' : 'open';
      if (sid === 'brows' && !shape) shape = 'neutral';
      if (sid === 'pupils') { if ((pose.blink || 0) > 0.25 || pose.eyes === 'closed') continue; shape = 'default'; }
      if (sw.replaces && !pose[sid]) continue;
      let strokes = sw.shapes[shape];
      if ((!strokes || !strokes.length) && sid === 'eyes' && shape === 'half') strokes = sw.shapes.open;
      if ((!strokes || !strokes.length) && sid === 'mouth') strokes = sw.shapes.small && sw.shapes.small.length && (pose.talk || 0) > 0.08 ? sw.shapes.small : sw.shapes.closed;
      if (!strokes || !strokes.length) continue;
      let mm = m;
      const ssh = pose.shifts && pose.shifts['@' + sid];  // driven offsets for swap sets (e.g. the face moving as the head turns)
      if (ssh) mm = mul(mm, [1, 0, 0, 1, ssh[0], ssh[1]]);
      if (sid === 'pupils' && pose.look) mm = mul(m, [1, 0, 0, 1, pose.look[0] * (sw.movable || 8), pose.look[1] * (sw.movable || 8) * 0.7]);
      items.push({ z: (pose.z && pose.z['@' + sid] != null) ? pose.z['@' + sid] : (sw.z ?? 40), svg: strokesSVG(strokes, pal, mm) });
    }
    items.sort((a, b) => a.z - b.z);
    const s = pose.s ?? 1, flip = pose.flip ?? 1, [ox, oy] = pose.offset || [0, 0];
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    const sq = pose.squash ?? 1;
    const base = `translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip * sq)} ${f2(s)}) translate(${f2(-hip[0] + ox)} ${f2(-(p.ground ?? p.artboard[1]) + oy)})`;
    return `<g transform="${base}">${items.map(i => i.svg).join('')}</g>`;
  }

  // world position of a part's point (e.g. a hand for props), in the same space render() draws into
  function pointOf(p, id, pt, x, y, pose = {}) {
    p = inView(p, pose.view);
    const M = matrices(p, pose), [px, py] = apply(M[id] || I, pt || p.parts[id].pivot);
    const s = pose.s ?? 1, flip = pose.flip ?? 1, [ox, oy] = pose.offset || [0, 0];
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    return [x + (px - hip[0] + ox) * s * flip, y + (py - (p.ground ?? p.artboard[1]) + oy) * s];
  }

  // build an empty puppet from a template
  function fromTemplate(t, name = 'Untitled') {
    const parts = {}; for (const pt of t.parts) parts[pt.id] = { parent: pt.parent, pivot: [...pt.pivot], z: pt.z, strokes: [] };
    const swaps = {}; for (const sw of t.swaps) swaps[sw.id] = { anchor: sw.anchor, z: sw.z, shapes: Object.fromEntries(sw.shapes.map(k => [k, []])), ...(sw.talk ? { talk: sw.talk } : {}), ...(sw.movable ? { movable: sw.movable } : {}), ...(sw.replaces ? { replaces: sw.replaces } : {}) };
    const palette = { skin: '#eebd9a', hair: '#5a3a26', cloth1: '#3f7fd0', cloth2: '#2c2f3a', cloth3: '#ffffff', shoe: '#3a2a20', eye: '#ffffff', ink: '#24160e', blush: '#ff8f8a' };
    return { format: 'doodleberry.puppet', version: '0.1', name, template: t.template, artboard: [...t.artboard], ground: t.ground, palette, parts, swaps, meta: { author: '', license: '', created: '' } };
  }

  // completeness and sanity checks against a template ("rig linter")
  function lint(p, t) {
    const out = [];
    for (const pt of t.parts) { const part = p.parts[pt.id]; if (pt.required && (!part || !part.strokes.length)) out.push({ level: 'missing', msg: `${pt.label}: not drawn yet` }); }
    for (const sw of t.swaps) for (const k of sw.required) if (!p.swaps[sw.id] || !(p.swaps[sw.id].shapes[k] || []).length) out.push({ level: 'missing', msg: `${sw.label}: "${k}" not drawn yet` });
    for (const [id, part] of Object.entries(p.parts)) if (part.strokes.some(st => !st.image && /^#/.test(st.fill || '') || /^#/.test(st.stroke || '') && st.stroke !== p.palette.ink)) out.push({ level: 'warn', msg: `${id}: uses raw colours instead of palette slots (can't be recoloured)` });
    return out;
  }

  root.Puppet = { render, pointOf, fromTemplate, lint, matrices, inView };
})(typeof window !== 'undefined' ? window : globalThis);
