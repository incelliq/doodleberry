# Puppet format v0.8 (`.puppet.json`)

A puppet is one JSON file: the character's parts as SVG path data, its skeleton (parents and pivots), swap sets
(mouths, eyes, brows, hand poses) and a palette of named colour slots. The drawing canvas writes it; the loader
(`puppet/loader/puppet.js`) renders it in any pose; templates (`puppet/templates/`) define which parts exist.

```jsonc
{
  "format": "doodleberry.puppet", "version": "0.1",
  "name": "Pip", "template": "humanoid",
  "artboard": [600, 1000],            // drawing space; origin top-left, y down
  "ground": 980,                      // y of the floor line (feet rest on it)
  "palette": { "skin": "#e8b48e", "hair": "#4a3020", "cloth1": "#f2a33a", "cloth2": "#3a5a8a",
               "cloth3": "#ffffff", "shoe": "#e9e9ee", "eye": "#ffffff", "ink": "#24160e" },
  "parts": {
    "upperarm_R": {
      "parent": "torso",              // rotates with its parent
      "pivot": [372, 350],            // joint position in artboard units, drawn (rest) pose
      "z": 30,                        // draw order, higher in front
      "strokes": [ { "d": "M…Z", "fill": "cloth1", "stroke": "ink", "width": 4 } ]
    }
  },
  "swaps": {
    "mouth": { "anchor": "head", "z": 45, "talk": ["closed", "small", "mid", "wide"],
               "shapes": { "closed": [ … ], "small": [ … ], "O": [ … ], "FV": [ … ] } },
    "pupils": { "anchor": "head", "z": 43, "movable": 8, "shapes": { "default": [ … ] } },
    "hand_R_pose": { "anchor": "forearm_R", "z": 33, "replaces": "hand_R", "shapes": { "point": [ … ] } }
  },
  "meta": { "author": "", "license": "", "created": "2026-11-01" }
}
```

## Strokes
`d` is SVG path data in artboard units, drawn in the rest pose. `fill` and `stroke` are **palette slot names**
(`"cloth1"`, `"ink"`) so code can recolour outfits and skin tones; a raw `#hex` is allowed but the rig check flags it.
`opacity` is optional.

## Skeleton
Each part's world transform is its parent's transform followed by a rotation about its own pivot. A pose gives
angles in degrees relative to the drawn pose, so a puppet drawn standing with arms down has every angle at 0.
The hips are the root; the loader places the hip pivot's x and the ground line at the scene point you give it.

## Swaps
A swap set is a group of alternative drawings attached to an anchor part (they move with it):
- `mouth`: chosen from `talk` by the lip-sync openness (0..1), or forced by name (`mouth: "O"`).
- `eyes`: `open` / `half` / `closed`, chosen from `blink` unless forced. `pupils` slide by `look: [x, y]` up to `movable` units.
- `brows`: by name. Sets with `replaces` (hand poses) hide the named part while one of their shapes is shown.

## Rules of thumb for artists
Draw each part a little past its joint so bends never open a gap; colour with palette slots; keep one line weight;
draw facing right (code mirrors for the other side); keep lighting flat (shading is added in code); keep the
character original.

## v0.2 additions (all optional; v0.1 files stay valid)

### Views
`views: {name: {parts: {id: {strokes, pivot, z}}, swaps: {id: {shapes: {...}}}}}` overrides the default (drawn) view.
Only the parts and swap shapes you redraw are listed; everything else is inherited. A timeline turns a character with
`view: [[t, "side"], [t2, "front"]]` (any name not in `views` means the default view). The loader squashes the
character horizontally for 0.09 s around each switch, a classic turn smear, so the swap reads as a turn.
Every renderer and exporter supports views: SVG, Synfig (a layer set per view), Grease Pencil, Lottie (a layer set
per view gated by opacity).
Draw side views with arm and leg pivots moved toward the body's centre line and one eye; see
`puppet/examples/pip_side.py`.

### Springs
`springs: {part: {driver, freq, damping, gain, limit}}`: secondary motion (hair, ears, coat-tails). The part swings
after its `driver` part's world angle with a damped spring (`freq` Hz, `damping` 0..1), `gain` × the driver's motion,
clamped to ±`limit` degrees. Deterministic: it is re-simulated from a short window before each frame, so any frame
renders on its own.

### Poses
`poses: {name: {angles, brows, eyes, mouth, hand_R_pose, ...}}`: named key poses for this character, used by
timelines like the shared presets in `puppet/clips/<template>.json`.

## v0.3 additions
- **Raster parts:** a stroke can be `{"image": "data:image/png;base64,...", "x", "y", "w", "h"}` in artboard units, for
  scanned pen ink or painted parts. `dbe/ink.py` (`puppet.from_ink`) makes these from a photo of a drawing. Raster
  puppets render with the SVG renderer; the other renderers still draw vector parts only.
- **anchors:** named points in artboard units, e.g. `{"bubble": [x, y]}` (top of the head, where speech bubbles
  point). Read with `Puppet.pointOf(p, "head", p.anchors.bubble, ...)`.
- **Templates:** `doodle` (hip, body, head, arm_L, arm_R, tail; L/R are image sides) with its own clip library
  (`puppet/clips/doodle.json`: idle, hop, wave_L/R, tilt, lean_in, wag, talk, shake). Each puppet uses the library of
  its template.

## v0.4 additions: smart bones, shifts, constraints
- **controls (smart bones / driven keys):**
  `"controls": {"turn": {"range": [-1, 1], "drives": [{"target": "angles.head", "keys": [[-1, -4], [0, 0], [1, 4]]}, {"target": "shift.@eyes", "keys": [[-1, [-16, 0]], [1, [16, 0]]]}, ...]}}`.
  - One control value drives several targets through piecewise-linear key curves.
  - Targets: `angles.<part>` (added degrees), `shift.<part>` or `shift.@<swap>` (moves before rotation), `swap.<id>`
    (discrete), `z.<part>` or `z.@<swap>` (layer order).
  - Timelines animate the control: `"controls": {"turn": [[t, value], ...]}`.
  - Pip has a `turn` control that turns the head, slides the face and parallaxes the hair.
- **Pose shifts and z:** `pose.shifts[part] = [dx, dy]` and `pose.z[part]`. Every renderer and exporter applies shifts;
  dynamic layer order applies in SVG and Grease Pencil.
- **lookat constraint (timeline):** `{"part": "head", "target": [x, y] | {"cast": i, "part": "hand_R", "at": [x, y]}, "aim": [0, -1], "limit": 10, "weight": 1}`
  rotates a part so its aim vector points at a target, clamped. Frame-space points work in every renderer; targets
  on other characters work in the SVG player.

- **bend (bendy limbs):** `"bend": {"width": 90}` on a part makes it curve out of its parent instead of hinging:
  - the centre line follows a circular arc of the joint angle over a zone `width` wide, centred on the joint;
  - cross-sections stay perpendicular, so the limb keeps its thickness;
  - a small correction is blended in so the curve meets the rigid child (hands and feet stay attached).

  Works in the SVG renderer and Grease Pencil; Synfig and Lottie stay rigid (they transform whole layers).
  `puppet/examples/pip_bendy.py` makes a rubber-hose Pip.

Shot-level **props** (SVG player): `"props": [{"id", "r", "color" | "svg", "spin", "travel", "arc", "attach": [[t, {"cast": i, "part": "hand_R", "at": [x, y]}], [t2, {"x", "y"}], ...]}]`.
A prop follows its current parent (a character's part or a fixed point) and travels on an arc when the parent
changes: hand to hand, a throw to another character, a drop to the floor.

## v0.5 additions: mesh strokes (skinned raster parts)
A stroke can be a texture on a triangle mesh whose vertices follow several parts:

```jsonc
{"mesh": {"image": "data:image/png;base64,...", "iw": 278, "ih": 1312,   // texture and its pixel size
          "verts": [[x, y], ...],          // artboard units, rest pose
          "uv": [[px, py], ...],           // texture pixels per vertex
          "tris": [[a, b, c], ...],
          "weights": [[["thigh_L", 0.7], ["shin_L", 0.3]], ...],   // per vertex, parts and weights
          "grow": 0.6}}                    // optional: grow each clip triangle to hide seams (artboard units)
```

- Vertices are skinned with the parts' world matrices (linear blend skinning), so a leg bends smoothly at the knee and
  a skirt follows the hips and its spring panels. The stroke sits in its part's layer (its `z`), but its own part's
  matrix is not applied: only the weights move it.
- Every part named in the weights must exist (it may have no strokes of its own).
- The SVG renderer draws each triangle as the shared texture under its affine map, clipped to the (slightly grown)
  triangle. Ids hash the content, so frames stay pure functions of time and identical frames still dedupe.
- `dbe/cutout_import.py` makes these from skinned meshes in Blender cut-out rigs. Like raster parts, mesh strokes
  render in the SVG renderer only; the other exporters skip them.
- **acting** (per character): `{"viseme_hold": 0.09, "tempo": 0.8, "fade": 0.35}`. Mouth shapes shorter than `viseme_hold`
  seconds fold into the previous shape (closures always land); clip layers play at `tempo` and blend in and out over
  `fade` seconds unless a layer sets its own; `energy` scales every clip's motion and `idle` the idle loop's (a layer's own
  `gain` multiplies in). Richly drawn characters read as shaky with cartoon-snappy timing.
- Linear blend skinning pinches at very sharp bends (beyond about 90°); subdivide the mesh for smoother arcs.

## Acting timelines (used by `puppet/loader/acting.js`)
`{clips: [{clip, start, end, weight, fadeIn, additive}], poses: [[t, name]], visemes: [[t, shape]] | visemes_from: speaker,
look: [[t, [x, y]]], view: [[t, name]], blinks: [t, ...] (scripted), blink: false (no automatic blinks), ik: {arm_R: [[t, [x, y]]]} (a null target lets the limb go), ik_bend: {arm_L: 1} (which way the elbow or knee bends), pins: {foot_L, foot_R}, travel, springs: true}`.
Clips come from the template's library (idle, walk, talk_beat, wave_R, point_R, nod, shrug, think, surprised...).
In a film's `shots.json`, any time can be written relative to a spoken line: `"mid.start+0.9"`, `"end.end-0.2"`.
These resolve against `timing.json`, so acting stays on the words after a voice change or translation.

## Roadmap
Mesh subdivision for very sharp bends, 3/4 views drawn from a turnaround
template, N-bone FABRIK chains (tails, tentacles), Rig Canvas tabs for views and pose previews.

## v0.6 additions: chains, joint limits, emotion charts, animation principles
- **`parts[id].limits`** `[min, max]`: joint limits in degrees from the rest pose. `Acting.evaluate` clamps the
  angle after clips, look-at, IK, pins and chains, and again after springs, so nothing can wring a joint past them.
  Generated characters limit the neck to ±30°, tail segments to ±40°.
- **`chains`** `{name: {parts: [p1, ..., pn], tip: [x, y], wave: {amp, freq, lag}}}`: an N-bone chain (tail,
  tentacle, rope), each part the parent of the next, `tip` the end of the last bone in artboard space. `wave` adds a
  travelling sine along the chain (a living tail; `chain_wave: false` in a timeline turns it off). A timeline
  `chains: {name: [[t, [x, y]]]}` gives reach targets in artboard space, solved by FABRIK with the root fixed and
  written back as local angles (then limited). Springs on chain parts add follow-through on top.
- **`swaps.mouth.charts`** `{emotion: {shape: drawn shape}}`: the emotion-aware mouth chart. A timeline
  `emotion: [[t, "happy" | "sad" | "angry" | "surprised" | "worried" | "neutral"]]` maps the viseme through the chart (default:
  happy and sad/angry turn the closed mouth into `smile`/`frown`, surprised into `O`), uses a drawn
  `<shape>_<emotion>` when the puppet has one, and sets brows (raised, worried, angry) unless a clip sets them.
- **`acting.principles`** `{snap, window}` (or timeline `principles`): anticipation and overshoot as an unsharp mask
  in time on the clip pose, `a + snap * (a - blur(a))` with the blur over ±`window` seconds: a joint dips the other
  way just before a move and carries past just after it stops. Pure (samples the clip stack at neighbouring times).

Blending (loader behaviour, all versions): foreground clips average by weight among themselves and override the base
layer (`idle`, or any layer with `base: true`) per track in proportion to their weight; idle still fills tracks the
gesture does not touch. Earlier loaders averaged gestures with idle, which halved them.

## v0.7 additions: a character's own clips
- **`clips`** `{name: {duration, loop, tracks, offset, swaps, contacts}}`: clips that belong to this character, in
  the same shape as a clip library entry. `Acting.evaluate` merges them over the template's library (a character
  clip wins over a library clip of the same name), so shots, the bake, `dbe/geom.py` and every exporter play them.
  The Rig Canvas Pose tool records them from keyed poses; `poses` (v0.2) holds its saved single poses.

## v0.8 additions: drawn levels (hand-drawn animation)
A **drawn level** is a puppet of template `level` (WP-35): one `root` part and a swap set `level` whose shapes are the
drawings and whose **`xsheet`** is the exposure sheet:

```jsonc
"swaps": {"level": {"anchor": "root", "z": 10,
                    "shapes": {"d01": [stroke...], "d02": [stroke...]},           // raster strokes (scans, brushes, Pencil2D) or vector strokes
                    "xsheet": {"fps": 24, "cells": ["d01", "d01", "d02", "d02"], "loop": true}}},   // one drawing per frame: runs are holds
"clips": {"play": {"duration": 0.1667, "loop": true, "fadeIn": 0, "fadeOut": 0, "tracks": {}, "swaps": {"level": [[0, "d01"], [0.0833, "d02"]]}}}
```

- `cells` holds one drawing per frame at the level's own `fps`: a run of the same drawing is a hold, so timing on ones,
  twos or threes, or any timing an animator writes, is data. Drawings may repeat (a cycle that comes back).
- The xsheet is compiled into the clip `play` (v0.7 clip swap keys hold until the next key), so the loader, the bake,
  `dbe/geom.py` and the exporters play a level like any swap. A shot casts it like a character, with
  `"timeline": {"clips": [{"clip": "play", "start": 0}]}`, and can move, scale, flip and speed it up (`speed`).
- **Clip fades** (`fadeIn`, `fadeOut` on a clip): the default blend a timeline uses for that clip when the layer does
  not set its own (0.25 s otherwise). Level clips set 0: drawings cut, never cross-fade.
- `ground` is where the drawings stand (by default the lowest ink across every drawing).
- **Colour styles** (`swaps.level.paint`): `{"styles": {"skin": "#f2c9a0"}, "seeds": {"d01": [[x, y, "skin"], ...]}}`. Each seed
  paints the closed area under it (gaps in the line up to 2 px are bridged; the outside is never painted); the paint is
  a raster stroke with `"role": "paint"` placed under the line art (`"role": "line"`, the default) and rebuilt
  whenever a style or a drawing changes, so recolouring a style repaints every drawing. `level.colour` carries a
  painted drawing's areas to the others by matching areas between neighbouring drawings.
- Commands: `level.make` (drawings plus timing), `level.xsheet` (retime, or write the cells), `level.from_pencil2d`
  (a Pencil2D animation, with its holds), `level.onion` (onion-skin drawings around a frame). Raster drawings render
  in the SVG renderer; vector drawings everywhere.
