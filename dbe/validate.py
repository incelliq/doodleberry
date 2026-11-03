"""Validation of a film's data before anything renders: JSON Schemas (dbe/schemas) plus semantic checks the schemas
can't express (line references point at real lines, puppets and clips exist, shots are contiguous, ids are unique)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LINE = re.compile(r"^\s*([\w-]+)\.(start|end)")


def _schema(kind):
    import jsonschema
    return jsonschema.Draft202012Validator(json.loads((ROOT / "dbe" / "schemas" / f"{kind}.schema.json").read_text()))


def schema_errors(kind, data):
    return [f"{kind}.json {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:160]}" for e in _schema(kind).iter_errors(data)]


def _clip_names():
    names = {}
    for f in (ROOT / "puppet" / "clips").glob("*.json"):
        lib = json.loads(f.read_text())
        names[lib.get("template", f.stem)] = set(lib.get("clips", {})) | {"__presets__:" + k for k in lib.get("presets", {})}
    return names


def _refs(obj, out):
    if isinstance(obj, str):
        m = _LINE.match(obj)
        if m:
            out.add(m.group(1))
    elif isinstance(obj, dict):
        for v in obj.values():
            _refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _refs(v, out)


def film(d):
    """-> {"errors": [...], "warnings": [...]} for films/<name>"""
    d = Path(d)
    errs, warns = [], []
    script = json.loads((d / "script.json").read_text()) if (d / "script.json").exists() else None
    shots = json.loads((d / "shots.json").read_text()) if (d / "shots.json").exists() else None
    if script is not None:
        errs += schema_errors("script", script)
        ids = [l.get("id") for l in script.get("lines", [])]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            errs.append(f"script.json: duplicate line ids {sorted(dup)}")
        spk = set(script.get("speakers") or {})
        for l in script.get("lines", []):
            if spk and l.get("speaker") and l["speaker"] not in spk:
                errs.append(f"script.json line {l.get('id')}: speaker {l['speaker']!r} is not in speakers")
    if shots is None:
        return {"errors": errs, "warnings": warns}
    errs += schema_errors("shots", shots)
    if errs:
        return {"errors": errs, "warnings": warns}
    line_ids = {l["id"] for l in (script or {}).get("lines", [])}
    refs = set(); _refs(shots, refs)
    for r in sorted(refs - line_ids):
        errs.append(f"shots.json refers to line {r!r}, which is not in script.json")
    ids = [s["id"] for s in shots["shots"]]
    if len(set(ids)) != len(ids):
        errs.append(f"shots.json: duplicate shot ids {sorted({i for i in ids if ids.count(i) > 1})}")
    clips = _clip_names()
    for s in shots["shots"]:
        for c in s.get("cast", []):
            pp = ROOT / c["puppet"]
            if not pp.exists():
                errs.append(f"shot {s['id']}: puppet {c['puppet']} not found"); continue
            pz = json.loads(pp.read_text()); tpl = pz.get("template", "humanoid")
            have = clips.get(tpl, clips.get("humanoid", set())) | set(pz.get("clips") or {})   # v0.7: the character's own clips
            for cl in (c.get("timeline") or {}).get("clips", []):
                if cl["clip"] not in have:
                    errs.append(f"shot {s['id']}: clip {cl['clip']!r} is neither in the {tpl} clip library nor one of {c['puppet']}'s own clips")
            for _, pose in (c.get("timeline") or {}).get("poses", []):
                if "__presets__:" + str(pose) not in have and pose not in (json.loads(pp.read_text()).get("poses") or {}):
                    warns.append(f"shot {s['id']}: pose {pose!r} is neither a {tpl} preset nor one of the puppet's poses")
    score = json.loads((d / "score.json").read_text()) if (d / "score.json").exists() else None
    palette = {"F", "Dm", "Bb", "C", "Gm", "Am"}   # engine/audio.py CHORDS: the music engine's F major palette
    for sec in (score or {}).get("sections", []):
        bad = sorted({c for c in sec.get("chords", []) + ([sec["end_chord"]] if sec.get("end_chord") else []) if c not in palette})
        if bad:
            errs.append(f"score.json: chords {bad} are not in the palette ({', '.join(sorted(palette))})")
    nums = [(s["id"], s["start"], s["end"]) for s in shots["shots"] if isinstance(s["start"], (int, float)) and isinstance(s["end"], (int, float))]
    for a, b in zip(nums, nums[1:]):
        if abs(a[2] - b[1]) > 1e-6:
            warns.append(f"shots {a[0]} and {b[0]} are not contiguous ({a[2]} vs {b[1]}): run film.retime or fix the times")
    for sid, st, en in nums:
        if en <= st:
            errs.append(f"shot {sid}: end {en} is not after start {st}")
    return {"errors": errs, "warnings": warns}
