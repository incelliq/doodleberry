// Doodleberry compositor and multiplane camera (WP-36): shots.json "comp" turns a shot into depth planes with
// parallax and depth of field, and per-plane nodes (grade, blur, glow, mask, blend), all SVG filters and masks in the
// SVG renderer: pure functions of time, so a rerun gives the same pixels. Exposes window.COMP.
//
//   "comp": {
//     "planes": [   // far to near; the shot's own set, cast and props are the plane "stage" (depth 1) unless listed
//       {"id": "sky", "depth": 6, "set": "night", "set_opts": {}, "drift": [4, 0]},
//       {"id": "hills", "depth": 2.5, "items": [{"type": "shape", "svg": "<path d='...' fill='#1d2b45'/>"},
//                                             {"type": "gradient", "kind": "radial", "rect": [0, 0, 1080, 1920], "center": [540, 900], "r": 700,
//                                              "stops": [[0, "#ffd27a", 0.5], [1, "#ffd27a", 0]]}]},
//       {"id": "stage", "depth": 1},
//       {"id": "front", "depth": 0.6, "items": [...]},    // cast entries with "plane": "front" are drawn here
//       {"id": "set3d", "depth": 40, "screen": true, "items": [{"type": "plate", "src": "proc/<key>/f_%04d.png", "start": 0, "fps": 30, "count": 120}]},
//       // WP-42: screen-locked (the 3D render is framed by the shot camera already); items also "particles":
//       // {"type": "particles", "kind": "confetti" | "snow" | "rain", "count": 90, "seed": 3, "rect": [x, y, w, h], "start": t}
//     ],
//     "stereo": {"separation": 24, "convergence": 1},   // WP-37: px of parallax at infinite depth; the depth on the screen
//     "linear": true,                      // WP-37: the planes' filters (grade, blur, glow, depth of field) work in linear light
//                                          // (brighter, truer halos); blending between planes stays the browser's sRGB
//     "focus": 1, "dof": 3,                // blur px per unit of |1/depth - 1/focus| (0: everything sharp)
//     "zoom": "scale" | "dolly",           // how planes zoom with the camera (dolly: true perspective, matches 3D renders)
//     "nodes": [
//       {"type": "grade", "plane": "sky", "brightness": 0.9, "contrast": 1.1, "saturation": 0.8, "tint": "#3050a0", "tint_amount": 0.15},
//       {"type": "blur", "plane": "hills", "radius": 2},
//       {"type": "glow", "plane": "front", "radius": 16, "strength": 0.9, "colour": "#ffb060"},
//       {"type": "mask", "plane": "sky", "shape": {"ellipse": [540, 700, 700, 600]}, "feather": 80, "invert": false, "screen": false},
//       {"type": "blend", "plane": "fog", "mode": "screen", "opacity": 0.6}
//     ]
//   }
//
//   WP-36, part 2:
//     "roll": 4 | [[t, deg], ...] | "=2*sin(t)"   camera roll about the frame centre (degrees)
//     any number in a plane, node or "roll"/"focus"/"dof" may be keyed ([[t, v], ...], linear) or an expression
//       ("=0.9 + 0.1*sin(2*t)"; t, sin, cos, abs, min, max, pow, sqrt, floor, clamp(v, a, b), pi, and
//       track("id", "x" | "y" | "luma") for a tracked region, below): pure functions of time
//     {"type": "lightwrap", "plane": "stage", "from": ["sky", "hills"], "radius": 14, "strength": 0.7}
//       the planes behind (or those listed) bleed their light onto the plane's edges (the real background, blurred)
//     items {"type": "prim", "shape": "circle" | "rect" | "star" | "polygon" | "arc" | "wave", ...} (WP-42): parametric
//       shapes whose numbers may be keyed or expressions; {"type": "growth", "seed", "x", "y", "length", "depth",
//       "start", "duration", ...}: a seeded plant growing over time
//     items {"type": "group", "items": [...], "pivot", "translate", "rotate", "scale", "opacity", "deform": {...}}: nested
//       groups whose motion and deformation compose (see group() below)
//     "tracks": {"sign": [[t, x, y, luma], ...]}   written by comp.track (a region followed through a plate); an item
//       with "attach": "sign" moves with it ("offset" adds [dx, dy], each keyed or an expression too)
// Parallax: a plane at depth d follows the camera by 1/d (the stage, d = 1, moves with it; far planes move less, near
// planes more), and zooms by 1 + (zoom - 1) / d. "drift" moves a plane on its own (px/s). Ids start with "comp-": the
// AI-look lint treats them as deliberate compositing, not generic effects.
(function (root) {
  const f2 = v => (+v).toFixed(2);
  const SAFE = s => String(s).replace(/<\/?(script|foreignObject|iframe)[^>]*>/gi, '').replace(/\son\w+\s*=/gi, ' data-x=');
  function hex(c) { const s = String(c || '#000').replace('#', ''); const v = s.length === 3 ? s.split('').map(x => x + x).join('') : s; return [0, 2, 4].map(i => parseInt(v.slice(i, i + 2), 16) / 255); }

  // WP-36: keyed values and expressions, pure functions of time
  function keyed(keys, t) {
    if (!keys.length) return 0; if (t <= keys[0][0]) return keys[0][1]; const L = keys[keys.length - 1]; if (t >= L[0]) return L[1];
    for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { const [t0, v0] = keys[i - 1], [t1, v1] = keys[i], u = (t - t0) / Math.max(1e-9, t1 - t0); return v0 + (v1 - v0) * u; }
    return L[1];
  }
  const EXPR = new Map();
  const FN = { sin: Math.sin, cos: Math.cos, abs: Math.abs, min: Math.min, max: Math.max, pow: Math.pow, sqrt: Math.sqrt, floor: Math.floor,
    clamp: (v, a, b) => Math.max(a, Math.min(b, v)), pi: Math.PI };
  function compile(src) {
    if (EXPR.has(src)) return EXPR.get(src);
    const body = src.replace(/^=/, '');
    // only numbers, operators, brackets, commas, quoted ids and whitelisted names: anything else is refused
    const names = body.replace(/"[^"]*"|'[^']*'/g, '""').match(/[A-Za-z_]\w*/g) || [];
    for (const n of names) if (n !== 't' && n !== 'track' && !Object.prototype.hasOwnProperty.call(FN, n)) throw new Error(`comp expression: unknown name ${n} in ${src}`);
    const bare = body.replace(/"[^"]*"|'[^']*'/g, '""');
    if (/[;{}\[\]=`\\]/.test(bare) || /\.(?!\d)/.test(bare.replace(/\d\.\d/g, '0'))) throw new Error(`comp expression: not allowed: ${src}`);   // no property access
    const f = new Function('t', 'track', ...Object.keys(FN), `return (${body});`);
    EXPR.set(src, f); return f;
  }
  function trackVal(ctx, id, field, t) {
    const tr = ((ctx.comp || {}).tracks || {})[id]; if (!tr || !tr.length) return 0;
    const col = { x: 1, y: 2, luma: 3 }[field || 'x'] || 1;
    return keyed(tr.map(r => [r[0], r[col] ?? 0]), t);
  }
  function V(v, t, ctx, dflt) {
    if (v == null) return dflt;
    if (typeof v === 'number') return v;
    if (Array.isArray(v) && v.length && Array.isArray(v[0])) return keyed(v, t);
    if (typeof v === 'string' && v.startsWith('=')) return +compile(v)(t, (id, f) => trackVal(ctx, id, f, t), ...Object.values(FN));
    return v;
  }
  const VALUED = ['brightness', 'contrast', 'saturation', 'tint_amount', 'radius', 'strength', 'opacity', 'feather', 'depth'];
  const at = (o, t, ctx) => { const r = { ...o }; for (const k of VALUED) if (k in r) r[k] = V(r[k], t, ctx); if (Array.isArray(r.drift) && !Array.isArray(r.drift[0])) r.drift = r.drift.map(x => V(x, t, ctx, 0)); return r; };

  function item(it, t, tag, k, ctx) {
    if (it.attach || it.offset) {   // WP-36: an item following a tracked region, or moved by keys or an expression
      const dx = (it.attach ? trackVal(ctx, it.attach, 'x', t) - trackVal(ctx, it.attach, 'x', (((ctx.comp || {}).tracks || {})[it.attach] || [[0]])[0][0]) : 0) + V((it.offset || [])[0], t, ctx, 0);
      const dy = (it.attach ? trackVal(ctx, it.attach, 'y', t) - trackVal(ctx, it.attach, 'y', (((ctx.comp || {}).tracks || {})[it.attach] || [[0]])[0][0]) : 0) + V((it.offset || [])[1], t, ctx, 0);
      const { attach, offset, ...rest } = it;
      return `<g transform="translate(${f2(dx)} ${f2(dy)})">${item(rest, t, tag, k, ctx)}</g>`;
    }
    if (it.type === 'shape') return SAFE(it.svg || '');
    if (it.type === 'gradient') {
      const id = `comp-g-${tag}-${k}`, [x, y, w, h] = it.rect || [0, 0, ctx.W, ctx.H];
      const stops = (it.stops || [[0, '#000', 1], [1, '#000', 0]]).map(([o, c, a]) => `<stop offset="${o}" stop-color="${c}" stop-opacity="${a ?? 1}"/>`).join('');
      const g = it.kind === 'radial'
        ? `<radialGradient id="${id}" gradientUnits="userSpaceOnUse" cx="${(it.center || [x + w / 2])[0]}" cy="${(it.center || [0, y + h / 2])[1]}" r="${it.r || Math.max(w, h) / 2}">${stops}</radialGradient>`
        : `<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${(it.from || [x, y])[0]}" y1="${(it.from || [x, y])[1]}" x2="${(it.to || [x, y + h])[0]}" y2="${(it.to || [x, y + h])[1]}">${stops}</linearGradient>`;
      return `<defs>${g}</defs><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="url(#${id})"/>`;
    }
    if (it.type === 'stars') {   // a seeded star field (no randomness at render time)
      let s = '', seed = it.seed || 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
      const [x0, y0, w, h] = it.rect || [0, 0, ctx.W, ctx.H * 0.6];
      for (let i = 0; i < (it.count || 120); i++) { const x = x0 + rnd() * w, y = y0 + rnd() * h, r = 0.8 + rnd() * (it.size || 2.2), tw = 0.55 + 0.45 * Math.sin(t * (1 + rnd() * 2) + i);
        s += `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(r)}" fill="${it.colour || '#fff8e0'}" opacity="${f2(tw)}"/>`; }
      return s;
    }
    if (it.type === 'plate') {   // WP-42: a rendered image sequence (a Geometry Nodes 3D set), one image per frame
      const fps = it.fps || 30, n = it.count || 1, every = it.every || 1;
      let f = Math.round((t - (it.start || 0)) * fps); f = Math.max(0, Math.min(n - 1, f)); f -= f % every;
      const src = String(it.src || '').replace('%04d', String(f).padStart(4, '0'));
      return `<image href="${src}" x="0" y="0" width="${ctx.W}" height="${ctx.H}" preserveAspectRatio="none"/>`;
    }
    if (it.type === 'particles') return particles(it, t, ctx);
    if (it.type === 'prim') return prim(it, t, ctx);
    if (it.type === 'growth') return growth(it, t, ctx);
    if (it.type === 'group') return group(it, t, tag, k, ctx);
    return ctx.overlay ? ctx.overlay(it, t) : '';
  }

  // WP-36: nested groups. A group's items (any item, groups too) move together: translate, then rotate and scale
  // about the pivot (each keyed or an expression), so a child group moves inside its parent's motion. A deformer bends
  // the group's drawing in the group's own space (so a deformed child is deformed again by its parent):
  //   {"kind": "wave", "axis": "y", "amount": 18, "wavelength": 240, "speed": 0.5, "rect": [x, y, w, h]}  a travelling sine
  //       (axis y: points move up and down as a sine of x; axis x: left and right as a sine of y)
  //   {"kind": "bend", "amount": 60, "rect": [...]}   x moves by amount * ((y - top) / h)^2: bends over toward the bottom
  //   {"kind": "shear", "amount": 40, "rect": [...]}  x moves by amount * (y - top) / h
  //   {"kind": "noise", "amount": 10, "scale": 0.02, "seed": 3, "speed": 1}  a seeded wobble (heat haze, a boil)
  // Each is an SVG displacement map (an image of the offsets, drawn as a gradient) over `rect` (default the frame), a
  // pure function of time. Offsets beyond the rect hold the edge value.
  function group(it, t, tag, k, ctx) {
    const gid = `${tag}-g${k}`, [px, py] = (it.pivot || [0, 0]).map(v => V(v, t, ctx, 0));
    const tr = (it.translate || [0, 0]).map(v => V(v, t, ctx, 0)), rot = V(it.rotate, t, ctx, 0);
    const sc = Array.isArray(it.scale) && !Array.isArray(it.scale[0]) ? it.scale.map(v => V(v, t, ctx, 1)) : [V(it.scale, t, ctx, 1), V(it.scale, t, ctx, 1)];
    const inner = (it.items || []).map((c, j) => item(c, t, gid, j, ctx)).join('');
    let body = inner, defs = '';
    if (it.deform) { const fd = deformFilter(`comp-${gid}-def`, it.deform, t, ctx); if (fd) { defs += fd; body = `<g filter="url(#comp-${gid}-def)">${inner}</g>`; } }
    const T = `translate(${f2(tr[0])} ${f2(tr[1])}) translate(${f2(px)} ${f2(py)}) rotate(${(+rot).toFixed(3)}) scale(${(+sc[0]).toFixed(4)} ${(+sc[1]).toFixed(4)}) translate(${f2(-px)} ${f2(-py)})`;
    const op = V(it.opacity, t, ctx, 1);
    return `${defs ? `<defs>${defs}</defs>` : ''}<g transform="${T}"${op < 1 ? ` opacity="${op}"` : ''}>${body}</g>`;
  }
  function deformFilter(id, d, t, ctx) {
    const [x, y, w, h] = d.rect || [0, 0, ctx.W, ctx.H], amt = V(d.amount, t, ctx, 0), kind = d.kind || 'wave';
    if (!amt) return '';
    const pad = Math.abs(amt) + 4, R = `x="${f2(x - pad)}" y="${f2(y - pad)}" width="${f2(w + 2 * pad)}" height="${f2(h + 2 * pad)}"`;
    if (kind === 'noise') {
      const sc = d.scale || 0.02, ph = (d.speed || 1) * t;
      return `<filter id="${id}" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" ${R} color-interpolation-filters="sRGB">`
        + `<feTurbulence type="fractalNoise" baseFrequency="${sc}" numOctaves="2" seed="${d.seed || 1}" result="n0"/><feOffset in="n0" dx="${f2(ph * 40)}" dy="${f2(ph * 23)}" result="n"/>`
        + `<feDisplacementMap in="SourceGraphic" in2="n" scale="${f2(2 * amt)}" xChannelSelector="R" yChannelSelector="G"/></filter>`;
    }
    // the map: the offset as a fraction of `amt`, stored as 0.5 - 0.5 * u in one channel (the other stays 0.5: no move);
    // the displacement samples the drawing at the offset, so storing -u moves each point by +amt * u. It is built from
    // filter primitives alone, so it is there the moment the frame is drawn (an image would load later): strips of
    // flat colour along the ramp (the outer two reaching into the margin, so offsets hold flat beyond the rect),
    // smoothed by a blur along the ramp only
    const N = 64, along = kind === 'wave' && (d.axis || 'y') === 'y' ? 'x' : 'y', L = along === 'x' ? w : h, st = L / N;
    const u = q => kind === 'wave' ? Math.sin(2 * Math.PI * ((q * L) / (d.wavelength || 240) - (d.speed || 0) * t))
      : kind === 'bend' ? q * q : kind === 'shear' ? q : 0;
    const ch = kind === 'wave' && (d.axis || 'y') === 'y' ? 'G' : 'R';
    let prim = '';
    for (let i = 0; i < N; i++) {
      const v = Math.round(255 * (0.5 - 0.5 * Math.max(-1, Math.min(1, u((i + 0.5) / N))))), c = ch === 'R' ? `rgb(${v},128,128)` : `rgb(128,${v},128)`;
      const a0 = i === 0 ? -pad : i * st, a1 = i === N - 1 ? L + pad : (i + 1) * st;
      const sub = along === 'x' ? `x="${f2(x + a0)}" y="${f2(y - pad)}" width="${f2(a1 - a0 + 0.5)}" height="${f2(h + 2 * pad)}"`
        : `x="${f2(x - pad)}" y="${f2(y + a0)}" width="${f2(w + 2 * pad)}" height="${f2(a1 - a0 + 0.5)}"`;
      prim += `<feFlood flood-color="${c}" ${sub} result="s${i}"/>`;
    }
    prim += `<feMerge ${R} result="steps">${Array.from({ length: N }, (_, i) => `<feMergeNode in="s${i}"/>`).join('')}</feMerge>`;
    prim += `<feGaussianBlur in="steps" ${R} edgeMode="duplicate" stdDeviation="${along === 'x' ? `${f2(st * 0.6)} 0` : `0 ${f2(st * 0.6)}`}" result="map"/>`;
    return `<filter id="${id}" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" ${R} color-interpolation-filters="sRGB">${prim}`
      + `<feDisplacementMap in="SourceGraphic" in2="map" scale="${f2(2 * amt)}" xChannelSelector="R" yChannelSelector="G"/></filter>`;
  }

  // WP-42: seeded particles, a pure function of time (each particle's path is fixed by the seed; nothing is simulated)
  function particles(it, t, ctx) {
    const st = it.start || 0; if (t < st || (it.end != null && t > it.end)) return '';
    let seed = it.seed || 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    const [x0, y0, w, h] = it.rect || [0, -40, ctx.W, ctx.H + 80], kind = it.kind || 'confetti', u = t - st;
    const cols = it.colours || (kind === 'confetti' ? ['#e8603c', '#f6c945', '#3c8ee8', '#5fb85a', '#b05fd0'] : ['#ffffff']);
    let s = '';
    for (let i = 0; i < (it.count || 80); i++) {
      const px = rnd(), py = rnd(), sp = rnd(), sw = rnd(), ph = rnd() * 6.283, c = cols[Math.floor(rnd() * cols.length) % cols.length], sz = rnd();
      if (kind === 'rain') { const v = 900 + 500 * sp, y = y0 + ((py * h + v * u) % h), x = x0 + ((px * w + 0.25 * v * u) % w);
        s += `<path d="M${f2(x)} ${f2(y)} l${f2(-10)} ${f2(-40)}" stroke="${it.colour || '#7fa6c9'}" stroke-width="3" stroke-linecap="round" opacity="0.7"/>`; continue; }
      const v = kind === 'snow' ? 60 + 60 * sp : 140 + 160 * sp, y = y0 + ((py * h + v * u) % h), x = x0 + px * w + (kind === 'snow' ? 20 : 34) * Math.sin(u * (1 + sw * 2) + ph);
      if (kind === 'snow') { s += `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(3 + 4 * sz)}" fill="${c}" opacity="0.9"/>`; continue; }
      const a = (u * (180 + 360 * sw) + ph * 57.3) % 360, k = Math.cos((u * (3 + 4 * sw) + ph));   // tumbling: the piece flips edge-on
      s += `<rect x="-8" y="-5" width="16" height="10" rx="2" fill="${c}" stroke="#181e26" stroke-width="1.5" transform="translate(${f2(x)} ${f2(y)}) rotate(${f2(a)}) scale(1 ${f2(Math.max(0.15, Math.abs(k)))})"/>`;
    }
    return s;
  }

  // WP-42: an animated parametric primitive. Every number may be keyed or an expression (V), so shapes morph in time:
  // circle (r), rect (w, h, round), star (points, r, inner), polygon (sides, r), arc (r, start, end in degrees: a
  // pie or a ring with "ring"), wave (w, amp, freq, phase: a sine line). x, y, rotate, scale, fill, stroke, width.
  function prim(it, t, ctx) {
    const v = (k, d) => V(it[k], t, ctx, d), x = v('x', 540), y = v('y', 960), rot = v('rotate', 0), sc = v('scale', 1);
    const fill = it.fill || 'none', stroke = it.stroke || 'none', sw = v('width', 4), sh = it.shape || 'circle';
    let d = '';
    if (sh === 'circle') { const r = Math.max(0, v('r', 60)); d = `M${f2(-r)} 0 A${f2(r)} ${f2(r)} 0 1 0 ${f2(r)} 0 A${f2(r)} ${f2(r)} 0 1 0 ${f2(-r)} 0 Z`; }
    else if (sh === 'rect') { const w = v('w', 120), h = v('h', 80), rr = Math.min(Math.abs(v('round', 0)), w / 2, h / 2);
      d = `M${f2(-w / 2 + rr)} ${f2(-h / 2)} H${f2(w / 2 - rr)} A${f2(rr)} ${f2(rr)} 0 0 1 ${f2(w / 2)} ${f2(-h / 2 + rr)} V${f2(h / 2 - rr)} A${f2(rr)} ${f2(rr)} 0 0 1 ${f2(w / 2 - rr)} ${f2(h / 2)} H${f2(-w / 2 + rr)} A${f2(rr)} ${f2(rr)} 0 0 1 ${f2(-w / 2)} ${f2(h / 2 - rr)} V${f2(-h / 2 + rr)} A${f2(rr)} ${f2(rr)} 0 0 1 ${f2(-w / 2 + rr)} ${f2(-h / 2)} Z`; }
    else if (sh === 'star' || sh === 'polygon') {
      const n = Math.max(3, Math.round(v(sh === 'star' ? 'points' : 'sides', 5))), r = v('r', 60), ri = sh === 'star' ? v('inner', r * 0.45) : r, k = sh === 'star' ? 2 * n : n;
      for (let i = 0; i < k; i++) { const a = -Math.PI / 2 + i * 2 * Math.PI / k, rr = sh === 'star' && i % 2 ? ri : r; d += `${i ? 'L' : 'M'}${f2(rr * Math.cos(a))} ${f2(rr * Math.sin(a))} `; }
      d += 'Z';
    } else if (sh === 'arc') {
      const r = v('r', 60), a0 = v('start', 0) * Math.PI / 180, a1 = v('end', 270) * Math.PI / 180, big = Math.abs(a1 - a0) % (2 * Math.PI) > Math.PI ? 1 : 0;
      const p0 = [r * Math.cos(a0), r * Math.sin(a0)], p1 = [r * Math.cos(a1), r * Math.sin(a1)];
      d = it.ring ? `M${f2(p0[0])} ${f2(p0[1])} A${f2(r)} ${f2(r)} 0 ${big} 1 ${f2(p1[0])} ${f2(p1[1])}` : `M0 0 L${f2(p0[0])} ${f2(p0[1])} A${f2(r)} ${f2(r)} 0 ${big} 1 ${f2(p1[0])} ${f2(p1[1])} Z`;
    } else if (sh === 'wave') {
      const w = v('w', 400), amp = v('amp', 30), fq = v('freq', 2), ph = v('phase', 0), n = 64;
      for (let i = 0; i <= n; i++) { const u = i / n, xx = -w / 2 + u * w, yy = amp * Math.sin(2 * Math.PI * (fq * u) + ph); d += `${i ? 'L' : 'M'}${f2(xx)} ${f2(yy)} `; }
    }
    return `<path transform="translate(${f2(x)} ${f2(y)}) rotate(${f2(rot)}) scale(${(+sc).toFixed(4)})" d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${f2(sw)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  }

  // WP-42: procedural growth, a seeded branching plant that grows over [start, start + duration]: each branch draws
  // along its length once its parent reaches the fork, thinner and shorter each level; leaves open at the tips. The
  // whole structure comes from the seed (no randomness at render time), so a frame is a pure function of time.
  function growth(it, t, ctx) {
    let seed = it.seed || 11; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    const x0 = V(it.x, t, ctx, 540), y0 = V(it.y, t, ctx, 1700), L0 = V(it.length, t, ctx, 260), depth = Math.min(7, Math.max(1, it.depth || 5));
    const st = it.start || 0, dur = Math.max(0.05, it.duration || 3), g = Math.max(0, Math.min(1, (t - st) / dur)) * depth;   // the last level's leaves open as t reaches start + duration
    const col = it.colour || '#3d6b35', leaf = it.leaf || '#6fae4f', w0 = V(it.width, t, ctx, 14), spread = (it.spread ?? 28) * Math.PI / 180;
    let s = '';
    const grow = (x, y, ang, len, w, lv) => {   // branch lv draws over growth time [lv, lv + 1]
      const k = Math.max(0, Math.min(1, g - lv)); if (k <= 0) return;
      const bend = (rnd() - 0.5) * 0.5, ex = x + Math.cos(ang) * len * k, ey = y + Math.sin(ang) * len * k;
      const cx = x + Math.cos(ang + bend) * len * k * 0.5, cy = y + Math.sin(ang + bend) * len * k * 0.5;
      s += `<path d="M${f2(x)} ${f2(y)} Q${f2(cx)} ${f2(cy)} ${f2(ex)} ${f2(ey)}" fill="none" stroke="${col}" stroke-width="${f2(w)}" stroke-linecap="round"/>`;
      const kids = lv + 1 < depth ? 2 + (rnd() < 0.35 ? 1 : 0) : 0, jit = [rnd(), rnd(), rnd(), rnd(), rnd(), rnd()];
      if (!kids) { const o = Math.max(0, Math.min(1, (g - lv - 0.6) / 0.4)), r = 10 + 8 * jit[0];
        if (o > 0) s += `<ellipse cx="${f2(ex)}" cy="${f2(ey)}" rx="${f2(r * o)}" ry="${f2(r * 0.55 * o)}" transform="rotate(${f2(ang * 57.3)} ${f2(ex)} ${f2(ey)})" fill="${leaf}"/>`; return; }
      if (k < 1) return;
      for (let c = 0; c < kids; c++) {
        const a = ang + (kids === 2 ? (c ? 1 : -1) : (c - 1)) * spread * (0.7 + 0.6 * jit[c]);
        grow(ex, ey, a, len * (0.62 + 0.18 * jit[c + 3]), w * 0.68, lv + 1);
      }
    };
    grow(x0, y0, -Math.PI / 2 + (V(it.lean, t, ctx, 0) * Math.PI / 180), L0, w0, 0);
    return s;
  }

  // zoom "scale" (default): a plane zooms by 1 + (z - 1) / d. zoom "dolly" (WP-42): true perspective, the camera moves in
  // by 1 - 1/z of its distance to the stage, so a plane zooms by d / (d - 1 + 1/z), exactly as a 3D render framed by
  // the same camera does (the stage, d = 1, zooms by z either way)
  // WP-37 depth pass: depth d as a 24-bit colour (thousandths of a depth unit), filled over what a group draws, opaque
  // and crisp, so a pixel decodes to exactly one depth: the nearest plane covering it
  function depthFill(d, W, H) {
    const code = Math.max(1, Math.min(16777215, Math.round(d * 1000))), hexc = '#' + code.toString(16).padStart(6, '0'), id = 'comp-dp' + code;
    return { id, def: `<filter id="${id}" filterUnits="userSpaceOnUse" x="${-4 * W}" y="${-4 * H}" width="${9 * W}" height="${9 * H}" color-interpolation-filters="sRGB">`
      + `<feComponentTransfer in="SourceAlpha" result="a"><feFuncA type="discrete" tableValues="0 1"/></feComponentTransfer><feFlood flood-color="${hexc}"/><feComposite in2="a" operator="in"/></filter>` };
  }
  function camFor(d, view, W, H, drift, t, model) {
    const [cx, cy, z] = view, zp = model === 'dolly' ? d / Math.max(1e-3, d - 1 + 1 / z) : 1 + (z - 1) / d;
    const px = W / 2 + (cx - W / 2) / d - (drift ? drift[0] * t : 0), py = H / 2 + (cy - H / 2) / d - (drift ? drift[1] * t : 0);
    return `translate(${f2(W / 2)} ${f2(H / 2)}) scale(${zp.toFixed(4)}) translate(${f2(-px)} ${f2(-py)})`;
  }

  function filterFor(id, nodes, dofR, linear) {
    let prim = '', last = 'SourceGraphic', n = 0;
    const out = () => `r${n++}`;
    for (const nd of nodes) {
      if (nd.type === 'grade') {
        const b = nd.brightness ?? 1, c = nd.contrast ?? 1, s = nd.saturation ?? 1, o = (1 - c) / 2;
        const sat = `<feColorMatrix in="${last}" type="saturate" values="${s}" result="${out()}"/>`; last = `r${n - 1}`;
        const bc = `<feComponentTransfer in="${last}" result="${out()}">` + ['R', 'G', 'B'].map(ch => `<feFunc${ch} type="linear" slope="${(b * c).toFixed(4)}" intercept="${(o * b).toFixed(4)}"/>`).join('') + `</feComponentTransfer>`; last = `r${n - 1}`;
        prim += sat + bc;
        if (nd.tint) { const [r, g, bb] = hex(nd.tint), a = nd.tint_amount ?? 0.2;
          prim += `<feColorMatrix in="${last}" type="matrix" values="${[[1 - a, 0, 0, 0, a * r], [0, 1 - a, 0, 0, a * g], [0, 0, 1 - a, 0, a * bb], [0, 0, 0, 1, 0]].map(rw => rw.map(v => v.toFixed(4)).join(' ')).join(' ')}" result="${out()}"/>`; last = `r${n - 1}`; }
      } else if (nd.type === 'blur') {
        prim += `<feGaussianBlur in="${last}" stdDeviation="${nd.radius || 2}" result="${out()}"/>`; last = `r${n - 1}`;
      } else if (nd.type === 'glow') {
        const [r, g, bb] = hex(nd.colour || '#ffffff'), k = nd.strength ?? 0.8, src = last;
        prim += `<feGaussianBlur in="${src}" stdDeviation="${nd.radius || 12}" result="${out()}"/>`; const bl = `r${n - 1}`;
        prim += `<feColorMatrix in="${bl}" type="matrix" values="0 0 0 0 ${r.toFixed(3)} 0 0 0 0 ${g.toFixed(3)} 0 0 0 0 ${bb.toFixed(3)} 0 0 0 ${k} 0" result="${out()}"/>`; const gl = `r${n - 1}`;
        prim += `<feMerge result="${out()}"><feMergeNode in="${gl}"/><feMergeNode in="${src}"/></feMerge>`; last = `r${n - 1}`;
      }
    }
    if (dofR > 0.05) { prim += `<feGaussianBlur in="${last}" stdDeviation="${dofR.toFixed(2)}" result="${out()}"/>`; last = `r${n - 1}`; }
    if (!prim) return null;
    return `<filter id="${id}" x="-25%" y="-25%" width="150%" height="150%" color-interpolation-filters="${linear ? 'linearRGB' : 'sRGB'}">${prim}</filter>`;
  }

  // WP-36: light wrap. The planes behind are drawn again (a copy, blurred) over this plane, screened, through a mask
  // that keeps only a band just inside the plane's edges (its alpha minus its blurred alpha). No feImage: Chromium will
  // not read elements holding the player's cached raster layers into a filter
  function wrapDefs(pid, nd, W, H) {
    const r = nd.radius ?? 14, k = Math.max(0, nd.strength ?? 0.7), U = `filterUnits="userSpaceOnUse" x="${-W}" y="${-H}" width="${3 * W}" height="${3 * H}"`;
    return `<filter id="${pid}-wedge" ${U} color-interpolation-filters="sRGB"><feGaussianBlur in="SourceAlpha" stdDeviation="${f2(r / 2)}" result="ab"/>`
      + `<feComposite in="SourceAlpha" in2="ab" operator="out" result="edge"/><feFlood flood-color="#fff"/><feComposite in2="edge" operator="in" result="w"/>`
      + `<feComponentTransfer in="w"><feFuncA type="linear" slope="${(2 * k).toFixed(3)}"/></feComponentTransfer></filter>`
      + `<filter id="${pid}-wblur" ${U} color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="${f2(r / 2)}"/></filter>`;
  }

  function maskFor(id, nd, W, H) {
    const sh = nd.shape || {}; let s = '';
    if (sh.ellipse) { const [cx, cy, rx, ry] = sh.ellipse; s = `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}"`; }
    else if (sh.rect) { const [x, y, w, h] = sh.rect; s = `<rect x="${x}" y="${y}" width="${w}" height="${h}"`; }
    else if (sh.path) s = `<path d="${String(sh.path).replace(/[^MLHVCSQTAZmlhvcsqtaz0-9.,\s-]/g, '')}"`;
    else return '';
    const fill = nd.invert ? '#000' : '#fff', bg = nd.invert ? '#fff' : '#000';
    const fe = nd.feather ? `<filter id="${id}-f" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="${nd.feather / 2}"/></filter>` : '';
    return `${fe}<mask id="${id}" maskUnits="userSpaceOnUse" x="${-W}" y="${-H}" width="${3 * W}" height="${3 * H}"><rect x="${-W}" y="${-H}" width="${3 * W}" height="${3 * H}" fill="${bg}"/>${s} fill="${fill}"${fe ? ` filter="url(#${id}-f)"` : ''}/></mask>`;
  }

  // ctx: {W, H, t, view: [cx, cy, z], stage: svg of the shot's own set/cast/props, planeInk: {plane: svg of cast members on it},
  //       drawSet(name, opts, t), overlay(item, t), tag: frame tag}
  function compose(sh, ctx) {
    const c = sh.comp || {}, W = ctx.W, H = ctx.H, t = ctx.t, tag = ctx.tag;
    ctx = { ...ctx, comp: c };
    const planes = (c.planes || []).map(p => at(p, t, ctx));
    if (!planes.some(p => p.id === 'stage')) planes.push({ id: 'stage', depth: 1 });
    const order = planes.map((p, i) => ({ ...p, i })).sort((a, b) => (b.depth ?? 1) - (a.depth ?? 1) || a.i - b.i);
    const focus = V(c.focus, t, ctx, 1), dof = V(c.dof, t, ctx, 0);
    const allNodes = (c.nodes || []).map(n => at(n, t, ctx));
    let defs = '', body = ''; const drawn = {};
    // WP-14: ctx.split "back" draws only what is behind the characters (the planes farther than the stage, and the
    // stage's own set), "front" only the planes nearer; another renderer draws the characters between the two passes
    const si = order.findIndex(p => p.id === 'stage');
    // WP-37 linear light: ctx.only draws one plane alone (no blend or opacity wrapper, no light wrap); each plane's blend
    // mode and opacity this frame go to ctx.info.blends, and the master composites the planes in linear light
    for (const p of order.filter((_, i) => (!ctx.split || (ctx.split === 'back' ? i <= si : i > si)) && (!ctx.only || order[i].id === ctx.only))) {
      const d = Math.max(0.05, p.depth ?? 1), pid = `comp-${p.id}-${tag}`;
      let content = '';
      if (p.id === 'stage') content = ctx.stage;
      if (p.set && ctx.drawSet) content += ctx.drawSet(p.set, p.set_opts || {}, t);
      content += (p.items || []).map((it, k) => item(it, t, `${p.id}-${tag}`, k, ctx)).join('');
      content += (ctx.planeInk || {})[p.id] || '';
      const nodes = allNodes.filter(n => n.plane === p.id);
      const fl = filterFor(`${pid}-fx`, nodes.filter(n => n.type !== 'mask' && n.type !== 'blend' && n.type !== 'lightwrap'), dof * Math.abs(1 / d - 1 / focus), !!c.linear);
      if (fl) defs += fl;
      const mk = nodes.find(n => n.type === 'mask'); const bl = nodes.find(n => n.type === 'blend');
      if (mk) defs += maskFor(`${pid}-mask`, mk, W, H);
      const inner = mk && !mk.screen ? `<g mask="url(#${pid}-mask)">${content}</g>` : content;   // a plane mask moves with its plane
      // a screen-locked plane (WP-42: a 3D render already framed by the shot camera) does not move with the 2D camera
      // WP-37 stereo: each eye sees the plane shifted by half the separation times (1/convergence - 1/depth): the plane
      // at the convergence depth sits on the screen, farther ones behind it, nearer ones in front (screen-locked planes too)
      const st = c.stereo || {}, eye = ctx.eye === 'left' ? -0.5 : ctx.eye === 'right' ? 0.5 : 0;
      const par = eye ? eye * V(st.separation, t, ctx, 24) * (1 / V(st.convergence, t, ctx, 1) - 1 / d) : 0;
      let g = `<g${p.screen ? '' : ` transform="${camFor(d, ctx.view, W, H, p.drift, t, c.zoom)}"`}${fl ? ` filter="url(#${pid}-fx)"` : ''}>${inner}</g>`;
      if (par) g = `<g transform="translate(${par.toFixed(3)} 0)">${g}</g>`;
      if (mk && mk.screen) g = `<g mask="url(#${pid}-mask)">${g}</g>`;                            // a screen mask stays put (a vignette)
      if (ctx.depthpass) {   // WP-37 depth pass: the plane's coverage in one flat colour that encodes its depth (no blends, no wrap)
        const dp = depthFill(d, W, H); defs += dp.def; g = `<g filter="url(#${dp.id})">${g}</g>`; drawn[p.id] = g; body += g; continue;
      }
      if (ctx.info) (ctx.info.blends = ctx.info.blends || {})[p.id] = { mode: bl ? (bl.mode || 'normal') : 'normal', opacity: bl ? (bl.opacity ?? 1) : (p.opacity ?? 1), depth: d, lightwrap: !!nodes.find(n => n.type === 'lightwrap') };
      if (ctx.only) { drawn[p.id] = g; body += g; continue; }
      const lw = nodes.find(n => n.type === 'lightwrap');
      let wrap = '';
      if (lw) {   // the planes behind (or those named), as drawn so far, blurred and screened onto this plane's inner edges
        const from = lw.from || order.filter(q => (q.depth ?? 1) > d && drawn[q.id]).map(q => q.id);
        defs += wrapDefs(pid, lw, W, H) + `<mask id="${pid}-wmask" maskUnits="userSpaceOnUse" x="${-W}" y="${-H}" width="${3 * W}" height="${3 * H}"><g filter="url(#${pid}-wedge)">${g}</g></mask>`;
        wrap = `<g mask="url(#${pid}-wmask)" style="mix-blend-mode:screen"><g filter="url(#${pid}-wblur)">${from.map(id => drawn[id] || '').join('')}</g></g>`;
      }
      if (bl || p.opacity != null) g = `<g style="${bl ? `mix-blend-mode:${bl.mode || 'normal'}` : ''}" opacity="${bl ? (bl.opacity ?? 1) : p.opacity}">${g}</g>`;
      drawn[p.id] = g; body += g + wrap;
    }
    const roll = V(c.roll, t, ctx, 0);   // WP-36: camera roll about the frame centre
    if (roll) body = `<g transform="rotate(${(+roll).toFixed(3)} ${f2(W / 2)} ${f2(H / 2)})">${body}</g>`;
    return `<defs>${defs}</defs><g style="isolation:isolate">${body}</g>`;
  }
  root.COMP = { compose, camFor, value: V, compile, depthFill };
})(typeof window !== 'undefined' ? window : globalThis);
