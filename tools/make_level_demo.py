"""Drawings for the drawn-level demo (WP-35): a campfire and a walk cycle, each 12 drawings, drawn with MyPaint brush
strokes (libmypaint, WP-34) and flat colour, then made into drawn levels on twos.

These drawings are made by code as stand-ins for an animator's: the Studio drawing page with onion skins is the next
part of WP-35. Deterministic: run it again and the same drawings come out.

    python tools/make_level_demo.py
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dbe import oss  # noqa: E402

OUT = ROOT / "out" / "leveldemo"
INK = "#24160e"


def over(base, top):
    a = Image.fromarray(base, "RGBA"); a.alpha_composite(Image.fromarray(top, "RGBA")); return np.asarray(a)


def fire(i, n=12, size=(360, 420)):
    """one drawing of a looping campfire: three flame tongues swaying, a brighter core, logs below"""
    W, H = size; ph = 2 * math.pi * i / n
    im = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    tongues = []
    for k, (cx, h, w, sp) in enumerate(((180, 300, 120, 1.0), (130, 220, 80, 1.3), (235, 240, 85, 0.8))):
        sway = 22 * math.sin(ph * sp + k * 2.1); top = 330 - h - 18 * math.sin(ph * 2 + k)
        pts = [(cx - w / 2, 330), (cx - w / 3 + sway * 0.3, 330 - h * 0.45), (cx + sway, top), (cx + w / 3 + sway * 0.5, 330 - h * 0.5), (cx + w / 2, 330)]
        tongues.append(pts)
        d.polygon(pts, fill=(232, 96, 40, 235))
    for k, (cx, h, w) in enumerate(((180, 170, 60), (150, 110, 36), (210, 120, 38))):
        sway = 14 * math.sin(ph * 1.2 + k); top = 330 - h - 10 * math.sin(ph * 2.5 + k * 1.7)
        d.polygon([(cx - w / 2, 330), (cx + sway, top), (cx + w / 2, 330)], fill=(255, 200, 70, 245))
    d.rounded_rectangle([70, 322, 290, 352], 12, fill=(124, 82, 50, 255)); d.rounded_rectangle([95, 345, 300, 372], 12, fill=(104, 66, 40, 255))
    a = np.asarray(im)
    strokes = [[[x, y, 0.55, 0.012] for x, y in _densify(pts)] for pts in tongues]
    strokes += [[[70, 336, 0.5], [290, 336, 0.6]], [[95, 360, 0.5], [300, 360, 0.6]]]
    ink = oss.paint("deevad/ballpen", strokes, size, INK, 1.4)
    return over(a, ink)


def _densify(pts, step=6):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    return out + [pts[-1]]


def walk(i, n=12, size=(320, 560)):
    """one drawing of a walk cycle in place: contact, down, passing, up for each leg; arms opposite; a bob"""
    W, H = size; ph = 2 * math.pi * i / n
    bob = -10 * math.cos(2 * ph)                       # lowest at the contacts, highest at the passing positions
    hip = (160, 330 + bob); sh = (160, 205 + bob); head = (160, 140 + bob)
    strokes, fills = [], []

    def leg(phase):
        th = 18 * math.sin(phase)                       # thigh swing (degrees from vertical; stride matched to the travel in level-demo)
        kn = 6 + 34 * max(0.0, math.sin(phase + 1.9))   # knee bends on the passing side
        t = math.radians(th); k = math.radians(th - kn)
        knee = (hip[0] + 95 * math.sin(t), hip[1] + 95 * math.cos(t))
        foot = (knee[0] + 95 * math.sin(k), knee[1] + 95 * math.cos(k))
        toe = (foot[0] + 26, foot[1] + 2)
        return [hip, knee, foot, toe]

    def arm(phase):
        a = math.radians(-22 * math.sin(phase)); e = math.radians(-22 * math.sin(phase) - 18)
        el = (sh[0] + 70 * math.sin(a), sh[1] + 70 * math.cos(a)); hand = (el[0] + 62 * math.sin(e), el[1] + 62 * math.cos(e))
        return [sh, el, hand]
    for lg in (leg(ph + math.pi), arm(ph)):             # far side first, slightly lighter
        strokes.append(([[x, y, 0.45, 0.012] for x, y in _densify(lg)], "#6b5a4e"))
    im = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([110, 200 + bob, 210, 345 + bob], fill=(108, 175, 216, 255))          # body
    d.ellipse([head[0] - 52, head[1] - 52, head[0] + 52, head[1] + 52], fill=(246, 222, 196, 255))
    body = [(160 + 50 * math.cos(u), 272 + bob + 72 * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 40)]
    hd = [(head[0] + 52 * math.cos(u), head[1] + 52 * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 44)]
    strokes.append(([[x, y, 0.6, 0.012] for x, y in body], INK)); strokes.append(([[x, y, 0.6, 0.012] for x, y in hd], INK))
    for lg in (leg(ph), arm(ph + math.pi)):             # near side
        strokes.append(([[x, y, 0.7, 0.012] for x, y in _densify(lg)], INK))
    for ex in (-18, 18):
        d.ellipse([head[0] + ex - 6, head[1] - 10, head[0] + ex + 6, head[1] + 4], fill=(36, 22, 14, 255))
    a = np.asarray(im)
    for st, col in strokes:
        a = over(a, oss.paint("deevad/ballpen", [st], size, col, 1.6))
    return a


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, fn in (("campfire", fire), ("doodle-walk", walk)):
        paths = []
        for i in range(12):
            p = OUT / f"{name}_{i + 1:02d}.png"; Image.fromarray(fn(i), "RGBA").save(p); paths.append(str(p.relative_to(ROOT)))
        r = subprocess.run([sys.executable, "-m", "dbe", "level.make", json.dumps({"name": name, "frames": paths, "timing": "twos", "fps": 24,
                            "author": "tools/make_level_demo.py (stand-in drawings)"})], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stderr[-800:])
        made[name] = json.loads(r.stdout)
    print(json.dumps({k: {x: v[x] for x in ("puppet", "drawings", "frames", "seconds")} for k, v in made.items()}, indent=1))


if __name__ == "__main__":
    main()
