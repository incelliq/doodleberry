// Doodleberry acting layer: turns a timeline into a puppet pose at time t.
// Two-bone IK with targets and pins, deterministic springs, pose presets and blending, action clips on a
// nonlinear (NLA) stack, viseme lip-sync, blinks and gaze. Pure functions of t. Needs puppet.js. Exposes `Acting`.
//
//   const pose = Acting.evaluate(puppet, {
//     clips: [{ clip: 'walk', start: 0, weight: 1 }, { clip: 'talk_beat', start: 2, additive: true }],
//     poses: [[0, 'neutral'], [3, 'arms_crossed']],     // preset keys (blended over `poseBlend` s)
//     visemes: [[0.4, 'small'], [0.44, 'wide'], ...],    // from timing.json "visemes"[speaker]
//     look: [[0, [1, 0]], [4, [-1, 0.3]]],               // gaze keys
//     ik: { arm_R: [[1, [460, 420]]] },                  // reach targets in artboard space over time
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
        if (Array.isArray(v0)) return v0.map((x, j) => x + (v1[j] - x) * k);
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
    return pose;
  }
  // layers: [{clip, start, speed=1, weight=1, fadeIn=0.25, fadeOut=0.25, end, additive, base}]
  // Blending per track: foreground clips average by weight among themselves and override the base layer ("idle", or
  // any layer with base: true) in proportion to their weight, so a gesture at weight 1 plays at full size over idle and
  // idle still fills every track the gesture does not touch. Additive layers add on top.
  function evalStack(layers, t, CLIPS) {
    const base = { angles: {} }, add = { angles: {} }, fg = {}, bg = {};
    const offs = [];
    for (const L of layers || []) {
      const clip = typeof L.clip === 'string' ? CLIPS[L.clip] : L.clip; if (!clip) continue;
      const speed = L.speed || 1, lt = (t - (L.start || 0)) * speed;
      const end = L.end ?? (clip.loop ? Infinity : (L.start || 0) + clip.duration / speed);
      if (t < (L.start || 0) || t > end + (L.fadeOut ?? 0.25)) continue;
      const fi = L.fadeIn ?? 0.25, fo = L.fadeOut ?? 0.25;
      let w = (L.weight ?? 1) * (fi ? smooth(clamp((t - (L.start || 0)) / fi)) : 1) * (isFinite(end) && fo ? 1 - smooth(clamp((t - end) / fo)) : 1);
      if (w <= 0) continue;
      const s = sampleClip(clip, lt), g = L.gain ?? 1;   // gain scales the clip's motion (calmer or bigger acting)
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
    const L1 = Math.hypot(pl[0] - pu[0], pl[1] - pu[1]), L2 = Math.hypot(pe[0] - pl[0], pe[1] - pl[1]);
    const dx = target[0] - S[0], dy = target[1] - S[1];
    const d = clamp(Math.hypot(dx, dy), Math.abs(L1 - L2) + 1e-3, L1 + L2 - 1e-3);
    const a = Math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1));
    const b = Math.acos(clamp((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2), -1, 1));
    const upW = Math.atan2(dy, dx) - bend * a, loW = upW + bend * (Math.PI - b);
    const r1 = Math.atan2(pl[1] - pu[1], pl[0] - pu[0]), r2 = Math.atan2(pe[1] - pl[1], pe[0] - pl[0]);
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
    // v0.4 controls (smart bones / driven keys): one value drives angles, shifts, swaps and layer order through key curves
    for (const [name, keys] of Object.entries(tl.controls || {})) {
      const ctl = (puppet.controls || {})[name]; if (!ctl) continue;
      const v = sampleKeys(keys, t); if (v == null) continue;
      for (const dr of ctl.drives || []) {
        const val = driveAt(dr.keys, v); if (val == null) continue;
        const [kind, id] = dr.target.split('.');
        if (kind === 'angles') pose.angles[id] = (pose.angles[id] || 0) + val;
        else if (kind === 'shift') { pose.shifts = pose.shifts || {}; const o = pose.shifts[id] || [0, 0]; pose.shifts[id] = [o[0] + val[0], o[1] + val[1]]; }
        else if (kind === 'swap') pose[id] = val;
        else if (kind === 'z') { pose.z = pose.z || {}; pose.z[id] = val; }
      }
    }
    // look-at constraint: rotate a part so its aim vector points at a target (artboard coordinates), clamped
    for (const la of [].concat(tl.lookat || [])) {
      const tgt = la.target_local || la.target; if (!tgt || !puppet.parts[la.part]) continue;
      const w = la.weight ?? 1, lim = la.limit ?? 30, part = puppet.parts[la.part];
      const M = P.matrices(puppet, pose), par = part.parent && M[part.parent];
      const pv = par ? [par[0] * part.pivot[0] + par[2] * part.pivot[1] + par[4], par[1] * part.pivot[0] + par[3] * part.pivot[1] + par[5]] : part.pivot;
      const aim = la.aim || [1, 0], cur = Math.atan2(aim[1], aim[0]) + (par ? Math.atan2(par[1], par[0]) : 0) + ((pose.angles[la.part] || 0) * Math.PI / 180);
      let d = (Math.atan2(tgt[1] - pv[1], tgt[0] - pv[0]) - cur) * 180 / Math.PI;
      while (d > 180) d -= 360; while (d < -180) d += 360;
      pose.angles[la.part] = (pose.angles[la.part] || 0) + Math.max(-lim, Math.min(lim, d)) * w;
    }
    // IK reach targets
    for (const [limb, keys] of Object.entries(tl.ik || {})) {
      const tgt = sampleKeys(keys, t); if (!tgt) continue;
      const [u, l, e, bend] = LIMBS[limb]; Object.assign(pose.angles, ik2(puppet, pose, u, l, e, [tgt[0] - (pose.offset || [0, 0])[0], tgt[1] - (pose.offset || [0, 0])[1]], bend));
    }
    // foot pins: during contact phases a foot stays where it first touched down
    if (tl.pins) for (const foot of ['foot_L', 'foot_R']) {
      if (!tl.pins[foot] || !pose.contacts || !pose.contacts[foot]) continue;
      const limb = foot === 'foot_L' ? 'leg_L' : 'leg_R', [u, l, e, bend] = LIMBS[limb];
      // find when this contact began (step back in small steps), and where the foot was then
      let t0 = t; for (let k = 0; k < 60; k++) { const s = evalStack(layers, t0 - 1 / 60, CLIPS); if (!s.contacts || !s.contacts[foot]) break; t0 -= 1 / 60; }
      const p0 = evalStack(layers, t0, CLIPS);
      const at0 = P.pointOf(puppet, e, null, 0, 0, { angles: { ...base.angles, ...p0.angles }, offset: p0.offset || [0, 0] });
      const hipX = (puppet.parts.hip.pivot[0]), ground = puppet.ground;
      const world = [at0[0] + hipX + (tl.travel || 0) * (t0 - t), Math.min(at0[1] + ground, ground - 2)];
      Object.assign(pose.angles, ik2(puppet, pose, u, l, e, [world[0] - (pose.offset || [0, 0])[0], world[1] - (pose.offset || [0, 0])[1]], bend));
    }
    // chains: a living wave along each chain, then FABRIK reach targets
    for (const [name, ch] of Object.entries(puppet.chains || {})) {
      if (ch.wave && tl.chain_wave !== false) { const wv = ch.wave; ch.parts.forEach((id, i) => { pose.angles[id] = (pose.angles[id] || 0) + (wv.amp ?? 8) * Math.sin(2 * Math.PI * (wv.freq ?? 0.6) * t - i * (wv.lag ?? 0.7) + (tl.seed || 0)); }); }
      const keys = (tl.chains || {})[name]; if (!keys) continue;
      const tgt = sampleKeys(keys, t); if (tgt) solveChain(puppet, pose, ch, [tgt[0] - (pose.offset || [0, 0])[0], tgt[1] - (pose.offset || [0, 0])[1]]);
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
    return pose;
  }

  root.Acting = { evaluate, evalStack, driveAt, sampleClip, sampleKeys, blend, presetAt, ik2, lagged, blinkAt, LIMBS, fabrik, solveChain, chainPoints, emotionalMouth, principled };
})(typeof window !== 'undefined' ? window : globalThis);
