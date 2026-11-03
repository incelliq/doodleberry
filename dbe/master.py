"""Film-grade masters (WP-37): a film rendered at 4K (or any multiple of its size) and any frame rate as a multi-pass
OpenEXR sequence in ACEScg, colour-managed with OpenColorIO's built-in ACES studio config, with a slate frame and a
cinema-style package; the social encodes are derived from the master, not from a second render.

Passes (one layer each in every EXR): beauty (RGBA), line (the visible ink, RGBA, un-composited from white), fill (the
flat colour without ink, RGBA) and matte (the characters' coverage, A). Pixels are half floats, premultiplied, in
ACEScg (AP1 primaries, D60 white), ZIP-compressed (lossless; about 16 MB a 4K frame).

Colour: our pictures are display-referred sRGB graphics, so the master stores them through the inverse sRGB texture
transform ("sRGB Encoded Rec.709 (sRGB)" -> ACEScg), and the social encode goes back the same way, so the colours the
artist picked survive the round trip; the ACES output transform (a display view) is offered for review only.
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from . import ROOT

CONFIG = "ocio://studio-config-v5.0.0_aces-v2.1_ocio-v2.6"   # ACES 2.1, the latest built-in OCIO config
SRC_SPACE = "sRGB Encoded Rec.709 (sRGB)"
WORK = "ACEScg"
AP1 = (0.713, 0.293, 0.165, 0.830, 0.128, 0.044, 0.32168, 0.33767)   # ACEScg primaries and D60 white
_P = {}


def processor(src, dst):
    import PyOpenColorIO as O
    key = (src, dst)
    if key not in _P:
        cfg = O.Config.CreateFromFile(CONFIG)
        _P[key] = cfg.getProcessor(src, dst).getDefaultCPUProcessor()
    return _P[key]


def to_space(rgb, src, dst):
    """float32 HxWx3 -> float32 HxWx3 through OCIO"""
    out = np.ascontiguousarray(rgb, dtype=np.float32).copy()
    processor(src, dst).applyRGB(out)
    return out


def _png(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255
    return a


def layers_for(frame_dir, f):
    """the passes of frame f (PNG, sRGB) -> {layer: (channel names, float32 arrays)} in ACEScg, premultiplied"""
    out = {}
    name = f"f_{f:05d}.png"
    for p in ("beauty", "line", "fill", "matte"):
        fp = Path(frame_dir) / p / name
        if not fp.exists():
            continue
        a = _png(fp)
        if p == "line":   # ink on white -> ink with coverage: alpha = 1 - min channel, colour un-composited from white
            al = np.clip(1 - a[..., :3].min(axis=2), 0, 1)
            rgb = np.where(al[..., None] > 1e-3, (a[..., :3] - (1 - al[..., None])) / np.maximum(al[..., None], 1e-3), 0)
            a = np.dstack([np.clip(rgb, 0, 1), al])
        if p == "matte":
            out["matte"] = {"A": a[..., 3]}
            continue
        lin = to_space(a[..., :3], SRC_SPACE, WORK) * a[..., 3:4]   # premultiplied, as EXR expects
        out[p] = {"R": lin[..., 0], "G": lin[..., 1], "B": lin[..., 2], "A": a[..., 3]}
    return out


def write_exr(path, layers, meta):
    import OpenEXR
    chans = {}
    for lay, ch in layers.items():
        for c, arr in ch.items():
            chans[f"{lay}.{c}"] = np.ascontiguousarray(arr, dtype=np.float16)
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage,
              "chromaticities": AP1, **{k: str(v) for k, v in meta.items()}}
    with OpenEXR.File(header, chans) as fo:
        fo.write(str(path))


def read_exr(path, layer="beauty"):
    """an EXR layer back as float32 HxWx4 (premultiplied ACEScg)"""
    import OpenEXR
    with OpenEXR.File(str(path), separate_channels=True) as fi:
        ch = fi.channels()
        get = lambda c: ch[f"{layer}.{c}"].pixels.astype(np.float32) if f"{layer}.{c}" in ch else None
        a = get("A")
        rgb = [get(c) for c in "RGB"]
        if rgb[0] is None:
            return np.dstack([a, a, a, a])
        return np.dstack(rgb + [a if a is not None else np.ones_like(rgb[0])])


def display(acescg_rgba, view="texture"):
    """master pixels -> sRGB 8-bit for an encode: the inverse of how they went in ("texture"), or the ACES output
    transform for review ("aces")"""
    a = acescg_rgba
    al = np.clip(a[..., 3:4], 0, 1)
    rgb = np.where(al > 1e-4, a[..., :3] / np.maximum(al, 1e-4), 0)
    if view == "aces":
        import PyOpenColorIO as O
        cfg = O.Config.CreateFromFile(CONFIG)
        t = O.DisplayViewTransform(src=WORK, display="sRGB - Display", view=cfg.getDefaultView("sRGB - Display"))
        p = cfg.getProcessor(t).getDefaultCPUProcessor(); out = np.ascontiguousarray(rgb, np.float32).copy(); p.applyRGB(out)
    else:
        out = to_space(rgb, WORK, SRC_SPACE)
    out = out * al + (1 - al)   # over white where there is no coverage
    return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)


def slate(path, info, size):
    """a slate frame: what the master is"""
    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    im = Image.new("RGB", (W, H), (24, 26, 30)); d = ImageDraw.Draw(im)
    font = lambda s: ImageFont.truetype(str(ROOT / "engine" / "fonts" / "Fredoka.ttf"), s)
    d.text((W * 0.08, H * 0.12), info["title"], fill=(246, 201, 69), font=font(int(W * 0.07)))
    y = H * 0.24
    for k in ("film", "resolution", "fps", "frames", "duration", "colour", "passes", "ocio", "version"):
        d.text((W * 0.08, y), f"{k}", fill=(150, 160, 170), font=font(int(W * 0.03)))
        d.text((W * 0.36, y), str(info.get(k, "")), fill=(240, 240, 240), font=font(int(W * 0.03)))
        y += H * 0.045
    for i, c in enumerate([(255, 255, 255), (232, 96, 60), (95, 184, 90), (60, 142, 232), (246, 201, 69), (24, 30, 38)]):   # colour chips
        d.rectangle([W * (0.08 + i * 0.14), H * 0.72, W * (0.2 + i * 0.14), H * 0.8], fill=c)
    im.save(path)
    return path


def scopes(rgb8):
    """histogram, luma waveform and vectorscope of an 8-bit sRGB picture, as one PNG-ready array"""
    from PIL import Image
    a = rgb8[..., :3].astype(np.float32)
    h, w = a.shape[:2]
    Y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    # histogram (R, G, B, luma) 256 x 200
    hist = np.zeros((200, 256, 3), np.uint8)
    for i, ch in enumerate([a[..., 0], a[..., 1], a[..., 2]]):
        c = np.bincount(ch.astype(int).ravel(), minlength=256)[:256]
        c = (c / max(1, c.max()) * 199).astype(int)
        for x in range(256):
            hist[199 - c[x]:, x, i] = 200
    # waveform: luma per column, 256 levels high
    cols = np.linspace(0, w - 1, 256).astype(int)
    wf = np.zeros((256, 256), np.float32)
    for j, x in enumerate(cols):
        np.add.at(wf, (255 - Y[:, x].astype(int), j), 1)
    wf = (np.clip(wf / max(1, np.percentile(wf[wf > 0], 99) if (wf > 0).any() else 1), 0, 1) * 255).astype(np.uint8)
    # vectorscope: Cb/Cr scatter
    cb = (-0.1146 * a[..., 0] - 0.3854 * a[..., 1] + 0.5 * a[..., 2]); cr = (0.5 * a[..., 0] - 0.4542 * a[..., 1] - 0.0458 * a[..., 2])
    vs = np.zeros((256, 256), np.float32)
    np.add.at(vs, (np.clip(127 - cr, 0, 255).astype(int).ravel(), np.clip(127 + cb, 0, 255).astype(int).ravel()), 1)
    vs = (np.clip(np.log1p(vs) / max(1e-6, np.log1p(vs).max()), 0, 1) * 255).astype(np.uint8)
    out = np.zeros((256, 256 * 3 + 20, 3), np.uint8)
    out[28:228, :256] = hist
    out[:, 266:522] = np.dstack([wf] * 3) * np.array([0.4, 1, 0.5])
    out[:, 532:788] = np.dstack([vs] * 3) * np.array([1, 0.85, 0.3])
    return out


def checksums(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*")) if p.is_file() and p.name != "MANIFEST.json"}
