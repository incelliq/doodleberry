// The map board (WP-16): a framed map on a wall, drawn from Natural Earth (sets/maps/<name>.js, made by
// tools/mapboard/make.mjs with d3-geo's Natural Earth 1 projection). A pure function of time: highlights fade in,
// pins drop, routes draw themselves and the view can move between keyed boxes. Registers SETS.map and MAPS.project.
//
// set_opts: {map: "world" | "south-asia" | ..., view: [lon0, lat0, lon1, lat1] or [{t, view}], full: bool,
//   title, highlight: [{country, colour, start}], pins: [{lon, lat, label, start, colour}],
//   routes: [{from: [lon, lat] | country, to, start, dur, colour}], boxes: [{lon0, lat0, lon1, lat1, label, start, colour}],
//   labels: [{country | lon, lat, text, start}], land, sea, wall}
// Times are film seconds, like every set's: write them as line references ("hook.start+1.2"), which the shot loader
// resolves, so a re-voiced or translated film keeps the map in step (`at` is accepted as a plain number too). Labels are text, so they translate with the film (WP-25).
(function (root) {
  const INK = '#24160e', f1 = n => (+n).toFixed(1), esc = s => String(s).replace(/[<&]/g, '');
  const MAPS = root.MAPS = root.MAPS || {};
  const R = Math.PI / 180;
  // d3-geo geoNaturalEarth1Raw, rotated by the map's centre longitude, scaled by k, y down (as d3 writes it)
  MAPS.project = (m, lon, lat) => {
    let l = (lon + m.rotate[0]) * R; while (l > Math.PI) l -= 2 * Math.PI; while (l < -Math.PI) l += 2 * Math.PI;
    const p = lat * R, p2 = p * p, p4 = p2 * p2;
    const x = l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)));
    const y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)));
    return [m.k * x, -m.k * y];
  };
  const AT = x => x.start ?? x.at;   // "start" (resolved from line references like "hook.start+1" by the shot loader) or "at", film seconds
  const ease = u => u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u);
  const ramp = (t, at, d = 0.5) => at == null ? 1 : ease((t - at) / d);
  // the projected box around a lon/lat box (its edges sampled: Natural Earth bends the meridians)
  const pbox = (m, [l0, a0, l1, a1]) => {
    const xs = [], ys = [];
    for (let i = 0; i <= 10; i++) for (const [lo, la] of [[l0 + (l1 - l0) * i / 10, a0], [l0 + (l1 - l0) * i / 10, a1], [l0, a0 + (a1 - a0) * i / 10], [l1, a0 + (a1 - a0) * i / 10]]) {
      const [x, y] = MAPS.project(m, lo, la); xs.push(x); ys.push(y); }
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  };
  const viewAt = (m, v, t) => {
    if (!v) return m.box || pbox(m, [-180 - m.rotate[0], -60, 180 - m.rotate[0], 84]);
    if (!Array.isArray(v[0]) && typeof v[0] === 'number') return pbox(m, v);
    const ks = v.map(k => ({ t: k.t || 0, b: pbox(m, k.view) }));   // keyed views: eased between keys
    if (t <= ks[0].t) return ks[0].b;
    for (let i = 1; i < ks.length; i++) if (t < ks[i].t) { const u = ease((t - ks[i - 1].t) / (ks[i].t - ks[i - 1].t)); return ks[i - 1].b.map((a, j) => a + (ks[i].b[j] - a) * u); }
    return ks[ks.length - 1].b;
  };
  const where = (m, p) => typeof p === 'string' ? ((m.countries[p] || {}).c || null) : MAPS.project(m, p[0], p[1]);

  const draw = (t, o, W, H, fl) => {
    const m = MAPS[o.map || 'world'];
    const xf = (root.SCRIPT_FONTS || []).map(f => `'${f.family}'`).join(',') || "'Noto Sans Sinhala'", FONT = `'Fredoka',${xf},sans-serif`;
    let s = `<rect width="${W}" height="${H}" fill="${o.wall || '#e7dfcc'}"/>`;
    // the board: above the floor, characters stand in front of it; full: the whole frame
    const land = W > H, pad = o.full ? 0 : Math.round(Math.min(W, H) * 0.045);
    const bx = o.full ? 0 : land ? W * 0.04 : pad, by = o.full ? 0 : land ? H * 0.07 : H * 0.075;
    const bw = o.full ? W : land ? W * 0.6 : W - 2 * pad, bh = o.full ? H : land ? fl - by - H * 0.06 : fl - by - 240;
    if (!o.full) s += `<rect x="${f1(bx - 18)}" y="${f1(by - 18)}" width="${f1(bw + 36)}" height="${f1(bh + 36)}" rx="10" fill="#9a6b43" stroke="${INK}" stroke-width="6"/>`;
    s += `<rect x="${f1(bx)}" y="${f1(by)}" width="${f1(bw)}" height="${f1(bh)}" fill="${o.sea || '#cfe5ef'}"/>`;
    if (!m) return s + `<text x="${f1(bx + bw / 2)}" y="${f1(by + bh / 2)}" text-anchor="middle" font-family="${FONT}" font-size="40" fill="${INK}">map ${esc(o.map || 'world')} not loaded</text>` + floor(W, H, fl, o);
    // fit the whole view into the board, centred (the map around it fills the rest); fit: "cover" fills the board
    const v = viewAt(m, o.view, t), vw = v[2] - v[0], vh = v[3] - v[1];
    const sc = (o.fit === 'cover' ? Math.max : Math.min)(bw / vw, bh / vh), ox = bx + bw / 2 - (v[0] + vw / 2) * sc, oy = by + bh / 2 - (v[1] + vh / 2) * sc;
    const P = (x, y) => [ox + x * sc, oy + y * sc], lw = px => f1(px / sc);
    const clip = `mapclip${Math.round(t * 1000)}`;
    s += `<defs><clipPath id="${clip}"><rect x="${f1(bx)}" y="${f1(by)}" width="${f1(bw)}" height="${f1(bh)}"/></clipPath></defs><g clip-path="url(#${clip})">`;
    // a little life on the sea, so a held map never freezes: faint swell marks drifting east
    for (let i = 0; i < 14; i++) { const x = bx + ((i * 263 + t * 9) % (bw + 120)) - 60, y = by + 40 + (i * 157) % Math.max(60, bh - 80);
      s += `<path d="M${f1(x)} ${f1(y)} q14 -8 28 0 t28 0" fill="none" stroke="#a9cfe0" stroke-width="3" opacity="0.7"/>`; }
    s += `<g transform="translate(${f1(ox)} ${f1(oy)}) scale(${sc.toFixed(5)})">`;
    s += `<path d="${m.grat}" fill="none" stroke="#b8d6e4" stroke-width="${lw(1.5)}"/>`;
    const hi = {}; for (const h of (o.highlight || [])) hi[h.country] = h;
    for (const [nm, c] of Object.entries(m.countries)) s += `<path d="${c.d}" fill="${o.land || '#f1e6c8'}"/>`;
    for (const [nm, h] of Object.entries(hi)) { const c = m.countries[nm]; if (!c) continue; const a = ramp(t, AT(h));
      if (a > 0) s += `<path d="${c.d}" fill="${h.colour || '#f2a33a'}" opacity="${a.toFixed(3)}"/>`; }
    s += `<path d="${m.borders}" fill="none" stroke="#8c7a5c" stroke-width="${lw(2)}" stroke-linejoin="round"/>`;
    s += `<path d="${m.coast}" fill="none" stroke="${INK}" stroke-width="${lw(3.5)}" stroke-linejoin="round"/></g>`;
    // boxes (a region of ocean, say): dashed outline and a soft fill
    for (const b of (o.boxes || [])) { const a = ramp(t, AT(b)); if (a <= 0) continue; const pts = [];
      for (let i = 0; i <= 12; i++) pts.push([b.lon0 + (b.lon1 - b.lon0) * i / 12, b.lat1]);
      for (let i = 0; i <= 12; i++) pts.push([b.lon1 - (b.lon1 - b.lon0) * i / 12, b.lat0]);
      const d = pts.map(([lo, la], i) => { const [x, y] = P(...MAPS.project(m, lo, la)); return `${i ? 'L' : 'M'}${f1(x)} ${f1(y)}`; }).join('') + 'Z';
      s += `<path d="${d}" fill="${b.colour || '#e05a4f'}" fill-opacity="${(0.28 * a).toFixed(3)}" stroke="${b.colour || '#e05a4f'}" stroke-width="5" stroke-dasharray="14 9" opacity="${a.toFixed(3)}"/>`;
      if (b.label) { const [x, y] = P(...MAPS.project(m, (b.lon0 + b.lon1) / 2, b.lat1)); s += label(x, y - 18, b.label, a, FONT, 34); } }
    // routes: a curve that draws itself from `at` over `dur`, with a head
    for (const r of (o.routes || [])) { const a0 = where(m, r.from), a1 = where(m, r.to); if (!a0 || !a1) continue;
      const u = AT(r) == null ? 1 : Math.max(0, Math.min(1, (t - AT(r)) / (r.dur || 1.5))); if (u <= 0) continue;
      const [x0, y0] = P(...a0), [x1, y1] = P(...a1), dx = x1 - x0, dy = y1 - y0, bend = r.bend == null ? 0.22 : r.bend;
      const cx = (x0 + x1) / 2 + dy * bend, cy = (y0 + y1) / 2 - dx * bend, q = k => [(1 - k) ** 2 * x0 + 2 * (1 - k) * k * cx + k * k * x1, (1 - k) ** 2 * y0 + 2 * (1 - k) * k * cy + k * k * y1];
      const n = Math.max(2, Math.round(40 * u)), pts = []; for (let i = 0; i <= n; i++) pts.push(q(u * i / n));
      s += `<path d="${pts.map(([x, y], i) => `${i ? 'L' : 'M'}${f1(x)} ${f1(y)}`).join('')}" fill="none" stroke="${r.colour || '#5a3fc0'}" stroke-width="8" stroke-linecap="round" stroke-dasharray="20 14"/>`;
      const [hx, hy] = pts[n], [px, py] = pts[n - 1], ang = Math.atan2(hy - py, hx - px) * 180 / Math.PI;
      s += `<path d="M0 0 L-30 -15 L-30 15 Z" transform="translate(${f1(hx)} ${f1(hy)}) rotate(${f1(ang)})" fill="${r.colour || '#5a3fc0'}" stroke="${INK}" stroke-width="3"/>`; }
    // country labels
    for (const l of (o.labels || [])) { const a = ramp(t, AT(l)); if (a <= 0) continue; const p = l.country ? where(m, l.country) : MAPS.project(m, l.lon, l.lat); if (!p) continue;
      const [x, y] = P(...p); s += label(x, y, l.text || l.country, a, FONT, l.size || 34); }
    // pins: drop in from above with a small bounce
    for (const p of (o.pins || [])) { const k = AT(p) == null ? 1 : Math.max(0, Math.min(1, (t - AT(p)) / 0.45)); if (k <= 0) continue;
      const [x, y] = P(...MAPS.project(m, p.lon, p.lat)), dropY = k < 0.7 ? -120 * (1 - k / 0.7) ** 2 : -14 * Math.sin((k - 0.7) / 0.3 * Math.PI);
      const c = p.colour || '#e05a4f';
      s += `<ellipse cx="${f1(x)}" cy="${f1(y)}" rx="12" ry="5" fill="#000" opacity="${(0.25 * k).toFixed(3)}"/>`;
      s += `<g transform="translate(${f1(x)} ${f1(y + dropY)})"><path d="M0 0 C-6 -16 -24 -30 -24 -50 A24 24 0 1 1 24 -50 C24 -30 6 -16 0 0 Z" fill="${c}" stroke="${INK}" stroke-width="4"/><circle cx="0" cy="-50" r="9" fill="#fff"/></g>`;
      if (p.label && k >= 1) s += label(x, y - 96, p.label, ramp(t, (AT(p) || 0) + 0.45, 0.3), FONT, p.size || 36); }
    s += `</g>`;
    if (o.title) s += `<rect x="${f1(bx + bw * 0.12)}" y="${f1(by - 34)}" width="${f1(bw * 0.76)}" height="78" rx="8" fill="#fffaf0" stroke="${INK}" stroke-width="5"/>` +
      `<text x="${f1(bx + bw / 2)}" y="${f1(by + 20)}" text-anchor="middle" font-family="${FONT}" font-weight="700" font-size="44" fill="${INK}">${esc(o.title)}</text>`;
    return s + (o.full ? '' : floor(W, H, fl, o));
  };
  const label = (x, y, txt, a, font, fs) => `<text x="${f1(x)}" y="${f1(y)}" text-anchor="middle" font-family="${font}" font-weight="700" font-size="${fs}" fill="${INK}" stroke="#fffaf0" stroke-width="${f1(fs * 0.22)}" paint-order="stroke" opacity="${a.toFixed(3)}">${esc(txt)}</text>`;
  const floor = (W, H, fl, o) => `<rect y="${fl}" width="${W}" height="${H - fl}" fill="${o.floor || '#c9b79a'}"/><path d="M0 ${fl} L${W} ${fl}" stroke="${INK}" stroke-width="5"/>`;

  const SETS = root.SETS = root.SETS || {};
  const frac = 0.8;
  SETS.map = { floor: Math.round(1920 * frac), frac, draw: (t, o = {}, W = 1080, H = 1920) => draw(t, o || {}, W, H, Math.round(H * frac)),
    floorAt: (W = 1080, H = 1920) => Math.round(H * frac) };
})(typeof window !== 'undefined' ? window : globalThis);
