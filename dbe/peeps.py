"""Open Peeps (Pablo Stanley, CC0) to a puppet with mix-and-match swap sets (WP-16).

openpeeps.com offers each finished peep as an SVG exported from Sketch. Every one is the same 240 x 324 bust, with its
pieces in named groups at fixed offsets: `body/<name>`, `head/<name>` (the head with its hair or hat),
`face/<name>`, `facial-hair/<name>` and `accessories/<name>` (`*-None` when absent). Reading many peeps therefore
recovers a parts kit: each named piece once, already placed. The puppet built from it:

    hip -> body -> head -> face, beard, glasses

Each piece category is also a swap set that replaces its part: `outfit` (bodies), `hair` (heads), `expression`
(faces), `beard_style` and `accessory`. So `{"hair": "Turban", "expression": "Smile-Big"}` in a pose (or a cast entry's
pose) changes the look, and the part's own drawing is the default pick. Colours: the ink is the palette's `ink`, the
white fill is `paper`, anything else gets a named slot.
"""
import hashlib
import json
import re
from pathlib import Path

from . import drawing_import as DI
from . import geom as G

CATS = {"body": ("body", "outfit"), "head": ("head", "hair"), "face": ("face", "expression"),
        "facial-hair": ("beard", "beard_style"), "accessories": ("glasses", "accessory")}
Z = {"body": 10, "head": 20, "face": 30, "beard": 31, "glasses": 32}
SIZE = (240, 324)


def _piece(names):
    """the (category, name) of an item from its group path, e.g. [..., 'a-person/bust', 'head/Turban', ...]"""
    for n in names:
        if "/" in n:
            cat, nm = n.split("/", 1)
            if cat in CATS:
                return cat, nm
    return None


def read_kit(folder):
    """{cat: {name: [records]}}, sources {file: sha256}; every SVG must be the 240 x 324 bust"""
    kit = {c: {} for c in CATS}; sources = {}
    for f in sorted(Path(folder).glob("*.svg")):
        src = DI.read_svg(f)
        if [round(v) for v in src["size"]] != list(SIZE):
            raise ValueError(f"{f.name}: not an Open Peeps bust ({src['size']})")
        sources[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        got = {}
        for r in src["items"]:
            pc = _piece(r["names"])
            if pc:
                got.setdefault(pc, []).append(r)
        for (cat, nm), recs in got.items():
            kit[cat].setdefault(nm, recs)   # the same piece in another peep is the same drawing
    return kit, sources


# the full kit ("Separate Atoms", one SVG per piece on a shared canvas per category): each piece goes into the bust at
# the scale and offset the site's finished busts use (measured: 150/710, the group offsets above, matching to 0.01 px)
ATOM_SCALE = 150 / 710
ATOM_AT = {"body": (31.056338, 135.052838), "head": (78.591549, 38.043053), "face": (112.183099, 77.354207),
           "facial-hair": (104.577451, 109.479380), "accessories": (88.521127, 88.978474)}


def read_atoms(folder):
    """the kit's Separate Atoms folder -> ({cat: {name: [records]}}, sources {relative path: sha256})"""
    root = Path(folder); kit = {c: {} for c in CATS}; sources = {}
    for cat in CATS:
        for f in sorted((root / cat).glob("*.svg")):
            src = DI.read_svg(f); sources[str(f.relative_to(root))] = hashlib.sha256(f.read_bytes()).hexdigest()
            ox, oy = ATOM_AT[cat]; M = [ATOM_SCALE, 0, 0, ATOM_SCALE, ox, oy]
            nm = re.sub(r"\s+", "-", f.stem.strip())
            if nm.startswith("*"):
                continue   # "* None": the empty choice, added as "none"
            kit[cat][nm] = [{**r, "d": DI.transform_d(r["d"], M)} for r in src["items"]]
    return kit, sources


def _strokes(recs, palette):
    out = []
    for r in recs:
        st = r["style"]; fill = (DI.colour(st.get("fill"), {}) or "none").lower()
        if fill in ("none", "transparent"):
            continue
        key = {"#000000": "ink", "#ffffff": "paper"}.get(fill)
        if not key:
            key = next((k for k, v in palette.items() if v == fill), None) or f"c{len(palette) - 1}"
            palette[key] = fill
        s = {"d": r["d"], "fill": key}
        if st.get("fill-rule") == "evenodd":
            s["rule"] = "evenodd"
        if st.get("opacity") not in (None, "1", "1.0"):
            s["opacity"] = float(st["opacity"])
        out.append(s)
    return out


def _bbox(strokes):
    xs, ys = [], []
    for st in strokes:
        for segs, _ in G.parse_path(st["d"]):
            for p in G.sample(segs, 3):
                xs.append(p[0]); ys.append(p[1])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def build(folder, name="Peep", picks=None, source_url="https://www.openpeeps.com/"):
    """the site's busts in `folder`, or the kit's Separate Atoms folder (subfolders head, face, ...) -> (puppet, report). picks: {category: piece name} for the default look (else the most
    common: the first peep's)"""
    kit, sources = read_atoms(folder) if (Path(folder) / "head").is_dir() else read_kit(folder)
    if not kit["body"] or not kit["head"]:
        raise ValueError("no Open Peeps pieces found (body/... and head/... groups)")
    palette = {"ink": "#000000", "paper": "#ffffff"}
    shapes = {c: {nm: _strokes(recs, palette) for nm, recs in sorted(kit[c].items())} for c in CATS}
    for c in ("facial-hair", "accessories"):   # "*-None" groups hold no paths: an explicit empty choice
        shapes[c] = {"none": [], **shapes[c]}
    picks = dict(picks or {})
    for c in CATS:
        if c not in picks or picks[c] not in shapes[c]:
            picks[c] = "none" if c in ("facial-hair", "accessories") else next(iter(shapes[c]))
    W, H = SIZE
    bb = _bbox(shapes["body"][picks["body"]]) or (0, 0, W, H)
    neck = [W / 2, round(bb[1] + 10, 1)]   # where the head meets the body's top (the bust is centred)
    parts = {"hip": {"parent": None, "pivot": [W / 2, H], "z": 0, "strokes": []},
             "body": {"parent": "hip", "pivot": [W / 2, H], "z": Z["body"], "strokes": shapes["body"][picks["body"]]},
             "head": {"parent": "body", "pivot": neck, "z": Z["head"], "strokes": shapes["head"][picks["head"]]}}
    for c in ("face", "facial-hair", "accessories"):
        part = CATS[c][0]
        parts[part] = {"parent": "head", "pivot": neck, "z": Z[part], "strokes": shapes[c][picks[c]]}
    swaps = {CATS[c][1]: {"anchor": CATS[c][0], "z": Z[CATS[c][0]], "replaces": CATS[c][0],   # drawn in its part's place, moving with it
                          "shapes": shapes[c]} for c in CATS}
    pz = {"format": "doodleberry.puppet", "version": "0.12", "name": name, "template": "doodle", "artboard": [W, H], "ground": H,
          "palette": palette, "parts": parts, "swaps": swaps,
          "meta": {"author": "Pablo Stanley (Open Peeps)", "license": "CC0-1.0", "source_url": source_url,
                   "provenance": "dbe/peeps.py from openpeeps.com's per-peep SVGs: pieces recovered by group name",
                   "picks": {c: picks[c] for c in CATS}, "sources": sources}}
    rep = {"peeps_read": len(sources), "pieces": {c: len(shapes[c]) for c in CATS}, "picks": picks, "palette": palette}
    return pz, rep


# Full-body peeps from the kit (WP-16): a headless pose ("pose/standing/*" or "pose/sitting/*", one canvas per kind)
# with the head on top, at the kit's own full-size layout ("Separate Atoms/a person/standing.svg" and "sitting.svg",
# read on the owner's machine): the pose at (-121, 634) standing or (-81, 637) sitting, the head at (404, 180) or
# (345, 180), and inside the head the face at (159, 186), facial hair at (123, 338) and accessories at (47, 241).
FULL = {"standing": {"pose": (-121.0, 634.0), "head": (404.0, 180.0), "size": (1179, 3291)},
        "sitting": {"pose": (-81.0, 637.0), "head": (345.0, 180.0), "size": (1647, 2500)}}
IN_HEAD = {"head": (0.0, 0.0), "face": (159.0, 186.0), "facial-hair": (123.0, 338.0), "accessories": (47.0, 241.0)}


def build_full(folder, kind="standing", name="Peep", picks=None, scale=0.3, source_url="https://www.openpeeps.com/"):
    """the kit's Separate Atoms folder -> (puppet, report): hip -> body (the pose) -> head -> face, beard, glasses, with swap sets
    pose (the kind's poses), hair, expression, beard_style and accessory. scale: atom pixels to artboard units."""
    root = Path(folder); L = FULL[kind]; S = scale; palette = {"ink": "#000000", "paper": "#ffffff"}; sources = {}

    def load(sub, at):
        out = {}
        for f in sorted((root / sub).glob("*.svg")):
            nm = re.sub(r"\s+", "-", f.stem.strip())
            if nm.startswith("*"):
                continue
            src = DI.read_svg(f); sources[str(f.relative_to(root))] = hashlib.sha256(f.read_bytes()).hexdigest()
            M = [S, 0, 0, S, at[0] * S, at[1] * S]
            out[nm] = _strokes([{**r, "d": DI.transform_d(r["d"], M)} for r in src["items"]], palette)
        return out
    hx, hy = L["head"]
    shapes = {"pose": load(f"pose/{kind}", L["pose"])}
    for cat, (dx, dy) in IN_HEAD.items():
        shapes[cat] = load(cat, (hx + dx, hy + dy))
    for c in ("facial-hair", "accessories"):
        shapes[c] = {"none": [], **shapes[c]}
    if not shapes["pose"] or not shapes["head"]:
        raise ValueError(f"no pose/{kind} or head atoms under {folder}")
    picks = dict(picks or {})
    for c in shapes:
        if picks.get(c) not in shapes[c]:
            picks[c] = "none" if c in ("facial-hair", "accessories") else next(iter(shapes[c]))
    W, H = round(L["size"][0] * S), round(L["size"][1] * S)
    pb = _bbox(shapes["pose"][picks["pose"]])
    ground = round(pb[3], 1) if pb else H
    neck = [round((hx + 236) * S, 1), round((hy + 520) * S, 1)]   # the bottom of the head atom's neck, near its centre
    parts = {"hip": {"parent": None, "pivot": [round(W / 2, 1), ground], "z": 0, "strokes": []},
             "body": {"parent": "hip", "pivot": [round(W / 2, 1), ground], "z": 10, "strokes": shapes["pose"][picks["pose"]]},
             "head": {"parent": "body", "pivot": neck, "z": 20, "strokes": shapes["head"][picks["head"]]}}
    names = {"face": ("face", "expression", 30), "facial-hair": ("beard", "beard_style", 31), "accessories": ("glasses", "accessory", 32)}
    for c, (part, _, z) in names.items():
        parts[part] = {"parent": "head", "pivot": neck, "z": z, "strokes": shapes[c][picks[c]]}
    swaps = {"pose": {"anchor": "body", "z": 10, "replaces": "body", "shapes": shapes["pose"]},
             "hair": {"anchor": "head", "z": 20, "replaces": "head", "shapes": shapes["head"]}}
    for c, (part, sid, z) in names.items():
        swaps[sid] = {"anchor": part, "z": z, "replaces": part, "shapes": shapes[c]}
    pz = {"format": "doodleberry.puppet", "version": "0.12", "name": name, "template": "doodle", "artboard": [W, H], "ground": ground,
          "palette": palette, "parts": parts, "swaps": swaps,
          "meta": {"author": "Pablo Stanley (Open Peeps)", "license": "CC0-1.0", "source_url": source_url,
                   "provenance": f"dbe/peeps.py build_full ({kind}): the kit's Separate Atoms at its own full-size layout",
                   "picks": picks, "sources": sources}}
    return pz, {"kind": kind, "pieces": {c: len(v) for c, v in shapes.items()}, "picks": picks, "artboard": [W, H], "ground": ground}
