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
// the shot's clock: film time for frame f; in a time-warped cut (the sound-off cut, plan 2.13) frames run on the cut's
// clock from cut_start, each showing the film at the warped time, as the player's renderFrame does (WP-14)
const WK = spec.timewarp && spec.timewarp.length > 1 ? spec.timewarp : null;
const lerpK = (k, i, j, v) => { if (v <= k[0][i]) return k[0][j] + (v - k[0][i]); for (let n = 1; n < k.length; n++) if (v <= k[n][i]) { const a = k[n - 1], b = k[n]; return a[j] + (b[j] - a[j]) * (v - a[i]) / ((b[i] - a[i]) || 1); } return k[k.length - 1][j] + (v - k[k.length - 1][i]); };
const tAt = f => { let t = WK ? lerpK(WK, 0, 1, (spec.cut_start ?? lerpK(WK, 1, 0, out.start)) + f / out.fps) : out.start + f / out.fps;
  if (spec.step) t = Math.floor(t * spec.step + 1e-6) / spec.step;   // animate on 12s like the player
  return t; };
const toLocal = (k, w, x, y, s, flip) => [(w[0] - x) / (s * flip) + k.hip[0], (w[1] - y) / s + k.puppet.ground];
for (let f = 0; f < spec.frames; f++) {
  const t = tAt(f);
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
// Props (WP-14): each prop becomes a small puppet (its drawing as in dbe/player/props.js: a ball or a box) with a frame
// per frame (position, spin, the camera folded in), appended after the characters so every renderer that draws baked
// puppets draws it on top of them. Squash, stretch and smear frames are SVG-only (rparity lists them as degraded);
// props with their own SVG drawing are SVG-only.
if ((spec.props || []).length || spec.fx) {
  load(path.join(root, 'dbe/player/props.js'));
  const INK = '#181e26', f2 = v => (+v).toFixed(2);
  const memo = {};
  const poseAt = (ci, tt) => {   // a character at any time, as the player's propCtx evaluates it (no cross targets)
    const k = CAST[ci]; if (!k) return null; const key = ci + ':' + tt.toFixed(4);
    if (!memo[key]) { const [x, y, s, flip] = Acting.placeAt(k.c.place, tt); const tl2 = { ...k.tl }; delete tl2.lookat;
      const tl3 = Acting.resolveTargets(tl2, tt, w => toLocal(k, w, x, y, s, flip), () => null);
      memo[key] = { x, y, s, flip, pose: Acting.evaluate(k.puppet, tl3, tt, k.LIB.clips, k.LIB.presets) }; }
    return memo[key];
  };
  const ctx = { fps: out.fps, poseAt, at: (tg, tt) => { if (!tg) return null; if (Array.isArray(tg)) return tg; if (tg.x != null && tg.cast == null) return [tg.x, tg.y];
    const c = poseAt(tg.cast, tt); return c ? Puppet.pointOf(CAST[tg.cast].puppet, tg.part, tg.at || null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip }) : null; } };
  spec.props.forEach((pr, i) => {
    if (pr.svg) return;   // a drawing of its own: the SVG renderer only
    const r = pr.r || 34, box = pr.shape === 'box', [w, h] = box ? (pr.size || [2 * r, 2 * r]) : [2 * r, 2 * r], pad = 8;
    const cx = w / 2 + pad, cy = h / 2 + pad;
    const strokes = box
      ? [{ d: `M${f2(cx - w / 2 + 6)} ${f2(cy - h / 2)} H${f2(cx + w / 2 - 6)} A6 6 0 0 1 ${f2(cx + w / 2)} ${f2(cy - h / 2 + 6)} V${f2(cy + h / 2 - 6)} A6 6 0 0 1 ${f2(cx + w / 2 - 6)} ${f2(cy + h / 2)} H${f2(cx - w / 2 + 6)} A6 6 0 0 1 ${f2(cx - w / 2)} ${f2(cy + h / 2 - 6)} V${f2(cy - h / 2 + 6)} A6 6 0 0 1 ${f2(cx - w / 2 + 6)} ${f2(cy - h / 2)} Z`, fill: 'body', stroke: 'ink', width: 5 },
         { d: `M${f2(cx - w / 2 + 8)} ${f2(cy - h / 2 + 10)} L${f2(cx + w / 2 - 8)} ${f2(cy - h / 2 + 10)}`, fill: 'none', stroke: 'shine', width: 4, opacity: 0.5 }]
      : [{ d: `M${f2(cx - r)} ${f2(cy)} A${r} ${r} 0 1 0 ${f2(cx + r)} ${f2(cy)} A${r} ${r} 0 1 0 ${f2(cx - r)} ${f2(cy)} Z`, fill: 'body', stroke: 'ink', width: 5 },
         { d: `M${f2(cx - r)} ${f2(cy)} Q${f2(cx)} ${f2(cy + r * 0.5)} ${f2(cx + r)} ${f2(cy)} M${f2(cx)} ${f2(cy - r)} Q${f2(cx + r * 0.45)} ${f2(cy)} ${f2(cx)} ${f2(cy + r)}`, fill: 'none', stroke: 'ink', width: 3, opacity: 0.55 }];
    const pz = { format: 'doodleberry.puppet', version: '0.12', name: `prop ${pr.id || i}`, template: 'doodle', artboard: [w + 2 * pad, h + 2 * pad], ground: cy,
      palette: { ink: INK, body: pr.color || '#e8603c', shine: '#ffffff' },
      parts: { hip: { parent: null, pivot: [cx, cy], z: 0, strokes: [] }, body: { parent: 'hip', pivot: [cx, cy], z: 1, strokes } }, swaps: {},
      meta: { prop: pr.id || i, generated_by: 'tools/bake.mjs' } };
    const pp = outPath.replace(/\.json$/, '') + `.prop${i}.puppet.json`; fs.writeFileSync(pp, JSON.stringify(pz));
    const frames = [];
    for (let f = 0; f < spec.frames; f++) {
      const t = tAt(f);
      const info = {}, p = PROPS.pos(pr, t, ctx, info);
      let x = p ? p[0] : -10000, y = p ? p[1] : -10000, s = p ? 1 : 0.0001;
      const spin = p ? (info.spin != null ? info.spin : (pr.spin ? t * pr.spin : 0)) : 0;
      if (spec.camera && p) { const [ccx, ccy, z] = Acting.sampleKeys(spec.camera, t) || [W / 2, H / 2, 1]; x = W / 2 + (x - ccx) * z; y = H / 2 + (y - ccy) * z; s *= z; }
      frames.push({ x, y, s, flip: 1, angles: { body: spin }, offset: [0, 0], mouth: null, eyes: null, blink: 0, look: null, brows: null, hand_R_pose: null, view: null, squash: 1, shifts: null, scales: null, grow: null, z: null, hidden: !p });
    }
    out.cast.push({ puppet: pp, name: pz.name, prop: pr.id || i, frames });
  });
  if (spec.fx) {   // motion effects (WP-14): each frame's drawing, in world coordinates, as the player's FX.render makes it
    load(path.join(root, 'dbe/player/fx.js'));
    const shot = { fx: spec.fx, props: spec.props || [], start: out.start };
    const pointAt = (ci, part, tt) => { if (tt < out.start) return null; const c = poseAt(ci, tt); return c ? Puppet.pointOf(CAST[ci].puppet, part, null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip }) : null; };
    out.fx = { frames: [], camera: [] };
    for (let f = 0; f < spec.frames; f++) {
      const t = tAt(f);
      const casts = CAST.map(k => { const [x, y, s, flip] = Acting.placeAt(k.c.place, t); return { p: k.puppet, x, y, s, flip, c: k.c }; });   // as the player's casts (dust reads x, y)
      out.fx.frames.push(FX.render(shot, t, { casts, pointAt, propPos: (pr, tt, info) => PROPS.pos(pr, tt, ctx, info), pctx: ctx }));
      out.fx.camera.push(spec.camera ? (Acting.sampleKeys(spec.camera, t) || [W / 2, H / 2, 1]) : [W / 2, H / 2, 1]);
    }
  }
}
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`baked ${out.cast.length} puppet(s) and prop(s) x ${spec.frames} frames -> ${outPath}`);
