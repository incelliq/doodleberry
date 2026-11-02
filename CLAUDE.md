# Doodleberry: notes for Claude

- Films live in `films/<name>/` (brief.md, facts.json, script.json, score.json, scene.js, index.html; generated files in `build/`, git-ignored).
- The QA bar (`engine/qa.py`): 1080×1920, 30 fps, no still stretch > 0.5 s, −14 ±1 LUFS, true peak ≤ −1 dBTP, every narrated line traced to `facts.json`. Run `engine/mixcheck.py --whisper` for intelligibility.
- Frame functions must be pure functions of the frame number (no clocks, no unseeded randomness). Filter ids must include the frame tag (`D.begin(f)`); camera holds must be exact.
- Characters and props are original designs. Never draw or trace existing copyrighted characters.
- Puppets: keep `puppet/spec/puppet-format.md`, `puppet.schema.json`, the loader and the canvas in step when the format changes; bump `version`.
- 3D pages fetch GLBs, so serve the repo over HTTP; software WebGL/Vulkan is slow (≈1 s/frame), plan renders in the background.
- Don't commit downloaded asset packs, renders or voices.
- The backend is `dbe/` (docs/dbe.md). Add features as `@command` functions in `dbe/commands.py`; they appear in the CLI, HTTP API, Studio and MCP at once. Keep arguments and results JSON-safe.
- Shot times in `shots.json` should reference lines (`"mid.start+0.9"`) rather than hard seconds, so re-voicing and localisation keep sync.
- Licences: Doodleberry is in-house R&D, not distributed, so any open-source code (GPL and AGPL included) and source-available or non-commercial models and data may be used, vendored and modified. Record every library, model or asset with its licence class in `assets/manifest.json` (and `docs/oss-research.md`). What goes into a publicly posted film is the exception: voices not marked `clean` in `voices/registry.json`, and non-commercial, research-only or share-alike inputs, are flagged at the posting gate for the owner to decide.
- All renderers read the baked animation from `tools/bake.mjs`; a new puppet feature must reach `puppet.js`, `acting.js`, `bake.mjs`, `dbe/geom.py` and the exporters together.
- Before committing engine, loader, player or puppet changes, run `python -m dbe test` (golden frames). After an intended visual change, run it with `{"update": true}` and check the new frames. `tests/golden/` holds small reference PNGs (fixtures, not renders); `tests/poses/*.json` are loader-level cases (puppets in given poses).
- Film data is validated against `dbe/schemas/*.schema.json` on `film.write` and before every render (`film.validate`).
