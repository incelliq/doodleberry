// Bake puppet acting to a renderer-neutral animation: per frame, every part's local angle, the root offset and the
// swap choices, plus where each puppet stands. Synfig, Grease Pencil and Lottie exporters read this file.
//   node tools/bake.mjs SPEC.json OUT.json
// SPEC: { fps, frames, start, size, camera: [[t, [cx, cy, zoom]]], cast: [{ puppet: "path.puppet.json", place: {x, y, s, flip} | [[t, {x,y,s,flip}]...] | {path},
//         timeline: { clips, poses, visemes, look, ik, pins, travel, springs, set } }] }
import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '..');
globalThis.window = globalThis;
const load = p => new Function(fs.readFileSync(p, 'utf8'))();
load(path.join(root, 'puppet/loader/puppet.js')); load(path.join(root, 'puppet/loader/acting.js'));
const LIBS = Object.fromEntries(fs.readdirSync(path.join(root, 'puppet/clips')).filter(f => f.endsWith('.json')).map(f => [f.replace('.json', ''), JSON.parse(fs.readFileSync(path.join(root, 'puppet/clips', f), 'utf8'))]));
const [specPath, outPath] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const base = path.dirname(path.resolve(specPath));
const [W, H] = spec.size || [1080, 1920];
const out = { fps: spec.fps || 30, frames: spec.frames, start: spec.start || 0, cast: [] };
// Characters may reach for or look at each other (WP-11): every frame is evaluated in two passes, first without
// targets on other characters, then those that have them against everyone's first-pass pose (as the SVG player does).
const CAST = spec.cast.map(c => {
  const pp = path.resolve(base, c.puppet), puppet = JSON.parse(fs.readFileSync(pp, 'utf8'));
  const hip = (puppet.parts.hip && puppet.parts.hip.pivot) || [puppet.artboard[0] / 2, puppet.ground];
  const tl = { ...(c.timeline || {}) };
  if (c.place && c.place.path && tl.pins && tl.travel == null) tl.travel = { path: c.place.path };   // planted feet on a path walk
  return { c, pp, puppet, hip, tl, LIB: LIBS[puppet.template] || LIBS.humanoid, cross: Acting.crossRefs(tl), frames: [] };
});
const toLocal = (k, w, x, y, s, flip) => [(w[0] - x) / (s * flip) + k.hip[0], (w[1] - y) / s + k.puppet.ground];
for (let f = 0; f < spec.frames; f++) {
  let t = out.start + f / out.fps;
  if (spec.step) t = Math.floor(t * spec.step + 1e-6) / spec.step;   // animate on 12s like the player
  const now = CAST.map(k => {
    const [x, y, s, flip] = Acting.placeAt(k.c.place, t);
    const loc = w => toLocal(k, w, x, y, s, flip);
    return { k, x, y, s, flip, loc, pose: Acting.evaluate(k.puppet, Acting.resolveTargets(k.tl, t, loc, () => null), t, k.LIB.clips, k.LIB.presets) };
  });
  const worldOf = tg => { const o = now[tg.cast]; return o ? Puppet.pointOf(o.k.puppet, tg.part, tg.at || null, o.x, o.y, { ...o.pose, s: o.s, flip: o.flip }) : null; };
  const poses = now.map(o => o.k.cross ? Acting.evaluate(o.k.puppet, Acting.resolveTargets(o.k.tl, t, o.loc, worldOf), t, o.k.LIB.clips, o.k.LIB.presets) : o.pose);
  now.forEach((o, i) => {
    const pose = poses[i], puppet = o.k.puppet;
    let { x, y, s, flip } = o;
    if (spec.camera) { // fold the shot camera [cx, cy, zoom] into the placement so every renderer frames it identically
      const [cx, cy, z] = Acting.sampleKeys(spec.camera, t) || [W / 2, H / 2, 1];
      x = W / 2 + (x - cx) * z; y = H / 2 + (y - cy) * z; s *= z;
    }
    o.k.frames.push({ x, y, s, flip, angles: pose.angles, offset: pose.offset || [0, 0], mouth: pose.mouth || null, eyes: pose.eyes || null, blink: pose.blink || 0,
      look: pose.look || null, brows: pose.brows || null, hand_R_pose: pose.hand_R_pose || null, view: pose.view || null, squash: pose.squash || 1, shifts: pose.shifts || null, scales: pose.scales || null, grow: pose.grow || null, z: pose.z || null,
      // every other swap set's drawing (drawn levels, control-driven swaps), so all renderers show the same one (WP-14)
      ...Object.fromEntries(Object.keys(puppet.swaps || {}).filter(k => !['mouth', 'eyes', 'brows', 'pupils', 'hand_R_pose'].includes(k) && pose[k] != null).map(k => [k, pose[k]])) });
  });
}
for (const k of CAST) out.cast.push({ puppet: k.pp, name: k.puppet.name, frames: k.frames });
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`baked ${out.cast.length} puppet(s) x ${spec.frames} frames -> ${outPath}`);
