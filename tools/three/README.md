# three.js 3D renderer (headless Chromium, software WebGL2)

`run3d.mjs PAGE OUT.mp4 [workers]` renders a page that defines `window.FRAMES`, `window.renderFrame(f)` and
`window.ready`, across N pages, then encodes with ffmpeg. GLB files must be served over HTTP (fetch is blocked on
file:// pages): `python3 -m http.server 8765 --bind 127.0.0.1` in the folder, then pass `http://127.0.0.1:8765/page.html`.

`cast-test.html` is a 5 s pipeline test: a code-built supermarket set; CC0 characters from Gobkit Free Character
Pack Vol.1 (walk, run, wave, hit → death), Kenney Animated Characters Survivors (zombie skin, converted by
`../blender/convert_packs.py`) and the Quaternius Universal Animation Library mannequin (walk → hit → death fall).
Poses are set deterministically per frame (clip time = f(frame)), so renders are reproducible.
It expects `assets/gobkit-v1`, `assets/converted` and `ual/UAL1_Standard.glb` next to it (assets are not committed).
Measured: 150 frames at 1080×1920 in 75 s with 4 workers (~2 frames/s).
