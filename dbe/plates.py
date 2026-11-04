"""Anatomy plates (WP-16): Servier Medical Art images (CC BY 4.0), listed in assets/plates/plates.json, downloaded on
demand into assets/external/plates/ (not committed) and checked against their recorded sha256. The player shows one
as an overlay ({"type": "plate", "plate": "heart", ...}); film.credits credits every plate a film shows."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "assets" / "plates" / "plates.json"
DIR = ROOT / "assets" / "external" / "plates"


def registry():
    return json.loads(REG.read_text())


def fetch(ids=None):
    reg = registry()["plates"]; out = {}
    DIR.mkdir(parents=True, exist_ok=True)
    for pid in ids or list(reg):
        p = reg[pid]; f = DIR / p["file"]
        if not f.exists():
            req = urllib.request.Request(p["url"], headers={"User-Agent": "doodleberry-plates/1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                f.write_bytes(r.read())
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != p["sha256"]:
            f.unlink()
            raise ValueError(f"plate {pid}: the download's sha256 {h[:12]} is not the recorded {p['sha256'][:12]} (the source changed; check it and update plates.json)")
        out[pid] = str(f.relative_to(ROOT))
    return out


def used(shots):
    """the plate ids a film's shots show"""
    return sorted({o.get("plate") for sh in shots.get("shots", []) for o in (sh.get("overlays") or []) + (sh.get("underlays") or []) if o.get("type") == "plate"} - {None})
