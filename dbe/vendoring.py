"""Licence ledger and vendored code (WP-33).

Doodleberry is in-house R&D, so any open-source code may come inside, GPL and AGPL included. Vendored code lives in
`vendor/<name>/` (or next to the page that loads it) with an `UPSTREAM.json`: repository, version, archive and its
sha256, licence and licence class, licence files, what was taken, local patches (kept as small commits so upstream
fixes can be pulled), how to build it and the binary it makes. Builds go to `out/vendor-build/<name>/` (git-ignored)
and run only when someone calls `vendor.build`: building runs the upstream's own scripts.

Licence classes (the ledger records one for every component; none is refused):
    public-domain, permissive, attribution (CC BY), weak-copyleft (LGPL, MPL), copyleft (GPL), network-copyleft (AGPL),
    share-alike (CC BY-SA), source-available, non-commercial, research-only, proprietary (the owner's own work)
What matters at posting: non-commercial, research-only, share-alike and source-available inputs that shaped a public
film are flagged for the owner (`film.provenance`).
"""
import json
import os
import re
import subprocess
from pathlib import Path

from . import ROOT

FLAG_AT_POSTING = {"non-commercial", "research-only", "share-alike", "source-available"}
CLASSES = ["public-domain", "permissive", "attribution", "weak-copyleft", "copyleft", "network-copyleft", "share-alike",
           "source-available", "non-commercial", "research-only", "proprietary"]


def classify(lic):
    """a licence string (SPDX-ish or prose) -> its class ("unknown" when it cannot tell)"""
    s = str(lic or "").lower()
    if not s.strip():
        return "unknown"
    if re.search(r"\bnc\b|non-?commercial|by-nc", s):
        return "non-commercial"
    if re.search(r"research[- ]only|academic|research licen[cs]e|research use", s):
        return "research-only"
    if "agpl" in s or "affero" in s:
        return "network-copyleft"
    if re.search(r"\blgpl|\bmpl|eupl|\bepl\b", s):
        return "weak-copyleft"
    if "gpl" in s:
        return "copyleft"
    if re.search(r"by-sa|share-?alike", s):
        return "share-alike"
    if re.search(r"cc0|public domain|\bpd\b|unlicense|librivox", s):
        return "public-domain"
    if re.search(r"cc[- ]?by|attribution", s):
        return "attribution"
    if re.search(r"source[- ]available|bsl-1\.1|elastic|sspl|business source", s):
        return "source-available"
    if re.search(r"licenseref-owner|licenseref-client|proprietary|all rights", s):
        return "proprietary"
    if re.search(r"\bmit\b|bsd|apache|\bisc\b|zlib|ofl|bsl-1\.0|boost|wtfpl|\bpsf\b|hpnd|unicode", s):
        return "permissive"
    return "unknown"


def vendored():
    """every UPSTREAM.json in the repository"""
    out = []
    for f in sorted(ROOT.glob("**/UPSTREAM.json")):
        if any(p in f.parts for p in ("node_modules", "out", ".git")):
            continue
        try:
            out.append({"dir": str(f.parent.relative_to(ROOT)), **json.loads(f.read_text())})
        except Exception as e:
            out.append({"dir": str(f.parent.relative_to(ROOT)), "error": str(e)})
    return out


def check():
    """notices, upstream records and ledger rows for every vendored component (nothing is refused for its licence)"""
    man = json.loads((ROOT / "assets" / "manifest.json").read_text())
    known = [x.get("path", "") for k in ("files", "generated", "external") for x in man.get(k, [])]
    probs, rows = [], []
    for v in vendored():
        d = ROOT / v["dir"]; name = v.get("name", v["dir"])
        if "error" in v:
            probs.append(f"{v['dir']}: UPSTREAM.json does not parse: {v['error']}"); continue
        for k in ("repository", "version", "license", "class", "license_files", "files", "patches"):
            if k not in v:
                probs.append(f"{name}: UPSTREAM.json lacks {k}")
        if v.get("class") and v["class"] not in CLASSES:
            probs.append(f"{name}: unknown licence class {v['class']}")
        if v.get("license") and v.get("class") and classify(v["license"]) not in (v["class"], "unknown"):
            probs.append(f"{name}: class {v['class']} but the licence reads as {classify(v['license'])}")
        for lf in v.get("license_files", []):
            if not (d / lf).exists():
                probs.append(f"{name}: licence file {lf} missing")
        if not any(k.rstrip("/") == v["dir"] or k.startswith(v["dir"] + "/") for k in known):
            probs.append(f"{name}: no row in assets/manifest.json")
        rows.append({"name": name, "dir": v["dir"], "version": v.get("version"), "license": v.get("license"), "class": v.get("class"),
                     "built": bool(v.get("binary") and (ROOT / "out" / "vendor-build" / name / v["binary"]).exists())})
    return {"ok": not probs, "problems": probs, "vendored": rows}


def build(name):
    """build a vendored component with its upstream recipe, in a copy, into out/vendor-build/<name>/"""
    v = next((x for x in vendored() if x.get("name") == name), None)
    if not v:
        raise FileNotFoundError(f"no vendored component {name}")
    out = ROOT / "out" / "vendor-build" / name; out.mkdir(parents=True, exist_ok=True)
    work = out / "src"   # build in a copy, so the vendored tree stays exactly as released
    subprocess.run(["rm", "-rf", str(work)], check=True); subprocess.run(["cp", "-r", str(ROOT / v["dir"]), str(work)], check=True)
    for step in v.get("build", []):
        cmd = step.format(out=str(out), src=str(work))
        r = subprocess.run(cmd, shell=True, cwd=work, capture_output=True, text=True, timeout=3600, env={**os.environ})
        if r.returncode:
            raise RuntimeError(f"{name}: {cmd} failed: {(r.stderr or r.stdout)[-800:]}")
    b = out / v["binary"] if v.get("binary") else None
    return {"name": name, "binary": str(b.relative_to(ROOT)) if b and b.exists() else None}


# ---------------------------------------------------------------- the ledger and a film's provenance
def ledger():
    """every component with its licence class: manifest files and tools, vendored code, voices, cast puppets"""
    man = json.loads((ROOT / "assets" / "manifest.json").read_text())
    rows = []
    for sec in ("files", "generated", "external", "tools_not_bundled"):
        for x in man.get(sec, []):
            rows.append({"kind": sec, "id": x.get("path") or x.get("name"), "license": x.get("license"),
                         "class": x.get("class") or classify(x.get("license"))})
    for v in vendored():
        rows.append({"kind": "vendored", "id": v["dir"], "license": v.get("license"), "class": v.get("class") or classify(v.get("license"))})
    reg = json.loads((ROOT / "voices" / "registry.json").read_text()).get("voices", {}) if (ROOT / "voices" / "registry.json").exists() else {}
    for vid, x in reg.items():
        rows.append({"kind": "voice", "id": vid, "license": x.get("license"), "class": classify(x.get("license")), "clean": x.get("status") == "clean"})
    idx = json.loads((ROOT / "cast" / "index.json").read_text()) if (ROOT / "cast" / "index.json").exists() else {"puppets": []}
    for p in idx.get("puppets", []):
        rows.append({"kind": "puppet", "id": p.get("path"), "license": p.get("license"), "class": classify(p.get("license"))})
    return rows


def provenance(film_dir, voice_status, credits_files, models=None):
    """what shaped a film, with its licence class, and the posting flags: voices not marked clean, and
    non-commercial, research-only, share-alike or source-available inputs.
    voice_status: {voice id: status}; credits_files: [{path, license}] from film.credits"""
    d = Path(film_dir)
    script = json.loads((d / "script.json").read_text()) if (d / "script.json").exists() else {}
    voices = {v.get("voice") for v in (script.get("speakers") or {}).values()} | ({script["voice"]} if script.get("voice") else set())
    used, flags = [], []
    for v in sorted(x for x in voices if x):
        st = voice_status.get(v, "unregistered")
        used.append({"kind": "voice", "id": v, "status": st})
        if st != "clean":
            flags.append(f"voice {v} is {st}, not clean")
    for f in credits_files:
        c = f.get("class") or classify(f.get("license"))
        used.append({"kind": "asset", "id": f.get("path") or f.get("name"), "license": f.get("license"), "class": c})
        if c in FLAG_AT_POSTING:
            flags.append(f"{f.get('path') or f.get('name')} is {c} ({f.get('license')})")
    recorded = json.loads((d / "provenance.json").read_text()).get("models", []) if (d / "provenance.json").exists() else []
    for m in recorded + list(models or []):
        c = m.get("class") or classify(m.get("license"))   # models that shaped outputs (WP-43 assists write these)
        used.append({"kind": "model", "id": m.get("name"), "license": m.get("license"), "class": c})
        if c in FLAG_AT_POSTING:
            flags.append(f"model {m.get('name')} is {c} ({m.get('license')})")
    return {"used": used, "flags": flags, "clear_to_post": not flags}


def self_test(tmp):
    """classes read right; vendored records pass; a film with a non-clean voice and a share-alike asset is flagged"""
    import shutil
    fails, got = [], {}
    cases = {"MIT": "permissive", "GPL-2.0-or-later": "copyleft", "AGPL-3.0": "network-copyleft", "CC BY-NC 4.0": "non-commercial",
             "CC-BY-SA-4.0": "share-alike", "CC0-1.0": "public-domain", "CC-BY-4.0": "attribution", "LGPL-2.1": "weak-copyleft",
             "OFL-1.1": "permissive", "Blizzard 2013 Lessac data, research licence": "research-only", "LicenseRef-owner": "proprietary",
             "MIT OR Apache-2.0": "permissive", "BSL-1.1": "source-available"}
    wrong = {k: classify(k) for k, v in cases.items() if classify(k) != v}
    if wrong:
        fails.append(f"classify: {wrong}")
    c = check(); got["vendored"] = [(r["name"], r["class"]) for r in c["vendored"]]
    if not c["ok"]:
        fails.append(f"vendor.check: {c['problems']}")
    d = Path(tmp) / "provenance_case"; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    (d / "script.json").write_text(json.dumps({"speakers": {"a": {"voice": "en_US-lessac-high"}, "b": {"voice": "kokoro:af_heart"}}}))
    (d / "provenance.json").write_text(json.dumps({"models": [{"name": "a gesture model", "license": "CC BY-NC 4.0"}]}))
    pr = provenance(d, {"en_US-lessac-high": "restricted", "kokoro:af_heart": "clean"}, [{"path": "sets/x.svg", "license": "CC-BY-SA-4.0"}, {"path": "f.ttf", "license": "OFL-1.1"}])
    got["flags"] = pr["flags"]
    if pr["clear_to_post"] or len(pr["flags"]) != 3:
        fails.append(f"provenance flags: {pr['flags']}")
    shutil.rmtree(d, ignore_errors=True)
    return fails, got
