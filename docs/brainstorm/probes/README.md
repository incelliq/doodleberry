# Feasibility probes (November 2026)

Small scripts behind the "Measured on this container" table in `../procedural-houdini.md`. They are not part of the
engine. Install their dependencies in a scratch venv or folder, never in the repo.

- `gn_scatter.py`: builds a Geometry Nodes graph from code and prints a mesh hash.
  `blender -b --factory-startup --python gn_scatter.py -- '{"size": 20, "height": 2.0, "density": 0.6, "seed": 7}'`
  Run twice: the hashes must match. Change the seed: the hash must change.
- `rapier_determinism.mjs`: 12 bouncing balls in Rapier 2D, run twice, hashes compared.
  `npm i @dimforge/rapier2d-deterministic-compat@0.21.0 && node rapier_determinism.mjs`
- `eco_probe.py`: Box2D, pybullet, Taichi, manifold3d, usd-core and music21 smoke tests.
  `pip install box2d pybullet taichi manifold3d usd-core music21 && python eco_probe.py`
