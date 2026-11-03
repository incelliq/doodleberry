// Sticker frames (WP-23): a character's baked move on a transparent square canvas, framed to the whole move.
//   node tools/sticker_frames.mjs SPEC.json
// SPEC: {puppet: "path.puppet.json", baked: "path/baked.json" (tools/bake.mjs, placed at the artboard: hip on its
//        pivot, scale 1), size: 512, margin: 0.06, out: "dir"}
//   -> dir/f0000.png ... and prints {frames, place: {x, y, s}, box}: where the hip and ground land on the canvas, so
//      the Lottie bake can be placed the same way. Frames are drawn from the baked poses, as every renderer is.
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path';
const { chromium } = createRequire(import.meta.url)('playwright');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const P = JSON.parse(fs.readFileSync(path.resolve(root, spec.puppet), 'utf8'));
const baked = JSON.parse(fs.readFileSync(path.resolve(root, spec.baked), 'utf8'));
const frs = baked.cast[0].frames, size = spec.size || 512, margin = spec.margin ?? 0.06;
fs.mkdirSync(spec.out, { recursive: true });
const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: size, height: size } });
await pg.setContent(`<html><body style="margin:0;background:transparent"><svg id="s" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"></svg><svg id="m" width="1" height="1" style="position:absolute;left:-9999px"></svg></body></html>`);
await pg.addScriptTag({ path: path.join(root, 'puppet/loader/puppet.js') });
const pose = fr => ({ angles: fr.angles, offset: fr.offset, mouth: fr.mouth, eyes: fr.eyes, blink: fr.blink, brows: fr.brows, look: fr.look, view: fr.view || undefined,
  squash: fr.squash, shifts: fr.shifts || undefined, scales: fr.scales || undefined, z: fr.z || undefined, hand_R_pose: fr.hand_R_pose || undefined, flip: fr.flip });
const poses = frs.map(pose);
// the box the move fills, as baked (hip on its pivot, scale 1)
const box = await pg.evaluate(([P, frs, poses]) => {
  const m = document.getElementById('m'); let box = null;
  frs.forEach((fr, i) => { m.innerHTML = Puppet.render(P, fr.x, fr.y, { s: fr.s, ...poses[i] }); const r = m.getBBox();
    box = box ? [Math.min(box[0], r.x), Math.min(box[1], r.y), Math.max(box[2], r.x + r.width), Math.max(box[3], r.y + r.height)] : [r.x, r.y, r.x + r.width, r.y + r.height]; });
  return box;
}, [P, frs, poses]);
const [x0, y0, x1, y1] = box, s = (1 - 2 * margin) * size / Math.max(x1 - x0, y1 - y0), fr0 = frs[0];
const place = { x: size / 2 + (fr0.x - (x0 + x1) / 2) * s, y: size / 2 + (fr0.y - (y0 + y1) / 2) * s, s: s * fr0.s };
for (let f = 0; f < frs.length; f++) {
  await pg.evaluate(([P, fr, po, place, k]) => { document.getElementById('s').innerHTML = Puppet.render(P, place.x + (fr.x - k.x0) * k.s, place.y + (fr.y - k.y0) * k.s, { ...po, s: fr.s * k.s }); },
    [P, frs[f], poses[f], place, { x0: fr0.x, y0: fr0.y, s }]);
  await (await pg.$('#s')).screenshot({ path: path.join(spec.out, `f${String(f).padStart(4, '0')}.png`), omitBackground: true });
}
await b.close();
console.log(JSON.stringify({ frames: frs.length, fps: baked.fps, size, place, box }));
