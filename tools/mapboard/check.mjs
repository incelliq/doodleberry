// Map board check (WP-16, test `mapboard`): for every map in sets/maps/, the set's own projection (MAPS.project in
// sets/map.js) agrees with d3-geo's on a grid of points; the countries the data names are where Natural Earth puts
// them (a city inside its country, by d3-geo's geoContains on the source data); and the set draws the same SVG for
// the same time (a pure function of the frame), with pins where the projection says.
//   node tools/mapboard/check.mjs  -> JSON
import { geoNaturalEarth1, geoContains } from 'd3-geo';
import { feature } from 'topojson-client';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url)), root = join(here, '..', '..');
const ctx = { globalThis: {} }; ctx.globalThis = ctx; vm.createContext(ctx);
for (const f of ['sets/sets.js', 'sets/map.js', ...readdirSync(join(root, 'sets/maps')).filter(f => f.endsWith('.js')).map(f => `sets/maps/${f}`)])
  vm.runInContext(readFileSync(join(root, f), 'utf8'), ctx, { filename: f });
const { MAPS, SETS } = ctx;
const out = { maps: {}, ok: true };
const CITIES = [['Sri Lanka', 79.86, 6.93], ['India', 77.21, 28.61], ['Australia', 149.13, -35.28], ['Peru', -77.04, -12.05], ['Indonesia', 106.85, -6.21]];
for (const [name, m] of Object.entries(MAPS)) {
  if (typeof m !== 'object' || !m.countries) continue;
  const d3p = geoNaturalEarth1().rotate(m.rotate).scale(m.k).translate([0, 0]);
  let worst = 0;
  for (let lon = -180; lon <= 180; lon += 7.5) for (let lat = -80; lat <= 80; lat += 5) {
    const a = MAPS.project(m, lon, lat), b = d3p([lon, lat]);
    if (Math.abs(lon + m.rotate[0]) % 360 === 180) continue;   // the antimeridian of the map: either edge is right
    worst = Math.max(worst, Math.hypot(a[0] - b[0], a[1] - b[1]));
  }
  const topo = JSON.parse(readFileSync(join(here, 'node_modules/world-atlas', `countries-${m.res}.json`)));
  const feats = Object.fromEntries(feature(topo, topo.objects.countries).features.map(f => [f.properties.name, f]));
  const cities = CITIES.filter(([c]) => m.countries[c]).map(([c, lon, lat]) => ({ country: c, inside: geoContains(feats[c], [lon, lat]),
    in_box: (([x, y], b) => x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3])(MAPS.project(m, lon, lat), m.countries[c].b.map((v, i) => v + (i < 2 ? -1 : 1))) }));
  // the set: same time, same drawing; a pin lands where the projection says
  const o = { map: name, pins: [{ lon: 80, lat: 8, at: 0.2 }], routes: [{ from: [70, 0], to: [80, 8], at: 0.1, dur: 1 }], highlight: [{ country: 'Sri Lanka', at: 0.3 }] };
  const s1 = SETS.map.draw(2.0, o, 1080, 1920), s2 = SETS.map.draw(2.0, o, 1080, 1920), s0 = SETS.map.draw(0.05, o, 1080, 1920);
  const tr = /<g transform="translate\(([\d.-]+) ([\d.-]+)\) scale\(([\d.]+)\)">/.exec(s1);
  const pin = /<g transform="translate\(([\d.-]+) ([\d.-]+)\)"><path d="M0 0 C-6/.exec(s1);
  const [px, py] = MAPS.project(m, 80, 8), want = tr && [+tr[1] + px * +tr[3], +tr[2] + py * +tr[3]];
  const pin_err = pin && want ? Math.hypot(+pin[1] - want[0], +pin[2] - want[1]) : null;
  const r = { countries: Object.keys(m.countries).length, projection_max_err: +worst.toFixed(4), cities,
    pure: s1 === s2, pin_err: pin_err == null ? null : +pin_err.toFixed(2), pin_hidden_before: !/C-6 -16/.test(s0) };
  r.ok = worst < 0.05 && cities.every(c => c.inside && c.in_box) && r.pure && pin_err != null && pin_err < 0.2 && r.pin_hidden_before;
  out.maps[name] = r; out.ok = out.ok && r.ok;
}
console.log(JSON.stringify(out));
