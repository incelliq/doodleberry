"""Sticker packs (WP-23): one character's moves exported for each messaging platform, inside that platform's limits.

A move is rendered once as transparent square frames (tools/sticker_frames.mjs, framed to the whole move and eased in
from and back out to rest, so it loops without a jump) and baked for Lottie. Each platform's file is then encoded
from those frames and **fitted**: quality, then frame rate, come down until the file is inside the limit, and the
result is checked against every limit (dimensions, length, frame rate, file size, transparency, codec):

| platform        | file                         | limits (sources in docs/dbe.md)                                        |
|-----------------|------------------------------|------------------------------------------------------------------------|
| Telegram video  | WebM, VP9 with alpha         | one side 512 px, the other at most 512; at most 3 s and 30 fps; 256 KB; no sound |
| Telegram TGS    | gzipped Lottie ("tgs": 1)    | 512 x 512, at most 3 s, 30 or 60 fps, 64 KB; vector only (no images)  |
| WhatsApp        | animated WebP                | 512 x 512, at most 10 s, 500 KB; a 96 x 96 PNG tray icon, 50 KB; 3 to 30 stickers a pack |
| Giphy           | GIF with transparency        | at least 2 frames; at least 20% of the first frame transparent          |
| iMessage        | APNG                         | 300, 408 or 618 px square (408 here), 500 KB                            |
"""
import gzip
import io
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

LIMITS = {
    "telegram": {"side": 512, "max_s": 3.0, "max_fps": 30, "max_kb": 256},
    "tgs": {"side": 512, "max_s": 3.0, "fps": (30, 60), "max_kb": 64},
    "whatsapp": {"side": 512, "max_s": 10.0, "max_kb": 500, "tray": 96, "tray_kb": 50, "pack": (3, 30)},
    "giphy": {"min_frames": 2, "min_transparent": 0.20},
    "imessage": {"side": 408, "max_kb": 500},
}


def frames_of(d):
    return sorted(Path(d).glob("f*.png"))


def _ff(args):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])


def _probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames,pix_fmt:stream_tags=alpha_mode:format=duration",
                        "-of", "json", str(f)], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def _fit(make, tries):
    """make(**try) -> path; the first try inside the limit wins (the last is kept either way)"""
    last = None
    for t in tries:
        p, ok = make(**t)
        last = (p, t)
        if ok:
            return p, t, True
    return last[0], last[1], False


def telegram(frames_dir, out, fps, size=512):
    """WebM VP9 with alpha, 512 px, under 256 KB (lower bitrate, then 24 or 15 fps)"""
    L = LIMITS["telegram"]; fr = frames_of(frames_dir)

    def make(rate, crf, bv):
        step = max(1, round(fps / rate))
        sel = f"select='not(mod(n\\,{step}))',setpts=N/{rate}/TB," if step > 1 else ""
        _ff(["-framerate", str(fps), "-i", str(Path(frames_dir) / "f%04d.png"), "-vf", f"{sel}scale={size}:{size}:flags=lanczos,format=yuva420p", "-r", str(rate),
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", str(crf), "-b:v", bv, "-an", "-auto-alt-ref", "0", str(out)])
        return out, Path(out).stat().st_size <= L["max_kb"] * 1024
    tries = [dict(rate=min(30, fps), crf=c, bv=b) for c, b in ((30, "0"), (36, "0"), (42, "0"), (48, "200k"))] + [dict(rate=24, crf=48, bv="150k"), dict(rate=15, crf=50, bv="120k")]
    return _fit(make, tries)


def check_telegram(f, frames_n, fps):
    L = LIMITS["telegram"]; pr = _probe(f); st = pr["streams"][0]; num, den = map(int, st["avg_frame_rate"].split("/"))
    dur = float(pr["format"].get("duration") or 0)
    rate = num / den if den else 0
    has_alpha = (st.get("tags") or {}).get("alpha_mode") == "1" or "a" in (st.get("pix_fmt") or "")
    checks = {"codec vp9": st["codec_name"] == "vp9", "one side 512, other at most 512": max(st["width"], st["height"]) == 512 and min(st["width"], st["height"]) <= 512,
              "at most 3 s": dur <= L["max_s"] + 1e-3, "at most 30 fps": rate <= L["max_fps"] + 1e-3, "at most 256 KB": Path(f).stat().st_size <= L["max_kb"] * 1024,
              "no sound": len(pr["streams"]) == 1, "alpha": has_alpha}
    return checks, {"bytes": Path(f).stat().st_size, "seconds": round(dur, 3), "fps": round(rate, 2), "size": [st["width"], st["height"]]}


def tgs(lottie_json, out):
    """Telegram's animated sticker: gzipped Lottie, 512 x 512, marked "tgs": 1, no image assets"""
    L = LIMITS["tgs"]; j = json.loads(Path(lottie_json).read_text()) if not isinstance(lottie_json, dict) else lottie_json
    j = {**j, "tgs": 1}
    raw = json.dumps(j, separators=(",", ":")).encode()
    Path(out).write_bytes(gzip.compress(raw, 9))
    return out


def _has_expression(o):
    """an animated property with an expression carries it as a string under "x" (easing tangents are lists, not strings)"""
    if isinstance(o, dict):
        return isinstance(o.get("x"), str) or any(_has_expression(v) for v in o.values())
    if isinstance(o, list):
        return any(_has_expression(v) for v in o)
    return False


def check_tgs(f):
    L = LIMITS["tgs"]; j = json.loads(gzip.decompress(Path(f).read_bytes()))
    dur = (j["op"] - j["ip"]) / j["fr"]
    checks = {"512 x 512": j["w"] == 512 and j["h"] == 512, "at most 3 s": dur <= L["max_s"] + 1e-3, "30 or 60 fps": j["fr"] in L["fps"],
              "at most 64 KB": Path(f).stat().st_size <= L["max_kb"] * 1024, "no images": not any("p" in a and "u" in a for a in j.get("assets", [])), "marked tgs": j.get("tgs") == 1,
              "no expressions": not _has_expression(j)}
    return checks, {"bytes": Path(f).stat().st_size, "seconds": round(dur, 3), "fps": j["fr"], "layers": len(j.get("layers", []))}


def whatsapp(frames_dir, out, fps, size=512):
    L = LIMITS["whatsapp"]

    def make(rate, q):
        step = max(1, round(fps / rate)); ims = [Image.open(f).convert("RGBA").resize((size, size), Image.LANCZOS) for f in frames_of(frames_dir)[::step]]
        ims[0].save(out, "WEBP", save_all=True, append_images=ims[1:], duration=round(1000 / rate), loop=0, quality=q, method=4, lossless=False)   # method 6: 100x slower for 4% smaller
        return out, Path(out).stat().st_size <= L["max_kb"] * 1024
    return _fit(make, [dict(rate=min(30, fps), q=q) for q in (80, 65, 50)] + [dict(rate=15, q=q) for q in (60, 45)] + [dict(rate=10, q=40)])


def whatsapp_tray(first_png, out):
    im = Image.open(first_png).convert("RGBA"); bb = im.getbbox() or (0, 0, im.width, im.height)
    t = Image.new("RGBA", (96, 96), (0, 0, 0, 0)); c = im.crop(bb); c.thumbnail((96, 96), Image.LANCZOS)
    t.alpha_composite(c, ((96 - c.width) // 2, (96 - c.height) // 2)); t.save(out, optimize=True)
    return out


def _webp_info(f):
    """size, frames and seconds of an animated WebP, from its ANMF chunks (each frame's duration, 24-bit, ms)"""
    b = Path(f).read_bytes(); i, n, dur = 12, 0, 0
    while i + 8 <= len(b):
        tag, ln = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], "little")
        if tag == b"ANMF":
            n += 1; dur += int.from_bytes(b[i + 8 + 12:i + 8 + 15], "little")
        i += 8 + ln + (ln & 1)
    return Image.open(f).size, n, dur / 1000


def check_whatsapp(f, tray):
    L = LIMITS["whatsapp"]; size, n, dur = _webp_info(f); tim = Image.open(tray)
    checks = {"512 x 512": size == (512, 512), "animated": n > 1, "at most 10 s": dur <= L["max_s"] + 1e-3, "at most 500 KB": Path(f).stat().st_size <= L["max_kb"] * 1024,
              "tray 96 x 96 PNG": tim.size == (96, 96) and tim.format == "PNG", "tray at most 50 KB": Path(tray).stat().st_size <= L["tray_kb"] * 1024}
    return checks, {"bytes": Path(f).stat().st_size, "seconds": round(dur, 3), "frames": n}


def giphy(frames_dir, out, fps, size=512):
    """GIF with real transparency: one palette for the move with a slot kept for transparent, 15 fps"""
    rate = min(15, fps); step = max(1, round(fps / rate))
    _ff(["-framerate", str(fps), "-i", str(Path(frames_dir) / "f%04d.png"), "-filter_complex",
         f"[0:v]select='not(mod(n\\,{step}))',setpts=N/{rate}/TB,scale={size}:{size}:flags=lanczos,split[a][b];[a]palettegen=reserve_transparent=1:stats_mode=full[p];[b][p]paletteuse=alpha_threshold=128:dither=bayer:bayer_scale=3",
         "-r", str(rate), "-loop", "0", str(out)])
    return out


def check_giphy(f):
    L = LIMITS["giphy"]; im = Image.open(f); n = getattr(im, "n_frames", 1); im.seek(0)
    a = np.asarray(im.convert("RGBA"))[..., 3]
    share = float((a == 0).mean())
    checks = {"GIF": im.format == "GIF", "at least 2 frames": n >= L["min_frames"], "first frame at least 20% transparent": share >= L["min_transparent"]}
    return checks, {"bytes": Path(f).stat().st_size, "frames": n, "transparent_first_frame": round(share, 3)}


def imessage(frames_dir, out, fps):
    L = LIMITS["imessage"]; side = L["side"]

    def make(rate, colours):
        step = max(1, round(fps / rate)); ims = []
        for f in frames_of(frames_dir)[::step]:
            im = Image.open(f).convert("RGBA").resize((side, side), Image.LANCZOS)
            ims.append(im.quantize(colours, method=Image.Quantize.FASTOCTREE).convert("RGBA") if colours else im)
        ims[0].save(out, "PNG", save_all=True, append_images=ims[1:], duration=round(1000 / rate), loop=0, optimize=True, disposal=1, blend=0)
        return out, Path(out).stat().st_size <= L["max_kb"] * 1024
    return _fit(make, [dict(rate=15, colours=None), dict(rate=15, colours=128), dict(rate=12, colours=64), dict(rate=10, colours=48), dict(rate=8, colours=32)])


def check_imessage(f):
    L = LIMITS["imessage"]; im = Image.open(f); n = getattr(im, "n_frames", 1)
    checks = {"APNG": im.format == "PNG" and n > 1, "square 300, 408 or 618 px": im.size[0] == im.size[1] and im.size[0] in (300, 408, 618),
              "at most 500 KB": Path(f).stat().st_size <= L["max_kb"] * 1024, "transparent": "A" in im.mode or im.info.get("transparency") is not None or im.mode == "RGBA"}
    return checks, {"bytes": Path(f).stat().st_size, "frames": n, "size": list(im.size)}
