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
  // layers: [{clip, start, speed=1, weight=1, fadeIn=0.25, fadeOut=0.25, end, additive}]
  function evalStack(layers, t, CLIPS) {
    const base = { angles: {} }, add = { angles: {} };
    let wsum = 0; const offs = [];
    for (const L of layers || []) {
      const clip = typeof L.clip === 'string' ? CLIPS[L.clip] : L.clip; if (!clip) continue;
      const speed = L.speed || 1, lt = (t - (L.start || 0)) * speed;
      const end = L.end ?? (clip.loop ? Infinity : (L.start || 0) + clip.duration / speed);
      if (t < (L.start || 0) || t > end + (L.fadeOut ?? 0.25)) continue;
      const fi = L.fadeIn ?? 0.25, fo = L.fadeOut ?? 0.25;
      let w = (L.weight ?? 1) * (fi ? smooth(clamp((t - (L.start || 0)) / fi)) : 1) * (isFinite(end) && fo ? 1 - smooth(clamp((t - end) / fo)) : 1);
      if (w <= 0) continue;
      const s = sampleClip(clip, lt);
      const tgt = L.additive ? add : base;
      for (const [k, v] of Object.entries(s.angles)) tgt.angles[k] = (tgt.angles[k] || 0) + v * w;
      if (!L.additive) { wsum += w; if (s.offset) offs.push([s.offset, w]); for (const [k, v] of Object.entries(s)) if (k !== 'angles' && k !== 'offset' && w >= 0.5) base[k] = v; }
      else { if (s.offset) add.offset = [(add.offset || [0, 0])[0] + s.offset[0] * w, (add.offset || [0, 0])[1] + s.offset[1] * w];  // additive moves (hops) stack on the base
        for (const [k, v] of Object.entries(s)) if (k !== 'angles' && k !== 'offset' && w >= 0.5) add[k] = v; }
    }
    if (wsum > 1) for (const k of Object.keys(base.angles)) base.angles[k] /= wsum;
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

  // ---------- evaluate everything at t ----------
  function evaluate(puppet, tl, t, CLIPS = {}, PRESETS = {}) {
    const base = presetAt(puppet, tl.poses, t, tl.poseBlend || 0.4, PRESETS) || { angles: {} };
    const stack = evalStack(tl.clips, t, CLIPS);
    const pose = { ...base, ...stack, angles: { ...base.angles } };
    for (const [k, v] of Object.entries(stack.angles)) pose.angles[k] = (pose.angles[k] || 0) + v;
    if (tl.visemes && tl.visemes.length && !pose.mouth) { let sh = 'closed'; for (const [ct, s] of tl.visemes) { if (ct > t + 0.033) break; sh = s; } pose.mouth = sh; }
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
      let t0 = t; for (let k = 0; k < 60; k++) { const s = evalStack(tl.clips, t0 - 1 / 60, CLIPS); if (!s.contacts || !s.contacts[foot]) break; t0 -= 1 / 60; }
      const p0 = evalStack(tl.clips, t0, CLIPS);
      const at0 = P.pointOf(puppet, e, null, 0, 0, { angles: { ...base.angles, ...p0.angles }, offset: p0.offset || [0, 0] });
      const hipX = (puppet.parts.hip.pivot[0]), ground = puppet.ground;
      const world = [at0[0] + hipX + (tl.travel || 0) * (t0 - t), Math.min(at0[1] + ground, ground - 2)];
      Object.assign(pose.angles, ik2(puppet, pose, u, l, e, [world[0] - (pose.offset || [0, 0])[0], world[1] - (pose.offset || [0, 0])[1]], bend));
    }
    // springs: secondary parts lag their driver's world angle
    if (tl.springs !== false && puppet.springs) for (const [part, sp] of Object.entries(puppet.springs)) {
      const drv = sp.driver || puppet.parts[part].parent;
      const fn = s => { const p2 = evaluate(puppet, { ...tl, springs: false, pins: null, ik: null }, s, CLIPS, PRESETS); return angOf(P.matrices(puppet, p2)[drv]) * 57.2958; };
      const now = fn(t), lag = lagged(fn, t, sp);
      pose.angles[part] = (pose.angles[part] || 0) + clamp((lag - now) * (sp.gain ?? 1), -(sp.limit || 35), sp.limit || 35);
    }
    return pose;
  }

  root.Acting = { evaluate, evalStack, driveAt, sampleClip, sampleKeys, blend, presetAt, ik2, lagged, blinkAt, LIMBS };
})(typeof window !== 'undefined' ? window : globalThis);
