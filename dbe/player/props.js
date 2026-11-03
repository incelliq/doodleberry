// Doodleberry props: where a prop is at time t, and how it is drawn (plan 1.2, 2.19, WP-09). Shared by the SVG player,
// the motion effects (fx.js) and the Node solvers (tools/physics/), so every one of them computes the same motion.
// Pure functions of time. Exposes window.PROPS.
//
// A prop (shots.json "props"[i]) moves by one of:
//   "attach": [[t, target], ...]  parents over time; a target is [x, y], {x, y}, or {cast, part, at} (a point on a
//             character). Each switch travels for `travel` s on a lifted arc, or as
//     "flight": "ballistic"  a true gravity arc: leaves the previous parent where it was at the key time and lands on
//                            this target where it is at "arrive" (line-relative times allowed upstream)
//     "drop": {"floor": y, "x": x, "e": 0.5, "roll": 0.6}  released at the key time: falls, bounces and rolls to rest
//   "track": {"t0", "fps", "frames": [[x, y, deg], ...], "contacts": [[t, x, y], ...]}  a baked simulation
//             (physics.solve, Rapier); after its last frame the prop holds. With "attach" too, the track takes over at t0.
// Drawing (all optional, WP-09):
//   "stretch": true | {"amount": 0.22, "max": 0.45, "v0": 500}  stretch along the velocity, squeeze across (area kept)
//   "squash":  true | {"amount": 0.32, "life": 0.2, "catch": 0.5}  squash on every contact, then wobble back
//   "smear":   true | {"min": 1.1, "color": "#..."}  a smear frame when the prop moves more than min * r in one frame
// ctx: {at(target, t) -> [x, y] | null, fps}: the world point of an attach target at any time (the caller evaluates
// characters at that time).
(function (root) {
  const INK = '#181e26', f1 = n => (+n).toFixed(1), f3 = n => (+n).toFixed(3);
  const clamp = (u, a = 0, b = 1) => Math.min(b, Math.max(a, u));
  const cfg = (v, d) => v === true ? d : v ? { ...d, ...v } : null;

  function dropSim(pr, from, d, t0, t) {   // fixed-step integration from the release; returns {pos, bounces, spin}
    const g = pr.gravity ?? 2600, r = pr.r || 34, floor = (d.floor ?? 1500) - r, e = d.e ?? 0.5, dt = 1 / 240;
    let x = from[0], y = from[1], vy = d.vy ?? 0;
    const tFall = Math.sqrt(Math.max(0, 2 * (floor - y) / g)) || 0.3;
    let vx = d.vx ?? (d.x != null ? (d.x - x) / (tFall + 0.35) : 0), spin = 0;
    const bounces = []; let tt = t0;
    while (tt + dt <= t) {
      vy += g * dt; x += vx * dt; y += vy * dt; tt += dt;
      if (y >= floor) { y = floor; if (vy > 60) bounces.push([tt, x, floor + r]); vy = vy > 60 ? -vy * e : 0; vx *= vy === 0 ? (1 - (d.roll_friction ?? 2.2) * dt) : (d.roll ?? 0.8); }
      spin += vx * dt / r * 57.3;
    }
    return { pos: [x, y], bounces, spin };
  }

  function trackAt(tr, t) {   // linear between baked samples (exact on them)
    const fr = tr.frames || []; if (!fr.length) return null;
    const u = (t - (tr.t0 || 0)) * (tr.fps || 60), i = Math.floor(u);
    if (i < 0) return fr[0]; if (i >= fr.length - 1) return fr[fr.length - 1];
    const a = fr[i], b = fr[i + 1], k = u - i; let da = b[2] - a[2]; while (da > 180) da -= 360; while (da < -180) da += 360;
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + da * k];
  }

  const flightOf = (pr, keys, k) => { const sp = keys[k][1]; return sp && sp.arrive != null ? Math.max(0.05, sp.arrive - keys[k][0]) : (pr.travel ?? 0.35); };

  function pos(pr, t, ctx, info) {
    const tr = pr.track, keys = pr.attach || [];
    if (tr && (!keys.length || t >= (tr.t0 || 0))) {
      if (t < (tr.t0 || 0)) return null;
      const s = trackAt(tr, t); if (!s) return null;
      if (info) { info.spin = s[2]; info.bounces = (tr.contacts || []).filter(c => c[0] <= t); }
      return [s[0], s[1]];
    }
    if (!keys.length || t < keys[0][0]) return null;
    let k = 0; while (k + 1 < keys.length && keys[k + 1][0] <= t) k++;
    const at = (spec, tt) => Array.isArray(spec) ? spec : (spec && spec.x != null && !spec.drop ? [spec.x, spec.y] : ctx.at(spec, tt));
    const spec = keys[k][1], t0 = keys[k][0];
    if (spec && spec.drop && k > 0) {   // released from the previous parent where it was at the key time: fall, bounce, roll
      const from = at(keys[k - 1][1], t0); if (!from) return null;
      const sim = dropSim(pr, from, spec.drop, t0, t); if (info) { info.bounces = sim.bounces; info.spin = sim.spin; }
      return sim.pos;
    }
    const travel = flightOf(pr, keys, k), since = t - t0;
    if (k > 0 && since < travel && spec && spec.flight === 'ballistic') {   // exact projectile between the two contacts
      const from = at(keys[k - 1][1], t0), to = at(spec, t0 + travel); if (!from || !to) return to || from;
      const g = pr.gravity ?? 2600, T = travel, vy = (to[1] - from[1] - g * T * T / 2) / T;
      return [from[0] + (to[0] - from[0]) * since / T, from[1] + vy * since + g * since * since / 2];
    }
    let p = at(spec, t);
    if (k > 0 && since < travel && p) {
      const from = at(keys[k - 1][1], t) || p, u = since / travel, e = u * u * (3 - 2 * u), lift = (pr.arc ?? 140) * 4 * u * (1 - u);
      p = [from[0] + (p[0] - from[0]) * e, from[1] + (p[1] - from[1]) * e - lift];
    }
    return p;
  }

  const H = 1 / 240;
  function velocity(pr, t, ctx) {
    const a = pos(pr, t - H, ctx), b = pos(pr, t, ctx);
    return a && b ? [(b[0] - a[0]) / H, (b[1] - a[1]) / H] : [0, 0];
  }

  // every contact up to tmax: arrivals at the end of a travel (catches), drop bounces, baked contacts. [t, x, y, kind]
  function contacts(pr, ctx, tmax) {
    const out = [], keys = pr.attach || [];
    for (let k = 1; k < keys.length; k++) {
      const sp = keys[k][1]; if (!sp || sp.drop) continue;
      const ta = keys[k][0] + flightOf(pr, keys, k); if (ta > tmax || (pr.track && ta >= (pr.track.t0 || 0))) continue;
      const p = pos(pr, ta, ctx); if (p) out.push([ta, p[0], p[1], 'catch']);
    }
    const last = keys.length ? keys[keys.length - 1] : null;
    if (last && last[1] && last[1].drop && keys.length > 1 && (!pr.track || last[0] < (pr.track.t0 || 0))) {
      const info = {}; pos(pr, tmax, ctx, info); for (const b of info.bounces || []) out.push([b[0], b[1], b[2], 'bounce']);
    }
    if (pr.track) for (const c of pr.track.contacts || []) if (c[0] <= tmax) out.push([c[0], c[1], c[2], 'hit']);
    return out.sort((a, b) => a[0] - b[0]);
  }

  // squash and stretch as one affine part: [angle of the axis (deg), scale along it, scale across it]
  function deform(pr, t, ctx, p) {
    const st = cfg(pr.stretch, { amount: 0.22, max: 0.45, v0: 500 }), sq = cfg(pr.squash, { amount: 0.32, life: 0.2, catch: 0.5 });
    if (!st && !sq) return null;
    if (sq) {
      const cs = contacts(pr, ctx, t).filter(c => t - c[0] >= 0 && t - c[0] < sq.life);
      if (cs.length) {
        const c = cs[cs.length - 1], u = (t - c[0]) / sq.life, v = velocity(pr, c[0] - H, ctx), sp = Math.hypot(v[0], v[1]);
        const amt = sq.amount * (c[3] === 'catch' ? sq.catch : 1) * clamp(sp / 1200, 0.25, 1);
        const a = amt * (1 - u) * (1 - u) * Math.cos(Math.PI * 1.5 * u);   // squash, overshoot to a stretch, settle
        const ang = sp > 1 ? Math.atan2(v[1], v[0]) * 57.2958 : 90;
        return [ang, 1 - a, 1 / (1 - a)];
      }
    }
    if (st) {
      const v = velocity(pr, t, ctx), sp = Math.hypot(v[0], v[1]); if (sp <= st.v0) return null;
      const k = clamp(st.amount * (sp - st.v0) / 1000, 0, st.max);
      return [Math.atan2(v[1], v[0]) * 57.2958, 1 + k, 1 / (1 + k)];
    }
    return null;
  }

  function body(pr) {
    const r = pr.r || 34;
    if (pr.svg) return pr.svg;
    if (pr.shape === 'box') { const [w, h] = pr.size || [2 * r, 2 * r];
      return `<rect x="${f1(-w / 2)}" y="${f1(-h / 2)}" width="${f1(w)}" height="${f1(h)}" rx="6" fill="${pr.color || '#e8603c'}" stroke="${INK}" stroke-width="5"/>` +
        `<path d="M${f1(-w / 2 + 8)} ${f1(-h / 2 + 10)} L${f1(w / 2 - 8)} ${f1(-h / 2 + 10)}" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity="0.5"/>`; }
    return `<circle r="${r}" fill="${pr.color || '#e8603c'}" stroke="${INK}" stroke-width="5"/>` +
      `<path d="M${-r} 0 Q0 ${r * 0.5} ${r} 0 M0 ${-r} Q${r * 0.45} 0 0 ${r}" fill="none" stroke="${INK}" stroke-width="3" opacity="0.55"/>`;
  }

  function smear(pr, t, ctx, p, spin) {   // a smear frame: a tapered streak back to where the prop was a frame ago
    const sm = cfg(pr.smear, { min: 1.1 }); if (!sm) return '';
    const fps = ctx.fps || 30, q = pos(pr, t - 1 / fps, ctx); if (!q) return '';
    const r = pr.r || 34, dx = p[0] - q[0], dy = p[1] - q[1], d = Math.hypot(dx, dy); if (d < sm.min * r) return '';
    const nx = -dy / d, ny = dx / d, tail = [q[0] - dx * 0.25, q[1] - dy * 0.25], w0 = r * 0.92, w1 = r * 0.3;
    const pts = [[p[0] + nx * w0, p[1] + ny * w0], [tail[0] + nx * w1, tail[1] + ny * w1], [tail[0] - nx * w1, tail[1] - ny * w1], [p[0] - nx * w0, p[1] - ny * w0]];
    let s = `<path d="M${pts.map(v => f1(v[0]) + ' ' + f1(v[1])).join(' L')} Z" fill="${sm.color || pr.color || '#e8603c'}" stroke="${INK}" stroke-width="3" stroke-linejoin="round" opacity="0.55"/>`;
    for (const k of [0.33, 0.66]) {   // multiples: ghost copies along the streak
      const g = [p[0] - dx * k, p[1] - dy * k];
      s += `<g transform="translate(${f1(g[0])} ${f1(g[1])}) rotate(${f1(spin)})" opacity="${f3(0.4 * (1 - k))}">${body(pr)}</g>`;
    }
    return s;
  }

  function svg(pr, t, ctx) {
    const info = {}, p = pos(pr, t, ctx, info);
    if (!p) return '';
    const spin = info.spin != null ? info.spin : (pr.spin ? t * pr.spin : 0), df = deform(pr, t, ctx, p);
    const sc = df ? ` rotate(${f1(df[0])}) scale(${f3(df[1])} ${f3(df[2])}) rotate(${f1(-df[0])})` : '';
    return smear(pr, t, ctx, p, spin) + `<g transform="translate(${f1(p[0])} ${f1(p[1])})${sc} rotate(${f1(spin)})">${body(pr)}</g>`;
  }

  root.PROPS = { pos, svg, velocity, contacts, deform, dropSim, trackAt };
})(typeof window !== 'undefined' ? window : globalThis);
