"""ML assists, in-house (WP-43): models used as assistants whose output is data a person accepts. Each model is
pinned by hash and carries its licence class; every output it shapes is recorded (a level's meta.assists, a film's
provenance.json "models"), so the posting gate (film.provenance) flags non-commercial or research-only inputs.

Assists here (CPU, onnxruntime):
- in-betweens for drawn levels: RIFE 4.9 proposes the drawing halfway between two drawings (level.inbetween); the
  animator accepts or drops each proposal (level.accept).
- depth for parallax: Depth Anything V2 estimates relative depth of a picture and splits it into depth planes for the
  compositor (depth.planes). Small is Apache-2.0; Base is CC BY-NC 4.0 (flagged at posting).

Each is measured against a baseline on our own material (assist.bench): in-betweens against holding the drawing and
against a cross-dissolve, on held-out true drawings; depth against "lower in the frame is nearer", on Blender
renders of our Geometry Nodes sets with their true depth.
"""
import hashlib
import json
import math
import os
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

from . import ROOT

MODELS = Path(os.environ.get("DBE_MODELS", str(Path.home() / ".cache" / "doodleberry" / "models")))
REGISTRY = {
    "rife49": {"file": "rife49.onnx", "url": "https://huggingface.co/yuvraj108c/rife-onnx/resolve/main/rife49_ensemble_True_scale_1_sim.onnx",
               "sha256": "76e4cef9ab42fa7dd4e8f6e4aba47462051e3faa969e4bca6479784fbab0ac6f", "license": "MIT", "class": "permissive",
               "source": "RIFE 4.9 (hzwer/Practical-RIFE, MIT), ONNX by yuvraj108c/rife-onnx (no card of its own)", "task": "in-betweens"},
    "depth_small": {"file": "depth_anything_v2_small.onnx", "url": "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx",
                    "sha256": "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c", "license": "Apache-2.0", "class": "permissive",
                    "source": "Depth Anything V2 Small (onnx-community/depth-anything-v2-small)", "task": "depth"},
    "depth_base": {"file": "depth_anything_v2_base.onnx", "url": "https://huggingface.co/onnx-community/depth-anything-v2-base/resolve/main/onnx/model.onnx",
                   "sha256": None, "license": "CC-BY-NC-4.0", "class": "non-commercial",
                   "source": "Depth Anything V2 Base (onnx-community/depth-anything-v2-base)", "task": "depth"},
    # WP-18: click-to-mask cut suggestions. Two graphs, each with its weights in an external .onnx_data file.
    "sam21_tiny": {"file": "sam21_tiny/vision_encoder.onnx", "license": "Apache-2.0", "class": "permissive",
                   "source": "SAM 2.1 Hiera tiny (Meta, facebookresearch/sam2, Apache-2.0), ONNX by onnx-community/sam2.1-hiera-tiny-ONNX", "task": "segmentation",
                   "files": {f: (f"https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/814a066640debee5a91e70aa401fb8e17e030503/onnx/{f.split('/')[1]}", h) for f, h in (
                       ("sam21_tiny/vision_encoder.onnx", "4f30aacd3aaefbca81a0b7fe4c1fc96345570ea0a6f80ced599493d1b3be2e8c"),
                       ("sam21_tiny/vision_encoder.onnx_data", "e83df9866a5afe68ea7f0f721f18f65137fc3acbf0da1c74e946d363e09c69cc"),
                       ("sam21_tiny/prompt_encoder_mask_decoder.onnx", "874414704c5d686db7d206a35f6e15d26563d50c8c4468fccc6739bd7e491dcf"),
                       ("sam21_tiny/prompt_encoder_mask_decoder.onnx_data", "e9874d900dd4134ed60eab1e97910327c2419e0b2954485d8fd6e7f1a1470f47"))}},
}
_SESS = {}


def model_path(name):
    """the model file, downloaded on first use and checked against its pinned hash"""
    m = REGISTRY[name]
    if m.get("files"):   # several files (graphs with external weights): each downloaded and checked
        for f, (url, sha) in m["files"].items():
            q = MODELS / f
            if not q.exists():
                q.parent.mkdir(parents=True, exist_ok=True); tmp = q.with_suffix(q.suffix + ".part")
                urllib.request.urlretrieve(url, tmp); tmp.rename(q)
            h = hashlib.sha256(q.read_bytes()).hexdigest()
            if h != sha:
                raise RuntimeError(f"{f}: sha256 {h[:16]} is not the pinned {sha[:16]}")
        return MODELS / m["file"]
    p = MODELS / m["file"]
    if not p.exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(m["url"], tmp)
        tmp.rename(p)
    if m.get("sha256"):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != m["sha256"]:
            raise RuntimeError(f"{m['file']}: sha256 {h[:16]} is not the pinned {m['sha256'][:16]}")
    return p


def session(name, file=None):
    """an onnxruntime session for a model (file: another graph of a several-file model)"""
    key = (name, file)
    if key not in _SESS:
        import onnxruntime as ort
        so = ort.SessionOptions(); so.intra_op_num_threads = max(1, (os.cpu_count() or 2))
        p = model_path(name)
        _SESS[key] = ort.InferenceSession(str(MODELS / file if file else p), so, providers=["CPUExecutionProvider"])
    return _SESS[key]


def record(target, model, output):
    """write that `model` shaped `output` into a film's provenance.json (target: film dir) or a puppet's meta (target:
    puppet dict); returns the record"""
    m = REGISTRY[model]
    rec = {"name": model, "license": m["license"], "class": m["class"], "source": m["source"], "task": m["task"], "output": output}
    if isinstance(target, dict):
        lst = target.setdefault("meta", {}).setdefault("assists", [])
    else:
        f = Path(target) / "provenance.json"
        doc = json.loads(f.read_text()) if f.exists() else {}
        lst = doc.setdefault("models", [])
    if not any(r.get("name") == model and r.get("output") == output for r in lst):
        lst.append(rec)
    if not isinstance(target, dict):
        f.write_text(json.dumps(doc, indent=1))
    return rec


# ---------------- in-betweens (RIFE) ----------------
def _pad(x, m=64):
    h, w = x.shape[-2:]
    ph, pw = (m - h % m) % m, (m - w % m) % m
    return np.pad(x, ((0, 0), (0, 0), (0, ph), (0, pw)), mode="edge"), (h, w)


def _rife(a, b, t):
    """a, b: float32 HxWx3 in 0..1 -> HxWx3"""
    s = session("rife49")
    A, (h, w) = _pad(a.transpose(2, 0, 1)[None].astype(np.float32))
    B, _ = _pad(b.transpose(2, 0, 1)[None].astype(np.float32))
    out = s.run(None, {"img0": A, "img1": B, "timestep": np.array([t], dtype=np.float32)})[0]
    return np.clip(out[0, :3, :h, :w].transpose(1, 2, 0), 0, 1)


def inbetween(a_rgba, b_rgba, t=0.5, method="rife"):
    """the drawing at t between two RGBA drawings (uint8 arrays of one size): "rife" (colour over white and coverage
    interpolated separately, then un-composited), "dissolve" or "hold" (baselines)"""
    a = a_rgba.astype(np.float32) / 255; b = b_rgba.astype(np.float32) / 255
    if method == "hold":
        return a_rgba.copy()
    if method == "dissolve":
        return np.clip((a * (1 - t) + b * t) * 255 + 0.5, 0, 255).astype(np.uint8)
    over = lambda x: x[..., :3] * x[..., 3:4] + (1 - x[..., 3:4])   # on white
    col = _rife(over(a), over(b), t)
    al = _rife(np.repeat(a[..., 3:4], 3, 2), np.repeat(b[..., 3:4], 3, 2), t).mean(axis=2, keepdims=True)
    al = np.where(al < 0.04, 0, al)
    rgb = np.where(al > 0.04, (col - (1 - al)) / np.maximum(al, 1e-3), 0)
    return np.clip(np.concatenate([rgb, al], axis=2) * 255 + 0.5, 0, 255).astype(np.uint8)


def _ink(rgba):
    """ink mask: covered and dark"""
    x = rgba.astype(np.float32)
    lum = 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]
    return (x[..., 3] > 128) & (lum < 90)


def line_f1(pred, truth, tol=2):
    """precision and recall of ink pixels within tol px of the other's ink"""
    from scipy import ndimage
    p, t = _ink(pred), _ink(truth)
    if not t.any() and not p.any():
        return 1.0
    dt_t = ndimage.distance_transform_edt(~t) if t.any() else np.full(t.shape, 1e9)
    dt_p = ndimage.distance_transform_edt(~p) if p.any() else np.full(p.shape, 1e9)
    prec = (dt_t[p] <= tol).mean() if p.any() else 0.0
    rec = (dt_p[t] <= tol).mean() if t.any() else 0.0
    return 0.0 if prec + rec == 0 else float(2 * prec * rec / (prec + rec))


def colour_error(pred, truth):
    """mean absolute difference of the drawings over white, 0..255"""
    over = lambda x: x[..., :3].astype(np.float32) * (x[..., 3:4] / 255) + 255 * (1 - x[..., 3:4] / 255)
    return float(np.abs(over(pred) - over(truth)).mean())


def bench_inbetween(accept_f1=0.8):
    """on the drawn-level demo's own drawings: each in-between of a 12-drawing cycle against the true drawing of the
    24-drawing cycle (the same code at twice the drawings), for hold, dissolve and RIFE. An in-between is accepted when
    its line art matches the truth (line F1 >= accept_f1 at 2 px)"""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import make_level_demo as LD
    out = {}
    for name, fn in (("campfire", LD.fire), ("walk", LD.walk)):
        rows = {m: [] for m in ("hold", "dissolve", "rife")}
        for k in range(12):
            A, T, B = (np.asarray(fn(i, 24)) for i in (2 * k, 2 * k + 1, (2 * k + 2) % 24))
            for m in rows:
                P = inbetween(A, B, 0.5, m)
                rows[m].append((line_f1(P, T), colour_error(P, T)))
        out[name] = {m: {"line_f1": round(float(np.mean([r[0] for r in v])), 3), "colour_error": round(float(np.mean([r[1] for r in v])), 2),
                         "accepted": round(float(np.mean([r[0] >= accept_f1 for r in v])), 3)} for m, v in rows.items()}
    allm = {m: round(float(np.mean([out[n][m]["accepted"] for n in out])), 3) for m in ("hold", "dissolve", "rife")}
    return {"levels": out, "acceptance": allm, "rule": f"line F1 >= {accept_f1} at 2 px against the true drawing"}


# ---------------- depth (Depth Anything V2) ----------------
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)


def depth(rgb, model="depth_small", size=518):
    """relative inverse depth (larger = nearer), same size as the picture, normalised to 0..1"""
    from PIL import Image
    h, w = rgb.shape[:2]
    k = size / max(h, w)
    nh, nw = max(14, int(round(h * k / 14)) * 14), max(14, int(round(w * k / 14)) * 14)
    x = np.asarray(Image.fromarray(rgb[..., :3]).resize((nw, nh), Image.BICUBIC)).astype(np.float32) / 255
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    d = session(model).run(None, {"pixel_values": x})[0][0]
    d = np.asarray(Image.fromarray(d.astype(np.float32)).resize((w, h), Image.BILINEAR))
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / max(1e-6, hi - lo), 0, 1)


def planes(rgb, n=3, model="depth_small"):
    """split a picture into n depth planes, far to near: [(rgba layer, relative depth for the compositor)]"""
    d = depth(rgb, model)
    cuts = np.quantile(d, np.linspace(0, 1, n + 1))
    out = []
    for i in range(n):
        m = (d >= cuts[i]) & ((d < cuts[i + 1]) if i < n - 1 else (d <= cuts[i + 1]))
        layer = np.dstack([rgb[..., :3], (m * 255).astype(np.uint8)])
        mid = float(d[m].mean()) if m.any() else 0.5
        out.append((layer, round(1 + 4 * (1 - mid), 2)))   # disparity 1 -> depth 1 (stage), disparity 0 -> depth 5
    return out


def ordinal_accuracy(pred_near, true_dist, pairs=20000, seed=3, min_ratio=1.15, mask=None):
    """how often a prediction (larger = nearer) orders random pixel pairs like the true distance does; pairs whose
    distances differ by less than min_ratio are skipped (too close to call)"""
    rng = np.random.default_rng(seed)
    h, w = true_dist.shape
    idx = np.flatnonzero(mask.ravel()) if mask is not None else np.arange(h * w)
    a, b = rng.choice(idx, pairs), rng.choice(idx, pairs)
    za, zb = true_dist.ravel()[a], true_dist.ravel()[b]
    keep = np.maximum(za, zb) / np.maximum(np.minimum(za, zb), 1e-6) >= min_ratio
    pa, pb = pred_near.ravel()[a][keep], pred_near.ravel()[b][keep]
    truth_a_nearer = za[keep] < zb[keep]
    return float(((pa > pb) == truth_a_nearer).mean()), int(keep.sum())


def gn_truth(tmp, seeds=(11, 23, 37), cams=([540, 960, 1.0], [700, 900, 1.25], [380, 1020, 0.9])):
    """Geometry Nodes city frames with their true depth (Blender Z pass): [(rgb uint8, distance float32)]"""
    from PIL import Image
    from .commands import BLENDER
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    out = []
    for i, (seed, cam) in enumerate(zip(seeds, cams)):
        d = tmp / f"c{i}"; d.mkdir(exist_ok=True)
        exr, rgbp, zp = d / "f_0000.exr", d / "rgb.png", d / "z.tif"
        if not (zp.exists() and rgbp.exists() and np.asarray(Image.open(rgbp)).max() > 0):
            req = {"size": [540, 960], "fps": 30, "start": 0, "frames": [0], "camera": [[0, cam]], "floor": 1500, "seed": seed, "zpass": True,
                   "blocks": {"depth": [20 + 4 * i, 150]}}
            (d / "r.json").write_text(json.dumps(req))
            subprocess.run([BLENDER, "-b", "--factory-startup", "--gpu-backend", "vulkan", "--python", str(ROOT / "dbe" / "blender_gn.py"), "--", str(d / "r.json"), str(d)],
                           capture_output=True, text=True, timeout=900, cwd=str(ROOT))
            subprocess.run(["oiiotool", str(exr), "--subimage", "0", "--ch", "ViewLayer.Combined.R,ViewLayer.Combined.G,ViewLayer.Combined.B", "--colorconvert", "linear", "sRGB", "-d", "uint8", "-o", str(rgbp)], capture_output=True, text=True, timeout=120)
            subprocess.run(["oiiotool", str(exr), "--subimage", "1", "-d", "float", "-o", str(zp)], capture_output=True, text=True, timeout=120)
        rgb = np.asarray(Image.open(rgbp).convert("RGB"))
        z = np.asarray(Image.open(zp)).astype(np.float32)
        out.append((rgb, z))
    return out


def bench_depth(tmp, model="depth_small"):
    """on our Geometry Nodes city renders: ordinal depth accuracy of the model against "lower in the frame is nearer",
    on pixels that are not sky"""
    rows = []
    for rgb, z in gn_truth(tmp):
        h, w = z.shape
        solid = z < 1e4                              # the sky has no surface
        prior = np.repeat(np.linspace(0, 1, h)[:, None], w, axis=1)   # lower = nearer
        da = depth(rgb, model)
        acc_m, n = ordinal_accuracy(da, z, mask=solid)
        acc_p, _ = ordinal_accuracy(prior, z, mask=solid)
        rows.append({"pairs": n, "model": round(acc_m, 3), "y_prior": round(acc_p, 3)})
    return {"frames": rows, "model": round(float(np.mean([r["model"] for r in rows])), 3),
            "y_prior": round(float(np.mean([r["y_prior"] for r in rows])), 3), "which": model}


# ---------------- click-to-mask (SAM 2.1 tiny; WP-18) ----------------
_EMB = {}


def sam_embed(image_path, cache=None):
    """SAM 2.1's image embeddings for a picture (about 4 s on 4 CPUs), kept in memory and in `cache` (.npz) if given"""
    from PIL import Image
    key = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    if key in _EMB:
        return _EMB[key]
    if cache and Path(cache).exists():
        z = np.load(cache)
        if str(z["key"]) == key:
            _EMB[key] = ([z["e0"], z["e1"], z["e2"]], tuple(int(v) for v in z["size"])); return _EMB[key]
    im = Image.open(image_path).convert("RGB"); W, H = im.size
    x = np.asarray(im.resize((1024, 1024), Image.BILINEAR)).astype(np.float32) / 255
    x = ((x - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])).transpose(2, 0, 1)[None].astype(np.float32)
    e = session("sam21_tiny").run(None, {"pixel_values": x})
    if cache:
        np.savez(cache, key=key, e0=e[0], e1=e[1], e2=e[2], size=np.array([W, H]))
    _EMB[key] = (e, (W, H))
    return _EMB[key]


def sam_mask(image_path, points, cache=None):
    """points: [[x, y, 1 (inside) or 0 (outside)], ...] in image pixels -> (boolean mask, predicted IoU)"""
    from PIL import Image
    e, (W, H) = sam_embed(image_path, cache)
    pts = np.array([[[[p[0] * 1024 / W, p[1] * 1024 / H] for p in points]]], np.float32)
    lab = np.array([[[int(p[2]) if len(p) > 2 else 1 for p in points]]], np.int64)
    r = session("sam21_tiny", "sam21_tiny/prompt_encoder_mask_decoder.onnx").run(None, {
        "input_points": pts, "input_labels": lab, "input_boxes": np.zeros((1, 0, 4), np.float32),
        "image_embeddings.0": e[0], "image_embeddings.1": e[1], "image_embeddings.2": e[2]})
    iou, masks = r[0][0, 0], r[1][0, 0]; k = int(iou.argmax())
    m = np.asarray(Image.fromarray(masks[k].astype(np.float32)).resize((W, H), Image.BILINEAR)) > 0
    return m, float(iou[k])
