"""Film-level captions: word-timed ASS subtitles burned in by ffmpeg/libass after the shots are joined, so every
renderer (svg, synfig, grease-pencil, lottie) gets identical captions.

Style: short chunks of up to `chunk` words, upper case, white with a thick dark outline, the spoken word in a
highlight colour. Font: engine/fonts/Fredoka.ttf (OFL).
"""
import re


def _ts(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_colour(hex_rgb, alpha=0):
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


CHAR_W = 0.6  # Fredoka bold caps: average advance as a share of the font size (measured generously)


def safe_width(W, H):
    return 896 if H > W else int(W * 0.9)  # 9:16: x 64-960 (platform rail); 16:9: 5% title-safe


def safe_margins(W, H):
    """left/right margins that centre captions inside the text-safe area (9:16 has a right rail)"""
    return (64, W - 960) if H > W else (int(W * 0.05), int(W * 0.05))


def fit_size(text, font_size, width):
    return int(min(font_size, width / max(1, len(text) * CHAR_W)))


def make_ass(timing, size, chunk=3, font="Fredoka", font_size=88, y_from_bottom=380,
             text="#ffffff", outline="#24160e", highlight="#ffd23f", upper=True):
    W, H = size
    if W > H and y_from_bottom == 380:  # landscape: keep inside 5% title-safe
        y_from_bottom, font_size = 90, min(font_size, 64)
    ml, mr = safe_margins(W, H)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{font_size},{_ass_colour(text)},{_ass_colour(text)},{_ass_colour(outline)},{_ass_colour('#000000', 0x80)},-1,0,0,0,100,100,1,0,1,9,4,2,{ml},{mr},{y_from_bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    hl = _ass_colour(highlight)
    events = []
    for line in timing.get("lines", []):
        words = line.get("words") or []
        for c0 in range(0, len(words), chunk):
            group = words[c0:c0 + chunk]
            for i, w in enumerate(group):
                start = w["start"]
                nxt = group[i + 1]["start"] if i + 1 < len(group) else None
                end = nxt if nxt is not None else w["end"] + 0.25
                # do not overlap the next chunk
                if i + 1 == len(group) and c0 + chunk < len(words):
                    end = min(end, words[c0 + chunk]["start"])
                parts = []
                for j, g in enumerate(group):
                    t = re.sub(r"[.,;:]$", "", _esc(g["text"]))
                    t = t.upper() if upper else t
                    parts.append(f"{{\\c{hl}}}{t}{{\\c{_ass_colour(text)}}}" if j == i else t)
                # a small pop on the first word of each chunk; long chunks shrink to fit the text-safe width
                pop = "{\\fscx92\\fscy92\\t(0,80,\\fscx100\\fscy100)}" if i == 0 else ""
                fs = fit_size(" ".join(g["text"] for g in group), font_size, safe_width(W, H))
                fit = f"{{\\fs{fs}}}" if fs < font_size else ""
                events.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{fit}{pop}{' '.join(parts)}")
    return head + "\n".join(events) + "\n"


# ---------------- sidecar subtitles (SRT / WebVTT) ----------------
def _cues(timing, max_chars=42, max_lines=2):
    """subtitle cues from word timings: split each spoken line into blocks of at most max_lines x max_chars"""
    out = []
    for line in timing.get("lines", []):
        words = line.get("words") or []
        block, rows, cur = [], [], ""
        def flush():
            nonlocal block, rows, cur
            if cur:
                rows.append(cur)
            if block:
                out.append((block[0]["start"], block[-1]["end"] + 0.25, "\n".join(rows)))
            block, rows, cur = [], [], ""
        for w in words:
            t = w["text"]
            if len(cur) + len(t) + 1 > max_chars and cur:
                rows.append(cur); cur = ""
                if len(rows) == max_lines:
                    cur_rows = rows; rows = []
                    out.append((block[0]["start"], block[-1]["end"] + 0.25, "\n".join(cur_rows))); block = []
            cur = (cur + " " + t).strip(); block.append(w)
        flush()
    # no overlaps
    fixed = []
    for i, (a, b, txt) in enumerate(out):
        nb = out[i + 1][0] if i + 1 < len(out) else b
        fixed.append((a, min(b, nb - 0.02) if nb > a else b, txt))
    return fixed


def _stamp(t, sep):
    t = max(0.0, t); ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def make_srt(timing):
    return "".join(f"{i}\n{_stamp(a, ',')} --> {_stamp(b, ',')}\n{txt}\n\n" for i, (a, b, txt) in enumerate(_cues(timing), 1))


def make_vtt(timing):
    return "WEBVTT\n\n" + "".join(f"{_stamp(a, '.')} --> {_stamp(b, '.')}\n{txt}\n\n" for a, b, txt in _cues(timing))
