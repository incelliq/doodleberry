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

  // palette variants per scene (WP-16; mirrored by dbe/geom.py recolour): desaturate, tint, multiply, clamp, round
  function recolourHex(h, v) {
    if (typeof h !== 'string' || h[0] !== '#' || (h.length !== 4 && h.length !== 7)) return h;
    if (h.length === 4) h = '#' + [...h.slice(1)].map(c => c + c).join('');
    let c = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
    const g = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2], d = v.desat || 0;
    c = c.map(x => x + (g - x) * d);
    if (v.tint) { const t = [1, 3, 5].map(i => parseInt(v.tint.slice(i, i + 2), 16) / 255), a = v.tint_amt || 0; c = c.map((x, k) => x + (t[k] - x) * a); }
    const m = v.mult || [1, 1, 1];
    c = c.map((x, k) => Math.min(1, Math.max(0, x * m[k])));
    return '#' + c.map(x => Math.floor(x * 255 + 0.5).toString(16).padStart(2, '0')).join('');
  }
  function recolour(puppet, v) {
    const p = JSON.parse(JSON.stringify(puppet));
    p.palette = Object.fromEntries(Object.entries(p.palette || {}).map(([k, x]) => [k, recolourHex(x, v)]));
    const strokes = lst => { for (const st of lst || []) for (const k of ['fill', 'stroke']) if (typeof st[k] === 'string' && st[k][0] === '#') st[k] = recolourHex(st[k], v); };
    for (const part of Object.values(p.parts || {})) strokes(part.strokes);
    for (const sw of Object.values(p.swaps || {})) for (const sh of Object.values(sw.shapes || {})) strokes(sh);
    for (const view of Object.values(p.views || {})) {
      for (const part of Object.values(view.parts || {})) if (part && typeof part === 'object') strokes(part.strokes);
      for (const sw of Object.values(view.swaps || {})) for (const sh of Object.values((sw || {}).shapes || {})) strokes(sh);
    }
    return p;
  }
  function colourOf(v, pal) { if (!v) return 'none'; return v[0] === '#' || v === 'none' ? v : pal[v] || '#ff00ff'; }
  // v0.5 toon shading (render option toon: {dir: [x, y] towards the light, d: 7, shade: '#2a1a10', opacity: 0.22, rim: 0}):
  // within each filled vector shape, the band facing away from the light is shaded: the shape is clipped to itself,
  // filled with the shade colour, and the same shape shifted towards the light repaints the lit part. The light stays
  // fixed in the world as parts rotate. The outline is drawn last so it stays crisp.
  function toonSVG(st, fill, line, m, toon) {
    const [lx, ly] = toon.dir || [-0.6, -0.8], n = Math.hypot(lx, ly) || 1, d = toon.d ?? 11;
    // world offset towards the light, expressed in the part's own axes (inverse rotation = transpose)
    const wx = lx / n * d, wy = ly / n * d, vx = m[0] * wx + m[1] * wy, vy = m[2] * wx + m[3] * wy;
    const id = 'tc' + hashStr(st.d), w = st.width || 3;
    let s = `<path d="${st.d}" fill="${fill}"${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`;
    s += `<clipPath id="${id}"><path d="${st.d}"/></clipPath><g clip-path="url(#${id})" opacity="${toon.opacity ?? 0.26}">` +
      `<rect x="-5000" y="-5000" width="10000" height="10000" fill="${toon.shade || '#2a1a10'}"/><path d="${st.d}" transform="translate(${f2(vx)} ${f2(vy)})" fill="${fill}"/></g>`;
    if (toon.rim) s += `<g clip-path="url(#${id})" opacity="${toon.rim}"><path d="${st.d}" fill="${toon.light || '#fff6e0'}"/><path d="${st.d}" transform="translate(${f2(-vx * 0.5)} ${f2(-vy * 0.5)})" fill="${fill}"/></g>`;
    if (line !== 'none') s += `<path d="${st.d}" fill="none" stroke="${line}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`;
    return s;
  }
  function strokesSVG(strokes, pal, m, extra = '', toon = null) {
    if (!strokes || !strokes.length) return '';
    let s = `<g transform="matrix(${m.map(f2).join(' ')})" ${extra}>`;
    for (const st of strokes) {
      if (toon && st.d && !st.image && st.fill && st.fill !== 'none' && (st.opacity == null || st.opacity > 0.9)) { s += toonSVG(st, colourOf(st.fill, pal), colourOf(st.stroke, pal), m, toon); continue; }
      // v0.3 raster part: original ink or paint as an image placed in artboard units
      if (st.image) { s += `<image href="${st.image}" x="${st.x}" y="${st.y}" width="${st.w}" height="${st.h}" preserveAspectRatio="none"${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`; continue; }
      const fill = colourOf(st.fill, pal), line = colourOf(st.stroke, pal);
      s += `<path d="${st.d}" fill="${fill}"${st.rule ? ` fill-rule="${st.rule}"` : ''}${line !== 'none' ? ` stroke="${line}" stroke-width="${st.width || 3}" stroke-linejoin="round" stroke-linecap="round"` : ''}${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`;
    }
    return s + '</g>';
  }

  // ---------- v0.5 mesh strokes: a texture on a triangle mesh whose vertices follow several parts ----------
  // {mesh: {image, iw, ih, verts: [[x, y]...] (artboard, rest pose), uv: [[px, py]...] (texture pixels), tris: [[a, b, c]...],
  //         weights: [[[part, w]...]...] per vertex}}: linear blend skinning with the parts' world matrices, so knees, hips,
  // skirts and hair bend smoothly. Each triangle is the shared texture under its own affine map, clipped to the triangle
  // (grown by `grow` artboard units to hide anti-aliasing seams). Ids hash the content, so a frame stays a pure function.
  const hashStr = s => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); };
  function meshSVG(st, M) {
    const m = st.mesh;
    if (!m._id) m._id = 'mt' + hashStr(m.image.length + ':' + m.image.slice(22, 400) + m.image.slice(-400) + m.verts.length);
    const P = m.verts.map((v, i) => {
      let x = 0, y = 0, ws = 0;
      for (const [pid, w] of m.weights[i] || []) { const q = apply(M[pid] || I, v); x += w * q[0]; y += w * q[1]; ws += w; }
      return ws > 0 ? [x / ws, y / ws] : v;
    });
    const grow = m.grow ?? 0.6;
    let s = `<defs><image id="${m._id}" href="${m.image}" width="${m.iw}" height="${m.ih}"/></defs>`;
    let body = '';
    for (const [a, b, c] of m.tris) {
      const [x0, y0] = P[a], [x1, y1] = P[b], [x2, y2] = P[c], [u0, v0] = m.uv[a], [u1, v1] = m.uv[b], [u2, v2] = m.uv[c];
      const den = (u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0);
      if (Math.abs(den) < 1e-9) continue;
      // affine T with T(u, v) = (x, y) for the three corners
      const A = ((x1 - x0) * (v2 - v0) - (x2 - x0) * (v1 - v0)) / den, C = ((x2 - x0) * (u1 - u0) - (x1 - x0) * (u2 - u0)) / den;
      const B = ((y1 - y0) * (v2 - v0) - (y2 - y0) * (v1 - v0)) / den, D = ((y2 - y0) * (u1 - u0) - (y1 - y0) * (u2 - u0)) / den;
      const E = x0 - A * u0 - C * v0, F = y0 - B * u0 - D * v0;
      const cx = (x0 + x1 + x2) / 3, cy = (y0 + y1 + y2) / 3;
      const g = ([x, y]) => { const dx = x - cx, dy = y - cy, l = Math.hypot(dx, dy) || 1; return [x + dx / l * grow, y + dy / l * grow]; };
      const q = [g(P[a]), g(P[b]), g(P[c])];
      const d = `M${f2(q[0][0])} ${f2(q[0][1])}L${f2(q[1][0])} ${f2(q[1][1])}L${f2(q[2][0])} ${f2(q[2][1])}Z`;
      const cid = 'mc' + hashStr(m._id + d);
      s += `<clipPath id="${cid}"><path d="${d}"/></clipPath>`;
      body += `<g clip-path="url(#${cid})"><use href="#${m._id}" transform="matrix(${[A, B, C, D, E, F].map(v => (+v).toFixed(5)).join(' ')})"/></g>`;
    }
    return s + `<g${st.opacity != null ? ` opacity="${st.opacity}"` : ''}>${body}</g>`;
  }

  // ---------- v0.4 bendy joints: points near a joint blend between the parent's and the child's transforms ----------
  // part.bend = {width}: this part curves out of its parent over `width` artboard units (rubber-hose limbs) instead of
  // hinging rigidly at its pivot. Angle blending keeps the limb's thickness.
  const TOK = /[MLHVCQAZmlhvcqaz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi;
  function arcToCubics(x1, y1, rx, ry, phi, fa, fs, x2, y2) {  // SVG arc -> cubic segments (same maths as dbe/geom.py)
    if (!rx || !ry) return [[x1, y1, x2, y2, x2, y2]];
    const cp = Math.cos(phi * Math.PI / 180), sp = Math.sin(phi * Math.PI / 180);
    const dx = (x1 - x2) / 2, dy = (y1 - y2) / 2, x1p = cp * dx + sp * dy, y1p = -sp * dx + cp * dy;
    rx = Math.abs(rx); ry = Math.abs(ry); const lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry);
    if (lam > 1) { rx *= Math.sqrt(lam); ry *= Math.sqrt(lam); }
    const num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p, den = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
    let co = den ? Math.sqrt(Math.max(0, num / den)) : 0; if (fa === fs) co = -co;
    const cxp = co * rx * y1p / ry, cyp = -co * ry * x1p / rx, cx = cp * cxp - sp * cyp + (x1 + x2) / 2, cy = sp * cxp + cp * cyp + (y1 + y2) / 2;
    const ang = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
    const t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry); let dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
    if (!fs && dt > 0) dt -= 2 * Math.PI; else if (fs && dt < 0) dt += 2 * Math.PI;
    const n = Math.max(1, Math.ceil(Math.abs(dt) / (Math.PI / 2))), d = dt / n, k = 4 / 3 * Math.tan(d / 4), out = [];
    const pt = a => [cx + rx * Math.cos(a) * cp - ry * Math.sin(a) * sp, cy + rx * Math.cos(a) * sp + ry * Math.sin(a) * cp];
    const der = a => [-rx * Math.sin(a) * cp - ry * Math.cos(a) * sp, -rx * Math.sin(a) * sp + ry * Math.cos(a) * cp];
    for (let i = 0, a = t1; i < n; i++, a += d) { const b = a + d, pa = pt(a), pb = pt(b), da = der(a), db = der(b);
      out.push([pa[0] + k * da[0], pa[1] + k * da[1], pb[0] - k * db[0], pb[1] - k * db[1], pb[0], pb[1]]); }
    return out;
  }
  function parsePath(d) {  // -> [[cmd, x1, y1, ...]] absolute M/L/C/Q/Z (arcs become cubics), or null for unsupported commands
    if (/[SsTt]/.test(d)) return null;
    const t = d.match(TOK) || [], out = []; let i = 0, cmd = null, cx = 0, cy = 0, sx = 0, sy = 0;
    const num = () => parseFloat(t[i++]);
    while (i < t.length) {
      if (/[A-Za-z]/.test(t[i])) cmd = t[i++];
      const rel = cmd === cmd.toLowerCase(), C = cmd.toUpperCase(), ox = rel ? cx : 0, oy = rel ? cy : 0;
      if (C === 'Z') { out.push(['Z']); cx = sx; cy = sy; continue; }
      if (C === 'M') { cx = num() + ox; cy = num() + oy; sx = cx; sy = cy; out.push(['M', cx, cy]); cmd = rel ? 'l' : 'L'; }
      else if (C === 'L') { cx = num() + ox; cy = num() + oy; out.push(['L', cx, cy]); }
      else if (C === 'H') { cx = num() + (rel ? cx : 0); out.push(['L', cx, cy]); }
      else if (C === 'V') { cy = num() + (rel ? cy : 0); out.push(['L', cx, cy]); }
      else if (C === 'C') { const a = [num() + ox, num() + oy, num() + ox, num() + oy, num() + ox, num() + oy]; cx = a[4]; cy = a[5]; out.push(['C', ...a]); }
      else if (C === 'Q') { const a = [num() + ox, num() + oy, num() + ox, num() + oy]; cx = a[2]; cy = a[3]; out.push(['Q', ...a]); }
      else if (C === 'A') { const rx = num(), ry = num(), phi = num(), fa = num(), fs = num(), x2 = num() + ox, y2 = num() + oy;
        for (const seg of arcToCubics(cx, cy, rx, ry, phi, fa, fs, x2, y2)) out.push(['C', ...seg]); cx = x2; cy = y2; }
      else return null;
    }
    return out;
  }
  const _pathCache = new Map();
  const parsed = d => { if (!_pathCache.has(d)) _pathCache.set(d, parsePath(d)); return _pathCache.get(d); };
  const smooth01 = u => (u = Math.max(0, Math.min(1, u)), u * u * (3 - 2 * u));
  // joints[k] = {pivot, axis (unit, into the child), width, Mp, Mc}; a point blends toward Mc by how far past the pivot it lies
  function bentD(d, joints, Mown) {
    const P = parsed(d); if (!P) return null;
    const tf = (x, y) => {
      for (const j of joints) {
        const ax = j.axis, nx = [-ax[1], ax[0]], dx = x - j.pivot[0], dy = y - j.pivot[1];
        const s = dx * ax[0] + dy * ax[1], n = dx * nx[0] + dy * nx[1], L = j.width, h = L / 2;
        if (s <= -h) return apply(j.Mp, [x, y]);
        const th = j.theta * Math.PI / 180, c = Math.cos(th), si = Math.sin(th);
        const rigid = (px, py) => [j.pivot[0] + c * (px - j.pivot[0]) - si * (py - j.pivot[1]), j.pivot[1] + si * (px - j.pivot[0]) + c * (py - j.pivot[1])];
        if (s >= h) return apply(j.Mp, rigid(x, y));
        // bend zone: the centre line follows a circular arc of the joint angle; cross-sections stay perpendicular to it
        const k = th / L, u = s + h, phi = k * u;
        const arc = uu => { const f = k * uu, A = Math.abs(k) < 1e-6 ? uu : Math.sin(f) / k, B = Math.abs(k) < 1e-6 ? 0 : (1 - Math.cos(f)) / k;
          return [j.pivot[0] - h * ax[0] + A * ax[0] + B * nx[0], j.pivot[1] - h * ax[1] + A * ax[1] + B * nx[1]]; };
        const cu = arc(u), cp = Math.cos(phi), sp = Math.sin(phi);
        const nr = [cp * nx[0] - sp * ax[0], cp * nx[1] - sp * ax[1]];     // the normal turned by phi
        let lx = cu[0] + n * nr[0], ly = cu[1] + n * nr[1];
        // blend in the small difference between the arc's end and the rigid child, so the hand stays attached
        const end = arc(L), want = rigid(j.pivot[0] + h * ax[0], j.pivot[1] + h * ax[1]), w = smooth01(u / L);
        lx -= (end[0] - want[0]) * w; ly -= (end[1] - want[1]) * w;
        return apply(j.Mp, [lx, ly]);
      }
      return apply(Mown, [x, y]);
    };
    return P.map(c => { if (c[0] === 'Z') return 'Z'; const v = []; for (let k = 1; k < c.length; k += 2) { const q = tf(c[k], c[k + 1]); v.push(f2(q[0]), f2(q[1])); } return c[0] + v.join(' '); }).join(' ');
  }
  function jointsFor(p, M, id, pose) {  // bendy joints touching part `id`: at its own pivot (with its parent) and at its children's pivots
    const out = [], parts = p.parts;
    const axisOf = cid => { const c = parts[cid], bb = c._center || (c._center = centerOf(c)); const dx = bb[0] - c.pivot[0], dy = bb[1] - c.pivot[1], L = Math.hypot(dx, dy) || 1; return [dx / L, dy / L]; };
    const add = cid => { const c = parts[cid]; if (!c || !c.bend || !c.parent || !M[c.parent]) return; if (pose.shifts && pose.shifts[cid]) return;  // shifted joints stay rigid
      out.push({ pivot: c.pivot, axis: axisOf(cid), width: c.bend.width || 40, Mp: M[c.parent], theta: (pose.angles && pose.angles[cid]) || 0 }); };
    add(id);  // only the child limb deforms: it leaves the parent in the parent's direction and curves into its own
    return out;
  }
  function centerOf(part) {  // rough centre of a part's drawing (from path coordinates)
    let sx = 0, sy = 0, n = 0;
    for (const st of part.strokes || []) { const P = st.d ? parsed(st.d) : null; if (!P) continue; for (const c of P) for (let k = 1; k < c.length; k += 2) { sx += c[k]; sy += c[k + 1]; n++; } }
    return n ? [sx / n, sy / n] : [part.pivot[0], part.pivot[1] + 1];
  }

  // world matrices for every part (parents first)
  // v0.9 per-part squash and stretch: pose.scales[part] = [sx, sy] in the part's rest axes, about its pivot. The scale
  // is local: it stretches the part's own drawing and carries its children's pivots with it, but children keep their
  // own proportions (no shear from a stretched parent), so every exporter can reproduce it exactly.
  const scaleAbout = (sc, [px, py]) => [sc[0], 0, 0, sc[1], px - sc[0] * px, py - sc[1] * py];
  function scaleOf(pose, id) { const v = pose.scales && pose.scales[id]; return v == null ? null : Array.isArray(v) ? v : [v, v]; }
  function matrices(p, pose) {
    const parts = p.parts, M = {}, B = {};   // B: the part's bone frame (no own scale), for its children
    const order = Object.keys(parts);
    const visit = id => {
      if (B[id]) return; const part = parts[id];
      const par = part.parent && parts[part.parent] ? part.parent : null;
      if (par) visit(par);
      // v0.4: pose.shifts[part] = [dx, dy] moves a part (and its children) in its parent's space before it rotates
      const sh = (pose.shifts && pose.shifts[id]) || null, ps = par ? scaleOf(pose, par) : null;
      let dx = sh ? sh[0] : 0, dy = sh ? sh[1] : 0;
      if (ps) { const pp = parts[par].pivot; dx += (ps[0] - 1) * (part.pivot[0] - pp[0]); dy += (ps[1] - 1) * (part.pivot[1] - pp[1]); }   // the parent's stretch moves this pivot
      const local = rotAbout((pose.angles && pose.angles[id]) || 0, part.pivot);
      B[id] = mul(par ? B[par] : I, dx || dy ? mul([1, 0, 0, 1, dx, dy], local) : local);
      const own = scaleOf(pose, id);
      M[id] = own ? mul(B[id], scaleAbout(own, part.pivot)) : B[id];
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
  function bentSVG(strokes, pal, M, J) {  // strokes deformed in world space (no group matrix); falls back to rigid per stroke
    let s = '';
    for (const st of strokes) {
      const d2 = st.d && bentD(st.d, J, M);
      if (!d2) { s += strokesSVG([st], pal, M); continue; }
      const fill = colourOf(st.fill, pal), line = colourOf(st.stroke, pal);
      s += `<path d="${d2}" fill="${fill}"${line !== 'none' ? ` stroke="${line}" stroke-width="${st.width || 3}" stroke-linejoin="round" stroke-linecap="round"` : ''}${st.opacity != null ? ` opacity="${st.opacity}"` : ''}/>`;
    }
    return s;
  }
  function render(p, x, y, pose = {}) {
    p = inView(p, pose.view);
    if (p._bendy === undefined) p._bendy = Object.values(p.parts).some(pt => pt.bend);
    const pal = { ...(p.palette || {}), ...(pose.palette || {}) };
    const M = matrices(p, pose);
    const items = [];
    for (const [id, part] of Object.entries(p.parts)) {
      const replaced = Object.entries(p.swaps || {}).some(([sid, sw]) => sw.replaces === id && pose[sid] && sw.shapes[pose[sid]] && sw.shapes[pose[sid]].length);
      const J = p._bendy ? jointsFor(p, M, id, pose) : [];
      const meshes = part.strokes.filter(st => st.mesh), flat = meshes.length ? part.strokes.filter(st => !st.mesh) : part.strokes;
      const svgPart = (J.length ? bentSVG(flat, pal, M[id], J) : strokesSVG(flat, pal, M[id], '', pose.toon || null)) + meshes.map(st => meshSVG(st, M)).join('');
      if (!replaced) items.push({ z: (pose.z && pose.z[id] != null) ? pose.z[id] : (part.z ?? 0), svg: svgPart });
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
      if (sid === 'pupils' && pose.look) mm = mul(mm, [1, 0, 0, 1, pose.look[0] * (sw.movable || 8), pose.look[1] * (sw.movable || 8) * 0.7]);
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
    const weighted = new Set();  // v0.5: parts that carry mesh weights count as drawn
    for (const part of Object.values(p.parts)) for (const st of part.strokes || []) if (st.mesh) for (const ws of st.mesh.weights) for (const [k] of ws) weighted.add(k);
    for (const pt of t.parts) { const part = p.parts[pt.id]; if (pt.required && (!part || (!part.strokes.length && !weighted.has(pt.id)))) out.push({ level: 'missing', msg: `${pt.label}: not drawn yet` }); }
    for (const sw of t.swaps) for (const k of sw.required) if (!p.swaps[sw.id] || !(p.swaps[sw.id].shapes[k] || []).length) out.push({ level: 'missing', msg: `${sw.label}: "${k}" not drawn yet` });
    for (const [id, part] of Object.entries(p.parts)) if (part.strokes.some(st => !st.image && /^#/.test(st.fill || '') || /^#/.test(st.stroke || '') && st.stroke !== p.palette.ink)) out.push({ level: 'warn', msg: `${id}: uses raw colours instead of palette slots (can't be recoloured)` });
    return out;
  }

  root.Puppet = { render, pointOf, fromTemplate, lint, matrices, inView, recolour, recolourHex };
})(typeof window !== 'undefined' ? window : globalThis);
