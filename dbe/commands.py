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
    r = _run([PY, "dbe/gestures.py", str(d)], timeout=600)
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
    return resolve_times(s, _json(FILMS / name / "timing.json", {})) if resolve else s


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
    for c in sh.get("cast", []):
        h.update((ROOT / c["puppet"]).read_bytes())
        sp = (c.get("timeline") or {}).get("visemes_from") or c.get("speaker")
        if sp:
            h.update(json.dumps((_json(FILMS / name / "timing.json", {}).get("visemes") or {}).get(sp, [])).encode())
    h.update(json.dumps(_json(FILMS / name / "timing.json", {}).get("lines", []), sort_keys=True).encode())  # bubbles, line-relative times
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
