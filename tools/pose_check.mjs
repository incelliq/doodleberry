// Rig Canvas posing check (plan 3.3): load Ravi, drag his right hand up (IK), turn his head, crouch (feet stay
// planted), set mouth and brows, save the pose "hooray", key rest + hooray and save the clip "cheer_up".
//   node tools/pose_check.mjs OUT_DIR   (writes pose_shot.png and ravi_posed.puppet.json)
import { createRequire } from 'module'; import path from 'path'; import fs from 'fs';
const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const out = process.argv[2];
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto('file://' + path.resolve('puppet/canvas/index.html'));
await p.evaluate(pz => window.RIG.load(pz), JSON.parse(fs.readFileSync('cast/generated/ravi.puppet.json', 'utf8')));
await p.click('#t-pose');
const toPage = async q => p.evaluate(([x, y]) => { const svg = document.getElementById('draw'); const pt = svg.createSVGPoint(); pt.x = x; pt.y = y; const r = pt.matrixTransform(svg.getScreenCTM()); return [r.x, r.y]; }, q);
const drag = async (from, to, shift) => { const a = await toPage(from), z = await toPage(to); if (shift) await p.keyboard.down('Shift');
  await p.mouse.move(a[0], a[1]); await p.mouse.down(); for (let i = 1; i <= 8; i++) await p.mouse.move(a[0] + (z[0] - a[0]) * i / 8, a[1] + (z[1] - a[1]) * i / 8); await p.mouse.up(); if (shift) await p.keyboard.up('Shift'); };
const H = await p.evaluate(() => Object.fromEntries(window.RIG.handles().map(h => [h.id, h.at])));
// raise the right hand above the head, tilt the head, crouch a little
const target = [H.head[0] - 160, H.head[1] - 40];
await drag(H.hand_R, target); await drag(H.head, [H.head[0] + 40, H.head[1] + 10]); await drag(H.hip, [H.hip[0], H.hip[1] + 40]);
await p.selectOption('#p-mouth', 'wide'); await p.selectOption('#p-brows', 'raised');
p.once('dialog', d => d.accept('hooray'));
await p.click('#p-save');
await p.waitForTimeout(300);
const res = await p.evaluate(() => { const P = window.RIG.puppet; return { pose: P.poses && P.poses.hooray, hand: window.RIG.handles().find(h => h.id === 'hand_R').at }; });
// check the saved pose reproduces the hand position when evaluated as a timeline pose (as films use it)
const check = await p.evaluate(() => { const P = window.RIG.puppet; const L = window.CLIPLIB.humanoid;
  const pose = Acting.evaluate(P, { poses: [[0, 'hooray']], blink: false, springs: false }, 1, L.clips, L.presets);
  return Puppet.pointOf(P, 'hand_R', null, P.parts.hip.pivot[0], P.ground, pose); });
await p.screenshot({ path: out + '/pose_shot.png' });
// record a two-key clip: rest at 0, hooray at 0.6
await p.click('#p-reset'); await p.fill('#p-t', '0'); await p.click('#p-key');
await p.selectOption('#p-load', 'hooray'); await p.fill('#p-t', '0.6'); await p.click('#p-key');
p.once('dialog', d => d.accept('cheer_up'));
await p.click('#p-clip'); await p.waitForTimeout(300);
const clip = await p.evaluate(() => window.RIG.puppet.clips && window.RIG.puppet.clips.cheer_up);
fs.writeFileSync(out + '/ravi_posed.puppet.json', JSON.stringify(await p.evaluate(() => window.RIG.puppet)));
console.log(JSON.stringify({ target, hand_after_drag: res.hand, hand_from_saved_pose: check, pose: res.pose, clip_parts: clip && Object.keys(clip.tracks), clip_dur: clip && clip.duration, errs }));
await b.close();
