"""Creator packages (WP-29): rig templates, loop packs and boil presets, packed by one project and installed into another.

A pack is a zip (`<id>-<version>.dbpack`) holding `pack.json` and its payload:

    {"format": "doodleberry.pack", "format_version": 1, "kind": "rig" | "loops" | "boil",
     "id", "name", "version", "author", "license", "description", "contact",
     "requires": {"template": "humanoid", "puppet_format": "0.9"},
     "files": [{"path": "payload/...", "sha256", "role": "puppet" | "clips" | "preset"}]}

- **rig**: a rigged character (a .puppet.json: parts, pivots, controls, poses, its own clips) for others to dress or
  use. Installed into cast/packs/<id>/ and registered in the cast library (cast/index.json, cast/provenance.jsonl)
  with its author, licence and the pack it came from, so its screen time is the author's in the usage report.
- **loops**: motion clips for a template (`{"template", "clips": {name: clip}}`, clips as in puppet/clips/). Installed
  into the project's clip library for that template (puppet/clips/<template>.json and .js, which every renderer and
  the bake read), each clip marked with its pack; puppet/clips/packs.json lists the installed packs with their
  authors. A clip name already in the library from elsewhere is refused (a pack may replace its own clips: an update).
- **boil**: named line-boil settings (`{"fps", "frames", "amount", "freq"}`), installed into presets/boil/<id>.json and
  applied to a film's shots by `boil.apply` (which records the preset, so its use is counted too).

Packing checks the author and licence, lints a rig, and hashes every file; installing checks the format version, the
hashes, that the template exists in the receiving project, and lints the rig there with that project's own loader.
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

FORMAT, FORMAT_VERSION = "doodleberry.pack", 1
KINDS = ("rig", "loops", "boil")
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,40}")
BOIL_KEYS = {"fps": (1, 30), "frames": (1, 24), "amount": (0, 20), "freq": (0.001, 0.2)}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def make(out_dir, kind, meta, payload):
    """payload: {name in payload/: bytes or JSON-able} -> path of the .dbpack"""
    if kind not in KINDS:
        raise ValueError(f"kind is one of {KINDS}")
    if not ID.fullmatch(meta.get("id", "")):
        raise ValueError("a pack id is lower-case letters, digits and hyphens")
    for k in ("name", "version", "author", "license"):
        if not meta.get(k):
            raise ValueError(f"a pack needs {k}")
    files, blobs = [], {}
    for name, v in payload.items():
        b = v if isinstance(v, bytes) else (json.dumps(v, indent=1, ensure_ascii=False) + "\n").encode()
        p = f"payload/{name}"; blobs[p] = b
        files.append({"path": p, "sha256": _sha(b), "role": {"rig": "puppet", "loops": "clips", "boil": "preset"}[kind] if name.endswith(".json") else "file"})
    pk = {"format": FORMAT, "format_version": FORMAT_VERSION, "kind": kind, **meta, "made": _now(), "files": files}
    out = Path(out_dir) / f"{meta['id']}-{meta['version']}.dbpack"; out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.json", json.dumps(pk, indent=1, ensure_ascii=False) + "\n")
        for p, b in blobs.items():
            z.writestr(p, b)
    return out, pk


def read(path):
    """-> (pack.json, {payload path: bytes}); refuses another format, a newer format version, or a changed file"""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        pk = json.loads(z.read("pack.json"))
        if pk.get("format") != FORMAT or not isinstance(pk.get("format_version"), int) or pk["format_version"] > FORMAT_VERSION:
            raise ValueError(f"not a pack this project can read ({pk.get('format')} v{pk.get('format_version')})")
        blobs = {}
        for f in pk["files"]:
            if f["path"] not in names or not f["path"].startswith("payload/") or ".." in f["path"]:
                raise ValueError(f"pack file {f['path']} is missing or outside payload/")
            b = z.read(f["path"])
            if _sha(b) != f["sha256"]:
                raise ValueError(f"{f['path']} does not match its sha256: the pack was changed after it was made")
            blobs[f["path"]] = b
    return pk, blobs


def lint_in(project, puppet_path):
    """lint a puppet with the receiving project's own loader and template"""
    p = json.loads((Path(project) / puppet_path).read_text())
    js = ("globalThis.window=globalThis; const fs=require('fs'); new Function(fs.readFileSync('puppet/loader/puppet.js','utf8'))();"
          f" const T=JSON.parse(fs.readFileSync('puppet/templates/{p['template']}.json','utf8')); const P=JSON.parse(fs.readFileSync({json.dumps(str(puppet_path))},'utf8'));"
          " console.log(JSON.stringify(Puppet.lint(P,T)))")
    r = subprocess.run(["node", "-e", js], cwd=project, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"lint failed in {project}: {r.stderr[-300:]}")
    return json.loads(r.stdout or "[]")


def _clip_js(template, lib):
    return f"window.CLIPLIB = window.CLIPLIB || {{}}; window.CLIPLIB.{template} = {json.dumps(lib, ensure_ascii=False)};\n"


def install(project, path):
    """install a pack into a project (a Doodleberry checkout) -> what was installed and where"""
    proj = Path(project).resolve(); pk, blobs = read(path); kind = pk["kind"]; tag = f"{pk['id']}@{pk['version']}"
    tpl = (pk.get("requires") or {}).get("template")
    if tpl and not (proj / "puppet" / "templates" / f"{tpl}.json").exists():
        raise ValueError(f"{proj.name} has no {tpl} template (puppet/templates/{tpl}.json)")
    reg = proj / "puppet" / "clips" / "packs.json"
    packs = json.loads(reg.read_text()) if reg.exists() else {"note": "WP-29: creator packs installed in this project (pack.install)", "packs": {}}
    out = {"pack": tag, "kind": kind}
    if kind == "rig":
        main = next(p for p, f in ((f["path"], f) for f in pk["files"]) if f["role"] == "puppet")
        dest = proj / "cast" / "packs" / pk["id"]; dest.mkdir(parents=True, exist_ok=True)
        for p, b in blobs.items():
            (dest / Path(p).name).write_bytes(b)
        rel = (dest / Path(main).name).relative_to(proj)
        issues = lint_in(proj, rel); missing = [i for i in issues if i.get("level") == "missing"]
        if missing:
            raise ValueError(f"the rig does not fit {proj.name}'s {tpl} template: {missing[:3]}")
        pup = json.loads((proj / rel).read_text())
        idx_p = proj / "cast" / "index.json"; idx = json.loads(idx_p.read_text()) if idx_p.exists() else {"puppets": []}
        entry = {"id": pk["id"], "name": pk["name"], "path": str(rel), "template": pup.get("template"), "author": pk["author"], "license": pk["license"],
                 "provenance": f"installed from creator pack {tag} ({Path(path).name})", "rights": {"type": "owner" if pk["license"].startswith("LicenseRef") else "open", "owner": pk["author"]},
                 "views": sorted((pup.get("views") or {}).keys()), "sha256": _sha((proj / rel).read_bytes())[:16], "pack": tag,
                 **({"royalty": pk["royalty"]} if pk.get("royalty") else {}), **({"contact": pk["contact"]} if pk.get("contact") else {})}
        idx["puppets"] = [e for e in idx["puppets"] if e["id"] != pk["id"]] + [entry]; idx_p.write_text(json.dumps(idx, indent=1))
        with open(proj / "cast" / "provenance.jsonl", "a") as f:
            f.write(json.dumps({"at": _now(), "action": "install", **entry}) + "\n")
        out.update({"puppet": str(rel), "registered": entry["id"], "lint_warnings": len(issues)})
    elif kind == "loops":
        src = json.loads(next(b for p, b in blobs.items() if p.endswith(".json")))
        tpl = src["template"]; lp = proj / "puppet" / "clips" / f"{tpl}.json"
        lib = json.loads(lp.read_text())
        clash = [k for k in src["clips"] if k in lib["clips"] and lib["clips"][k].get("pack", "").split("@")[0] != pk["id"]]
        if clash:
            raise ValueError(f"{tpl} already has clips named {clash}: rename them in the pack")
        for k, c in src["clips"].items():
            lib["clips"][k] = {**c, "pack": tag}
        lp.write_text(json.dumps(lib, indent=1, ensure_ascii=False) + "\n"); (lp.with_suffix(".js")).write_text(_clip_js(tpl, lib))
        out.update({"template": tpl, "clips": sorted(src["clips"]), "library": str(lp.relative_to(proj))})
    else:
        pr = json.loads(next(b for p, b in blobs.items() if p.endswith(".json")))
        bad = [k for k, (lo, hi) in BOIL_KEYS.items() if k in pr and not lo <= pr[k] <= hi]
        if bad:
            raise ValueError(f"boil settings out of range: {bad}")
        d = proj / "presets" / "boil"; d.mkdir(parents=True, exist_ok=True)
        (d / f"{pk['id']}.json").write_text(json.dumps({**{k: pr[k] for k in BOIL_KEYS if k in pr}, "pack": tag, "author": pk["author"], "license": pk["license"]}, indent=1) + "\n")
        out.update({"preset": f"presets/boil/{pk['id']}.json"})
    packs["packs"][pk["id"]] = {"version": pk["version"], "kind": kind, "name": pk["name"], "author": pk["author"], "license": pk["license"],
                                "installed": _now(), **({"royalty": pk["royalty"]} if pk.get("royalty") else {}), **{k: out[k] for k in ("template", "clips") if k in out}}
    reg.parent.mkdir(parents=True, exist_ok=True); reg.write_text(json.dumps(packs, indent=1, ensure_ascii=False) + "\n")
    return out
