"""Humaaans (Pablo Stanley) to a puppet with mix-and-match swap sets (WP-16).

The kit's "Single Pieces" are SVGs on shared canvases per kind: `Head/Front/*` (136 x 104: hair, headwear and the
skin of the head and neck), `Body/*` (256 x 187: torso and arms), `Bottom/Standing/*` and `Bottom/Sitting/*`
(300 x 239: legs and shoes). The finished figures in `Humaaans/` show how they stack: at rest a head sits at (82, 0),
a body at (22, 82) and the legs at (0, 187) of a 300 x 426 figure (the figures that turn a head or lean a body move
those, so they are not used for the rest layout). The puppet:

    hip -> legs -> body -> head

with the pieces' fills as named palette slots, and swap sets replacing each part: `outfit` (bodies), `legs`
(bottoms; sitting ones prefixed `sit-`) and `hair` (heads). The body turns about the waist (the top centre of the
legs) and the head about the neck (the bottom centre of the head's skin group), so leans and nods bend the figure;
the arms are drawn into each body, so they do not move on their own.
"""
import hashlib
import re
from pathlib import Path

from . import drawing_import as DI
from . import geom as G

REST = {"head": (82.0, 0.0), "body": (22.0, 82.0), "legs": (0.0, 187.0)}
SIZE = (300, 426)
Z = {"head": 10, "legs": 20, "body": 30}   # as the finished figures stack them: the collar over the neck


def _norm(n):
    return re.sub(r"\s+", "-", n.strip())


def read_kit(folder):
    """{"head": {name: (records, skin_bbox)}, "body": {...}, "legs": {...}}, sources {relative path: sha256}"""
    root = Path(folder); sp = root / "Single Pieces"
    if not sp.exists():
        raise ValueError(f"{folder}: no 'Single Pieces' folder (the Humaaans 'Flat Assets' download)")
    kinds = {"head": [sp / "Head" / "Front"], "body": [sp / "Body"], "legs": [sp / "Bottom" / "Standing", sp / "Bottom" / "Sitting"]}
    kit = {k: {} for k in kinds}; sources = {}
    for kind, dirs in kinds.items():
        for dd in dirs:
            for f in sorted(dd.glob("*.svg")):
                src = DI.read_svg(f); sources[str(f.relative_to(root))] = hashlib.sha256(f.read_bytes()).hexdigest()
                name = ("sit-" if dd.name == "Sitting" else "") + _norm(f.stem)
                ox, oy = REST[kind]; M = [1, 0, 0, 1, ox, oy]
                recs = [{**r, "d": DI.transform_d(r["d"], M)} for r in src["items"]]
                skin = [r for r in recs if any(n == "Head" for n in r["names"])]
                kit[kind][name] = (recs, _bbox(skin) if skin else None)
    return kit, sources


def _bbox(recs):
    xs, ys = [], []
    for r in recs:
        for segs, _ in G.parse_path(r["d"]):
            for p in G.sample(segs, 3):
                xs.append(p[0]); ys.append(p[1])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _strokes(recs, palette):
    out = []
    for r in recs:
        st = r["style"]; fill = (DI.colour(st.get("fill"), {}) or "none").lower()
        if fill in ("none", "transparent"):
            continue
        key = next((k for k, v in palette.items() if v == fill), None)
        if not key:
            key = f"c{len(palette)}"; palette[key] = fill
        s = {"d": r["d"], "fill": key}
        if st.get("fill-rule") == "evenodd":
            s["rule"] = "evenodd"
        if st.get("opacity") not in (None, "1", "1.0"):
            s["opacity"] = float(st["opacity"])
        out.append(s)
    return out


def build(folder, name="Humaaan", picks=None, source_url="https://www.humaaans.com/"):
    """-> (puppet, report). picks: {"head", "body", "legs"} piece names for the default look"""
    kit, sources = read_kit(folder)
    palette = {}
    shapes = {k: {n: _strokes(recs, palette) for n, (recs, _) in sorted(kit[k].items())} for k in kit}
    picks = dict(picks or {})
    for k in kit:
        if picks.get(k) not in shapes[k]:
            picks[k] = next((n for n in shapes[k] if not n.startswith("sit-")), next(iter(shapes[k])))
    W, H = SIZE
    lb = _bbox([{"d": s["d"]} for s in shapes["legs"][picks["legs"]]])
    waist = [round((lb[0] + lb[2]) / 2, 1) if lb else 150.0, REST["legs"][1] + 6]
    skin = kit["head"][picks["head"]][1]
    neck = [round((skin[0] + skin[2]) / 2, 1), round(skin[3] - 4, 1)] if skin else [140.0, 90.0]
    parts = {"hip": {"parent": None, "pivot": [W / 2, H], "z": 0, "strokes": []},
             "legs": {"parent": "hip", "pivot": [W / 2, H], "z": Z["legs"], "strokes": shapes["legs"][picks["legs"]]},
             "body": {"parent": "legs", "pivot": waist, "z": Z["body"], "strokes": shapes["body"][picks["body"]]},
             "head": {"parent": "body", "pivot": neck, "z": Z["head"], "strokes": shapes["head"][picks["head"]]}}
    sets = {"legs": "legs", "body": "outfit", "head": "hair"}
    swaps = {sets[k]: {"anchor": k, "z": Z[k], "replaces": k, "shapes": shapes[k]} for k in kit}
    pz = {"format": "doodleberry.puppet", "version": "0.12", "name": name, "template": "doodle", "artboard": [W, H], "ground": H,
          "palette": palette, "parts": parts, "swaps": swaps,
          "meta": {"author": "Pablo Stanley (Humaaans)", "license": "CC0-1.0 (humaaans.com; releases before were CC BY 4.0, so credit is kept)",
                   "source_url": source_url, "provenance": "dbe/humaaans.py from the Humaaans 'Single Pieces' SVGs at their rest layout",
                   "picks": picks, "sources": sources}}
    return pz, {"pieces": {k: len(v) for k, v in shapes.items()}, "picks": picks, "palette_slots": len(palette), "waist": waist, "neck": neck}
