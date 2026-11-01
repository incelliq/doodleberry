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
    r = film_validate(name)
    r["errors"] = r["errors"] + _rights_errors(name)
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
    reg = _json(ROOT / "voices" / "registry.json", {}).get("voices", {})
    bad = {spk: (v.get("voice"), reg.get(v.get("voice"), {"status": "unknown", "license": "not in voices/registry.json"}))
           for spk, v in (script.get("speakers") or {}).items() if reg.get(v.get("voice"), {}).get("status") != "clean"}
    if bad and not script.get("allow_restricted_voices"):
        raise PermissionError("voice licence gate: " + "; ".join(f"{spk} uses {vid} ({r['status']}: {r['license']})" for spk, (vid, r) in bad.items())
                              + '. Pick a clean voice (voices.list) or set "allow_restricted_voices": true in script.json for internal tests.')
    return bad


@command("voices.list")
def voices_list():
    """Piper voices with licence status (clean / restricted / unclear) and whether each is installed."""
    reg = _json(ROOT / "voices" / "registry.json", {}).get("voices", {})
    return {vid: {**r, "installed": (Path(VOICES) / f"{vid}.onnx").exists()} for vid, r in reg.items()}


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
            lines.append(f"Character: {e.get('name', c['puppet'])} by {e.get('author', 'unknown')} ({lic})")
    for spk, v in (sc.get("speakers") or {}).items():
        r = reg.get(v.get("voice"), {})
        lines.append(f"Voice of {spk}: Piper voice {v.get('voice')} ({r.get('license', 'licence not recorded')})")
    rend = sorted({sh.get("renderer", "svg") for sh in s["shots"]})
    names = {"svg": "Chromium (Playwright)", "synfig": "Synfig (GPL-3.0)", "grease-pencil": "Blender Grease Pencil (GPL)", "lottie": "lottie-web (MIT)"}
    uses = {"captions", "player"} | {f"renderer:{r}" for r in rend}
    assets = [f["attribution"] for f in man["files"] if set(f.get("used_by", [])) & uses]
    lines += ["", "Rendered with " + ", ".join(names.get(r, r) for r in rend) + "; speech by Piper; alignment by faster-whisper (MIT); audio by ffmpeg.",
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
            return {k: (t_of(v) if k in ("start", "end", "t") and isinstance(v, str) and k != "clip" else walk(v)) for k, v in o.items()}
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
    spec = {"fps": fps, "frames": round((sh["end"] - sh["start"]) * fps), "start": sh["start"], "cast": cast,
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
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>@font-face{{font-family:'Fredoka';src:url('../../../engine/fonts/Fredoka.ttf')}}html,body{{margin:0;background:#000;overflow:hidden}}text{{font-family:'Fredoka',sans-serif}}</style></head>
<body><svg id="stage" xmlns="http://www.w3.org/2000/svg"></svg>
<script src="../../../engine/timeline.js"></script><script src="../../../puppet/loader/puppet.js"></script><script src="../../../puppet/loader/acting.js"></script>
<script src="../../../puppet/clips/humanoid.js"></script><script src="../../../sets/sets.js"></script>{tags}
<script>window.SHOTS={json.dumps(_shots(name))};window.TIMING={json.dumps(_json(d / 'timing.json', {}))};</script>
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
@command("film.render", name=("string", "film"), only=("array", "shot ids to (re)render; default all", None))
def film_render(name, only=None):
    """Render every shot with its renderer, assemble, score and mix the audio, mux, and run QA."""
    _require_valid(name)
    d = _film(name); s = _shots(name); fps = s.get("fps", 30)
    done = []
    for sh in s["shots"]:
        mp4 = d / "build" / "shots" / f"{sh['id']}.mp4"
        if only is None or sh["id"] in only or not mp4.exists():
            done.append(shot_render(name, sh["id"]))
    lst = d / "build" / "shots" / "concat.txt"
    lst.write_text("".join(f"file '{(d / 'build' / 'shots' / (sh['id'] + '.mp4')).resolve()}'\n" for sh in s["shots"]))
    pic = d / "build" / "picture.mp4"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps), str(pic)])
    if s.get("captions", True):
        # one caption pass over the joined picture, so every renderer gets the same word-timed captions
        from .captions import make_ass
        ass = d / "build" / "captions.ass"
        ass.write_text(make_ass(_json(d / "timing.json", {}), s.get("size", [1080, 1920]), **(s.get("caption_style") or {})))
        capd = d / "build" / "picture_cap.mp4"
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-vf", f"subtitles={ass.relative_to(ROOT)}:fontsdir=engine/fonts",
              "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(capd)])
        pic = capd
    # sound cues: a soft whoosh on every cut plus any cues the shots declare
    cues = [{"t": sh["start"], "type": "whoosh", "gain": 0.7} for sh in s["shots"][1:]]
    for sh in s["shots"]:
        cues += [{"t": c["t"], "type": c["type"], "gain": c.get("gain", 1)} for c in sh.get("cues", [])]
    (d / "build" / "cues.json").write_text(json.dumps(sorted(cues, key=lambda c: c["t"])))
    total = s["shots"][-1]["end"]
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
    tm = _json(d / "timing.json", {})
    (d / "build" / "captions.srt").write_text(make_srt(tm)); (d / "build" / "captions.vtt").write_text(make_vtt(tm))
    qa = qa_run(name)
    mb = final.stat().st_size / 1e6
    return {"rendered": done, "final": str(final.relative_to(ROOT)), "size_mb": round(mb, 1), "under_cap": mb <= M.get("max_mb", 100),
            "subtitles": ["build/captions.srt", "build/captions.vtt"], "qa": qa.get("checks"), "layout_advisory": qa.get("layout_advisory_failures")}


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
        (FILMS / name / "build" / "qa.json").write_text(json.dumps(rep, indent=1))
    return rep


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
