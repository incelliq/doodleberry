// Bake puppet acting to a renderer-neutral animation: per frame, every part's local angle, the root offset and the
// swap choices, plus where each puppet stands. Synfig, Grease Pencil and Lottie exporters read this file.
//   node tools/bake.mjs SPEC.json OUT.json
// SPEC: { fps, frames, start, size, camera: [[t, [cx, cy, zoom]]], cast: [{ puppet: "path.puppet.json", place: {x, y, s, flip} | [[t, {x,y,s,flip}]...],
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
for (const c of spec.cast) {
  const pp = path.resolve(base, c.puppet), puppet = JSON.parse(fs.readFileSync(pp, 'utf8'));
  const placeAt = t => Array.isArray(c.place) ? Acting.sampleKeys(c.place.map(([k, v]) => [k, [v.x, v.y, v.s ?? 1, v.flip ?? 1]]), t) : [c.place.x, c.place.y, c.place.s ?? 1, c.place.flip ?? 1];
  const frames = [];
  for (let f = 0; f < spec.frames; f++) {
    let t = out.start + f / out.fps;
    if (spec.step) t = Math.floor(t * spec.step + 1e-6) / spec.step;   // animate on 12s like the player
    const LIB = LIBS[puppet.template] || LIBS.humanoid;
    let [x, y, s, flip] = placeAt(t);
    const tl = { ...(c.timeline || {}) };
    if (tl.lookat) {  // frame-space targets [x, y] -> artboard space (targets on other characters are SVG-player only)
      const hip = (puppet.parts.hip && puppet.parts.hip.pivot) || [puppet.artboard[0] / 2, puppet.ground];
      tl.lookat = [].concat(tl.lookat).map(la => Array.isArray(la.target) ? { ...la, target_local: [(la.target[0] - x) / (s * flip) + hip[0], (la.target[1] - y) / s + puppet.ground] } : la);
    }
    const pose = Acting.evaluate(puppet, tl, t, LIB.clips, LIB.presets);
    if (spec.camera) { // fold the shot camera [cx, cy, zoom] into the placement so every renderer frames it identically
      const [cx, cy, z] = Acting.sampleKeys(spec.camera, t) || [W / 2, H / 2, 1];
      x = W / 2 + (x - cx) * z; y = H / 2 + (y - cy) * z; s *= z;
    }
    frames.push({ x, y, s, flip, angles: pose.angles, offset: pose.offset || [0, 0], mouth: pose.mouth || null, eyes: pose.eyes || null, blink: pose.blink || 0,
      look: pose.look || null, brows: pose.brows || null, hand_R_pose: pose.hand_R_pose || null, view: pose.view || null, squash: pose.squash || 1, shifts: pose.shifts || null, z: pose.z || null,
      // every other swap set's drawing (drawn levels, control-driven swaps), so all renderers show the same one (WP-14)
      ...Object.fromEntries(Object.keys(puppet.swaps || {}).filter(k => !['mouth', 'eyes', 'brows', 'pupils', 'hand_R_pose'].includes(k) && pose[k] != null).map(k => [k, pose[k]])) });
  }
  out.cast.push({ puppet: pp, name: puppet.name, frames });
}
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`baked ${out.cast.length} puppet(s) x ${spec.frames} frames -> ${outPath}`);
