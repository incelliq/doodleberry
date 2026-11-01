import RAPIER from '@dimforge/rapier2d-deterministic-compat';
import crypto from 'node:crypto';
await RAPIER.init();
function run() {
  const w = new RAPIER.World({ x: 0, y: -9.81 });
  w.createCollider(RAPIER.ColliderDesc.cuboid(20, 0.5));
  const bodies = [];
  for (let i = 0; i < 12; i++) {
    const b = w.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(-3 + (i % 4) * 1.7, 2 + Math.floor(i / 4) * 1.6).setRotation(i * 0.3));
    w.createCollider(RAPIER.ColliderDesc.ball(0.5).setRestitution(0.6), b); bodies.push(b);
  }
  const out = []; const t = performance.now();
  for (let f = 0; f < 300; f++) { w.step(); out.push(...bodies.map(b => [b.translation().x, b.translation().y, b.rotation()]).flat()); }
  return { ms: +(performance.now() - t).toFixed(1), hash: crypto.createHash('sha256').update(new Float64Array(out)).digest('hex').slice(0, 16) };
}
console.log(JSON.stringify([run(), run()]));
