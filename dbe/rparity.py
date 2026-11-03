"""Renderer parity (WP-14): the same shot, drawn by each renderer, compared by silhouette.

Every renderer reads the same baked acting (tools/bake.mjs), so the characters should stand in the same place with
the same outline whichever renderer draws them. For a shot and a few moments, each renderer draws the cast alone on
a transparent background:

    svg            the player page with castonly=1 (tools/stills.mjs)
    synfig         the shot's Synfig document (transparent), one frame per moment (synfig --time)
    lottie         the shot's Lottie animation (no plate), lottie-web in Chromium, one frame per moment
    grease-pencil  Blender's Grease Pencil, when Blender is installed (DBE_BLENDER)

and the silhouettes (alpha over half) are compared with the SVG renderer's: intersection over union per moment. A
renderer that cannot draw a shot says why (`refusals`), and a refusal is a result, not a failure.

CAPABILITIES records what each renderer draws, so a shot that needs more is refused up front with a clear reason.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from . import ROOT

CAPABILITIES = {   # feature -> renderers that draw it (svg draws everything)
    "vector parts": {"svg", "synfig", "lottie", "grease-pencil"},
    "swaps and lip-sync": {"svg", "synfig", "lottie", "grease-pencil"},
    "views": {"svg", "synfig", "lottie", "grease-pencil"},
    "camera keys": {"svg", "synfig", "lottie", "grease-pencil"},
    "raster parts": {"svg", "synfig", "lottie"},
    "clip-driven layer order": {"svg", "synfig", "lottie"},
    "mesh parts": {"svg"},
    "drawn levels (raster)": {"svg", "synfig", "lottie"},
    "props": {"svg"},
    "motion effects (fx)": {"svg"},
    "toon shading": {"svg"},
    "compositor planes (comp)": {"svg"},
    "overlays and kit": {"svg"},
}


DEGRADES = {   # styles a renderer draws the shot without (a known difference, not a refusal)
    "line boil": {"svg"},
}


def degrades(renderer, shot):
    st = shot.get("style") or {}
    return sorted(k for k, ok in DEGRADES.items() if renderer not in ok and (k != "line boil" or st.get("boil")))


def needs(shot, puppets):
    """the features a shot uses"""
    f = {"vector parts", "swaps and lip-sync"}
    if shot.get("camera"):
        f.add("camera keys")
    for p in puppets:
        strokes = [st for part in p.get("parts", {}).values() for st in part.get("strokes", [])] + \
                  [st for sw in (p.get("swaps") or {}).values() for sh in sw.get("shapes", {}).values() for st in sh]
        if any("image" in st for st in strokes):
            f.add("drawn levels (raster)" if p.get("template") == "level" else "raster parts")
        if any("mesh" in st for st in strokes):
            f.add("mesh parts")
        if p.get("views"):
            f.add("views")
        if any((c.get("z") or {}) for c in (p.get("clips") or {}).values()) or (p.get("controls") and any("z." in json.dumps(v) for v in p["controls"].values())):
            f.add("clip-driven layer order")
    if shot.get("props"):
        f.add("props")
    if shot.get("fx"):
        f.add("motion effects (fx)")
    if (shot.get("style") or {}).get("toon"):
        f.add("toon shading")
    if shot.get("comp"):
        f.add("compositor planes (comp)")
    return f


def refusal(renderer, shot, puppets):
    missing = sorted(x for x in needs(shot, puppets) if renderer not in CAPABILITIES.get(x, {"svg"}))
    return f"{renderer} cannot draw: {', '.join(missing)}" if missing else None


def rgba(png, size=(270, 480)):
    from PIL import Image
    return np.asarray(Image.open(png).convert("RGBA").resize(size, Image.BILINEAR)).astype(np.int16)


def silhouette(png, size=(270, 480)):
    """the filled outline (holes filled), so thin line art is compared by its shape, not by its 2-pixel lines"""
    from scipy import ndimage
    m = rgba(png, size)[..., 3] > 127
    return ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))


def line_f1(pa, pb, tol=1):
    """ink of each render that lies within tol pixels (at 270 x 480, about 4 at full size) of the other's ink: an
    F-score that judges line art by its lines"""
    from scipy import ndimage
    A, B = rgba(pa)[..., 3] > 127, rgba(pb)[..., 3] > 127
    if not A.any() and not B.any():
        return 1.0
    p_ = (B & ndimage.binary_dilation(A, iterations=tol)).sum() / max(1, B.sum())
    r_ = (A & ndimage.binary_dilation(B, iterations=tol)).sum() / max(1, A.sum())
    return float(2 * p_ * r_ / max(1e-9, p_ + r_))


def colour_diff(a, b):
    """mean RGB difference (0-255) where both renders have ink: wrong colours or a wrong layer order show here"""
    m = (a[..., 3] > 200) & (b[..., 3] > 200)
    return float(np.abs(a[..., :3] - b[..., :3])[m].mean()) if m.any() else 0.0


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def stills_svg(C, name, shot, times, out):
    page = C._player_page(name)
    r = subprocess.run(["node", "tools/stills.mjs", str(page), f"shot={shot}&castonly=1&captions=0", str(out / "svg")] + [f"{t:.3f}" for t in times],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return [out / f"svg_{t:.3f}.png" for t in times]


def stills_synfig(C, name, shot, times, out):
    from . import exporters as X
    s, sh, bdir, baked = C._bake(name, shot)
    W, H = s.get("size", [1080, 1920])
    (out / "assets").mkdir(exist_ok=True)
    sif = out / "shot.sif"; sif.write_text(X.to_synfig(baked, (W, H), transparent=True, assets_dir=out / "assets"))
    paths = []
    for t in times:
        p = out / f"synfig_{t:.3f}.png"
        subprocess.run(["synfig", str(sif), "-t", "png", "-o", str(p), "--time", f"{t:.4f}s", "-q"], capture_output=True, timeout=600, check=True)   # with the unit: a bare number is read as frames
        paths.append(p)
    return paths


def stills_lottie(C, name, shot, times, out):
    s, sh, bdir, baked = C._bake(name, shot)
    W, H = s.get("size", [1080, 1920]); fps = s.get("fps", 30)
    lj = ROOT / C.export_lottie(name, shot, background="none")["path"]
    page = out / "lottie.html"
    page.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}#a{{width:{W}px;height:{H}px}}</style></head><body><div id="a"></div>
<script src="{ROOT}/engine/vendor/lottie/lottie.min.js"></script><script>const anim=lottie.loadAnimation({{container:document.getElementById('a'),renderer:'svg',loop:false,autoplay:false,animationData:{lj.read_text()}}});
anim.addEventListener('DOMLoaded',()=>{{window.ready=true;}});</script></body></html>""")
    js = out / "lottie_stills.mjs"
    js.write_text("""import { createRequire } from 'module'; import path from 'path';
const require = createRequire('%s/tools/x.mjs'); const { chromium } = require('playwright');
const [page, out, W, H, ...frames] = process.argv.slice(2);
const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage({ viewport: { width: +W, height: +H } });
await p.goto('file://' + path.resolve(page)); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
for (const f of frames) { await p.evaluate(ff => anim.goToAndStop(+ff, true), f); await p.screenshot({ path: `${out}_${f}.png`, omitBackground: true }); }
await b.close();""" % ROOT)
    frames = [str(round(t * fps)) for t in times]
    subprocess.run(["node", str(js), str(page), str(out / "lottie"), str(W), str(H)] + frames, cwd=ROOT, capture_output=True, timeout=600, check=True)
    return [out / f"lottie_{f}.png" for f in frames]


def stills_gp(C, name, shot, times, out):
    import os
    from . import exporters as X
    s, sh, bdir, baked = C._bake(name, shot)
    W, H = s.get("size", [1080, 1920]); fps = s.get("fps", 30)
    gpj = out / "gp.json"; gpj.write_text(json.dumps(X.to_gp_frames(baked, (W, H))))
    frames = [round(t * fps) + 1 for t in times]   # Grease Pencil keyframes start at 1
    env = {**os.environ, "DBE_GP_FRAMES": ",".join(map(str, frames))}
    r = subprocess.run([C.BLENDER, "-b", "--factory-startup", "--python", "dbe/blender_gp.py", "--", str(gpj), str(out / "gp_"), "-", "0.5"],
                       cwd=ROOT, capture_output=True, text=True, env=env, timeout=3600)
    paths = [out / f"gp_{f:04d}.png" for f in frames]
    if r.returncode or not all(p.exists() for p in paths):
        raise RuntimeError(f"blender: {(r.stderr or r.stdout)[-400:]}")
    return paths


STILLS = {"synfig": stills_synfig, "lottie": stills_lottie, "grease-pencil": stills_gp}


def run(name, shot, times=None, renderers=("synfig", "lottie", "grease-pencil"), min_iou=0.85, max_colour=24.0):
    from . import commands as C
    s = C._shots(name); sh = next(x for x in s["shots"] if x["id"] == shot)
    puppets = [json.loads((ROOT / c["puppet"]).read_text()) for c in sh.get("cast", [])]
    dur = sh["end"] - sh["start"]
    times = times or [round(dur * k, 3) for k in (0.2, 0.5, 0.8)]
    out = ROOT / "out" / "rparity" / name / shot; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    refp = stills_svg(C, name, shot, times, out); ref = [silhouette(p) for p in refp]; refc = [rgba(p) for p in refp]
    res = {"film": name, "shot": shot, "times": times, "needs": sorted(needs(sh, puppets)), "renderers": {}, "refusals": {}}
    for r in renderers:
        why = refusal(r, sh, puppets)
        if not why and r == "grease-pencil" and not C.BLENDER:
            why = "grease-pencil: Blender is not installed (DBE_BLENDER)"
        if not why and r not in STILLS:
            why = f"{r}: no still renderer"
        if why:
            res["refusals"][r] = why; continue
        try:
            ps = STILLS[r](C, name, shot, times, out); sil = [silhouette(p) for p in ps]; cols = [rgba(p) for p in ps]
        except Exception as e:
            res["renderers"][r] = {"error": str(e)[-300:], "ok": False}; continue
        ious = [round(iou(a, b), 3) for a, b in zip(ref, sil)]
        lf = [round(line_f1(a, b), 3) for a, b in zip(refp, ps)]
        scores = [max(x, y) for x, y in zip(ious, lf)]   # filled shapes for solid characters, lines for line art
        cd = [round(colour_diff(a, b), 1) for a, b in zip(refc, cols)]
        res["renderers"][r] = {"iou": ious, "line_f1": lf, "score": scores, "min": min(scores), "colour_diff": cd, "drawn_without": degrades(r, sh), "ok": min(scores) >= min_iou and max(cd) <= max_colour,
                               "ink_ratio": [round(float(b.sum() / max(1, a.sum())), 3) for a, b in zip(ref, sil)]}
    res["ok"] = all(v.get("ok") for v in res["renderers"].values())
    (out / "parity.json").write_text(json.dumps(res, indent=1))
    return res


BENCH = [("pip-park", "s1"), ("pip-park", "s2"), ("pip-park", "s3"), ("direct-demo", "s1"), ("dialogue-demo", "s1"), ("clips-demo", "s1"),
         ("nib-hello", "s1"), ("level-demo", "s1"), ("fx-demo", "s1"), ("props-demo", "s1"), ("night-planes", "s1")]


def bench(shots=None):
    """renderer parity on the benchmark shots: every renderer that accepts a shot must match the SVG renderer"""
    rows = []
    for film, shot in shots or BENCH:
        try:
            r = run(film, shot)
            rows.append({"film": film, "shot": shot, "ok": r["ok"], "refusals": r["refusals"],
                         "scores": {k: {"min": v.get("min"), "colour": max(v.get("colour_diff") or [0]), "without": v.get("drawn_without"), "error": v.get("error")} for k, v in r["renderers"].items()}})
        except Exception as e:
            rows.append({"film": film, "shot": shot, "ok": False, "error": str(e)[-300:]})
    out = {"ok": all(x["ok"] for x in rows), "shots": rows}
    (ROOT / "out" / "rparity").mkdir(parents=True, exist_ok=True)
    (ROOT / "out" / "rparity" / "bench.json").write_text(json.dumps(out, indent=1))
    return out


def self_test(tmp):
    """three benchmark shots (vector, raster line art, drawn levels) match across renderers; shots that need what a
    renderer cannot draw are refused with the reason"""
    fails, got = [], {}
    from . import commands as C
    r = bench([("pip-park", "s1"), ("nib-hello", "s1"), ("level-demo", "s1")])
    got["bench"] = [{"shot": f"{x['film']}/{x['shot']}", "ok": x["ok"], "scores": {k: v["min"] for k, v in x.get("scores", {}).items()}} for x in r["shots"]]
    bad = [x for x in r["shots"] if not x["ok"]]
    if bad:
        fails.append(f"renderer parity: {bad}")
    for film, want in (("night-planes", "compositor planes"), ("fx-demo", "props")):
        sh = C._shots(film)["shots"][0]
        why = refusal("synfig", sh, [json.loads((ROOT / c["puppet"]).read_text()) for c in sh.get("cast", [])])
        got.setdefault("refusals", {})[film] = why
        if not why or want not in why:
            fails.append(f"{film} should be refused by synfig for {want}: {why}")
    return fails, got
