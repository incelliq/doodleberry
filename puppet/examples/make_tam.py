"""Tam: a recoloured Pip (front and side views), the second walker in films/handshake-demo, with the v0.9 features
used by films/stretch-demo (WP-11).
    python puppet/examples/make_tam.py   -> puppet/examples/tam.puppet.json"""
import json
from pathlib import Path

here = Path(__file__).parent
p = json.loads((here / "pip.puppet.json").read_text())
p["name"] = "Tam"
p["palette"] = {**p["palette"], "skin": "#9a6440", "hair": "#1c1410", "cloth1": "#3aa58c", "cloth2": "#5a3e74", "shoe": "#f2d36b"}
p["meta"] = {**p.get("meta", {}), "author": "doodleberry (generated example)", "license": "CC0-1.0", "created": "2026-11-03",
             "note": "recoloured from Pip by make_tam.py"}
# v0.9 features (WP-11 part 2): a ring badge with an even-odd fill, a held hand chosen by the forearm's angle, whole-face
# lip-sync poses and free part attributes
p["version"] = "0.9"
p["parts"]["torso"]["strokes"].append({"d": "M322 412 m-20 0 a20 20 0 1 0 40 0 a20 20 0 1 0 -40 0 Z M322 412 m-9 0 a9 9 0 1 0 18 0 a9 9 0 1 0 -18 0 Z",
                                       "fill": "shoe", "stroke": "ink", "width": 3, "rule": "evenodd"})
p["parts"]["torso"]["attrs"] = {"material": "cotton", "badge": "ring"}
p["parts"]["hand_R"]["attrs"] = {"grip": "hold"}
p["swaps"]["hand_R_pose"]["by_angle"] = {"part": "forearm_R", "world": True, "shapes": [[-180, -120, "hold"], [120, 180.01, "hold"]]}
p["lipsync"] = {"O": {"angles": {"head": -1.5}, "shifts": {"@brows": [0, -4]}, "scales": {"head": [0.99, 1.025]}},
                "wide": {"shifts": {"@brows": [0, -2]}, "scales": {"head": [1.02, 0.99]}},
                "mid": {"angles": {"head": -0.8}, "shifts": {"@brows": [0, -1.5]}}}
(here / "tam.puppet.json").write_text(json.dumps(p, separators=(",", ":")))
print("wrote", here / "tam.puppet.json")
