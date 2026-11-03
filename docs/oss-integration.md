# Open-source integration map (WP-34)

For each group of gaps in the parity matrix (`docs/parity-matrix.md`), the codebases that can close it, and a decision
per part. Doodleberry is in-house R&D and not distributed, so any licence may be used (`CLAUDE.md`); the class is
recorded so the posting gate can flag inputs to a public film (`licence.ledger`, `film.provenance`).

How a part comes in:
- **drive**: run the program headless as a separate process (command line, its own scripting); nothing is linked.
- **link**: load the library into our process (Python package or ctypes).
- **vendor**: keep its source in `vendor/<name>/` with an `UPSTREAM.json` (`vendor.check`), build it ourselves.
- **fork**: vendor and change it (patches kept small, upstream fixes pulled).

Status: **working** (behind a command, tested by `python -m dbe test`), **installed** (available here, not yet behind a
command), **planned** (the work package that brings it in), **blocked** (needs the owner's permission: building
external source with its own scripts is held by the environment's safety check, as for `vendor.build`, WP-33).

Measured on 2 November 2026 in this container (Ubuntu 24.04 packages).

## 1. Frame-by-frame, exposure sheet, levels (WP-35)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| **Pencil2D 0.6.6**: open and render hand-drawn projects | GPL-2.0 (copyleft) | drive: its command-line exporter, Qt offscreen | **working**: `pencil2d.write` writes a drawn level (drawings with their exposure frames) as a project an artist can open; `pencil2d.render` renders any project to transparent PNG frames with holds. Round trip tested |
| OpenToonz 1.7/1.8 `tcomposer`: render scenes with the Xsheet and FX | BSD-3-Clause (permissive) | drive `tcomposer` headless for Xsheet scenes; vendor the `toonz/sources/toonzlib` level formats later if needed | **blocked**: no Ubuntu package; building from source (CMake, Qt 5) needs the owner's permission |
| Tahoma2D (OpenToonz fork) | BSD-3-Clause (permissive) | same as OpenToonz; prefer it if its stop-motion capture is wanted (WP-35) | blocked, as above |
| Exposure sheet exchange (XDTS, TVPaint and OpenToonz) | format, no code | write our own reader and writer | planned (WP-35) |

## 2. Painting and brushes (WP-18, WP-35)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| **libmypaint 1.6**: the MyPaint brush engine | ISC (permissive) | link through ctypes (no GObject bindings needed) | **working**: `brush.paint` paints pressure strokes with any MyPaint preset onto a transparent PNG; `brush.list` lists them |
| **mypaint-brushes 2.0**: brush presets (pencils, inks, charcoal, watercolour) | CC0-1.0, some sets GPL-2.0-or-later (public-domain / copyleft data) | read the presets as data | **working** (used by `brush.paint`) |
| Krita 5.2 brush engines | GPL-3.0 (copyleft) | drive Krita headless for `.kra` import and export only; its engines are tied to its canvas | installed on demand (`apt-get install krita`); planned (WP-18) |

## 3. Vector editing and deformers (WP-18, WP-14)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| **Inkscape 1.2**: path operations | GPL-2.0-or-later (copyleft) | drive its `--actions` headless | **working**: `vector.boolean` (union, difference, intersection, exclusion, division) |
| **Synfig 1.5 core**: vector renderer with bones | GPL-3.0-or-later (copyleft) | drive the `synfig` CLI | installed; `shot.render` renderer `synfig` and `export.synfig` already use it (WP-14 finishes bones and z-order in the export) |
| Inkscape text-to-path, simplify, offset | GPL-2.0-or-later | drive, as above | planned (WP-18) |

## 4. Compositing (WP-36)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| Natron 2.5 and its OpenFX plugins | GPL-2.0 (copyleft) | drive `NatronRenderer` on a generated project for heavy node graphs | planned (WP-36); not packaged here (AppImage or a source build: owner's permission) |
| Blender compositor | GPL-2.0-or-later (copyleft) | link `bpy` in a separate Python and drive its compositor nodes | planned (WP-36, WP-42); Blender 5.2.3 LTS installed (`bash tools/setup.sh blender`) and already drives the Grease Pencil renderer |
| Our own node graph in the SVG and WebGL renderers | ours | build: blend modes, mattes, glows and multiplane are cheap in the browser renderer | planned (WP-36) |

## 5. Colour and image formats (WP-37)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| OpenColorIO 2.1 | BSD-3-Clause (permissive) | link (PyOpenColorIO) for transforms; tools for checks | installed (`ociocheck` and friends); planned (WP-37) |
| OpenImageIO 2.4 | Apache-2.0 (permissive) | drive `oiiotool` for EXR, conversions and statistics | installed; planned (WP-37) |
| OpenEXR | BSD-3-Clause (permissive) | link through OpenImageIO | planned (WP-37) |

## 6. Editing and review (WP-19, WP-22)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| MLT (`melt`) and Kdenlive projects | LGPL-2.1 / GPL-3.0 (weak-copyleft / copyleft) | drive `melt` to render and round-trip Kdenlive edits | planned (WP-22); `engine.doctor` already checks `melt` |
| OpenRV, xSTUDIO | Apache-2.0 (permissive) | drive as desktop review players from the OTIO export | planned (WP-19), optional |
| Olive | GPL-3.0 (copyleft) | not chosen: MLT covers the round trip | not planned |

## 7. Sound (WP-40, WP-13)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| Ardour (Lua scripting, headless sessions) | GPL-2.0 (copyleft) | drive for mixing sessions an editor can open | planned (WP-40) |
| Audacity | GPL-2.0/3.0 (copyleft) | not driven (its scripting needs the GUI); export stems it can open | not planned |
| SoX, ffmpeg filters | GPL / LGPL | drive (ffmpeg already does the mix) | in use |

## 8. Render farm (WP-38)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| OpenCue | Apache-2.0 (permissive) | drive for frame-range jobs across machines | planned (WP-38) |
| Flamenco | GPL-3.0 (copyleft) | consider for Blender-only jobs | planned (WP-38), second choice |
| CGRU Afanasy | GPL-3.0 (copyleft) | not chosen | not planned |

## 9. 3D and procedural (WP-42, WP-09)

| Part | Licence (class) | Decision | Status |
|---|---|---|---|
| **Blender 5.2 Geometry Nodes and EEVEE** (`bpy` in headless Blender) | GPL-2.0-or-later (copyleft) | drive: a generated script builds the node tree and renders | **working**: `proc.cook` gn_set (procedural 3D sets, cel-shaded with Freestyle ink lines, framed by the shot camera); renders are byte-identical twice. OpenUSD and Bullet stay planned (WP-42) |
| **Rapier 0.21** (2D physics, cross-platform deterministic build) | Apache-2.0 (permissive) | link: the npm WASM package in Node (`tools/physics/`), baked into prop tracks so no renderer needs it | **working**: `physics.solve` (multi-body scenes, contacts retimed onto the beat); reruns byte-equal |
| Bullet (PyBullet) | zlib (permissive) | link for cloth and soft bodies if needed | not needed for WP-09 (Rapier covers rigid bodies); planned with WP-42 if cloth is wanted |
| Manifold | Apache-2.0 (permissive) | link (`manifold3d`) for solid booleans | planned (WP-42) |
| OpenUSD | Apache-2.0 with trademark terms (permissive) | link (`usd-core`) for scene exchange | planned (WP-42) |

## What is behind a command now

    python -m dbe brush.paint '{"brush": "deevad/2B_pencil", "strokes": [[[40,120,0.3],[200,140,0.8],[360,120,0.3]]], "size": [400,240], "out": "out/stroke.png"}'
    python -m dbe pencil2d.write '{"frames": [{"frame": 1, "png": "a.png"}, {"frame": 3, "png": "b.png"}], "out": "out/level.pclx"}'
    python -m dbe pencil2d.render '{"file": "out/level.pclx", "out_dir": "out/level"}'
    python -m dbe physics.solve '{"name": "juggle-demo", "shot": "s1"}'
    python -m dbe vector.boolean '{"shapes": ["<rect x=\"0\" y=\"0\" width=\"100\" height=\"100\"/>", "<circle cx=\"100\" cy=\"50\" r=\"50\"/>"], "op": "union"}'

`bash tools/setup.sh oss` installs every installable part above (about 700 MB); `engine.doctor` reports them.
