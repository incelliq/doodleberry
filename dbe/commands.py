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
        reg = _json(ROOT / "voices" / "registry.json", {}).get("voices", {})
        if reg.get(voice["voice"], {}).get("status") != "clean":
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
{clip_tags}<script src="../../../sets/sets.js"></script><script src="../../../sets/more.js"></script><script src="../../../assets/icons/lucide.js"></script><script src="../../../dbe/player/kit.js"></script><script src="../../../dbe/player/fx.js"></script>{tags}
<script>window.SHOTS={json.dumps(_shots(name))};window.TIMING={json.dumps(_json(d / 'timing.json', {}))};window.SCRIPT={json.dumps(_json(d / 'script.json', {}))};window.DATA={json.dumps(_json(d / 'data.json', {}))};window.BRAND={json.dumps(_json(ROOT / 'brand' / 'brand.json', {}) if _shots(name).get('brand') else None)};</script>
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
    if renderer != "svg" and any(st.get("image") for c in baked["cast"] for part in _json(c["puppet"])["parts"].values() for st in part["strokes"]):
        raise ValueError(f"shot {shot} uses raster-part puppets (scanned ink); render it with svg (other renderers draw vector parts only, for now)")
    if renderer != "svg" and sh.get("props"):
        raise ValueError(f"shot {shot} has props; render it with svg (props are drawn by the SVG player only, for now)")
    W, H = s.get("size", [1080, 1920]); fps = s.get("fps", 30)
    out = bdir / (f"{shot}.mp4" if renderer == own else f"{shot}.{renderer}.mp4")
    if renderer == "svg":
        _render_page(_player_page(name), f"shot={shot}", out)
    elif renderer == "synfig":
        # characters by Synfig (alpha), over the animated set from the player
        setv = _set_video(name, sh, bdir)
        sif = bdir / f"{shot}.sif"; sif.write_text(X.to_synfig(baked, (W, H), transparent=True))
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
ENGINE_FILES = ["dbe/player/player.js", "dbe/player/kit.js", "dbe/player/fx.js", "puppet/loader/puppet.js", "puppet/loader/acting.js", "sets/sets.js", "sets/more.js", "tools/bake.mjs",
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
            b = _json(ROOT / "brand" / "brand.json", {}); pal = b.get("palette", {}); bc = b.get("captions", {})
            res = lambda v: pal.get(v, v) if isinstance(v, str) else v
            for k in ("highlight", "outline", "text"):
                if bc.get(k) and k not in cs:
                    cs[k] = res(bc[k])
        ass.write_text(make_ass(_cut_timing(s, _json(d / "timing.json", {}), s.get("caption_lines")), s.get("size", [1080, 1920]), **cs))
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
                              "directed": bool(kk.get("directed")), "weight": kk.get("weight", 1)})
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


@command("timeline.edit", name=("string", "film"), op=("string", "move_clip | resize_clip | add_clip | delete_clip"),
         shot=("string", "shot id"), cast=("integer", "cast index in the shot"), index=("integer", "clip layer index (move, resize, delete)", -1),
         start=("number", "new start in film seconds (move, add)", None), end=("number", "new end in film seconds (resize; null = the clip's own length)", None),
         clip=("string", "clip name (add)", ""), anchor=("string", "for add: a line id to anchor the start to (line-relative)", ""))
def timeline_edit(name, op, shot, cast, index=-1, start=None, end=None, clip="", anchor=""):
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
    errs = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:120]}" for e in jsonschema.Draft202012Validator(_json(ROOT / "puppet" / "spec" / "puppet.schema.json")).iter_errors(puppet)]
    if errs:
        raise ValueError("not a valid puppet: " + "; ".join(errs[:5]))
    new = not f.exists(); f.parent.mkdir(parents=True, exist_ok=True)
    puppet.setdefault("meta", {})["cast_path"] = str(f.relative_to(ROOT))
    f.write_text(json.dumps(puppet))
    if new:
        cast_add(str(f.relative_to(ROOT)), f.stem.split(".")[0], (puppet.get("meta") or {}).get("author", "Rig Canvas"), (puppet.get("meta") or {}).get("license", "CC0-1.0"), "drawn in the Rig Canvas", rights="open")
    return {"path": str(f.relative_to(ROOT)), "new": new, "poses": len(puppet.get("poses") or {}), "clips": len(puppet.get("clips") or {})}


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
    co = LQ.cold_open(res["shots"], tm, res.get("size", [1080, 1920])); rd = LQ.reading_time(res["shots"], tm)
    facts = _json(d / "facts.json", {"facts": []}).get("facts", [])
    checks = {"cold_open": bool(co["character_in_frame_one"] and co["first_text_s"] is not None and co["first_text_s"] <= 1.5),
              "reading_time": not rd["too_short"] and rd["caption_words_per_s"] <= 3.2}
    return {"ok": all(checks.values()), "checks": checks, "cold_open": co, "reading": rd,
            "facts_need_sources": [f["id"] for f in facts if not f.get("source")]}


@command("film.from_template", name=("string", "new film"), format=("string", "myth_vs_data | dialogue | wonder_story | we_reran_it | anniversary | series"),
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
    voices = {"ravi": "kokoro:am_michael", "momo": "kokoro:af_heart", "priya": "kokoro:af_bella"}
    spk = {l["speaker"] for l in lines}
    script = {"title": brief.get("title", name), "format": format,
              "speakers": {k: ({"voice": voices.get(k, "kokoro:af_sarah"), **({"fx": {"pitch": 1.2, "formant": 1.08, "range": 1.25}} if k == "momo" else {})}) for k in sorted(spk)},
              "lead_in_s": 0.6, "gap_s": 0.45, "lines": lines}
    (d / "script.json").write_text(json.dumps(script, indent=1, ensure_ascii=False))
    (d / "shots.json").write_text(json.dumps({"title": brief.get("title", name), "size": [1080, 1920], "fps": 30, "captions": True, "shots": shots}, indent=1, ensure_ascii=False))
    (d / "facts.json").write_text(json.dumps({"facts": facts}, indent=1, ensure_ascii=False))
    (d / "score.json").write_text(json.dumps({"length_s": 30, "bpm": 96, "offset_s": 0, "sections": [{"kind": "main", "from_beat": 0, "to_beat": 64, "chords": ["F", "Am", "Dm", "C"], "end_chord": "F"}]}, indent=1))
    if brief.get("data"):
        (d / "data.json").write_text(json.dumps(brief["data"], indent=1, ensure_ascii=False))
    if edit:
        (d / "edit.json").write_text(json.dumps(edit, indent=1))
    (d / "brief.md").write_text(f"# {brief.get('title', name)}\n\nFormat: {format} ({FM.TEMPLATES.get(format, {}).get('about', 'series of parts')}).\n\n"
                                + "\n".join(f"- {k}: {v}" for k, v in brief.items() if isinstance(v, (str, int, float))) + "\n")
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
    title = b["title"]
    checks = {"title_under_50_chars": len(title) <= 50, "has_takeaway": bool(b.get("takeaway")), "has_sources": bool(srcs) or not facts,
              "cover_chosen": True, "subtitles": (d / "build" / "captions.srt").exists()}
    posts = {}
    for k, pf in prof.items():
        n = pf.get("hashtags", 4)
        body = f"{takeaway}{part}" + (f" {hook}" if hook else "")
        posts[k] = {"caption": body + ("\n\n" + " ".join(tags[:n]) if tags else ""), "aspect": pf["aspect"], "captions": pf["captions"],
                    **({"title": title, "description": body + ("\n\n" + "\n".join(chapters) if chapters else "") + ("\n\n" + pinned if pinned else "")} if k == "youtube" else {})}
    pkg = {"film": name, "title": title, "takeaway": takeaway, "posts": posts, "pinned_comment": pinned, "alt_text": alt,
           "chapters": chapters, "cover": "build/package/cover.png", "video": "build/final.mp4", "subtitles": ["build/captions.srt", "build/captions.vtt"],
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
    return {"package": str((pk / "posts.md").relative_to(ROOT)), "checks": checks, "chapters": len(chapters)}


@command("asset.check")
def asset_check():
    """Every tracked third-party file (fonts, vendored scripts, images, sounds, models) must have a row in
    assets/manifest.json with its licence; reports what is missing."""
    man = _json(ROOT / "assets" / "manifest.json", {"files": []})
    known = [f["path"] for f in man["files"]] + [g["path"] for g in man.get("generated", [])]
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    pat = re.compile(r"(^engine/vendor/|\.(ttf|otf|woff2?|png|jpe?g|gif|webp|svg|wav|mp3|ogg|flac|glb|gltf|fbx|onnx)$)", re.I)
    third = [t for t in tracked if pat.search(t) and not t.startswith(("tests/golden/", "dbe/", "puppet/canvas/")) and not t.endswith(("LICENSE", "LICENSE.md"))]
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
