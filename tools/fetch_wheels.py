"""Fetch the wheels for pinned requirements with plain HTTP, for this exact platform (WP-02).

pip can stall on large wheels behind some proxies; downloading them first and then installing with
`pip install --find-links DIR` avoids that. The wheel is chosen by this interpreter's own compatibility tags
(packaging.tags.sys_tags, most specific first), so an ARM or macOS build is never picked by mistake.

    python tools/fetch_wheels.py DIR requirements-audio.txt [more files...]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dbe.doctor import requirements  # noqa: E402


def best_wheel(name, version):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as r:
        files = [u for u in json.load(r)["urls"] if u["filename"].endswith(".whl")]
    rank = {t: i for i, t in enumerate(sys_tags())}
    best = None
    for u in files:
        _, _, _, tags = parse_wheel_filename(u["filename"])
        score = min((rank[t] for t in tags if t in rank), default=None)
        if score is not None and (best is None or score < best[0]):
            best = (score, u)
    return best[1] if best else None


def fetch(url, dst, tries=4):
    for k in range(tries):
        try:
            tmp = dst.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dst); return True
        except Exception as e:
            print(f"  retry {k + 1}: {e}", file=sys.stderr); time.sleep(2 ** (k + 1))
    return False


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    for fname in sys.argv[2:]:
        for name, op, ver in requirements(fname):
            if op != "==":
                continue   # unpinned: small, left to pip
            w = best_wheel(name, ver)
            if not w:
                print(f"{name}=={ver}: no wheel for this platform (pip will build it from source)"); continue
            dst = out / w["filename"]
            if dst.exists() and dst.stat().st_size == w["size"]:
                print(f"{name}=={ver}: cached"); continue
            ok = fetch(w["url"], dst)
            print(f"{name}=={ver}: {'fetched' if ok else 'FAILED'} {w['filename']} ({w['size'] // 1_000_000} MB)")


if __name__ == "__main__":
    main()
