"""All dbe commands. Each is a plain function registered with @command; arguments and results are JSON-safe."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import ROOT, COMMANDS, command, describe
from . import exporters as X

FILMS = ROOT / "films"
PY = os.environ.get("DBE_PY", sys.executable)            # python with piper/whisper/numpy for voice and audio
BLENDER = os.environ.get("DBE_BLENDER", shutil.which("blender") or "")
VOICES = os.environ.get("DBE_VOICES", str(Path.home() / "voices"))


def _run(cmd, cwd=ROOT, timeout=7200):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd[:3]))} failed: {(r.stderr or r.stdout)[-1500:]}")
    return (r.stdout or "").strip().splitlines()[-3:]


def _film(name):
    d = FILMS / name
    if not d.exists():
        raise FileNotFoundError(f"no film {name}")
    return d


def _json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


# ---------------- engine ----------------
@command("engine.commands")
def engine_commands():
    """List every command with its input schema (what agents see as tools)."""
    return describe()


@command("engine.doctor", deep=("boolean", "also start the browser and hash the model files", True))
def engine_doctor(deep=True):
    """What this machine has and lacks for Doodleberry (WP-02): core (engine, Studio, SVG renders, tests), audio
    (voices, alignment, mixing) and tools (PSD import, Act it out, extra renderers), each with the exact fix;
    tools/setup.sh applies them. ok means every required check passed."""
    from . import doctor
    return doctor.check(deep)


@command("docs.check")
def docs_check():
    """The build plan, feature map, work packages and command registry agree (WP-01): commands named in the docs
    exist, open feature rows name a work package, work-package references exist, every plan item has a status row
    or a work package, and every work package is scheduled."""
    from . import docscheck
    return docscheck.check()


@command("engine.info")
def engine_info():
    """Report which renderers and tools are available in this environment."""
    def ver(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30); return ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[0][:80]
        except Exception:
            return None
    return {"root": str(ROOT), "python": PY, "voices": VOICES,
            "renderers": {"svg": bool(shutil.which("node")), "synfig": ver(["synfig", "--version"]), "grease-pencil": ver([BLENDER, "--version"]) if BLENDER else None,
                          "lottie": True, "three": bool(shutil.which("node"))},
            "ffmpeg": ver(["ffmpeg", "-version"]), "films": sorted(p.name for p in FILMS.iterdir() if p.is_dir() and not p.name.startswith("_"))}


# ---------------- films ----------------
@command("film.create", name=("string", "folder name"), title=("string", "film title", ""), size=("array", "[w, h]", [1080, 1920]), fps=("integer", "frame rate", 30))
def film_create(name, title="", size=None, fps=30):
    """Create a shot-based film folder with empty brief, facts, script, shots and score."""
    d = FILMS / name
    d.mkdir(parents=True, exist_ok=True); (d / "build").mkdir(exist_ok=True)
    defaults = {"brief.md": f"# Brief — {title or name}\n", "facts.json": json.dumps({"facts": []}, indent=1),
                "script.json": json.dumps({"speakers": {}, "lines": []}, indent=1),
                "shots.json": json.dumps({"title": title or name, "size": size or [1080, 1920], "fps": fps, "shots": []}, indent=1),
                "score.json": json.dumps({"length_s": 10, "bpm": 100, "offset_s": 0, "sections": [{"kind": "main", "from_beat": 0, "to_beat": 16, "chords": ["F", "C", "Dm", "Bb"], "end_chord": "F"}]}, indent=1)}
    for f, c in defaults.items():
        if not (d / f).exists():
            (d / f).write_text(c)
    return {"film": name, "path": str(d)}


@command("film.get", name=("string", "film"))
def film_get(name):
    """Return a film's source files (brief, facts, script, shots, score) and its build outputs."""
    d = _film(name)
    src = {f: (d / f).read_text() for f in ["brief.md", "facts.json", "script.json", "shots.json", "score.json"] if (d / f).exists()}
    outs = sorted(str(p.relative_to(ROOT)) for p in (d / "build").rglob("*") if p.suffix in (".mp4", ".json", ".sif", ".html", ".png") and p.stat().st_size < 5e8)[:200] if (d / "build").exists() else []
    return {"film": name, "files": src, "outputs": outs}


@command("film.validate", name=("string", "film"))
def film_validate(name):
    """Check a film's data against the schemas and its own references (lines, puppets, clips, shot order)."""
    from . import validate
    return validate.film(_film(name))


def _rights_errors(name):
    """client-work characters may appear only in films for that client (shots.json brief.client)"""
    s = _shots(name, resolve=False); client = (s.get("brief") or {}).get("client", "")
    cast = {e["path"]: e for e in _json(ROOT / "cast" / "index.json", {"puppets": []})["puppets"]}
    errs = []
    for sh in s["shots"]:
        for c in sh.get("cast", []):
            r = (cast.get(c["puppet"]) or {}).get("rights") or {}
            if r.get("type") == "client" and r.get("owner") != client:
                errs.append(f"shot {sh['id']}: {c['puppet']} is client work for {r.get('owner')!r}; this film's brief.client is {client!r}")
    return errs


def _require_valid(name):
    from . import research
    r = film_validate(name)
    r["errors"] = r["errors"] + _rights_errors(name) + research.check(FILMS / name)["errors"]
    if r["errors"]:
        raise ValueError("film data is invalid:\n- " + "\n- ".join(r["errors"][:20]))
    return r


@command("film.write", name=("string", "film"), file=("string", "brief.md | facts.json | script.json | shots.json | score.json"), content=("string", "full file content (JSON as text for .json)"))
def film_write(name, file, content):
    """Write one source file of a film (validated as JSON for .json files)."""
    if file not in ("brief.md", "facts.json", "script.json", "shots.json", "score.json"):
        raise ValueError("file not allowed")
    data = json.loads(content) if file.endswith(".json") else None
    if file in ("script.json", "shots.json"):
        from . import validate
        bad = validate.schema_errors(file[:-5], data)
        if bad:
            raise ValueError("not written; schema errors:\n- " + "\n- ".join(bad[:20]))
    (_film(name) / file).write_text(content)
    return {"ok": True, **({"check": film_validate(name)} if file in ("script.json", "shots.json") else {})}


# ---------------- voice ----------------
@command("voice.build", name=("string", "film"))
def voice_build(name):
    """Synthesize narration/dialogue (Piper), align words (Whisper), make lip-sync visemes; writes timing.json.
    Voices are checked against voices/registry.json: only 'clean' voices pass unless script.json allows restricted ones."""
    _film(name)
    sc = _json(FILMS / name / "script.json", {})
    if sc.get("draft"):   # WP-06: drafted storyboards carry placeholder words until research rewrites them
        raise ValueError(f"script.json is a draft storyboard ({sc['draft']}); rewrite the lines after research and remove \"draft\" before voicing")
    voice_check(name)
    out = _run([PY, "engine/voice.py", f"films/{name}", "--voices-dir", VOICES])
    t = _json(FILMS / name / "timing.json", {})
    return {"duration": t.get("duration"), "lines": len(t.get("lines", [])), "speakers_with_visemes": list((t.get("visemes") or {}).keys()), "log": out}


@command("script.slots", name=("string", "film"), wpm=("number", "narration pace the slots are sized for (125-145)", 135),
         draft=("boolean", "also write a voiceless timing.json from the slots, so the picture (and the sound-off cut) can be made first", True))
def script_slots(name, wpm=135, draft=True):
    """Narration slots (plan 2.16): give every script line a fixed start and a maximum length at `wpm`, before any
    voice exists. The picture is cut on the slots (the sound-off cut is the master); voice.build then places each line
    at its slot start and keeps the slot's end, fitting a long line with its short alternate ("alt") or up to 15%
    faster, so a voice recorded later drops in without moving a single cut. Reports lines that still overflow."""
    d = _film(name); sc = _json(d / "script.json")
    gap = sc.get("gap_s", 0.4); t = sc.get("lead_in_s", 0.6); rows = []
    for ln in sc["lines"]:
        n = len(re.findall(r"[\w']+", ln["text"])); dur = round(n * 60.0 / wpm + 0.25, 3)
        ln["slot"] = [round(t, 3), dur]
        rows.append({"line": ln["id"], "start": round(t, 3), "max_s": dur, "words": n, **({"alt_words": len(re.findall(r"[\w']+", ln["alt"]))} if ln.get("alt") else {})})
        t += dur + gap + ln.get("pause", 0.0)
    sc["slots"] = {"wpm": wpm}
    (d / "script.json").write_text(json.dumps(sc, indent=1, ensure_ascii=False))
    if draft and not (d / "build" / "voice.wav").exists():
        lines = []
        for ln in sc["lines"]:
            s0, mx = ln["slot"]; ws = ln["text"].split(); L = [max(1, len(re.sub(r"\W", "", w))) for w in ws]; tot = sum(L); acc = 0; words = []
            for w, l in zip(ws, L):   # words spread over the slot by letters (a stand-in until a voice exists)
                a_ = s0 + (mx - 0.25) * acc / tot; acc += l; words.append({"text": w, "start": round(a_, 3), "end": round(s0 + (mx - 0.25) * acc / tot, 3)})
            lines.append({"id": ln["id"], "speaker": ln.get("speaker", "narrator"), "fact": ln.get("fact"), "text": ln["text"], "start": s0, "end": round(s0 + mx, 3),
                          "slot": ln["slot"], "align": "slot", "words": words})
        (d / "timing.json").write_text(json.dumps({"fps": sc.get("fps", 30), "duration": round(t, 3), "lines": lines, "visemes": {}, "draft": "slots (no voice yet)"}, indent=1))
    return {"wpm": wpm, "slots": rows, "length_s": round(t, 3), "draft_timing": bool(draft and not (d / "build" / "voice.wav").exists())}


def voice_check(name):
    script = _json(FILMS / name / "script.json", {})
    reg = _voice_registry()
    bad = {spk: (v.get("voice"), reg.get(v.get("voice"), {"status": "unknown", "license": "not in voices/registry.json"}))
           for spk, v in (script.get("speakers") or {}).items() if reg.get(v.get("voice"), {}).get("status") != "clean"}
    if bad and not script.get("allow_restricted_voices"):
        raise PermissionError("voice licence gate: " + "; ".join(f"{spk} uses {vid} ({r['status']}: {r['license']})" for spk, (vid, r) in bad.items())
                              + '. Pick a clean voice (voices.list) or set "allow_restricted_voices": true in script.json for internal tests.')
    return bad


def _voice_registry():
    """registry voices plus every installed Kokoro voice (Apache-2.0 weights; listed as clean)"""
    reg = dict(_json(ROOT / "voices" / "registry.json", {}).get("voices", {}))
    kdir = Path(VOICES) / "kokoro"
    if (kdir / "voices-v1.0.bin").exists():
        import numpy as np
        try:
            names = sorted(np.load(kdir / "voices-v1.0.bin").files)
        except Exception:
            names = []
        lang = {"a": "US English", "b": "UK English", "e": "Spanish", "f": "French", "h": "Hindi", "i": "Italian", "j": "Japanese", "p": "Brazilian Portuguese", "z": "Mandarin"}
        for n in names:
            reg.setdefault(f"kokoro:{n}", {"status": "clean", "license": "Apache-2.0 (Kokoro-82M weights)", "language": lang.get(n[:1], "?"),
                                          "gender": {"f": "female", "m": "male"}.get(n[1:2], "?")})
    return reg


@command("voices.list", language=("string", "filter by language name, e.g. Spanish", ""))
def voices_list(language=""):
    """Voices (Piper and Kokoro) with licence status (clean / restricted / unclear) and whether each is installed."""
    reg = _voice_registry()
    inst = lambda vid: (Path(VOICES) / "kokoro" / "kokoro-v1.0.onnx").exists() if vid.startswith("kokoro:") else (Path(VOICES) / f"{vid}.onnx").exists()
    return {vid: {**r, "installed": inst(vid)} for vid, r in reg.items() if not language or language.lower() in str(r.get("language", vid)).lower()}


# ---------------- cast ----------------
@command("cast.list")
def cast_list():
    """List registered puppets (cast library) with author, licence and voice profile."""
    return _json(ROOT / "cast" / "index.json", {"puppets": []})


OPEN_LICENSES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT", "Apache-2.0", "OFL-1.1", "public-domain"}


RIGHTS = ("open", "owner", "client")


@command("cast.add", path=("string", "path to a .puppet.json inside the repo"), id=("string", "cast id"),
         author=("string", "who drew it"), license=("string", "open: an SPDX id (CC0-1.0, CC-BY-4.0...); owner or client: LicenseRef-owner / LicenseRef-client"),
         provenance=("string", "how it was made (drawn in Rig Canvas, traced from own sketch...)"),
         voice=("object", "optional voice profile {voice, fx}", None), personality=("string", "acting notes", ""),
         rights=("string", "open (openly licensed) | owner (the studio's or a creator's own IP) | client (made for a client)", "open"),
         owner=("string", "rights holder, required for owner and client rights", ""),
         terms=("string", "client work: usage and transfer terms (e.g. 'exclusive to ACME films, rights transfer on payment')", ""))
def cast_add(path, id, author, license, provenance, voice=None, personality="", rights="open", owner="", terms=""):
    """Register a puppet in the cast library: lints it, records author, licence, provenance and a content hash, and
    appends an entry to cast/provenance.jsonl so every change to the library is traceable."""
    import hashlib, datetime
    pp = (ROOT / path).resolve()
    if ROOT not in pp.parents or not pp.exists():
        raise FileNotFoundError(f"{path} is not a puppet file inside the repo")
    if rights not in RIGHTS:
        raise ValueError(f"rights must be one of {RIGHTS}")
    if rights == "open" and license not in OPEN_LICENSES:
        raise ValueError(f"open rights need an open licence ({', '.join(sorted(OPEN_LICENSES))}); for your own characters use rights=owner")
    if rights in ("owner", "client") and not owner:
        raise ValueError(f"{rights} rights need an owner (the rights holder)")
    if rights == "client" and not terms:
        raise ValueError("client work needs its usage and transfer terms")
    lint = puppet_lint(path)
    missing = [i for i in lint.get("issues", []) if i["level"] == "missing"]
    if missing:
        raise ValueError(f"puppet is incomplete: {missing[:5]}")
    pup = _json(pp)
    if voice and voice.get("voice"):
        if _voice_registry().get(voice["voice"], {}).get("status") != "clean":   # registry file plus installed Kokoro voices
            raise PermissionError(f"voice {voice['voice']} is not marked clean in voices/registry.json")
    idx = _json(ROOT / "cast" / "index.json", {"puppets": []})
    entry = {"id": id, "name": pup.get("name", id), "path": str(pp.relative_to(ROOT)), "template": pup.get("template"),
             "author": author, "license": license, "provenance": provenance,
             "rights": {"type": rights, **({"owner": owner} if owner else {}), **({"terms": terms} if terms else {})}, "views": sorted((pup.get("views") or {}).keys()),
             "sha256": hashlib.sha256(pp.read_bytes()).hexdigest()[:16], **({"voice": voice} if voice else {}), **({"personality": personality} if personality else {})}
    idx["puppets"] = [e for e in idx["puppets"] if e["id"] != id] + [entry]
    (ROOT / "cast" / "index.json").write_text(json.dumps(idx, indent=1))
    with open(ROOT / "cast" / "provenance.jsonl", "a") as f:
        f.write(json.dumps({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "action": "add", **entry}) + "\n")
    return {"registered": entry, "warnings": [i["msg"] for i in lint.get("issues", []) if i["level"] != "missing"]}


@command("cast.generate", spec=("object", "character spec (see puppet/generator.py): name, build, age, skin, hair, top, bottom, shoes, eyes, accessories"),
         id=("string", "cast id (also the file name under cast/generated/)"))
def cast_generate(spec, id):
    """Make an original, fully rigged humanoid from a short spec (build, age, skin, hair, outfit, accessories) and
    register it in the cast library (CC0, provenance records the spec). Every character works with every clip, the
    acting tools, the turn control and all renderers."""
    import re as _re
    if not _re.match(r"^[a-z0-9_-]+$", id):
        raise ValueError("id must be lowercase letters, digits, - or _")
    sys.path.insert(0, str(ROOT / "puppet"))
    from generator import generate
    pz = generate({**spec, "id": id})
    out = ROOT / "cast" / "generated" / f"{id}.puppet.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pz))
    reg = cast_add(str(out.relative_to(ROOT)), id, "Doodleberry character generator", "CC0-1.0",
                   f"generated by puppet/generator.py from spec {json.dumps(spec, sort_keys=True)}", rights="open")
    return {"puppet": str(out.relative_to(ROOT)), "registered": reg["registered"]["id"], "warnings": reg.get("warnings")}


@command("acting.plan", name=("string", "film (voiced: run voice.build first)"))
def acting_plan(name):
    """Gesture planner: every speaking cast member acts from the script and the voice with no hand-placed clips:
    beats on emphasised words (loudness, pitch, length), points on pointing words, open palms on exclamations, a shrug
    or tilt on questions; listeners look at the speaker, nod after each line and blink on pauses. Generated clips are
    tagged auto and replaced on every run; hand-placed clips are kept."""
    d = _film(name)
    if not (d / "timing.json").exists():
        raise FileNotFoundError("no timing.json: run voice.build first")
    spans = {sh["id"]: [sh["start"], sh["end"]] for sh in _shots(name)["shots"]}   # resolved (line-relative) shot times
    r = _run([PY, "dbe/gestures.py", str(d), json.dumps(spans)], timeout=600)
    return {"film": name, "plan": json.loads(r[-1])}


@command("film.credits", name=("string", "film"))
def film_credits(name):
    """Credits for a film from what it actually uses: puppets (author, licence), voices (licence), fonts and engines.
    Writes films/<name>/build/credits.txt."""
    d = _film(name); s = _shots(name); sc = _json(d / "script.json", {})
    cast = {e["path"]: e for e in _json(ROOT / "cast" / "index.json", {"puppets": []})["puppets"]}
    reg = _json(ROOT / "voices" / "registry.json", {}).get("voices", {})
    man = _json(ROOT / "assets" / "manifest.json", {"files": []})
    lines, used = [f"{(s.get('brief') or {}).get('title') or s.get('title', name)}", ""], set()
    for sh in s["shots"]:
        for c in sh.get("cast", []):
            if c["puppet"] in used:
                continue
            used.add(c["puppet"]); e = cast.get(c["puppet"], {}); r = e.get("rights") or {}
            lic = e.get("license", "licence not recorded") if r.get("type", "open") == "open" else f"© {r.get('owner')}, all rights reserved"
            meta = _json(ROOT / c["puppet"], {}).get("meta", {}) if (ROOT / c["puppet"]).exists() else {}
            if meta.get("credit"):  # attribution licences: the creator's own credit line, licence link, and what changed
                lic_url = {"CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/", "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/"}.get(e.get("license", ""), "")
                lines.append(f"Character: {meta['credit']}{' ' + lic_url if lic_url else ''} Source: {meta.get('source_url', 'n/a')}. "
                             "Changes: imported into Doodleberry as a puppet (parts re-rasterised, swaps and springs derived from the rig).")
            else:
                lines.append(f"Character: {e.get('name', c['puppet'])} by {e.get('author', 'unknown')} ({lic})")
    vreg = {**reg, **{k: v for k, v in _voice_registry().items() if k not in reg}} if "_voice_registry" in globals() else reg
    engines = set()
    for spk, v in (sc.get("speakers") or {}).items():
        vid = v.get("voice", ""); r = vreg.get(vid, {})
        if vid.startswith("kokoro:"):
            engines.add("Kokoro-82M (Apache-2.0)")
            lines.append(f"Voice of {spk}: Kokoro-82M voice {vid.split(':', 1)[1]} ({r.get('license', 'Apache-2.0')})")
        else:
            engines.add("Piper")
            lines.append(f"Voice of {spk}: Piper voice {vid} ({r.get('license', 'licence not recorded')})")
    rend = sorted({sh.get("renderer", "svg") for sh in s["shots"]})
    names = {"svg": "Chromium (Playwright)", "synfig": "Synfig (GPL-3.0)", "grease-pencil": "Blender Grease Pencil (GPL)", "lottie": "lottie-web (MIT)"}
    uses = {"captions", "player"} | {f"renderer:{r}" for r in rend}
    assets = [f["attribution"] for f in man["files"] if set(f.get("used_by", [])) & uses]
    lines += ["", "Rendered with " + ", ".join(names.get(r, r) for r in rend) + f"; speech by {', '.join(sorted(engines)) or 'Piper'}; alignment by faster-whisper (MIT); audio by ffmpeg.",
              *(["Assets: " + "; ".join(dict.fromkeys(assets))] if assets else []), "Made with Doodleberry."]
    out = d / "build" / "credits.txt"; out.parent.mkdir(exist_ok=True); out.write_text("\n".join(lines) + "\n")
    return {"path": str(out.relative_to(ROOT)), "credits": lines}


# ---------------- licence ledger and vendored code (WP-33) ----------------
@command("licence.ledger", cls=("string", "only this licence class (e.g. copyleft, non-commercial); empty for all", ""))
def licence_ledger(cls=""):
    """Every component with its licence class (WP-33): manifest files and tools, vendored code, voices, cast puppets.
    In-house R&D may use any class; the classes non-commercial, research-only, share-alike and source-available are
    flagged when they shape a film that is posted publicly (film.provenance)."""
    from collections import Counter
    from . import vendoring as V
    rows = [r for r in V.ledger() if not cls or r["class"] == cls]
    return {"by_class": dict(Counter(r["class"] for r in V.ledger())), "flagged_at_posting": sorted(V.FLAG_AT_POSTING), "rows": rows}


@command("vendor.check")
def vendor_check():
    """Vendored code is recorded (WP-33): every UPSTREAM.json has its repository, version, licence and class, licence
    files present, patches listed, and a row in assets/manifest.json; reports which components are built. No licence
    class is refused."""
    from . import vendoring as V
    return V.check()


@command("vendor.build", name=("string", "vendored component (vendor/<name>/UPSTREAM.json)"))
def vendor_build(name):
    """Build a vendored component with its upstream recipe, in a copy, into out/vendor-build/<name>/ (WP-33). This
    runs the upstream's own build scripts (configure, make, cargo)."""
    from . import vendoring as V
    return V.build(name)


@command("film.provenance", name=("string", "film"))
def film_provenance(name):
    """What shaped a film, each with its licence class (WP-33): characters, voices, the third-party files its
    renderers and captions use, and models recorded in provenance.json. Flags what restricts a public post: voices not
    marked clean, and non-commercial, research-only, share-alike or source-available inputs."""
    from . import vendoring as V
    d = _film(name); s = _shots(name, resolve=False)
    cast = {e["path"]: e for e in _json(ROOT / "cast" / "index.json", {"puppets": []})["puppets"]}
    files = []
    for p in sorted({c["puppet"] for sh in s["shots"] for c in sh.get("cast", [])}):
        e = cast.get(p, {}); files.append({"path": p, "license": e.get("license") or (_json(ROOT / p, {}) or {}).get("meta", {}).get("license", "")})
    man = _json(ROOT / "assets" / "manifest.json", {"files": []})
    uses = {"captions", "player"} | {f"renderer:{sh.get('renderer', 'svg')}" for sh in s["shots"]}
    files += [{"path": f["path"], "license": f.get("license"), "class": f.get("class")} for f in man["files"] if set(f.get("used_by", [])) & uses]
    status = {k: v.get("status", "unknown") for k, v in _voice_registry().items()}
    return V.provenance(d, status, files)


def _puppet_errors(puppet):
    """schema errors for a puppet (puppet/spec/puppet.schema.json)"""
    import jsonschema
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:120]}"
            for e in jsonschema.Draft202012Validator(_json(ROOT / "puppet" / "spec" / "puppet.schema.json")).iter_errors(puppet)]


@command("puppet.lint", path=("string", "path to a .puppet.json"))
def puppet_lint(path):
    """Check a puppet against its template (missing parts, swaps, raw colours)."""
    p = _json(ROOT / path)
    js = f"globalThis.window=globalThis; const fs=require('fs'); new Function(fs.readFileSync('puppet/loader/puppet.js','utf8'))(); const T=JSON.parse(fs.readFileSync('puppet/templates/{p['template']}.json','utf8')); const P=JSON.parse(fs.readFileSync({json.dumps(path)},'utf8')); console.log(JSON.stringify(Puppet.lint(P,T)))"
    r = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True)
    return {"issues": json.loads(r.stdout or "[]")}


# ---------------- shots ----------------
_LINE_T = re.compile(r"^\s*([\w-]+)\.(start|end)\s*([+-]\s*[\d.]+)?\s*$")


def resolve_times(obj, timing):
    """Turn line-relative times into seconds, so acting stays on the words after any voice or language change.
    "mid.start+0.9" = 0.9 s after line "mid" begins; "end.end-0.2". Applies to start/end/t fields and to the time of
    every [t, value] key in a list."""
    L = {l["id"]: l for l in (timing or {}).get("lines", [])}

    def t_of(v):
        if not isinstance(v, str):
            return v
        m = _LINE_T.match(v)
        if not m or m.group(1) not in L:
            raise ValueError(f"unknown time reference {v!r} (lines: {', '.join(L) or 'none - run voice.build'})")
        return round(L[m.group(1)][m.group(2)] + float((m.group(3) or "0").replace(" ", "")), 3)

    def walk(o):
        if isinstance(o, dict):
            return {k: (t_of(v) if k in ("start", "end", "t", "until", "arrive") and isinstance(v, str) and k != "clip" else walk(v)) for k, v in o.items()}
        if isinstance(o, list):
            if len(o) == 2 and isinstance(o[0], str) and _LINE_T.match(o[0]):
                return [t_of(o[0]), walk(o[1])]
            return [walk(x) for x in o]
        return o
    return walk(obj)


def _brand_kit(shots_all):
    """a film's brand kit: shots.json "brand": true is the house kit (brand/brand.json); a string names one,
    brand/<id>.json, so each channel's films carry their own (WP-32); none when the film sets no brand"""
    b = shots_all.get("brand")
    if not b:
        return None
    kit = "brand" if b is True else str(b)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", kit):
        raise ValueError(f"brand kit ids are lower-case words: {kit!r}")
    k = _json(ROOT / "brand" / f"{kit}.json", None)
    if k is None:
        raise FileNotFoundError(f"no brand kit brand/{kit}.json")
    return k


def _shots(name, resolve=True):
    s = _json(FILMS / name / "shots.json")
    if not s:
        raise FileNotFoundError("shots.json missing")
    if not resolve:
        return s
    tm = _json(FILMS / name / "timing.json", {})
    r = resolve_times(s, tm)
    if (FILMS / name / "data.json").exists():   # data-bound text and charts (plan 2.17)
        from .databind import bind
        r = bind(r, _json(FILMS / name / "data.json", {}))
    if r.get("beat_cuts") and (FILMS / name / "score.json").exists() and tm.get("lines"):
        # cuts on the music (plan 2.14): each shot change moves to the bar line (else beat) in the pause it falls in
        from . import edit as E
        g = E.grid(FILMS / name); fps = r.get("fps", 30); lines = {l["id"]: l for l in tm["lines"]}
        for a_, b_ in zip(r["shots"], r["shots"][1:]):
            if abs(a_["end"] - b_["start"]) < 1e-3:
                t, _ = E.snap(b_["start"], "start", lines, g, r["shots"][-1]["end"])
                a_["end"] = b_["start"] = round(round(t * fps) / fps, 4)
    return r


def _shot(name, shot_id):
    s = _shots(name)
    for i, sh in enumerate(s["shots"]):
        if sh["id"] == shot_id:
            return s, sh, i
    raise KeyError(f"no shot {shot_id}")


def _bake(name, shot_id):
    s, sh, _ = _shot(name, shot_id)
    d = FILMS / name
    timing = _json(d / "timing.json", {})
    fps = s.get("fps", 30)
    cast = []
    for c in sh.get("cast", []):
        tl = dict(c.get("timeline", {}))
        if "visemes_from" in tl:
            tl["visemes"] = (timing.get("visemes") or {}).get(tl.pop("visemes_from"), [])
        cast.append({"puppet": str((ROOT / c["puppet"]).resolve()), "place": c.get("place", {"x": 540, "y": 1500, "s": 1}), "timeline": tl})
    spec = {"fps": fps, "frames": round((sh["end"] - sh["start"]) * fps), "start": sh["start"], "cast": cast, "step": (sh.get("style") or {}).get("step"),
            "size": s.get("size", [1080, 1920]), **({"camera": sh["camera"]} if sh.get("camera") else {})}
    if not sh.get("camera") and (sh.get("camera_auto") or (sh.get("style") or {}).get("float")):
        # the SVG player's own camera (auto framing, float drift), frame by frame, so every renderer frames the shot alike (WP-14)
        vk = subprocess.run(["node", "tools/view_keys.mjs", str(_player_page(name)), shot_id, str(sh["start"]), str(fps), str(spec["frames"])],
                            cwd=ROOT, capture_output=True, text=True, timeout=900)
        if vk.returncode == 0 and vk.stdout.strip():
            spec["camera"] = json.loads(vk.stdout.strip().splitlines()[-1])
    bdir = d / "build" / "shots"; bdir.mkdir(parents=True, exist_ok=True)
    (bdir / f"{shot_id}.spec.json").write_text(json.dumps(spec))
    _run(["node", "tools/bake.mjs", str(bdir / f"{shot_id}.spec.json"), str(bdir / f"{shot_id}.baked.json")])
    return s, sh, bdir, _json(bdir / f"{shot_id}.baked.json")


def _player_page(name):
    """write the shot player page for a film (SVG renderer and background plates)"""
    d = FILMS / name
    puppets = sorted({c["puppet"] for sh in _shots(name)["shots"] for c in sh.get("cast", [])})
    (d / "build").mkdir(exist_ok=True)
    tags = "".join(f'<script>window.PUPPETS=window.PUPPETS||{{}};window.PUPPETS[{json.dumps(p)}]={(ROOT / p).read_text()};</script>' for p in puppets)
    clip_tags = "".join(f'<script src="../../../puppet/clips/{c.name}"></script>' for c in sorted((ROOT / "puppet" / "clips").glob("*.js")))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>@font-face{{font-family:'Fredoka';src:url('../../../engine/fonts/Fredoka.ttf')}}@font-face{{font-family:'Patrick Hand';src:url('../../../engine/fonts/PatrickHand-latin.woff2') format('woff2'),url('../../../engine/fonts/PatrickHand-latin-ext.woff2') format('woff2')}}@font-face{{font-family:'Atkinson Mono';src:url('../../../engine/fonts/AtkinsonMono-400.woff2') format('woff2')}}@font-face{{font-family:'Noto Sans Sinhala';font-weight:400;src:url('../../../engine/fonts/NotoSansSinhala-400.woff2') format('woff2')}}@font-face{{font-family:'Noto Sans Sinhala';font-weight:700;src:url('../../../engine/fonts/NotoSansSinhala-700.woff2') format('woff2')}}html,body{{margin:0;background:#000;overflow:hidden}}text{{font-family:'Fredoka',sans-serif}}</style></head>
<body><svg id="stage" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="../../../engine/timeline.js"></script><script src="../../../puppet/loader/puppet.js"></script><script src="../../../puppet/loader/acting.js"></script>
{clip_tags}<script src="../../../sets/sets.js"></script><script src="../../../sets/more.js"></script><script src="../../../assets/icons/lucide.js"></script><script src="../../../dbe/player/kit.js"></script><script src="../../../dbe/player/props.js"></script><script src="../../../dbe/player/fx.js"></script><script src="../../../dbe/player/comp.js"></script>{tags}
<script>window.SHOTS={json.dumps(_shots(name))};window.TIMING={json.dumps(_json(d / 'timing.json', {}))};window.SCRIPT={json.dumps(_json(d / 'script.json', {}))};window.DATA={json.dumps(_json(d / 'data.json', {}))};window.BRAND={json.dumps(_brand_kit(_shots(name)))};</script>
<script src="../../../dbe/player/player.js"></script></body></html>"""
    (d / "build" / "player.html").write_text(page)
    return d / "build" / "player.html"


def _render_page(page, query, out):
    url = "file://" + str(page) + "?" + query
    _run(["node", "tools/three/run3d.mjs", url, str(out), "4"])


def _set_video(name, sh, bdir):
    """the shot's set (with drifting clouds, ground shadows) rendered as video by the player, for compositing"""
    v = bdir / f"{sh['id']}.set.mp4"
    _render_page(_player_page(name), f"shot={sh['id']}&bg=1", v)
    return v


def _composite(set_video, layer_input, W, H, out):
    """alpha character frames (any size; scaled to W×H) over the set video"""
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(set_video), *layer_input, "-filter_complex",
          f"[1:v]scale={W}:{H}:flags=lanczos,format=rgba[c];[0:v][c]overlay=0:0:shortest=1,format=yuv420p[v]", "-map", "[v]",
          "-c:v", "libx264", "-crf", "16", str(out)])


def _bg_png(name, sh, bdir):
    page = _player_page(name)
    png = bdir / f"{sh['id']}.bg.png"
    js = f"""const {{createRequire}}=require('module');const r=createRequire(process.cwd()+'/');const {{chromium}}=r('playwright');(async()=>{{const b=await chromium.launch();const p=await b.newPage({{viewport:{{width:1080,height:1920}}}});
await p.goto('file://{page}?shot={sh["id"]}&bg=1');await p.waitForFunction(()=>window.ready===true);await p.evaluate(()=>window.renderFrame(0));await p.screenshot({{path:'{png}'}});await b.close();}})();"""
    subprocess.run(["node", "-e", js], cwd=ROOT, check=True, capture_output=True, text=True)
    return png


@command("shot.render", name=("string", "film"), shot=("string", "shot id"), renderer=("string", "svg | synfig | grease-pencil | lottie (default: the shot's renderer)", ""))
def shot_render(name, shot, renderer=""):
    """Render one shot to build/shots/<id>.mp4 with its renderer (all renderers read the same baked acting).
    Overriding the renderer writes <id>.<renderer>.mp4 instead, for side-by-side comparison."""
    _require_valid(name)
    s, sh, bdir, baked = _bake(name, shot)
    own = sh.get("renderer", "svg"); renderer = renderer or own
    from . import rparity as RP   # WP-14: each renderer draws what it can, and says what it cannot
    why = RP.refusal(renderer, sh, [_json(c["puppet"]) for c in baked["cast"]]) if renderer != "svg" else None
    if why:
        raise ValueError(f"shot {shot}: {why}; render it with svg")
    W, H = s.get("size", [1080, 1920]); fps = s.get("fps", 30)
    out = bdir / (f"{shot}.mp4" if renderer == own else f"{shot}.{renderer}.mp4")
    if renderer == "svg":
        _render_page(_player_page(name), f"shot={shot}", out)
    elif renderer == "synfig":
        # characters by Synfig (alpha), over the animated set from the player
        setv = _set_video(name, sh, bdir)
        (bdir / f"{shot}_assets").mkdir(exist_ok=True)
        sif = bdir / f"{shot}.sif"; sif.write_text(X.to_synfig(baked, (W, H), transparent=True, assets_dir=bdir / f"{shot}_assets"))
        fr = bdir / f"{shot}_syn"; shutil.rmtree(fr, ignore_errors=True); fr.mkdir()
        _run(["synfig", str(sif), "-t", "png", "-o", str(fr / "f.png"), "-q"])
        frames = sorted(fr.glob("f.*.png"))
        _composite(setv, ["-framerate", str(fps), "-start_number", frames[0].stem.split(".")[-1], "-i", str(fr / "f.%04d.png")], W, H, out)
    elif renderer == "grease-pencil":
        if not BLENDER:
            raise RuntimeError("Blender not found; set DBE_BLENDER")
        setv = _set_video(name, sh, bdir)
        gpj = bdir / f"{shot}.gp.json"; gpj.write_text(json.dumps(X.to_gp_frames(baked, (W, H))))
        fr = bdir / f"{shot}_gp"; shutil.rmtree(fr, ignore_errors=True); fr.mkdir()
        _run([BLENDER, "-b", "--factory-startup", "--gpu-backend", "vulkan", "--python", "dbe/blender_gp.py", "--", str(gpj), str(fr / "f_"), "-", "0.5"], timeout=14400)
        _composite(setv, ["-framerate", str(fps), "-start_number", "1", "-i", str(fr / "f_%04d.png")], W, H, out)
    elif renderer == "lottie":
        lj = export_lottie(name, shot)["path"]
        page = bdir / f"{shot}.lottie.html"
        page.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:{sh.get('lottie_bg', '#ffffff')}}}#a{{width:{W}px;height:{H}px}}</style></head><body><div id="a"></div>
<script src="{ROOT}/engine/vendor/lottie/lottie.min.js"></script><script>const anim=lottie.loadAnimation({{container:document.getElementById('a'),renderer:'svg',loop:false,autoplay:false,animationData:{(ROOT / lj).read_text()}}});
window.FRAMES={baked['frames']};window.renderFrame=f=>anim.goToAndStop(f,true);anim.addEventListener('DOMLoaded',()=>{{window.ready=true;}});</script></body></html>""")
        _render_page(page, "", out)
    else:
        raise ValueError(f"unknown renderer {renderer}")
    if renderer == own:   # record what was rendered, so film.render reuses this shot while it is unchanged
        (bdir / f"{shot}.hash").write_text(_shot_hash(name, next(x for x in _shots(name)["shots"] if x["id"] == shot), _shots(name)))
    return {"shot": shot, "renderer": renderer, "frames": baked["frames"], "path": str(out.relative_to(ROOT))}


@command("export.lottie", name=("string", "film"), shot=("string", "shot id"),
         background=("string", "plate (embed the set as an image, default) | none (transparent, for overlays)", "plate"))
def export_lottie(name, shot, background="plate"):
    """Export one shot's puppet animation as Lottie JSON (web, apps, After Effects). Views, swaps, lip-sync and
    springs are baked; the set is embedded as an image unless background is none."""
    import base64
    s, sh, bdir, baked = _bake(name, shot)
    lj = bdir / f"{shot}.lottie.json"
    img = None
    if background == "plate":
        img = "data:image/png;base64," + base64.b64encode(_bg_png(name, sh, bdir).read_bytes()).decode()
    lj.write_text(json.dumps(X.to_lottie(baked, s.get("size", [1080, 1920]), name=f"{name}:{shot}", bg=sh.get("lottie_bg"), bg_image=img)))
    return {"path": str(lj.relative_to(ROOT)), "bytes": lj.stat().st_size}


@command("export.synfig", name=("string", "film"), shot=("string", "shot id"))
def export_synfig(name, shot):
    """Export one shot as a Synfig .sif project (open and edit it in Synfig Studio)."""
    s, sh, bdir, baked = _bake(name, shot)
    sif = bdir / f"{shot}.sif"; sif.write_text(X.to_synfig(baked, s.get("size", [1080, 1920])))
    return {"path": str(sif.relative_to(ROOT))}


# ---------------- whole film ----------------
ENGINE_FILES = ["dbe/player/player.js", "dbe/player/kit.js", "dbe/player/fx.js", "dbe/player/props.js", "dbe/player/comp.js", "puppet/loader/puppet.js", "puppet/loader/acting.js", "sets/sets.js", "sets/more.js", "tools/bake.mjs",
                "dbe/exporters.py", "dbe/geom.py", "dbe/blender_gp.py", "tools/three/run3d.mjs"]


def _shot_hash(name, sh, s):
    """content hash of everything a shot's picture depends on: the resolved shot, film size/fps, puppets and clip
    libraries, lip-sync data for its speakers, and the renderer code. Unchanged hash = the old render is still right."""
    import hashlib
    h = hashlib.sha256()
    h.update(json.dumps({"shot": sh, "size": s.get("size"), "fps": s.get("fps"), "captions": s.get("captions")}, sort_keys=True).encode())
    # lines and mouth cues the shot can show; the auto camera also looks at lines up to 0.5 s around the shot
    mg = 0.5 if sh.get("camera_auto") else 0.0
    tm = _json(FILMS / name / "timing.json", {}); a0, a1 = sh.get("start", 0) - mg, sh.get("end", 1e9) + mg
    for c in sh.get("cast", []):
        h.update((ROOT / c["puppet"]).read_bytes())
        sp = (c.get("timeline") or {}).get("visemes_from") or c.get("speaker")
        if sp:   # only the mouth cues inside this shot
            h.update(json.dumps([v for v in (tm.get("visemes") or {}).get(sp, []) if a0 <= v[0] <= a1]).encode())
    # only the lines this shot shows (bubbles, words); line-relative times are already resolved into the shot itself
    h.update(json.dumps([l for l in tm.get("lines", []) if l["start"] < a1 - 1e-6 and l["end"] > a0 + 1e-6], sort_keys=True).encode())
    for f in sorted((ROOT / "puppet" / "clips").glob("*.json")) + [ROOT / x for x in ENGINE_FILES]:
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:20]


POST_PRESETS = {  # finishing looks: colour grade, vignette strength (0-1), grain strength (0-20)
    "crisp": {},
    "film": {"grade": "eq=contrast=1.04:saturation=1.05,colorbalance=rs=0.03:gs=0.01:bs=-0.03:rh=0.02:bh=-0.02", "vignette": 0.35, "grain": 6},
    "warm": {"grade": "colorbalance=rs=0.05:gs=0.02:bs=-0.05:rm=0.03:bm=-0.03", "vignette": 0.2, "grain": 2},
    "cool": {"grade": "colorbalance=rs=-0.04:bs=0.05:bm=0.03", "vignette": 0.2, "grain": 2},
    "paper": {"grade": "eq=saturation=0.88:contrast=0.97", "vignette": 0.25, "grain": 5},
    "noir": {"grade": "hue=s=0,eq=contrast=1.15", "vignette": 0.5, "grain": 8},
}


def post_filters(post):
    """shots.json "post": "film" | {"preset": "film", "grade": "<ffmpeg filters>", "vignette": 0.3, "grain": 6, "lut": "path.cube"}
    -> an ffmpeg filter chain. Grain uses a fixed seed, so renders are repeatable."""
    if isinstance(post, str):
        post = {"preset": post}
    p = {**POST_PRESETS.get(post.get("preset", "crisp"), {}), **{k: v for k, v in post.items() if k != "preset"}}
    chain = []
    if p.get("lut"):
        lut = _inside(p["lut"], True); chain.append(f"lut3d=file={lut.relative_to(ROOT)}")
    if p.get("grade"):
        chain.append(p["grade"])
    if p.get("vignette"):
        chain.append(f"vignette=angle={0.25 + 0.5 * float(p['vignette']):.3f}:mode=forward")
    if p.get("grain"):
        chain.append(f"noise=c0s={int(p['grain'])}:c0f=t+u:all_seed=7")
    return ",".join(chain)


@command("film.render", name=("string", "film"), only=("array", "shot ids to (re)render; default: only shots whose inputs changed", None),
         aspect=("string", "render another aspect ratio from the same film: 16:9 | 9:16 | 1:1 (default: the film's own)", ""))
def film_render(name, only=None, aspect=""):
    """Render every shot with its renderer, assemble, score and mix the audio, mux, and run QA."""
    if aspect:
        W0, H0 = _shots(name, resolve=False).get("size", [1080, 1920])
        if ASPECT_SIZE.get(aspect) != [W0, H0]:
            if aspect not in ASPECT_SIZE:
                raise ValueError(f"aspect must be one of {list(ASPECT_SIZE)}")
            dname, tag = _derive_aspect(name, aspect)
            r = film_render(dname, only)
            for f, to in (("final.mp4", f"final_{tag}.mp4"), ("captions.srt", f"captions_{tag}.srt"), ("captions.vtt", f"captions_{tag}.vtt")):
                if (FILMS / dname / "build" / f).exists():
                    shutil.copy(FILMS / dname / "build" / f, FILMS / name / "build" / to)
            return {**r, "aspect": aspect, "final": f"films/{name}/build/final_{tag}.mp4", "derived_film": dname}
    _require_valid(name)
    d = _film(name); s = _shots(name); fps = s.get("fps", 30)
    done = []
    skipped = []
    for sh in s["shots"]:
        mp4 = d / "build" / "shots" / f"{sh['id']}.mp4"; hf = d / "build" / "shots" / f"{sh['id']}.hash"
        hsh = _shot_hash(name, sh, s)
        stale = not mp4.exists() or not hf.exists() or hf.read_text().strip() != hsh
        if (only is None and stale) or (only is not None and (sh["id"] in only or not mp4.exists())):
            done.append(shot_render(name, sh["id"])); hf.write_text(hsh)
        else:
            skipped.append(sh["id"])
    lst = d / "build" / "shots" / "concat.txt"
    lst.write_text("".join(f"file '{(d / 'build' / 'shots' / (sh['id'] + '.mp4')).resolve()}'\n" for sh in s["shots"]))
    pic = d / "build" / "picture.mp4"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps), str(pic)])
    if s.get("post"):  # finishing (plan 1.7): grade, vignette, grain, LUT, before captions so text stays crisp
        vf = post_filters(s["post"])
        if vf:
            graded = d / "build" / "picture_post.mp4"
            _run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(graded)])
            pic = graded
    if s.get("captions", True):
        # one caption pass over the joined picture, so every renderer gets the same word-timed captions
        from .captions import make_ass
        ass = d / "build" / "captions.ass"
        cs = dict(s.get("caption_style") or {})
        if s.get("brand"):  # brand caption colours unless the film overrides them
            b = _brand_kit(s) or {}; pal = b.get("palette", {}); bc = b.get("captions", {})
            res = lambda v: pal.get(v, v) if isinstance(v, str) else v
            for k in ("highlight", "outline", "text"):
                if bc.get(k) and k not in cs:
                    cs[k] = res(bc[k])
        from .research import labels_for
        ctm = _cut_timing(s, _json(d / "timing.json", {}), s.get("caption_lines"))
        ass.write_text(make_ass(ctm, s.get("size", [1080, 1920]), labels=labels_for(d, ctm.get("lines", [])), **cs))   # honest labels (WP-05)
        capd = d / "build" / "picture_cap.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-vf", f"subtitles={ass.relative_to(ROOT)}:fontsdir=engine/fonts",
              "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(capd)])
        pic = capd
    # sound cues: a soft whoosh on every cut plus any cues the shots declare
    cues = [{"t": sh["start"], "type": "whoosh", "gain": 0.7} for sh in s["shots"][1:]]
    for sh in s["shots"]:
        cues += [{"t": c["t"], "type": c["type"], "gain": c.get("gain", 1), **({"dur": c["dur"]} if c.get("dur") else {})} for c in sh.get("cues", [])]
    if s.get("foley"):  # automatic foley from the motion (plan 2.7)
        page = _player_page(name)
        r = subprocess.run(["node", "tools/foley.mjs", str(page)], cwd=ROOT, capture_output=True, text=True, timeout=1800)
        if r.returncode == 0 and r.stdout.strip():
            cues += json.loads(r.stdout.strip().splitlines()[-1])
    if s.get("timewarp"):  # the sound-off cut runs on its own clock
        cues = [{**c, "t": round(_warp(s["timewarp"], c["t"], inverse=True), 3),
                 **({"dur": round(_warp(s["timewarp"], c["t"] + c["dur"], inverse=True) - _warp(s["timewarp"], c["t"], inverse=True), 3)} if c.get("dur") else {})} for c in cues]
    (d / "build" / "cues.json").write_text(json.dumps(sorted(cues, key=lambda c: c["t"])))
    total = _warp(s.get("timewarp"), s["shots"][-1]["end"], inverse=True)
    score = _json(d / "score.json", {}); score["length_s"] = total; (d / "score.json").write_text(json.dumps(score, indent=1))
    _run([PY, "engine/audio.py", f"films/{name}"])
    final = d / "build" / "final.mp4"
    M = _json(ROOT / "dbe" / "profiles.json")["master"]
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-i", str(d / "build" / "mix.wav"), "-map", "0:v", "-map", "1:a",
          "-c:v", M["vcodec"], "-profile:v", M["profile"], "-preset", M["preset"], "-crf", str(M["crf"]), "-pix_fmt", M["pix_fmt"],
          "-c:a", M["acodec"], "-ar", str(M["ar"]), "-b:a", M["ab"], "-af", "apad", "-t", f"{total:.3f}",
          *(["-movflags", "+faststart"] if M.get("faststart") else []), str(final)])
    # sidecar subtitles for platforms that take caption files
    from .captions import make_srt, make_vtt
    tm = _cut_timing(s, _json(d / "timing.json", {}))
    (d / "build" / "captions.srt").write_text(make_srt(tm)); (d / "build" / "captions.vtt").write_text(make_vtt(tm))
    qa = qa_run(name)
    mb = final.stat().st_size / 1e6
    if s.get("soundoff") and not s.get("timewarp"):  # every film ships a voiced cut and a bubble-only cut (plan 2.13)
        so = film_soundoff(name, **(s["soundoff"] if isinstance(s["soundoff"], dict) else {}))
        qa = {**qa, "soundoff": {k: so.get(k) for k in ("final", "qa", "stretched_lines", "length_s")}}
    return {"rendered": done, "unchanged": skipped, "final": str(final.relative_to(ROOT)), "size_mb": round(mb, 1), "under_cap": mb <= M.get("max_mb", 100),
            "subtitles": ["build/captions.srt", "build/captions.vtt"], "qa": qa.get("checks"), "layout_advisory": qa.get("layout_advisory_failures"), "lint": qa.get("lint"),
            **({"soundoff": qa["soundoff"]} if qa.get("soundoff") else {})}


@command("qa.run", name=("string", "film"), layout=("boolean", "also run the measured layout checks (frame fill, safe zones, type size, reading time, seams, cold open, mix)", True))
def qa_run(name, layout=True):
    """Run the measured quality bar (size, fps, stills, loudness, true peak, fact tracing), the layout checks, and
    write contact sheets. Layout checks fail the film only when shots.json "qa": {"enforce": [...]} lists them."""
    _film(name)
    r = subprocess.run([PY, "engine/qa.py", f"films/{name}"], cwd=ROOT, capture_output=True, text=True)
    try:
        rep = json.loads(r.stdout)
    except Exception:
        return {"error": (r.stderr or r.stdout)[-800:]}
    # lip-sync cross-check (plan 2.2): every speaker's mouths against their own voice (lag and agreement)
    ls = subprocess.run([PY, "dbe/lipsync_qa.py", f"films/{name}"], cwd=ROOT, capture_output=True, text=True)
    try:
        rep["lipsync"] = json.loads(ls.stdout)
        if not rep["lipsync"].get("skipped"):
            rep.setdefault("checks", {})["lipsync"] = rep["lipsync"]["ok"]
    except Exception:
        rep["lipsync"] = {"error": (ls.stderr or ls.stdout)[-400:]}
    if layout and (FILMS / name / "shots.json").exists():
        from . import layout_qa
        lay = layout_qa.run(FILMS / name, page=_player_page(name))
        rep["layout"] = lay
        for k in lay["enforced"]:
            rep["checks"][f"layout:{k}"] = lay["checks"].get(k, True)
        rep["layout_advisory_failures"] = lay["advisory_failures"]
        # visual lint (plan 2.8): advisory unless shots.json "qa": {"enforce": ["lint"]}, which fails the film on lint errors
        li = film_lint(name)
        if "issues" in li:
            rep["lint"] = li["summary"]
            if "lint" in ((_json(FILMS / name / "shots.json", {}).get("qa") or {}).get("enforce") or []):
                rep["checks"]["lint"] = li["summary"]["error"] == 0
        (FILMS / name / "build" / "qa.json").write_text(json.dumps(rep, indent=1))
    return rep


# ---------------- acting from prose, gags, rig abilities (plans 2.4, 2.11, 2.12) ----------------
DIRECTED_FIELDS = ("look", "emotion", "blinks", "place")


def _clip_lib(template, puppet=None):
    lib = _json(ROOT / "puppet" / "clips" / f"{template}.json", {"clips": {}})
    if puppet and puppet.get("clips"):   # v0.7: the character's own clips count as its abilities too
        lib = {**lib, "clips": {**lib.get("clips", {}), **puppet["clips"]}}
    return lib


@command("acting.direct", name=("string", "film"), text=("string", "directions in plain English (default: the script lines' and shots' \"direction\" fields)", ""),
         shot=("string", "shot id for text (default: the shot each direction falls in)", ""))
def acting_direct(name, text="", shot=""):
    """Acting from prose (plans 2.4, 2.11): "Momo is nervous and glances at Ravi", "When Ravi says 'telescope', Momo
    does a double take", "After her line Priya shrugs, then nods slowly". Each sentence becomes clips, emotion, gaze,
    blinks, moves or a gag (double take, long stare, slow burn, deadpan, button, rule of three) on the right
    character at the right moment, written line-relative into shots.json and tagged so directing again replaces it.
    Reports how each sentence was read and anything it could not stage."""
    from . import director as DR
    d = _film(name); raw = _json(d / "shots.json"); res = _shots(name); tm = _json(d / "timing.json", {}); lines = tm.get("lines", [])
    script = _json(d / "script.json", {})
    jobs = []   # (shot index, line id, text)
    if text:
        si = next((i for i, x in enumerate(res["shots"]) if x["id"] == shot), 0) if shot else 0
        jobs.append((si, None, text))
    else:
        for i, sh in enumerate(raw["shots"]):
            if sh.get("direction"):
                jobs.append((i, None, sh["direction"]))
        for sl in script.get("lines", []):
            if sl.get("direction"):
                ln = next((l for l in lines if l["id"] == sl["id"]), None)
                if ln:
                    si = next((i for i, x in enumerate(res["shots"]) if x["start"] - 0.01 <= ln["start"] < x["end"]), 0)
                    jobs.append((si, sl["id"], sl["direction"]))
    # undo earlier directing
    for sh in raw["shots"]:
        for c in sh.get("cast") or []:
            tl = c.get("timeline") or {}
            if "undirected" in tl:
                for k, v in tl.pop("undirected").items():
                    if v is None:
                        tl.pop(k, None)
                    else:
                        tl[k] = v
                if "place_undirected" in c:
                    c["place"] = c.pop("place_undirected")
            if tl.get("clips"):
                tl["clips"] = [k for k in tl["clips"] if not k.get("directed")]
    report = []
    for si, lid, txt in sorted(jobs, key=lambda j: (j[0], [l["id"] for l in lines].index(j[1]) if j[1] in [l["id"] for l in lines] else -1)):
        ctx = DR.Ctx(res["shots"][si], lines, lid); sh = raw["shots"][si]
        for sent in [x for x in re.split(r"(?<=[.!?;])\s+|\s+(?=then\b)", txt) if x.strip()]:
            acts = DR.parse(ctx, sent)
            edits, end = DR.compile_actions(ctx, acts, sent)
            if end is not None:
                ctx.cursor = round(end, 3)
                for a_ in acts:
                    if a_.get("who"):
                        ctx.cursors[a_["who"]] = round(end, 3)
            for ci, E in edits.items():
                c = sh["cast"][ci]; tl = c.setdefault("timeline", {})
                if "undirected" not in tl:
                    tl["undirected"] = {k: (json.loads(json.dumps(tl[k])) if k in tl else None) for k in DIRECTED_FIELDS if k != "place"}
                for k in E.get("clips", []):
                    tl.setdefault("clips", []).append({**k, "directed": True})
                if E.get("look"):
                    tl["look"] = (tl.get("look") or []) + E["look"]; tl["look_manual"] = True
                if E.get("emotion"):
                    tl["emotion"] = (tl.get("emotion") or []) + E["emotion"]
                if E.get("blinks"):
                    tl["blinks"] = sorted(set((tl.get("blinks") or []) + E["blinks"]))
                for mv in E.get("place", []):
                    if "place_undirected" not in c:
                        c["place_undirected"] = json.loads(json.dumps(c.get("place")))
                    pl = c.get("place")
                    keys = pl if isinstance(pl, list) else [[0, dict(pl or {"x": mv["from"], "y": 1500})]]
                    last = dict(keys[-1][1])
                    keys = keys + [[mv["t0"], {**last, "x": mv["from"]}], [mv["t1"], {**last, "x": mv["to"]}]]
                    c["place"] = keys
            report.append({"shot": sh["id"], "line": lid, "sentence": sent.strip(),
                           "read": [{k: v for k, v in a.items() if k in ("who", "when", "kind", "clip", "emotion", "gag", "target", "manner", "t", "error", "text")} for a in acts]})
    # keys sorted by time (line-relative keys sort by their resolved time)
    for i, sh in enumerate(raw["shots"]):
        for c in sh.get("cast") or []:
            tl = c.get("timeline") or {}
            for k in ("look", "emotion"):
                if tl.get(k):
                    rv = resolve_times({"k": tl[k]}, tm)["k"]
                    tl[k] = [x for _, x in sorted(zip([r[0] for r in rv], tl[k]), key=lambda z: z[0])]
            if isinstance(c.get("place"), list):
                rv = resolve_times({"k": c["place"]}, tm)["k"]
                c["place"] = [x for _, x in sorted(zip([r[0] for r in rv], c["place"]), key=lambda z: z[0])]
    (d / "shots.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    unstaged = [r["sentence"] for r in report if any(a.get("kind") in ("unknown", None) or a.get("error") for a in r["read"])]
    return {"directions": len(report), "staged": report, "not_understood": unstaged}


@command("puppet.abilities", puppet=("string", "puppet file"))
def puppet_abilities(puppet):
    """Rig ability inventory (plan 2.12): what this character does for free (clips whose parts it has, emotions whose
    mouths and brows are drawn, glances, blinks, lip-sync, turn, tail) and what each costly move would need drawn."""
    from . import director as DR
    p = _json(ROOT / puppet)
    return DR.abilities(p, _clip_lib(p.get("template", "humanoid"), p))


@command("script.rigcheck", name=("string", "film"))
def script_rigcheck(name):
    """Rig-aware writing (plan 2.12): read every direction in the film (script lines and shots), work out what each
    character is asked to do, and list per character the moves that are free and exactly which drawings the rest
    would need. A script written within the rigs returns no drawing requests."""
    from . import director as DR
    d = _film(name); raw = _json(d / "shots.json"); res = _shots(name); tm = _json(d / "timing.json", {}); lines = tm.get("lines", [])
    script = _json(d / "script.json", {})
    jobs = [(i, None, sh["direction"]) for i, sh in enumerate(raw["shots"]) if sh.get("direction")]
    for sl in script.get("lines", []):
        ln = next((l for l in lines if l["id"] == sl["id"]), None)
        if sl.get("direction") and ln:
            jobs.append((next((i for i, x in enumerate(res["shots"]) if x["start"] - 0.01 <= ln["start"] < x["end"]), 0), sl["id"], sl["direction"]))
    per = {}
    for si, lid, txt in jobs:
        ctx = DR.Ctx(res["shots"][si], lines, lid)
        for sent in [x for x in re.split(r"(?<=[.!?;])\s+|\s+(?=then\b)", txt) if x.strip()]:
            for a in DR.parse(ctx, sent):
                if a.get("error") or a.get("kind") == "unknown":
                    continue
                c = res["shots"][si]["cast"][ctx.cast[a["who"]]]; p = _json(ROOT / c["puppet"]); lib = _clip_lib(p.get("template", "humanoid"), p)
                need = DR.needs_of(a, p, lib)
                e = per.setdefault(a["who"], {"puppet": c["puppet"], "free": [], "needs_drawings": {}})
                label = a.get("clip") or a.get("gag") or a.get("emotion") or a["kind"]
                if need:
                    for n in need:
                        e["needs_drawings"].setdefault(n, []).append(sent.strip())
                elif label not in e["free"]:
                    e["free"].append(label)
    return {"characters": per, "drawings_needed": sum(len(v["needs_drawings"]) for v in per.values()),
            "ok": all(not v["needs_drawings"] for v in per.values())}


# ---------------- data-bound visuals and original analysis (plan 2.17) ----------------
@command("film.data", name=("string", "film"), refresh=("boolean", "download every source again (default: use the cached copy)", False),
         revoice=("boolean", "re-voice the lines whose bound numbers changed", False), render=("boolean", "re-render what changed (incremental)", False))
def film_data(name, refresh=False, revoice=False, render=False):
    """Run the film's analysis (plan 2.17): fetch each source in analysis/sources.json once into analysis/cache/
    (url, terms, version, access date and sha256 recorded), run analysis/*.py in order with DBE_PY (they read the cache
    and write data.json), then report what the new data changes: which shots' pictures (charts, bound text) and which
    narrated lines (bound numbers). With revoice/render it re-voices those lines and re-renders only those shots."""
    import datetime
    import hashlib
    import urllib.request
    d = _film(name); an = d / "analysis"
    if not an.exists():
        raise FileNotFoundError("no analysis/ folder (scripts that write data.json, sources.json for inputs)")
    cache = an / "cache"; cache.mkdir(exist_ok=True)
    srcs = _json(an / "sources.json", {"sources": []})
    for src in srcs.get("sources", []):
        f = cache / src["file"]
        if src.get("url") and (refresh or not f.exists()):
            with urllib.request.urlopen(src["url"], timeout=120) as r:
                f.write_bytes(r.read())
            src["accessed"] = datetime.date.today().isoformat()
        if f.exists():
            src["sha256"] = hashlib.sha256(f.read_bytes()).hexdigest()
    (an / "sources.json").write_text(json.dumps(srcs, indent=1, ensure_ascii=False))
    old_data = _json(d / "data.json", {})
    def hashes():
        try:
            res = _shots(name); return {sh["id"]: _shot_hash(name, sh, res) for sh in res["shots"]}
        except (ValueError, KeyError, FileNotFoundError):   # no voice yet (line-relative times unresolved) or data missing
            return {}
    old_hash = hashes()
    from .databind import bind_text
    sc = _json(d / "script.json", {})
    old_lines = {ln["id"]: bind_text(ln["text"], old_data) for ln in sc.get("lines", []) if "{{" in ln.get("text", "")} if old_data else {}
    ran = []
    for py in sorted(an.glob("*.py")):
        subprocess.run([PY, py.name], cwd=an, check=True, capture_output=True, text=True, timeout=1800)
        ran.append(py.name)
    data = _json(d / "data.json", {})
    data["_provenance"] = {"scripts": {p: hashlib.sha256((an / p).read_bytes()).hexdigest()[:16] for p in ran},
                           "sources": [{k: v for k, v in x.items() if k in ("id", "url", "terms", "version", "accessed", "sha256", "file")} for x in srcs.get("sources", [])]}
    (d / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    new_hash = hashes()
    shots_changed = [k for k in new_hash if old_hash.get(k) != new_hash[k]]
    lines_changed = [{"line": ln["id"], "was": old_lines.get(ln["id"]), "now": bind_text(ln["text"], data)}
                     for ln in sc.get("lines", []) if "{{" in ln.get("text", "") and old_lines.get(ln["id"]) != bind_text(ln["text"], data)]
    changed_keys = sorted(k for k in set(data) | set(old_data) if not k.startswith("_") and data.get(k) != old_data.get(k))
    out = {"ran": ran, "data_keys_changed": changed_keys, "shots_to_rerender": shots_changed, "lines_to_revoice": lines_changed}
    if revoice and lines_changed:
        voice_build(name); out["revoiced"] = True
        if any(c.get("speaker") for sh in _shots(name, resolve=False)["shots"] for c in sh.get("cast", [])):
            acting_plan(name)
    if render:
        r = film_render(name); out["rendered"] = r.get("rendered"); out["unchanged"] = r.get("unchanged"); out["qa"] = r.get("qa")
    return out


# ---------------- Studio timeline (plan 3.1) ----------------
@command("film.preview", name=("string", "film"))
def film_preview(name):
    """Write the film's player page (every frame is a pure function of time) for live preview and scrubbing."""
    return {"page": str(_player_page(name).relative_to(ROOT))}


@command("timeline.get", name=("string", "film"))
def timeline_get(name):
    """Everything the Studio timeline draws: per shot its resolved start/end, set and cast; per cast member the clip
    layers (raw start as written, resolved start and end, length from the clip library), emotion and gaze keys; the
    dialogue lines with words; the film length."""
    d = _film(name); raw = _json(d / "shots.json"); res = _shots(name); tm = _json(d / "timing.json", {})
    shots = []
    for rs, rr in zip(raw["shots"], res["shots"]):
        cast = []
        for ci, (rc, cc) in enumerate(zip(rs.get("cast") or [], rr.get("cast") or [])):
            p = _json(ROOT / cc["puppet"]); lib = {**_json(ROOT / "puppet" / "clips" / f"{p.get('template', 'humanoid')}.json", {"clips": {}})["clips"], **(p.get("clips") or {})}
            clips = []
            for ki, (rk, kk) in enumerate(zip((rc.get("timeline") or {}).get("clips", []), (cc.get("timeline") or {}).get("clips", []))):
                cl = lib.get(kk.get("clip")) or {}
                dur = (cl.get("duration") or 1.0) / (kk.get("speed") or 1)
                end = kk.get("end") if kk.get("end") is not None else (rr["end"] if cl.get("loop") else kk.get("start", 0) + dur)
                clips.append({"i": ki, "clip": kk.get("clip"), "start": kk.get("start", 0), "end": round(min(end, rr["end"]), 3), "raw_start": rk.get("start", 0),
                              "raw_end": rk.get("end"), "loop": bool(cl.get("loop")), "additive": bool(kk.get("additive")), "auto": bool(kk.get("auto")),
                              "directed": bool(kk.get("directed")), "weight": kk.get("weight", 1), "speed": kk.get("speed", 1), "gain": kk.get("gain", 1)})
            tl = cc.get("timeline") or {}
            cast.append({"i": ci, "who": cc.get("speaker") or p.get("name") or f"cast {ci}", "puppet": cc["puppet"], "clips": clips,
                         "emotion": tl.get("emotion") or [], "look": tl.get("look") or []})
        shots.append({"id": rr["id"], "start": rr["start"], "end": rr["end"], "set": rr.get("set", "plain"), "renderer": rr.get("renderer", "svg"), "cast": cast})
    return {"film": name, "length": res["shots"][-1]["end"], "fps": res.get("fps", 30), "shots": shots,
            "lines": [{k: l[k] for k in ("id", "speaker", "text", "start", "end", "words") if k in l} for l in tm.get("lines", [])],
            "clip_names": sorted({n for t in ("humanoid", "doodle") for n in _json(ROOT / "puppet" / "clips" / f"{t}.json", {"clips": {}})["clips"]})}


def _retime(raw_value, new_t, timing):
    """a new time in seconds, written the way the old one was: line-relative stays line-relative (same line, same
    edge), so re-voicing still carries the edit; plain seconds stay seconds"""
    if isinstance(raw_value, str):
        m = _LINE_T.match(raw_value)
        L = {l["id"]: l for l in (timing or {}).get("lines", [])}
        if m and m.group(1) in L:
            lid, edge = m.group(1), m.group(2)
            near = lambda l: l["start"] - 0.5 <= new_t <= l["end"] + 1.0
            if not near(L[lid]):   # moved away from its line: anchor to the line it now sits by
                cand = [l for l in L.values() if near(l)]
                if cand:
                    l = min(cand, key=lambda l: abs(new_t - l["start"])); lid, edge = l["id"], "start" if new_t <= l["end"] else "end"
            off = round(new_t - L[lid][edge], 3)
            return f"{lid}.{edge}{'+' if off >= 0 else '-'}{abs(off)}"
    return round(max(0.0, new_t), 3)


@command("timeline.edit", name=("string", "film"), op=("string", "move_clip | resize_clip | add_clip | delete_clip | set_clip"),
         shot=("string", "shot id"), cast=("integer", "cast index in the shot"), index=("integer", "clip layer index (move, resize, delete)", -1),
         start=("number", "new start in film seconds (move, add)", None), end=("number", "new end in film seconds (resize; null = the clip's own length)", None),
         clip=("string", "clip name (add)", ""), anchor=("string", "for add: a line id to anchor the start to (line-relative)", ""),
         props=("object", "set_clip: speed, gain, weight, additive", None))
def timeline_edit(name, op, shot, cast, index=-1, start=None, end=None, clip="", anchor="", props=None):
    """One timeline edit from the Studio (plan 3.1), written into shots.json: move a clip layer (its end moves with
    it), resize its end, add a clip at a time (anchored to a line if given, so re-voicing keeps it on the words) or
    delete one. Line-relative times stay line-relative. Returns the clip as stored."""
    d = _film(name); raw = _json(d / "shots.json"); tm = _json(d / "timing.json", {}); res = _shots(name)
    si = next((i for i, x in enumerate(raw["shots"]) if x["id"] == shot), None)
    if si is None:
        raise KeyError(f"no shot {shot}")
    tl = raw["shots"][si]["cast"][cast].setdefault("timeline", {}); clips = tl.setdefault("clips", [])
    rclips = (res["shots"][si]["cast"][cast].get("timeline") or {}).get("clips", [])
    if op == "add":
        op = "add_clip"
    if op == "add_clip":
        if not clip:
            raise ValueError("add_clip needs clip")
        st = _retime(f"{anchor}.start" if anchor else 0.0, float(start), tm) if anchor else round(float(start), 3)
        k = {"clip": clip, "start": st, "weight": 3}
        clips.append(k); stored = k
    else:
        if not 0 <= index < len(clips):
            raise IndexError(f"no clip layer {index}")
        k = clips[index]; rk = rclips[index]
        if op == "move_clip":
            dt = float(start) - float(rk.get("start", 0))
            k["start"] = _retime(k.get("start", 0), float(start), tm)
            if k.get("end") is not None:
                k["end"] = _retime(k["end"], float(rk["end"]) + dt, tm)
        elif op == "resize_clip":
            if end is None:
                k.pop("end", None)
            else:
                k["end"] = _retime(k.get("end") if k.get("end") is not None else k.get("start", 0), max(float(end), float(rk.get("start", 0)) + 0.1), tm)
        elif op == "delete_clip":
            clips.pop(index)
        elif op == "set_clip":
            for kk, vv in (props or {}).items():
                if kk not in ("speed", "gain", "weight", "additive"):
                    raise ValueError(f"set_clip cannot set {kk}")
                k[kk] = vv
        else:
            raise ValueError(f"unknown op {op}")
        k.pop("auto", None)   # a hand edit: the gesture planner keeps it from now on
        stored = None if op == "delete_clip" else k
    (d / "shots.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    _player_page(name)
    return {"stored": stored, "shot": shot, "cast": cast, "op": op}


@command("puppet.save", path=("string", "cast/.../x.puppet.json, or a bare id for cast/drawn/<id>.puppet.json"), puppet=("object", "the puppet"))
def puppet_save(path, puppet):
    """Write a puppet from the Rig Canvas into the project's cast (plan 3.3): checked against the puppet schema,
    only under cast/; a new file is registered in the cast library. Poses and clips made by posing travel with it."""
    import jsonschema
    p = path if path.endswith(".puppet.json") else f"cast/drawn/{re.sub(r'[^a-z0-9_-]', '_', path.lower())}.puppet.json"
    f = (ROOT / p).resolve()
    if not str(f).startswith(str((ROOT / "cast").resolve()) + "/"):
        raise ValueError("puppets are saved under cast/")
    errs = _puppet_errors(puppet)
    if errs:
        raise ValueError("not a valid puppet: " + "; ".join(errs[:5]))
    new = not f.exists(); f.parent.mkdir(parents=True, exist_ok=True)
    puppet.setdefault("meta", {})["cast_path"] = str(f.relative_to(ROOT))
    f.write_text(json.dumps(puppet))
    if new:
        cast_add(str(f.relative_to(ROOT)), f.stem.split(".")[0], (puppet.get("meta") or {}).get("author", "Rig Canvas"), (puppet.get("meta") or {}).get("license", "CC0-1.0"), "drawn in the Rig Canvas", rights="open")
    return {"path": str(f.relative_to(ROOT)), "new": new, "poses": len(puppet.get("poses") or {}), "clips": len(puppet.get("clips") or {})}


# ---------------- review room (plan 3.4) ----------------
def _review(name):
    return _json(_film(name) / "review.json", {"notes": []})


@command("review.add", name=("string", "film"), frame=("integer", "frame number (at the film's fps)"), text=("string", "the note, in plain English"),
         who=("string", "reviewer", "director"))
def review_add(name, frame, text, who="director"):
    """Pin a review note to a frame (plan 3.4), e.g. "raise the arm earlier" on frame 120. Stored in review.json."""
    rv = _review(name); fps = _shots(name).get("fps", 30)
    note = {"id": f"n{len(rv['notes']) + 1}", "frame": int(frame), "t": round(frame / fps, 3), "text": text, "who": who, "status": "open"}
    rv["notes"].append(note); (_film(name) / "review.json").write_text(json.dumps(rv, indent=1, ensure_ascii=False))
    return note


@command("review.list", name=("string", "film"))
def review_list(name):
    """All review notes with their status (open, verified, needs_human) and what was done."""
    return _review(name)


@command("review.fix", name=("string", "film"), id=("string", "note id (default: every open note)", ""))
def review_fix(name, id=""):
    """Turn review notes into data edits and check them (plan 3.4): read the note (verb, amount, part, character),
    find the clip making that motion at that frame, edit it (timeline.edit), re-render, then the critic measures the
    part's motion before and after over the same window (an earlier move must start sooner by most of the asked
    amount; bigger must travel further; ...) and re-runs QA. Verified notes close; others are reverted and marked
    needs_human with the reason. Before/after stills go to build/review/."""
    from . import review as RV
    d = _film(name); rv = _review(name); out = []
    todo = [n for n in rv["notes"] if (n["id"] == id if id else n["status"] == "open")]
    for n in todo:
        tlg = timeline_get(name); t = n["t"]
        shot = next((s_ for s_ in tlg["shots"] if s_["start"] <= t < s_["end"]), tlg["shots"][-1])
        intent = RV.interpret(n["text"], [c["who"] for c in shot["cast"]])
        n["intent"] = intent
        if not intent["verb"]:
            n.update(status="needs_human", reason="could not tell what to change (earlier, later, faster, slower, bigger, smaller, longer, shorter, remove)"); out.append(n); continue
        libs = {c["i"]: {**_json(ROOT / "puppet" / "clips" / f"{_json(ROOT / c['puppet']).get('template', 'humanoid')}.json", {"clips": {}})["clips"], **(_json(ROOT / c["puppet"]).get("clips") or {})} for c in shot["cast"]}
        hit = RV.locate(intent, shot, t, libs)
        if not hit:
            n.update(status="needs_human", reason="no clip near that frame makes that motion"); out.append(n); continue
        ci, ki, watch, why = hit
        k = next(x for x in next(c for c in shot["cast"] if c["i"] == ci)["clips"] if x["i"] == ki)
        edit, amount = RV.plan_edit(intent, k, k["end"] - k["start"], libs[ci].get(k["clip"]))
        page = _player_page(name)
        w0, w1 = max(shot["start"], min(k["start"], (edit or {}).get("start", k["start"])) - 0.6), min(shot["end"], k["end"] + 1.2 + (amount if intent["verb"] in ("later", "longer") and amount else 0))
        probe = lambda: json.loads(_run(["node", "tools/probe.mjs", str(page), str(ci), watch, f"{w0:.3f}", f"{w1:.3f}"], timeout=600)[-1])
        before = probe(); qa_before = (_json(d / "build" / "qa.json", {}).get("checks") or {})
        raw_before = (d / "shots.json").read_text()
        timeline_edit(name, shot=shot["id"], cast=ci, index=ki, **edit)
        page = _player_page(name); after = probe()
        ok, msg, mb, ma = RV.verify(intent, amount or 0, before, after)
        n.update(target=why, watch=watch, edit=edit, measured={"before": mb, "after": ma}, check=msg)
        if ok:
            r = film_render(name); qa_after = r.get("qa") or {}
            worse = [k_ for k_, v in qa_after.items() if v is False and qa_before.get(k_) is not False]
            if worse:
                (d / "shots.json").write_text(raw_before); film_render(name)
                n.update(status="needs_human", reason=f"the edit broke QA ({', '.join(worse)}); reverted")
            else:
                sdir = d / "build" / "review"; sdir.mkdir(parents=True, exist_ok=True)
                n.update(status="verified", reviewer="critic: measured motion + QA")
                try:   # after-still at the note's frame
                    _run(["node", "tools/board_stills.mjs", str(page), str(sdir), "360", str(t)], timeout=300); (sdir / "still_0.png").rename(sdir / f"{n['id']}_after.png")
                    n["still_after"] = str((sdir / f"{n['id']}_after.png").relative_to(ROOT))
                except Exception:
                    pass
        else:
            (d / "shots.json").write_text(raw_before); _player_page(name)
            n.update(status="needs_human", reason="the edit did not change the motion as asked: " + msg + " (reverted)")
        out.append(n)
    (d / "review.json").write_text(json.dumps(rv, indent=1, ensure_ascii=False))
    return {"fixed": [n["id"] for n in out if n["status"] == "verified"], "needs_human": [n["id"] for n in out if n["status"] == "needs_human"], "notes": out}


# ---------------- act it out (plan 3.5) ----------------
@command("actout.clip", video=("string", "the take: a phone or webcam video (any format ffmpeg reads), path from the project root or absolute"),
         puppet=("string", "character file, cast/.../x.puppet.json"), name=("string", "name of the new clip on that character"),
         start=("number", "seconds into the video where the take starts", 0), duration=("number", "seconds to use (0 = to the end, at most 20)", 0),
         mirror=("boolean", "flip the take first (selfie and webcam previews are mirrored)", False),
         face=("string", "upper (eyes, brows, gaze; the mouth stays with lip-sync, the default) | all (the take's mouth too: for silent reactions, since it overrides lip-sync while the clip plays) | none", "upper"),
         root=("string", "move (the take's travel, planted feet kept on the ground) | in_place", "move"),
         arms=("string", "angles (joint angles copied: natural silhouettes, the default) | reach (hands placed where the take's hands are, scaled to this body: keeps claps and hands-on-body contacts)", "angles"),
         tolerance=("number", "largest angle error the reduced keys may have, in degrees", 1.5),
         save=("boolean", "write the clip into the character file (otherwise a copy under out/actout/)", True))
def actout_clip(video, puppet, name, start=0, duration=0, mirror=False, face="upper", root="move", arms="angles", tolerance=1.5, save=True):
    """Act it out (plan 3.5): a short take of a person becomes an action clip on a character. MediaPipe Pose and
    Face Landmarker read body points and face blendshapes per frame; they are retargeted onto the character's own
    rest pose (joint angles, the root's travel with planted feet held on the ground, foot contacts, mouth, eye and
    brow drawings, gaze), and keys are reduced against the eased curve the player will actually play. Parts the take
    cannot see (legs in a waist-up webcam take) are left out, so idle or other clips fill them. The clip is saved in
    the character (puppet format v0.7 clips), so shots, the bake and every exporter play it by name. Also writes
    out/actout/<name>_sheet.png: frames of the take above the character at the same moments."""
    import time
    from . import actout as AO
    t0 = time.time()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", name):
        raise ValueError("clip names are letters, digits and _ (starting with a letter)")
    if face not in ("all", "upper", "none") or root not in ("move", "in_place") or arms not in ("reach", "angles"):
        raise ValueError("face is all, upper or none; root is move or in_place; arms is reach or angles")
    vid = Path(video) if Path(video).is_absolute() else ROOT / video
    if not vid.is_file():
        raise FileNotFoundError(f"no video at {video}")
    pfile = (ROOT / puppet).resolve()
    if not pfile.is_file():
        raise FileNotFoundError(f"no puppet at {puppet}")
    pz = _json(pfile)
    dur = min(float(duration) or 20.0, 20.0)
    cache = ROOT / "out" / "actout"; cache.mkdir(parents=True, exist_ok=True)
    key = AO.cache_key(vid, start=float(start), duration=dur, mirror=bool(mirror), face=face != "none", fps=30)
    kpf = cache / f"{key}.keypoints.json"
    cached = kpf.exists()
    kp = _json(kpf) if cached else AO.detect(vid, fps=30, start=float(start), duration=dur, mirror=bool(mirror), face=face != "none")
    if not cached:
        kpf.write_text(json.dumps(kp))
    clip, rep = AO.retarget(kp, pz, tol=float(tolerance), face=face, root=root, arms=arms)
    clip["source"] = {"take": vid.name, "start": float(start), "seconds": rep["seconds"], "mirror": bool(mirror),
                      "by": "actout.clip (MediaPipe Pose + Face Landmarker, retargeted to this character)"}
    pz.setdefault("clips", {})[name] = clip
    if str(pz.get("version", "0")) < "0.7":
        pz["version"] = "0.7"      # character clips arrived in v0.7
    if save:
        out_path = puppet_save(str(pfile.relative_to(ROOT)), pz)["path"]
    else:
        out_path = str((cache / f"{name}.puppet.json").relative_to(ROOT)); (ROOT / out_path).write_text(json.dumps(pz))
    sheet = _actout_sheet(vid, float(start), bool(mirror), out_path, name, clip["duration"], cache / f"{name}_sheet.png", kp)
    return {"clip": name, "puppet": out_path, "saved": bool(save), "report": rep, "keypoints": str(kpf.relative_to(ROOT)),
            "reused_keypoints": cached, "timing": {**(kp.get("timing") or {}), "total_s": round(time.time() - t0, 1)},
            "sheet": str(sheet.relative_to(ROOT)) if sheet else None}


def _actout_sheet(vid, start, mirror, puppet_rel, clip, dur, out, kp=None, n=6):
    """take frames (top, cropped around the performer) over the character playing the new clip (bottom) at the same
    moments"""
    import tempfile
    from PIL import Image
    tdir = Path(tempfile.mkdtemp(prefix="actout_"))
    times = [round(dur * (i + 0.5) / n, 3) for i in range(n)]
    col, h = 240, 400
    spec = {"size": [col * n, h], "bg": "#f4f3ee", "items": [
        {"puppet": puppet_rel, "x": col * i + col // 2, "y": h - 12, "s": 0.36, "t": t,
         "timeline": {"clips": [{"clip": clip, "start": 0, "fadeIn": 0, "fadeOut": 0}], "blink": False, "springs": False}} for i, t in enumerate(times)]}
    (tdir / "spec.json").write_text(json.dumps(spec))
    try:
        _run(["node", "tools/pose_still.mjs", str(tdir / "spec.json"), str(tdir / "pz.png")], timeout=300)
    except Exception:
        return None
    sheet = Image.new("RGB", (col * n, h * 2), "#f4f3ee"); sheet.paste(Image.open(tdir / "pz.png").convert("RGB"), (0, h))
    for i, t in enumerate(times):
        f = tdir / f"v{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start + t:.3f}", "-i", str(vid), "-frames:v", "1"] + (["-vf", "hflip"] if mirror else []) + [str(f)], check=False)
        if not f.exists():
            continue
        im = Image.open(f).convert("RGB")
        fr = (kp or {}).get("frames") or []
        pose = fr[min(len(fr) - 1, int(round(t * kp["fps"])))].get("pose") if fr else None
        if pose:   # crop around the performer (keypoints are in the detection frame's pixels)
            k = im.width / kp["size"][0]; xs = [q[0] * k for q in pose]; ys = [q[1] * k for q in pose]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            bh = max((max(ys) - min(ys)) * 1.15, (max(xs) - min(xs)) * 1.2 * h / col, 40)
            bw = bh * col / h
            box = Image.new("RGB", (int(bw), int(bh)), "#f4f3ee"); box.paste(im, (-int(cx - bw / 2), -int(cy - bh / 2))); im = box
        im.thumbnail((col, h))
        sheet.paste(im, (col * i + (col - im.width) // 2, (h - im.height) // 2))
    sheet.save(out); shutil.rmtree(tdir, ignore_errors=True)
    return out


# ---------------- phone-first creator flow (plan 3.6) ----------------
DOODLES = ROOT / "out" / "doodle"


def _doodle_dir(id):
    if not re.fullmatch(r"[0-9a-f]{12}", id or ""):
        raise ValueError("not a doodle id")
    d = DOODLES / id
    if not d.is_dir():
        raise FileNotFoundError(f"no doodle {id}")
    return d


def _doodle_build(d, spec):
    spec = {**spec, "photo": str(d / "photo.png")}
    spec.pop("found", None)
    (d / "spec.json").write_text(json.dumps(spec))
    out = json.loads(_run([PY, "dbe/ink.py", str(d / "spec.json"), str(d / "doodle.puppet.json")])[-1])
    return out


@command("doodle.snap", photo=("string", "a phone photo of a pen doodle (path from the project root or absolute; /upload puts one in out/actout/takes/)"),
         name=("string", "the character's name", "Doodle"))
def doodle_snap(photo, name="Doodle"):
    """Phone-first creator flow (plan 3.6), step 1: a photo of a doodle becomes a talking doodle puppet with suggested
    cuts and pivots. The photo is turned upright, cropped to the ink and scaled; closed loops give the head and body
    (or one blob), marks inside the head the eyes (blinking by squash) and mouth (talking shapes drawn to match in the
    same line), strokes leaving the body's sides the arms and a tail, marks above the body ride with the head. Returns
    the doodle id, the ink spec (polygons and pivots to confirm or move, then doodle.cut) and what was found, with
    reasons and notes for anything it could not find."""
    import hashlib
    from . import autorig as AR
    src = Path(photo) if Path(photo).is_absolute() else ROOT / photo
    if not src.is_file():
        raise FileNotFoundError(f"no photo at {photo}")
    id = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
    d = DOODLES / id; d.mkdir(parents=True, exist_ok=True)
    info = AR.prepare(src, d / "photo.png")
    spec = AR.suggest(str(d / "photo.png"), name=name)
    built = _doodle_build(d, spec)
    rel = lambda p: str(p.relative_to(ROOT))
    return {"id": id, "photo": rel(d / "photo.png"), "size": info["size"], "puppet": rel(d / "doodle.puppet.json"),
            "found": spec["found"], "spec": {k: v for k, v in spec.items() if k != "found"}, "built": built}


@command("doodle.cut", id=("string", "doodle id from doodle.snap"), spec=("object", "the ink spec with confirmed or moved cuts and pivots"))
def doodle_cut(id, spec):
    """Step 2: rebuild a doodle puppet from confirmed cuts and pivots (parts' polygons and pivots, swaps' boxes;
    remove a part to leave it on the body)."""
    d = _doodle_dir(id)
    for pid, ps in (spec.get("parts") or {}).items():
        if pid not in ("head", "arm_L", "arm_R", "tail", "body"):
            raise ValueError(f"doodle parts are head, arm_L, arm_R, tail (and body as the rest), not {pid}")
        if "pivot" not in ps or ("poly" in ps and len(ps["poly"]) < 3):
            raise ValueError(f"{pid} needs a pivot and a polygon of 3 or more points")
    return {"id": id, "puppet": str((d / "doodle.puppet.json").relative_to(ROOT)), "built": _doodle_build(d, spec)}


@command("doodle.say", puppet=("string", "puppet file (a doodle from doodle.snap, or any character)"), text=("string", "the line to say"),
         voice=("string", "a clean voice (Kokoro voices are clean)", "kokoro:af_heart"))
def doodle_say(puppet, text, voice="kokoro:af_heart"):
    """Step 3: the character says a line. The line is voiced in a separate process (Kokoro) with lip-sync cues from
    the model's own phoneme timings, and a short acting timeline is made for it: idle, a hop on an exclamation, a
    wave on a greeting, head and body beats while talking, blinks. Returns the audio file and the timeline, which the
    page plays live (Acting.evaluate with the template's clips)."""
    import hashlib
    reg = _voice_registry()
    if reg.get(voice, {}).get("status") != "clean":
        raise PermissionError(f"{voice} is not a clean voice")
    if not text.strip() or len(text) > 300:
        raise ValueError("say one line (up to 300 characters)")
    pz = _json(ROOT / puppet)
    if pz is None:
        raise FileNotFoundError(f"no puppet at {puppet}")
    out = DOODLES / "say"; out.mkdir(parents=True, exist_ok=True)
    wav = out / (hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:16] + ".wav")
    r = json.loads(_run([PY, "engine/say_line.py", text, voice, str(wav), VOICES], timeout=300)[-1])
    dur, lead = r["duration"], 0.35
    tpl = pz.get("template", "humanoid"); low = text.lower().strip()
    clips = [{"clip": "idle", "start": 0}]
    if tpl == "doodle":
        if re.match(r"(hi|hello|hey|hiya|good (morning|afternoon|evening))\b", low):
            clips.append({"clip": "wave_R" if "arm_R" in pz["parts"] else "wave_L", "start": 0.0, "end": lead + 0.9, "fadeIn": 0.1, "fadeOut": 0.2})
        if "!" in text:
            clips.append({"clip": "hop", "start": 0.0, "additive": True, "fadeIn": 0, "fadeOut": 0})
        clips.append({"clip": "talk", "start": lead, "end": lead + dur, "weight": 0.8, "fadeIn": 0.1, "fadeOut": 0.2})
    else:
        if re.match(r"(hi|hello|hey)\b", low):
            clips.append({"clip": "wave_R", "start": 0.0, "end": lead + 1.2, "weight": 3})
        clips.append({"clip": "talk_beat", "start": lead, "end": lead + dur, "weight": 1})
    tl = {"clips": clips, "visemes": [[round(t + lead, 3), sh] for t, sh in r["visemes"]], "blink": True, "springs": False}
    return {"audio": str(wav.relative_to(ROOT)), "lead": lead, "duration": round(lead + dur + 0.6, 2), "timeline": tl, "visemes": len(r["visemes"]), "voice": voice}


@command("doodle.keep", id=("string", "doodle id"), name=("string", "the character's name"), owner=("string", "who drew it (the rights holder)"),
         voice=("string", "the character's voice", "kokoro:af_heart"))
def doodle_keep(id, name, owner, voice="kokoro:af_heart"):
    """Step 4: keep the doodle as a cast member (cast/drawn/<name>.puppet.json, rights: owner), with its voice, so
    films, the Rig Canvas and drawing requests can use it."""
    d = _doodle_dir(id); pz = _json(d / "doodle.puppet.json")
    slug = re.sub(r"[^a-z0-9_-]", "_", name.lower()).strip("_") or "doodle"
    pz["name"] = name; pz.setdefault("meta", {}).update({"author": owner, "license": "LicenseRef-owner", "made": "phone photo, auto cuts (doodle.snap)"})
    path = f"cast/drawn/{slug}.puppet.json"
    f = ROOT / path; f.parent.mkdir(parents=True, exist_ok=True); pz["meta"]["cast_path"] = path
    f.write_text(json.dumps(pz))
    idx = _json(ROOT / "cast" / "index.json", {"puppets": []})
    if not any(p.get("path") == path for p in idx["puppets"]):
        cast_add(path, slug, owner, "LicenseRef-owner", "drawn by the owner; photo cut and rigged by doodle.snap (plan 3.6)", voice={"voice": voice}, rights="owner", owner=owner)
    return {"path": path, "id": slug}


# ---------------- drawing request queue with ghost guides (plan 3.6, E20) ----------------
def _req_puppet(puppet):
    f = (ROOT / puppet).resolve()
    if not (str(f).startswith(str((ROOT / "cast").resolve()) + "/") or str(f).startswith(str(DOODLES.resolve()) + "/")) or not f.is_file():
        raise ValueError("drawing requests are for characters under cast/ or doodles under out/doodle/")
    return f


@command("drawing.requests", puppet=("string", "character file (cast/... or a doodle under out/doodle/)"),
         film=("string", "a film whose directions need drawings from this character (script.rigcheck); empty: every costly move", ""))
def drawing_requests(puppet, film=""):
    """Drawing request queue (plan 3.6, E20): each drawing this character is missing, for a film's directions or for
    its costly moves, becomes a request with the reason and a ghost guide (out/requests/): the character faintly at
    rest on its own artboard, the related drawing it has, and a dashed box where the new one goes. Needs that are
    rigged rather than drawn (pupils, a turn view, chains) are listed for the Rig Canvas. Queue: <puppet>.requests.json."""
    from . import director as DR, drawreq as RQ
    f = _req_puppet(puppet); p = _json(f); rel = str(f.relative_to(ROOT))
    if film:
        ch = next((v for v in script_rigcheck(film)["characters"].values() if v["puppet"] == rel), None)
        needs = (ch or {}).get("needs_drawings", {})
    else:
        needs = {}
        for c in DR.abilities(p, _clip_lib(p.get("template", "humanoid"), p))["costly"]:
            for lbl in c.get("draw", []):
                needs.setdefault(lbl, []).append(c["move"])
    qp = RQ.queue_path(rel); q = _json(qp, {"puppet": rel, "requests": []})
    have = {(r.get("swap"), r.get("shape"), r.get("part"), r.get("what")) for r in q["requests"]}
    for r in RQ.make_requests(p, needs):
        k = (r.get("swap"), r.get("shape"), r.get("part"), r.get("what"))
        if k in have:
            continue
        r["id"] = f"r{len(q['requests']) + 1}"
        if film:
            r["film"] = film
        q["requests"].append(r); have.add(k)
    gdir = ROOT / "out" / "requests" / (f.parent.name if f.name == "doodle.puppet.json" else f.name.split(".")[0]); gdir.mkdir(parents=True, exist_ok=True)
    rest = None
    for r in q["requests"]:
        if r["status"] != "open" or (r.get("ghost") and (ROOT / r["ghost"]).exists()):
            continue
        if rest is None:
            rest = gdir / "rest.png"; (gdir / "rest.json").write_text(json.dumps(RQ.ghost_spec(p, rel)))
            _run(["node", "tools/pose_still.mjs", str(gdir / "rest.json"), str(rest)], timeout=300)
        r["ghost"] = str(RQ.compose_ghost(rest, p, r, gdir / f"{r['id']}.png").relative_to(ROOT))
    qp.write_text(json.dumps(q, indent=1))
    return {**q, "open": sum(r["status"] == "open" for r in q["requests"]), "rig_canvas": sum(r["status"] == "rig_canvas" for r in q["requests"])}


@command("drawing.fulfil", puppet=("string", "character file"), id=("string", "request id"),
         image=("string", "the drawing: made on the ghost guide (same framing), a canvas export or a photo"),
         render=("boolean", "re-render the request's film afterwards", False))
def drawing_fulfil(puppet, id, image, render=False):
    """Slot a drawing into the rig (plan 3.6, E20): ink is lifted from the drawing inside the request's box and stored
    as that swap shape or part (a tail gets its pivot where the stroke meets the body), the character is saved, and
    the request closes only when the rig check no longer lists the need; the moves that became free are reported.
    With render, the film that asked for it is re-rendered."""
    from . import director as DR, drawreq as RQ
    f = _req_puppet(puppet); rel = str(f.relative_to(ROOT)); p = _json(f)
    qp = RQ.queue_path(rel); q = _json(qp, {"requests": []})
    r = next((x for x in q["requests"] if x["id"] == id), None)
    if not r:
        raise ValueError(f"no request {id}")
    if r["status"] == "rig_canvas":
        raise ValueError(f"{r['need']} is rigged in the Rig Canvas, not drawn over a guide")
    img = Path(image) if Path(image).is_absolute() else ROOT / image
    lib = _clip_lib(p.get("template", "humanoid"), p)
    before = {c["move"] for c in DR.abilities(p, lib)["free"]}
    st, A = RQ.lift(img, p, r)
    where = RQ.slot(p, r, st, A)
    if rel.startswith("cast/"):
        puppet_save(rel, p)
    else:
        f.write_text(json.dumps(p))
    now_free = sorted({c["move"] for c in DR.abilities(p, lib)["free"]} - before)
    ok = not RQ.missing(p, r)
    r.update(status="done" if ok else "open", slotted=where, freed=now_free)
    qp.write_text(json.dumps(q, indent=1))
    out = {"request": r, "verified": ok, "now_free": now_free}
    if ok and render and r.get("film"):
        out["render"] = film_render(r["film"]).get("qa")
    return out


# ---------------- production orchestrator and board (plan 3.7) ----------------
def _today(today=""):
    import datetime as _dt
    return _dt.date.fromisoformat(today) if today else _dt.date.today()


@command("prod.plan", film=("string", "film folder name (it may not exist yet for claude or manual runners)"),
         post_on=("string", "posting date, YYYY-MM-DD"), runner=("string", "pipeline | claude | manual", "pipeline"),
         priority=("integer", "lower goes first among films posting the same day", 1),
         brief=("string", "for a new film: the brief (written to films/<film>/brief.md in its workspace)", ""),
         storyboard=("object", "for a new film: {format, brief} for film.from_template, built in its workspace at launch", None),
         plan=("object", "the calendar row it comes from (quarter, date, start_by, fact_lock_by, role, review)", None),
         budget_usd=("number", "for a claude runner: the most its session may spend (0: the board's default)", 0))
def prod_plan(film, post_on, runner="pipeline", priority=1, brief="", storyboard=None, plan=None, budget_usd=0):
    """Put a film on the production board (plan 3.7) with its posting date and the kind of session that makes it:
    pipeline (tools/film_agent.py rebuilds an existing film through every gate), claude (a Claude Code session with
    the director prompt), manual (any agent, given the written protocol)."""
    import datetime as _dt
    from . import production as PR
    _dt.date.fromisoformat(post_on)
    if runner not in ("pipeline", "claude", "manual"):
        raise ValueError("runner is pipeline, claude or manual")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", film):
        raise ValueError("film names are lower-case letters, digits and -")
    if runner == "pipeline" and not (FILMS / film).is_dir():
        raise FileNotFoundError(f"the pipeline runner rebuilds an existing film; {film} does not exist")
    with PR.registry() as reg:
        e = reg["films"].get(film) or {"film": film, "state": "planned", "checkpoints": [], "events": []}
        if e["state"] not in ("planned", "queued", "stopped", "failed", "needs_work"):
            raise ValueError(f"{film} is {e['state']}; stop it first to re-plan")
        e.update(post_on=post_on, runner=runner, priority=priority, **({"brief": brief} if brief else {}),
                 **({"storyboard": storyboard} if storyboard else {}), **({"plan": plan} if plan else {}), **({"budget_usd": budget_usd} if budget_usd else {}))
        PR.event(e, "planned", post_on=post_on, runner=runner); reg["films"][film] = e
        return {k: e[k] for k in ("film", "post_on", "runner", "state")}


@command("prod.launch", film=("string", "one film, or empty for every planned film", ""), max_parallel=("integer", "sessions at once (0: keep the board's setting)", 0))
def prod_launch(film="", max_parallel=0):
    """Start production sessions (plan 3.7): each film gets a git worktree on branch film/<name> and a session that
    reports at checkpoints; beyond max_parallel, films queue and start as others finish (prod.status starts them)."""
    from . import production as PR
    with PR.registry() as reg:
        if max_parallel:
            reg["max_parallel"] = int(max_parallel)
        todo = [reg["films"][film]] if film else [e for e in reg["films"].values() if e["state"] == "planned"]
        for e in todo:
            if e["state"] not in ("planned", "stopped", "failed", "needs_work"):
                continue
            if e["runner"] != "pipeline":   # a new film's brief and draft storyboard go into its workspace (WP-06)
                sb = PR.prepare(e)
                if sb:
                    PR.event(e, "storyboard drafted", ok=sb["ok"], checks=sb["checks"], facts_need_sources=len(sb.get("facts_need_sources", [])))
            e["state"] = "queued"; PR.event(e, "queued")
        PR.tick(reg)
        return {"running": [k for k, e in reg["films"].items() if e["state"] == "running"], "queued": [k for k, e in reg["films"].items() if e["state"] == "queued"],
                "max_parallel": reg["max_parallel"]}


@command("prod.checkpoint", film=("string", "film"), stage=("string", "research | first_render | final"),
         report=("object", "the session's report: research {contradictions: [...]}, first_render {shot}, final {}", None))
def prod_checkpoint(film, stage, report=None):
    """A film session reports a checkpoint (plan 3.7). The orchestrator measures for itself in the film's workspace
    (research: research.check and counter-evidence in the ledger; first_render: the shot file's size; final: qa.json
    checks, loudness, layout, the director's verdict) and answers with a verdict (ok, ready, fail, blocked,
    escalate), the owner's pending instructions, and whether to continue. Research that contradicts the brief
    escalates to the owner and pauses the film."""
    from . import production as PR
    if stage not in PR.STAGES:
        raise ValueError(f"stage is one of {PR.STAGES}")
    return PR.checkpoint(film, stage, report or {})


@command("prod.status", today=("string", "date for the schedule (YYYY-MM-DD; default today)", ""))
def prod_status(today=""):
    """The production board (plan 3.7): every film with its state, checkpoints and verdicts, latest measurements,
    escalations, and where it stands against its posting date (on_track, due_soon, late, needs_owner); starts queued
    films when sessions finish. Also a calendar of posting dates by week."""
    import datetime as _dt
    from . import production as PR
    d = _today(today)
    with PR.registry() as reg:
        PR.tick(reg)
        films = []
        for e in sorted(reg["films"].values(), key=lambda e: (e["post_on"], e.get("priority", 1))):
            cps = e.get("checkpoints", [])
            last = {}
            for c in cps:
                last[c["stage"]] = {k: c[k] for k in ("verdict", "reasons", "measured", "at")}
            media = {k: str((PR.reg_dir() / e["film"] / f).relative_to(ROOT)) for k, f in (("poster", "poster.jpg"), ("first", "first.jpg"), ("final", "final.mp4"))
                     if (PR.reg_dir() / e["film"] / f).exists() and ROOT in (PR.reg_dir() / e["film"] / f).resolve().parents}
            films.append({"film": e["film"], "post_on": e["post_on"], "runner": e["runner"], "state": e["state"], "schedule": PR.schedule(e, reg["lead_days"], d),
                          "plan": e.get("plan"), "channel": (e.get("plan") or {}).get("channel"),
                          "cost_usd": e.get("cost_usd"), "costs": e.get("costs", []),   # WP-03: what its Claude Code sessions spent
                          "checkpoints": last, "escalation": e.get("escalation") if e["state"] == "escalated" else None,
                          "approved": (e.get("approvals") or [None])[-1], "narrowed": e.get("narrowed", []), "media": media,
                          "session": {k: v for k, v in (e.get("session") or {}).items() if k in ("runner", "started", "pid", "log")},
                          "events": e.get("events", [])[-5:]})
        weeks = {}
        for f in films:
            p = _dt.date.fromisoformat(f["post_on"]); wk = (p - _dt.timedelta(days=p.weekday())).isoformat()
            weeks.setdefault(wk, []).append({"film": f["film"], "post_on": f["post_on"], "status": f["schedule"]["status"], "channel": f["channel"]})
        counts = {}
        for f in films:
            counts[f["state"]] = counts.get(f["state"], 0) + 1
        chans = {c["id"]: {"name": c["name"], "colour": c["colour"]} for c in plan_channels()}   # WP-32: films by channel
        nf = PR.reg_dir() / "notifications.jsonl"
        notes = [json.loads(x) for x in nf.read_text().splitlines()[-20:]] if nf.exists() else []
        return {"today": d.isoformat(), "max_parallel": reg["max_parallel"], "lead_days": reg["lead_days"], "counts": counts, "channels": chans,
                "notifications": notes[::-1], "budget_usd": reg.get("budget_usd"), "spent_usd": round(sum(e.get("cost_usd") or 0 for e in reg["films"].values()), 2),
                "calendar": [{"week_of": k, "films": v} for k, v in sorted(weeks.items())], "films": films}


def _prod_entry(reg, film):
    e = reg["films"].get(film)
    if not e:
        raise KeyError(f"{film} is not in the production registry")
    return e


@command("prod.session_prompt", film=("string", "a film running with a manual runner"))
def prod_session_prompt(film):
    """The prompt for any agent session making a film (WP-03): the production protocol (brief, checkpoints, how to
    report) and the director prompt, ready to paste into a Claude Code session on this machine or in the cloud that
    works in the film's workspace."""
    from . import production as PR
    with PR.registry(write=False) as reg:
        e = _prod_entry(reg, film)
    pd = Path(e.get("workspace") or "") / ".production" / "PRODUCTION.md"
    if not pd.exists():
        raise FileNotFoundError(f"{film} has no workspace yet: prod.launch it")
    return {"film": film, "workspace": e["workspace"], "branch": e.get("branch"),
            "prompt": pd.read_text() + "\n\n" + (ROOT / "docs" / "director-prompt.md").read_text()}


@command("prod.stop", film=("string", "film"), reason=("string", "why", ""))
def prod_stop(film, reason=""):
    """Stop a film's session (plan 3.7); its workspace and branch stay, so it can be relaunched."""
    from . import production as PR
    with PR.registry() as reg:
        e = _prod_entry(reg, film); PR.kill(e); e["state"] = "stopped"; PR.event(e, "stopped by the owner", reason=reason)
        return {"film": film, "state": "stopped"}


@command("prod.narrow", film=("string", "film"), text=("string", "the change of scope, in plain words (e.g. drop the dosage claim; 30 s cut only)"))
def prod_narrow(film, text):
    """Narrow a film's scope (plan 3.7): the change is added to its brief in the workspace and delivered to the
    session with its next checkpoint answer."""
    from . import production as PR
    with PR.registry() as reg:
        e = _prod_entry(reg, film)
        e.setdefault("inbox", []).append({"at": PR.now(), "text": text}); e.setdefault("narrowed", []).append(text)
        if e.get("workspace"):
            PR.narrow_brief(e, text)
        PR.event(e, "narrowed", text=text)
        return {"film": film, "narrowed": e["narrowed"]}


@command("prod.relaunch", film=("string", "film"))
def prod_relaunch(film):
    """Start a stopped, failed, needs_work or escalated film's session again in its workspace (renders there are reused)."""
    from . import production as PR
    with PR.registry() as reg:
        e = _prod_entry(reg, film); PR.kill(e)
        if e["state"] == "escalated" and not e.get("decisions"):
            raise ValueError(f"{film} waits for the owner's decision on its research (prod.decide)")
        e["state"] = "queued"; PR.event(e, "relaunched"); PR.tick(reg)
        return {"film": film, "state": e["state"]}


@command("prod.decide", film=("string", "escalated film"), decision=("string", "proceed | narrow | stop"), note=("string", "for narrow: the change of scope; otherwise why", ""))
def prod_decide(film, decision, note=""):
    """The owner's decision on research that contradicts a film's brief (plan 3.7): proceed as briefed, narrow the
    scope (the note is added to the brief) and continue, or stop. Proceed and narrow relaunch the session."""
    from . import production as PR
    if decision not in ("proceed", "narrow", "stop"):
        raise ValueError("decision is proceed, narrow or stop")
    if decision == "narrow" and not note:
        raise ValueError("say how to narrow it")
    with PR.registry() as reg:
        e = _prod_entry(reg, film)
        if e["state"] != "escalated":
            raise ValueError(f"{film} is not waiting for a decision")
        e.setdefault("decisions", []).append({"at": PR.now(), "decision": decision, "note": note})
        PR.event(e, f"owner decided: {decision}", note=note)
        if decision == "stop":
            e["state"] = "stopped"; return {"film": film, "state": "stopped"}
        if decision == "narrow":
            e.setdefault("inbox", []).append({"at": PR.now(), "text": note}); e.setdefault("narrowed", []).append(note); PR.narrow_brief(e, note)
        e["state"] = "queued"; PR.tick(reg)
        return {"film": film, "state": e["state"]}


@command("prod.approve", film=("string", "film"), by=("string", "who approves (the owner)"), note=("string", "", ""))
def prod_approve(film, by, note=""):
    """The owner approves a film whose final render passed QA (plan 3.7); only approved films can be merged."""
    from . import production as PR
    with PR.registry() as reg:
        e = _prod_entry(reg, film)
        fin = [c for c in e.get("checkpoints", []) if c["stage"] == "final"]
        if e["state"] != "waiting_owner" or not fin or fin[-1]["verdict"] != "ready":
            raise ValueError(f"{film} has no passing final render to approve (state {e['state']})")
        if (fin[-1].get("measured") or {}).get("expert_review") == "pending":   # WP-05
            from . import research as RS
            led = RS.ledger(Path(e["workspace"]) / "films" / film) if e.get("workspace") else []
            if not any(x.get("role") == "expert_review" and x.get("verdict") == "cleared" for x in led):
                raise PermissionError(f"{film} needs an expert review before approval: a qualified reviewer records ledger.add role expert_review verdict cleared")
        e.setdefault("approvals", []).append({"by": by, "at": PR.now(), "note": note}); e["state"] = "approved"; PR.event(e, "approved", by=by)
        return {"film": film, "state": "approved"}


@command("prod.merge", film=("string", "approved film"))
def prod_merge(film):
    """Merge an approved film's branch into the current branch (plan 3.7), refusing a branch that touches anything
    outside the film's folder (or new characters in cast/drawn/); the approved render and QA report are copied next
    to the film data."""
    from . import production as PR
    with PR.registry() as reg:
        e = _prod_entry(reg, film)
        if e["state"] != "approved":
            raise ValueError(f"{film} is not approved (state {e['state']})")
        changed = PR.merge(e); e["state"] = "merged"; PR.event(e, "merged", files=len(changed))
        return {"film": film, "state": "merged", "files": changed}


# ---------------- content planner (plan 3.8) ----------------
CH_ARG = ("string", "channel id (default: the default channel, plan/channels.json)", "")


def _plan_bank(channel=""):
    from . import planner as PL
    return _json(PL.chan_dir(channel) / "ideas.json", {"note": "idea bank (plan 3.8): sweeps add ideas; the planner schedules them", "ideas": []})


def _plan_save(name, obj, channel=""):
    from . import planner as PL
    d = PL.chan_dir(channel); d.mkdir(parents=True, exist_ok=True); (d / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def _plan_cal(quarter, channel=""):
    from . import planner as PL
    c = _json(PL.chan_dir(channel) / f"{quarter}.json")
    if not c:
        raise FileNotFoundError(f"no calendar for {quarter} on channel {channel or PL.default_channel()}: plan.schedule first")
    return c


@command("plan.quarters", channel=CH_ARG)
def plan_quarters(channel=""):
    """Quarters that have a calendar on a channel, newest first."""
    from . import planner as PL
    return sorted((f.stem for f in PL.chan_dir(channel).glob("*-Q*.json")), reverse=True)


@command("plan.channels")
def plan_channels():
    """The channels the studio plans for (WP-32), each with its audience, fields, brand kit, cast and quarters; the
    default first."""
    from . import planner as PL
    out = []
    for cid in sorted(PL.channel_ids(), key=lambda c: c != PL.default_channel()):
        ch = PL.channel(cid); br = _json(ROOT / "brand" / f"{ch.get('brand', 'brand')}.json", {})
        out.append({"id": cid, "name": ch["name"], "audience": ch["audience"], "fields": ch["fields"], "locale": ch.get("locale"),
                    "brand": ch.get("brand", "brand"), "colour": (br.get("palette") or {}).get(br.get("wordmark_accent", "primary")) or "#888888",
                    "cast": ch.get("cast"), "series": (ch["rules"].get("series") or {}).get("name"), "quarters": plan_quarters(cid),
                    "default": cid == PL.default_channel()})
    return out


@command("plan.channel", update=("object", "fields to change (name, audience, fields, locale, languages, rules, brand, cast, voices)", None),
         channel=("string", "channel id (default: the default channel); a new id makes a new channel from the defaults", ""))
def plan_channel(update=None, channel=""):
    """The channel the content planner plans for (plan 3.8): audience, topic fields, locale for the local quota, and the
    spread rules (posting days, the weekly series, topic diversity, field gap, local quota, analysis cadence, lead and
    fact-lock days per sweep), and (WP-32) its brand kit (brand/<brand>.json), default cast {role: character} and voices
    {character: voice}. plan/channels/<id>/channel.json."""
    from . import planner as PL
    ch = PL.channel(channel)
    if update:
        for k, v in update.items():
            ch[k] = {**ch[k], **v} if isinstance(v, dict) and isinstance(ch.get(k), dict) else v
        if ch.get("brand") and not (ROOT / "brand" / f"{ch['brand']}.json").exists():
            raise FileNotFoundError(f"no brand kit brand/{ch['brand']}.json")
        _plan_save("channel.json", {k: v for k, v in ch.items() if k != "id"}, channel)
    return ch


@command("plan.sweep_prompt", sweep=("string", "dated_hook | recent | evergreen | tool | analysis | local"), quarter=("string", "e.g. 2027-Q1"),
         count=("integer", "ideas to ask for", 20), channel=CH_ARG)
def plan_sweep_prompt(sweep, quarter, count=20, channel=""):
    """The research prompt for one sweep (plan 3.8), for a research agent with web search: what to find for this
    channel and quarter, the sourcing rules (real, opened sources; nothing invented) and the exact JSON to return,
    which plan.ideas_add accepts."""
    from . import planner as PL
    if sweep not in PL.SWEEPS:
        raise ValueError(f"sweep is one of {PL.SWEEPS}")
    return {"sweep": sweep, "channel": PL.channel(channel)["id"], "prompt": PL.sweep_prompt(sweep, quarter, PL.channel(channel), count)}


@command("plan.ideas_add", ideas=("array", "ideas in the sweep schema (plan.sweep_prompt)"), by=("string", "who found them (agent or person)"),
         check_urls=("boolean", "fetch every cited URL and refuse sources that do not exist", True), channel=CH_ARG)
def plan_ideas_add(ideas, by, check_urls=True, channel=""):
    """Add ideas to the bank (plan 3.8): each is checked (fields, sweep, a source URL, a date for dated hooks,
    fresh_until for recent stories, data and terms for analyses), near-duplicates of banked ideas are refused, and
    with check_urls every cited URL is fetched: an idea whose sources are all missing (404, or no such host) is
    refused, a missing source is dropped from an idea that has others, and each source records what the check saw."""
    from . import planner as PL
    rej0 = []
    if check_urls:
        st = PL.check_sources(ideas); keep = []
        for x in ideas:
            srcs = [dict(s, checked=st.get(s.get("url"), "unchecked")) for s in x.get("sources", []) if isinstance(s, dict)]
            good = [s for s in srcs if s["checked"] != "missing"]
            data_missing = isinstance(x.get("data"), dict) and st.get(x["data"].get("url")) == "missing"
            if not good or data_missing:
                rej0.append({"title": x.get("title"), "why": ["sources not found: " + ", ".join(s["url"] for s in srcs if s["checked"] == "missing")]}); continue
            keep.append({**x, "sources": good})
        ideas = keep
    bank = _plan_bank(channel); added, rejected = PL.add_ideas(bank, ideas, PL.channel(channel), by); rejected = rej0 + rejected
    _plan_save("ideas.json", bank, channel)
    return {"added": len(added), "ids": added, "rejected": rejected, "bank": len(bank["ideas"])}


@command("plan.ideas", sweep=("string", "filter", ""), field=("string", "filter", ""), status=("string", "filter", ""), channel=CH_ARG)
def plan_ideas(sweep="", field="", status="", channel=""):
    """The idea bank, filtered, with counts by sweep, field and status."""
    from collections import Counter
    ideas = [i for i in _plan_bank(channel)["ideas"] if (not sweep or i["sweep"] == sweep) and (not field or i["field"] == field) and (not status or i["status"] == status)]
    return {"count": len(ideas), "by_sweep": dict(Counter(i["sweep"] for i in ideas)), "by_field": dict(Counter(i["field"] for i in ideas)),
            "by_status": dict(Counter(i["status"] for i in ideas)), "ideas": ideas}


@command("plan.schedule", quarter=("string", "e.g. 2027-Q1"), planned_on=("string", "the day the plan is made (lead times count from it; default today)", ""),
         channel=CH_ARG)
def plan_schedule(quarter, planned_on="", channel=""):
    """Make the quarter's calendar (plan 3.8): dated hooks on their day, the weekly series, the analysis cadence, the
    local quota, then the rest, an empty field getting the next slot; each row with a start-by date and a fact-lock
    date. Writes plan/<quarter>.json (ideas used are marked planned) and returns plan.check's verdict."""
    import datetime as _dt
    from . import planner as PL
    ch = PL.channel(channel); bank = _plan_bank(channel); po = _dt.date.fromisoformat(planned_on) if planned_on else _dt.date.today()
    old = _json(PL.chan_dir(channel) / f"{quarter}.json")
    if old and any(r.get("film") for r in old["rows"]):
        raise ValueError(f"{quarter} already has briefed rows; edit it rather than re-planning")
    for i in bank["ideas"]:   # re-planning frees this quarter's ideas
        if i["status"] == "planned" and i.get("quarter") == quarter:
            i["status"] = "idea"
    rows = PL.schedule(quarter, bank, ch, po)
    used = {r["idea"] for r in rows if r.get("idea")}
    for i in bank["ideas"]:
        if i["id"] in used:
            i["status"] = "planned"; i["quarter"] = quarter
    cal = {"quarter": quarter, "planned_on": po.isoformat(), "channel": ch["name"], "channel_id": ch["id"], "rules": ch["rules"], "rows": rows}
    _plan_save(f"{quarter}.json", cal, channel); _plan_save("ideas.json", bank, channel)
    return PL.check(cal, bank, ch)


@command("plan.check", quarter=("string", "e.g. 2027-Q1"), channel=CH_ARG)
def plan_check(quarter, channel=""):
    """Check a quarter's calendar against every spread rule (plan 3.8), independently of how it was made: slots
    filled, posts per week, topic diversity, field gap, local quota, analysis cadence, series cadence, dated hooks on
    their day and recent stories while fresh, lead times, a fact-lock date on every row, an empty field getting the
    next slot, no repeats, sources on every idea."""
    from . import planner as PL
    return PL.check(_plan_cal(quarter, channel), _plan_bank(channel), PL.channel(channel))


@command("plan.track", quarter=("string", "e.g. 2027-Q1"), today=("string", "YYYY-MM-DD (default today)", ""), channel=CH_ARG)
def plan_track(quarter, today="", channel=""):
    """The live tracker (plan 3.8): every row with where it really is (planned, briefed, in production, final ready,
    approved, merged, posted, from the films and the production registry), its fact-lock status (locked once the
    film's ledger has a cleared fact gate) and what is overdue."""
    from . import planner as PL, production as PR
    reg = {}
    if (PR.reg_dir() / "registry.json").exists():
        with PR.registry(write=False) as r:
            reg = r["films"]
    rows = PL.track(_plan_cal(quarter, channel), _plan_bank(channel), reg, _today(today))
    from collections import Counter
    return {"quarter": quarter, "channel": PL.channel(channel)["id"], "today": _today(today).isoformat(), "stages": dict(Counter(r["stage"] for r in rows)),
            "overdue": [r for r in rows if r["overdue"]], "rows": rows}


@command("plan.brief", quarter=("string", "e.g. 2027-Q1"), date=("string", "the row's posting date"),
         storyboard=("boolean", "also draft the storyboard from the row's format template (film.from_template)", True),
         launch=("boolean", "put it on the production board with its posting date and start its session (prod.plan + prod.launch)", False),
         runner=("string", "production runner when launching: claude | manual", "claude"), channel=CH_ARG)
def plan_brief(quarter, date, storyboard=True, launch=False, runner="claude", channel=""):
    """Calendar to production in one command (plan 3.8, WP-06, feature map E24): the row's brief (hook, angle, why now,
    starting-point sources, research leads, cautions, start-by and fact-lock dates, review level), a draft storyboard
    from the format template the row names (myth_vs_data, explainer, dialogue), drafted from the idea's own words with
    every fact unsourced so the research gate holds it, and its storyboard.check. Without launch it is written to
    films/<slug>/ for a look; with launch it goes onto the board with its plan row and starts a session, and the brief
    and storyboard are committed on the film's branch in its workspace (nothing is left in the main checkout)."""
    from . import planner as PL
    cal = _plan_cal(quarter, channel); bank = _plan_bank(channel); ch = PL.channel(channel)
    row = next((r for r in cal["rows"] if r["date"] == date and r.get("idea")), None)
    if not row:
        raise ValueError(f"no planned row on {date}")
    idea = next(i for i in bank["ideas"] if i["id"] == row["idea"])
    film = row.get("film") or PL.slug(idea["title"])
    d = FILMS / film
    if (d / "script.json").exists():
        raise FileExistsError(f"films/{film} already has a script")
    text = PL.brief_md(idea, row, ch)
    fmt, fields = PL.draft_storyboard(idea, row)
    fields.update({k: ch[k] for k in ("cast", "voices") if ch.get(k)})   # WP-32: the channel's cast, voices and brand kit
    fields["brand"] = ch.get("brand", "brand")
    out = {"film": film, "format": fmt, "channel": ch["id"]}
    if launch:
        if runner not in ("claude", "manual"):
            raise ValueError("a new film is made by a claude or manual session")
        plan = {"channel": ch["id"], "quarter": quarter, "date": row["date"], "start_by": row["start_by"], "fact_lock_by": row["fact_lock"]["by"],
                "role": row.get("role"), "review": row.get("review", "standard"), "idea": idea["id"], "title": idea["title"]}
        out["production"] = prod_plan(film, date, runner=runner, brief=text, storyboard={"format": fmt, "brief": fields} if storyboard else None, plan=plan)
        out["launch"] = prod_launch(film)
        from . import production as PR
        with PR.registry(write=False) as reg:
            ev = [x for x in reg["films"][film]["events"] if x.get("what") == "storyboard drafted"]
        out["storyboard"] = ev[-1] if ev else None
        out["brief"] = f"films/{film}/brief.md (in its workspace, branch film/{film})"
    else:
        d.mkdir(parents=True, exist_ok=True); (d / "brief.md").write_text(text)
        out["brief"] = f"films/{film}/brief.md"
        if storyboard:
            out["storyboard"] = film_from_template(film, fmt, fields)["storyboard"]
    row["film"] = film; idea["status"] = "briefed"; idea["film"] = film
    _plan_save(f"{quarter}.json", cal, channel); _plan_save("ideas.json", bank, channel)
    return out


@command("plan.posted", quarter=("string", "e.g. 2027-Q1"), date=("string", "the row's posting date"), url=("string", "where it was posted"), channel=CH_ARG)
def plan_posted(quarter, date, url, channel=""):
    """Mark a calendar row as posted, with its link (the tracker's last stage)."""
    cal = _plan_cal(quarter, channel); row = next((r for r in cal["rows"] if r["date"] == date and r.get("idea")), None)
    if not row:
        raise ValueError(f"no planned row on {date}")
    row["posted"] = {"url": url, "at": _today().isoformat()}; _plan_save(f"{quarter}.json", cal, channel)
    bank = _plan_bank(channel)
    for i in bank["ideas"]:
        if i["id"] == row["idea"]:
            i["status"] = "posted"
    _plan_save("ideas.json", bank, channel)
    return row


@command("plan.cross", quarter=("string", "e.g. 2027-Q1"), same_week=("boolean", "flag two channels posting the same subject in one week", True))
def plan_cross(quarter, same_week=True):
    """Every channel's quarter side by side, week by week (WP-32): posts per channel, and (when same_week) the weeks in
    which two channels post on the same subject (the planner's topic guard across channels)."""
    import datetime as _dt
    from . import planner as PL
    weeks, chans, rows_by = {}, [], {}
    for cid in PL.channel_ids():
        cal = _json(PL.chan_dir(cid) / f"{quarter}.json")
        if not cal:
            continue
        chans.append(cid); ideas = {i["id"]: i for i in _plan_bank(cid)["ideas"]}
        for r in cal["rows"]:
            if not r.get("idea"):
                continue
            d = _dt.date.fromisoformat(r["date"]); wk = (d - _dt.timedelta(days=d.weekday())).isoformat()
            weeks.setdefault(wk, {}).setdefault(cid, []).append({"date": r["date"], "title": r["title"], "field": r.get("field")})
            rows_by.setdefault(wk, []).append((cid, ideas.get(r["idea"], {"title": r["title"]})))
    clashes = []
    if same_week:
        for wk, xs in sorted(rows_by.items()):
            for i, (ca, a) in enumerate(xs):
                for cb, b in xs[i + 1:]:
                    if ca != cb and PL.same_topic(a, b):
                        clashes.append({"week_of": wk, "a": [ca, a["title"]], "b": [cb, b["title"]]})
    return {"quarter": quarter, "channels": chans, "weeks": [{"week_of": k, **v} for k, v in sorted(weeks.items())], "clashes": clashes, "ok": not clashes}


# ---------------- storyboard strip and animatic (plan 3.2) ----------------
def _board_frames(name):
    """one representative moment per shot: a moment into its first line (the picture as it speaks), else its middle"""
    d = _film(name); res = _shots(name); tm = _json(d / "timing.json", {}); sc = _json(d / "script.json", {})
    dirs = {l["id"]: l.get("direction") for l in sc.get("lines", []) if l.get("direction")}
    rows = []
    for sh in res["shots"]:
        ls = [l for l in tm.get("lines", []) if sh["start"] - 0.01 <= l["start"] < sh["end"]]
        t = (ls[0]["start"] + min(1.0, (ls[0]["end"] - ls[0]["start"]) / 2)) if ls else (sh["start"] + sh["end"]) / 2
        rows.append({"shot": sh["id"], "t": round(min(t, sh["end"] - 0.05), 3), "start": sh["start"], "end": sh["end"], "set": sh.get("set", "plain"),
                     "cast": [c.get("speaker") or Path(c["puppet"]).stem.split(".")[0] for c in sh.get("cast") or []],
                     "lines": [f"{l.get('speaker', '')}: {l['text']}" for l in ls],
                     "notes": [x for x in [sh.get("direction"), sh.get("notes")] + [dirs.get(l["id"]) for l in ls] if x]})
    return rows


@command("film.storyboard", name=("string", "film"), width=("integer", "still width in px", 360))
def film_storyboard(name, width=360):
    """Storyboard (plan 3.2): one still per shot from the player (a moment into its first line, else its middle),
    with notes (shot, times, set, cast, its lines, directions). Writes build/storyboard/strip.png (all shots in a grid)
    and build/storyboard/contact.pdf (six shots a page, notes beside each), plus the stills."""
    from PIL import Image, ImageDraw, ImageFont
    d = _film(name); out = d / "build" / "storyboard"; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    rows = _board_frames(name); page = _player_page(name)
    _run(["node", "tools/board_stills.mjs", str(page), str(out), str(width), *[str(r["t"]) for r in rows]], timeout=900)
    font = lambda n, bold=False: ImageFont.truetype(str(ROOT / "engine" / "fonts" / "Fredoka.ttf"), n)
    def wrap(txt, f, w, draw):
        lines, cur = [], ""
        for word in str(txt).split():
            if draw.textlength((cur + " " + word).strip(), font=f) > w and cur:
                lines.append(cur); cur = word
            else:
                cur = (cur + " " + word).strip()
        return lines + ([cur] if cur else [])
    stills = []
    for i, r in enumerate(rows):
        im = Image.open(out / f"still_{i}.png").convert("RGB"); h = round(width * im.height / im.width)
        im = im.resize((width, h), Image.LANCZOS); im.save(out / f"{r['shot']}.png"); (out / f"still_{i}.png").unlink(); stills.append(im)
    # strip: a grid with a caption block under each still
    cols = min(len(rows), 6); cap = 150; pad = 16; h = stills[0].height
    strip = Image.new("RGB", (pad + cols * (width + pad), pad + -(-len(rows) // cols) * (h + cap + pad)), "#f4f1ea"); dr = ImageDraw.Draw(strip)
    for i, (r, im) in enumerate(zip(rows, stills)):
        x, y = pad + (i % cols) * (width + pad), pad + (i // cols) * (h + cap + pad)
        strip.paste(im, (x, y)); dr.rectangle([x, y, x + width - 1, y + h - 1], outline="#24160e", width=2)
        dr.text((x, y + h + 8), f"{r['shot']}  {r['start']:.1f}-{r['end']:.1f} s  ·  {r['set']}", font=font(17), fill="#24160e")
        ty = y + h + 34
        for ln in (wrap(" / ".join(r["lines"]) or "(no lines)", font(14), width, dr))[:5]:
            dr.text((x, ty), ln, font=font(14), fill="#5a4a3a"); ty += 18
    strip.save(out / "strip.png", optimize=True)
    # contact PDF: A4 portrait at 100 dpi, six shots per page, notes beside each still
    W, H = 827, 1169; per = 3; pages = []
    title = _shots(name, resolve=False).get("title", name)
    for p0 in range(0, len(rows), per):
        pg = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(pg)
        dr.text((40, 30), f"{title} · storyboard · page {p0 // per + 1}", font=font(22), fill="#24160e")
        for j, (r, im) in enumerate(zip(rows[p0:p0 + per], stills[p0:p0 + per])):
            y = 80 + j * 360; th = 340; tw = round(th * im.width / im.height); pg.paste(im.resize((tw, th), Image.LANCZOS), (40, y))
            dr.rectangle([40, y, 40 + tw - 1, y + th - 1], outline="#24160e", width=2); x = 40 + tw + 24; ty = y
            dr.text((x, ty), f"{r['shot']}   {r['start']:.2f} - {r['end']:.2f} s   ({r['end'] - r['start']:.1f} s)", font=font(18), fill="#24160e"); ty += 28
            dr.text((x, ty), f"set: {r['set']}   cast: {', '.join(r['cast']) or '-'}", font=font(14), fill="#5a4a3a"); ty += 26
            for ln in [*r["lines"], *[f"direction: {n}" for n in r["notes"]]]:
                for wl in wrap(ln, font(14), W - x - 40, dr):
                    if ty < y + th - 18:
                        dr.text((x, ty), wl, font=font(14), fill="#24160e" if not ln.startswith("direction") else "#7a5cc4"); ty += 19
                ty += 6
        pages.append(pg)
    pages[0].save(out / "contact.pdf", save_all=True, append_images=pages[1:], resolution=100)
    return {"strip": str((out / "strip.png").relative_to(ROOT)), "pdf": str((out / "contact.pdf").relative_to(ROOT)), "shots": len(rows), "pages": len(pages),
            "stills": [str((out / f"{r['shot']}.png").relative_to(ROOT)) for r in rows]}


@command("film.animatic", name=("string", "film"))
def film_animatic(name):
    """Animatic (plan 3.2): the storyboard stills held for their shots' lengths over the film's sound (the mix if
    rendered, else the voice), as build/animatic.mp4. Seconds to make; use it to judge pacing before a render."""
    d = _film(name); sb = d / "build" / "storyboard"; rows = _board_frames(name)
    if not all((sb / f"{r['shot']}.png").exists() for r in rows):
        film_storyboard(name)
    lst = d / "build" / "animatic.txt"
    lst.write_text("".join(f"file '{(sb / (r['shot'] + '.png')).resolve()}'\nduration {r['end'] - r['start']:.3f}\n" for r in rows) + f"file '{(sb / (rows[-1]['shot'] + '.png')).resolve()}'\n")
    audio = next((p for p in (d / "build" / "mix.wav", d / "build" / "voice.wav") if p.exists()), None)
    out = d / "build" / "animatic.mp4"; total = rows[-1]["end"]
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *(["-i", str(audio)] if audio else []),
          "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", *(["-c:a", "aac", "-b:a", "160k"] if audio else []),
          "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
    return {"animatic": str(out.relative_to(ROOT)), "length_s": round(total, 2), "sound": audio.name if audio else None}


# ---------------- format templates (plan 2.15) ----------------
@command("storyboard.check", name=("string", "film"))
def storyboard_check(name):
    """The cold-open and reading-time rules on a storyboard, before or after voicing (with slots the timing is known
    before any voice): a character in frame one and the first words by 1.5 s; every sign, title or bubble up for
    words / 3 + 1 s; captions at most 3.2 words/s. Also lists facts still waiting for a source (the research gate)."""
    from . import layout_qa as LQ
    d = _film(name); res = _shots(name); tm = _json(d / "timing.json", {})
    co = LQ.cold_open(res["shots"], tm, res.get("size", [1080, 1920])); rd = LQ.reading_time(res["shots"], tm, captions=res.get("captions", True))
    facts = _json(d / "facts.json", {"facts": []}).get("facts", [])
    style, cfg = LQ.config_for(res)   # the film's style thresholds (WP-04)
    checks = {k: v for k, v in LQ.judge({"cold_open": co, "reading": rd}, cfg)["checks"].items() if k in ("cold_open", "reading_time")}
    return {"ok": all(checks.values()), "checks": checks, "style": style, "cold_open": co, "reading": rd,
            "facts_need_sources": [f["id"] for f in facts if not f.get("source")]}


@command("film.from_template", name=("string", "new film"), format=("string", "myth_vs_data | explainer | dialogue | wonder_story | we_reran_it | anniversary | series"),
         brief=("object", "the brief: the fields the format needs (see dbe/formats.py), optional cast {role: id}, lines {beat: text}, facts, data"))
def film_from_template(name, format, brief):
    """Format templates (plan 2.15): build a storyboard from a format and a brief: script with narration slots
    (135 wpm, draft timing so it can be checked and cut before voicing), shots (one per scene, line-relative), kit
    signs held long enough to read, prediction prompts with a silent count before reveals, facts (gated until
    sourced), data for charts, edit.json for a series; then run storyboard.check."""
    from . import formats as FM
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", name):
        raise ValueError("film name: lowercase letters, digits, - and _")
    d = FILMS / name
    if d.exists() and (d / "script.json").exists():
        raise FileExistsError(f"films/{name} exists")
    lines, shots, facts, edit = FM.storyboard(format, brief)
    d.mkdir(parents=True, exist_ok=True)
    voices = {"ravi": "kokoro:am_michael", "momo": "kokoro:af_heart", "priya": "kokoro:af_bella", **(brief.get("voices") or {})}
    spk = {l["speaker"] for l in lines}
    script = {"title": brief.get("title", name), "format": format,
              "speakers": {k: ({"voice": voices.get(k, "kokoro:af_sarah"), **({"fx": {"pitch": 1.2, "formant": 1.08, "range": 1.25}} if k == "momo" else {})}) for k in sorted(spk)},
              "lead_in_s": 0.6, "gap_s": 0.45, "lines": lines}
    (d / "script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False))
    (d / "shots.json").write_text(json.dumps({"title": brief.get("title", name), "size": [1080, 1920], "fps": 30, "captions": True,
                                              **({"brand": brief["brand"]} if brief.get("brand") else {}), "shots": shots}, indent=1, ensure_ascii=False))
    (d / "facts.json").write_text(json.dumps({"facts": facts}, indent=1, ensure_ascii=False))
    (d / "score.json").write_text(json.dumps({"length_s": 30, "bpm": 96, "offset_s": 0, "sections": [{"kind": "main", "from_beat": 0, "to_beat": 64, "chords": ["F", "Am", "Dm", "C"], "end_chord": "F"}]}, indent=1))
    if brief.get("data"):
        (d / "data.json").write_text(json.dumps(brief["data"], indent=1, ensure_ascii=False))
    if edit:
        (d / "edit.json").write_text(json.dumps(edit, indent=1))
    if brief.get("draft"):
        script["draft"] = brief["draft"]; (d / "script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False))
    about = (f"Format: {format} ({FM.TEMPLATES.get(format, {}).get('about', 'series of parts')}).\n\n"
             + "\n".join(f"- {k}: {v}" for k, v in brief.items() if isinstance(v, (str, int, float))) + "\n")
    if (d / "brief.md").exists():   # a planner brief stays; the storyboard's fields are added under it
        with open(d / "brief.md", "a") as fh:
            fh.write(f"\n## Storyboard (film.from_template)\n{about}")
    else:
        (d / "brief.md").write_text(f"# {brief.get('title', name)}\n\n{about}")
    sl = script_slots(name)
    chk = storyboard_check(name)
    return {"film": f"films/{name}", "lines": len(lines), "shots": [s_["id"] for s_ in shots], "length_s": sl["length_s"], "storyboard": chk,
            "next": ["voice.build", "acting.plan", "acting.direct (optional)", "film.render"] + (["research: source the facts"] if chk["facts_need_sources"] else [])}


@command("film.heal", name=("string", "film"), rounds=("integer", "most render-and-repair rounds", 3),
         revoice=("boolean", "allow re-voicing slower when captions flow too fast", False))
def film_heal(name, rounds=3, revoice=False):
    """Self-healing (plans 2.9, 2.18): render, read every failure (QA bar, layout checks including advisory ones,
    visual lint errors), apply the known repair for each to shots.json (frozen stretches, text outside the safe area
    or too small, short reading time, bare frames, heads cut by the frame, bubbles over faces; slower voice with
    revoice), re-render what changed and repeat until the film passes or nothing more can be repaired. Keeps the
    original as build/shots.before_heal.json and returns the log of every failure and edit."""
    from . import heal as HL
    d = _film(name); raw0 = _json(d / "shots.json")
    (d / "build").mkdir(exist_ok=True)
    if not (d / "build" / "shots.before_heal.json").exists():
        (d / "build" / "shots.before_heal.json").write_text(json.dumps(raw0, indent=1, ensure_ascii=False))
    log, tried = [], {}
    for rnd in range(1, rounds + 2):
        film_render(name); dirty = False
        rep = _json(d / "build" / "qa.json", {}); lint = _json(d / "build" / "lint.json", {})
        fails = HL.failures(rep, lint)
        if not fails or rnd > rounds:
            break
        res = _shots(name); size = res.get("size", [1080, 1920])
        reps = HL.diagnose(rep, lint, res, size, _json(d / "script.json", {}) if revoice else None)
        # a repair that did not help is undone and not tried again (frame fill: scaling the cast up must cut the bare
        # share by at least 3 points, else the shot needs new content, not a bigger character)
        ff = ((rep.get("layout") or {}).get("frame_fill") or {}).get("per_shot_mean") or {}
        for (sid, kind), (before, saved) in list(tried.items()):
            if kind == "grow" and ff.get(sid, 0) > before - 0.03:
                cur = _json(d / "shots.json")
                for sh_ in cur["shots"]:
                    if sh_["id"] == sid:
                        sh_["cast"] = saved
                (d / "shots.json").write_text(json.dumps(cur, indent=1, ensure_ascii=False))
                log.append({"round": rnd, "undone": f"cast scale-up in {sid}: bare ground {before:.0%} -> {ff.get(sid, 0):.0%}, not enough to keep"})
                dirty = True
                tried[(sid, kind)] = (before, None)
        reps = [r for r in reps if not (r["edit"][0] == "grow" and ((r["shot"], "grow") in tried or rnd >= rounds))]   # needs a round left to measure it
        for r in reps:
            if r["edit"][0] == "grow":
                sh_ = next(x for x in _json(d / "shots.json")["shots"] if x["id"] == r["shot"])
                tried[(r["shot"], "grow")] = (ff.get(r["shot"], 1), json.loads(json.dumps(sh_.get("cast"))))
        if not reps:
            break
        new, slow = HL.apply(_json(d / "shots.json"), reps, res, size)
        log.append({"round": rnd, "failing": fails, "repairs": [{k: r[k] for k in ("check", "shot", "what")} for r in reps]})
        (d / "shots.json").write_text(json.dumps(new, indent=1, ensure_ascii=False))
        if slow:
            # anchor hard shot times to their lines first, so the picture follows the slower voice
            old = {l["id"]: l for l in _json(d / "timing.json", {}).get("lines", [])}; cur = _json(d / "shots.json"); resd = {x["id"]: x for x in res["shots"]}
            for sh in cur["shots"]:
                for key, lk, edge in (("start", "start_line", "start"), ("end", "end_line", "end")):
                    ln = old.get(sh.get(lk))
                    if ln and isinstance(sh.get(key), (int, float)) and not (key == "start" and sh[key] == 0):
                        off = round(resd[sh["id"]][key] - ln[edge], 3)
                        sh[key] = f"{ln['id']}.{edge}{'+' if off >= 0 else '-'}{abs(off)}"
            (d / "shots.json").write_text(json.dumps(cur, indent=1, ensure_ascii=False))
            log[-1]["repairs"].append({"check": "reading_time", "shot": "*", "what": "hard shot times anchored to their lines before re-voicing"})
            sc = _json(d / "script.json"); sc["length_scale"] = round(sc.get("length_scale", 1.0) * slow, 3)
            (d / "script.json").write_text(json.dumps(sc, indent=1, ensure_ascii=False))
            voice_build(name)
            if any(c.get("speaker") for sh in new["shots"] for c in sh.get("cast", [])):
                acting_plan(name)
    if dirty:   # an undo came after the last render
        film_render(name); rep = _json(d / "build" / "qa.json", {}); lint = _json(d / "build" / "lint.json", {})
    still = HL.failures(rep, lint)
    return {"passes": not still, "rounds": log, "still_failing": {f: HL.HINTS.get(f, "no automatic repair yet") for f in still}}


@command("lipsync.check", name=("string", "film"))
def lipsync_check(name):
    """Lip-sync cross-check (plan 2.2): each speaker's viseme track against their own voice (first-formant energy of
    build/voice.wav inside their lines): best lag in frames and correlation; with DBE_RHUBARB set, also agreement with
    Rhubarb Lip Sync's reading of the same audio and text. Fails beyond +-2 frames or below 0.2 correlation."""
    _film(name)
    return json.loads(subprocess.run(
        [PY, "dbe/lipsync_qa.py", f"films/{name}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)


@command("film.lint", name=("string", "film"), step=("integer", "sample every Nth frame", 3))
def film_lint(name, step=3):
    """Visual lint (plan 2.8): play the film in the player and flag picture problems with frame ranges. Heads cut by
    the frame (error), speech bubbles over faces (error), hands leaving the frame or feet cropped in a wide shot,
    faces under the caption band, arms locked straight by an unreachable IK target, props through someone else's
    head (warn), and silhouettes tangent to the frame edge or to each other (info). Writes build/lint.json."""
    d = _film(name)
    if not (d / "shots.json").exists():
        return {"error": "film.lint needs a shots.json film"}
    page = _player_page(name)
    r = subprocess.run(["node", "tools/lint.mjs", str(page), str(int(step))], cwd=ROOT, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not r.stdout.strip():
        return {"error": (r.stderr or r.stdout)[-800:]}
    issues = json.loads(r.stdout.strip().splitlines()[-1])
    summary = {lv: sum(1 for i in issues if i.get("level") == lv) for lv in ("error", "warn", "info")}
    (d / "build" / "lint.json").write_text(json.dumps({"summary": summary, "issues": issues}, indent=1))
    return {"summary": summary, "issues": issues}


# ---------------- reach ----------------
@command("export.web", name=("string", "film"))
def export_web(name):
    """Export a self-contained interactive web player (play, scrub, frame step) that renders the film live in the
    browser: build/web/index.html with scripts and font inlined, plus audio.ogg (Opus). Host the folder anywhere."""
    import base64
    d = _film(name); page = _player_page(name)
    html = page.read_text()
    out_dir = d / "build" / "web"; out_dir.mkdir(parents=True, exist_ok=True)
    html = html.replace('<script src="../../../dbe/player/player.js"></script>',
                        '<script src="../../../dbe/player/player.js"></script><script src="../../../dbe/player/web_ui.js"></script>')
    for src in re.findall(r'<script src="\.\./\.\./\.\./([^"]+)"></script>', html):
        code = (ROOT / src).read_text().replace("</script", "<\\/script")
        html = html.replace(f'<script src="../../../{src}"></script>', f"<script>/* {src} */\n{code}\n</script>")
    font = base64.b64encode((ROOT / "engine" / "fonts" / "Fredoka.ttf").read_bytes()).decode()
    html = html.replace("url('../../../engine/fonts/Fredoka.ttf')", f"url(data:font/ttf;base64,{font})")
    mix = d / "build" / "mix.wav"
    if mix.exists():
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(mix), "-c:a", "libopus", "-b:a", "96k", str(out_dir / "audio.ogg")])
    html = html.replace("</body>", f'<audio id="aud" src="{"audio.ogg" if mix.exists() else ""}" preload="auto"></audio></body>')
    (out_dir / "index.html").write_text(html)
    return {"path": str((out_dir / "index.html").relative_to(ROOT)), "bytes": len(html), "audio": mix.exists(),
            "note": "fonts and scripts are inlined; Fredoka is under the SIL OFL (engine/fonts/OFL.txt)"}


@command("film.localize", name=("string", "film"), lang=("string", "language tag, e.g. es"), voice=("string", "Piper voice id for the language"), lines=("object", "line id -> translated text"),
         renderer=("string", "optional: render every shot with this renderer (e.g. svg for a fast draft)", ""))
def film_localize(name, lang, voice, lines, renderer=""):
    """Make a language version: copy the film, swap every speaker's voice, replace line texts, re-voice and re-render.
    All timing (shots, acting, visemes) re-derives from the new word timings."""
    src = _film(name); dst = FILMS / f"{name}-{lang}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "timing.json"))
    (dst / "build").mkdir(exist_ok=True)
    sc = _json(dst / "script.json")
    for spk in sc.get("speakers", {}).values():
        spk["voice"] = voice
    for ln in sc["lines"]:
        if ln["id"] in lines:
            ln["text"] = lines[ln["id"]]
    sc["lang"] = lang
    (dst / "script.json").write_text(json.dumps(sc, indent=1))
    if renderer:
        sj = _json(dst / "shots.json")
        for sh in sj["shots"]:
            sh["renderer"] = renderer
        (dst / "shots.json").write_text(json.dumps(sj, indent=1))
    v = voice_build(f"{name}-{lang}")
    # shot times are written against line ids, so re-derive them from the new timing
    retime(f"{name}-{lang}")
    r = film_render(f"{name}-{lang}")
    return {"film": f"{name}-{lang}", "voice": v, "render": r}


@command("film.retime", name=("string", "film"))
def retime(name):
    """Re-derive shot start/end from line references (start_line/end_line in shots.json) after a voice change."""
    s = _shots(name, resolve=False); t = _json(FILMS / name / "timing.json", {})
    L = {l["id"]: l for l in t.get("lines", [])}
    for sh in s["shots"]:
        if "start_line" in sh and sh["start_line"] in L:
            sh["start"] = round(L[sh["start_line"]]["start"] - sh.get("lead", 0.2), 3) if sh is not s["shots"][0] else 0
    for a, b in zip(s["shots"], s["shots"][1:]):
        a["end"] = b["start"]
    last = s["shots"][-1]
    if "end_line" in last and last["end_line"] in L:
        last["end"] = round(L[last["end_line"]]["end"] + last.get("tail", 1.5), 3)
    (FILMS / name / "shots.json").write_text(json.dumps(s, indent=1))
    return {"shots": [(sh["id"], sh["start"], sh["end"]) for sh in s["shots"]]}


@command("variants.hooks", name=("string", "film"))
def variants_hooks(name):
    """Render each hook variant (shots.json "hooks": {id: shot}) as an alternative opening, joined to the rest of the film."""
    d = _film(name); s = _shots(name, resolve=False)
    outs = []
    for hid, hook in (s.get("hooks") or {}).items():
        first = dict(s["shots"][0]); first.update(hook); first["id"] = f"hook_{hid}"
        s2 = dict(s); s2["shots"] = [first] + s["shots"][1:]
        (d / "shots.json").write_text(json.dumps(s2, indent=1))
        try:
            shot_render(name, first["id"])
        finally:
            (d / "shots.json").write_text(json.dumps(s, indent=1))
        lst = d / "build" / "shots" / f"hook_{hid}.txt"
        lst.write_text(f"file '{(d / 'build' / 'shots' / (first['id'] + '.mp4')).resolve()}'\n" + "".join(f"file '{(d / 'build' / 'shots' / (sh['id'] + '.mp4')).resolve()}'\n" for sh in s["shots"][1:]))
        out = d / "build" / f"variant_{hid}.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(d / "build" / "mix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)])
        outs.append(str(out.relative_to(ROOT)))
    return {"variants": outs}


# ---------------- tests ----------------
@command("test", update=("boolean", "rewrite the golden frames instead of comparing", False),
         film=("string", "only cases for this film", ""))
def test_golden(update=False, film=""):
    """Golden-frame regression test: render key frames of benchmark films (SVG player) and compare with tests/golden.
    Frames are pure functions of time, so any difference is a real change."""
    import tempfile
    import numpy as np
    from PIL import Image
    spec = _json(ROOT / "tests" / "golden.json")
    tol = spec.get("tolerance", {"mean_abs": 1.5, "pixels_over_32": 0.004})
    results, failed = [], 0
    tmp = Path(tempfile.mkdtemp(prefix="golden_"))
    for case in spec.get("poses", []):  # loader-level cases: puppets in given poses (bends, controls, views)
        if film and film != "poses":
            continue
        img = tmp / (Path(case).stem + ".png")
        _run(["node", "tools/pose_still.mjs", str(ROOT / case), str(img)], timeout=300)
        g = ROOT / "tests" / "golden" / "poses" / img.name; g.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(img).convert("RGB"); im = im.resize((450, round(450 * im.height / im.width)), Image.LANCZOS)
        if update or not g.exists():
            im.save(g, optimize=True); results.append({"frame": str(g.relative_to(ROOT)), "status": "written"}); continue
        a = np.asarray(im, np.float32); b = np.asarray(Image.open(g).convert("RGB"), np.float32)
        d = np.abs(a - b); mean, over = float(d.mean()), float((d.max(-1) > 32).mean()); ok = mean <= tol["mean_abs"] and over <= tol["pixels_over_32"]
        failed += 0 if ok else 1
        results.append({"frame": str(g.relative_to(ROOT)), "status": "ok" if ok else "FAIL", "mean_abs": round(mean, 3), "pixels_over_32": round(over, 5)})
    if not film or film == "review":   # review room (plan 3.4): notes read right, the critic measures right
        from . import review as RV
        notes = {"raise the arm earlier": "earlier", "Ravi's nod should be bigger": "bigger", "make the wave a bit slower": "slower",
                 "hold the shrug longer": "longer", "lose the point": "remove", "the jump starts too late": "earlier", "this feels off": None}
        bad = [(t, RV.interpret(t, ["ravi"])["verb"], v) for t, v in notes.items() if RV.interpret(t, ["ravi"])["verb"] != v]
        rise = lambda t0: [[i / 30, 100.0, 500.0 - (200.0 if i / 30 >= t0 else 0.0)] for i in range(90)]
        ok_early, _, _, _ = RV.verify({"verb": "earlier"}, 0.33, rise(1.5), rise(1.17))
        ok_wrong, _, _, _ = RV.verify({"verb": "earlier"}, 0.33, rise(1.5), rise(1.5))
        if not ok_early or ok_wrong:
            bad.append(("critic earlier", ok_early, ok_wrong))
        failed += 1 if bad else 0
        results.append({"review": "notes and critic", "status": "FAIL" if bad else "ok", **({"cases": bad} if bad else {})})
    if not film or film == "actout":   # Act it out (plan 3.5): synthetic takes come back as the clips that made them
        from . import actout as AO
        bad, meas = AO.self_test(_json(ROOT / "cast" / "generated" / "ravi.puppet.json"), _json(ROOT / "puppet" / "clips" / "humanoid.json")["clips"])
        failed += 1 if bad else 0
        results.append({"actout": "retarget round trips", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "layout":   # layout QA per style and the AI-look lint (WP-04)
        from . import layout_qa as LQ
        bad, meas = LQ.self_test(ROOT / "out" / "layouttest")
        failed += 1 if bad else 0
        results.append({"layout": "AI-look lint, style thresholds, seeded failures per style", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "levels":   # drawn levels (WP-35): exposure sheets, compiled clips, the loader, Pencil2D import
        from . import levels as LVL
        bad, meas = LVL.self_test(ROOT / "out" / "leveltest")
        pb, pm = LVL.page_check(ROOT / "out" / "drawcheck"); bad += pb; meas["draw_page"] = pm
        pb, pm = LVL.part3_test(ROOT / "out" / "levelpart3"); bad += pb; meas["cleanup_capture_colour"] = pm
        failed += 1 if bad else 0
        results.append({"levels": "timings, compiled clips, drawings over time in the loader, Pencil2D import", "status": "FAIL" if bad else "ok",
                        "measured": {k: v for k, v in meas.items() if k != "cells"}, **({"cases": bad} if bad else {})})
    if not film or film == "oss":   # open-source parts behind commands (WP-34): Pencil2D, libmypaint, Inkscape
        from . import oss as OSS
        bad, meas = OSS.self_test(ROOT / "out" / "osstest")
        failed += 1 if bad else 0
        results.append({"oss": "MyPaint brushes, Pencil2D round trip, Inkscape booleans", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "rparity":   # renderer parity (WP-14): the same shots from every renderer that accepts them
        from . import rparity as RPY
        bad, meas = RPY.self_test(ROOT / "out" / "rparitytest")
        failed += 1 if bad else 0
        results.append({"rparity": "svg, synfig and lottie draw the same characters; refusals say why", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "motion":   # juggling and physics (WP-09): siteswaps, beat grid, deterministic Rapier bakes
        bad, meas = _motion_test()
        failed += 1 if bad else 0
        results.append({"motion": "siteswaps, contacts on the beat grid, Rapier bakes rerun byte-equal", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "interact":   # interaction and locomotion (WP-11): paths, planted feet, IK/FK, handshakes
        bad, meas = _interact_test()
        failed += 1 if bad else 0
        results.append({"interact": "path walks without foot sliding, IK/FK blends, hands that meet", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "parity":   # the parity matrix stays valid (WP-41): commands and work packages it names exist
        from . import parity as PRT
        r = PRT.check()
        failed += 0 if r["ok"] else 1
        results.append({"parity": "matrix references", "status": "ok" if r["ok"] else "FAIL", "measured": r["overall"], **({"cases": r["problems"]} if not r["ok"] else {})})
    if not film or film == "posting":   # posting with a human approval per post (WP-08)
        from . import posting as PST
        bad, meas = PST.self_test(ROOT / "out" / "postingtest_q")
        failed += 1 if bad else 0
        results.append({"posting": "approval gate, held and blocked posts, export and reminder, links close the row", "status": "FAIL" if bad else "ok",
                        "measured": {k: v for k, v in meas.items() if k in ("run", "row")}, **({"cases": bad} if bad else {})})
    if not film or film == "channels":   # several series side by side (WP-32)
        from . import planner as PLN
        bad, meas = PLN.channels_self_test(ROOT / "out" / "channeltest")
        failed += 1 if bad else 0
        results.append({"channels": "two channels, own rules and brands, cross view", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "packaging":   # title, thumbnail and cover lab (WP-07)
        from . import packaging as PKG
        bad, meas = PKG.self_test(ROOT / "out" / "packagingtest")
        failed += 1 if bad else 0
        results.append({"packaging": "truth check, back-catalogue titles, covers", "status": "FAIL" if bad else "ok", "measured": {k: v for k, v in meas.items() if k != "truth"},
                        **({"cases": bad} if bad else {})})
    if not film or film == "licence":   # licence ledger and vendored code (WP-33)
        from . import vendoring as VND
        bad, meas = VND.self_test(ROOT / "out")
        failed += 1 if bad else 0
        results.append({"licence": "classes, vendored records, posting flags", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "research":   # research gates (0.10) and the expert review gate (WP-05)
        from . import research as RSH
        bad, meas = RSH.self_test(ROOT / "out")
        failed += 1 if bad else 0
        results.append({"research": "expert review, omissions, honest labels", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "docs":   # the docs agree with each other and with the registry (WP-01)
        from . import docscheck as DC
        r = DC.check()
        failed += 0 if r["ok"] else 1
        results.append({"docs": "plan, feature map, work packages, registry", "status": "ok" if r["ok"] else "FAIL", "measured": r["counts"],
                        **({"cases": {k: v for k, v in r["problems"].items() if v}} if not r["ok"] else {})})
    if not film or film == "doctor":   # environment doctor (WP-02): every required check passes on this machine
        from . import doctor as DOC
        d = DOC.check(deep=False)
        failed += 0 if d["ok"] else 1
        results.append({"doctor": "required environment", "status": "ok" if d["ok"] else "FAIL", "measured": {"missing_optional": d["missing_optional"]},
                        **({"cases": d["missing_required"], "fixes": d["fixes"]} if not d["ok"] else {})})
    if not film or film == "planner":   # content planner (plan 3.8): the scheduler's quarter passes the independent rule check
        from . import planner as PLN
        bad, meas = PLN.self_test()
        failed += 1 if bad else 0
        results.append({"planner": "spread rules on a synthetic quarter; broken calendars caught", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "production":   # production orchestrator (plan 3.7): worktrees, checkpoints, owner controls, merge
        from . import production as PRD
        bad, meas = PRD.self_test(ROOT / "out")
        failed += 1 if bad else 0
        results.append({"production": "checkpoints, escalation, approval, scoped merge", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "doodle":   # phone-first creator flow (plan 3.6): cuts, a talking rig, drawing requests
        from . import autorig as AR
        from PIL import ImageDraw
        work = ROOT / "out" / "doodletest"; bad, meas = AR.self_test(work)
        im, _ = AR.synthetic_doodle("cat"); im.save(work / "cat_photo.png")
        snap = doodle_snap(str((work / "cat_photo.png").relative_to(ROOT)), "Miso")
        __import__("shutil").rmtree(DOODLES / snap["id"]); snap = doodle_snap(str((work / "cat_photo.png").relative_to(ROOT)), "Miso")   # a clean queue
        pz = _json(ROOT / snap["puppet"]); sw = pz.get("swaps", {})
        if set(pz["parts"]) < {"head", "arm_L", "arm_R", "tail", "body"} or set(sw.get("eyes", {}).get("shapes", {})) != {"open", "half", "closed"} \
                or not {"closed", "small", "mid", "wide", "O", "FV", "smile"} <= set(sw.get("mouth", {}).get("shapes", {})):
            bad.append(f"snap: parts {sorted(pz['parts'])}, swaps {({k: sorted(v.get('shapes', {})) for k, v in sw.items()})}")
        q = drawing_requests(snap["puppet"]); rq = next((r for r in q["requests"] if r.get("swap") == "brows" and r.get("shape") == "raised"), None)
        meas["requests"] = {"open": q["open"], "rig_canvas": q["rig_canvas"]}
        if not rq or not (ROOT / rq.get("ghost", "")).is_file():
            bad.append("requests: no raised-brows request with a ghost guide")
        else:
            W, H = pz["artboard"]; dr = Image.new("RGBA", (int(W), int(H)), (0, 0, 0, 0)); g = ImageDraw.Draw(dr); x0, y0, x1, y1 = rq["box"]
            for a0 in (x0 + 0.1 * (x1 - x0), x0 + 0.6 * (x1 - x0)):
                g.arc([a0, y0 + 0.3 * (y1 - y0), a0 + 0.3 * (x1 - x0), y0 + 0.9 * (y1 - y0)], 200, 340, fill=(20, 20, 20, 255), width=6)
            dr.save(work / "brows.png")
            r = drawing_fulfil(snap["puppet"], rq["id"], str((work / "brows.png").relative_to(ROOT)))
            meas["fulfil"] = {"verified": r["verified"], "now_free": r["now_free"]}
            if not r["verified"] or "emotion happy" not in r["now_free"]:
                bad.append(f"fulfil: {r['verified']}, now free {r['now_free']}")
        if (Path(VOICES) / "kokoro" / "voices-v1.0.bin").exists():
            sy = doodle_say(snap["puppet"], "Hi! I'm Miso.")
            meas["say"] = {"visemes": sy["visemes"], "seconds": sy["duration"], "clips": [c["clip"] for c in sy["timeline"]["clips"]]}
            if sy["visemes"] < 5 or "wave_R" not in meas["say"]["clips"] or "hop" not in meas["say"]["clips"]:
                bad.append(f"say: {meas['say']}")
        failed += 1 if bad else 0
        results.append({"doodle": "auto cuts, talking rig, drawing requests", "status": "FAIL" if bad else "ok", "measured": meas, **({"cases": bad} if bad else {})})
    if not film or film == "timeline":   # Studio timeline re-timing (plan 3.1): anchored edits stay anchored
        tmx = {"lines": [{"id": "a", "start": 1.0, "end": 2.0}, {"id": "b", "start": 4.0, "end": 5.5}]}
        cases = [(("a.start+0.2", 1.5), "a.start+0.5"), (("a.end", 2.4), "a.end+0.4"), (("a.start", 4.3), "b.start+0.3"), ((0.7, 3.0), 3.0)]
        bad = [(c, _retime(c[0], c[1], tmx), want) for c, want in cases if _retime(c[0], c[1], tmx) != want]
        failed += 1 if bad else 0
        results.append({"timeline": "retime", "status": "FAIL" if bad else "ok", **({"cases": bad} if bad else {})})
    for case in spec.get("lint", []):  # visual-lint cases: a film staged badly on purpose; the expected checks must fire
        if film and film != "lint":
            continue
        import shutil
        c = _json(ROOT / case); tmpname = "_lint_case"; dst = FILMS / tmpname
        shutil.rmtree(dst, ignore_errors=True); shutil.copytree(FILMS / c["film"], dst, ignore=shutil.ignore_patterns("build"))
        try:
            sj = _json(dst / "shots.json")
            for path, val in c.get("set", []):
                o = sj
                for k in path[:-1]:
                    o = o[k]
                if val is None:
                    o.pop(path[-1], None)
                else:
                    o[path[-1]] = val
            (dst / "shots.json").write_text(json.dumps(sj))
            li = film_lint(tmpname)
        finally:
            shutil.rmtree(dst, ignore_errors=True)
        got = {(i["check"], i["who"], i["level"]) for i in li.get("issues", [])}
        missing = [e for e in c["expect"] if tuple(e) not in got]
        extra = sorted({g for g in got if g[2] == "error" and list(g) not in c["expect"]})
        ok = "issues" in li and not missing and not extra
        failed += 0 if ok else 1
        results.append({"lint": case, "status": "ok" if ok else "FAIL", **({"missing": missing, "unexpected_errors": extra, "error": li.get("error")} if not ok else {})})
    for case in spec.get("imports", []):  # drawing-import round trips: puppet -> layered file -> puppet, pivots compared
        if film and film != "imports":
            continue
        src = tmp / ("rt_" + Path(case["puppet"]).stem + "." + case.get("format", "svg"))
        _run([PY, "dbe/layers_export.py", str(ROOT / case["puppet"]), str(src)], timeout=300)
        back = tmp / "rt.puppet.json"
        rep = json.loads(_run([PY, "dbe/drawing_import.py", str(src), str(back)], timeout=300)[-1])
        a, b = _json(ROOT / case["puppet"]), _json(back)
        errs = {k: round(((v["pivot"][0] - b["parts"][k]["pivot"][0]) ** 2 + (v["pivot"][1] - b["parts"][k]["pivot"][1]) ** 2) ** 0.5, 1)
                for k, v in a["parts"].items() if k in b["parts"]}
        worst = max(errs.values()) if errs else 1e9
        ok = not rep["unmatched"] and len(errs) == len(a["parts"]) and worst <= case.get("max_pivot_error", 30)
        failed += 0 if ok else 1
        results.append({"import": f"{case['puppet']} via {case.get('format', 'svg')}", "status": "ok" if ok else "FAIL",
                        "mean_pivot_error": round(sum(errs.values()) / max(1, len(errs)), 1), "max_pivot_error": worst, "unmatched": rep["unmatched"]})
    for case in spec["cases"]:
        if film and case["film"] != film:
            continue
        page = _player_page(case["film"])
        prefix = tmp / f"{case['film']}_{case['shot']}"
        _run(["node", "tools/stills.mjs", str(page), f"shot={case['shot']}", str(prefix), *[str(t) for t in case["times"]]], timeout=600)
        gdir = ROOT / "tests" / "golden" / case["film"]; gdir.mkdir(parents=True, exist_ok=True)
        for t in case["times"]:
            im = Image.open(f"{prefix}_{t}.png").convert("RGB")
            im = im.resize((270, round(270 * im.height / im.width)), Image.LANCZOS)
            g = gdir / f"{case['shot']}_{t}.png"
            if update or not g.exists():
                im.save(g, optimize=True); results.append({"frame": str(g.relative_to(ROOT)), "status": "written"}); continue
            a = np.asarray(im, np.float32); b = np.asarray(Image.open(g).convert("RGB"), np.float32)
            if a.shape != b.shape:
                failed += 1; results.append({"frame": str(g.relative_to(ROOT)), "status": "FAIL", "why": f"size {a.shape} vs {b.shape}"}); continue
            d = np.abs(a - b); mean, over = float(d.mean()), float((d.max(-1) > 32).mean())
            ok = mean <= tol["mean_abs"] and over <= tol["pixels_over_32"]
            if not ok:
                failed += 1
                Image.fromarray(np.clip(d * 4, 0, 255).astype(np.uint8)).save(gdir / f"{case['shot']}_{t}.diff.png")
            results.append({"frame": str(g.relative_to(ROOT)), "status": "ok" if ok else "FAIL", "mean_abs": round(mean, 3), "pixels_over_32": round(over, 5)})
    return {"passed": failed == 0, "failed": failed, "results": results}


# ---------------- packaging ----------------
def _brief_of(d, s):
    b = dict(s.get("brief") or {})
    if not b.get("title"):
        md = (d / "brief.md").read_text() if (d / "brief.md").exists() else ""
        m = re.search(r"^#\s*(?:Brief\s*[—:-]\s*)?(.+)$", md, re.M)
        b["title"] = (m.group(1).strip() if m else s.get("title", d.name))
    return b


@command("film.package", name=("string", "film"),
         cover_t=("number", "time of the cover frame (default: brief.cover_t, else the end of the first line)", None))
def film_package(name, cover_t=None):
    """Posting package for a finished film: per-platform captions (takeaway first, sources in a pinned comment,
    hashtags last), title, description with chapters, alt text, cover image, subtitles and a 48-hour checklist.
    Writes build/package/ (posts.md, package.json, cover.png). Wording is a data-filled draft for the editor agent."""
    from PIL import Image, ImageDraw, ImageFont
    d = _film(name); s = _shots(name); tm = _json(d / "timing.json", {})
    final = d / "build" / "final.mp4"
    if not final.exists():
        raise FileNotFoundError("render the film first (film.render)")
    b = _brief_of(d, s); prof = _json(ROOT / "dbe" / "profiles.json")["platforms"]
    lines = tm.get("lines", [])
    takeaway = b.get("takeaway") or (lines[0]["text"] if lines else b["title"])
    hook = b.get("hook") or ""
    tags = [t if t.startswith("#") else "#" + t for t in b.get("hashtags", [])]
    part = f" Part {b['part']} of {b['parts']}." if b.get("part") and b.get("parts") else ""
    facts = _json(d / "facts.json", {"facts": []}).get("facts", [])
    srcs = sorted({f.get("source") for f in facts if f.get("source")})
    pinned = ("Sources: " + "; ".join(srcs)) if srcs else ""
    credits = film_credits(name)["credits"]
    # chapters: YouTube needs >= 3, the first at 0:00, each >= 10 s
    shots = s["shots"]; chapters = []
    if len(shots) >= 3 and all(x["end"] - x["start"] >= 10 for x in shots):
        for x in shots:
            nm = x.get("title") or next((l["text"] for l in lines if l["start"] >= x["start"] - 0.3), x["id"])
            chapters.append(f"{int(x['start'] // 60)}:{int(x['start'] % 60):02d} {nm[:60]}")
    names = []
    for x in shots:
        for c in x.get("cast", []):
            pz = _json(ROOT / c["puppet"], {}); nm = pz.get("name")
            if nm and nm not in names:
                names.append(nm)
    sets = sorted({x.get("set", "plain") for x in shots})
    alt = b.get("alt") or f"Animated short: {', '.join(names) or 'characters'} in a {' and '.join(sets)} setting. {takeaway}"
    # cover: chosen frame (never the platform default), optional cover text inside the safe area
    pk = d / "build" / "package"; pk.mkdir(parents=True, exist_ok=True)
    ct = cover_t if cover_t is not None else b.get("cover_t", lines[0]["end"] if lines else 1.0)
    _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ct:.3f}", "-i", str(final), "-frames:v", "1", str(pk / "cover.png")])
    if b.get("cover_text"):
        im = Image.open(pk / "cover.png").convert("RGB"); W, H = im.size; dr = ImageDraw.Draw(im)
        txt = b["cover_text"].upper(); x0, y0 = (64, 260) if H > W else (int(W * 0.05), int(H * 0.08))
        safe_w = (960 - 64) if H > W else int(W * 0.9); fs = 110 if H > W else 90
        while fs > 30 and ImageFont.truetype(str(ROOT / "engine" / "fonts" / "Fredoka.ttf"), fs).getlength(txt) + 20 > safe_w:
            fs -= 4  # fit the cover text inside the platform-safe width
        f = ImageFont.truetype(str(ROOT / "engine" / "fonts" / "Fredoka.ttf"), fs)
        dr.text((x0, y0), txt, font=f, fill="#ffffff", stroke_width=10, stroke_fill="#24160e")
        im.save(pk / "cover.png")
    from . import packaging as PK
    tl = PK.load(d); ci = (tl.get("chosen") or {}).get("title")
    title = tl["titles"][ci]["text"] if ci is not None and ci < len(tl["titles"]) else b["title"]
    tcheck = PK.check_title(title, PK.support_of(d), _film_format(d))   # WP-07: the posted title is true of the film
    cov = d / "build" / "package" / "covers" / "covers.json"
    if cov.exists():
        pkg_covers = {f"{c['cut']}--{c['platform']}": c["file"] for c in _json(cov)["covers"]}
    else:
        pkg_covers = {}
    checks = {"title_true": tcheck["ok"], "title_under_50_chars": len(title) <= 50, "has_takeaway": bool(b.get("takeaway")), "has_sources": bool(srcs) or not facts,
              "cover_chosen": True, "subtitles": (d / "build" / "captions.srt").exists()}
    posts = {}
    for k, pf in prof.items():
        n = pf.get("hashtags", 4)
        body = f"{takeaway}{part}" + (f" {hook}" if hook else "")
        posts[k] = {"caption": body + ("\n\n" + " ".join(tags[:n]) if tags else ""), "aspect": pf["aspect"], "captions": pf["captions"],
                    **({"title": title, "description": body + ("\n\n" + "\n".join(chapters) if chapters else "") + ("\n\n" + pinned if pinned else "")} if k == "youtube" else {})}
    pkg = {"film": name, "title": title, "takeaway": takeaway, "posts": posts, "pinned_comment": pinned, "alt_text": alt,
           "chapters": chapters, "cover": "build/package/cover.png", "covers": pkg_covers, "title_problems": tcheck["truth"]["problems"] + tcheck["newcomer"]["problems"],
           "video": "build/final.mp4", "subtitles": ["build/captions.srt", "build/captions.vtt"],
           "post_date": b.get("post_date"), "engagement_prompt": b.get("prompt"), "credits": credits, "checks": checks}
    md = [f"# Posts: {title}", "", f"Video `build/final.mp4` · cover `build/package/cover.png` (upload it; don't use the platform default) · subtitles `build/captions.srt`",
          f"Post date: {b.get('post_date') or 'not set'}", "", "Draft generated from the film's data. Check every word of the title and captions is literally true of the film.", ""]
    for k, v in posts.items():
        md += [f"## {k}", "", *(["**Title:** " + v["title"], ""] if "title" in v else []), "> " + v["caption"].replace("\n", "\n> "), ""]
        if "description" in v:
            md += ["**Description:**", "", "```", v["description"], "```", ""]
    md += ["## Pinned comment", "", "> " + (pinned or "(no sources: add facts.json sources)"), "", "## Alt text", "", alt, ""]
    if b.get("prompt"):
        md += ["## Engagement prompt (reply to your own comment)", "", "> " + b["prompt"], ""]
    md += ["## Credits", "", *credits, "", "## 48-hour checklist", "",
           "- Views, average view duration and retention at 3 s / 50% / end, per platform",
           "- Shares and saves per 1,000 views; comments that show a misunderstanding (note them for a follow-up)",
           "- Which hook and cover were used; whether the title needs a (true) alternative",
           "- Any factual correction: log it on the film's page with the date, and fix every caption"]
    (pk / "posts.md").write_text("\n".join(md) + "\n"); (pk / "package.json").write_text(json.dumps(pkg, indent=1))
    prov = film_provenance(name)   # WP-33: inputs whose terms restrict a public film are flagged for the owner
    return {"package": str((pk / "posts.md").relative_to(ROOT)), "checks": checks, "chapters": len(chapters),
            "posting_flags": prov["flags"], "clear_to_post": prov["clear_to_post"]}


# ---------------- title, thumbnail and cover lab (plan 3.9, WP-07) ----------------
def _film_format(d):
    return _json(d / "script.json", {}).get("format")


@command("title.check", name=("string", "film"), text=("string", "a title to check", ""),
         top=("string", "thumbnail top line", ""), bottom=("string", "thumbnail bottom line", ""))
def title_check(name, text="", top="", bottom=""):
    """The packaging truth check (WP-07): is a title or a double-barrel thumbnail literally true of the film? Numbers,
    absolutes and causal claims must be in its facts or narration, a claim the film negates is contradicted, a myth
    film may ask its myth or deny it but never state it; plus the newcomer check (length, acronyms, long words,
    insider wording, emoji). Questions make no claim."""
    from . import packaging as PK
    d = _film(name); sup = PK.support_of(d); fmt = _film_format(d); out = {}
    if text:
        out["title"] = {"text": text, **PK.check_title(text, sup, fmt)}
    if top or bottom:
        out["thumbnail"] = {"top": top, "bottom": bottom, **PK.thumb_check(top, bottom, sup, fmt)}
    if not out:
        raise ValueError("give text, or top and bottom")
    out["ok"] = all(v["ok"] for v in out.values() if isinstance(v, dict))
    return out


@command("title.set", name=("string", "film"), titles=("array", "title candidates (strings)", None),
         thumbnails=("array", "double-barrel thumbnail texts: [{top, bottom}]", None), by=("string", "who wrote them (agent or person)", "agent"),
         chosen=("object", "{title: index, thumbnail: index} to use in the package (must pass)", None))
def title_set(name, titles=None, thumbnails=None, by="agent", chosen=None):
    """Record title and thumbnail candidates in films/<name>/titles.json with their checks (WP-07). Candidates that
    fail are kept with their problems so the next writer sees why; the chosen ones must pass. Returns how many pass."""
    from . import packaging as PK
    d = _film(name); sup = PK.support_of(d); fmt = _film_format(d); t = PK.load(d)
    for x in titles or []:
        t["titles"] = [y for y in t["titles"] if y["text"] != x] + [{"text": x, "by": by, "checks": PK.check_title(x, sup, fmt)}]
    for x in thumbnails or []:
        t["thumbnails"] = [y for y in t["thumbnails"] if (y["top"], y["bottom"]) != (x["top"], x["bottom"])] + \
                          [{"top": x["top"], "bottom": x["bottom"], "by": by, "checks": PK.thumb_check(x["top"], x["bottom"], sup, fmt)}]
    for y in t["titles"]:   # re-check old candidates against today's facts
        y["checks"] = PK.check_title(y["text"], sup, fmt)
    for y in t["thumbnails"]:
        y["checks"] = PK.thumb_check(y["top"], y["bottom"], sup, fmt)
    ch = dict(t.get("chosen") or {}); ch.update(chosen or {})
    for k, lst in (("title", t["titles"]), ("thumbnail", t["thumbnails"])):
        if k in ch and not (0 <= ch[k] < len(lst) and lst[ch[k]]["checks"]["ok"]):
            raise ValueError(f"the chosen {k} must be a candidate that passes the checks")
        if k not in ch:   # default: the first that passes
            ok = [i for i, y in enumerate(lst) if y["checks"]["ok"]]
            if ok:
                ch[k] = ok[0]
    t["chosen"] = ch
    (d / "titles.json").write_text(json.dumps(t, indent=1, ensure_ascii=False))
    return {"titles_passing": sum(y["checks"]["ok"] for y in t["titles"]), "thumbnails_passing": sum(y["checks"]["ok"] for y in t["thumbnails"]),
            "failing": [{"text": y.get("text") or f"{y['top']} / {y['bottom']}", "problems": y["checks"].get("problems") or y["checks"]["truth"]["problems"] + y["checks"]["newcomer"]["problems"]}
                        for y in t["titles"] + t["thumbnails"] if not y["checks"]["ok"]], "chosen": ch}


@command("title.propose", name=("string", "film"))
def title_propose(name):
    """Draft packaging for an agent to improve (WP-07): mechanical candidates from the film (its question, its hook,
    its first fact), each with its checks, plus the brief for a writer: two titles for a newcomer that are literally
    true, two double-barrel thumbnails, then title.set."""
    from . import packaging as PK
    d = _film(name); s = _shots(name, resolve=False); b = _brief_of(d, s); sup = PK.support_of(d); fmt = _film_format(d)
    sc = _json(d / "script.json", {}); lines = [l["text"] for l in sc.get("lines", [])]
    cands = [b["title"]] + [l for l in lines if l.endswith("?") and 3 <= len(l.split()) <= 10][:2]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c); out.append({"text": c, **PK.check_title(c, sup, fmt)})
    return {"film": name, "format": fmt, "candidates": out, "support": sup[:12],
            "writer_brief": ("Write two titles a newcomer would click that are literally true of this film (its facts and narration "
                             "above): plain words, at most 60 characters, no episode numbers or insider wording, no emoji; a question "
                             "is fine; a myth film asks or denies its myth. Write two double-barrel thumbnails (top and bottom, at most "
                             "4 words each) that are true together. Then: python -m dbe title.set '{\"name\": \"%s\", \"titles\": [...], "
                             "\"thumbnails\": [{\"top\": ..., \"bottom\": ...}]}'" % name)}


def _cuts_of(name):
    """every finished cut of a film: the master, a sound-off cut, episode and teaser cuts, other aspects"""
    d = FILMS / name; size = _json(d / "shots.json", {}).get("size", [1080, 1920])   # older films have no shots.json
    asp = next((k for k, v in ASPECT_SIZE.items() if v == size), "9:16")
    out = {}
    if (d / "build" / "final.mp4").exists():
        out["master"] = {"video": d / "build" / "final.mp4", "aspect": asp}
    for f in sorted((d / "build").glob("final_*.mp4")):
        tag = f.stem[len("final_"):]
        a = tag.replace("x", ":") if re.fullmatch(r"\d+x\d+", tag) else asp
        out[tag] = {"video": f, "aspect": a}
    for f in sorted((d / "build" / "cuts").glob("*.mp4")) if (d / "build" / "cuts").exists() else []:
        out[f"cut-{f.stem}"] = {"video": f, "aspect": asp}
    for a in ASPECT_SIZE:
        alt = FILMS / f"{name}--{a.replace(':', 'x')}" / "build" / "final.mp4"
        if alt.exists() and a != asp:
            out[f"master-{a.replace(':', 'x')}"] = {"video": alt, "aspect": a}
    return out


def _duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip().splitlines()[-1])


@command("cover.make", name=("string", "film"), thumbnail=("integer", "thumbnail index in titles.json (default: the chosen one)", -1))
def cover_make(name, thumbnail=-1):
    """Deliberate covers (WP-07): for every finished cut and every platform, the best frame of that cut (least bare
    ground, a character on screen, away from cuts and the ends), with the chosen double-barrel thumbnail text in the
    brand kit inside the platform-safe area. A platform in another aspect gets the cut in that aspect when one was
    rendered, else the frame on the brand's paper. Writes build/package/covers/<cut>--<platform>.png and covers.json."""
    from . import packaging as PK
    d = _film(name); t = PK.load(d); s = _shots(name)
    i = thumbnail if thumbnail >= 0 else (t.get("chosen") or {}).get("thumbnail")
    if i is None or not (0 <= i < len(t["thumbnails"])):
        raise ValueError("no thumbnail text: title.set it first (title.propose drafts the brief)")
    th = t["thumbnails"][i]
    if not th["checks"]["ok"]:
        raise ValueError(f"the thumbnail text fails its checks: {th['checks']['problems']}")
    cuts = _cuts_of(name)
    if not cuts:
        raise FileNotFoundError("render the film first (film.render)")
    brand = _brand_kit(_json(d / "shots.json", {})) or _json(ROOT / "brand" / "brand.json", {})   # the film's own brand kit (WP-32)
    plats = _json(ROOT / "dbe" / "profiles.json")["platforms"]
    out_dir = d / "build" / "package" / "covers"; out_dir.mkdir(parents=True, exist_ok=True)
    shot_cuts = [x["start"] for x in s["shots"][1:]]
    cast_t = [(x["start"], x["end"]) for x in s["shots"] if x.get("cast") or any(o.get("type") == "face" for o in x.get("overlays", []))]
    picks, made = {}, []
    for cid, c in cuts.items():
        dur = _duration(c["video"])
        tt, score, _ = PK.pick_frame(c["video"], shot_cuts if cid.startswith("master") or cid == "soundoff" else [], dur,
                                     cast_t if (cid.startswith("master") and cast_t) else None)
        if tt is None:
            tt, score = dur / 2, None
        fr = out_dir / f"_{cid}.png"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.3f}", "-i", str(c["video"]), "-frames:v", "1", str(fr)])
        picks[cid] = {"t": tt, "score": score, "aspect": c["aspect"], "frame": fr}
    base_cuts = [k for k in cuts if not re.match(r"master-\d+x\d+$", k)]
    for cid in base_cuts:
        for pn, pf in plats.items():
            want = pf["aspect"].split(" or ")[0]
            src = picks[cid]
            alt = f"master-{want.replace(':', 'x')}"
            if src["aspect"] != want and cid == "master" and alt in picks:
                src = picks[alt]
            o = out_dir / f"{cid}--{pn}.png"
            info = PK.make_cover(src["frame"], o, want, th["top"], th["bottom"], brand)
            made.append({"cut": cid, "platform": pn, "aspect": want, "file": str(o.relative_to(ROOT)), "frame_t": src["t"],
                         "from": "own aspect" if src["aspect"] == want else "on paper", **info})
    for p_ in out_dir.glob("_*.png"):
        p_.unlink()
    (out_dir / "covers.json").write_text(json.dumps({"thumbnail": {k: th[k] for k in ("top", "bottom")}, "covers": made}, indent=1))
    return {"covers": len(made), "cuts": base_cuts, "platforms": list(plats), "frames": {k: v["t"] for k, v in picks.items()}, "files": [m["file"] for m in made]}


@command("titles.status", films=("array", "films (default: every film with a script)", None))
def titles_status(films=None):
    """The back catalogue (WP-07): per film, how many title and thumbnail candidates pass today's truth check (facts
    change, so old titles are re-checked), whether a cover exists for every cut and platform, and what is missing."""
    from . import packaging as PK
    names = films or sorted(p.name for p in FILMS.iterdir() if (p / "script.json").exists() and "--" not in p.name)
    plats = list(_json(ROOT / "dbe" / "profiles.json")["platforms"])
    rows = []
    for n in names:
        d = FILMS / n; t = PK.load(d); sup = PK.support_of(d); fmt = _film_format(d)
        tp = sum(PK.check_title(y["text"], sup, fmt)["ok"] for y in t["titles"])
        hp = sum(PK.thumb_check(y["top"], y["bottom"], sup, fmt)["ok"] for y in t["thumbnails"])
        cuts = [k for k in _cuts_of(n) if not re.match(r"master-\d+x\d+$", k)]
        cov = [f"{c}--{p}" for c in cuts for p in plats]
        missing = [c for c in cov if not (d / "build" / "package" / "covers" / f"{c}.png").exists()]
        rows.append({"film": n, "titles_passing": tp, "thumbnails_passing": hp, "rendered_cuts": cuts, "covers_missing": len(missing),
                     "ok": tp >= 2 and hp >= 1 and (not cuts or not missing)})
    return {"films": rows, "ok": all(r["ok"] for r in rows), "short": [r["film"] for r in rows if not r["ok"]]}


# ---------------- posting with a human approval per post (plan 4.15, WP-08) ----------------
def _post_at(date, channel=""):
    """a calendar date at the channel's posting time, in its time zone (channel.json post_time and timezone)"""
    import datetime as _dt
    from zoneinfo import ZoneInfo
    from . import planner as PL
    ch = PL.channel(channel)
    hh, mm = map(int, str(ch.get("post_time", "18:30")).split(":"))
    return _dt.datetime.combine(_dt.date.fromisoformat(date), _dt.time(hh, mm), ZoneInfo(ch.get("timezone", "Asia/Colombo"))).isoformat()


@command("post.queue", film=("string", "a finished film (film.package and cover.make done)"), quarter=("string", "the calendar quarter of its row", ""),
         date=("string", "the row's posting date (default: the row whose film this is, or today)", ""), channel=CH_ARG,
         platforms=("array", "only these platforms (default: every platform in dbe/profiles.json)", None),
         require_merged=("boolean", "the film must be approved or merged on the production board", True))
def post_queue(film, quarter="", date="", channel="", platforms=None, require_merged=True):
    """Queue a film's posts (WP-08): one per platform, from its posting package (caption, title, the cover for that
    platform, subtitles, audio tracks of its localised versions) at its calendar row's date and the channel's posting
    time. A post whose package fails (title not true of the film, no subtitles, no sources) or that carries posting
    flags (film.provenance) is marked; nothing is posted until a person approves it (post.approve)."""
    from . import planner as PL, posting as PO, production as PR
    d = _film(film)
    if require_merged:
        st = None
        if (PR.reg_dir() / "registry.json").exists():
            with PR.registry(write=False) as reg:
                st = (reg["films"].get(film) or {}).get("state")
        if st not in ("approved", "merged"):
            raise PermissionError(f"{film} is not approved on the production board ({st or 'not on the board'})")
    row = None
    if quarter:
        cal = _plan_cal(quarter, channel)
        row = next((r for r in cal["rows"] if r.get("idea") and (r["date"] == date if date else r.get("film") == film)), None)
        if not row:
            raise ValueError(f"no row for {film} in {quarter}")
        date = row["date"]
    date = date or _today().isoformat()
    pk = film_package(film)
    pkg = _json(d / "build" / "package" / "package.json")
    covs = {f"{c['cut']}--{c['platform']}": c["file"] for c in _json(d / "build" / "package" / "covers" / "covers.json", {"covers": []})["covers"]}
    if platforms:
        pkg["posts"] = {k: v for k, v in pkg["posts"].items() if k in platforms}
    rowref = {"quarter": quarter, "date": date, "channel": PL.channel(channel)["id"], "title": row["title"]} if row else None
    posts = PO.make_posts(film, pkg, covs, _post_at(date, channel), rowref, pk["posting_flags"])
    with PO.queue() as q:
        for pid, p in posts.items():
            old = q["posts"].get(pid)
            if old and old["state"] in ("exported", "posted"):
                continue
            PO.event(p, "queued", blocked=p["blocked"], flags=len(p["flags"])); q["posts"][pid] = p
    return {"queued": sorted(posts), "post_at": _post_at(date, channel), "blocked": {k: v["blocked"] for k, v in posts.items() if v["blocked"]},
            "flags": pk["posting_flags"]}


@command("post.approve", id=("string", "post id (date-film-platform), or empty with film and date for all of a film's posts that day", ""),
         film=("string", "film", ""), date=("string", "posting date", ""), by=("string", "who approves (a person)", ""),
         accept_flags=("boolean", "the approver accepts the posting flags shown (non-clean voice, restricted inputs)", False),
         note=("string", "", ""))
def post_approve(id="", film="", date="", by="", accept_flags=False, note=""):
    """A person approves a post (WP-08): recorded with their name and the time. A blocked post cannot be approved; a
    post with posting flags only when the approver accepts them by name."""
    from . import posting as PO
    if not by.strip():
        raise ValueError("an approval needs the approver's name")
    out = []
    with PO.queue() as q:
        sel = [q["posts"][id]] if id else [p for p in q["posts"].values() if p["film"] == film and p["post_at"][:10] == date]
        if not sel:
            raise KeyError("no such post")
        for p in sel:
            if p["state"] == "blocked":
                raise PermissionError(f"{p['id']} is blocked: {p['blocked']}")
            if p["flags"] and not accept_flags:
                raise PermissionError(f"{p['id']} has posting flags: {p['flags']}; approve with accept_flags to accept them")
            if p["state"] in ("exported", "posted"):
                continue
            p["state"] = "approved"; p["approval"] = {"by": by, "at": PO.now().isoformat(), "note": note, **({"accepted_flags": p["flags"]} if p["flags"] else {})}
            PO.event(p, "approved", by=by); out.append(p["id"])
    return {"approved": out}


@command("post.revoke", id=("string", "post id"), reason=("string", "why", ""))
def post_revoke(id, reason=""):
    """Withdraw an approval before the post goes out (WP-08)."""
    from . import posting as PO
    with PO.queue() as q:
        p = q["posts"][id]
        if p["state"] in ("exported", "posted"):
            raise ValueError(f"{id} is already {p['state']}")
        p["state"] = "held"; p.pop("approval", None); PO.event(p, "revoked", reason=reason)
    return {"held": id}


@command("post.run", at=("string", "the time to act as now (ISO 8601; default now)", ""))
def post_run(at=""):
    """Send what is due (WP-08): every approved post whose time has come goes through its platform's connector when
    one is configured (productions/connectors.json), otherwise into an export folder (out/posting/<date>/<platform>/
    <film>/: video, cover, caption and title, subtitles, audio tracks, reminder.ics) for a person to post. Posts that
    are due but not approved are held and listed; they never leave."""
    import datetime as _dt
    from . import posting as PO
    t = _dt.datetime.fromisoformat(at) if at else PO.now()
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    out_root = ROOT / "out" / "posting"; cons = PO.connectors(); res = {"exported": [], "posted": [], "held": [], "blocked": []}
    with PO.queue() as q:
        for p in sorted(q["posts"].values(), key=lambda p: p["post_at"]):
            if _dt.datetime.fromisoformat(p["post_at"]) > t:
                continue
            if p["state"] in ("queued", "held"):
                res["held"].append({"id": p["id"], "why": "no approval"}); continue
            if p["state"] == "blocked":
                res["blocked"].append({"id": p["id"], "why": p["blocked"]}); continue
            if p["state"] != "approved":
                continue
            con = (cons.get(p["platform"]) or {}).get("connector")
            if con in PO.CONNECTORS:
                url = PO.CONNECTORS[con](p, out_root)
                p["state"] = "posted"; p["url"] = url; PO.event(p, "posted", connector=con, url=url); res["posted"].append(p["id"])
            else:
                folder, files = PO.export(p, out_root)
                p["state"] = "exported"; p["export"] = str(folder.relative_to(ROOT)); PO.event(p, "exported", folder=p["export"], files=files)
                res["exported"].append({"id": p["id"], "folder": p["export"], "files": files})
        rows_done = _post_rows_done(q)
    res["rows_posted"] = rows_done
    return res


def _post_rows_done(q):
    """mark calendar rows whose posts are all out as posted in the plan, with every link"""
    from . import posting as PO
    done = []
    rows = {(p["row"]["quarter"], p["row"]["date"], p["row"]["channel"]): p["row"] for p in q["posts"].values() if p.get("row")}
    for (qu, dte, ch), row in rows.items():
        ps = PO.row_posts(q, row)
        if ps and all(p["state"] == "posted" for p in ps):
            cal = _plan_cal(qu, ch); r = next((x for x in cal["rows"] if x["date"] == dte and x.get("idea")), None)
            if r and not r.get("posted"):
                links = {p["platform"]: p["url"] for p in ps}
                plan_posted(qu, dte, links.get("youtube") or next(iter(links.values())), ch)
                cal = _plan_cal(qu, ch); r = next(x for x in cal["rows"] if x["date"] == dte and x.get("idea"))
                r["posted"]["links"] = links; _plan_save(f"{qu}.json", cal, ch)
                done.append({"quarter": qu, "date": dte, "channel": ch, "links": links})
    return done


@command("post.done", id=("string", "post id"), url=("string", "the link to the post, as published"))
def post_done(id, url):
    """A person reports a post they published from its export (WP-08); when every post of a calendar row is out, the
    row is marked posted in the plan with all its links."""
    from . import posting as PO
    if not re.match(r"^(https?|dryrun)://", url):
        raise ValueError("give the post's link")
    with PO.queue() as q:
        p = q["posts"][id]
        if p["state"] not in ("exported", "approved"):
            raise PermissionError(f"{id} is {p['state']}: only an approved post can be marked posted")
        p["state"] = "posted"; p["url"] = url; PO.event(p, "posted", url=url, by="person")
        rows = _post_rows_done(q)
    return {"posted": id, "rows_posted": rows}


@command("post.status", state=("string", "filter by state", ""))
def post_status(state=""):
    """The posting queue (WP-08): every post with its time, platform, state, approval, flags and link; counts."""
    from . import posting as PO
    from collections import Counter
    with PO.queue(write=False) as q:
        ps = sorted(q["posts"].values(), key=lambda p: (p["post_at"], p["film"], p["platform"]))
    rows = [{k: p.get(k) for k in ("id", "film", "platform", "post_at", "state", "approval", "flags", "blocked", "url", "export", "row", "cover")} for p in ps if not state or p["state"] == state]
    return {"counts": dict(Counter(p["state"] for p in ps)), "posts": rows}


# ---------------- drawn levels (WP-35, puppet format v0.8) ----------------
def _level_path(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,60}", name):
        raise ValueError("level names are lower-case letters, digits, - and _")
    return ROOT / "cast" / "levels" / f"{name}.puppet.json"


@command("level.make", name=("string", "level name (cast/levels/<name>.puppet.json)"),
         frames=("array", "drawings in order: PNG paths (all the level's size, transparent background)"),
         timing=("string", "ones | twos | threes | fours, or a number of frames per drawing", "twos"),
         holds=("array", "instead of timing: frames to hold each drawing, one per drawing", None),
         fps=("integer", "the level's frame rate", 24), loop=("boolean", "", True), author=("string", "", ""),
         license=("string", "", "LicenseRef-owner"))
def level_make(name, frames, timing="twos", holds=None, fps=24, loop=True, author="", license="LicenseRef-owner"):
    """A drawn level (WP-35): drawings with an exposure sheet, as a puppet a shot casts like any character. Each
    drawing is trimmed to its ink; the xsheet (timing on ones, twos or threes, or holds per drawing) compiles into the
    level's clip "play", which every renderer plays. Cast it with "timeline": {"clips": [{"clip": "play", "start": 0}]}."""
    from PIL import Image
    from . import levels as LV
    fs = [ROOT / f if not Path(f).is_absolute() else Path(f) for f in frames]
    size = list(Image.open(fs[0]).size)
    tm = holds if holds else (int(timing) if str(timing).isdigit() else timing)
    p = LV.make(name, [{"png": str(f)} for f in fs], size, tm, fps, loop, author, license)
    errs = _puppet_errors(p)
    if errs:
        raise ValueError(f"level does not validate: {errs[:3]}")
    out = _level_path(name); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(p, separators=(",", ":")))
    x = p["swaps"]["level"]["xsheet"]
    return {"puppet": str(out.relative_to(ROOT)), "drawings": len(p["swaps"]["level"]["shapes"]), "frames": len(x["cells"]),
            "seconds": round(len(x["cells"]) / fps, 3), "xsheet": LV.runs(x["cells"])}


@command("level.xsheet", name=("string", "level"), timing=("string", "ones | twos | threes | fours, or frames per drawing", ""),
         cells=("array", "explicit exposure cells, one drawing name per frame", None), fps=("integer", "", 0), loop=("boolean", "", True))
def level_xsheet(name, timing="", cells=None, fps=0, loop=True):
    """Retime a drawn level (WP-35): new holds for every drawing, or an explicit exposure sheet (one drawing per
    frame: runs are holds, drawings may repeat); the level's clip is recompiled. Without changes, returns the sheet."""
    from . import levels as LV
    f = _level_path(name); p = _json(f)
    if timing or cells is not None or fps:
        LV.set_xsheet(p, timing=(int(timing) if str(timing).isdigit() else timing) or None, cells=cells, fps=fps or None, loop=loop)
        f.write_text(json.dumps(p, separators=(",", ":")))
    x = p["swaps"]["level"]["xsheet"]
    return {"fps": x["fps"], "frames": len(x["cells"]), "seconds": round(len(x["cells"]) / x["fps"], 3), "loop": x.get("loop", True), "xsheet": LV.runs(x["cells"])}


@command("level.from_pencil2d", name=("string", "level name"), file=("string", "a Pencil2D project (.pclx)"),
         fps=("integer", "the project's frame rate", 24), end=("string", "last frame, or last", "last"))
def level_from_pencil2d(name, file, fps=24, end="last"):
    """Bring a hand-drawn Pencil2D animation in as a drawn level (WP-35, via WP-34): Pencil2D renders it headless,
    identical consecutive frames become one drawing held for that many frames, so the artist's timing is kept."""
    import shutil as _sh
    import tempfile
    from . import levels as LV, oss
    with tempfile.TemporaryDirectory() as td:
        fr = oss.pencil2d_render(ROOT / file if not Path(file).is_absolute() else Path(file), Path(td) / "f", end=end)
        ds, cells = LV.from_frames(fr)
        h, w = ds[0]["rgba"].shape[:2]
        p = LV.make(name, ds, (w, h), 1, fps)
        LV.set_xsheet(p, cells=cells)
    errs = _puppet_errors(p)
    if errs:
        raise ValueError(f"level does not validate: {errs[:3]}")
    out = _level_path(name); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(p, separators=(",", ":")))
    return {"puppet": str(out.relative_to(ROOT)), "drawings": len(ds), "frames": len(cells), "xsheet": LV.runs(cells)}


@command("level.list")
def level_list():
    """Drawn levels in cast/levels (WP-35): name, size, drawings, frames, fps."""
    out = []
    for f in sorted((ROOT / "cast" / "levels").glob("*.puppet.json")):
        p = _json(f); x = p["swaps"]["level"].get("xsheet") or {}
        out.append({"name": f.name[:-len(".puppet.json")], "size": p["artboard"], "drawings": len(p["swaps"]["level"]["shapes"]),
                    "frames": len(x.get("cells", [])), "fps": x.get("fps")})
    return out


@command("level.new", name=("string", "level name"), size=("array", "[width, height] in pixels", [720, 720]), fps=("integer", "", 24))
def level_new(name, size=None, fps=24):
    """Start an empty drawn level (WP-35) to draw on the Studio drawing page: one blank drawing on one frame."""
    from . import levels as LV
    f = _level_path(name)
    if f.exists():
        raise FileExistsError(f"level {name} exists")
    W, H = size or [720, 720]
    p = LV.make(name, [{"name": "d01", "strokes": []}], (W, H), 1, fps, ground=H)
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(p, separators=(",", ":")))
    return {"puppet": str(f.relative_to(ROOT)), "size": [W, H], "fps": fps}


@command("level.get", name=("string", "level"))
def level_get(name):
    """A drawn level for the Studio drawing page (WP-35): size, fps, the exposure cells and every drawing (its raster
    strokes, positioned in the level's pixels)."""
    p = _json(_level_path(name)); sw = p["swaps"]["level"]
    return {"name": name, "size": p["artboard"], "ground": p.get("ground"), "fps": sw["xsheet"]["fps"], "cells": sw["xsheet"]["cells"],
            "loop": sw["xsheet"].get("loop", True),
            "drawings": {k: [st for st in v if "image" in st and st.get("role", "line") != "paint"] for k, v in sw["shapes"].items()},
            "paint": {k: [st for st in v if st.get("role") == "paint"] for k, v in sw["shapes"].items()},
            "styles": (sw.get("paint") or {}).get("styles", {}), "seeds": (sw.get("paint") or {}).get("seeds", {})}


@command("level.draw", name=("string", "level"), drawing=("string", "drawing name (a new name adds a drawing)"),
         png=("string", "the whole drawing as a PNG data URI at the level's size (transparent background)", ""),
         place_after=("string", "for a new drawing: expose it after this drawing's run in the sheet (default: at the end)", ""),
         hold=("integer", "frames to expose a new drawing", 2))
def level_draw(name, drawing, png="", place_after="", hold=2):
    """Save one drawing of a drawn level (WP-35), as the Studio drawing page sends it; a new drawing is exposed in
    the sheet after the given drawing (or at the end) for `hold` frames; the level's clip is recompiled."""
    import base64
    import io
    import numpy as np
    from PIL import Image
    from . import levels as LV
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", drawing):
        raise ValueError("drawing names are letters, digits, - and _")
    f = _level_path(name); p = _json(f); sw = p["swaps"]["level"]; W, H = p["artboard"]
    st = []
    if png:
        a = np.asarray(Image.open(io.BytesIO(base64.b64decode(png.split(",", 1)[1]))).convert("RGBA"))
        if a.shape[1] != W or a.shape[0] != H:
            raise ValueError(f"the drawing is {a.shape[1]}x{a.shape[0]}; the level is {W}x{H}")
        r = LV.raster_stroke(a); st = [r] if r else []
    new = drawing not in sw["shapes"]
    sw["shapes"][drawing] = st
    cells = list(sw["xsheet"]["cells"])
    if new:
        at = len(cells)
        if place_after and place_after in cells:
            at = max(i for i, c in enumerate(cells) if c == place_after) + 1
        cells[at:at] = [drawing] * max(1, hold)
    lows = [s_["y"] + s_["h"] for sh in sw["shapes"].values() for s_ in sh if "h" in s_]
    p["ground"] = max(lows) if lows else H
    LV.set_xsheet(p, cells=cells)
    if ((sw.get("paint") or {}).get("seeds") or {}).get(drawing):   # its colours follow the redrawn lines
        LV.recolour(p)
    f.write_text(json.dumps(p, separators=(",", ":")))
    return {"drawing": drawing, "new": new, "drawings": len(sw["shapes"]), "frames": len(cells), "inked": bool(st)}


@command("level.cleanup", name=("string", "level"), drawings=("array", "drawings to clean (default: all)", None),
         keep=("number", "strokes fainter than this (0-1 alpha) are construction lines and go", 0.45),
         min_speck=("integer", "ink islands smaller than this many pixels go", 12), ink=("string", "one ink colour for every line (empty: keep)", ""))
def level_cleanup(name, drawings=None, keep=0.45, min_speck=12, ink=""):
    """Clean rough drawings (WP-35): faint construction lines and specks go, the lines that stay are inked at full
    strength with their soft edges; paint is redone from the level's colour styles."""
    from . import levels as LV
    f = _level_path(name); p = _json(f); sw = p["swaps"]["level"]; W, H = p["artboard"]; out = {}
    for d in drawings or list(sw["shapes"]):
        a = LV.drawing_rgba(p, d, role="line")
        before = int((a[..., 3] > 0).sum())
        c = LV.clean_rgba(a, keep, min_speck, ink or None)
        st = LV.raster_stroke(c)
        sw["shapes"][d] = [x for x in sw["shapes"][d] if x.get("role") == "paint"] + ([st] if st else [])
        out[d] = {"ink_px_before": before, "ink_px_after": int((c[..., 3] > 0).sum())}
    LV.recolour(p)
    f.write_text(json.dumps(p, separators=(",", ":")))
    return {"cleaned": out}


@command("level.capture", name=("string", "level"), drawing=("string", "drawing name (a new name adds a drawing)"),
         photo=("string", "a photo or scan of the drawing on paper (path)"), place_after=("string", "", ""), hold=("integer", "", 2),
         register=("boolean", "line it up with the drawing before it (a digital peg bar)", True), ink=("string", "", "#24160e"))
def level_capture(name, drawing, photo, place_after="", hold=2, register=True, ink="#24160e"):
    """A pencil test (WP-35): a photo of a drawing on paper becomes a drawing of the level: lighting and paper are
    removed, the ink is fitted into the frame, and the drawing is lined up with the one before it in the sheet so a
    sequence of photos plays without jitter."""
    import base64
    import io
    import numpy as np
    from PIL import Image
    from . import levels as LV
    f = _level_path(name); p = _json(f); sw = p["swaps"]["level"]; W, H = p["artboard"]
    rgb = np.asarray(Image.open(ROOT / photo if not Path(photo).is_absolute() else Path(photo)).convert("RGB"))
    a = LV.photo_to_ink(rgb, (W, H), ink)
    prev = place_after or (sw["xsheet"]["cells"][-1] if sw["xsheet"]["cells"] else None)
    moved = [0, 0]
    if register and prev and prev in sw["shapes"] and prev != drawing:
        ref = LV.drawing_rgba(p, prev, role="line")
        if (ref[..., 3] > 0).any():
            dx, dy = LV.register(ref, a, max_shift=max(W, H) // 6); a = LV.shift(a, dx, dy); moved = [dx, dy]
    buf = io.BytesIO(); Image.fromarray(a, "RGBA").save(buf, "PNG")
    r = level_draw(name, drawing, "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), place_after or prev or "", hold)
    return {**r, "registered_by": moved}


@command("level.colour", name=("string", "level"), styles=("object", "colour styles {id: colour}; changing one repaints every drawing", None),
         seeds=("object", "{drawing: [[x, y, style], ...]}: paint the closed area under each point", None),
         propagate_from=("string", "carry this drawing's painted areas to every other drawing in sheet order", ""))
def level_colour(name, styles=None, seeds=None, propagate_from=""):
    """Colour a drawn level across every drawing (WP-35): named colour styles, areas painted by a point inside each
    closed shape (small gaps in the line are bridged), carried from a painted key drawing to every other drawing by
    matching areas, and repainted everywhere when a style changes. Paint sits under the line."""
    from . import levels as LV
    f = _level_path(name); p = _json(f); sw = p["swaps"]["level"]
    pt = sw.setdefault("paint", {"styles": {}, "seeds": {}})
    pt["styles"].update(styles or {})
    for d, ss in (seeds or {}).items():
        if d not in sw["shapes"]:
            raise KeyError(f"no drawing {d}")
        pt["seeds"][d] = ss
    carried = {}
    if propagate_from:
        order = []
        for c in sw["xsheet"]["cells"]:
            if c not in order:
                order.append(c)
        order += [d for d in sw["shapes"] if d not in order]
        i = order.index(propagate_from)
        chain = order[i:] + order[:i]
        for a_, b_ in zip(chain, chain[1:]):
            prev_line = LV.drawing_rgba(p, a_, role="line"); line = LV.drawing_rgba(p, b_, role="line")
            pt["seeds"][b_] = LV.carry_seeds(prev_line, pt["seeds"].get(a_, []), line)
            carried[b_] = len(pt["seeds"][b_])
    LV.recolour(p)
    f.write_text(json.dumps(p, separators=(",", ":")))
    return {"styles": pt["styles"], "seeds": {k: len(v) for k, v in pt["seeds"].items()}, "carried": carried}


@command("level.delete_drawing", name=("string", "level"), drawing=("string", "drawing to remove (and its cells)"))
def level_delete_drawing(name, drawing):
    """Remove a drawing from a drawn level and from its exposure sheet (WP-35)."""
    from . import levels as LV
    f = _level_path(name); p = _json(f); sw = p["swaps"]["level"]
    if drawing not in sw["shapes"] or len(sw["shapes"]) == 1:
        raise ValueError("no such drawing, or it is the last one")
    del sw["shapes"][drawing]
    LV.set_xsheet(p, cells=[c for c in sw["xsheet"]["cells"] if c != drawing])
    f.write_text(json.dumps(p, separators=(",", ":")))
    return {"drawings": len(sw["shapes"]), "frames": len(sw["xsheet"]["cells"])}


@command("level.onion", name=("string", "level"), frame=("integer", "frame of the level (0-based)"),
         before=("integer", "", 2), after=("integer", "", 1))
def level_onion(name, frame, before=2, after=1):
    """The drawings to show as onion skins around a frame of a drawn level (WP-35): previous and next drawings with
    the opacity to draw them at (the Studio drawing page uses it)."""
    from . import levels as LV
    return {"frame": frame, "onion": [{"drawing": d, "offset": o, "opacity": a} for d, o, a in LV.onion(_json(_level_path(name)), frame, before, after)]}


# ---------------- open-source parts behind commands (WP-34; docs/oss-integration.md) ----------------
@command("brush.list")
def brush_list():
    """MyPaint brush presets installed (WP-34): name -> file; brush.paint draws with any of them."""
    from . import oss
    return {"available": oss.available(), "brushes": oss.brushes()}


@command("brush.paint", brush=("string", "a MyPaint brush (brush.list name like deevad/2B_pencil, or a .myb path)"),
         strokes=("array", "strokes: lists of [x, y, pressure 0-1, seconds since the last point]"), size=("array", "[width, height]"),
         out=("string", "PNG to write (transparent background)"), colour=("string", "ink colour", "#24160e"),
         radius_scale=("number", "scale the brush radius", 1.0))
def brush_paint(brush, strokes, size, out, colour="#24160e", radius_scale=1.0):
    """Paint pressure strokes with a MyPaint brush (WP-34: libmypaint linked in-process): pencils, inks, charcoal,
    watercolour and the rest of the MyPaint presets, onto a transparent PNG for a set, a drawn level or a puppet part."""
    from PIL import Image
    from . import oss
    a = oss.paint(brush, strokes, tuple(size), colour, radius_scale)
    o = ROOT / out if not Path(out).is_absolute() else Path(out); o.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a, "RGBA").save(o)
    ink = a[..., 3] > 20
    return {"file": str(o), "inked_px": int(ink.sum())}


@command("pencil2d.write", frames=("array", "drawings: [{frame, png}] (each held until the next, as on an exposure sheet)"),
         out=("string", ".pclx to write"), size=("array", "[width, height]", [1080, 1920]), fps=("integer", "", 24))
def pencil2d_write(frames, out, size=None, fps=24):
    """Write a drawn level as a Pencil2D project (WP-34) that an artist can open and keep drawing in."""
    from . import oss
    o = ROOT / out if not Path(out).is_absolute() else Path(out); o.parent.mkdir(parents=True, exist_ok=True)
    return oss.pencil2d_write(frames, o, tuple(size or [1080, 1920]), fps)


@command("pencil2d.render", file=("string", "a Pencil2D project (.pclx)"), out_dir=("string", "folder for the frames"),
         start=("integer", "", 1), end=("string", "last frame, or last / last-sound", "last"))
def pencil2d_render(file, out_dir, start=1, end="last"):
    """Render a Pencil2D project headless with Pencil2D's own exporter (WP-34): PNG frames with transparency, holds
    included, so hand-drawn animation from Pencil2D comes into a film as a frame sequence."""
    from . import oss
    fr = oss.pencil2d_render(ROOT / file if not Path(file).is_absolute() else Path(file), ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir), start, end)
    return {"frames": len(fr), "first": str(fr[0]), "last": str(fr[-1])}


@command("vector.boolean", shapes=("array", "SVG elements in drawing order (path, rect, circle, ellipse, polygon)"),
         op=("string", "union | difference | intersection | exclusion | division"), size=("array", "canvas [width, height]", [1080, 1920]))
def vector_boolean(shapes, op, size=None):
    """Path boolean operations with Inkscape's own engine, headless (WP-34): unite shapes, cut one from another,
    keep their overlap. Returns the resulting path data, for puppet parts, set pieces and masks."""
    from . import oss
    return {"paths": oss.boolean(shapes, op, tuple(size or [1080, 1920]))}


# ---------------- renderer parity (WP-14) ----------------
@command("render.parity", name=("string", "film"), shot=("string", "shot id"), renderers=("array", "renderers to compare with svg", None),
         times=("array", "moments (seconds into the shot; default 20, 50 and 80 percent)", None))
def render_parity(name, shot, renderers=None, times=None):
    """Renderer parity (WP-14): the shot's cast drawn alone by the SVG renderer and by Synfig, Lottie and Grease
    Pencil at the same moments, compared by filled silhouette and by line (the better of the two), with the colour
    difference where both have ink. Renderers that cannot draw the shot say why."""
    from . import rparity as RP
    return RP.run(name, shot, times=times, renderers=tuple(renderers or ("synfig", "lottie", "grease-pencil")))


@command("render.parity_bench")
def render_parity_bench():
    """Renderer parity on every benchmark shot (WP-14); writes out/rparity/bench.json."""
    from . import rparity as RP
    return RP.bench()


# ---------------- parity matrix (WP-41) ----------------
@command("parity.check")
def parity_check():
    """The parity matrix (WP-41): validate parity/<tool>.json (commands named exist, every gap and partial names a work
    package that exists, every chapter has capabilities) and measure coverage per professional tool and overall."""
    from . import parity as PY_
    return PY_.check()


@command("parity.matrix")
def parity_matrix():
    """Write docs/parity-matrix.md from parity/<tool>.json: per tool and chapter, each capability in our own words, how
    professionals use it, and Doodleberry's match (command, data, metric, partial with its WP, gap with its WP, n/a)."""
    from . import parity as PY_
    md, rep = PY_.matrix_md()
    (ROOT / "docs" / "parity-matrix.md").write_text(md)
    return {"file": "docs/parity-matrix.md", "ok": rep["ok"], "overall": rep["overall"], "problems": rep["problems"][:10]}


@command("asset.check")
def asset_check():
    """Every tracked third-party file (fonts, vendored scripts, images, sounds, models) must have a row in
    assets/manifest.json with its licence; reports what is missing."""
    man = _json(ROOT / "assets" / "manifest.json", {"files": []})
    known = [f["path"] for f in man["files"]] + [g["path"] for g in man.get("generated", [])]
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    pat = re.compile(r"(^engine/vendor/|\.(ttf|otf|woff2?|png|jpe?g|gif|webp|svg|wav|mp3|ogg|flac|glb|gltf|fbx|onnx)$)", re.I)
    third = [t for t in tracked if pat.search(t) and not t.startswith(("tests/golden/", "dbe/", "puppet/canvas/")) and not t.endswith(("LICENSE", "LICENSE.md", "UPSTREAM.json"))]   # UPSTREAM.json: our own provenance records (WP-33)
    missing = [t for t in third if not any(t == k or (k.endswith("/") and t.startswith(k)) for k in known)]
    return {"third_party_files": len(third), "missing_from_manifest": missing, "ok": not missing}


# ---------------- research gates and critic loop ----------------
@command("research.check", name=("string", "film"))
def research_check(name):
    """Research gate: sources and trace excerpts for every fact, two independent sources for numbers, the research
    log's sections, a recorded fact-check clearance, and a safety clearance for sensitive briefs. Renders refuse to
    start while it reports errors."""
    from . import research
    return research.check(_film(name))


@command("ledger.add", name=("string", "film"), role=("string", "fact_gate | safety | sound_off_reader | fact_checker | director | counter_evidence | builder"),
         verdict=("string", "cleared | blocked | ready | one more pass | ..."), notes=("string", "findings and fixes", ""),
         round=("integer", "critic round (default: the current one; pass a new number to open a round)", None),
         snapshot=("boolean", "attach the film's current QA numbers as this entry's metrics", True))
def ledger_add(name, role, verdict, notes="", round=None, snapshot=True):
    """Record a gate verdict or critic round in ledger.json and ledger.md, with before/after QA numbers."""
    from . import research
    d = _film(name); metrics = {}
    q = _json(d / "build" / "qa.json", {}) if snapshot else {}
    if q:
        L = q.get("layout", {})
        metrics = {"duration_s": q.get("duration"), "loudness_lufs": q.get("loudness_lufs"), "true_peak": q.get("true_peak_dbtp"),
                   "frozen_stretches": len(q.get("frozen_stretches_over_0.5s", [])),
                   "worst_bare": (L.get("frame_fill") or {}).get("worst_bare"), "text_outside_safe": len((L.get("text") or {}).get("outside_safe", [])),
                   "type_too_small": len((L.get("text") or {}).get("too_small", [])), "advisory_failures": ",".join(L.get("advisory_failures", [])) or "none"}
        metrics = {k: v for k, v in metrics.items() if v is not None}
    return research.add(d, role, verdict, notes, metrics, round)


@command("critic.pack", name=("string", "film"), step=("number", "seconds between stills", 3.0))
def critic_pack(name, step=3.0):
    """Review packet for fresh critic agents (they get the film's evidence, not the builder's conclusions):
    stills every few seconds from the final encode, contact sheets, transcript with times and fact ids, facts.json,
    the QA and layout report, and a prompt per role (sound-off reader, fact checker, director)."""
    import shutil as sh
    d = _film(name); final = d / "build" / "final.mp4"
    if not final.exists():
        raise FileNotFoundError("render the film first")
    out = d / "build" / "critic"; sh.rmtree(out, ignore_errors=True); (out / "stills").mkdir(parents=True)
    _run(["ffmpeg", "-v", "error", "-i", str(final), "-vf", f"fps=1/{step},scale=540:-2", str(out / "stills" / "t%03d.png")])
    for f in sorted((out / "stills").glob("t*.png")):  # name stills by time
        k = int(f.stem[1:]) - 1; f.rename(out / "stills" / f"{k * step:06.1f}s.png")
    qa = d / "build" / "qa.json"
    if not qa.exists():
        qa_run(name)
    for f in (d / "build" / "qa").glob("*.jpg"):
        sh.copy(f, out / f.name)
    sh.copy(qa, out / "qa.json")
    if (d / "facts.json").exists():
        sh.copy(d / "facts.json", out / "facts.json")
    tm = _json(d / "timing.json", {}); sc = {l["id"]: l for l in _json(d / "script.json", {}).get("lines", [])}
    tr = ["# Transcript", "", "| time | speaker | line | facts |", "|---|---|---|---|"]
    for l in tm.get("lines", []):
        fct = sc.get(l["id"], {}).get("fact")
        tr.append(f"| {l['start']:.2f}–{l['end']:.2f} | {l.get('speaker', '')} | {l['text']} | {', '.join(fct) if isinstance(fct, list) else (fct or '')} |")
    (out / "transcript.md").write_text("\n".join(tr) + "\n")
    roles = {}
    for r in ("sound_off_reader", "fact_checker", "director"):
        sh.copy(ROOT / "dbe" / "critic" / f"{r}.md", out / f"prompt_{r}.md"); roles[r] = str((out / f"prompt_{r}.md").relative_to(ROOT))
    return {"packet": str(out.relative_to(ROOT)), "stills": len(list((out / "stills").glob("*.png"))), "prompts": roles,
            "next": "give each prompt to a fresh agent with the packet; record each verdict with ledger.add"}


@command("puppet.from_ink", spec=("string", "path to an ink spec JSON (photo, crop, parts polygons and pivots, swaps); see dbe/ink.py"),
         out=("string", "where to write the .puppet.json"))
def puppet_from_ink(spec, out):
    """Ink-fidelity import: a photo or scan of a drawing becomes a raster-part puppet in the artist's own line
    (lighting flattened, ink thresholded, specks removed, parts cut by polygons with hidden overlaps, blink shapes
    squashed with the line weight kept)."""
    sp, op = (ROOT / spec).resolve(), (ROOT / out).resolve()
    if ROOT not in sp.parents or ROOT not in op.parents:
        raise ValueError("spec and out must be inside the repository")
    r = _run([PY, "dbe/ink.py", str(sp), str(op)])
    lint = puppet_lint(str(op.relative_to(ROOT)))
    return {"puppet": str(op.relative_to(ROOT)), "report": json.loads(r[-1]) if r else None, "lint": lint.get("issues")}


# ---------------- re-voicing (plan 0.6) ----------------
CLEAN_EQUIVALENTS = {  # restricted Piper voices -> clean Kokoro voices of similar age, sex and accent
    "en_US-amy-medium": "kokoro:af_bella", "en_US-ryan-high": "kokoro:am_michael", "en_GB-alan-medium": "kokoro:bm_george",
    "en_US-lessac-high": "kokoro:af_sarah", "en_US-lessac-medium": "kokoro:af_sarah", "en_US-ryan-medium": "kokoro:am_michael"}


@command("film.revoice", name=("string", "film"), map=("object", "voice -> voice overrides (else the clean equivalents table)", None),
         build=("boolean", "rebuild audio and picture and run QA", True),
         rebuild=("boolean", "rebuild even when no voice needed changing (e.g. after a failed build)", False))
def film_revoice(name, map=None, build=True, rebuild=False):
    """Swap restricted voices for clean ones (voices/registry.json status "clean"), keeping each speaker's effects, then
    rebuild: shot films with voice.build, retime and film.render; scene.js films through the engine pipeline (voice,
    voice fx, cues, audio, picture, mux, QA). Scenes and shots are timed off words, so sync survives the new voices."""
    d = _film(name); sp = d / "script.json"; s = _json(sp)
    reg = _voice_registry(); mapping = {**CLEAN_EQUIVALENTS, **(map or {})}
    changed = {}

    def swap(v):
        if not v or reg.get(v, {}).get("status") == "clean":
            return v
        new = mapping.get(v)
        if not new or reg.get(new, {}).get("status") != "clean":
            raise PermissionError(f"no clean replacement for {v}; pass map={{'{v}': '<clean voice>'}}")
        changed[v] = new
        return new
    if s.get("speakers"):
        for k, v in s["speakers"].items():
            v["voice"] = swap(v.get("voice"))
    if s.get("voice"):
        s["voice"] = swap(s["voice"])
    voices_now = [v.get("voice") for v in (s.get("speakers") or {}).values()] + ([s["voice"]] if s.get("voice") else [])
    if all(reg.get(v, {}).get("status") == "clean" for v in voices_now if v):  # no longer internal-only
        for k in ("allow_restricted_voices", "voice_licence_note"):
            s.pop(k, None)
    sp.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    out = {"film": name, "changed": changed}
    if not build or (not changed and not rebuild):
        return out
    if (d / "shots.json").exists():
        voice_build(name); film_retime(name)
        r = film_render(name)
        return {**out, "final": r.get("final"), "qa": r.get("qa")}
    # scene.js film: the engine pipeline
    F = f"films/{name}"
    old_end = (_json(d / "timing.json", {}).get("lines") or [{}])[-1].get("end")
    _run([PY, "engine/voice.py", F, "--voices-dir", os.environ.get("DBE_VOICES", str(ROOT / "voices"))], timeout=3600)
    new_end = (_json(d / "timing.json", {}).get("lines") or [{}])[-1].get("end")
    sc = _json(d / "score.json", {})
    if old_end and new_end and sc.get("length_s"):  # the new voice may run longer or shorter: keep the original tail after the last line
        tail = max(1.0, sc["length_s"] - old_end)
        sc["length_s"] = round(new_end + tail, 3); (d / "score.json").write_text(json.dumps(sc, indent=1))
        scene = d / "scene.js"
        if scene.exists():  # legacy scenes hard-code their end
            scene.write_text(re.sub(r"const END = [\d.]+;", f"const END = {sc['length_s']};", scene.read_text(), count=1))
    if s.get("voice_fx"):
        _run([PY, "engine/voicefx.py", F])
    is3d = any(k in ((d / "index.html").read_text() + (d / "scene.js").read_text()) for k in (".glb", "three.module", "THREE"))
    srv, base = None, []
    if is3d:  # 3D films fetch GLB models: serve the repo over HTTP for the render
        import socket
        sk = socket.socket(); sk.bind(("127.0.0.1", 0)); port = sk.getsockname()[1]; sk.close()
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = ["--base", f"http://127.0.0.1:{port}/"]
        import time; time.sleep(1.0)
    try:
        _run(["node", "engine/render.mjs", F, "--dump-cues", *base], timeout=3600)
        _run([PY, "engine/audio.py", F], timeout=1800)
        _run(["node", "engine/render.mjs", F, "--workers", str(max(1, (os.cpu_count() or 2) - 1)), *base], timeout=7200 * (3 if is3d else 1))
    finally:
        if srv:
            srv.terminate()
    mix = d / "build" / "mix.wav"
    length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mix)], capture_output=True, text=True).stdout or 0)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(d / "build" / "picture.mp4"), "-i", str(mix), "-map", "0:v", "-map", "1:a",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-af", "apad", "-t", f"{length:.3f}", str(d / "build" / "final.mp4")])
    qa = subprocess.run([PY, "engine/qa.py", F], cwd=ROOT, capture_output=True, text=True)
    return {**out, "final": f"{F}/build/final.mp4", "qa": (qa.stdout or qa.stderr).strip().splitlines()[-12:]}


# ---------------- drawing import (plan 1.3) ----------------
def _inside(p, must_exist=False):
    q = (ROOT / p).resolve()
    if ROOT not in q.parents or (must_exist and not q.exists()):
        raise ValueError(f"{p} must be {'an existing file ' if must_exist else ''}inside the repository")
    return q


@command("puppet.import", source=("string", "layered drawing inside the repo: .svg (Inkscape layers or groups), .psd or .ora (Krita/GIMP export)"),
         out=("string", "where to write the .puppet.json"),
         template=("string", "humanoid | doodle (default: guessed from the layer names)", ""), name=("string", "character name", ""),
         z=("string", "document (layer order) | template (template draw order)", "document"),
         author=("string", "who drew it", ""), license=("string", "licence of the drawing", ""))
def puppet_import(source, out, template="", name="", z="document", author="", license=""):
    """Layered drawing to puppet by layer name: parts (`head`, `upperarm_R`, `Upper arm R`), swap shapes (`mouth/closed`
    or a `mouth` group of shapes), `pivot:<part>` and `anchor:<name>` markers, a `ground` line; guide and sketch layers
    skipped. Missing pivots are estimated from the drawing (the cap at the near end of each limb). Returns the
    layer mapping, pivots with the method used, unmatched layers with suggestions, and the lint."""
    sp, op = _inside(source, True), _inside(out)
    opts = {k: v for k, v in {"template": template, "name": name, "z": z, "author": author, "license": license}.items() if v}
    r = _run([PY, "dbe/drawing_import.py", str(sp), str(op), json.dumps(opts)])
    coach = puppet_coach(str(op.relative_to(ROOT)))
    return {"puppet": str(op.relative_to(ROOT)), "report": json.loads(r[-1]), "lint": puppet_lint(str(op.relative_to(ROOT))).get("issues"),
            "coach": {"errors": coach["errors"], "warnings": coach["warnings"], "advice": [i["msg"] for i in coach["issues"]], "image": coach["image"]}}


@command("puppet.coach", source=("string", "a .puppet.json, or a layered .svg/.psd/.ora before import"),
         out=("string", "annotated PNG to write (inside the repo)", ""))
def puppet_coach(source, out=""):
    """Drawing coach: checks a character before it is rigged and says exactly what to fix, with an annotated image:
    missing parts, joints that open a gap when bent (each joint is bent +-50 degrees and the hole measured), pivots
    outside their drawing, limb proportions and left/right mismatch, eyes/pupils/mouths needed to blink, look and
    lip-sync, scale and ground contact, and layers the importer could not place."""
    sp = _inside(source, True)
    op = _inside(out) if out else sp.with_name(sp.name.split(".")[0] + ".coach.png")
    r = _run([PY, "dbe/coach.py", str(sp), str(op)], timeout=900)
    res = json.loads(r[-1]); res["image"] = str(op.relative_to(ROOT))
    return res


@command("puppet.sheet", path=("string", "a .puppet.json"), out=("string", "PNG to write (default next to the puppet)", ""))
def puppet_sheet(path, out=""):
    """Model sheet: the character in key poses and views (rest, wave, turned both ways, every drawn view) and every
    expression close up (mouths, brows, eyes, gaze), on one page. The Rig Canvas shows the same sheet."""
    pp = _inside(path, True); op = _inside(out) if out else pp.with_name(pp.name.split(".")[0] + ".sheet.png")
    _run(["node", "tools/sheet.mjs", str(pp), str(op)], timeout=300)
    return {"sheet": str(op.relative_to(ROOT))}


@command("puppet.export_layers", path=("string", "a .puppet.json"), out=("string", "output .svg, .ora or .psd inside the repo"),
         pivots=("boolean", "add a pivots layer with a dot per joint", True))
def puppet_export_layers(path, out, pivots=True):
    """Hand a puppet to an artist as a layered file (one layer per part, swap sets as groups, palette slots kept in SVG);
    repaint it and bring it back with puppet.import."""
    pp, op = _inside(path, True), _inside(out)
    _run([PY, "dbe/layers_export.py", str(pp), str(op), json.dumps({"pivots": pivots})])
    return {"out": str(op.relative_to(ROOT)), "bytes": op.stat().st_size}


@command("puppet.from_blend", recipe=("string", "a recipe JSON (cast/recipes/*.json): source .blend, variants, spec"))
def puppet_from_blend(recipe):
    """Blender cut-out rig to puppet: Blender (headless, scripts off) flattens the rig's textured meshes, bones and
    sprite/shape-key variants to data; each mesh is rasterised from its UVs, assigned to a template part by its bone,
    layered by depth; hair and skirt chains become spring parts; phonemes, blinks and hand sprites become swaps."""
    rp = _inside(recipe, True); R = _json(rp)
    src = _inside(R["source"])
    if not src.exists():
        raise FileNotFoundError(f"{R['source']} is missing: download it from {R.get('source_url', 'its source')} ({R.get('license', '')}) and place it there")
    blender = os.environ.get("DBE_BLENDER", "blender")
    work = ROOT / "cast" / "external" / (Path(R["out"]).stem.split(".")[0] + "_extract")
    work.mkdir(parents=True, exist_ok=True)
    (work / "variants.json").write_text(json.dumps({"variants": R.get("variants", []), "keep_pose": R.get("keep_pose", [])}))
    r = subprocess.run([blender, "-b", "--factory-startup", str(src), "--python", str(ROOT / "dbe" / "blender_cutout.py"), "--", str(work), str(work / "variants.json")],
                       capture_output=True, text=True, timeout=1800)
    line = next((l for l in r.stdout.splitlines() if l.startswith("CUTOUT ")), None)
    if not line:
        raise RuntimeError("Blender extraction failed: " + (r.stderr or r.stdout)[-800:])
    op = _inside(R["out"]); op.parent.mkdir(parents=True, exist_ok=True)
    spec = dict(R.get("spec", {})); spec.setdefault("meta", {}).update({"license": R.get("license", ""), "source_url": R.get("source_url", ""), "credit": R.get("credit", "")})
    (work / "spec.json").write_text(json.dumps(spec))
    out = _run([PY, "dbe/cutout_import.py", str(work), str(op), str(work / "spec.json")])
    return {"puppet": str(op.relative_to(ROOT)), "extract": json.loads(line[7:]), "report": json.loads(out[-1]),
            "lint": puppet_lint(str(op.relative_to(ROOT))).get("issues"), "credit": R.get("credit")}


# ---------------- aspect ratios (plan 1.12) ----------------
SET_FLOOR = {"plain": 1500, "park": 1500, "clinic": 1500, "paper": 1440, "cutaway": 1100}
SET_FLOOR_FRAC = {"plain": 0.8, "park": 0.8, "clinic": 0.8, "paper": 0.8, "cutaway": 0.55, "kitchen": 0.78, "classroom": 0.8, "office": 0.8,
                  "street": 0.82, "farm": 0.74, "bedroom": 0.8, "forest": 0.8, "lab": 0.8, "night": 0.82, "reservoir": 0.82, "stage": 0.8}
ASPECT_SIZE = {"16:9": [1920, 1080], "9:16": [1080, 1920], "1:1": [1080, 1080]}


def _floor_of(set_name, W, H):
    if set_name not in SET_FLOOR:  # aspect-independent sets (sets/more.js) scale their floor with the frame
        return round(H * SET_FLOOR_FRAC.get(set_name, 0.8))
    return SET_FLOOR.get(set_name, 1500) if H >= W and (W, H) == (1080, 1920) else round(H * SET_FLOOR_FRAC.get(set_name, 0.8))


def restage(s, aspect):
    """Re-block a portrait film for another frame: same shots, timings and acting; placements, overlays and camera
    recomposed (characters keep their share of the frame height and spread wider; off-screen entrances stay
    off-screen). shots.json "aspects": {"16:9": {"shots": {id: {...}}}} overrides any shot (cast entries merge by
    index)."""
    import copy
    Wo, Ho = s.get("size", [1080, 1920]); Wn, Hn = ASPECT_SIZE[aspect]
    k = Hn / Ho; spread = 1.6 if Wn > Wo else 1.0
    grow = 1.3 if Wn > Hn else 1.0  # a wide frame has room: characters take a bigger share of its height
    out = copy.deepcopy(s); out["size"] = [Wn, Hn]
    out.pop("aspects", None)
    mapx = lambda x: x * k if x < 0 else (Wn + (x - Wo) * k if x > Wo else Wn / 2 + (x - Wo / 2) * k * spread)
    for sh in out["shots"]:
        fo, fn = _floor_of(sh.get("set", "plain"), Wo, Ho), _floor_of(sh.get("set", "plain"), Wn, Hn)
        def place(p):
            return {**p, "x": round(mapx(p["x"]), 1), "y": round(fn + (p["y"] - fo) * k, 1), "s": round(p.get("s", 1) * k * grow, 4)}
        for c in sh.get("cast", []):
            pl = c.get("place")
            if isinstance(pl, list):
                c["place"] = [[t, place(p)] for t, p in pl]
            elif isinstance(pl, dict) and "path" in pl:   # a walk along a path (WP-11): move its points and scale
                pa = pl["path"]
                pts = [place({"x": x, "y": y}) for x, y in pa.get("points", [])]
                c["place"] = {**pl, "path": {**pa, "points": [[q["x"], q["y"]] for q in pts], **({"s": round(pa.get("s", 1) * k * grow, 4)} if "s" in pa or "s_by_y" not in pa else {}),
                                              **({"speed": round(pa["speed"] * k, 2)} if "speed" in pa else {})}}
            elif isinstance(pl, dict):
                c["place"] = place(pl)
        for o in sh.get("overlays", []):
            if "x" in o:
                o["x"] = round(o["x"] / Wo * Wn, 1)
            if "y" in o:
                o["y"] = round(o["y"] * k, 1) if o.get("type") != "sign" else round(max(70, o["y"] * k), 1)
            if "size" in o:
                o["size"] = round(o["size"] * 0.8)
        if sh.get("camera"):
            sh["camera"] = [[t, [round(mapx(c[0]), 1), round(c[1] * k, 1), c[2]]] for t, c in sh["camera"]]
    for sid, ov in ((s.get("aspects") or {}).get(aspect, {}).get("shots") or {}).items():
        sh = next((x for x in out["shots"] if x["id"] == sid), None)
        if not sh:
            continue
        for key, val in ov.items():
            if key == "cast" and isinstance(val, list):
                for i, cv in enumerate(val):
                    if i < len(sh.get("cast", [])) and cv:
                        sh["cast"][i].update(cv)
            else:
                sh[key] = val
    return out


def _derive_aspect(name, aspect):
    """films/<name>--<tag>: the same film data with re-staged shots (build artefacts reused where possible)"""
    tag = aspect.replace(":", "x")
    src = _film(name); dst = FILMS / f"{name}--{tag}"
    (dst / "build").mkdir(parents=True, exist_ok=True)
    for f in ("script.json", "timing.json", "facts.json", "score.json", "ledger.json", "ledger.md", "research_log.md", "brief.md"):
        if (src / f).exists():
            shutil.copy(src / f, dst / f)
    for f in ("voice.wav", "voice_fx.wav"):
        if (src / "build" / f).exists():
            shutil.copy(src / "build" / f, dst / "build" / f)
    (dst / "shots.json").write_text(json.dumps(restage(_shots(name, resolve=False), aspect), indent=1))
    return dst.name, tag


# ---------------- sound-off cut (plan 2.13) ----------------
def _warp(knots, t, inverse=False):
    """film time -> cut time (inverse=True) or cut time -> film time, piecewise linear through [[cut, film], ...]"""
    if not knots or len(knots) < 2:
        return t
    i, j = (1, 0) if inverse else (0, 1)
    if t <= knots[0][i]:
        return knots[0][j] + (t - knots[0][i])
    for a, b in zip(knots, knots[1:]):
        if t <= b[i]:
            return a[j] + (b[j] - a[j]) * (t - a[i]) / ((b[i] - a[i]) or 1)
    return knots[-1][j] + (t - knots[-1][i])


def _cut_timing(s, tm, only=None):
    """timing.json on the cut's clock (identity without a timewarp); only: keep these line ids"""
    k = s.get("timewarp")
    if not k and only is None:
        return tm
    w = lambda t: round(_warp(k, t, inverse=True), 3)
    lines = [{**ln, "start": w(ln["start"]), "end": w(ln["end"]),
              **({"words": [{**wd, "start": w(wd["start"]), "end": w(wd["end"])} for wd in ln["words"]]} if ln.get("words") else {})}
             for ln in tm.get("lines", []) if only is None or ln.get("id") in only]
    return {**tm, "lines": lines}


def soundoff_plan(s, tm, wpm=170, max_stretch=2.5, min_hold=1.2):
    """Knots that hold each line long enough to read with the sound off: 0.4 s + words at `wpm`, at least `min_hold`,
    never more than `max_stretch` times its voiced length. Gaps between lines play at speed. Also decides which lines
    get a speech bubble (a speaker on screen) and which need a caption (narration with nobody to speak it)."""
    knots, off, stretched = [[0.0, 0.0]], 0.0, []
    lines = sorted(tm.get("lines", []), key=lambda l: l["start"])
    for ln in lines:
        dur = max(0.05, ln["end"] - ln["start"])
        words = len((ln.get("text") or "").split()) or len(ln.get("words") or []) or 1
        need = max(min_hold, 0.4 + words * 60.0 / wpm)
        new = min(max(dur, need), dur * max_stretch)
        if new > dur + 0.02:
            knots.append([round(ln["start"] + off, 4), round(ln["start"], 4)])
            off += new - dur
            knots.append([round(ln["end"] + off, 4), round(ln["end"], 4)])
            stretched.append({"line": ln.get("id"), "voiced_s": round(dur, 2), "reading_s": round(new, 2), **({"short_by_s": round(need - new, 2)} if need > new + 0.02 else {})})
    end = s["shots"][-1]["end"]
    knots.append([round(end + off, 4), round(end, 4)])
    bubbled, captioned = [], []
    for ln in lines:
        sh = next((x for x in s["shots"] if x["start"] <= ln["start"] < x["end"]), None)
        speakers = {c.get("speaker") for c in (sh or {}).get("cast", [])}
        (bubbled if sh and ln.get("speaker") in speakers and sh.get("renderer", "svg") == "svg" else captioned).append(ln.get("id"))
    return {"knots": knots, "stretched": stretched, "bubbled": bubbled, "captioned": captioned, "length_s": round(end + off, 3)}


@command("film.soundoff", name=("string", "film"), wpm=("number", "reading speed the lines are paced for (words per minute)", 170),
         max_stretch=("number", "longest a line may be held, as a multiple of its voiced length", 2.5),
         render=("boolean", "render the cut (false: only write the derived film and report the plan)", True))
def film_soundoff(name, wpm=170, max_stretch=2.5, render=True):
    """The sound-off cut (plan 2.13): the same film with no voice, every spoken line in a speech bubble (narration
    with nobody on screen to speak it stays as a caption), each line held long enough to read, music and effects
    re-timed to match. Built as the derived film <name>--soundoff and copied to build/final_soundoff.mp4."""
    src = _film(name); s = _shots(name, resolve=False); sr = _shots(name); tm = _json(src / "timing.json", {})
    if not s.get("shots") or not tm.get("lines"):
        raise ValueError("film.soundoff needs a shots.json film with voiced lines (timing.json)")
    bad = [sh["id"] for sh in sr["shots"] if sh.get("renderer", "svg") != "svg"]
    if bad:
        raise ValueError(f"film.soundoff re-times shots in the SVG player; shots {bad} use other renderers")
    plan = soundoff_plan(sr, tm, wpm, max_stretch)
    dst = FILMS / f"{name}--soundoff"; (dst / "build").mkdir(parents=True, exist_ok=True)
    for f in ("script.json", "timing.json", "facts.json", "brief.md", "data.json"):
        if (src / f).exists():
            shutil.copy(src / f, dst / f)
    score = _json(src / "score.json", {}); score["voice"] = False; (dst / "score.json").write_text(json.dumps(score, indent=1))
    s2 = json.loads(json.dumps(s)); s2.pop("soundoff", None)
    s2["timewarp"] = plan["knots"]; s2["caption_lines"] = plan["captioned"]
    s2["captions"] = bool(plan["captioned"])
    for sh in s2["shots"]:
        if any(c.get("speaker") for c in sh.get("cast", [])):
            sh["bubbles"] = True
    (dst / "shots.json").write_text(json.dumps(s2, indent=1))
    out = {"derived_film": dst.name, "length_s": plan["length_s"], "voiced_length_s": sr["shots"][-1]["end"],
           "stretched_lines": plan["stretched"], "bubbled": plan["bubbled"], "captioned": plan["captioned"]}
    if not render:
        return out
    r = film_render(dst.name)
    shutil.copy(dst / "build" / "final.mp4", src / "build" / "final_soundoff.mp4")
    return {**out, "final": f"films/{name}/build/final_soundoff.mp4", "qa": r.get("qa"), "lint": r.get("lint")}


# ---------------- beat grid and master-to-many cuts (plan 2.14) ----------------
@command("film.beats", name=("string", "film"))
def film_beats(name):
    """The film's beat grid from its score (bpm, offset): beats and bars, and where each shot change and line start
    falls relative to it (how far from the nearest beat and bar), for cutting picture on the music."""
    from . import edit as E
    d = _film(name); g = E.grid(d); s = _shots(name); tm = _json(d / "timing.json", {})
    near = lambda t, pts: round(min((t - p for p in pts), key=abs), 3) if pts else None
    return {"bpm": g["bpm"], "beat_s": round(g["beat"], 4), "bar_s": round(g["bar"], 4), "bars": len(g["bars"]),
            "shot_changes": [{"shot": sh["id"], "t": round(sh["start"], 3), "from_beat": near(sh["start"], g["beats"]), "from_bar": near(sh["start"], g["bars"])} for sh in s["shots"][1:]],
            "lines": [{"line": l["id"], "start": l["start"], "from_beat": near(l["start"], g["beats"])} for l in tm.get("lines", [])]}


def _cut_source(film, aspect):
    """the build folder holding a film's master render in this aspect (film.render aspect=... makes it)"""
    W0, H0 = _shots(film, resolve=False).get("size", [1080, 1920])
    if not aspect or ASPECT_SIZE.get(aspect) == [W0, H0]:
        b = FILMS / film / "build"
    else:
        b = FILMS / f"{film}--{aspect.replace(':', 'x')}" / "build"
    if not (b / "final.mp4").exists() or not (b / "stems" / "voice.wav").exists():
        raise FileNotFoundError(f"no {aspect or 'master'} render of {film} with stems: run film.render" + (f" with aspect {aspect}" if aspect else ""))
    return b


@command("film.cuts", name=("string", "film"), only=("array", "cut ids to make (default: all in edit.json)", None),
         plan_only=("boolean", "only resolve the edit list (cut points on the grid), make no files", False))
def film_cuts(name, only=None, plan_only=False):
    """Master to many (plan 2.14): assemble the cuts in films/<name>/edit.json (full film, episodes from "split",
    teasers, recaps, inserts from other films) from the master renders, every cut point on a bar line or beat in a
    pause and never inside a line. Audio comes from the master's mixed stems, crossfaded at joins and levelled to
    -14 LUFS. Writes build/cuts/<cut>.mp4 with .srt captions and an OpenTimelineIO .otio edit."""
    from . import edit as E
    d = _film(name)
    if not (d / "edit.json").exists():
        raise FileNotFoundError("no edit.json (see docs/dbe.md, master-to-many cuts)")
    cuts = E.plan(name, _shots(name), _json(d / "edit.json"))
    if only:
        cuts = {k: v for k, v in cuts.items() if k in only or re.sub(r"\d+$", "", k) in only}
    if plan_only:
        return {"cuts": cuts}
    out_dir = d / "build" / "cuts"; out_dir.mkdir(parents=True, exist_ok=True)
    fps = _shots(name).get("fps", 30); M = _json(ROOT / "dbe" / "profiles.json")["master"]; made = {}
    for cid, cut in cuts.items():
        srcs = {s["film"]: _cut_source(s["film"], cut["aspect"]) for s in cut["segments"]}
        tmp = out_dir / f"_{cid}"; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
        parts = []
        for i, sg in enumerate(cut["segments"]):
            pv = tmp / f"v{i}.mp4"
            _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sg['t0']:.4f}", "-i", str(srcs[sg['film']] / "final.mp4"), "-t", f"{sg['t1'] - sg['t0']:.4f}", "-an",
                  "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps), str(pv)])
            parts.append(pv)
        (tmp / "list.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        pic = tmp / "picture.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(pic)])
        spec = {"segments": [{"build": str(srcs[s["film"]].relative_to(ROOT)), "t0": s["t0"], "t1": s["t1"]} for s in cut["segments"]], "out": str(tmp / "mix.wav")}
        (tmp / "spec.json").write_text(json.dumps(spec))
        au = json.loads(_run([PY, "dbe/cut_audio.py", str(tmp / "spec.json")])[-1])
        mp4 = out_dir / f"{cid}.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-i", str(tmp / "mix.wav"), "-map", "0:v", "-map", "1:a",
              "-c:v", "copy", "-c:a", M["acodec"], "-ar", str(M["ar"]), "-b:a", M["ab"], "-t", f"{cut['length']:.3f}",
              *(["-movflags", "+faststart"] if M.get("faststart") else []), str(mp4)])
        timings = {f: _json(FILMS / f / "timing.json", {}).get("lines", []) for f in srcs}
        (out_dir / f"{cid}.srt").write_text(E.srt(cut, timings))
        (out_dir / f"{cid}.otio").write_text(json.dumps(E.otio(cid, cut, fps, {f: str((b / "final.mp4").relative_to(ROOT)) for f, b in srcs.items()}), indent=1))
        shutil.rmtree(tmp, ignore_errors=True)
        made[cid] = {"file": str(mp4.relative_to(ROOT)), "aspect": cut["aspect"] or "master", "length_s": cut["length"],
                     "segments": [[s["film"], s["t0"], s["t1"], "/".join(s["snapped"])] for s in cut["segments"]],
                     "lufs": au["lufs"], "true_peak_db": au["true_peak_db"], "loudness_ok": abs(au["lufs"] + 14) <= 1 and au["true_peak_db"] <= -1}
    return {"cuts": made}


# ---------------- brand (plan 1.14) ----------------
def _brand(path="brand/brand.json"):
    b = _json(ROOT / path)
    if not b:
        raise FileNotFoundError(f"{path} not found")
    return b


@command("brand.check", path=("string", "brand file", "brand/brand.json"))
def brand_check(path="brand/brand.json"):
    """Measure the brand palette: WCAG contrast for every declared text pair, colour-blind separation of the accents
    (Machado 2009 simulation, CIEDE2000) and distance from each platform's interface colour."""
    from . import brand
    return brand.check(_brand(path))


@command("brand.assets", path=("string", "brand file", "brand/brand.json"), out=("string", "output folder", "brand/out"))
def brand_assets(path="brand/brand.json", out="brand/out"):
    """Generate the profile tile (720/400/180) and covers (YouTube, Facebook, LinkedIn, story) with text inside each
    platform's safe area, plus safe-area QA overlays. Refuses a palette that fails brand.check."""
    from . import brand
    b = _brand(path); chk = brand.check(b)
    if not chk["ok"]:
        raise ValueError("brand.check fails: " + "; ".join(chk["errors"]))
    made = brand.assets(b, ROOT / out, str(ROOT / "engine" / "fonts" / "Fredoka.ttf"))
    return {"out": out, "files": made, "warnings": chk["warnings"]}


# ---------------- motion: juggling and multi-body physics (WP-09) ----------------
def _beat_grid(name):
    sc = _json(FILMS / name / "score.json", {}) or {}
    return 60.0 / float(sc.get("bpm") or 100), float(sc.get("offset_s") or 0)


def _raw_shot(raw, shot):
    for sh in raw["shots"]:
        if sh["id"] == shot:
            return sh
    raise ValueError(f"no shot {shot!r}")


def _juggle_into(name, raw, shot):
    """solve the shot's juggle block into the raw shots.json (in memory); returns the solve summary or None"""
    from . import juggle as J
    rs = _raw_shot(raw, shot)
    if not rs.get("juggle"):
        return None
    tm = _json(FILMS / name / "timing.json", {})
    req = resolve_times(rs["juggle"], tm)
    span = resolve_times({"start": rs.get("start", 0), "end": rs.get("end", 0)}, tm)
    c = rs["cast"][int(req.get("cast", 0))]
    pup = _json(ROOT / c["puppet"])
    place = c.get("place") or {}
    if isinstance(place, list):
        place = place[0][1]
    beat, off = _beat_grid(name)
    res = J.solve(req, pup, place, beat, off, raw.get("fps", 30), float(span["start"]), float(span["end"]))
    old = {p.get("id"): p for p in rs.get("props", []) if p.get("solved") == "juggle"}
    for p in res["props"]:   # a later physics bake on the same ball survives a re-solve of the juggle
        if "track" in old.get(p["id"], {}):
            p["track"] = old[p["id"]]["track"]
    J.apply(rs, res)
    return {k: v for k, v in res.items() if k not in ("props", "ik", "ik_bend")}


@command("juggle.solve", name=("string", "film"), shot=("string", "shot id"),
         block=("object", "a juggle block to store first (pattern, start, end, every, dwell, subdiv, height, balls, cast); empty: the shot's own", None))
def juggle_solve(name, shot, block=None):
    """Solve a juggling pattern (WP-09): a siteswap ("3" cascade, "441", "531", ...) becomes one prop per ball with
    ballistic flights and both arms' IK keys (a scoop while carrying, a lift while empty), every throw and catch on
    the beat grid of score.json. The block stays in shots.json, so re-solving after a tempo change keeps it in step.
    Returns the contacts and whether all of them are on the grid."""
    d = _film(name)
    raw = _json(d / "shots.json")
    if block:
        _raw_shot(raw, shot)["juggle"] = block
    res = _juggle_into(name, raw, shot)
    if res is None:
        raise ValueError(f"shot {shot} has no juggle block")
    (d / "shots.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    return res


@command("physics.solve", name=("string", "film"), shot=("string", "shot id"),
         block=("object", "a physics block to store first (bodies, static, floor, walls, impulses, start, end, retime); empty: the shot's own", None))
def physics_solve(name, shot, block=None):
    """Bake a multi-body physics scene (WP-09) with Rapier's deterministic build: bodies (balls, boxes, or props
    already in the shot, which start from their own motion) fall, bounce and collide with each other and with static
    colliders; contacts are retimed onto the beat grid. Writes prop tracks into shots.json (re-solving the shot's
    juggle first, if it has one) and the bake's sha256, which a rerun reproduces."""
    d = _film(name)
    raw = _json(d / "shots.json")
    if block:
        _raw_shot(raw, shot)["physics"] = block
    res = _physics_into(name, raw, shot)
    (d / "shots.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    return res


def _physics_into(name, raw, shot):
    """juggle (if any) then bake the shot's physics into the raw shots.json in memory; returns the summary"""
    from . import physics as PH
    jug = _juggle_into(name, raw, shot)
    rs = _raw_shot(raw, shot)
    if not rs.get("physics"):
        raise ValueError(f"shot {shot} has no physics block")
    tm = _json(FILMS / name / "timing.json", {})
    res_shot = resolve_times(rs, tm)
    beat, off = _beat_grid(name)
    blk = {k: v for k, v in res_shot["physics"].items() if k != "solved_hash"}
    req = PH.request(blk, res_shot, raw.get("size", [1080, 1920]), raw.get("fps", 30), beat, off)
    out = PH.run(req)
    PH.apply(rs, {k: v for k, v in rs["physics"].items() if k != "solved_hash"}, out, req)
    return {"hash": out["hash"], "rapier": out["rapier"], "keys": out["keys"], "contacts": len(out["contacts"]),
            "bodies": list(out["bodies"]), **({"juggle": jug} if jug else {})}


def _motion_test():
    """WP-09 checks: the juggling solver, the physics bake, and juggle-demo re-solved from its blocks gives exactly the
    committed props, IK keys and tracks (a rerun is hash-equal), with every juggling contact on the beat grid."""
    from . import juggle as J, physics as PH
    bad, meas = [], {}
    j = J.self_test(); meas["juggle"] = j
    if not j["ok"]:
        bad.append({"juggle": j})
    p = PH.self_test(); meas["physics"] = p
    if not p["ok"]:
        bad.append({"physics": p})
    if PH.available() and (FILMS / "juggle-demo").exists():
        raw = _json(FILMS / "juggle-demo" / "shots.json")
        before = json.dumps(raw, sort_keys=True)
        r = _physics_into("juggle-demo", raw, "s1")
        same = json.dumps(raw, sort_keys=True) == before
        meas["juggle_demo"] = {"rerun_equal": same, "hash": r["hash"][:16], "on_grid": r["juggle"]["on_grid"], "throws": r["juggle"]["throws"],
                               "physics_keys_on_grid": all(abs(k["film"] / 0.3 - round(k["film"] / 0.3)) < 1e-6 for k in r["keys"]), "physics_keys": len(r["keys"])}
        if not (same and r["juggle"]["on_grid"] and meas["juggle_demo"]["physics_keys_on_grid"] and r["keys"]):
            bad.append({"juggle_demo": meas["juggle_demo"]})
    return bad, meas


# ---------------- interaction and locomotion (WP-11) ----------------
def _node_json(args, timeout=600):
    r = subprocess.run(["node", *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} failed: {(r.stderr or r.stdout)[-1500:]}")


def _interact_into(name, raw, shot):
    """solve the shot's interact block into the raw shots.json shot (in memory); returns the solve summary"""
    import tempfile
    rs = _raw_shot(raw, shot)
    if not rs.get("interact"):
        raise ValueError(f"shot {shot} has no interact block")
    tm = _json(FILMS / name / "timing.json", {})
    res = resolve_times(rs, tm)
    blk = {k: v for k, v in res["interact"].items() if k != "solved"}
    req = {"fps": raw.get("fps", 30), "start": res["start"], "end": res["end"], "interact": blk,
           "cast": [{"puppet": c["puppet"], "place": c.get("place"), "timeline": {k: v for k, v in (c.get("timeline") or {}).items() if k != "visemes_from"}} for c in res["cast"]]}
    with tempfile.TemporaryDirectory(prefix="interact_") as td:
        a, b = Path(td) / "req.json", Path(td) / "out.json"
        a.write_text(json.dumps(req))
        _node_json(["tools/interact.mjs", "solve", a, b])
        out = json.loads(b.read_text())
    for ci, o in enumerate(out["cast"]):
        c = rs["cast"][ci]
        tl = c.setdefault("timeline", {})
        if o.get("place"):
            c["place"] = o["place"]
        if o["clips"] or any(x.get("solved") == "interact" for x in tl.get("clips", [])):
            tl["clips"] = [x for x in tl.get("clips", []) if x.get("solved") != "interact"] + o["clips"]
        add = o["timeline"]
        cur = tl.get("lookat")
        cur = cur if isinstance(cur, list) else ([cur] if cur else [])
        looks = [x for x in cur if x.get("solved") != "interact"] + add.get("lookat", [])
        if looks:
            tl["lookat"] = looks
        else:
            tl.pop("lookat", None)
        for k in ("pins", "view"):
            if k in add:
                tl[k] = add[k]
        for k in ("ik", "ik_weight"):
            if k in add:
                tl[k] = {**tl.get(k, {}), **add[k]}
    rs["interact"] = {**{k: v for k, v in rs["interact"].items() if k != "solved"}, "solved": {"walks": out["walks"], "handshakes": out["handshakes"]}}
    return {"walks": out["walks"], "handshakes": out["handshakes"]}


@command("interact.solve", name=("string", "film"), shot=("string", "shot id"),
         block=("object", "an interact block to store first ({walks, handshakes, eye_contact}); empty: the shot's own", None))
def interact_solve(name, shot, block=None):
    """Interaction and locomotion (WP-11): walks along curved paths (Catmull-Rom through the points; the root speed
    matches the walk clip's stride and the walk ends on a passing step; feet planted while the root moves), handshakes
    (one character holds out a hand to the meeting point and pumps it, the other takes that hand: an IK target on
    another character, blended in and out by IK/FK weights) and eye contact (heads look at each other in a window).
    Writes places and timeline keys into shots.json; times may be line-relative or "arrive"."""
    d = _film(name)
    raw = _json(d / "shots.json")
    if block:
        _raw_shot(raw, shot)["interact"] = block
    res = _interact_into(name, raw, shot)
    (d / "shots.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    return res


@command("interact.measure", name=("string", "film"), shot=("string", "shot id"),
         points=("array", "optional checks [{cast, part, t, want: [x, y]}]: how far a part is from a frame point", None))
def interact_measure(name, shot, points=None):
    """The WP-11 measurements on the baked frames every renderer reads: how far a planted foot moves in the frame
    while it is in contact (max and mean px per frame, per walking character) and how far apart the two hands are
    during each solved handshake (max px)."""
    import tempfile
    s, sh, bdir, _ = _bake(name, shot)
    hands = []
    for h in ((sh.get("interact") or {}).get("solved") or {}).get("handshakes", []):
        hands.append({"a": h["a"], "b": h["b"], "start": h["start"], "end": h["end"]})
    with tempfile.TemporaryDirectory(prefix="measure_") as td:
        o, op = Path(td) / "m.json", Path(td) / "opts.json"
        op.write_text(json.dumps({"hands": hands, "points": points or []}))
        _node_json(["tools/interact.mjs", "measure", bdir / f"{shot}.spec.json", bdir / f"{shot}.baked.json", o, op])
        m = json.loads(o.read_text())
    m["ok"] = all(f["max_slide_px"] <= 1.0 for f in m["feet"]) and all(h["max_gap_px"] <= 2.0 for h in m["hands"]) and all(q["gap_px"] <= 2.0 for q in m.get("points", []))
    return m


def _interact_test():
    """WP-11 checks: loader pieces (path speed and facing, exact contact starts, IK/FK weights, targets on other
    characters), and handshake-demo re-solved from its block gives exactly the committed shot, with planted feet that
    slide at most 1 px per frame and hands that meet within 2 px on the baked frames every renderer reads."""
    bad, meas = [], {}
    r = subprocess.run(["node", "tools/interact.mjs", "selftest"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    st = json.loads(r.stdout or "{}") if r.returncode == 0 else {"ok": False, "error": r.stderr[-500:]}
    meas["loader"] = st
    if not st.get("ok"):
        bad.append({"loader": st})
    if (FILMS / "handshake-demo").exists():
        raw = _json(FILMS / "handshake-demo" / "shots.json")
        before = json.dumps(raw, sort_keys=True)
        _interact_into("handshake-demo", raw, "s1")
        same = json.dumps(raw, sort_keys=True) == before
        m = interact_measure("handshake-demo", "s1")
        meas["handshake_demo"] = {"resolve_equal": same, "feet": [{k: f[k] for k in ("cast", "max_slide_px", "mean_slide_px", "planted_frames")} for f in m["feet"]], "hands": m["hands"]}
        if not (same and m["ok"] and m["feet"] and m["hands"]):
            bad.append({"handshake_demo": meas["handshake_demo"]})
    # v0.9: dbe/geom.py (Synfig, Grease Pencil) computes the same matrices as puppet.js with stretched parts
    from . import geom as G
    pose = {"angles": {"upperarm_R": 35, "forearm_R": -50, "hand_R": 10, "head": 6}, "shifts": {"head": [3, -2]}, "scales": {"upperarm_R": [0.9, 1.4], "forearm_R": [1, 1.2], "torso": [1.1, 0.95]}}
    r = subprocess.run(["node", "tools/interact.mjs", "matrices", json.dumps(pose)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    js = json.loads(r.stdout or "{}")
    py = G.part_matrices(_json(ROOT / "puppet/examples/pip.puppet.json"), pose["angles"], pose["shifts"], pose["scales"])
    err = max((abs(a - b) for k in py for a, b in zip(py[k], js.get(k, [0] * 6))), default=1)
    meas["geom_vs_loader"] = round(err, 9)
    if err > 1e-6:
        bad.append({"geom_vs_loader": err})
    # stretch-demo: the stretched arm reaches the balloon string on the baked frames
    if (FILMS / "stretch-demo").exists():
        m2 = interact_measure("stretch-demo", "s1", points=[{"cast": 0, "part": "hand_R", "t": 3.0, "want": [722, 640]}])
        meas["stretch_demo"] = m2["points"]
        if not m2["ok"]:
            bad.append({"stretch_demo": m2["points"]})
    return bad, meas
