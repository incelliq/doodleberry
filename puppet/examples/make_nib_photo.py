"""Draw "Nib", an original doodle character, as a fake phone photo of a pen drawing on paper (uneven lighting, grain,
a few specks), to exercise ink-fidelity import end to end without anyone's real drawings.

    python puppet/examples/make_nib_photo.py      -> puppet/examples/nib_photo.png and nib.ink.json (the parts spec)
Then: python -m dbe puppet.from_ink '{"spec": "puppet/examples/nib.ink.json", "out": "puppet/examples/nib.puppet.json"}'
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
W, H = 520, 700
rng = random.Random(11)


def wobble(points, amp=1.6):
    return [(x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)) for x, y in points]


def pen(d, pts, w=4):
    pts = wobble(pts)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d.line([(x0, y0), (x1, y1)], fill=(28, 30, 36), width=w + rng.choice([0, 0, 1]))


def ellipse(cx, cy, rx, ry, n=60, start=0.0):
    return [(cx + rx * math.cos(start + 2 * math.pi * i / n), cy + ry * math.sin(start + 2 * math.pi * i / n)) for i in range(n + 1)]


def main():
    img = Image.new("RGB", (W, H), (236, 234, 226))
    d = ImageDraw.Draw(img)
    pen(d, ellipse(260, 430, 120, 150))                       # body: a tall egg
    pen(d, ellipse(260, 230, 92, 82))                         # head
    pen(d, ellipse(226, 222, 16, 20), 3); pen(d, ellipse(292, 222, 16, 20), 3)   # eyes (rings)
    d.ellipse([222, 222, 232, 234], fill=(28, 30, 36)); d.ellipse([288, 222, 298, 234], fill=(28, 30, 36))  # pupils
    pen(d, [(236, 268), (250, 276), (270, 276), (284, 268)], 3)   # smile
    pen(d, [(196, 160), (184, 128), (206, 146), (214, 116), (230, 150)], 3)   # a tuft of hair
    pen(d, [(150, 400), (120, 450), (98, 500)])                # arm (image left), small gap at the body
    pen(d, [(370, 400), (402, 446), (424, 492)])               # arm (image right)
    pen(d, [(226, 578), (222, 640)]); pen(d, [(296, 578), (300, 640)])   # legs
    pen(d, [(200, 646), (236, 642)]); pen(d, [(286, 642), (322, 646)])   # feet
    # paper: lighting gradient, grain and specks, like a phone photo
    px = img.load()
    for y in range(H):
        for x in range(W):
            g = 1.0 - 0.18 * (x / W) - 0.10 * (y / H)
            r, gg, b = px[x, y]
            n = rng.uniform(-5, 5)
            px[x, y] = (int(r * g + n), int(gg * g + n), int(b * g + n))
    for _ in range(40):
        x, y = rng.randrange(W), rng.randrange(H)
        d.point((x, y), fill=(90, 90, 90))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(HERE / "nib_photo.png")
    spec = {
        "photo": "nib_photo.png", "name": "Nib", "template": "doodle", "ink": "#1c1e24", "rest": "body",
        "parts": {
            "head": {"poly": [[150, 100], [370, 100], [370, 316], [150, 316]], "pivot": [260, 300], "parent": "body", "z": 20, "overlap": 3},
            "arm_L": {"poly": [[86, 390], [156, 390], [156, 512], [86, 512]], "pivot": [150, 402], "parent": "body", "z": 12},
            "arm_R": {"poly": [[364, 390], [436, 390], [436, 504], [364, 504]], "pivot": [370, 402], "parent": "body", "z": 12},
        },
        "swaps": {"eyes": {"anchor": "head", "z": 30, "open": {"poly": [[202, 196], [316, 196], [316, 248], [202, 248]]}, "blink": "squash"}},
        "anchors": {"bubble": [260, 140]},
        "meta": {"author": "doodleberry (generated example)", "license": "CC0-1.0"},
    }
    (HERE / "nib.ink.json").write_text(json.dumps(spec, indent=1))
    print("wrote nib_photo.png and nib.ink.json")


if __name__ == "__main__":
    main()
