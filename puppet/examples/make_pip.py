"""Build the example puppet "Pip" (an original character) from simple shapes, on the humanoid template.

    python puppet/examples/make_pip.py      ->  puppet/examples/pip.puppet.json (+ pip.puppet.js for file:// pages)

A hand-drawn puppet from the canvas has exactly the same structure; this one exists to test the loader and engine.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
T = json.loads((HERE.parent / "templates" / "humanoid.json").read_text())


def f(n):
    return f"{n:.1f}"


def ellipse(cx, cy, rx, ry):
    return f"M{f(cx - rx)} {f(cy)} A{f(rx)} {f(ry)} 0 1 0 {f(cx + rx)} {f(cy)} A{f(rx)} {f(ry)} 0 1 0 {f(cx - rx)} {f(cy)} Z"


def capsule(a, b, r0, r1):
    """tapered capsule from a (radius r0) to b (radius r1)"""
    (ax, ay), (bx, by) = a, b
    ang = math.atan2(by - ay, bx - ax)
    nx, ny = -math.sin(ang), math.cos(ang)
    p1 = (ax + nx * r0, ay + ny * r0); p2 = (bx + nx * r1, by + ny * r1)
    p3 = (bx - nx * r1, by - ny * r1); p4 = (ax - nx * r0, ay - ny * r0)
    return (f"M{f(p1[0])} {f(p1[1])} L{f(p2[0])} {f(p2[1])} A{f(r1)} {f(r1)} 0 0 0 {f(p3[0])} {f(p3[1])} "
            f"L{f(p4[0])} {f(p4[1])} A{f(r0)} {f(r0)} 0 0 0 {f(p1[0])} {f(p1[1])} Z")


def st(d, fill, stroke="ink", width=4):
    return {"d": d, "fill": fill, "stroke": stroke, "width": width}


def line(d, width=4):
    return {"d": d, "fill": "none", "stroke": "ink", "width": width}


P = {p["id"]: p["pivot"] for p in T["parts"]}
parts = {p["id"]: {"parent": p["parent"], "pivot": p["pivot"], "z": p["z"], "strokes": []} for p in T["parts"]}
add = lambda pid, *s: parts[pid]["strokes"].extend(s)

# body: rounded shirt, shorts, limbs; overlaps past each joint so bends never gap
add("hip", st("M244 548 L356 548 L362 612 C330 620 270 620 238 612 Z", "cloth2"))
add("torso", st("M232 352 C236 336 364 336 368 352 L362 470 C360 520 352 556 350 566 L250 566 C248 556 240 520 238 470 Z", "cloth1"),
    line("M282 338 L300 362 L318 338", 3.5), line("M250 520 L350 520", 2.5))
add("neck", st(capsule((300, 318), (300, 352), 17, 18), "skin"))
add("head", st(ellipse(222, 272, 13, 18), "skin"), st(ellipse(378, 272, 13, 18), "skin"), st(ellipse(300, 262, 80, 90), "skin"),
    {"d": ellipse(262, 300, 14, 8), "fill": "#ff8f8a", "opacity": 0.35}, {"d": ellipse(338, 300, 14, 8), "fill": "#ff8f8a", "opacity": 0.35},
    line("M300 270 Q310 292 298 296", 3.5))
add("hair_front", st("M218 250 C214 186 258 160 304 162 C352 164 388 196 382 252 C370 220 350 204 322 200 C300 214 262 222 236 214 C226 224 220 238 218 250 Z", "hair"))
add("hair_back", st("M226 230 C220 300 232 330 250 340 L350 340 C368 330 380 300 374 230 Z", "hair"))
for side, (u, fo, h) in {"L": ("upperarm_L", "forearm_L", "hand_L"), "R": ("upperarm_R", "forearm_R", "hand_R")}.items():
    sx = -1 if side == "L" else 1
    add(u, st(capsule(P[u], P[fo], 27, 24), "cloth1"))
    add(fo, st(capsule((P[fo][0], P[fo][1] - 6), P[h], 20, 17), "skin"))
    hx, hy = P[h]
    add(h, st(ellipse(hx + sx * 2, hy + 18, 21, 24), "skin"), st(capsule((hx - sx * 14, hy + 6), (hx - sx * 26, hy + 22), 7, 6), "skin"))
for side in "LR":
    t_, s_, ft = f"thigh_{side}", f"shin_{side}", f"foot_{side}"
    add(t_, st(capsule((P[t_][0], P[t_][1] - 14), P[s_], 33, 27), "cloth2"))
    add(s_, st(capsule((P[s_][0], P[s_][1] - 10), P[ft], 22, 19), "skin"))
    fx, fy = P[ft]
    add(ft, st(f"M{fx - 26} {fy - 14} C{fx - 30} {fy + 14} {fx - 18} {fy + 34} {fx} {fy + 34} L{fx + 50} {fy + 34} C{fx + 62} {fy + 32} {fx + 60} {fy + 12} {fx + 40} {fy + 4} L{fx + 16} {fy - 16} Z", "shoe"))

# face swaps
E = [(272, 262), (328, 262)]
eyes = {
    "open": [st(ellipse(x, y, 13, 16), "eye", width=3.5) for x, y in E],
    "half": [st(f"M{x - 13} {y} A13 9 0 0 0 {x + 13} {y} Z", "eye", width=3.5) for x, y in E] + [line(f"M{x - 14} {y} L{x + 14} {y}", 3.5) for x, y in E],
    "closed": [line(f"M{x - 13} {y + 2} Q{x} {y + 10} {x + 13} {y + 2}", 4) for x, y in E],
}
pupils = {"default": [{"d": ellipse(x, y + 1, 6, 7), "fill": "ink"} for x, y in E] + [{"d": ellipse(x + 2.5, y - 2.5, 2, 2), "fill": "#ffffff"} for x, y in E]}
brow = lambda dy_in, dy_out: [line(f"M{x - 14} {y - 26 + (dy_out if x < 300 else dy_in)} Q{x} {y - 34} {x + 14} {y - 26 + (dy_in if x < 300 else dy_out)}", 5) for x, y in E]
brows = {"neutral": brow(0, 0), "raised": brow(-8, -8), "worried": brow(-8, 4), "angry": brow(8, -4)}
M = (300, 320)
mouth = {
    "closed": [line(f"M{M[0] - 14} {M[1]} Q{M[0]} {M[1] + 4} {M[0] + 14} {M[1]}")],
    "small": [st(ellipse(M[0], M[1] + 2, 9, 5), "#6a2420", width=3.5)],
    "mid": [st(ellipse(M[0], M[1] + 4, 12, 9), "#6a2420", width=3.5), {"d": ellipse(M[0], M[1] + 9, 7, 3), "fill": "#e27a76"}],
    "wide": [st(f"M{M[0] - 16} {M[1] - 2} Q{M[0]} {M[1] - 6} {M[0] + 16} {M[1] - 2} Q{M[0] + 13} {M[1] + 22} {M[0]} {M[1] + 22} Q{M[0] - 13} {M[1] + 22} {M[0] - 16} {M[1] - 2} Z", "#6a2420", width=3.5),
             {"d": f"M{M[0] - 11} {M[1] - 1} L{M[0] + 11} {M[1] - 1} L{M[0] + 9} {M[1] + 4} L{M[0] - 9} {M[1] + 4} Z", "fill": "#ffffff"}, {"d": ellipse(M[0], M[1] + 15, 8, 4), "fill": "#e27a76"}],
    "O": [st(ellipse(M[0], M[1] + 4, 8, 11), "#6a2420", width=3.5)],
    "FV": [st(ellipse(M[0], M[1] + 2, 13, 5), "#6a2420", width=3.5), {"d": f"M{M[0] - 10} {M[1] - 1} L{M[0] + 10} {M[1] - 1} L{M[0] + 8} {M[1] + 3} L{M[0] - 8} {M[1] + 3} Z", "fill": "#ffffff"}],
    "smile": [line(f"M{M[0] - 18} {M[1] - 4} Q{M[0]} {M[1] + 14} {M[0] + 18} {M[1] - 4}", 4.5)],
    "frown": [line(f"M{M[0] - 15} {M[1] + 6} Q{M[0]} {M[1] - 6} {M[0] + 15} {M[1] + 6}", 4.5)],
}
hx, hy = P["hand_R"]
hand_point = {"point": [st(ellipse(hx + 2, hy + 16, 19, 20), "skin"), st(capsule((hx + 10, hy + 6), (hx + 46, hy - 8), 8, 7), "skin")],
              "fist": [st(ellipse(hx + 2, hy + 16, 19, 19), "skin"), line(f"M{hx - 8} {hy + 10} L{hx + 12} {hy + 10} M{hx - 8} {hy + 20} L{hx + 12} {hy + 20}", 2.5)],
              "hold": []}
swaps = {
    "eyes": {"anchor": "head", "z": 42, "shapes": eyes},
    "pupils": {"anchor": "head", "z": 43, "shapes": pupils, "movable": 8},
    "brows": {"anchor": "head", "z": 44, "shapes": brows},
    "mouth": {"anchor": "head", "z": 45, "shapes": mouth, "talk": ["closed", "small", "mid", "wide"]},
    "hand_R_pose": {"anchor": "forearm_R", "z": 33, "shapes": hand_point, "replaces": "hand_R"},
}
puppet = {"format": "doodleberry.puppet", "version": "0.1", "name": "Pip", "template": "humanoid", "artboard": T["artboard"], "ground": T["ground"],
          "palette": {"skin": "#e8b48e", "hair": "#4a3020", "cloth1": "#f2a33a", "cloth2": "#3a5a8a", "cloth3": "#ffffff", "shoe": "#e9e9ee", "eye": "#ffffff", "ink": "#24160e"},
          "parts": parts, "swaps": swaps, "meta": {"author": "doodleberry (generated example)", "license": "CC0-1.0", "created": "2026-11-01"}}
(HERE / "pip.puppet.json").write_text(json.dumps(puppet, indent=1))
(HERE / "pip.puppet.js").write_text("window.PIP = " + json.dumps(puppet) + ";\n")
print("wrote pip.puppet.json:", sum(len(p["strokes"]) for p in parts.values()), "part strokes,", sum(len(v) for s in swaps.values() for v in s["shapes"].values()), "swap strokes")
