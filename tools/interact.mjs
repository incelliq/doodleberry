// Interaction and locomotion solver and measurements (WP-11). Pure functions of the request; no randomness.
//   node tools/interact.mjs solve REQ.json OUT.json     a shot's "interact" block -> places and timeline additions
//   node tools/interact.mjs measure BAKE_SPEC.json BAKED.json OUT.json   foot slide and hand gaps on the baked frames
// solve REQ: {fps, start, end, cast: [{puppet, place, timeline}], interact: {walks, handshakes, eye_contact}}
//   walks:      [{cast, points: [[x, y]...], start, speed: "auto" | px/s, s | s_by_y: [y0, s0, y1, s1], view: "side", clip: "walk"}]
//   handshakes: [{a, b, start ("arrive" = when both have arrived, + 0.3 s), hold: 1.6, pumps: 3, amp: 10, reach: 0.5, arm: "arm_R"}]
//   hugs:       [{a, b, start ("arrive" + 0.3 s by default), hold: 2.0, reach: 0.6, back: [x, y] (a point on the partner's torso, its own artboard; default the back at chest height)}]
//   eye_contact: [{a, b, start, end}]
// OUT: {cast: [{place?, clips: [...], timeline: {...}}], walks: [{cast, length, speed, clip_speed, arrive, stride_speed}], handshakes: [{meet, start, end}], hugs: [{a, b, start, end, reach_used}]}
import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '..');
globalThis.window = globalThis;
const load = p => new Function(fs.readFileSync(p, 'utf8'))();
load(path.join(root, 'puppet/loader/puppet.js')); load(path.join(root, 'puppet/loader/acting.js'));
const LIBS = Object.fromEntries(fs.readdirSync(path.join(root, 'puppet/clips')).filter(f => f.endsWith('.json')).map(f => [f.replace('.json', ''), JSON.parse(fs.readFileSync(path.join(root, 'puppet/clips', f), 'utf8'))]));
const r1 = v => Math.round(v * 10) / 10, r3 = v => Math.round(v * 1000) / 1000;
const [op, ...args] = process.argv.slice(2);
const pup = p => JSON.parse(fs.readFileSync(path.resolve(root, p), 'utf8'));
const libOf = p => LIBS[p.template] || LIBS.humanoid;
const hipOf = p => (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];

// how fast the root must move so a planted foot does not slide: the backward speed of the stance foot in the clip
function strideSpeed(p, clip, view) {
  const keys = clip.contacts && clip.contacts.foot_L; if (!keys) return null;
  const on = keys.find(([, v]) => v), off = keys.find(([k, v]) => !v && k > on[0]);
  // over the whole stance: keys ease in and out, so the middle of a step moves faster than the step on average
  const a = on[0] + 1e-4, b = (off ? off[0] : clip.duration) - 1e-4;
  const at = ph => { const s = Acting.sampleClip(clip, ph); return Puppet.pointOf(p, 'foot_L', null, 0, 0, { angles: s.angles, offset: s.offset || [0, 0], view }); };
  const pa = at(a), pb = at(b);
  return { speed: 0.96 * Math.abs(pb[0] - pa[0]) / (b - a), dir: Math.sign(pa[0] - pb[0]) };   // artboard px per clip second, 4% slack
}

function solve(req) {
  const ia = req.interact || {}, out = { cast: req.cast.map(() => ({ clips: [], timeline: {} })), walks: [], handshakes: [], hugs: [] };
  const casts = req.cast.map(c => ({ ...c, p: pup(c.puppet), tl: { ...(c.timeline || {}) } }));
  const arrive = {};
  for (const w of ia.walks || []) {
    const c = casts[w.cast], p = c.p, L = libOf(p), clipName = w.clip || 'walk', clip = (p.clips || {})[clipName] || L.clips[clipName];
    if (!clip) throw new Error(`no clip ${clipName}`);
    const s = w.s_by_y ? (w.s_by_y[1] + w.s_by_y[3]) / 2 : w.s ?? (c.place && !Array.isArray(c.place) ? (c.place.s ?? (c.place.path || {}).s ?? 1) : 1);
    const st = strideSpeed(p, clip, w.view || 'side'), vNat = st.speed * s;   // frame px/s at clip speed 1
    const len = Acting.pathTable({ points: w.points }).L;
    // the root ramps up and down over `ease` s (the feet planted while the walk fades in are behind the stride, so the
    // root must move less in that first step); the clip runs a whole number of half steps plus a quarter, so the walk
    // ends on a passing position (feet together) and settles into the next clip without a scissor step; its stride
    // is never slower than the root (a slower stride would leave a planted leg straining behind)
    const speed = w.speed === 'auto' || w.speed == null ? vNat : w.speed, ease = w.ease ?? 0.45;
    const dur = len / speed + ease, start = w.start, end = start + dur, k0 = speed / vNat;
    // the clip starts a quarter cycle in (the first stance foot under the hips, as it stands in idle)
    const phase = 0.25 * clip.duration, target = Math.max(1, Math.ceil(dur * k0 * 2 - 1e-9) / 2), k = target / dur;
    const path = { points: w.points.map(q => [r1(q[0]), r1(q[1])]), start, end: r3(end), ease, ...(w.s_by_y ? { s_by_y: w.s_by_y } : { s }), face: 'auto' };
    out.cast[w.cast].place = { path };
    out.cast[w.cast].clips.push({ clip: clipName, start: r3(start), end: r3(end), speed: r3(k), phase, fadeIn: 0.15, fadeOut: 0.25, solved: 'interact' });
    out.cast[w.cast].timeline.pins = { foot_L: 'auto', foot_R: 'auto' };
    if (w.view !== null) out.cast[w.cast].timeline.view = [[0, w.view || 'side']];
    c.place = { path }; c.tl = { ...c.tl, view: [[0, w.view || 'side']], clips: [...(c.tl.clips || []).filter(x => x.solved !== 'interact'), out.cast[w.cast].clips.at(-1)], pins: { foot_L: 'auto', foot_R: 'auto' }, travel: { path } };
    arrive[w.cast] = end;
    out.walks.push({ cast: w.cast, length: r1(len), speed: r3(speed), clip_speed: r3(k), stride_speed: r1(vNat * k), cycles: target, arrive: r3(end) });
  }
  const poseAt = (ci, t) => { const c = casts[ci], [x, y, s, flip] = Acting.placeAt(c.place, t), L = libOf(c.p);
    const tl = Acting.resolveTargets(c.tl, t, w => [(w[0] - x) / (s * flip) + hipOf(c.p)[0], (w[1] - y) / s + c.p.ground], () => null);
    return { x, y, s, flip, pose: Acting.evaluate(c.p, tl, t, L.clips, L.presets) }; };
  const pt = (ci, part, t, at) => { const o = poseAt(ci, t); return Puppet.pointOf(casts[ci].p, part, at || null, o.x, o.y, { ...o.pose, s: o.s, flip: o.flip }); };
  for (const h of ia.handshakes || []) {
    const arm = h.arm || 'arm_R', side = arm.slice(-1), up = `upperarm_${side}`, hand = `hand_${side}`, fore = `forearm_${side}`;
    const start = h.start === 'arrive' || h.start == null ? Math.max(arrive[h.a] ?? 0, arrive[h.b] ?? 0) + 0.3 : h.start;
    const hold = h.hold ?? 1.6, reach = h.reach ?? 0.5, end = start + hold, pumps = h.pumps ?? 3, amp = h.amp ?? 10;
    const pa = casts[h.a].p, sa = poseAt(h.a, start).s, sb = poseAt(h.b, start).s;
    const len = q => Math.hypot(q.parts[fore].pivot[0] - q.parts[up].pivot[0], q.parts[fore].pivot[1] - q.parts[up].pivot[1]) + Math.hypot(q.parts[hand].pivot[0] - q.parts[fore].pivot[0], q.parts[hand].pivot[1] - q.parts[fore].pivot[1]);
    const shA = pt(h.a, up, start), shB = pt(h.b, up, start), reachA = len(pa) * sa, reachB = len(casts[h.b].p) * sb;
    const mid = [(shA[0] + shB[0]) / 2, (shA[1] + shB[1]) / 2 + 0.62 * Math.min(reachA, reachB)];
    const fA = Math.hypot(mid[0] - shA[0], mid[1] - shA[1]) / reachA, fB = Math.hypot(mid[0] - shB[0], mid[1] - shB[1]) / reachB;
    // b holds out a hand to the meeting point and pumps it; a takes b's hand wherever it is (a target on b)
    const keysB = [], fps = req.fps || 30;
    for (let f = Math.ceil((start - reach) * fps); f <= Math.floor((end + reach) * fps); f++) {
      const t = f / fps, u = Math.min(1, Math.max(0, (t - start) / hold)), dy = t >= start && t <= end ? -amp * Math.sin(2 * Math.PI * pumps * u) * Math.sin(Math.PI * u) : 0;
      keysB.push([r3(t), { x: r1(mid[0]), y: r1(mid[1] + dy) }]);
    }
    const weight = [[r3(start - reach), 0], [r3(start), 1], [r3(end), 1], [r3(end + reach), 0]];
    // (elbows bend down with the default bend: both stand in their own artboard facing +x, the facing is in the flip)
    const addIk = (ci, keys) => { const tl = out.cast[ci].timeline; tl.ik = { ...(tl.ik || {}), [arm]: keys }; tl.ik_weight = { ...(tl.ik_weight || {}), [arm]: weight }; };
    addIk(h.b, keysB);
    addIk(h.a, [[r3(start - reach), { cast: h.b, part: hand }]]);
    out.handshakes.push({ a: h.a, b: h.b, start: r3(start), end: r3(end), meet: mid.map(r1), reach_used: [r3(fA), r3(fB)] });
  }
  // hugs (WP-11): both arms of each round the other's back, the heads turned to each other; the arms blend in by IK
  // over `reach` s and out after `hold`. Each target is a point on the partner's torso (its own artboard, so it follows
  // the partner's pose, flip and squash). Drawn in cast order: the later character's front arm crosses over the
  // earlier one's back, the earlier one's arms go behind the later, as a hug looks from the side.
  for (const g of ia.hugs || []) {
    const start = g.start === 'arrive' || g.start == null ? Math.max(arrive[g.a] ?? 0, arrive[g.b] ?? 0) + 0.3 : g.start;
    const hold = g.hold ?? 2.0, reach = g.reach ?? 0.6, end = start + hold, weight = [[r3(start - reach), 0], [r3(start), 1], [r3(end), 1], [r3(end + reach), 0]];
    const used = [], targets = [];
    for (const [me, you] of [[g.a, g.b], [g.b, g.a]]) {
      const P = casts[you].p, tp = P.parts.torso || P.parts.body || P.parts[Object.keys(P.parts)[0]], neck = P.parts.neck || P.parts.head;
      // the back at chest height: behind the torso's pivot (the artboard faces +x, so the back is towards -x)
      const hx = tp.pivot[0], top = neck ? neck.pivot[1] : tp.pivot[1] - 200, cy = tp.pivot[1] + (top - tp.pivot[1]) * 0.55;
      const back = g.back || [r1(hx - 38), r1(cy)], low = [r1(hx - 30), r1(cy + 0.25 * (tp.pivot[1] - top))];
      const tl = out.cast[me].timeline;
      tl.ik = { ...(tl.ik || {}), arm_R: [[r3(start - reach), { cast: you, part: tp === P.parts.torso ? 'torso' : Object.keys(P.parts).find(k => P.parts[k] === tp), at: back }]],
                arm_L: [[r3(start - reach), { cast: you, part: tp === P.parts.torso ? 'torso' : Object.keys(P.parts).find(k => P.parts[k] === tp), at: low }]] };
      tl.ik_weight = { ...(tl.ik_weight || {}), arm_R: weight, arm_L: weight };
      const tpart = tl.ik.arm_R[0][1].part; targets.push({ cast: me, hand: 'hand_R', of: you, part: tpart, at: back }, { cast: me, hand: 'hand_L', of: you, part: tpart, at: low });
      tl.lookat = [...(tl.lookat || []), { part: 'head', target: { cast: you, part: 'head' }, limit: 20, weight: 1, start: r3(start - reach), end: r3(end + reach), solved: 'interact' }];
      const sh = pt(me, 'upperarm_R', start), tg = (() => { const o = poseAt(you, start); return Puppet.pointOf(P, 'torso', back, o.x, o.y, { ...o.pose, s: o.s, flip: o.flip }); })();
      const q = casts[me].p, L = Math.hypot(q.parts.forearm_R.pivot[0] - q.parts.upperarm_R.pivot[0], q.parts.forearm_R.pivot[1] - q.parts.upperarm_R.pivot[1]) + Math.hypot(q.parts.hand_R.pivot[0] - q.parts.forearm_R.pivot[0], q.parts.hand_R.pivot[1] - q.parts.forearm_R.pivot[1]);
      used.push(r3(Math.hypot(tg[0] - sh[0], tg[1] - sh[1]) / (L * poseAt(me, start).s)));
    }
    out.hugs.push({ a: g.a, b: g.b, start: r3(start), end: r3(end), reach_used: used, targets });
  }
  for (const e of ia.eye_contact || []) for (const [me, you] of [[e.a, e.b], [e.b, e.a]]) {
    const tl = out.cast[me].timeline;
    tl.lookat = [...(tl.lookat || []), { part: 'head', target: { cast: you, part: 'head' }, limit: e.limit ?? 18, weight: 1, start: e.start, end: e.end, solved: 'interact' }];
  }
  return out;
}

// the measurements behind the done-when: how far a planted foot slides along the ground (x in the frame, per frame,
// while the same contact lasts; its height is the clip's heel roll, and up and down the frame is depth), and how far
// apart two hands are
function measure(spec, baked, opts) {
  const base = path.dirname(path.resolve(args[0]));
  const res = { feet: [], hands: [] };
  const P = spec.cast.map(c => pup(path.resolve(base, c.puppet)));
  const world = (ci, f, part, at) => { const fr = baked.cast[ci].frames[f]; return Puppet.pointOf(P[ci], part, at || null, fr.x, fr.y, { angles: fr.angles, offset: fr.offset, view: fr.view, s: fr.s, flip: fr.flip, squash: fr.squash, shifts: fr.shifts || undefined, scales: fr.scales || undefined }); };
  spec.cast.forEach((c, ci) => {
    const tl = { ...(c.timeline || {}) }; if (!tl.pins) return;
    const L = libOf(P[ci]); let max = 0, sum = 0, n = 0, worst = null;
    for (const foot of ['foot_L', 'foot_R']) {
      let prev = null;
      for (let f = 0; f < baked.cast[ci].frames.length; f++) {
        const t = spec.start + f / spec.fps, pose = Acting.evaluate(P[ci], { ...tl, ik: null, lookat: null }, t, L.clips, L.presets);
        const on = pose.contacts && pose.contacts[foot], t0 = on ? Acting.contactStart(tl.clips, t, foot, { ...L.clips, ...(P[ci].clips || {}) }) : null;
        const fr = baked.cast[ci].frames[f], w = on && t0 != null ? world(ci, f, foot) : null;
        const q = w ? [w[0], w[1] - fr.y] : null;   // x in the frame (sliding); the height is the clip's heel roll
        if (q && prev && prev.t0 === t0) { const d = Math.abs(q[0] - prev.q[0]); sum += d; n++; if (d > max) { max = d; worst = { foot, frame: f }; } }
        prev = q ? { q, t0 } : null;
      }
    }
    res.feet.push({ cast: ci, max_slide_px: r3(max), mean_slide_px: r3(n ? sum / n : 0), planted_frames: n, worst });
  });
  for (const h of opts.hands || []) {
    let max = 0, n = 0;
    for (let f = 0; f < baked.cast[h.a].frames.length; f++) {
      const t = spec.start + f / spec.fps; if (t < h.start || t > h.end) continue;
      const a = world(h.a, f, h.part_a || 'hand_R', h.at_a), b = world(h.b, f, h.part_b || 'hand_R', h.at_b), d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      max = Math.max(max, d); n++;
    }
    res.hands.push({ a: h.a, b: h.b, max_gap_px: r3(max), frames: n });
  }
  res.points = (opts.points || []).map(q => { const f = Math.round((q.t - spec.start) * spec.fps), w = world(q.cast, f, q.part);
    return { ...q, at: w.map(r1), gap_px: r3(Math.hypot(w[0] - q.want[0], w[1] - q.want[1])) }; });
  return res;
}

// loader-level checks of the WP-11 pieces (pure, fast)
function selftest() {
  const bad = [], close = (a, b, e = 1e-6) => Math.abs(a - b) <= e;
  const path = { points: [[0, 0], [300, 60], [600, 0]], start: 1, speed: 200 }, T = Acting.pathTable(path);
  const d1 = Acting.pathDist(path, 2), d2 = Acting.pathDist(path, 2.5);
  if (!close(d1, 200) || !close(d2 - d1, 100)) bad.push({ path_speed: [d1, d2] });
  const end = Acting.pathAt(path, 99); if (!close(end[0], 600) || !close(end[1], 0) || end[3] !== 1) bad.push({ path_end: end });
  const back = Acting.pathAt({ points: [[600, 0], [0, 0]], start: 0, speed: 100 }, 1); if (back[3] !== -1 || !close(back[0], 500)) bad.push({ path_flip: back });
  const eased = { ...path, end: 5, ease: 1 }; if (!close(Acting.pathDist(eased, 5), T.L) || !(Acting.pathDist(eased, 1.5) < 0.5 * Acting.pathDist({ ...path, end: 5 }, 1.5))) bad.push({ path_ease: true });
  // the exact contact start agrees with stepping back in small steps
  const L = LIBS.humanoid, layers = [{ clip: 'walk', start: 0.2, speed: 0.8, phase: 0.25, fadeIn: 0.1 }];
  for (const t of [0.9, 1.37, 2.05]) {
    const s = Acting.evalStack(layers, t, L.clips); if (!s.contacts || !s.contacts.foot_L) continue;
    let tb = t; while (tb > 0.25) { const q = Acting.evalStack(layers, tb - 1e-4, L.clips); if (!q.contacts || !q.contacts.foot_L) break; tb -= 1e-4; }
    const tc = Acting.contactStart(layers, t, 'foot_L', L.clips); if (!close(tc, tb, 2e-4)) bad.push({ contact_start: [t, tc, tb] });
  }
  // IK/FK blend: weight 0 is the clip pose, weight 1 reaches the target
  const pip = pup('puppet/examples/pip.puppet.json'), tl = { clips: [{ clip: 'idle', start: 0, fadeIn: 0 }], ik: { arm_R: [[0, [470, 420]]] } };
  const fk = Acting.evaluate(pip, { clips: tl.clips }, 1, L.clips, L.presets), w0 = Acting.evaluate(pip, { ...tl, ik_weight: { arm_R: [[0, 0]] } }, 1, L.clips, L.presets);
  const w1 = Acting.evaluate(pip, tl, 1, L.clips, L.presets), hand = Puppet.pointOf(pip, 'hand_R', null, 0, 0, w1);
  if (!close(w0.angles.forearm_R ?? 0, fk.angles.forearm_R ?? 0, 1e-9)) bad.push({ ik_weight0: true });
  if (Math.hypot(hand[0] + hipOf(pip)[0] - 470, hand[1] + pip.ground - 420) > 0.5) bad.push({ ik_reach: hand });
  // a target on another character resolves through the caller; unresolved targets are skipped, not NaN
  const raw = Acting.evaluate(pip, { ...tl, ik: { arm_R: [[0, { cast: 1, part: 'hand_R' }]] } }, 1, L.clips, L.presets);
  if (Object.values(raw.angles).some(v => !isFinite(v))) bad.push({ unresolved_target: true });
  const res = Acting.resolveTargets({ ik: { arm_R: [[0, { cast: 1, part: 'hand_R' }]] } }, 1, w => [w[0] + 1, w[1] + 2], () => [10, 20]);
  if (JSON.stringify(res.ik.arm_R) !== '[[0,[11,22]]]') bad.push({ resolve: res.ik });
  // v0.9: stretchy IK lands past full reach; a stretched parent carries its child's pivot without shearing it
  const far = [300 + 330, 350 + 260];   // well past Pip's arm reach (about 230)
  const st1 = Acting.evaluate(pip, { clips: tl.clips, ik: { arm_R: [[0, far]] }, ik_stretch: { arm_R: 2 } }, 1, L.clips, L.presets);
  const wr = Puppet.pointOf(pip, 'hand_R', null, 0, 0, st1), gap = Math.hypot(wr[0] + hipOf(pip)[0] - far[0], wr[1] + pip.ground - far[1]);
  if (gap > 0.5 || !st1.scales || !st1.scales.upperarm_R) bad.push({ ik_stretch: gap });
  const M = Puppet.matrices(pip, { angles: { upperarm_R: 30, forearm_R: -20 }, scales: { upperarm_R: [1, 1.5] } });
  const elbow = [M.forearm_R[0] * 378 + M.forearm_R[2] * 470 + M.forearm_R[4], M.forearm_R[1] * 378 + M.forearm_R[3] * 470 + M.forearm_R[5]];
  const axes = M.forearm_R, shear = Math.abs(axes[0] * axes[2] + axes[1] * axes[3]);
  const want = Puppet.matrices(pip, { angles: { upperarm_R: 30 } }).upperarm_R, up = [372 + (378 - 372) * 1, 350 + (470 - 350) * 1.5], wE = [want[0] * up[0] + want[2] * up[1] + want[4], want[1] * up[0] + want[3] * up[1] + want[5]];
  if (Math.hypot(elbow[0] - wE[0], elbow[1] - wE[1]) > 1e-6 || shear > 1e-9) bad.push({ local_scale: { elbow, wE, shear } });
  // copy rotation, angle-driven drawings, layer order keys, whole-face lip-sync
  const tam = pup('puppet/examples/tam.puppet.json');
  const cr = Acting.evaluate(tam, { clips: [], set: {}, copy_rotation: [{ part: 'upperarm_L', from: 'upperarm_R', factor: -0.5 }], poses: [], ik: { arm_R: [[0, [470, 200]]] } }, 1, L.clips, L.presets);
  if (!close(cr.angles.upperarm_L, -0.5 * cr.angles.upperarm_R, 1e-9)) bad.push({ copy_rotation: [cr.angles.upperarm_L, cr.angles.upperarm_R] });
  if (cr.hand_R_pose !== 'hold') bad.push({ by_angle_up: cr.hand_R_pose });
  const down = Acting.evaluate(tam, { clips: [] }, 1, L.clips, L.presets); if (down.hand_R_pose != null) bad.push({ by_angle_down: down.hand_R_pose });
  const zk = Acting.evaluate(tam, { clips: [], z: [[0, {}], [2, { arm_R: 30 }]] }, 2.5, L.clips, L.presets); if (!zk.z || zk.z.arm_R !== 30) bad.push({ z_keys: zk.z });
  const vis = [[0.5, 'O'], [1.0, 'closed']], lO = Acting.evaluate(tam, { clips: [], visemes: vis }, 0.8, L.clips, L.presets), lC = Acting.evaluate(tam, { clips: [], visemes: vis }, 1.4, L.clips, L.presets);
  if (!close(lO.angles.head || 0, -1.5, 1e-9) || !lO.shifts || !close(lO.shifts['@brows'][1], -4, 1e-9) || Math.abs(lC.angles.head || 0) > 1e-9) bad.push({ lipsync: [lO.angles.head, lC.angles.head] });
  return { ok: !bad.length, bad, path_length: r1(T.L), ik_stretch_gap: r3(gap), ik_stretch_k: st1.scales.upperarm_R.map(r3) };
}

if (op === 'selftest') { process.stdout.write(JSON.stringify(selftest())); }
else if (op === 'matrices') {   // for the Python check that dbe/geom.py follows puppet.js (v0.9 scales)
  const pip = pup('puppet/examples/pip.puppet.json'), pose = JSON.parse(args[0]);
  process.stdout.write(JSON.stringify(Puppet.matrices(pip, pose))); }
else if (op === 'solve') { const req = JSON.parse(fs.readFileSync(args[0], 'utf8')); fs.writeFileSync(args[1], JSON.stringify(solve(req))); }
else if (op === 'measure') { const spec = JSON.parse(fs.readFileSync(args[0], 'utf8')), baked = JSON.parse(fs.readFileSync(args[1], 'utf8')), opts = args[3] ? JSON.parse(fs.readFileSync(args[3], 'utf8')) : {};
  fs.writeFileSync(args[2], JSON.stringify(measure(spec, baked, opts))); }
else { console.error('usage: node tools/interact.mjs solve REQ OUT | measure SPEC BAKED OUT [OPTS]'); process.exit(2); }
