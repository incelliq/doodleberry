# Puppet format v0.3 (`.puppet.json`)

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

## Acting timelines (used by `puppet/loader/acting.js`)
`{clips: [{clip, start, end, weight, fadeIn, additive}], poses: [[t, name]], visemes: [[t, shape]] | visemes_from: speaker,
look: [[t, [x, y]]], view: [[t, name]], blinks: [t, ...] (scripted), blink: false (no automatic blinks), ik: {arm_R: [[t, [x, y]]]}, pins: {foot_L, foot_R}, travel, springs: true}`.
Clips come from the template's library (idle, walk, talk_beat, wave_R, point_R, nod, shrug, think, surprised...).
In a film's `shots.json`, any time can be written relative to a spoken line: `"mid.start+0.9"`, `"end.end-0.2"`.
These resolve against `timing.json`, so acting stays on the words after a voice change or translation.

## Roadmap
Bendy limbs (mesh or path warp), raster parts (PNG with pivot) for painted styles, 3/4 views drawn from a turnaround
template, N-bone FABRIK chains (tails, tentacles), Rig Canvas tabs for views and pose previews.
