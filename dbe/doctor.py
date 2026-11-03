"""Environment doctor (work package WP-02): what this machine has, what it lacks, and the exact fix for each gap.

Checks are grouped by what they unlock:
    core     the engine, Studio, the SVG renderer and `python -m dbe test`
    audio    voices (Kokoro, Piper), alignment, mixing and loudness
    tools    optional features: PSD import, Act it out (MediaPipe), extra renderers
Each check is {name, group, ok, required, detail, fix}. `ok` overall means every required check passed.
Read-only: `tools/setup.sh` applies the fixes.
"""
import ctypes.util
import hashlib
import importlib.metadata as md
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import ROOT

VOICES = Path(os.environ.get("DBE_VOICES", str(Path.home() / "voices")))
KOKORO_FILES = {  # model-files-v1.0 from github.com/thewh1teagle/kokoro-onnx releases (Apache-2.0 weights)
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
IMPORT_NAME = {"Pillow": "PIL", "piper-tts": "piper", "faster-whisper": "faster_whisper", "kokoro-onnx": "kokoro_onnx",
               "psd-tools": "psd_tools", "opencv-python-headless": "cv2"}


def requirements(fname):
    out = []
    f = ROOT / fname
    for line in (f.read_text().splitlines() if f.exists() else []):
        line = line.split("#")[0].strip()
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(==|>=)?\s*([\w.\-]+)?", line)
        if m and line:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def _ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd, timeout=60, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        return r.returncode, (r.stdout or r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def check(deep=True):
    checks = []

    def add(name, group, ok, required, detail="", fix=""):
        checks.append({"name": name, "group": group, "ok": bool(ok), "required": required, "detail": detail, **({"fix": fix} if not ok and fix else {})})

    add("python >= 3.11", "core", sys.version_info >= (3, 11), True, sys.version.split()[0], "install Python 3.11 or newer")
    for group, fname, required in (("core", "requirements-core.txt", True), ("audio", "requirements-audio.txt", True), ("tools", "requirements-tools.txt", False)):
        for name, op, ver in requirements(fname):
            try:
                have = md.version(name)
            except md.PackageNotFoundError:
                add(f"python package {name}", group, False, required, "not installed", f"bash tools/setup.sh python   # or: python -m pip install -r {fname}")
                continue
            good = not ver or (op == ">=" and _ver_tuple(have) >= _ver_tuple(ver)) or (op == "==" and have == ver)
            add(f"python package {name}", group, good, required and (op != "==" or good), f"{have}" + (f" (wants {op}{ver})" if ver and not good else ""),
                f"python -m pip install '{name}{op or ''}{ver or ''}'")
    for tool, group, required, fix in (("ffmpeg", "core", True, "apt-get install -y ffmpeg"), ("ffprobe", "core", True, "apt-get install -y ffmpeg"),
                                       ("node", "core", True, "install Node.js 20 or newer"), ("git", "core", True, "apt-get install -y git"),
                                       ("synfig", "tools", False, "apt-get install -y synfig   (Synfig renderer)"),
                                       ("blender", "tools", False, "bash tools/setup.sh blender   (Blender 5.2 LTS: the Grease Pencil renderer needs 4.3 or newer)"),
                                       ("pencil2d", "tools", False, "bash tools/setup.sh oss   (Pencil2D: drawn levels, WP-34)"),
                                       ("inkscape", "tools", False, "bash tools/setup.sh oss   (Inkscape: path booleans, WP-34)"),
                                       ("melt", "tools", False, "apt-get install -y melt   (editor round trips)"),
                                       ("krita", "tools", False, "bash tools/setup.sh oss   (Krita: .kra round-trip test, WP-18; .kra files are read without it)")):
        p = shutil.which(tool)
        add(f"program {tool}", group, p, required, p or "not on PATH", fix)
    node_path = _run(["npm", "root", "-g"])[1] if shutil.which("npm") else ""
    env = {**os.environ, "NODE_PATH": os.pathsep.join(x for x in (os.environ.get("NODE_PATH", ""), node_path) if x)}
    code, out = _run(["node", "-e", "console.log(require('playwright/package.json').version)"], env=env) if shutil.which("node") else (1, "no node")
    add("node package playwright", "core", code == 0, True, out.splitlines()[-1] if out else "", "npm install -g playwright && npx playwright install chromium")
    if deep and code == 0:   # the browser actually starts (every SVG render and page test needs it)
        js = "require('playwright').chromium.launch().then(async b=>{const p=await b.newPage();await p.setContent('<b>ok</b>');console.log(await p.textContent('b'));await b.close()})"
        c2, o2 = _run(["node", "-e", js], timeout=90, env=env)
        add("headless Chromium starts", "core", c2 == 0 and o2.endswith("ok"), True, o2[-200:], "npx playwright install chromium   (or point PLAYWRIGHT_BROWSERS_PATH at an installed browser)")
    from . import physics as PHY   # WP-09: deterministic Rapier for physics.solve (an npm package in tools/physics)
    add("node package @dimforge/rapier2d-deterministic-compat", "tools", PHY.available(), False, str(PHY.PKG) if PHY.available() else "not installed",
        "bash tools/setup.sh physics   (deterministic Rapier 0.21: physics.solve, WP-09)")
    from . import assists as ASM   # WP-43 ML assists: model files (fetched by tools/setup.sh models, or on first use)
    for name in ("rife49", "depth_small"):
        mp = ASM.MODELS / ASM.REGISTRY[name]["file"]
        add(f"assist model {name}", "tools", mp.exists(), False, str(mp) if mp.exists() else "not downloaded",
            "bash tools/setup.sh models   (or let level.inbetween / depth.planes fetch it on first use)")
    egl = ctypes.util.find_library("EGL")
    add("system library libEGL", "tools", egl, False, egl or "missing (MediaPipe's native library needs it)", "apt-get install -y libegl1 libgles2")
    kd = VOICES / "kokoro"
    for fn, sha in KOKORO_FILES.items():
        p = kd / fn
        ok = p.exists() and (not deep or _sha(p) == sha)
        add(f"Kokoro model {fn}", "audio", ok, True, str(p) if p.exists() else f"missing in {kd}" , f"bash tools/setup.sh models   # or: curl -L -o {p} {KOKORO_URL}{fn}")
    add("Kokoro timed model (phoneme timings)", "audio", (kd / "kokoro-v1.0-timed.onnx").exists(), False, "made once from kokoro-v1.0.onnx",
        "bash tools/setup.sh models   (python -c 'import sys; sys.path.insert(0,\"engine\"); import kokoro_voice, pathlib; kokoro_voice.timed_model(pathlib.Path(\"%s\"))')" % kd)
    try:
        from . import actout as AO
        for kind, (fn, url, sha) in AO.MODEL_FILES.items():
            p = AO.MODELS / fn
            add(f"MediaPipe model {fn}", "tools", p.exists() and (not deep or _sha(p) == sha), False, str(p) if p.exists() else "missing (fetched on first use)",
                "bash tools/setup.sh models")
    except Exception as e:
        add("MediaPipe models", "tools", False, False, str(e)[:120])
    reg = json.loads((ROOT / "voices" / "registry.json").read_text()).get("voices", {}) if (ROOT / "voices" / "registry.json").exists() else {}
    piper = [v for v in reg if not v.startswith("kokoro:") and (VOICES / f"{v}.onnx").exists()]
    add("Piper voices installed", "audio", True, False, f"{len(piper)} of {sum(1 for v in reg if not v.startswith('kokoro:'))} registry voices (films use Kokoro)")
    du = shutil.disk_usage(ROOT)
    add("free disk >= 5 GB", "core", du.free >= 5e9, True, f"{du.free / 1e9:.1f} GB free", "delete renders under films/*/build and out/")
    add("CPU cores", "core", True, False, f"{os.cpu_count()} (renders use one browser per core)")
    req = [c for c in checks if c["required"]]
    fixes = []
    for c in checks:
        if not c["ok"] and c.get("fix") and c["fix"] not in fixes:
            fixes.append(c["fix"])
    return {"ok": all(c["ok"] for c in req), "missing_required": [c["name"] for c in req if not c["ok"]],
            "missing_optional": [c["name"] for c in checks if not c["required"] and not c["ok"]], "fixes": fixes, "checks": checks}
