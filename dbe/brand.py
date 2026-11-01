"""Brand kit (plan 1.14): a measured palette and generated brand assets.

check(brand) measures, the way the film playbook's palette research did:
- WCAG 2.x contrast for every text-on-ground pair the brand declares (4.5:1 body, 3:1 large text and graphics)
- colour-vision-deficiency separation: the accent colours simulated under protanopia, deuteranopia and tritanopia
  (Machado, Oliveira & Fernandes 2009, severity 1.0) and compared with CIEDE2000
- distance from the platforms' own interface colours (CIEDE2000), so the brand stands out in each feed

assets(brand, out) renders a profile tile and covers sized for each platform, with text inside each one's safe area.
"""
import math
from pathlib import Path

import numpy as np

PLATFORM_UI = {"Facebook": "#0866FF", "LinkedIn": "#0A66C2", "YouTube": "#FF0000", "TikTok": "#FE2C55"}
# Machado et al. 2009, severity 1.0, applied to linear RGB
CVD = {
    "protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def luminance(h):
    r, g, b = to_lin(hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lab(rgb):
    r, g, b = to_lin(rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def de2000(c1, c2):
    """CIEDE2000 colour difference between two sRGB colours (0..1 arrays or hex strings)"""
    L1, a1, b1 = lab(hex_rgb(c1) if isinstance(c1, str) else c1)
    L2, a2, b2 = lab(hex_rgb(c2) if isinstance(c2, str) else c2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2); Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360; h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dhp = 0 if C1p * C2p == 0 else (h2p - h1p if abs(h2p - h1p) <= 180 else h2p - h1p - 360 if h2p > h1p else h2p - h1p + 360)
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    hpm = h1p + h2p if C1p * C2p == 0 else ((h1p + h2p) / 2 if abs(h1p - h2p) <= 180 else ((h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2))
    T = 1 - 0.17 * math.cos(math.radians(hpm - 30)) + 0.24 * math.cos(math.radians(2 * hpm)) + 0.32 * math.cos(math.radians(3 * hpm + 6)) - 0.20 * math.cos(math.radians(4 * hpm - 63))
    dth = 30 * math.exp(-((hpm - 275) / 25) ** 2); Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2); Sc = 1 + 0.045 * Cpm; Sh = 1 + 0.015 * Cpm * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def simulate(h, kind):
    return to_srgb(np.array(CVD[kind]) @ to_lin(hex_rgb(h)))


def check(brand):
    pal = brand["palette"]
    out = {"contrast": [], "cvd": [], "platform_distance": {}, "errors": [], "warnings": []}
    for pair in brand.get("text_pairs", []):
        fg, bg, kind = pair[0], pair[1], (pair[2] if len(pair) > 2 else "body")
        r = contrast(pal[fg], pal[bg]); need = 4.5 if kind == "body" else 3.0
        out["contrast"].append({"text": fg, "on": bg, "ratio": round(r, 2), "use": kind, "pass": bool(r >= need)})
        if r < need:
            out["errors"].append(f"{fg} on {bg}: {r:.2f}:1 is below {need}:1 for {kind} text")
    accents = brand.get("accents", [])
    worst = None
    for kind in CVD:
        for i, a in enumerate(accents):
            for b in accents[i + 1:]:
                d = de2000(simulate(pal[a], kind), simulate(pal[b], kind))
                out["cvd"].append({"pair": [a, b], "vision": kind, "de2000": round(d, 1)})
                worst = d if worst is None else min(worst, d)
    if worst is not None:
        out["cvd_min_de2000"] = round(worst, 1)
        if worst < 10:
            out["errors"].append(f"two accents become hard to tell apart for colour-blind viewers (CIEDE2000 {worst:.1f} < 10)")
        elif worst < 20:
            out["warnings"].append(f"closest accent pair under colour-blindness simulation is CIEDE2000 {worst:.1f} (aim for 20+), and never use colour alone")
    for name, ui in PLATFORM_UI.items():
        out["platform_distance"][name] = {a: round(de2000(pal[a], ui), 1) for a in accents}
        close = [a for a in accents if de2000(pal[a], ui) < 10]
        if close:
            out["warnings"].append(f"on {name}, {', '.join(close)} sits close to the platform's own colour {ui}: lead with another accent there")
    out["ok"] = not out["errors"]
    return out


def assets(brand, out_dir, font_path):
    """profile tile and platform covers with text inside each platform's safe area"""
    from PIL import Image, ImageDraw, ImageFont
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pal = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in brand["palette"].items()}
    wm = brand.get("wordmark", {"text": brand.get("name", "brand"), "accent_text": ""})
    made = []
    _truetype = ImageFont.truetype

    def bold(path, size):  # variable fonts (Fredoka) default to their lightest instance in PIL
        f = _truetype(path, size)
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
        return f
    ImageFont_truetype = bold

    def wordmark(d, x, y, size, on_dark=False):
        f = ImageFont_truetype(font_path, size)
        a, b = wm["text"], wm.get("accent_text", "")
        d.text((x, y), a, font=f, fill=pal["paper"] if on_dark else pal["ink"])
        d.text((x + f.getlength(a), y), b, font=f, fill=pal[brand.get("wordmark_accent", "primary")] if not on_dark else pal.get("highlight", pal["paper"]))
        return f.getlength(a + b)

    # profile tile: the initial on the primary colour (works as avatar, favicon and app icon)
    for size in (720, 400, 180):
        im = Image.new("RGB", (size, size), pal["paper"]); d = ImageDraw.Draw(im)
        r = size * 0.22; d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=pal["primary"])
        f = ImageFont_truetype(font_path, int(size * 0.62)); ch = wm["text"][:1]
        w = f.getlength(ch); bbox = f.getbbox(ch)
        d.text(((size - w) / 2, (size - (bbox[3] - bbox[1])) / 2 - bbox[1]), ch, font=f, fill=pal["paper"])
        d.ellipse([size * 0.70, size * 0.66, size * 0.80, size * 0.76], fill=pal.get("highlight", pal["paper"]))
        im.save(out / f"profile_{size}.png"); made.append(f"profile_{size}.png")
    # covers: (name, size, safe box) using each platform's visible area
    covers = [("youtube_banner", (2560, 1440), (507, 508, 2053, 931)), ("facebook_cover", (1640, 924), (120, 300, 1520, 700)),
              ("linkedin_cover", (1128, 191), (340, 30, 1100, 160)), ("story", (1080, 1920), (64, 300, 960, 1500))]
    for name, (W, H), (x0, y0, x1, y1) in covers:
        im = Image.new("RGB", (W, H), pal["paper"]); d = ImageDraw.Draw(im)
        for i in range(0, W, max(40, W // 40)):  # a quiet signature band of the accent colours
            c = pal[brand["accents"][(i // max(40, W // 40)) % len(brand["accents"])]]
            d.rectangle([i, H - max(10, H // 30), i + max(40, W // 40) - 6, H], fill=c)
        size = int(min((y1 - y0) * 0.38, (x1 - x0) / max(1, len(wm["text"] + wm.get("accent_text", ""))) * 1.7))
        f = ImageFont_truetype(font_path, size); tw = f.getlength(wm["text"] + wm.get("accent_text", ""))
        wordmark(d, x0 + ((x1 - x0) - tw) / 2, y0 + (y1 - y0) * 0.18, size)
        if brand.get("tagline"):
            ts = max(18, int(size * 0.36)); tf = ImageFont_truetype(font_path, ts); tl = brand["tagline"]
            while tf.getlength(tl) > (x1 - x0) and ts > 14:
                ts -= 2; tf = ImageFont_truetype(font_path, ts)
            d.text((x0 + ((x1 - x0) - tf.getlength(tl)) / 2, y0 + (y1 - y0) * 0.18 + size * 1.25), tl, font=tf, fill=pal["ink"])
        im.save(out / f"{name}_{W}x{H}.png"); made.append(f"{name}_{W}x{H}.png")
        qa = im.copy(); dq = ImageDraw.Draw(qa); dq.rectangle([x0, y0, x1, y1], outline=(255, 0, 255), width=max(2, W // 400))
        (out / "qa").mkdir(exist_ok=True); qa.save(out / "qa" / f"{name}_safe.png")
    return made
