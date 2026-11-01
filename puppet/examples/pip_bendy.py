"""Pip with bendy joints (puppet v0.4 `bend`): elbows and knees curve like rubber hose instead of hinging.

    python puppet/examples/pip_bendy.py      -> puppet/examples/pip_bendy.puppet.json (+ .js)
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
P = json.loads((HERE / "pip.puppet.json").read_text())
P["name"] = "Pip (bendy)"
for pid, w in {"forearm_L": 90, "forearm_R": 90, "shin_L": 100, "shin_R": 100}.items():
    P["parts"][pid]["bend"] = {"width": w}
P["version"] = "0.4"
(HERE / "pip_bendy.puppet.json").write_text(json.dumps(P))
(HERE / "pip_bendy.puppet.js").write_text("window.PIP_BENDY = " + json.dumps(P) + ";\n")
print("wrote pip_bendy.puppet.json")
