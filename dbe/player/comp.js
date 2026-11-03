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
//       {"id": "front", "depth": 0.6, "items": [...]}     // cast entries with "plane": "front" are drawn here
//     ],
//     "focus": 1, "dof": 3,                // blur px per unit of |1/depth - 1/focus| (0: everything sharp)
//     "nodes": [
//       {"type": "grade", "plane": "sky", "brightness": 0.9, "contrast": 1.1, "saturation": 0.8, "tint": "#3050a0", "tint_amount": 0.15},
//       {"type": "blur", "plane": "hills", "radius": 2},
//       {"type": "glow", "plane": "front", "radius": 16, "strength": 0.9, "colour": "#ffb060"},
//       {"type": "mask", "plane": "sky", "shape": {"ellipse": [540, 700, 700, 600]}, "feather": 80, "invert": false, "screen": false},
//       {"type": "blend", "plane": "fog", "mode": "screen", "opacity": 0.6}
//     ]
//   }
//
// Parallax: a plane at depth d follows the camera by 1/d (the stage, d = 1, moves with it; far planes move less, near
// planes more), and zooms by 1 + (zoom - 1) / d. "drift" moves a plane on its own (px/s). Ids start with "comp-": the
// AI-look lint treats them as deliberate compositing, not generic effects.
(function (root) {
  const f2 = v => (+v).toFixed(2);
  const SAFE = s => String(s).replace(/<\/?(script|foreignObject|iframe)[^>]*>/gi, '').replace(/\son\w+\s*=/gi, ' data-x=');
  function hex(c) { const s = String(c || '#000').replace('#', ''); const v = s.length === 3 ? s.split('').map(x => x + x).join('') : s; return [0, 2, 4].map(i => parseInt(v.slice(i, i + 2), 16) / 255); }

  function item(it, t, tag, k, ctx) {
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
    return ctx.overlay ? ctx.overlay(it, t) : '';
  }

  function camFor(d, view, W, H, drift, t) {
    const [cx, cy, z] = view, zp = 1 + (z - 1) / d;
    const px = W / 2 + (cx - W / 2) / d - (drift ? drift[0] * t : 0), py = H / 2 + (cy - H / 2) / d - (drift ? drift[1] * t : 0);
    return `translate(${f2(W / 2)} ${f2(H / 2)}) scale(${zp.toFixed(4)}) translate(${f2(-px)} ${f2(-py)})`;
  }

  function filterFor(id, nodes, dofR) {
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
    return `<filter id="${id}" x="-25%" y="-25%" width="150%" height="150%" color-interpolation-filters="sRGB">${prim}</filter>`;
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
    const planes = (c.planes || []).slice();
    if (!planes.some(p => p.id === 'stage')) planes.push({ id: 'stage', depth: 1 });
    const order = planes.map((p, i) => ({ ...p, i })).sort((a, b) => (b.depth ?? 1) - (a.depth ?? 1) || a.i - b.i);
    const focus = c.focus ?? 1, dof = c.dof ?? 0;
    let defs = '', body = '';
    for (const p of order) {
      const d = Math.max(0.05, p.depth ?? 1), pid = `comp-${p.id}-${tag}`;
      let content = '';
      if (p.id === 'stage') content = ctx.stage;
      if (p.set && ctx.drawSet) content += ctx.drawSet(p.set, p.set_opts || {}, t);
      content += (p.items || []).map((it, k) => item(it, t, `${p.id}-${tag}`, k, ctx)).join('');
      content += (ctx.planeInk || {})[p.id] || '';
      const nodes = (c.nodes || []).filter(n => n.plane === p.id);
      const fl = filterFor(`${pid}-fx`, nodes.filter(n => n.type !== 'mask' && n.type !== 'blend'), dof * Math.abs(1 / d - 1 / focus));
      if (fl) defs += fl;
      const mk = nodes.find(n => n.type === 'mask'); const bl = nodes.find(n => n.type === 'blend');
      if (mk) defs += maskFor(`${pid}-mask`, mk, W, H);
      const inner = mk && !mk.screen ? `<g mask="url(#${pid}-mask)">${content}</g>` : content;   // a plane mask moves with its plane
      let g = `<g transform="${camFor(d, ctx.view, W, H, p.drift, t)}"${fl ? ` filter="url(#${pid}-fx)"` : ''}>${inner}</g>`;
      if (mk && mk.screen) g = `<g mask="url(#${pid}-mask)">${g}</g>`;                            // a screen mask stays put (a vignette)
      if (bl || p.opacity != null) g = `<g style="${bl ? `mix-blend-mode:${bl.mode || 'normal'}` : ''}" opacity="${bl ? (bl.opacity ?? 1) : p.opacity}">${g}</g>`;
      body += g;
    }
    return `<defs>${defs}</defs><g style="isolation:isolate">${body}</g>`;
  }
  root.COMP = { compose, camFor };
})(typeof window !== 'undefined' ? window : globalThis);
