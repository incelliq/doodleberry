"""Region tracker for the compositor (WP-36): a rectangle chosen on the first frame of a plate (an image sequence or a
video) is followed through the frames by normalised cross-correlation (OpenCV's matchTemplate) in a window around
where it was last, with a parabola fitted through the peak for sub-pixel positions. The template is the first frame's
region, refreshed from the matched spot when the match is very good (slow appearance changes) but never drifting
away from the original (a refresh needs a strong match to the first template too). Also gives the region's mean
luminance per frame, so picture content can drive a parameter (a glow that brightens with a lamp in the plate).
"""
import glob
import subprocess
from pathlib import Path

import numpy as np


def frames_of(src, root, fps=30):
    """grey float32 frames (0..1) from an image sequence pattern (printf %04d or a glob) or a video file"""
    import cv2
    p = str(src)
    if "%" in p:
        files = []
        i = 0
        while True:
            f = Path(root) / (p % i)
            if not f.exists():
                if i == 0:
                    i += 1; continue
                break
            files.append(f); i += 1
    elif any(ch in p for ch in "*?["):
        files = [Path(f) for f in sorted(glob.glob(str(Path(root) / p)))]
    else:
        files = None
    if files is not None:
        for f in files:
            im = cv2.imread(str(f), cv2.IMREAD_COLOR)
            yield cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        return
    v = Path(p) if Path(p).is_absolute() else Path(root) / p
    w, h = [int(x) for x in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(v)],
                                            capture_output=True, text=True, check=True).stdout.strip().split(",")[:2]]
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(v), "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    while True:
        b = pr.stdout.read(w * h)
        if len(b) < w * h:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w).astype(np.float32) / 255.0
    pr.wait()


def _peak(res):
    """sub-pixel peak of a correlation map: a parabola through the best cell and its neighbours, each axis"""
    _, mx, _, (x, y) = __import__("cv2").minMaxLoc(res)
    dx = dy = 0.0
    if 0 < x < res.shape[1] - 1:
        l, c, r = res[y, x - 1], res[y, x], res[y, x + 1]; den = l - 2 * c + r
        dx = 0.5 * (l - r) / den if den else 0.0
    if 0 < y < res.shape[0] - 1:
        u, c, d = res[y - 1, x], res[y, x], res[y + 1, x]; den = u - 2 * c + d
        dy = 0.5 * (u - d) / den if den else 0.0
    return x + float(np.clip(dx, -0.5, 0.5)), y + float(np.clip(dy, -0.5, 0.5)), float(mx)


def track(frames, region, search=48, refresh=0.97):
    """frames: iterable of grey float arrays; region: [x, y, w, h] on the first. -> [(cx, cy, luma, score)] per frame,
    cx, cy the region's centre in frame pixels"""
    import cv2
    x, y, w, h = [int(round(v)) for v in region]
    out, tpl0, tpl, pos = [], None, None, None
    for k, f in enumerate(frames):
        f = np.asarray(f, np.float32)
        if k == 0:
            tpl0 = f[y:y + h, x:x + w].copy(); tpl = tpl0; pos = (float(x), float(y))
            out.append((x + w / 2, y + h / 2, float(tpl0.mean()), 1.0)); continue
        H, W = f.shape
        sx0, sy0 = max(0, int(pos[0]) - search), max(0, int(pos[1]) - search)
        sx1, sy1 = min(W, int(pos[0]) + w + search), min(H, int(pos[1]) + h + search)
        win = f[sy0:sy1, sx0:sx1]
        if win.shape[0] < h or win.shape[1] < w:
            out.append((pos[0] + w / 2, pos[1] + h / 2, out[-1][2], 0.0)); continue
        px, py, score = _peak(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED))
        pos = (sx0 + px, sy0 + py)
        ix, iy = int(round(pos[0])), int(round(pos[1]))
        cut = f[iy:iy + h, ix:ix + w]
        luma = float(cut.mean()) if cut.shape == tpl0.shape else out[-1][2]
        if score > refresh and cut.shape == tpl0.shape and float(cv2.matchTemplate(cut, tpl0, cv2.TM_CCOEFF_NORMED)[0, 0]) > refresh - 0.05:
            tpl = cut.copy()
        out.append((pos[0] + w / 2, pos[1] + h / 2, luma, score))
    return out
