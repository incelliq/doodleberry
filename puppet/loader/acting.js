// Doodleberry acting layer: turns a timeline into a puppet pose at time t.
// Two-bone IK with targets and pins, deterministic springs, pose presets and blending, action clips on a
// nonlinear (NLA) stack, viseme lip-sync, blinks and gaze. Pure functions of t. Needs puppet.js. Exposes `Acting`.
//
//   const pose = Acting.evaluate(puppet, {
//     clips: [{ clip: 'walk', start: 0, weight: 1 }, { clip: 'talk_beat', start: 2, additive: true }],
//     poses: [[0, 'neutral'], [3, 'arms_crossed']],     // preset keys (blended over `poseBlend` s)
//     visemes: [[0.4, 'small'], [0.44, 'wide'], ...],    // from timing.json "visemes"[speaker]
//     look: [[0, [1, 0]], [4, [-1, 0.3]]],               // gaze keys
//     ik: { arm_R: [[1, [460, 420]]] },                  // reach targets in artboard space over time (a null key lets go)
//     ik_bend: { arm_L: 1 },                             // which way an elbow or knee bends (default from LIMBS)
//     ik_weight: { arm_R: [[2, 0], [2.4, 1]] },          // IK/FK blend per limb: 0 = the clips' pose, 1 = the reach target
//     lookat: [{part: 'head', target: [x, y] | {cast, part}, limit: 30, start, end, ease: 0.3}],   // a window eases in and out
//     scales: { forearm_R: [[1, 1], [1.2, 1.3]] },       // v0.9 squash and stretch per part: k (along its rest axis, area kept) or [sx, sy]
//     ik_stretch: { arm_R: 1.4 },                        // v0.9 stretchy limbs: past full reach the bones stretch up to 1.4x
//     copy_rotation: [{ part: 'tail', from: 'hip', factor: -0.5 }],   // v0.9 a part copies another's angle
//     z: [[0, {}], [2, { arm_R: 30 }]],                   // v0.9 layer order keys (per-pose z-order)
//     pins: {...}, travel: {path: {...}},                 // planted feet stay put while the root walks a path (WP-11)
//     pins: { foot_L: 'auto', foot_R: 'auto' },          // keep planted feet planted during walks
//     springs: true,                                     // hair/tie/coat follow-through (from puppet.springs)
//     blinks: [t, ...], blink: false,                   // scripted blinks; false turns off automatic blinking
//   }, t, CLIPS);
(function (root) {
  const P = root.Puppet;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const smooth = k => k * k * (3 - 2 * k);
  const deg = r => (r * 180) / Math.PI;
  const angOf = m => Math.atan2(m[1], m[0]);

  // ---------- keyframes ----------
  function sampleKeys(keys, t, loopDur) {
    if (!keys || !keys.length) return undefined;
    if (loopDur) t = ((t % loopDur) + loopDur) % loopDur;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      if (t <= keys[i][0]) {
        const [t0, v0] = keys[i - 1], [t1, v1] = keys[i];
        const k = smooth(clamp((t - t0) / (t1 - t0 || 1)));
        if (typeof v0 === 'number') return v0 + (v1 - v0) * k;
        if (Array.isArray(v0)) return Array.isArray(v1) ? v0.map((x, j) => x + (v1[j] - x) * k) : v0;
        return v0; // discrete values (swap names, contacts) hold until the next key
      }
    }
    if (loopDur) { const [t0, v0] = keys[keys.length - 1], [, v1] = keys[0], k = smooth(clamp((t - t0) / (loopDur - t0 || 1)));
      return typeof v0 === 'number' ? v0 + (v1 - v0) * k : Array.isArray(v0) ? v0.map((x, j) => x + (v1[j] - x) * k) : v0; }
    return keys[keys.length - 1][1];
  }

  // ---------- clips and the NLA stack ----------
  function sampleClip(clip, lt) {
    const loop = clip.loop ? clip.duration : 0;
    if (!loop) lt = clamp(lt, 0, clip.duration);
    const pose = { angles: {} };
    for (const [part, keys] of Object.entries(clip.tracks || {})) pose.angles[part] = sampleKeys(keys, lt, loop);
    if (clip.offset) pose.offset = sampleKeys(clip.offset, lt, loop);
    for (const [sw, keys] of Object.entries(clip.swaps || {})) pose[sw] = sampleKeys(keys, lt, loop);
    if (clip.contacts) pose.contacts = Object.fromEntries(Object.entries(clip.contacts).map(([f, keys]) => [f, sampleKeys(keys, lt, loop)]));
    if (clip.controls) pose.controls = Object.fromEntries(Object.entries(clip.controls).map(([c, keys]) => [c, sampleKeys(keys, lt, loop)]));   // v0.10: a clip may move a control (a head turn from Act it out)
    return pose;
  }
  // layers: [{clip, start, speed=1, weight=1, fadeIn=0.25, fadeOut=0.25, end, additive, base, phase=0 (clip seconds to start into the clip)}]
  // Blending per track: foreground clips average by weight among themselves and override the base layer ("idle", or
  // any layer with base: true) in proportion to their weight, so a gesture at weight 1 plays at full size over idle and
  // idle still fills every track the gesture does not touch. Additive layers add on top.
  function evalStack(layers, t, CLIPS) {
    const base = { angles: {} }, add = { angles: {} }, fg = {}, bg = {}, ctl = {};
    const offs = [];
    for (const L of layers || []) {
      const clip = typeof L.clip === 'string' ? CLIPS[L.clip] : L.clip; if (!clip) continue;
      const speed = L.speed || 1, lt = (t - (L.start || 0)) * speed + (L.phase || 0);
      const end = L.end ?? (clip.loop ? Infinity : (L.start || 0) + clip.duration / speed);
      const fi = L.fadeIn ?? clip.fadeIn ?? 0.25, fo = L.fadeOut ?? clip.fadeOut ?? 0.25;   // v0.8: a clip may set its own fades (drawn levels cut, never fade)
      if (t < (L.start || 0) || t > end + fo) continue;
      let w = (L.weight ?? 1) * (fi ? smooth(clamp((t - (L.start || 0)) / fi)) : 1) * (isFinite(end) && fo ? 1 - smooth(clamp((t - end) / fo)) : 1);
      if (w <= 0) continue;
      const s = sampleClip(clip, lt), g = L.gain ?? 1;   // gain scales the clip's motion (calmer or bigger acting)
      if (s.controls) { for (const [c, v] of Object.entries(s.controls)) if (v != null) ctl[c] = (ctl[c] || 0) + v * w * g; delete s.controls; }   // v0.10: weighted like an additive layer
      if (L.additive) for (const [k, v] of Object.entries(s.angles)) add.angles[k] = (add.angles[k] || 0) + v * w * g;
      else { const acc = (L.base || L.clip === 'idle') ? bg : fg; for (const [k, v] of Object.entries(s.angles)) { const a = acc[k] || (acc[k] = [0, 0]); a[0] += v * w * g; a[1] += w; } }
      if (!L.additive) { if (s.offset) offs.push([g === 1 ? s.offset : s.offset.map(v => v * g), w]); for (const [k, v] of Object.entries(s)) if (k !== 'angles' && k !== 'offset' && w >= 0.5) base[k] = v; }
      else { if (s.offset) add.offset = [(add.offset || [0, 0])[0] + s.offset[0] * w, (add.offset || [0, 0])[1] + s.offset[1] * w];  // additive moves (hops) stack on the base
        for (const [k, v] of Object.entries(s)) if (k !== 'angles' && k !== 'offset' && w >= 0.5) add[k] = v; }
    }
    for (const k of new Set([...Object.keys(fg), ...Object.keys(bg)])) {
      const f = fg[k] || [0, 0], g2 = bg[k], fw = Math.min(1, f[1]), gv = g2 ? g2[0] / Math.max(1, g2[1]) : 0;
      base.angles[k] = f[0] / Math.max(1, f[1]) + gv * (1 - fw);   // under weight 1 the gesture cross-fades with the base
    }
    if (offs.length) { const ws = offs.reduce((a, [, w]) => a + w, 0); base.offset = [0, 1].map(i => offs.reduce((a, [o, w]) => a + o[i] * w, 0) / Math.max(1, ws)); }
    const out = { ...base, ...add, angles: { ...base.angles } };
    if (add.offset) out.offset = [(base.offset || [0, 0])[0] + add.offset[0], (base.offset || [0, 0])[1] + add.offset[1]];
    for (const [k, v] of Object.entries(add.angles)) out.angles[k] = (out.angles[k] || 0) + v;
    if (Object.keys(ctl).length) out.controls = ctl;
    return out;
  }

  // piecewise-linear drive curve: numbers and [x, y] interpolate; strings/null hold the key at or below v
  function driveAt(keys, v) {
    if (!keys || !keys.length) return null;
    if (v <= keys[0][0]) return keys[0][1];
    for (let i = 0; i < keys.length - 1; i++) { const [a, va] = keys[i], [b, vb] = keys[i + 1];
      if (v <= b) { if (typeof va === 'number' && typeof vb === 'number') return va + (vb - va) * (v - a) / (b - a);
        if (Array.isArray(va) && Array.isArray(vb)) return va.map((x, k) => x + (vb[k] - x) * (v - a) / (b - a));
        return v - a < b - v ? va : vb; } }
    return keys[keys.length - 1][1];
  }

  // ---------- presets ----------
  function blend(a, b, w) {
    const out = { ...(w < 0.5 ? a : b), angles: {} };
    const keys = new Set([...Object.keys(a.angles || {}), ...Object.keys(b.angles || {})]);
    for (const k of keys) out.angles[k] = ((a.angles || {})[k] || 0) * (1 - w) + ((b.angles || {})[k] || 0) * w;
    return out;
  }
  function presetAt(puppet, keys, t, dur = 0.4, PRESETS = {}) {
    if (!keys || !keys.length) return null;
    const get = n => (puppet.poses || {})[n] || PRESETS[n] || { angles: {} };
    let i = 0; for (let j = 0; j < keys.length; j++) if (t >= keys[j][0]) i = j;
    const cur = get(keys[i][1]); if (i === 0 && t < keys[0][0]) return get(keys[0][1]);
    const prev = i > 0 ? get(keys[i - 1][1]) : cur;
    return blend(prev, cur, smooth(clamp((t - keys[i][0]) / dur)));
  }

  // ---------- two-bone IK ----------
  // Solve upper/lower angles so the end joint reaches `target` (artboard space). bend: +1 / -1 picks the elbow side.
  function ik2(puppet, pose, upper, lower, end, target, bend = 1) {
    puppet = P.inView(puppet, pose.view);
    const parts = puppet.parts, M = P.matrices(puppet, pose);
    const parent = parts[upper].parent, Mp = parent ? M[parent] : [1, 0, 0, 1, 0, 0];
    const pu = parts[upper].pivot, pl = parts[lower].pivot, pe = parts[end].pivot;
    const S = [Mp[0] * pu[0] + Mp[2] * pu[1] + Mp[4], Mp[1] * pu[0] + Mp[3] * pu[1] + Mp[5]];
    const sc = id => { const v = pose.scales && pose.scales[id]; return v == null ? [1, 1] : Array.isArray(v) ? v : [v, v]; }, su = sc(upper), sl = sc(lower);
    const vU = [(pl[0] - pu[0]) * su[0], (pl[1] - pu[1]) * su[1]], vL = [(pe[0] - pl[0]) * sl[0], (pe[1] - pl[1]) * sl[1]];   // v0.9: stretched bones
    const gr = id => { let k = 1; for (let q = id; q && parts[q]; q = parts[q].parent) k *= +((pose.grow || {})[q] ?? 1); return k; };   // v0.11: grown bones reach further
    const L1 = Math.hypot(vU[0], vU[1]) * gr(upper), L2 = Math.hypot(vL[0], vL[1]) * gr(lower);
    const dx = target[0] - S[0], dy = target[1] - S[1];
    const d = clamp(Math.hypot(dx, dy), Math.abs(L1 - L2) + 1e-3, L1 + L2 - 1e-3);
    const a = Math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1));
    const b = Math.acos(clamp((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2), -1, 1));
    const upW = Math.atan2(dy, dx) - bend * a, loW = upW + bend * (Math.PI - b);
    const r1 = Math.atan2(vU[1], vU[0]), r2 = Math.atan2(vL[1], vL[0]);
    const pW = angOf(Mp);
    return { [upper]: deg(upW - pW - r1), [lower]: deg(loW - upW - (r2 - r1)) };
  }
  const LIMBS = { arm_L: ['upperarm_L', 'forearm_L', 'hand_L', -1], arm_R: ['upperarm_R', 'forearm_R', 'hand_R', -1], leg_L: ['thigh_L', 'shin_L', 'foot_L', 1], leg_R: ['thigh_R', 'shin_R', 'foot_R', 1] };

  // ---------- springs (deterministic: re-simulated over a fixed window ending at t) ----------
  function lagged(fn, t, { freq = 2.2, damping = 0.35, window = 1.6, dt = 1 / 120 } = {}) {
    const w = 2 * Math.PI * freq; let x = fn(t - window), v = 0;
    for (let s = t - window; s < t; s += dt) { const target = fn(s); const a = -w * w * (x - target) - 2 * damping * w * v; v += a * dt; x += v * dt; }
    return x;
  }

  // ---------- blinks ----------
  function blinkAt(t, seed = 0, every = 3.4) {
    const h = n => { const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return s - Math.floor(s); };
    const k = Math.floor(t / every), t0 = k * every + h(k) * every * 0.7, d = t - t0;
    return d >= 0 && d < 0.16 ? Math.sin((d / 0.16) * Math.PI) : 0;
  }

  // v0.5 puppet.acting.viseme_hold: mouth shapes shorter than `hold` seconds are folded into the previous one, so a
  // richly drawn mouth does not flicker every frame (animators hold mouths on twos or threes). Pure: same list, same result.
  const HELD = new WeakMap();
  function heldVisemes(vis, hold) {
    if (!hold) return vis;
    const memo = HELD.get(vis) || {}; if (memo[hold]) return memo[hold];
    const out = [];
    for (let i = 0; i < vis.length; i++) {
      const [ct, sh] = vis[i], next = i + 1 < vis.length ? vis[i + 1][0] : Infinity;
      if (out.length && (next - ct < hold) && sh !== 'closed') continue;   // too short: keep the previous shape (closures always land)
      if (out.length && out[out.length - 1][1] === sh) continue;
      if (out.length && ct - out[out.length - 1][0] < hold * 0.5) { out[out.length - 1] = [out[out.length - 1][0], sh]; continue; }
      out.push([ct, sh]);
    }
    memo[hold] = out; HELD.set(vis, memo); return out;
  }

  // ---------- v0.6: FABRIK chains (tails, tentacles, ropes) ----------
  // puppet.chains.<name> = {parts: [p1, ..., pn] (each the parent of the next), tip: [x, y] (artboard, end of the last bone),
  //   wave: {amp, freq, lag}}; timeline chains.<name> = [[t, [x, y]]] reach targets in artboard space.
  // The chain is solved in artboard space with the root fixed, then written back as local angle changes.
  function chainPoints(puppet, pose, ch) {
    const M = P.matrices(puppet, pose), ap = (m, q) => [m[0] * q[0] + m[2] * q[1] + m[4], m[1] * q[0] + m[3] * q[1] + m[5]];
    const pts = ch.parts.map(id => ap(M[puppet.parts[id].parent] || [1, 0, 0, 1, 0, 0], puppet.parts[id].pivot));
    pts.push(ap(M[ch.parts[ch.parts.length - 1]], ch.tip)); return pts;
  }
  function fabrik(pts, target, iters = 12) {
    const n = pts.length, len = pts.slice(1).map((q, i) => Math.hypot(q[0] - pts[i][0], q[1] - pts[i][1])), root = pts[0].slice();
    const total = len.reduce((a, b) => a + b, 0), P2 = pts.map(q => q.slice());
    const toward = (a, b, l) => { const d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-6; return [a[0] + (b[0] - a[0]) * l / d, a[1] + (b[1] - a[1]) * l / d]; };
    if (Math.hypot(target[0] - root[0], target[1] - root[1]) >= total) { for (let i = 1; i < n; i++) P2[i] = toward(P2[i - 1], target, len[i - 1]); return P2; }
    for (let it = 0; it < iters; it++) {
      P2[n - 1] = target.slice(); for (let i = n - 2; i >= 0; i--) P2[i] = toward(P2[i + 1], P2[i], len[i]);
      P2[0] = root.slice(); for (let i = 1; i < n; i++) P2[i] = toward(P2[i - 1], P2[i], len[i - 1]);
      if (Math.hypot(P2[n - 1][0] - target[0], P2[n - 1][1] - target[1]) < 0.5) break;
    }
    return P2;
  }
  function solveChain(puppet, pose, ch, target) {
    const cur = chainPoints(puppet, pose, ch), want = fabrik(cur, target);
    const ang = (a, b) => Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI, wrap = d => { while (d > 180) d -= 360; while (d < -180) d += 360; return d; };
    let prevD = 0;
    ch.parts.forEach((id, i) => { const d = wrap(ang(want[i], want[i + 1]) - ang(cur[i], cur[i + 1])); pose.angles[id] = (pose.angles[id] || 0) + wrap(d - prevD); prevD = d; });
  }

  // ---------- v0.6: emotion-aware mouth chart ----------
  // timeline emotion = [[t, "happy" | "sad" | "angry" | "surprised" | "worried" | "neutral"]]: the resting mouth (and any shape with
  // an "<shape>_<emotion>" drawing) follows the emotion, and brows follow it unless something else sets them.
  const MOUTH_CHARTS = { happy: { closed: 'smile' }, sad: { closed: 'frown' }, angry: { closed: 'frown' }, surprised: { closed: 'O' }, worried: { closed: 'small' } };
  const EMO_BROWS = { happy: 'raised', sad: 'worried', angry: 'angry', surprised: 'raised', worried: 'worried' };
  function emotionalMouth(puppet, shape, emo) {
    if (!emo || emo === 'neutral') return shape;
    const sw = (puppet.swaps || {}).mouth || {}, shapes = sw.shapes || {};
    if (shapes[shape + '_' + emo]) return shape + '_' + emo;
    const chart = (sw.charts || {})[emo] || MOUTH_CHARTS[emo] || {}, m = chart[shape];
    return m && shapes[m] ? m : shape;
  }

  // ---------- v0.6: animation principles (anticipation and overshoot) ----------
  // An unsharp mask in time on the clip pose: a(t) + k (a(t) - blur(a)(t)). Before a move starts the blur already
  // sees it coming and the joint dips the other way (anticipation); after it stops the joint carries past and settles
  // (overshoot). Pure: it samples the same clip stack at neighbouring times. principles = {snap: 0..1, window: s}.
  function principled(angles, sampleAt, t, pr) {
    const k = pr.snap ?? 0.35, w = pr.window ?? 0.14; if (!k) return angles;
    const offs = [-w, -w / 2, w / 2, w], wts = [1, 2, 2, 1], sm = offs.map(o => sampleAt(t + o)), out = { ...angles };
    for (const id of Object.keys(angles)) { let b = 3 * angles[id], tw = 3; sm.forEach((a, i) => { b += wts[i] * (a[id] ?? angles[id]); tw += wts[i]; }); out[id] = angles[id] + k * (angles[id] - b / tw); }
    return out;
  }

  // ---------- v0.8 walking along a path (WP-11) ----------
  // place.path = {points: [[x, y], ...] (frame px, a Catmull-Rom curve through them), start: t, speed: px/s | end: t,
  //               ease: s (speed up and slow down), s: scale | s_by_y: [y0, s0, y1, s1] (perspective), face: "auto" | 1 | -1}
  // pathAt(path, t) -> [x, y, s, flip]: the root at time t, at constant speed along the arc length; pure.
  const PATHS = new WeakMap();
  function pathTable(path) {
    let T = PATHS.get(path); if (T) return T;
    const P = path.points || [[0, 0]], pts = [];
    if (P.length < 2) pts.push(P[0] || [0, 0]);
    for (let i = 0; i < P.length - 1; i++) {
      const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
      for (let k = 0; k < 32; k++) { const u = k / 32, u2 = u * u, u3 = u2 * u;
        pts.push([0, 1].map(j => 0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u3))); }
    }
    if (P.length >= 2) pts.push(P[P.length - 1]);
    const len = [0]; for (let i = 1; i < pts.length; i++) len.push(len[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    T = { pts, len, L: len[len.length - 1] }; PATHS.set(path, T); return T;
  }
  function pathDist(path, t) {   // distance travelled at t (trapezoid speed profile with `ease` seconds at each end)
    const T = pathTable(path), st = path.start || 0, L = T.L;
    const dur = path.end != null ? Math.max(1e-3, path.end - st) : L / Math.max(1e-3, path.speed || 150);
    const e = Math.min(path.ease || 0, dur / 2), v = L / Math.max(1e-6, dur - e), u = clamp(t - st, 0, dur);
    if (!e) return L * u / dur;
    if (u < e) return v * u * u / (2 * e);
    if (u > dur - e) { const r = dur - u; return L - v * r * r / (2 * e); }
    return v * e / 2 + v * (u - e);
  }
  function pathAt(path, t) {
    const T = pathTable(path), d = pathDist(path, t), { pts, len } = T;
    let i = 1; while (i < len.length - 1 && len[i] < d) i++;
    const a = pts[i - 1] || pts[0], b = pts[i] || a, k = len[i] > len[i - 1] ? (d - len[i - 1]) / (len[i] - len[i - 1]) : 0;
    const x = a[0] + (b[0] - a[0]) * k, y = a[1] + (b[1] - a[1]) * k;
    let flip = path.face === 1 || path.face === -1 ? path.face : 1;
    if (path.face == null || path.face === 'auto') {   // face the way the path heads (looking back past flat bits)
      let j = Math.min(Math.max(i, 1), pts.length - 1); while (j > 1 && Math.abs(pts[j][0] - pts[j - 1][0]) < 1e-6) j--;
      let dx = pts[j][0] - pts[j - 1][0]; if (Math.abs(dx) < 1e-6) { let m = 1; while (m < pts.length - 1 && Math.abs(pts[m][0] - pts[0][0]) < 1e-6) m++; dx = pts[m][0] - pts[0][0]; }
      flip = dx < 0 ? -1 : 1;
    }
    let s = path.s ?? 1;
    if (path.s_by_y) { const [y0, s0, y1, s1] = path.s_by_y; s = s0 + (s1 - s0) * clamp((y - y0) / ((y1 - y0) || 1), -1, 2); }
    return [x, y, s, flip];
  }
  // where a cast entry stands at t: {x, y, s, flip}, keyed [[t, {...}]], or {path: {...}}
  function placeAt(pl, t) {
    if (!pl) return null;
    if (pl.path) return pathAt(pl.path, t);
    if (Array.isArray(pl)) return sampleKeys(pl.map(([k, v]) => [k, [v.x, v.y, v.s ?? 1, v.flip ?? 1]]), t);
    return [pl.x, pl.y, pl.s ?? 1, pl.flip ?? 1];
  }

  // when the current contact of a foot began: exact, from the dominant clip's contact keys (no stepping back)
  function contactStart(layers, t, foot, CLIPS) {
    let best = null;
    for (const L of layers || []) {
      if (L.additive) continue;
      const clip = typeof L.clip === 'string' ? CLIPS[L.clip] : L.clip; if (!clip || !clip.contacts || !clip.contacts[foot]) continue;
      const st = L.start || 0, speed = L.speed || 1, fi = L.fadeIn ?? clip.fadeIn ?? 0.25, fo = L.fadeOut ?? clip.fadeOut ?? 0.25;
      const end = L.end ?? (clip.loop ? Infinity : st + clip.duration / speed);
      if (t < st || t > end + fo) continue;
      const w = (L.weight ?? 1) * (fi ? smooth(clamp((t - st) / fi)) : 1) * (isFinite(end) && fo ? 1 - smooth(clamp((t - end) / fo)) : 1);
      if (w < 0.5) continue;
      const keys = clip.contacts[foot], loop = clip.loop ? clip.duration : 0, lt = (t - st) * speed + (L.phase || 0);
      const ph = loop ? ((lt % loop) + loop) % loop : clamp(lt, 0, clip.duration);
      let i = 0; while (i + 1 < keys.length && keys[i + 1][0] < ph) i++;
      if (!keys[i][1]) continue;
      let j = i, back = 0;
      for (let n = 0; n < keys.length; n++) {
        if (j > 0) { if (!keys[j - 1][1]) break; j--; }
        else if (loop && keys[keys.length - 1][1] && keys.length > 1) { j = keys.length - 1; back += loop; }
        else break;
      }
      const startPh = keys[j][0] - back, from = st + (fi ? fi / 2 : 0);
      best = Math.max(from, t - (ph - startPh) / speed);
    }
    return best;
  }

  // Targets that the caller resolves before evaluate (it knows where everyone stands): an IK key value or a look-at
  // target may be {x, y} (a frame point) or {cast, part, at} (a point on another character). toLocal(frame point)
  // gives this puppet's artboard point; worldOf(target, t) a frame point (null when unknown, which drops it).
  const isRef = v => v && typeof v === 'object' && !Array.isArray(v);
  function crossRefs(tl) {
    return Object.values(tl.ik || {}).some(keys => keys.some(([, v]) => isRef(v) && v.cast != null)) || [].concat(tl.lookat || []).some(la => isRef(la.target) && la.target.cast != null);
  }
  function resolveTargets(tl, t, toLocal, worldOf) {
    const out = { ...tl };
    const res = v => { if (!isRef(v)) return v; const w = v.cast != null ? worldOf(v, t) : [v.x, v.y]; return w ? toLocal(w) : null; };
    if (tl.ik) { out.ik = {}; for (const [limb, keys] of Object.entries(tl.ik)) { const r = keys.map(([k, v]) => [k, res(v)]); if (r.every(([, v]) => v == null || Array.isArray(v))) out.ik[limb] = r; } }
    if (tl.lookat) out.lookat = [].concat(tl.lookat).map(la => { if (la.target_local) return la; const tg = Array.isArray(la.target) ? toLocal(la.target) : res(la.target); return tg ? { ...la, target_local: tg } : null; }).filter(Boolean);
    return out;
  }

  // ---------- v0.9 squash and stretch per part ----------
  // a number k stretches a part along its rest axis (pivot to its first child, or down) and squeezes it across by
  // 1/sqrt(k) so its area is kept; [sx, sy] scales the rest axes directly
  function stretchOf(puppet, id, k) {
    if (Array.isArray(k)) return k;
    const parts = puppet.parts, part = parts[id]; if (!part) return [1, 1];
    const child = Object.entries(parts).find(([, c]) => c.parent === id);
    const v = child ? [child[1].pivot[0] - part.pivot[0], child[1].pivot[1] - part.pivot[1]] : [0, 1];
    const across = 1 / Math.sqrt(Math.max(1e-3, k));
    return Math.abs(v[1]) >= Math.abs(v[0]) ? [across, k] : [k, across];
  }
  // v0.9 drawing substitution driven by angle: swaps[sid].by_angle = {part, world: false, shapes: [[min, max, shape], ...]}
  function swapByAngle(puppet, pose) {
    for (const [sid, sw] of Object.entries(puppet.swaps || {})) {
      const ba = sw.by_angle; if (!ba || pose[sid] != null) continue;
      let a = (pose.angles || {})[ba.part] || 0;
      if (ba.world) { const M = P.matrices(puppet, pose)[ba.part]; if (M) a = angOf(M) * 57.2958; }
      while (a > 180) a -= 360; while (a <= -180) a += 360;
      const hit = (ba.shapes || []).find(([lo, hi]) => a >= lo && a < hi); if (hit) pose[sid] = hit[2];
    }
  }
  // v0.9 phoneme poses for the whole face: puppet.lipsync = {shape: {angles, shifts, scales}} follows the mouth shape,
  // cross-faded over `fade` s, so the jaw, cheeks and brows move with the words, not only the mouth drawing
  function lipsyncPose(puppet, tl, t, emo) {
    const ls = puppet.lipsync; if (!ls || !tl.visemes || !tl.visemes.length) return null;
    const fade = ls._fade ?? 0.06, held = heldVisemes(tl.visemes, tl.viseme_hold ?? (puppet.acting || {}).viseme_hold ?? 0);
    let cur = 'closed', prev = 'closed', t0 = -1e9;
    for (const [ct, sh] of held) { if (ct > t + 0.033) break; prev = cur; cur = sh; t0 = ct; }
    const w = clamp((t + 0.033 - t0) / fade), A = ls[prev] || {}, Bp = ls[cur] || {}, out = { angles: {}, shifts: {}, scales: {} };
    for (const k of ['angles', 'shifts', 'scales']) for (const id of new Set([...Object.keys(A[k] || {}), ...Object.keys(Bp[k] || {})])) {
      const a = (A[k] || {})[id], b = (Bp[k] || {})[id], z = k === 'scales' ? 1 : 0;
      const mix = (x, y) => (x ?? z) + ((y ?? z) - (x ?? z)) * w;
      out[k][id] = Array.isArray(a) || Array.isArray(b) ? [0, 1].map(j => mix((a || [z, z])[j], (b || [z, z])[j])) : mix(a, b);
    }
    return out;
  }

  const OWN = new WeakMap();
  function ownClips(puppet, CLIPS) { let m = OWN.get(puppet); if (!m || m.lib !== CLIPS) { m = { lib: CLIPS, all: { ...CLIPS, ...puppet.clips } }; OWN.set(puppet, m); } return m.all; }

  // ---------- evaluate everything at t ----------
  function evaluate(puppet, tl, t, CLIPS = {}, PRESETS = {}) {
    if (puppet.clips) CLIPS = ownClips(puppet, CLIPS);   // v0.7: a character's own clips (Rig Canvas recordings) win over the library
    const base = presetAt(puppet, tl.poses, t, tl.poseBlend || 0.4, PRESETS) || { angles: {} };
    const ac = puppet.acting || {};
    const layers = (ac.tempo || ac.fade || ac.energy) ? (tl.clips || []).map(L => ({ ...L, speed: (L.speed || 1) * (ac.tempo || 1), fadeIn: L.fadeIn ?? ac.fade, fadeOut: L.fadeOut ?? ac.fade,
      gain: (L.gain ?? 1) * (ac.energy ?? 1) * (L.clip === 'idle' ? (ac.idle ?? 1) : 1) })) : tl.clips;
    const stack = evalStack(layers, t, CLIPS);
    const pose = { ...base, ...stack, angles: { ...base.angles } };
    for (const [k, v] of Object.entries(stack.angles)) pose.angles[k] = (pose.angles[k] || 0) + v;
    const pr = tl.principles ?? ac.principles;
    if (pr) pose.angles = principled(pose.angles, s => { const b2 = presetAt(puppet, tl.poses, s, tl.poseBlend || 0.4, PRESETS) || { angles: {} }, s2 = evalStack(layers, s, CLIPS), a = { ...b2.angles };
      for (const [k, v] of Object.entries(s2.angles)) a[k] = (a[k] || 0) + v; return a; }, t, pr);
    const emo = tl.emotion ? sampleKeys(tl.emotion, t) : null;
    if (tl.visemes && tl.visemes.length && !pose.mouth) { let sh = 'closed'; for (const [ct, s] of heldVisemes(tl.visemes, tl.viseme_hold ?? (puppet.acting || {}).viseme_hold ?? 0)) { if (ct > t + 0.033) break; sh = s; } pose.mouth = emotionalMouth(puppet, sh, emo); }
    else if (emo && !pose.mouth) pose.mouth = emotionalMouth(puppet, 'closed', emo);
    if (emo && !pose.brows && EMO_BROWS[emo] && ((puppet.swaps || {}).brows || {}).shapes && puppet.swaps.brows.shapes[EMO_BROWS[emo]]) pose.brows = EMO_BROWS[emo];
    if (tl.look) pose.look = sampleKeys(tl.look, t);
    if (tl.view) { pose.view = sampleKeys(tl.view, t); for (const [ts] of tl.view.slice(1)) { const d = Math.abs(t - ts); if (d < 0.09) pose.squash = Math.min(pose.squash ?? 1, 1 - 0.35 * (1 - d / 0.09)); } }
    if (tl.blink !== false) pose.blink = Math.max(pose.blink || 0, blinkAt(t, tl.seed || 0));
    // scripted blinks (timed for comedy): half, closed, closed, half over a third of a second
    for (const b of tl.blinks || []) { const d = t - b; if (d >= 0 && d < 0.34) pose.blink = Math.max(pose.blink || 0, d < 0.085 || d >= 0.25 ? 0.45 : 0.95); }
    for (const [k, v] of Object.entries(tl.set || {})) pose[k] = v;
    // v0.4 controls (smart bones / driven keys): one value drives angles, shifts, swaps and layer order through key curves;
    // v0.10: the clips' control tracks add to the timeline's own keys
    const cvals = { ...(pose.controls || {}) }; delete pose.controls;
    for (const [name, keys] of Object.entries(tl.controls || {})) { const v = sampleKeys(keys, t); if (v != null) cvals[name] = (cvals[name] || 0) + v; }
    for (const [name, v] of Object.entries(cvals)) {
      const ctl = (puppet.controls || {})[name]; if (!ctl) continue;
      for (const dr of ctl.drives || []) {
        const val = driveAt(dr.keys, v); if (val == null) continue;
        const [kind, id] = dr.target.split('.');
        if (kind === 'angles') pose.angles[id] = (pose.angles[id] || 0) + val;
        else if (kind === 'shift') { pose.shifts = pose.shifts || {}; const o = pose.shifts[id] || [0, 0]; pose.shifts[id] = [o[0] + val[0], o[1] + val[1]]; }
        else if (kind === 'swap') pose[id] = val;
        else if (kind === 'z') { pose.z = pose.z || {}; pose.z[id] = val; }
        else if (kind === 'scale') { pose.scales = pose.scales || {}; pose.scales[id] = stretchOf(puppet, id, val); }
        else if (kind === 'grow') { pose.grow = { ...(pose.grow || {}), [id]: (pose.grow?.[id] ?? 1) * val }; }
      }
    }
    // v0.11: recursive scale keys (the part and everything below it)
    for (const [id, keys] of Object.entries(tl.grow || {})) { const v = sampleKeys(keys, t); if (v == null) continue; pose.grow = { ...(pose.grow || {}), [id]: (pose.grow?.[id] ?? 1) * v }; }
    // v0.9: per-part squash and stretch keys, layer order keys, whole-face phoneme poses
    for (const [id, keys] of Object.entries(tl.scales || {})) { const v = sampleKeys(keys, t); if (v == null) continue; pose.scales = { ...(pose.scales || {}), [id]: stretchOf(puppet, id, v) }; }
    if (tl.z) { const zv = sampleKeys(tl.z, t); if (zv) pose.z = { ...(pose.z || {}), ...zv }; }
    const lp = lipsyncPose(puppet, tl, t, emo);
    if (lp) {
      for (const [id, v] of Object.entries(lp.angles)) pose.angles[id] = (pose.angles[id] || 0) + v;
      for (const [id, v] of Object.entries(lp.shifts)) { pose.shifts = pose.shifts || {}; const o = pose.shifts[id] || [0, 0]; pose.shifts[id] = [o[0] + v[0], o[1] + v[1]]; }
      for (const [id, v] of Object.entries(lp.scales)) { pose.scales = pose.scales || {}; const o = stretchOf(puppet, id, pose.scales[id] ?? 1), n = stretchOf(puppet, id, v); pose.scales[id] = [o[0] * n[0], o[1] * n[1]]; }
    }
    // look-at constraint: rotate a part so its aim vector points at a target (artboard coordinates), clamped
    for (const la of [].concat(tl.lookat || [])) {
      const tgt = la.target_local || la.target; if (!Array.isArray(tgt) || !puppet.parts[la.part]) continue;
      const ez = la.ease ?? 0.3, win = (la.start != null ? smooth(clamp((t - la.start) / ez + 1)) : 1) * (la.end != null ? 1 - smooth(clamp((t - la.end) / ez)) : 1);
      const w = (la.weight ?? 1) * win, lim = la.limit ?? 30, part = puppet.parts[la.part]; if (w <= 0) continue;
      const M = P.matrices(puppet, pose), par = part.parent && M[part.parent];
      const pv = par ? [par[0] * part.pivot[0] + par[2] * part.pivot[1] + par[4], par[1] * part.pivot[0] + par[3] * part.pivot[1] + par[5]] : part.pivot;
      const aim = la.aim || [1, 0], cur = Math.atan2(aim[1], aim[0]) + (par ? Math.atan2(par[1], par[0]) : 0) + ((pose.angles[la.part] || 0) * Math.PI / 180);
      let d = (Math.atan2(tgt[1] - pv[1], tgt[0] - pv[0]) - cur) * 180 / Math.PI;
      while (d > 180) d -= 360; while (d < -180) d += 360;
      pose.angles[la.part] = (pose.angles[la.part] || 0) + Math.max(-lim, Math.min(lim, d)) * w;
    }
    // IK reach targets
    for (const [limb, keys] of Object.entries(tl.ik || {})) {
      const tgt = sampleKeys(keys, t); if (!Array.isArray(tgt) || !LIMBS[limb]) continue;   // unresolved targets are skipped
      const wk = (tl.ik_weight || {})[limb], w = wk ? clamp(sampleKeys(wk, t) ?? 1) : 1; if (w <= 0) continue;
      const [u, l, e, bend0] = LIMBS[limb], bend = (tl.ik_bend || {})[limb] ?? bend0;
      const mx = (tl.ik_stretch || {})[limb];
      if (mx && mx > 1) {   // v0.9 stretchy limbs: past full reach, both bones stretch (up to mx times) to touch the target
        const Mi = P.matrices(P.inView(puppet, pose.view), pose), par = puppet.parts[u].parent, Mp = par ? Mi[par] : [1, 0, 0, 1, 0, 0], pu = P.inView(puppet, pose.view).parts[u].pivot;
        const S = [Mp[0] * pu[0] + Mp[2] * pu[1] + Mp[4], Mp[1] * pu[0] + Mp[3] * pu[1] + Mp[5]], want = [tgt[0] - (pose.offset || [0, 0])[0], tgt[1] - (pose.offset || [0, 0])[1]];
        const vp = P.inView(puppet, pose.view).parts, reach = Math.hypot(vp[l].pivot[0] - pu[0], vp[l].pivot[1] - pu[1]) + Math.hypot(vp[e].pivot[0] - vp[l].pivot[0], vp[e].pivot[1] - vp[l].pivot[1]);
        const d = Math.hypot(want[0] - S[0], want[1] - S[1]) / (Math.hypot(Mp[0], Mp[1]) || 1);
        let k = clamp(d / reach * 1.0005, 1, mx);
        if (k > 1) { pose.scales = { ...(pose.scales || {}), [u]: stretchOf(puppet, u, k), [l]: stretchOf(puppet, l, k) };
          for (let it = 0; it < 2; it++) { const su = pose.scales[u], sl = pose.scales[l];   // the squeeze across shortens a slanted bone: correct k
            const len = Math.hypot((vp[l].pivot[0] - pu[0]) * su[0], (vp[l].pivot[1] - pu[1]) * su[1]) + Math.hypot((vp[e].pivot[0] - vp[l].pivot[0]) * sl[0], (vp[e].pivot[1] - vp[l].pivot[1]) * sl[1]);
            k = clamp(k * d * 1.0005 / len, 1, mx); pose.scales[u] = stretchOf(puppet, u, k); pose.scales[l] = stretchOf(puppet, l, k); } }
        else if (pose.scales) { delete pose.scales[u]; delete pose.scales[l]; }
      }
      const sol = ik2(puppet, pose, u, l, e, [tgt[0] - (pose.offset || [0, 0])[0], tgt[1] - (pose.offset || [0, 0])[1]], bend);
      for (const [k, v] of Object.entries(sol)) { let d = v - (pose.angles[k] || 0); while (d > 180) d -= 360; while (d < -180) d += 360; pose.angles[k] = (pose.angles[k] || 0) + d * w; }
    }
    // foot pins: during contact phases a foot stays where it first touched down. tl.travel is the root's speed along x
    // in artboard px/s, or {path} (the cast's place.path): the planted point keeps its x in the frame while the root moves.
    if (tl.pins) for (const foot of ['foot_L', 'foot_R']) {
      if (!tl.pins[foot] || !pose.contacts || !pose.contacts[foot]) continue;
      const limb = foot === 'foot_L' ? 'leg_L' : 'leg_R', [u, l, e, bend] = LIMBS[limb];
      const t0 = contactStart(layers, t, foot, CLIPS); if (t0 == null) continue;
      const p0 = evalStack(layers, t0, CLIPS);
      const a0 = { ...base.angles }; for (const [k, v] of Object.entries(p0.angles)) a0[k] = (a0[k] || 0) + v;   // as evaluate combines them
      const at0 = P.pointOf(puppet, e, null, 0, 0, { angles: a0, offset: p0.offset || [0, 0], view: tl.view ? sampleKeys(tl.view, t0) : pose.view });
      const hipX = (puppet.parts.hip.pivot[0]), ground = puppet.ground, fy = Math.min(at0[1], -2);
      let world;
      if (tl.travel && typeof tl.travel === 'object' && tl.travel.path) {
        const [x0, y0, s0, f0] = pathAt(tl.travel.path, t0), [x1, y1, s1, f1] = pathAt(tl.travel.path, t);
        // the planted point keeps its place in the frame along x (no sliding); its height is the clip's own (the heel
        // rolls up at the end of a step), and up and down the frame is depth in a 2.5D stage, so it rides on the ground
        // line under the hips (a foot pinned in y as well would leave the leg straining or crushed)
        const Wx = x0 + at0[0] * s0 * f0, now = P.pointOf(puppet, e, null, 0, 0, { angles: pose.angles, offset: pose.offset || [0, 0], view: pose.view });
        world = [(Wx - x1) / (s1 * f1) + hipX, Math.min(now[1], -2) + ground];
      } else world = [at0[0] + hipX + (tl.travel || 0) * (t0 - t), fy + ground];
      Object.assign(pose.angles, ik2(puppet, pose, u, l, e, [world[0] - (pose.offset || [0, 0])[0], world[1] - (pose.offset || [0, 0])[1]], bend));
    }
    // chains: a living wave along each chain, then FABRIK reach targets
    for (const [name, ch] of Object.entries(puppet.chains || {})) {
      if (ch.wave && tl.chain_wave !== false) { const wv = ch.wave; ch.parts.forEach((id, i) => { pose.angles[id] = (pose.angles[id] || 0) + (wv.amp ?? 8) * Math.sin(2 * Math.PI * (wv.freq ?? 0.6) * t - i * (wv.lag ?? 0.7) + (tl.seed || 0)); }); }
      const keys = (tl.chains || {})[name]; if (!keys) continue;
      const tgt = sampleKeys(keys, t); if (tgt) solveChain(puppet, pose, ch, [tgt[0] - (pose.offset || [0, 0])[0], tgt[1] - (pose.offset || [0, 0])[1]]);
    }
    // v0.9 copy-rotation constraints: copy_rotation = [{part, from, factor: 1, offset: 0, weight: 1}] (a tail that
    // follows the hips, a sleeve that follows the forearm, a second wheel that turns with the first)
    for (const cr of [].concat(tl.copy_rotation || puppet.copy_rotation || [])) {
      if (!puppet.parts[cr.part]) continue;
      const v = (pose.angles[cr.from] || 0) * (cr.factor ?? 1) + (cr.offset || 0), w = cr.weight ?? 1;
      pose.angles[cr.part] = (pose.angles[cr.part] || 0) * (1 - w) + v * w;
    }
    // joint limits (v0.6): parts[id].limits = [min, max] degrees from the rest pose; everything above is clamped
    const limit = () => { for (const [id, part] of Object.entries(puppet.parts)) if (part.limits && pose.angles[id] != null) pose.angles[id] = clamp(pose.angles[id], part.limits[0], part.limits[1]); };
    limit();
    // springs: secondary parts lag their driver's world angle
    if (tl.springs !== false && puppet.springs) for (const [part, sp] of Object.entries(puppet.springs)) {
      const drv = sp.driver || puppet.parts[part].parent;
      const fn = s => { const p2 = evaluate(puppet, { ...tl, springs: false, pins: null, ik: null }, s, CLIPS, PRESETS); return angOf(P.matrices(puppet, p2)[drv]) * 57.2958; };
      const now = fn(t), lag = lagged(fn, t, sp);
      pose.angles[part] = (pose.angles[part] || 0) + clamp((lag - now) * (sp.gain ?? 1), -(sp.limit || 35), sp.limit || 35);
    }
    if (tl.springs !== false && puppet.springs) limit();
    swapByAngle(P.inView(puppet, pose.view), pose);   // v0.9: drawings chosen by a part's final angle
    return pose;
  }

  root.Acting = { stretchOf, swapByAngle, lipsyncPose, pathAt, pathDist, pathTable, placeAt, contactStart, resolveTargets, crossRefs, evaluate, evalStack, driveAt, sampleClip, sampleKeys, blend, presetAt, ik2, lagged, blinkAt, LIMBS, fabrik, solveChain, chainPoints, emotionalMouth, principled };
})(typeof window !== 'undefined' ? window : globalThis);
