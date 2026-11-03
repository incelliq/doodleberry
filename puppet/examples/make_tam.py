"""Tam: a recoloured Pip (front and side views), the second walker in films/handshake-demo (WP-11).
    python puppet/examples/make_tam.py   -> puppet/examples/tam.puppet.json"""
import json
from pathlib import Path

here = Path(__file__).parent
p = json.loads((here / "pip.puppet.json").read_text())
p["name"] = "Tam"
p["palette"] = {**p["palette"], "skin": "#9a6440", "hair": "#1c1410", "cloth1": "#3aa58c", "cloth2": "#5a3e74", "shoe": "#f2d36b"}
p["meta"] = {**p.get("meta", {}), "author": "doodleberry (generated example)", "license": "CC0-1.0", "created": "2026-11-03",
             "note": "recoloured from Pip by make_tam.py"}
(here / "tam.puppet.json").write_text(json.dumps(p, separators=(",", ":")))
print("wrote", here / "tam.puppet.json")
