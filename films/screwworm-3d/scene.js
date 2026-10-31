// "What happens if a fly lays its eggs in your cut?" — 3D short.
// three.js (r160) in headless Chromium; CC0 characters (Quaternius Universal Base Characters + UAL clips + CMU mocap
// retargeted by tools/blender/cmu_retarget.py); every prop (fly, eggs, maggots, plane, set) is built here in code.
// Every frame is a pure function of the frame number.
import * as THREE from 'three';
import { GLTFLoader } from '../../engine/vendor/three/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from '../../engine/vendor/three/jsm/environments/RoomEnvironment.js';

const W = 1080, H = 1920, FPS = 30;
const TIMING = window.TIMING;
const L = Object.fromEntries(TIMING.lines.map(l => [l.id, l]));
const norm = s => s.toLowerCase().replace(/[^a-z0-9']/g, '');
const at = (line, word, frac = 0.5) => { const w = L[line].words.find(w => norm(w.text) === norm(word)); return w ? w.start : L[line].start + (L[line].end - L[line].start) * frac; };
const END = L.end.end + 2.2;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const inv = (a, b, x) => clamp((x - a) / (b - a));
const lerp = (a, b, k) => a + (b - a) * k;
const ease = k => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
const spring = (t, f = 2.6, d = 0.5) => { if (t <= 0) return 0; const w = 2 * Math.PI * f, wd = w * Math.sqrt(1 - d * d); return 1 - Math.exp(-d * w * t) * (Math.cos(wd * t) + (d * w / wd) * Math.sin(wd * t)); };
const hash = n => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };

// ---------- renderer ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(W, H); renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.insertBefore(renderer.domElement, document.body.firstChild);
const scene = new THREE.Scene();
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture; // soft studio reflections so metals aren't black
const cam = new THREE.PerspectiveCamera(32, W / H, 0.005, 200);
const sun = new THREE.DirectionalLight('#ffe2b8', 3.0); sun.position.set(-6, 7, 5); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 4; sun.shadow.bias = -0.0004;
Object.assign(sun.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 0.5, far: 30 }); scene.add(sun);
const rim = new THREE.DirectionalLight('#8fb8ff', 1.6); rim.position.set(5, 3, -5); scene.add(rim);
const hemi = new THREE.HemisphereLight('#cfe6ff', '#b0886a', 0.5); scene.add(hemi);
const std = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.7, ...o });
const mesh = (geo, mat, parent, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; (parent || scene).add(m); return m; };
const canvasTex = (w, h, draw, repeat) => { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat, repeat); } return t; };

// ---------- sets ----------
// lakeshore at golden hour: sky dome, water, sand, palms, a driftwood log
const beach = new THREE.Group(); scene.add(beach);
const skyTex = canvasTex(8, 512, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#3b6fb6'); gr.addColorStop(0.45, '#9cc3e8'); gr.addColorStop(0.62, '#ffd6a0'); gr.addColorStop(1, '#ffb27a'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
const sky = new THREE.Mesh(new THREE.SphereGeometry(80, 32, 16), new THREE.MeshBasicMaterial({ map: skyTex, side: THREE.BackSide, fog: false })); scene.add(sky);
const sand = mesh(new THREE.PlaneGeometry(60, 60), std('#e3c99a', { map: canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#e8cfa0'; g.fillRect(0, 0, w, h); for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(${150 + hash(i) * 60},${120 + hash(i + 1) * 50},${80 + hash(i + 2) * 40},0.35)`; g.fillRect(hash(i + 3) * w, hash(i + 4) * h, 2, 2); } }, 14), roughness: 0.95 }), beach);
sand.rotation.x = -Math.PI / 2;
const water = new THREE.Mesh(new THREE.PlaneGeometry(80, 40), new THREE.MeshStandardMaterial({ color: '#3f8fb0', roughness: 0.15, metalness: 0.2, transparent: true, opacity: 0.95 }));
water.rotation.x = -Math.PI / 2; water.position.set(0, 0.02, -24); water.receiveShadow = true; beach.add(water);
function palm(x, z, h, lean, seed) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.z = lean; beach.add(g);
  for (let i = 0; i < 9; i++) mesh(new THREE.CylinderGeometry(0.11 - i * 0.006, 0.13 - i * 0.006, h / 9, 10), std('#8a6a4a'), g, Math.sin(i * 0.35) * 0.25 * (i / 9), (i + 0.5) * h / 9, 0);
  for (let k = 0; k < 8; k++) {
    const leaf = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 0.42, 6, 1), std('#4f8f3a', { side: THREE.DoubleSide, roughness: 0.8 }));
    const pos = leaf.geometry.attributes.position; for (let i = 0; i < pos.count; i++) { const u = (pos.getX(i) + 1.1) / 2.2; pos.setY(i, pos.getY(i) * (1 - u * 0.7)); pos.setZ(i, -u * u * 0.9); }
    leaf.geometry.computeVertexNormals(); leaf.castShadow = true;
    const holder = new THREE.Group(); holder.position.set(0.25, h, 0); holder.rotation.set(0, k * Math.PI / 4 + seed, -0.35); leaf.position.x = 1.1; holder.add(leaf); g.add(holder);
  }
}
palm(-3.2, -3.5, 5.5, 0.12, 0); palm(3.8, -5, 6.2, -0.18, 1); palm(-6, -7, 5, 0.05, 2); palm(1.2, -9, 5.8, 0.1, 3);
const log = mesh(new THREE.CylinderGeometry(0.2, 0.22, 2.4, 14), std('#9b7b5a', { roughness: 0.95 }), beach, 0, 0.2, -0.08); log.rotation.z = Math.PI / 2;

// ranchland seen from the air (for the sterile-fly drop)
const ranch = new THREE.Group(); scene.add(ranch);
const fields = mesh(new THREE.PlaneGeometry(400, 400), std('#c9b77a', { map: canvasTex(512, 512, (g, w, h) => { for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) { g.fillStyle = ['#c9b77a', '#a9a85e', '#d6c38c', '#8f9b52'][(i * 3 + j * 5) % 4]; g.fillRect(i * 64, j * 64, 64, 64); } g.strokeStyle = 'rgba(80,60,40,0.4)'; g.lineWidth = 2; for (let i = 0; i <= 8; i++) { g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, h); g.stroke(); g.beginPath(); g.moveTo(0, i * 64); g.lineTo(w, i * 64); g.stroke(); } }, 6), roughness: 1 }), ranch);
fields.rotation.x = -Math.PI / 2;
for (let i = 0; i < 70; i++) { const tr = mesh(new THREE.SphereGeometry(1.4 + hash(i) * 1.2, 8, 6), std('#5f7f3a'), ranch, (hash(i + 7) - 0.5) * 160, 1.2, (hash(i + 11) - 0.5) * 160 - 30); tr.scale.y = 0.7; }

// the map: our Natural Earth map drawn onto a tilted board
const mapG = new THREE.Group(); scene.add(mapG);
const MAPW = 4, MAPH = 4 * window.MAP.h / window.MAP.w;
let mapTex;
async function buildMap() {
  const M = window.MAP;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="${Math.round(2000 * M.h / M.w)}" viewBox="0 0 ${M.w} ${M.h}"><rect width="100%" height="100%" fill="#7fc0e0"/>`;
  svg += `<path d="${Object.values(M.countries).join('')}" fill="#efe1bd" stroke="#3a2a1a" stroke-width="1.6" stroke-linejoin="round"/>`;
  svg += `<path d="${Object.values(M.states).join('')}" fill="none" stroke="#b49a6a" stroke-width="0.8"/>`;
  svg += `<path d="${M.countries.nicaragua}" fill="#e25b4a" opacity="0.6"/>`;
  for (const s of ['Texas', 'New Mexico', 'Arizona']) svg += `<path d="${M.states[s]}" fill="#e25b4a" opacity="0.45"/>`;
  svg += `<path d="${M.countries.usa}" fill="none" stroke="#3a2a1a" stroke-width="1.6"/></svg>`;
  const img = new Image(); img.src = 'data:image/svg+xml;base64,' + btoa(svg); await img.decode();
  const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
  mapTex = new THREE.CanvasTexture(c); mapTex.colorSpace = THREE.SRGBColorSpace; mapTex.anisotropy = 8;
  const board = mesh(new THREE.BoxGeometry(MAPW, 0.06, MAPH), [std('#6b4a30'), std('#6b4a30'), new THREE.MeshStandardMaterial({ map: mapTex, roughness: 0.8 }), std('#6b4a30'), std('#6b4a30'), std('#6b4a30')], mapG);
  mesh(new THREE.PlaneGeometry(40, 40), std('#2c3440', { roughness: 0.9 }), mapG, 0, -0.04, 0).rotation.x = -Math.PI / 2;
}
const mapXY = (lon, lat) => { const [x, y] = window.MAP.xy(lon, lat); return new THREE.Vector3((x / window.MAP.w - 0.5) * MAPW, 0.035, (y / window.MAP.h - 0.5) * MAPH); };
const pins = [];
function pin(lon, lat, col, h = 0.25, r = 0.03) {
  const g = new THREE.Group(); g.position.copy(mapXY(lon, lat)); mapG.add(g);
  mesh(new THREE.CylinderGeometry(0.008, 0.008, h, 8), std('#ddd'), g, 0, h / 2, 0);
  mesh(new THREE.SphereGeometry(r, 14, 10), std(col, { emissive: col, emissiveIntensity: 0.35 }), g, 0, h, 0);
  pins.push(g); return g;
}
const nicPin = pin(-85.2, 12.9, '#e2463a', 0.4);
const casePins = [];
for (let i = 0; i < 71; i++) {
  const lon = i === 70 ? -109.9 : i % 9 === 4 ? -104.2 - hash(i) * 2.5 : -100.6 + (hash(i + 11) - 0.3) * 2.8;
  const lat = i === 70 ? 31.8 : i % 9 === 4 ? 32.1 + hash(i + 3) * 1.2 : 27.4 + hash(i + 17) * 2.3;
  casePins.push(pin(lon, lat, '#e2463a', 0.05 + hash(i + 5) * 0.06, 0.011));
}

// ---------- props built in code ----------
function makeFly(sterile = false) {
  const g = new THREE.Group();
  const body = sterile ? '#8e9aa6' : '#1f8fa0';
  const metal = new THREE.MeshStandardMaterial({ color: body, metalness: 0.75, roughness: 0.25 });
  const stripes = canvasTex(256, 128, (c, w, h) => { c.fillStyle = body; c.fillRect(0, 0, w, h); c.fillStyle = sterile ? '#59636e' : '#0f3e52'; for (const x of [0.36, 0.5, 0.64]) c.fillRect(x * w - 7, 0, 14, h); });
  mesh(new THREE.SphereGeometry(0.5, 24, 16), new THREE.MeshStandardMaterial({ map: stripes, metalness: 0.7, roughness: 0.3 }), g, 0, 0, 0).scale.set(1, 0.9, 1.05);
  const abd = mesh(new THREE.SphereGeometry(0.55, 24, 16), metal, g, 0, -0.05, -0.85); abd.scale.set(0.95, 0.85, 1.25);
  if (sterile) { const band = mesh(new THREE.TorusGeometry(0.52, 0.07, 8, 24), std('#ffd84a', { emissive: '#ffb000', emissiveIntensity: 0.3 }), g, 0, -0.05, -0.85); band.scale.set(1, 0.85, 1); }
  const head = mesh(new THREE.SphereGeometry(0.36, 20, 14), std(sterile ? '#9a8a80' : '#7a5a3a'), g, 0, 0.05, 0.6);
  const eyeMat = new THREE.MeshStandardMaterial({ color: sterile ? '#b9a29a' : '#e2552c', roughness: 0.3, emissive: sterile ? '#000' : '#5a1000', emissiveIntensity: 0.4 });
  for (const s of [-1, 1]) mesh(new THREE.SphereGeometry(0.27, 20, 14), eyeMat, g, s * 0.24, 0.12, 0.72);
  const wingMat = new THREE.MeshStandardMaterial({ color: '#dff3ff', transparent: true, opacity: 0.35, roughness: 0.1, side: THREE.DoubleSide });
  g.userData.wings = [-1, 1].map(s => { const pv = new THREE.Group(); pv.position.set(s * 0.25, 0.4, -0.1); const wing = new THREE.Mesh(new THREE.CircleGeometry(0.75, 20), wingMat); wing.scale.set(0.55, 1, 1); wing.position.set(s * 0.6, 0, -0.35); wing.rotation.x = -Math.PI / 2; pv.add(wing); g.add(pv); return { pv, s }; });
  for (let i = 0; i < 3; i++) for (const s of [-1, 1]) { const leg = mesh(new THREE.CylinderGeometry(0.03, 0.02, 0.9, 6), std('#1a2a30'), g, s * 0.45, -0.45, 0.35 - i * 0.35); leg.rotation.z = s * 0.7; }
  return g;
}
const flapFly = (fly, t, amt = 1) => { for (const { pv, s } of fly.userData.wings) pv.rotation.z = s * (0.25 + amt * 0.55 * Math.sin(t * 2 * Math.PI * 18)); };
function makeMaggot() {
  const g = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: '#f4e7c8', roughness: 0.55, emissive: '#000000' });
  const bodyM = mesh(new THREE.CapsuleGeometry(0.22, 0.9, 6, 14), mat, g); bodyM.rotation.x = Math.PI / 2;
  for (let i = 0; i < 7; i++) { const r = mesh(new THREE.TorusGeometry(0.215 - Math.abs(i - 3) * 0.012, 0.035, 6, 18), new THREE.MeshStandardMaterial({ color: '#c9b285', roughness: 0.6 }), g, 0, 0, -0.42 + i * 0.14); r.rotation.y = 0.25; }
  g.userData.mats = [mat];
  return g;
}
const egg = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.0006, 0.0019, 3, 6), std('#fffaf0', { roughness: 0.4 }), 120); egg.count = 0; scene.add(egg);
const woundTex = canvasTex(256, 256, (g, w, h) => { g.translate(w / 2, h / 2); g.beginPath(); for (let i = 0; i <= 40; i++) { const a = (i / 40) * Math.PI * 2, r = 70 * (1 + (hash(i * 3.1) - 0.5) * 0.5) * (1 + 0.25 * Math.sin(a * 2)); g.lineTo(Math.cos(a) * r * 1.35, Math.sin(a) * r * 0.75); } g.closePath();
  const gr = g.createRadialGradient(0, 0, 4, 0, 0, 95); gr.addColorStop(0, '#4a0d0c'); gr.addColorStop(0.55, '#8e2420'); gr.addColorStop(0.85, '#c4544a'); gr.addColorStop(1, 'rgba(214,120,110,0)'); g.fillStyle = gr; g.fill();
  for (let i = 0; i < 26; i++) { g.fillStyle = 'rgba(70,10,10,0.5)'; g.fillRect((hash(i) - 0.5) * 150, (hash(i + 9) - 0.5) * 70, 6, 2); } });
const scrape = new THREE.Mesh(new THREE.PlaneGeometry(0.03, 0.03), new THREE.MeshStandardMaterial({ map: woundTex, transparent: true, roughness: 0.35, polygonOffset: true, polygonOffsetFactor: -4, depthWrite: false })); scene.add(scrape);
const bandage = mesh(new THREE.BoxGeometry(0.032, 0.042, 0.003), std('#f6eee2', { roughness: 0.9 }), scene); bandage.visible = false;
const tweezers = new THREE.Group(); for (const s of [-1, 1]) { const arm = mesh(new THREE.BoxGeometry(0.004, 0.003, 0.12), std('#d8dce2', { metalness: 0.6, roughness: 0.3 }), tweezers, s * 0.004, 0, 0.06); arm.rotation.y = s * 0.05; } scene.add(tweezers); tweezers.visible = false;
const fly = makeFly(false); scene.add(fly);
const flyF = makeFly(false), flyM = makeFly(true); scene.add(flyF); scene.add(flyM);
const maggots = Array.from({ length: 5 }, () => { const m = makeMaggot(); scene.add(m); return m; });
const plane = (() => { const g = new THREE.Group(); const y = std('#f2c23a', { metalness: 0.2, roughness: 0.5 });
  mesh(new THREE.CapsuleGeometry(0.5, 3.4, 8, 16), y, g).rotation.z = Math.PI / 2;
  mesh(new THREE.BoxGeometry(1.6, 0.08, 6.5), y, g, 0.2, 0.55, 0);
  mesh(new THREE.BoxGeometry(0.6, 0.06, 2.2), y, g, -2.1, 0.1, 0); mesh(new THREE.BoxGeometry(0.6, 1.0, 0.06), y, g, -2.1, 0.5, 0);
  const prop = mesh(new THREE.BoxGeometry(0.05, 1.6, 0.14), std('#333'), g, 2.25, 0, 0); g.userData.prop = prop;
  ranch.add(g); return g; })();
const boxes = Array.from({ length: 8 }, () => mesh(new THREE.BoxGeometry(0.4, 0.3, 0.3), std('#d8b07a'), ranch));
const sterileSwarm = new THREE.InstancedMesh(new THREE.SphereGeometry(0.14, 6, 5), std('#9aa6b2', { metalness: 0.5, roughness: 0.4 }), 400); sterileSwarm.count = 0; ranch.add(sterileSwarm);
const eggsXF = new THREE.Group(); scene.add(eggsXF);
for (let i = 0; i < 18; i++) mesh(new THREE.CapsuleGeometry(0.035, 0.11, 4, 8), std('#e6e2da', { roughness: 0.5 }), eggsXF, (i % 6 - 2.5) * 0.09, 0.05, Math.floor(i / 6) * 0.1).rotation.x = Math.PI / 2;

// ---------- characters ----------
const loader = new GLTFLoader();
const load = u => new Promise((res, rej) => loader.load(u, res, undefined, rej));
const A = 'build/assets/';
const UBC = A + 'ubc/Universal Base Characters[Standard]/';
let CLIPS, man, xray = [];
async function person(files) {
  const holder = new THREE.Group(); scene.add(holder);
  const mixers = [], meshes = [];
  for (const f of files) {
    const g = await load(f);
    g.scene.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; o.frustumCulled = false; meshes.push(o); o.userData.mat0 = o.material; } });
    holder.add(g.scene); mixers.push(new THREE.AnimationMixer(g.scene));
  }
  return { holder, mixers, meshes };
}
function play(p, name, lt, loop) {
  const clip = CLIPS[name];
  for (const m of p.mixers) { m.stopAllAction(); const a = m.clipAction(clip); a.reset(); a.play(); a.time = loop ? lt % clip.duration : Math.min(lt, clip.duration - 1e-3); m.update(0); }
}
const xrayMat = new THREE.MeshPhysicalMaterial({ color: '#8fd8ff', emissive: '#2a6fdf', emissiveIntensity: 0.9, transparent: true, opacity: 0.42, roughness: 0.2, depthWrite: false, side: THREE.DoubleSide });
const tibia = mesh(new THREE.CylinderGeometry(0.008, 0.009, 0.36, 10), new THREE.MeshStandardMaterial({ color: '#dfe8f6', emissive: '#6f9fdf', emissiveIntensity: 0.25, transparent: true, opacity: 0.7 }), scene); tibia.visible = false;

// ---------- shots ----------
const SH = [
  { id: 'beach', t0: 0 },
  { id: 'eggs', t0: L.eggs.start - 0.2 },
  { id: 'xray', t0: L.burrow.start - 0.2 },
  { id: 'map', t0: L.rare.start - 0.3 },
  { id: 'doctor', t0: L.doctor.start - 0.2 },
  { id: 'cases', t0: L.back.start - 0.3 },
  { id: 'planes', t0: L.planes.start - 0.2 },
  { id: 'mates', t0: L.once.start - 0.2 },
  { id: 'end', t0: L.end.start - 0.3 },
];
SH.forEach((s, i) => { s.t1 = i < SH.length - 1 ? SH[i + 1].t0 : END; });
const shotAt = t => SH.reduce((a, s) => (t >= s.t0 ? s : a), SH[0]);

// limb points of the seated man, in world space
const V = () => new THREE.Vector3();
const bone = name => man.holder.getObjectByName(name);
function shinFrame() {
  const knee = bone('calf_r').getWorldPosition(V()), ankle = bone('foot_r').getWorldPosition(V());
  const along = ankle.clone().sub(knee).normalize();
  const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(man.holder.quaternion);
  const front = fwd.clone().sub(along.clone().multiplyScalar(fwd.dot(along))).normalize();
  const side = along.clone().cross(front).normalize();
  const p = knee.clone().lerp(ankle, 0.42);
  return { knee, ankle, along, front, side, p, surf: p.clone().add(front.clone().multiplyScalar(0.043)) };
}
function setXray(on) { for (const m of man.meshes) m.material = on ? xrayMat : m.userData.mat0; tibia.visible = on; }

function frame(f) {
  const t = f / FPS, sh = shotAt(t), lt = t - sh.t0;
  const show = { beach: ['beach', 'eggs', 'xray', 'doctor', 'end'].includes(sh.id), ranch: sh.id === 'planes', map: ['map', 'cases'].includes(sh.id), mates: sh.id === 'mates' };
  beach.visible = show.beach; sky.visible = show.beach || show.ranch; ranch.visible = show.ranch; mapG.visible = show.map;
  man.holder.visible = show.beach; scrape.visible = show.beach && sh.id !== 'xray';
  [fly, egg, tweezers, bandage, ...maggots].forEach(o => (o.visible = false));
  flyF.visible = flyM.visible = eggsXF.visible = show.mates;
  scene.background = new THREE.Color(show.map ? '#1d242e' : show.mates ? '#f2c4cf' : '#9cc3e8');
  scene.fog = show.map || show.mates ? null : new THREE.Fog('#ffd6b0', 18, 70);
  setXray(sh.id === 'xray');
  // the man: sits on the log the whole time, stands at the end
  man.holder.position.set(0, 0, 0.12); man.holder.rotation.y = 0;
  if (sh.id === 'end' && t > at('end', 'again') - 0.6) { const k = t - (at('end', 'again') - 0.6); if (k < CLIPS.Sitting_Exit.duration) play(man, 'Sitting_Exit', k, false); else play(man, 'Idle_Loop', k - CLIPS.Sitting_Exit.duration, true); }
  else play(man, 'Sitting_Idle_Loop', t, true);
  man.holder.updateMatrixWorld(true);
  const S = shinFrame();
  // scrape on the shin, facing out of the leg
  scrape.position.copy(S.surf); scrape.lookAt(S.surf.clone().add(S.front)); scrape.scale.setScalar(1);
  const tick = t;
  let camPos, camLook, fov = 32;
  if (sh.id === 'beach') {
    const tLand = at('alive', 'alive') - 0.2, tIn = 0.5;
    const k = ease(inv(0, L.alive.end, t));
    camPos = new THREE.Vector3(lerp(1.6, 0.55, k), lerp(1.25, 0.55, k), lerp(4.2, 1.15, k)); camLook = new THREE.Vector3(lerp(0, S.p.x, k), lerp(0.75, S.p.y, k), lerp(0, S.p.z, k));
    fly.visible = t > tIn; const s = 0.009; fly.scale.setScalar(s);
    if (t < tLand) { const u = t - tIn, r = lerp(0.9, 0.15, inv(tIn, tLand, t)); fly.position.copy(S.surf).add(new THREE.Vector3(Math.cos(u * 2.6) * r, 0.1 + Math.sin(u * 4) * 0.06 + r * 0.4, Math.sin(u * 2.6) * r)); fly.lookAt(fly.position.clone().add(new THREE.Vector3(-Math.sin(u * 2.6), 0, Math.cos(u * 2.6)))); flapFly(fly, t, 1); }
    else { fly.position.copy(S.surf).add(S.front.clone().multiplyScalar(0.006)); fly.lookAt(fly.position.clone().add(S.along.clone().negate())); fly.up.copy(S.front); flapFly(fly, t, 0.15); }
  } else if (sh.id === 'eggs') {
    camPos = S.surf.clone().add(S.front.clone().multiplyScalar(0.2)).add(S.side.clone().multiplyScalar(0.07)).add(new THREE.Vector3(0, 0.05, 0)); camLook = S.surf.clone(); fov = 30;
    fly.visible = true; fly.scale.setScalar(0.009); fly.position.copy(S.surf).add(S.front.clone().multiplyScalar(0.006)).add(S.along.clone().multiplyScalar(-0.012));
    fly.up.copy(S.front); fly.lookAt(fly.position.clone().add(S.along)); flapFly(fly, t, 0.1);
    const n = Math.round(110 * inv(at('eggs', 'lays') - 0.2, L.eggs.end, t)); egg.visible = true; egg.count = n;
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
    for (let i = 0; i < n; i++) { const a = (i / 110) * Math.PI * 1.6 + 0.4, r = 0.0105 + (i % 3) * 0.0016; const p = S.surf.clone().add(S.side.clone().multiplyScalar(Math.cos(a) * r)).add(S.along.clone().multiplyScalar(Math.sin(a) * r)).add(S.front.clone().multiplyScalar(0.001)); q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), S.along); m4.compose(p, q, new THREE.Vector3(1, 1, 1)); egg.setMatrixAt(i, m4); }
    egg.instanceMatrix.needsUpdate = true;
  } else if (sh.id === 'xray') {
    const tD = at('screw', 'disturb'), deeper = ease(inv(tD, tD + 1.4, t));
    camPos = S.p.clone().add(S.front.clone().multiplyScalar(0.3)).add(S.side.clone().multiplyScalar(0.16)).add(new THREE.Vector3(0, 0.05, 0)); camLook = S.p.clone(); fov = 30;
    tibia.position.copy(S.p); tibia.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), S.along); tibia.position.add(S.front.clone().multiplyScalar(-0.008));
    maggots.forEach((m, i) => {
      m.visible = true; m.scale.setScalar(0.014);
      const depth = 0.004 + inv(sh.t0, sh.t0 + 3, t) * 0.012 + deeper * 0.018 + (i % 2) * 0.003;
      const pos = S.surf.clone().add(S.side.clone().multiplyScalar((i - 2) * 0.008)).add(S.along.clone().multiplyScalar(Math.sin(i * 2.1) * 0.01)).add(S.front.clone().multiplyScalar(-depth));
      m.position.copy(pos); m.lookAt(pos.clone().add(S.front.clone().negate())); m.rotateZ(t * (1.5 + deeper * 9) + i);
      m.userData.mats[0].emissive.set('#ff6a1a'); m.userData.mats[0].emissiveIntensity = 1.4;
    });
    if (t > tD - 0.3 && t < tD + 1.0) { tweezers.visible = true; const pk = Math.sin(inv(tD - 0.3, tD + 1.0, t) * Math.PI); tweezers.position.copy(S.surf).add(S.front.clone().multiplyScalar(0.02 + (1 - pk) * 0.05)); tweezers.lookAt(S.surf); }
  } else if (sh.id === 'doctor') {
    camPos = S.surf.clone().add(S.front.clone().multiplyScalar(0.26)).add(S.side.clone().multiplyScalar(-0.06)).add(new THREE.Vector3(0, 0.05, 0)); camLook = S.surf.clone(); fov = 30;
    const tR = at('doctor', 'remove'), tC = at('doctor', 'cover');
    if (t < tC - 0.2) {
      const pull = inv(tR - 0.3, tR + 0.9, t);
      const m = maggots[0]; m.visible = true; m.scale.setScalar(0.011); m.userData.mats[0].emissiveIntensity = 0;
      const p = S.surf.clone().add(S.front.clone().multiplyScalar(lerp(-0.004, 0.05, ease(pull)))); m.position.copy(p); m.lookAt(p.clone().add(S.front)); m.rotateZ(Math.sin(t * 10) * 0.4);
      tweezers.visible = true; tweezers.position.copy(p).add(S.front.clone().multiplyScalar(0.012)); tweezers.lookAt(p);
    } else {
      bandage.visible = true; const k = spring(t - tC + 0.2, 3, 0.6);
      bandage.position.copy(S.surf).add(S.front.clone().multiplyScalar(0.003 + (1 - Math.min(1, k)) * 0.03)); bandage.lookAt(S.surf.clone().add(S.front.clone().multiplyScalar(2))); bandage.rotateZ(Math.atan2(S.along.x, S.along.y));
    }
  } else if (sh.id === 'map' || sh.id === 'cases') {
    fov = 30;
    const nic = mapXY(-85.2, 12.9), us = mapXY(-98, 38), tx = mapXY(-103, 31);
    if (sh.id === 'map') { const k = ease(inv(sh.t0, at('rare', 'nicaragua'), t)), k2 = ease(inv(at('us', 'august') - 0.3, at('us', 'united'), t));
      const target = nic.clone().lerp(us, k2), dist = lerp(lerp(5.5, 2.4, k), 3.6, k2);
      camLook = target; camPos = target.clone().add(new THREE.Vector3(0.3, dist * 0.8, dist * 0.7)); }
    else { const k = ease(inv(sh.t0, sh.t0 + 1.6, t)); camLook = us.clone().lerp(tx, k); const d = lerp(3.6, 1.5, k); camPos = camLook.clone().add(new THREE.Vector3(0.25, d * 0.85, d * 0.65)); }
    nicPin.scale.setScalar(sh.id === 'map' ? spring(t - (at('rare', 'thirty') - 0.2)) : 1);
    const tA = sh.id === 'cases' ? sh.t0 + 0.8 : 1e9, tB = sh.id === 'cases' ? at('back', 'seventy') + 0.4 : 1e9;
    casePins.forEach((p, i) => p.scale.setScalar(sh.id === 'cases' ? spring(t - (tA + (i / 71) * (tB - tA))) : 0));
  } else if (sh.id === 'planes') {
    plane.position.set(-22 + lt * 14, 10, 0);
    camPos = plane.position.clone().add(new THREE.Vector3(-3 + lt * 1.2, 2.5, 21)); camLook = plane.position.clone().add(new THREE.Vector3(2.5, -2.2, 0)); fov = 40; plane.userData.prop.rotation.x = t * 60;
    let n = 0; const m4 = new THREE.Matrix4();
    boxes.forEach((b, i) => { const td = 0.35 + i * 0.32, d = lt - td; b.visible = d > 0 && d < 4; if (!b.visible) return; b.position.set(-22 + td * 14 + d * 11.5, 10 - 2.2 * d * d - 0.6, 0); b.rotation.set(d * 3, d * 2, 0);
      if (d > 0.45) for (let k = 0; k < 40; k++) { const a = hash(i * 50 + k) * 6.28, r = (d - 0.45) * (2 + hash(k) * 4); m4.makeTranslation(b.position.x + Math.cos(a) * r, b.position.y + (hash(k + 3) - 0.6) * r, Math.sin(a) * r); sterileSwarm.setMatrixAt(n++, m4); } });
    sterileSwarm.count = n; sterileSwarm.instanceMatrix.needsUpdate = true;
  } else if (sh.id === 'mates') {
    fov = 30; camPos = new THREE.Vector3(0, 0.7, 6.2); camLook = new THREE.Vector3(0, 0.15, 0);
    const kIn = ease(inv(sh.t0, sh.t0 + 1.2, t));
    flyF.scale.setScalar(0.25); flyF.position.set(-0.42, 0.35 + Math.sin(t * 3) * 0.03, 0); flyF.rotation.set(0, Math.PI / 2 - 0.4, 0); flapFly(flyF, t, 0.3);
    flyM.scale.setScalar(0.25); flyM.position.set(lerp(2.2, 0.42, kIn), 0.35 + Math.sin(t * 3 + 1) * 0.03, 0); flyM.rotation.set(0, -Math.PI / 2 + 0.4, 0); flapFly(flyM, t, 1 - kIn * 0.7);
    eggsXF.position.set(0, -0.55, 0.4); eggsXF.scale.setScalar(spring(t - at('once', 'eggs') + 0.3));
    hemi.intensity = 1.2;
  } else if (sh.id === 'end') {
    const k = ease(inv(sh.t0, END, t));
    camPos = new THREE.Vector3(lerp(0.9, 2.2, k), lerp(0.9, 1.4, k), lerp(2.0, 4.0, k)); camLook = new THREE.Vector3(0, lerp(0.7, 0.95, k), 0);
    bandage.visible = true; bandage.position.copy(S.surf).add(S.front.clone().multiplyScalar(0.003)); bandage.lookAt(S.surf.clone().add(S.front.clone().multiplyScalar(2))); bandage.rotateZ(Math.atan2(S.along.x, S.along.y));
  }
  if (sh.id !== 'mates') hemi.intensity = 0.9;
  if (show.map) { sun.position.set(-3, 8, 4); sun.intensity = 2.4; } else if (show.ranch) { sun.position.set(-30, 40, 20); sun.intensity = 3; } else { sun.position.set(-6, 7, 5); sun.intensity = sh.id === 'end' ? 2.4 : 3.0; }
  sun.target.position.copy(camLook || new THREE.Vector3()); sun.target.updateMatrixWorld(); sun.position.add(camLook || new THREE.Vector3());
  // every shot drifts: a slow push and orbit so holds never freeze
  { const dist = camPos.distanceTo(camLook), a = 0.05 * Math.sin(lt * 0.6), push = 0.025 * lt;
    const off = camPos.clone().sub(camLook).applyAxisAngle(new THREE.Vector3(0, 1, 0), a).multiplyScalar(Math.max(0.8, 1 - push));
    camPos = camLook.clone().add(off); }
  cam.fov = fov; cam.updateProjectionMatrix(); cam.position.copy(camPos); cam.lookAt(camLook);
  renderer.render(scene, cam);
  overlay(t, sh);
}

// ---------- 2D overlay: captions and cards ----------
const ov = document.getElementById('ov');
const txt = (x, y, s, size, fill, o = '') => `<text x="${x}" y="${y}" font-size="${size}" font-weight="700" fill="${fill}" text-anchor="middle" stroke="#1a0e08" stroke-width="${Math.round(size / 7)}" paint-order="stroke" stroke-linejoin="round" ${o}>${s}</text>`;
const tw = (s, size) => [...s].reduce((w, c) => w + (c === ' ' ? 0.26 : /[A-Z0-9]/.test(c) ? 0.64 : 0.55), 0) * size;
function card(x, y, big, small, k, fill = '#fff8e8', col = '#1a0e08', rot = -2) {
  if (k <= 0.01) return '';
  const w = Math.max(tw(big, 70), tw(small || '', 32)) + 80, h = small ? 150 : 110;
  return `<g transform="translate(${x} ${y}) rotate(${rot}) scale(${k.toFixed(3)})"><rect x="${-w / 2 + 8}" y="${-h / 2 + 10}" width="${w}" height="${h}" rx="26" fill="#000" opacity="0.3"/><rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="26" fill="${fill}" stroke="#1a0e08" stroke-width="7"/>` +
    `<text x="0" y="${small ? -6 : 24}" font-size="70" font-weight="700" fill="${col}" text-anchor="middle">${big}</text>` + (small ? `<text x="0" y="48" font-size="32" font-weight="600" fill="${col}" text-anchor="middle">${small}</text>` : '') + '</g>';
}
const CH = (() => { const out = []; for (const l of TIMING.lines) { const ws = l.words; let i = 0; while (i < ws.length) { let j = i + 1; while (j < ws.length && j - i < 3 && !/[,.?!]$/.test(ws[j - 1].text) && ws.slice(i, j + 1).map(w => w.text).join(' ').length <= 16) j++; out.push({ text: ws.slice(i, j).map(w => w.text.replace(/[.,?!]$/, '')).join(' ').toUpperCase(), s: ws[i].start, e: j < ws.length ? ws[j].start : l.end + 0.25 }); i = j; } } out[0].s = 0; return out; })();
const KEY = /SCREWWORM|MAGGOTS|EGGS|STERILE|ONCE|ALIVE|CUT|1966|DEEPER/;
function overlay(t, sh) {
  let s = '';
  const p = k => spring(k, 2.6, 0.5);
  if (sh.id === 'eggs') s += card(540, 330, 'UP TO 500', 'eggs at the wound edge', p(t - at('eggs', 'five')));
  if (sh.id === 'xray') { s += card(540, 300, 'X-RAY VIEW', '', p(t - sh.t0 - 0.2), '#bfe8ff'); if (t > at('screw', 'name') - 0.3) s += card(540, 470, 'SCREW + WORM', '', p(t - at('screw', 'name') + 0.3), '#ffe45c'); }
  if (sh.id === 'map') { s += card(540, 330, '30 HUMAN CASES', 'Nicaragua · early 2025', p(t - at('rare', 'thirty')), '#ffffff'); if (t > at('us', 'first') - 0.2) s += card(540, 520, '1ST US HUMAN CASE', 'August 2025', p(t - at('us', 'first') + 0.2), '#ffe45c'); }
  if (sh.id === 'doctor') { if (t > at('doctor', 'doctor') - 0.1) s += card(540, 330, 'A DOCTOR REMOVES THEM', '', p(t - at('doctor', 'doctor') + 0.1)); if (t > at('doctor', 'cover') - 0.2) s += card(540, 500, 'COVER OPEN WOUNDS', '', p(t - at('doctor', 'cover') + 0.2), '#bff0c8'); }
  if (sh.id === 'cases') { const n = Math.round(71 * clamp((t - sh.t0 - 0.8) / Math.max(0.5, at('back', 'seventy') + 0.4 - sh.t0 - 0.8))); s += card(540, 330, `${n} CASES`, 'Texas · New Mexico · Arizona', p(t - sh.t0 - 0.3), '#ffffff'); }
  if (sh.id === 'planes') s += card(540, 330, 'STERILE FLIES', 'dropped from planes', p(t - at('planes', 'sterile')), '#ffffff');
  if (sh.id === 'mates') { s += card(540, 330, 'MATES ONCE', '', p(t - at('once', 'once')), '#ffe45c'); if (t > at('once', 'sterile') - 0.2) s += card(540, 1260, 'STERILE MATE', '', p(t - at('once', 'sterile') + 0.2), '#d6dde4');
    if (t > at('once', 'never')) s += `<g transform="translate(540 1140) scale(${p(t - at('once', 'never')).toFixed(3)})"><circle r="60" fill="#e2463a" stroke="#1a0e08" stroke-width="7"/><path d="M-25 -25 L25 25 M25 -25 L-25 25" stroke="#fff" stroke-width="14" stroke-linecap="round"/></g>`; }
  if (sh.id === 'end' && t > at('end', 'again') - 0.2) { const k = p(t - at('end', 'again') + 0.2); s += `<g transform="translate(540 520) rotate(-2) scale(${k.toFixed(3)})"><rect x="-440" y="-150" width="880" height="300" rx="40" fill="#fff8e8" stroke="#1a0e08" stroke-width="9"/>${txt(0, -30, 'THE FLY THAT', 86, '#1a0e08', 'stroke-width="0"')}${txt(0, 80, 'CAME BACK', 116, '#e2463a')}<text x="0" y="128" font-size="24" font-weight="600" fill="#6b5646" text-anchor="middle">Sources: USDA APHIS · USDA ARS · CDC · BMJ · DTN</text></g>`; }
  const c = CH.find(c => t >= c.s - 0.07 && t < c.e - 0.07);
  if (c) { let size = KEY.test(c.text) ? 104 : 92; const w = tw(c.text, size); if (w > 800) size *= 800 / w; const pw = Math.min(900, tw(c.text, size) + 80), ph = size * 1.25;
    s += `<g transform="translate(540 1520)"><rect x="${-pw / 2}" y="${-size * 0.95}" width="${pw}" height="${ph}" rx="${ph / 2}" fill="#140c06" fill-opacity="0.82"/>${txt(0, 0, c.text, size, KEY.test(c.text) ? '#ffe45c' : '#ffffff')}</g>`; }
  // flash on cuts
  const d = t - sh.t0; if (sh !== SH[0] && d < 0.12) s += `<rect width="1080" height="1920" fill="#fff" opacity="${(1 - d / 0.12) * 0.6}"/>`;
  ov.innerHTML = s;
}

// ---------- sound cues ----------
const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
window.CUES = [
  cue(0.5, 'buzz', 0.9), cue(2.0, 'buzz', 0.7), cue(at('alive', 'alive') - 0.2, 'pop_small', 0.6),
  ...SH.slice(1).map(s => cue(s.t0, 'whoosh', 0.8)),
  cue(at('eggs', 'five'), 'pop'), cue(L.burrow.start, 'shimmer', 0.6), cue(at('burrow', 'burrow'), 'squirm', 0.8),
  cue(at('screw', 'disturb') - 0.2, 'boing', 0.6), cue(at('screw', 'disturb') + 0.2, 'drill', 0.8), cue(at('screw', 'name') - 0.3, 'pop'),
  cue(at('rare', 'thirty') - 0.2, 'ping'), cue(at('us', 'first') - 0.2, 'stamp', 0.8),
  cue(at('doctor', 'remove') - 0.3, 'squirm', 0.6), cue(at('doctor', 'cover') - 0.2, 'stamp', 0.6),
  ...Array.from({ length: 12 }, (_, i) => cue(L.back.start + 0.5 + i * 0.3, 'tick', 0.5)),
  cue(L.planes.start, 'plane', 0.9), cue(at('planes', 'sterile'), 'swarm', 0.7),
  cue(at('once', 'once'), 'pop'), cue(at('once', 'never'), 'stamp', 0.7),
  cue(L.end.end + 0.05, 'chime'),
].sort((a, b) => a.t - b.t);

// ---------- boot ----------
await buildMap();
const lib = await load(A + 'converted/ual_cmu.glb');
CLIPS = Object.fromEntries(lib.animations.map(c => [c.name, c]));
const HR = UBC + 'Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)/';
man = await person([UBC + 'Base Characters/Godot - UE/Superhero_Male_FullBody.gltf', HR + 'Hair_SimpleParted.gltf', HR + 'Eyebrows_Regular.gltf', HR + 'Hair_Beard.gltf']);
window.renderFrame = frame;
window.FRAMES = Math.round(END * FPS);
window.FILM = { width: W, height: H, fps: FPS, frames: window.FRAMES, ready: false };
await document.fonts.load('700 40px Fredoka');
window.FILM.ready = true; window.ready = true;
