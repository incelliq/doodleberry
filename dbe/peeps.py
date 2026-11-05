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
    pz, ls = add_lipsync(pz)
    pz, ar = add_arms(pz, Path(__file__).resolve().parent.parent / "puppet" / "clips" / "humanoid.json")
    return pz, {**rep, **ls, **ar}


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
    pz, ls = add_lipsync(pz)
    return pz, {"kind": kind, "pieces": {c: len(v) for c, v in shapes.items()}, "picks": picks, "artboard": [W, H], "ground": ground, **ls}


# ---------- lip-sync (WP-16): mouths out of the kit's faces ----------
# Each face is drawn whole (brows, eyes, nose, mouth in one path). The nose is the one piece nearly every face shares;
# what lies below it is the mouth. Faces lose their mouths, and a "mouth" swap set takes the kit's own mouths for the
# visemes (the faces share one frame, so a mouth from one face sits right on another) and each face's own mouth as
# "rest-<face>"; a layer set per face picks the face and its resting mouth together.
VISEME_FACES = {"closed": ["Serious", "Tired", "Suspicious", "Blank"], "small": ["Cute", "Contempt", "Calm"],
                "mid": ["Concerned-Fear", "Concerned", "Eating-Happy"], "wide": ["Explaining", "Smile-LOL"],
                "O": ["Cheeky", "Awe"], "FV": ["Hectic", "Smile-Teeth-Gap", "Smile-Big", "Happy-Grin"],
                "smile": ["Smile", "Smiling", "Calm"], "frown": ["Solemn", "Very-Angry", "Old"]}


def _subpaths(d):
    return [s.strip() for s in re.split(r"(?=M)", d.strip()) if s.strip()]


def _sbox(d):
    pts = [p for segs, _ in G.parse_path(d) for p in G.sample(segs, 4)]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)) if pts else None


def split_mouth(faces):
    """{face: strokes} -> ({face: strokes without the mouth}, {face: mouth strokes}, nose box). The nose: the subpath
    box most faces share (to a unit); the mouth: what starts below each face's nose (the subpath nearest that box)"""
    from collections import Counter
    boxes = {nm: [(st, sp, _sbox(sp)) for st in strokes if st.get("d") for sp in _subpaths(st["d"])] for nm, strokes in faces.items()}
    common = Counter(tuple(round(v) for v in b) for rows in boxes.values() for _, _, b in rows if b).most_common(1)
    if not common:
        return faces, {}, None
    nb = common[0][0]; nc = ((nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2)
    rest, mouths = {}, {}
    for nm, rows in boxes.items():
        rows = [r for r in rows if r[2]]
        if not rows:
            rest[nm], mouths[nm] = faces[nm], []; continue
        nose = min(rows, key=lambda r: abs((r[2][0] + r[2][2]) / 2 - nc[0]) + abs((r[2][1] + r[2][3]) / 2 - nc[1]))
        below = lambda r: r is not nose and r[2][1] >= nose[2][3] - 2
        def group(sel):
            out = []
            for st in faces[nm]:
                sps = [sp for (s2, sp, b) in rows if s2 is st and sel((s2, sp, b))]
                if sps:
                    out.append({**st, "d": " ".join(sps)})
            return out
        rest[nm] = group(lambda r: not below(r)); mouths[nm] = group(below)
    return rest, mouths, nb


def add_lipsync(pz, swap="expression", part="face"):
    """the puppet with a mouth swap set for lip-sync, its faces without their mouths, and a layer set per face"""
    sw = pz["swaps"].get(swap)
    if not sw:
        return pz, {"lipsync": "no faces"}
    rest, mouths, nose = split_mouth(sw["shapes"])
    norm = lambda s: re.sub(r"[\s_]+", "-", s).lower()
    by = {norm(k): k for k in mouths if mouths[k]}
    pick = pz.get("meta", {}).get("picks", {}).get("face")
    shapes, used = {}, {}
    for vis, cands in VISEME_FACES.items():
        k = next((by[norm(c)] for c in cands if norm(c) in by), None)
        if k:
            shapes[vis] = mouths[k]; used[vis] = k
    for k, m in mouths.items():
        shapes[f"rest-{k}"] = m
    sw["shapes"] = rest
    if pz["parts"].get(part, {}).get("strokes") and pick in rest:
        pz["parts"][part]["strokes"] = rest[pick]
    pz["swaps"]["mouth"] = {"anchor": part, "z": sw.get("z", Z["face"]) + 0.5, "talk": [v for v in ("closed", "small", "mid", "wide") if v in shapes], "shapes": shapes}
    pz["layer_sets"] = {**(pz.get("layer_sets") or {}), **{k: {swap: k, "mouth": f"rest-{k}"} for k in rest if mouths.get(k)}}
    pz["version"] = max(pz.get("version", "0.12"), "0.13", key=lambda v: tuple(int(x) for x in v.split(".")))
    return pz, {"lipsync": {"visemes": used, "faces_split": sum(1 for k in mouths if mouths[k]), "nose_box": nose}}


# ---------- gesturing arms for the bust (WP-16) ----------
# The kit's bust bodies draw their arms into one outline with the body, so they cannot be moved. These are original
# arms in the kit's manner (a white sleeve and hand, a heavy black line), hung from each shoulder behind the body:
# at rest they hang inside its silhouette, hidden; raised, they come out past the shoulder. The humanoid gesture clips
# drive them (same part names, same rest: hanging down), copied into the puppet with their hand and face keys.
ARM_CLIPS = ("point_R", "point_L", "wave_R", "wave_L", "present_R", "present_L", "talk_open_palms", "shrug")


def _arm_R(sx, sy, l1=44, l2=38):
    up = (f"M{sx - 10} {sy - 2} C{sx - 10} {sy - 10} {sx + 10} {sy - 10} {sx + 10} {sy - 2} L{sx + 11} {sy + l1} "
          f"C{sx + 11} {sy + l1 + 8} {sx - 11} {sy + l1 + 8} {sx - 11} {sy + l1} Z")
    fy = sy + l1
    fore = f"M{sx - 8} {fy - 2} L{sx - 7} {fy + l2} C{sx - 7} {fy + l2 + 7} {sx + 7} {fy + l2 + 7} {sx + 7} {fy + l2} L{sx + 8} {fy - 2} Z"
    hy = fy + l2
    hand = [{"d": f"M{sx - 8} {hy + 8} A8 10 0 1 0 {sx + 8} {hy + 8} A8 10 0 1 0 {sx - 8} {hy + 8} Z", "fill": "paper", "stroke": "ink", "width": 3},
            {"d": f"M{sx - 11} {hy + 1} C{sx - 15} {hy + 5} {sx - 13} {hy + 11} {sx - 8} {hy + 9}", "fill": "none", "stroke": "ink", "width": 3}]
    point = [{"d": f"M{sx - 7} {hy + 7} A7 8 0 1 0 {sx + 7} {hy + 7} A7 8 0 1 0 {sx - 7} {hy + 7} Z", "fill": "paper", "stroke": "ink", "width": 3},
             {"d": f"M{sx - 3} {hy + 12} L{sx - 3} {hy + 30} C{sx - 3} {hy + 34} {sx + 3} {hy + 34} {sx + 3} {hy + 30} L{sx + 3} {hy + 12} Z", "fill": "paper", "stroke": "ink", "width": 3}]
    return ({"upperarm": [{"d": up, "fill": "paper", "stroke": "ink", "width": 3}], "forearm": [{"d": fore, "fill": "paper", "stroke": "ink", "width": 3}], "hand": hand},
            {"upper": (sx, sy), "fore": (sx, fy), "hand": (sx, hy)}, point)


def add_arms(pz, clips_file):
    """the bust puppet with arms (upperarm/forearm/hand, L and R) behind the body and the humanoid arm clips. The arm
    parts draw nothing themselves: their drawings are swaps (arm_up_<s>, arm_fore_<s>, hand_<s>_pose) that a gesture
    clip shows for as long as it plays, so a bust whose outfit has gaps (a mug, hands on hips) shows no arm at rest"""
    W = pz["artboard"][0]; bb = _bbox(pz["parts"]["body"]["strokes"]) or (35, 128, 201, 285)
    cx = W / 2; sy = round(bb[1] + 46); dx = round((bb[2] - bb[0]) * 0.3)
    zb = pz["parts"]["body"]["z"]
    shapes, piv, point = _arm_R(cx + dx, sy)
    mirror = lambda strokes: [{**st, "d": DI.transform_d(st["d"], [-1, 0, 0, 1, 2 * cx, 0])} for st in strokes]
    for side, f in (("R", lambda s: s), ("L", mirror)):
        px = (lambda q: q) if side == "R" else (lambda q: (round(2 * cx - q[0], 1), q[1]))
        for part, key, z, parent in (("upperarm", "arm_up", zb - 3, "body"), ("forearm", "arm_fore", zb - 2, f"upperarm_{side}")):
            pz["parts"][f"{part}_{side}"] = {"parent": parent, "pivot": list(px(piv["upper" if part == "upperarm" else "fore"])), "z": z, "strokes": []}
            pz["swaps"][f"{key}_{side}"] = {"anchor": f"{part}_{side}", "z": z, "replaces": f"{part}_{side}", "shapes": {"on": f(shapes[part])}}
        pz["parts"][f"hand_{side}"] = {"parent": f"forearm_{side}", "pivot": list(px(piv["hand"])), "z": zb - 1, "strokes": []}
        pz["swaps"][f"hand_{side}_pose"] = {"anchor": f"hand_{side}", "z": zb - 1, "replaces": f"hand_{side}", "shapes": {"open": f(shapes["hand"]), "point": f(point), "fist": f(point[:1])}}
    lib = json.loads(Path(clips_file).read_text())["clips"]; clips = {}
    for k in ARM_CLIPS:
        if k not in lib:
            continue
        c = json.loads(json.dumps(lib[k])); sw = c.setdefault("swaps", {})
        for side in ("R", "L"):
            if any(t.endswith(f"_{side}") for t in c.get("tracks", {})):
                sw[f"arm_up_{side}"] = [[0, "on"]]; sw[f"arm_fore_{side}"] = [[0, "on"]]
                hp = sw.get(f"hand_{side}_pose"); sw[f"hand_{side}_pose"] = ([[0, "open"]] + [kk for kk in hp if kk[0] > 0]) if hp else [[0, "open"]]
        clips[k] = c
    pz["clips"] = {**(pz.get("clips") or {}), **clips}
    pz["acting"] = {**(pz.get("acting") or {}), "gestures": "humanoid"}
    return pz, {"arms": {"shoulders": [[round(2 * cx - piv["upper"][0], 1), sy], [piv["upper"][0], sy]], "clips": list(clips)}}
