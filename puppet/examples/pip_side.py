"""Add a side (profile) view to the example puppet Pip (puppet format v0.2 `views`).

    python puppet/examples/make_pip.py && python puppet/examples/pip_side.py

The side view narrows the torso, swings both arms and legs toward the body's centre line, and swaps in a profile
head: one eye, one brow, a nose, and mouths moved to the front of the face.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))
from dbe.geom import parse_path  # noqa: E402

P = json.loads((HERE / "pip.puppet.json").read_text())


def path_of(subs, dx=0, dy=0, sx=1, cx=0):
    out = ""
    X = lambda x: cx + (x - cx) * sx + dx
    for segs, closed in subs:
        out += f"M{X(segs[0][0][0]):.1f} {segs[0][0][1] + dy:.1f}"
        for (p0, c1, c2, p1) in segs:
            out += f" C{X(c1[0]):.1f} {c1[1] + dy:.1f} {X(c2[0]):.1f} {c2[1] + dy:.1f} {X(p1[0]):.1f} {p1[1] + dy:.1f}"
        out += " Z" if closed else ""
    return out


def moved(strokes, dx=0, dy=0, sx=1, cx=0):
    return [{**st, "d": path_of(parse_path(st["d"]), dx, dy, sx, cx)} for st in strokes]


def ellipse(cx, cy, rx, ry):
    return f"M{cx - rx} {cy} A{rx} {ry} 0 1 0 {cx + rx} {cy} A{rx} {ry} 0 1 0 {cx - rx} {cy} Z"


st = lambda d, fill, w=4: {"d": d, "fill": fill, "stroke": "ink", "width": w}
line = lambda d, w=4: {"d": d, "fill": "none", "stroke": "ink", "width": w}
parts = {}
shift = {"upperarm_L": 64, "forearm_L": 64, "hand_L": 64, "upperarm_R": -64, "forearm_R": -64, "hand_R": -64,
         "thigh_L": 18, "shin_L": 18, "foot_L": 18, "thigh_R": -18, "shin_R": -18, "foot_R": -18}
for pid, dx in shift.items():
    part = P["parts"][pid]
    parts[pid] = {"pivot": [part["pivot"][0] + dx, part["pivot"][1]], "strokes": moved(part["strokes"], dx)}
parts["torso"] = {"strokes": moved(P["parts"]["torso"]["strokes"], sx=0.72, cx=300)}
parts["hip"] = {"strokes": moved(P["parts"]["hip"]["strokes"], sx=0.8, cx=300)}
# profile head: skull, nose, one ear at the back, a cheek
parts["head"] = {"strokes": [st(ellipse(282, 272, 13, 18), "skin"),
                             st("M226 262 C226 200 268 172 306 172 C350 172 378 206 380 248 C392 262 396 276 384 286 C380 320 352 352 304 352 C258 352 226 318 226 262 Z", "skin"),
                             {"d": ellipse(344, 300, 13, 8), "fill": "blush", "opacity": 0.35}]}
parts["hair_front"] = {"strokes": [st("M222 252 C214 190 254 164 300 164 C344 166 374 190 376 226 C352 212 326 206 300 208 C276 214 250 226 240 248 C232 252 226 254 222 252 Z", "hair")]}
parts["hair_back"] = {"strokes": [st("M226 230 C216 290 226 330 248 342 L300 342 C292 300 270 262 270 230 Z", "hair")]}
E = (344, 262)
swaps = {
    "eyes": {"shapes": {"open": [st(ellipse(E[0], E[1], 11, 15), "eye", 3.5)],
                        "half": [st(f"M{E[0] - 11} {E[1]} A11 8 0 0 0 {E[0] + 11} {E[1]} Z", "eye", 3.5), line(f"M{E[0] - 12} {E[1]} L{E[0] + 12} {E[1]}", 3.5)],
                        "closed": [line(f"M{E[0] - 11} {E[1] + 2} Q{E[0]} {E[1] + 10} {E[0] + 11} {E[1] + 2}", 4)]}},
    "pupils": {"shapes": {"default": [{"d": ellipse(E[0] + 4, E[1] + 1, 5.5, 6.5), "fill": "ink"}, {"d": ellipse(E[0] + 6, E[1] - 2, 1.8, 1.8), "fill": "#ffffff"}]}, "movable": 4},
    "brows": {"shapes": {k: [line(f"M{E[0] - 12} {E[1] - 24 + a} Q{E[0]} {E[1] - 32} {E[0] + 12} {E[1] - 24 + b}", 5)]
                         for k, (a, b) in {"neutral": (0, 0), "raised": (-8, -8), "worried": (4, -8), "angry": (-4, 8)}.items()}},
    "mouth": {"shapes": {k: moved(v, dx=52, sx=0.6, cx=300) for k, v in P["swaps"]["mouth"]["shapes"].items()}},
}
P["views"] = {"side": {"parts": parts, "swaps": swaps}}
P["version"] = "0.2"
(HERE / "pip.puppet.json").write_text(json.dumps(P, indent=1))
(HERE / "pip.puppet.js").write_text("window.PIP = " + json.dumps(P) + ";\n")
print("added side view:", len(parts), "parts,", len(swaps), "swap sets")
