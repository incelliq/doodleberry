"""Three new templates with an example character and a clip library each (WP-16): a quadruped (Biscuit, a dog), a bird
(Pim) and an object with a face (Kettle, a teapot). Original designs drawn from shapes here.

    python puppet/examples/make_critters.py
      -> puppet/templates/{quadruped,bird,object}.json and .js, puppet/clips/{quadruped,bird,object}.json and .js,
         puppet/examples/{biscuit,pim,kettle}.puppet.json

Every part is a plain cut-out with a parent and a pivot, so the loader, the bake and every exporter draw it like any
other puppet; the clips are angle tracks, root offsets and mouth or eye swaps.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INK = "ink"


def ell(cx, cy, rx, ry):
    return f"M{cx - rx} {cy} A{rx} {ry} 0 1 0 {cx + rx} {cy} A{rx} {ry} 0 1 0 {cx - rx} {cy} Z"


def S(d, fill, width=5, stroke=INK, **kw):
    return {"d": d, "fill": fill, "stroke": stroke, "width": width, **kw}


def limb(x0, y0, x1, y1, w):
    """a rounded capsule from (x0, y0) to (x1, y1)"""
    import math
    a = math.atan2(y1 - y0, x1 - x0); nx, ny = -math.sin(a) * w / 2, math.cos(a) * w / 2
    return (f"M{x0 + nx:.1f} {y0 + ny:.1f} L{x1 + nx:.1f} {y1 + ny:.1f} A{w / 2} {w / 2} 0 0 0 {x1 - nx:.1f} {y1 - ny:.1f} "
            f"L{x0 - nx:.1f} {y0 - ny:.1f} A{w / 2} {w / 2} 0 0 0 {x0 + nx:.1f} {y0 + ny:.1f} Z")


def eyes_set(cx, cy, dx, r):
    """open, half and closed eyes and the pupils, centred at (cx, cy), dx apart"""
    o = [S(ell(cx - dx / 2, cy, r, r * 1.15), "eye", 4), S(ell(cx + dx / 2, cy, r, r * 1.15), "eye", 4)]
    h = [S(f"M{cx - dx / 2 - r} {cy} A{r} {r * 0.6} 0 0 0 {cx - dx / 2 + r} {cy} Z", "eye", 4), S(f"M{cx + dx / 2 - r} {cy} A{r} {r * 0.6} 0 0 0 {cx + dx / 2 + r} {cy} Z", "eye", 4)]
    c = [S(f"M{cx - dx / 2 - r} {cy} Q{cx - dx / 2} {cy + r * 0.6} {cx - dx / 2 + r} {cy}", "none", 5), S(f"M{cx + dx / 2 - r} {cy} Q{cx + dx / 2} {cy + r * 0.6} {cx + dx / 2 + r} {cy}", "none", 5)]
    p = [S(ell(cx - dx / 2 + r * 0.15, cy + r * 0.1, r * 0.45, r * 0.5), "ink", 0, stroke="none"), S(ell(cx + dx / 2 + r * 0.15, cy + r * 0.1, r * 0.45, r * 0.5), "ink", 0, stroke="none")]
    return {"open": o, "half": h, "closed": c}, {"default": p}


def template(tid, artboard, ground, note, parts, swaps, palette):
    return {"template": tid, "version": "0.1", "artboard": artboard, "ground": ground, "note": note,
            "parts": [{"id": k, "parent": v["parent"], "pivot": v["pivot"], "z": v["z"], "required": v.get("required", True), "label": v["label"]} for k, v in parts.items()],
            "swaps": swaps, "palette": list(palette), "guide": []}


def puppet(name, tid, artboard, ground, parts, swaps, palette, about):
    return {"format": "doodleberry.puppet", "version": "0.6", "name": name, "template": tid, "artboard": artboard, "ground": ground, "palette": palette,
            "parts": {k: {"parent": v["parent"], "pivot": v["pivot"], "z": v["z"], "strokes": v.get("strokes", [])} for k, v in parts.items()},
            "swaps": swaps, "meta": {"author": "doodleberry (generated example)", "license": "CC0-1.0", "created": "2026-11-03", "note": about}}


def key(*pairs):
    return [[round(t, 3), v] for t, v in pairs]


# ----------------------------------------------------------------------------------------------- Biscuit, a dog
def biscuit():
    pal = {"fur": "#d9a066", "fur2": "#a8703d", "nose": "#2a1a10", "eye": "#ffffff", "tongue": "#e8707a", "ink": "#24160e", "collar": "#3a7fd0"}
    P = {"hip": {"parent": None, "pivot": [350, 330], "z": 20, "label": "Root (no drawing)", "required": False},
         "body": {"parent": "hip", "pivot": [350, 330], "z": 22, "label": "Body", "strokes": [S(ell(340, 320, 170, 82), "fur"), S("M250 300 Q300 280 350 300", "none", 4, stroke="fur2")]},
         "head": {"parent": "body", "pivot": [470, 275], "z": 40, "label": "Head", "strokes": [S(ell(520, 228, 74, 64), "fur"), S(ell(588, 255, 42, 30), "fur"),
                                                                                              S(ell(624, 246, 12, 9), "nose", 3), S("M470 290 Q520 312 560 292", "none", 7, stroke="collar")]},
         "ear_back": {"parent": "head", "pivot": [495, 182], "z": 36, "label": "Ear (far side)", "strokes": [S("M480 175 Q450 200 462 262 Q482 272 498 230 Q508 195 495 178 Z", "fur2")]},
         "ear_near": {"parent": "head", "pivot": [540, 178], "z": 44, "label": "Ear (near side)", "strokes": [S("M528 172 Q500 196 512 262 Q534 274 548 230 Q558 194 545 175 Z", "fur2")]},
         "tail": {"parent": "body", "pivot": [178, 290], "z": 18, "label": "Tail", "strokes": [S("M182 296 Q140 270 132 220 Q130 205 142 206 Q150 250 190 280 Z", "fur")]}}
    for side, x, z in (("front_back", 440, 14), ("front_near", 475, 30), ("hind_back", 230, 12), ("hind_near", 262, 28)):
        fill = "fur2" if "back" in side else "fur"
        P[f"{side}_upper"] = {"parent": "body", "pivot": [x, 360], "z": z, "label": f"{side.replace('_', ' ')} leg (upper)", "strokes": [S(limb(x, 360, x, 455, 40), fill)]}
        P[f"{side}_lower"] = {"parent": f"{side}_upper", "pivot": [x, 455], "z": z + 1, "label": f"{side.replace('_', ' ')} leg (lower)",
                              "strokes": [S(limb(x, 455, x, 560, 34), fill), S(ell(x + 10, 566, 26, 14), fill)]}
    eo, pu = eyes_set(530, 214, 40, 13)
    SW = {"eyes": {"anchor": "head", "z": 46, "shapes": eo}, "pupils": {"anchor": "head", "z": 47, "shapes": pu, "movable": 6},
          "mouth": {"anchor": "head", "z": 45, "talk": ["closed", "small", "wide"], "shapes": {
              "closed": [S("M590 280 Q600 288 612 280", "none", 4)],
              "small": [S("M588 278 Q600 296 614 278 Z", "tongue", 4)],
              "wide": [S("M584 276 Q600 312 618 276 Z", "tongue", 4), S("M594 292 Q600 300 606 292", "none", 3)]}}}
    tparts = {k: {**v} for k, v in P.items()}
    tswaps = [{"id": "eyes", "anchor": "head", "z": 46, "shapes": ["open", "half", "closed"], "required": ["open", "closed"], "label": "Eyes"},
              {"id": "pupils", "anchor": "head", "z": 47, "shapes": ["default"], "required": [], "movable": 6, "label": "Pupils"},
              {"id": "mouth", "anchor": "head", "z": 45, "shapes": ["closed", "small", "wide"], "required": ["closed", "wide"], "talk": ["closed", "small", "wide"], "label": "Mouth"}]
    T = template("quadruped", [700, 600], 580, "Four-legged animals in side view, facing right: a body on the hips, a head on the body, two-part legs (front and hind, far and near), ears and a tail. The near legs draw in front of the body.",
                 tparts, tswaps, pal)
    L = {"template": "quadruped", "note": "Angles in degrees from the drawn rest pose; the animal faces right, so a negative angle swings a part forward and up.", "presets": {}, "clips": {
        "idle": {"duration": 2.0, "loop": True, "tracks": {"body": key((0, 0), (1, 1.2), (2, 0)), "head": key((0, 0), (1, -2.5), (2, 0)), "tail": key((0, 0), (0.5, 10), (1, 0), (1.5, -6), (2, 0)),
                                                             "ear_near": key((0, 0), (1, 3), (2, 0))}},
        "walk": {"duration": 0.8, "loop": True, "tracks": {
            "front_near_upper": key((0, -18), (0.4, 18), (0.8, -18)), "front_near_lower": key((0, 0), (0.2, 22), (0.4, 0), (0.8, 0)),
            "hind_back_upper": key((0, -18), (0.4, 18), (0.8, -18)), "hind_back_lower": key((0, 0), (0.2, -20), (0.4, 0), (0.8, 0)),
            "front_back_upper": key((0, 18), (0.4, -18), (0.8, 18)), "front_back_lower": key((0, 0), (0.4, 0), (0.6, 22), (0.8, 0)),
            "hind_near_upper": key((0, 18), (0.4, -18), (0.8, 18)), "hind_near_lower": key((0, 0), (0.4, 0), (0.6, -20), (0.8, 0)),
            "head": key((0, -2), (0.4, 2), (0.8, -2)), "tail": key((0, 12), (0.4, -8), (0.8, 12))}, "offset": key((0, [0, 0]), (0.2, [0, -6]), (0.4, [0, 0]), (0.6, [0, -6]), (0.8, [0, 0]))},
        "wag": {"duration": 0.4, "loop": True, "tracks": {"tail": key((0, 0), (0.1, 25), (0.3, -20), (0.4, 0)), "body": key((0, 0), (0.2, 1), (0.4, 0))}},
        "bark": {"duration": 0.7, "tracks": {"head": key((0, 0), (0.12, -12), (0.4, -8), (0.7, 0)), "body": key((0, 0), (0.12, -2), (0.7, 0))}, "swaps": {"mouth": key((0, "closed"), (0.1, "wide"), (0.35, "small"), (0.45, "closed"))}},
        "sit": {"duration": 1.0, "tracks": {"body": key((0, 0), (0.6, -22), (1.0, -22)), "hind_near_upper": key((0, 0), (0.6, -60), (1.0, -60)), "hind_near_lower": key((0, 0), (0.6, 75), (1.0, 75)),
                                             "hind_back_upper": key((0, 0), (0.6, -60), (1.0, -60)), "hind_back_lower": key((0, 0), (0.6, 75), (1.0, 75)), "head": key((0, 0), (0.6, 14), (1.0, 14)),
                                             "front_near_upper": key((0, 0), (0.6, 22), (1.0, 22)), "front_back_upper": key((0, 0), (0.6, 22), (1.0, 22))},
                "offset": key((0, [0, 0]), (0.6, [0, 30]), (1.0, [0, 30]))},
        "talk": {"duration": 0.5, "loop": True, "tracks": {"head": key((0, 0), (0.25, -3), (0.5, 0)), "ear_near": key((0, 0), (0.25, 4), (0.5, 0))}}}}
    return T, L, puppet("Biscuit", "quadruped", [700, 600], 580, P, SW, pal, "a friendly dog, drawn from shapes by make_critters.py")


# ----------------------------------------------------------------------------------------------- Pim, a bird
def pim():
    pal = {"plume": "#4fa3d9", "plume2": "#2f6f9f", "belly": "#f4e2b8", "beak": "#f2a33a", "leg": "#e07a3a", "eye": "#ffffff", "ink": "#24160e"}
    P = {"hip": {"parent": None, "pivot": [250, 450], "z": 20, "label": "Root (no drawing)", "required": False},
         "body": {"parent": "hip", "pivot": [250, 430], "z": 22, "label": "Body", "strokes": [S(ell(250, 370, 112, 96), "plume"), S(ell(272, 395, 66, 62), "belly", 0, stroke="none")]},
         "head": {"parent": "body", "pivot": [290, 300], "z": 40, "label": "Head", "strokes": [S(ell(318, 232, 70, 66), "plume")]},
         "crest": {"parent": "head", "pivot": [312, 168], "z": 41, "label": "Crest", "strokes": [S("M300 172 Q290 120 318 132 Q322 110 340 140 Q348 150 330 172 Z", "plume2")]},
         "wing_back": {"parent": "body", "pivot": [222, 330], "z": 18, "label": "Wing (far side)", "strokes": [S("M222 330 Q150 330 118 400 Q170 410 236 372 Z", "plume2")]},
         "wing_near": {"parent": "body", "pivot": [232, 335], "z": 30, "label": "Wing (near side)", "strokes": [S("M232 335 Q170 345 150 420 Q210 425 250 380 Z", "plume2")]},
         "tail": {"parent": "body", "pivot": [148, 400], "z": 16, "label": "Tail", "strokes": [S("M150 398 L70 380 L84 410 L64 432 L150 420 Z", "plume2")]},
         "leg_back": {"parent": "hip", "pivot": [238, 452], "z": 14, "label": "Leg (far side)", "strokes": [S("M238 452 L236 568", "none", 6, stroke="leg"), S("M214 572 L262 572 M236 568 L250 580", "none", 6, stroke="leg")]},
         "leg_near": {"parent": "hip", "pivot": [266, 452], "z": 25, "label": "Leg (near side)", "strokes": [S("M266 452 L268 568", "none", 7, stroke="leg"), S("M244 574 L294 574 M268 568 L282 582", "none", 7, stroke="leg")]}}
    eo, pu = eyes_set(330, 222, 36, 12)
    SW = {"eyes": {"anchor": "head", "z": 46, "shapes": eo}, "pupils": {"anchor": "head", "z": 47, "shapes": pu, "movable": 5},
          "mouth": {"anchor": "head", "z": 45, "talk": ["closed", "small", "wide"], "shapes": {
              "closed": [S("M372 236 L418 250 L372 262 Z", "beak", 4)],
              "small": [S("M372 232 L416 240 L374 250 Z", "beak", 4), S("M374 254 L412 262 L372 268 Z", "beak", 4)],
              "wide": [S("M372 226 L414 230 L374 246 Z", "beak", 4), S("M374 258 L410 274 L372 276 Z", "beak", 4)]}}}
    tswaps = [{"id": "eyes", "anchor": "head", "z": 46, "shapes": ["open", "half", "closed"], "required": ["open", "closed"], "label": "Eyes"},
              {"id": "pupils", "anchor": "head", "z": 47, "shapes": ["default"], "required": [], "movable": 5, "label": "Pupils"},
              {"id": "mouth", "anchor": "head", "z": 45, "shapes": ["closed", "small", "wide"], "required": ["closed", "wide"], "talk": ["closed", "small", "wide"], "label": "Beak (lip-sync)"}]
    T = template("bird", [500, 600], 580, "Birds in side view, facing right: a round body, a head with a crest, a beak that talks (the mouth swap), two wings (far and near), a tail and two thin legs.",
                 P, tswaps, pal)
    L = {"template": "bird", "note": "Angles in degrees from the drawn rest pose; the bird faces right.", "presets": {}, "clips": {
        "idle": {"duration": 1.6, "loop": True, "tracks": {"head": key((0, 0), (0.8, -3), (1.6, 0)), "tail": key((0, 0), (0.8, 4), (1.6, 0)), "body": key((0, 0), (0.8, 1), (1.6, 0))}},
        "flap": {"duration": 0.3, "loop": True, "tracks": {"wing_near": key((0, 0), (0.15, 42), (0.3, 0)), "wing_back": key((0, 0), (0.15, 38), (0.3, 0))}, "offset": key((0, [0, 0]), (0.15, [0, -8]), (0.3, [0, 0]))},
        "hop": {"duration": 0.6, "tracks": {"leg_near": key((0, 0), (0.15, 20), (0.45, 20), (0.6, 0)), "leg_back": key((0, 0), (0.15, 20), (0.45, 20), (0.6, 0)), "wing_near": key((0, 0), (0.3, 30), (0.6, 0))},
                "offset": key((0, [0, 0]), (0.3, [0, -60]), (0.6, [0, 0]))},
        "peck": {"duration": 0.5, "tracks": {"body": key((0, 0), (0.2, 12), (0.5, 0)), "head": key((0, 0), (0.2, 28), (0.3, 30), (0.5, 0))}},
        "talk": {"duration": 0.5, "loop": True, "tracks": {"head": key((0, 0), (0.25, -4), (0.5, 0)), "crest": key((0, 0), (0.25, 6), (0.5, 0))}}}}
    return T, L, puppet("Pim", "bird", [500, 600], 580, P, SW, pal, "a small blue bird, drawn from shapes by make_critters.py")


# ----------------------------------------------------------------------------------------------- Kettle, a teapot with a face
def kettle():
    pal = {"porcelain": "#f3efe6", "pattern": "#4f7fbf", "eye": "#ffffff", "blush": "#f2a0a0", "ink": "#24160e"}
    P = {"hip": {"parent": None, "pivot": [300, 560], "z": 20, "label": "Root (no drawing)", "required": False},
         "body": {"parent": "hip", "pivot": [300, 560], "z": 22, "label": "Body (the face is drawn on it)",
                  "strokes": [S(ell(300, 400, 168, 150), "porcelain"), S("M150 450 Q300 500 450 450", "none", 5, stroke="pattern"), S("M170 330 Q300 300 430 330", "none", 5, stroke="pattern"),
                              S("M210 540 L390 540 L370 566 L230 566 Z", "porcelain"), S(ell(225, 440, 18, 10), "blush", 0, stroke="none"), S(ell(375, 440, 18, 10), "blush", 0, stroke="none")]},
         "lid": {"parent": "body", "pivot": [300, 258], "z": 24, "label": "Lid", "strokes": [S("M205 262 Q300 190 395 262 Z", "porcelain"), S(ell(300, 200, 20, 16), "pattern")]},
         "spout": {"parent": "body", "pivot": [452, 430], "z": 20, "label": "Spout", "strokes": [S("M440 400 Q520 400 548 320 L572 330 Q548 450 452 470 Z", "porcelain")]},
         "handle": {"parent": "body", "pivot": [142, 400], "z": 18, "label": "Handle", "strokes": [S("M150 330 Q60 340 66 410 Q72 480 160 470", "none", 22, stroke="ink"), S("M150 330 Q60 340 66 410 Q72 480 160 470", "none", 13, stroke="porcelain")]},
         "arm_L": {"parent": "body", "pivot": [190, 470], "z": 26, "label": "Arm (image left)", "required": False, "strokes": [S(limb(190, 470, 140, 520, 26), "porcelain")]},
         "arm_R": {"parent": "body", "pivot": [410, 470], "z": 26, "label": "Arm (image right)", "required": False, "strokes": [S(limb(410, 470, 460, 520, 26), "porcelain")]}}
    eo, pu = eyes_set(300, 380, 90, 20)
    SW = {"eyes": {"anchor": "body", "z": 40, "shapes": eo}, "pupils": {"anchor": "body", "z": 41, "shapes": pu, "movable": 8},
          "mouth": {"anchor": "body", "z": 42, "talk": ["closed", "small", "wide"], "shapes": {
              "closed": [S("M270 445 Q300 462 330 445", "none", 5)],
              "small": [S("M274 442 Q300 474 326 442 Z", "blush", 4)],
              "wide": [S("M266 438 Q300 500 334 438 Z", "blush", 4)]}}}
    tswaps = [{"id": "eyes", "anchor": "body", "z": 40, "shapes": ["open", "half", "closed"], "required": ["open", "closed"], "label": "Eyes"},
              {"id": "pupils", "anchor": "body", "z": 41, "shapes": ["default"], "required": [], "movable": 8, "label": "Pupils"},
              {"id": "mouth", "anchor": "body", "z": 42, "shapes": ["closed", "small", "wide"], "required": ["closed", "wide"], "talk": ["closed", "small", "wide"], "label": "Mouth"}]
    T = template("object", [600, 600], 580, "Objects with a face (a teapot, a mug, a book): a body that carries the face, a lid or top, a spout or nose part, a handle, and optional stubby arms.",
                 P, tswaps, pal)
    L = {"template": "object", "note": "Angles in degrees from the drawn rest pose.", "presets": {}, "clips": {
        "idle": {"duration": 2.0, "loop": True, "tracks": {"body": key((0, 0), (1, 1.5), (2, 0)), "lid": key((0, 0), (1, -2), (2, 0)), "arm_L": key((0, 0), (1, 4), (2, 0)), "arm_R": key((0, 0), (1, -4), (2, 0))}},
        "bounce": {"duration": 0.6, "tracks": {"body": key((0, 0), (0.15, -3), (0.45, 3), (0.6, 0)), "lid": key((0, 0), (0.3, -10), (0.6, 0))}, "offset": key((0, [0, 0]), (0.3, [0, -50]), (0.6, [0, 0]))},
        "wave": {"duration": 1.0, "tracks": {"arm_R": key((0, 0), (0.2, -80), (0.4, -60), (0.6, -80), (0.8, -60), (1.0, 0))}},
        "whistle": {"duration": 0.8, "tracks": {"lid": key((0, 0), (0.1, -14), (0.2, -4), (0.3, -14), (0.4, -4), (0.8, 0)), "spout": key((0, 0), (0.2, -6), (0.8, 0))}, "swaps": {"mouth": key((0, "small"), (0.7, "closed"))}},
        "talk": {"duration": 0.5, "loop": True, "tracks": {"body": key((0, 0), (0.25, -2), (0.5, 0)), "lid": key((0, 0), (0.25, -4), (0.5, 0))}}}}
    return T, L, puppet("Kettle", "object", [600, 600], 580, P, SW, pal, "a teapot with a face, drawn from shapes by make_critters.py")


if __name__ == "__main__":
    for make, pid in ((biscuit, "biscuit"), (pim, "pim"), (kettle, "kettle")):
        T, L, PZ = make(); tid = T["template"]
        (ROOT / "puppet" / "templates" / f"{tid}.json").write_text(json.dumps(T, indent=1) + "\n")
        (ROOT / "puppet" / "templates" / f"{tid}.js").write_text(f"window.TEMPLATES = window.TEMPLATES || {{}}; window.TEMPLATES.{tid} = {json.dumps(T)};\n")
        (ROOT / "puppet" / "clips" / f"{tid}.json").write_text(json.dumps(L, indent=1) + "\n")
        (ROOT / "puppet" / "clips" / f"{tid}.js").write_text(f"window.CLIPLIB = window.CLIPLIB || {{}}; window.CLIPLIB.{tid} = {json.dumps(L)};\n")
        (HERE / f"{pid}.puppet.json").write_text(json.dumps(PZ, separators=(",", ":")) + "\n")
        print("wrote", tid, pid)
