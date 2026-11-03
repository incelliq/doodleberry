// Multi-body physics bake (WP-09): a shot's "physics" block becomes baked prop tracks, simulated with Rapier's
// cross-platform deterministic build (@dimforge/rapier2d-deterministic-compat, Apache-2.0), so a rerun on any machine
// gives the same bytes. Bodies can start from a prop's motion (a juggled ball thrown up and let go), and contacts can
// be retimed onto the beat grid with a gentle piecewise-linear time warp.
//   node tools/physics/solve.mjs REQ.json OUT.json
// REQ: {fps, start, end, gravity: px/s^2, scale: px per metre (100), sample_fps (60), substeps_hz (240),
//       bodies: [{id, shape: "ball"|"box", r, size: [w, h], at: [x, y], angle, v: [vx, vy], spin: deg/s,
//                 density, restitution, friction, prop: {prop object} (start from its motion at `start`)}],
//       static: [{box: [cx, cy, w, h], angle, restitution, friction} | {segment: [x1, y1, x2, y2]}],
//       impulses: [{t, body, v: [vx, vy]}],   // a kick at a time (sets the velocity)
//       casts: [{puppet: path, place, timeline}],   // for bodies that start from a prop held by a character
//       retime: {grid: s, offset: s, min_dv: px/s, slope: [0.75, 1.33]} | null}
// OUT: {bodies: {id: {t0, fps, frames: [[x, y, deg]...], contacts: [[t, x, y]...]}}, contacts, keys, hash, rapier}
import fs from 'fs'; import path from 'path'; import crypto from 'crypto'; import { fileURLToPath } from 'url';
import RAPIER from '@dimforge/rapier2d-deterministic-compat';
const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '../..');
globalThis.window = globalThis;
const load = p => new Function(fs.readFileSync(p, 'utf8'))();
for (const f of ['puppet/loader/puppet.js', 'puppet/loader/acting.js', 'dbe/player/props.js']) load(path.join(root, f));
const LIBS = Object.fromEntries(fs.readdirSync(path.join(root, 'puppet/clips')).filter(f => f.endsWith('.json')).map(f => [f.replace('.json', ''), JSON.parse(fs.readFileSync(path.join(root, 'puppet/clips', f), 'utf8'))]));

const [reqPath, outPath] = process.argv.slice(2);
const req = JSON.parse(fs.readFileSync(reqPath, 'utf8'));
await RAPIER.init();

// where an attach target is at any time (the same evaluation as the SVG player's, minus look-at)
const casts = (req.casts || []).map(c => ({ ...c, p: JSON.parse(fs.readFileSync(path.resolve(root, c.puppet), 'utf8')) }));
const ctx = { fps: req.fps || 30, at(tg, tt) {
  if (!tg) return null; if (Array.isArray(tg)) return tg;
  const c = casts[tg.cast]; if (!c) return null;
  const pl = c.place || { x: 540, y: 1500 };
  const [x, y, s, flip] = Array.isArray(pl) ? Acting.sampleKeys(pl.map(([k, v]) => [k, [v.x, v.y, v.s ?? 1, v.flip ?? 1]]), tt) : [pl.x, pl.y, pl.s ?? 1, pl.flip ?? 1];
  const tl = { ...(c.timeline || {}) }; delete tl.lookat; delete tl.visemes_from;
  const L = LIBS[c.p.template] || LIBS.humanoid, pose = Acting.evaluate(c.p, tl, tt, L.clips, L.presets);
  return Puppet.pointOf(c.p, tg.part, tg.at || null, x, y, { ...pose, s, flip });
} };

const K = req.scale || 100, t0 = req.start || 0, t1 = req.end ?? t0 + 3, hz = req.substeps_hz || 240, dt = 1 / hz;
const world = new RAPIER.World({ x: 0, y: (req.gravity ?? 2600) / K });
world.timestep = dt;
for (const st of req.static || []) {
  let desc;
  if (st.box) { const [cx, cy, w, h] = st.box; desc = RAPIER.ColliderDesc.cuboid(w / 2 / K, h / 2 / K).setTranslation(cx / K, cy / K).setRotation((st.angle || 0) * Math.PI / 180); }
  else if (st.segment) { const [a, b, c, d] = st.segment; desc = RAPIER.ColliderDesc.segment({ x: a / K, y: b / K }, { x: c / K, y: d / K }); }
  else continue;
  world.createCollider(desc.setRestitution(st.restitution ?? 0.4).setFriction(st.friction ?? 0.6));
}
const bodies = [], byHandle = new Map();
for (const b of req.bodies || []) {
  let at = b.at || [540, 600], v = b.v || [0, 0];
  if (b.prop) { const p = PROPS.pos(b.prop, t0, ctx); if (p) at = p; if (!b.v) v = PROPS.velocity(b.prop, t0, ctx); }
  const rb = world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(at[0] / K, at[1] / K).setRotation((b.angle || 0) * Math.PI / 180)
    .setLinvel(v[0] / K, v[1] / K).setAngvel((b.spin || 0) * Math.PI / 180).setCcdEnabled(true));
  const shape = b.shape === 'box' ? RAPIER.ColliderDesc.cuboid((b.size || [60, 60])[0] / 2 / K, (b.size || [60, 60])[1] / 2 / K) : RAPIER.ColliderDesc.ball((b.r || 30) / K);
  const col = world.createCollider(shape.setDensity(b.density ?? 1).setRestitution(b.restitution ?? 0.55).setFriction(b.friction ?? 0.5)
    .setActiveEvents(RAPIER.ActiveEvents.COLLISION_EVENTS), rb);
  const rec = { id: b.id, rb, col, r: b.r || 30, sim: [], hits: [], prevV: [v[0], v[1]] };
  bodies.push(rec); byHandle.set(col.handle, rec);
}
const kicks = (req.impulses || []).map(k => ({ ...k, step: Math.round((k.t - t0) * hz) }));
const q = new RAPIER.EventQueue(true), steps = Math.round((t1 - t0) * hz);
const snap = () => bodies.forEach(r => { const p = r.rb.translation(); r.sim.push([p.x * K, p.y * K, r.rb.rotation() * 180 / Math.PI]); });
snap();
for (let i = 1; i <= steps; i++) {
  for (const k of kicks) if (k.step === i - 1) { const r = bodies.find(b => b.id === k.body); if (r) r.rb.setLinvel({ x: k.v[0] / K, y: k.v[1] / K }, true); }
  bodies.forEach(r => { const v = r.rb.linvel(); r.prevV = [v.x * K, v.y * K]; });
  world.step(q);
  const started = [];
  q.drainCollisionEvents((h1, h2, ok) => { if (ok) started.push([h1, h2]); });
  for (const [h1, h2] of started) for (const h of [h1, h2]) {
    const r = byHandle.get(h); if (!r) continue;
    const v = r.rb.linvel(), dv = Math.hypot(v.x * K - r.prevV[0], v.y * K - r.prevV[1]);
    const p = r.rb.translation(); r.hits.push([t0 + i * dt, p.x * K, p.y * K, dv, i]);
  }
  snap();
}

// retime: the strongest contacts move to the nearest grid points, with the time between stretched or squeezed
let knots = [[t0, t0]];   // [sim time, film time]
const rt = req.retime;
if (rt && rt.grid) {
  const g = rt.grid, off = rt.offset || 0, minDv = rt.min_dv ?? 250, [lo, hi] = rt.slope || [0.75, 1.33];
  // strongest first: a contact becomes a key if its grid point is free and the warp around it stays gentle
  const cand = bodies.flatMap(r => r.hits.filter(h => h[3] >= minDv).map(h => ({ t: h[0], dv: h[3] }))).sort((a, b) => b.dv - a.dv || a.t - b.t);
  for (const c of cand) {
    const gt = +(off + Math.round((c.t - off) / g) * g).toFixed(6);
    let i = knots.findIndex(k => k[0] > c.t); if (i < 0) i = knots.length;
    const prev = knots[i - 1], next = knots[i];
    if (c.t - prev[0] < 1e-6 || gt <= prev[1] + 1e-9 || (next && (next[0] - c.t < 1e-6 || gt >= next[1] - 1e-9))) continue;
    const s1 = (gt - prev[1]) / (c.t - prev[0]), s2 = next ? (next[1] - gt) / (next[0] - c.t) : 1;
    if (s1 < lo || s1 > hi || s2 < lo || s2 > hi) continue;   // too strong a warp: leave this contact where physics put it
    knots.splice(i, 0, [c.t, gt]);
  }
}
const lastK = knots[knots.length - 1];
const toFilm = s => { for (let i = 1; i < knots.length; i++) if (s <= knots[i][0]) { const [a, fa] = knots[i - 1], [b, fb] = knots[i]; return fa + (fb - fa) * (s - a) / (b - a); } return lastK[1] + (s - lastK[0]); };
const toSim = f => { for (let i = 1; i < knots.length; i++) if (f <= knots[i][1]) { const [a, fa] = knots[i - 1], [b, fb] = knots[i]; return a + (b - a) * (f - fa) / (fb - fa); } return lastK[0] + (f - lastK[1]); };
const sfps = req.sample_fps || 60, nOut = Math.round((t1 - t0) * sfps);
const r2 = v => Math.round(v * 100) / 100;
const out = { bodies: {}, contacts: [], keys: knots.slice(1).map(([s, f]) => ({ sim: +s.toFixed(6), film: f })), rapier: RAPIER.version() };
for (const r of bodies) {
  const frames = [];
  for (let k = 0; k <= nOut; k++) {
    const s = Math.min(t1, toSim(t0 + k / sfps)), u = (s - t0) * hz, i = Math.min(r.sim.length - 2, Math.max(0, Math.floor(u))), w = Math.min(1, u - i);
    const a = r.sim[i], b = r.sim[i + 1]; let da = b[2] - a[2]; while (da > 180) da -= 360; while (da < -180) da += 360;
    frames.push([r2(a[0] + (b[0] - a[0]) * w), r2(a[1] + (b[1] - a[1]) * w), r2(a[2] + da * w)]);
  }
  const contacts = r.hits.filter(h => h[3] >= (rt && rt.min_dv != null ? rt.min_dv * 0.5 : 120)).map(h => [+toFilm(h[0]).toFixed(4), r2(h[1]), r2(h[2] + r.r)]);
  out.bodies[r.id] = { t0, fps: sfps, frames, contacts };
  for (const h of r.hits) out.contacts.push({ body: r.id, t: +toFilm(h[0]).toFixed(4), sim_t: +h[0].toFixed(4), dv: Math.round(h[3]) });
}
out.contacts.sort((a, b) => a.t - b.t || (a.body < b.body ? -1 : 1));
out.hash = crypto.createHash('sha256').update(JSON.stringify(out.bodies)).digest('hex');
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(JSON.stringify({ ok: true, hash: out.hash, bodies: bodies.length, contacts: out.contacts.length, keys: out.keys.length }));
