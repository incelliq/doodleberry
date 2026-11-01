# Doodleberry: notes for Claude

- Films live in `films/<name>/` (brief.md, facts.json, script.json, score.json, scene.js, index.html; generated files in `build/`, git-ignored).
- The QA bar (`engine/qa.py`): 1080×1920, 30 fps, no still stretch > 0.5 s, −14 ±1 LUFS, true peak ≤ −1 dBTP, every narrated line traced to `facts.json`. Run `engine/mixcheck.py --whisper` for intelligibility.
- Frame functions must be pure functions of the frame number (no clocks, no unseeded randomness). Filter ids must include the frame tag (`D.begin(f)`); camera holds must be exact.
- Characters and props are original designs. Never draw or trace existing copyrighted characters.
- Puppets: keep `puppet/spec/puppet-format.md`, `puppet.schema.json`, the loader and the canvas in step when the format changes; bump `version`.
- 3D pages fetch GLBs, so serve the repo over HTTP; software WebGL/Vulkan is slow (≈1 s/frame), plan renders in the background.
- Don't commit downloaded asset packs, renders or voices.
