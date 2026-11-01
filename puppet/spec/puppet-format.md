# Puppet format v0.1 (`.puppet.json`)

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

## Roadmap
v0.2: multiple views (`views: {"3q": …, "side": …}`) with per-view z-order, IK targets and foot pins, bendy limbs
(mesh or path warp), springs for hair/coat/tie, per-phoneme visemes, raster parts (PNG with pivot) for painted styles.
