#!/usr/bin/env bash
# One-step setup for a fresh machine or container (work package WP-02). Idempotent: run it again any time.
#   bash tools/setup.sh            everything
#   bash tools/setup.sh system     apt packages (ffmpeg, libEGL for MediaPipe, git)
#   bash tools/setup.sh python     core, audio and tools requirements (large wheels fetched with plain HTTP first)
#   bash tools/setup.sh models     Kokoro voice model files (+ the timed model) and MediaPipe models, checked by sha256
#   bash tools/setup.sh node       Playwright and its Chromium, only if `require('playwright')` fails
#   bash tools/setup.sh blender    Blender 5.2.3 LTS from blender.org (sha256 checked) into /opt/blender, for the Grease
#                                  Pencil renderer (needs 4.3 or newer; Ubuntu's package is 4.0)
#   bash tools/setup.sh oss        optional open-source parts (WP-34): Pencil2D, Inkscape, Synfig, libmypaint and the
#                                  MyPaint brushes, OpenColorIO and OpenImageIO tools (not part of "all": about 700 MB)
#   bash tools/setup.sh physics    deterministic Rapier 2D (npm, pinned in tools/physics/package.json) for physics.solve (WP-09)
#   bash tools/setup.sh dotlottie  the dotLottie player (npm, pinned in tools/dotlottie/package.json) for lottie.dotlottie's checks (WP-23)
#   bash tools/setup.sh plates     Servier Medical Art anatomy plates (CC BY 4.0) into assets/external/plates, sha256-checked (WP-16)
#   bash tools/setup.sh maps       d3-geo, topojson-client and world-atlas (npm, pinned in tools/mapboard/package.json) to make and check map board data (WP-16)
#   bash tools/setup.sh voices [de,uk,...]  Piper voices from voices/registry.json: those films use ("fetched"), or every voice
#                                  of the languages named (checked by sha256 or the catalogue's md5) (WP-25)
#   bash tools/setup.sh locales    world languages (WP-25): Noto fonts for captions, Noto CJK, eSpeak NG, Tesseract and its language data
#   bash tools/setup.sh provenance c2patool 0.27.22, the C2PA reference tool (sha256 checked), into /opt/c2patool (WP-26)
# Then: python -m dbe engine.doctor
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${DBE_PY:-python3}"
VOICES="${DBE_VOICES:-$HOME/voices}"
WHEELS="${DBE_WHEELS:-$HOME/.cache/doodleberry/wheels}"
what="${1:-all}"

system() {
  if command -v apt-get >/dev/null; then
    need=""
    command -v ffmpeg >/dev/null || need="$need ffmpeg"
    command -v git >/dev/null || need="$need git"
    "$PY" -c "import ctypes.util,sys; sys.exit(0 if ctypes.util.find_library('EGL') else 1)" || need="$need libegl1 libgles2"
    if [ -n "$need" ]; then
      echo "apt: installing$need"; (apt-get install -y -q $need || (apt-get update -q && apt-get install -y -q $need))
    else echo "system: ok"; fi
  else echo "system: no apt-get; install ffmpeg, git and libEGL with your package manager"; fi
}

python_deps() {
  "$PY" -m pip --version >/dev/null
  "$PY" -c "import packaging" 2>/dev/null || "$PY" -m pip install -q packaging
  "$PY" tools/fetch_wheels.py "$WHEELS" requirements-audio.txt requirements-tools.txt
  for f in requirements-core.txt requirements-audio.txt requirements-tools.txt; do
    echo "pip: $f"; "$PY" -m pip install -q --progress-bar off --default-timeout 60 --find-links "$WHEELS" -r "$f"
  done
}

models() {
  mkdir -p "$VOICES/kokoro"
  "$PY" - "$VOICES" <<'PYEOF'
import hashlib, sys, urllib.request
from pathlib import Path
sys.path.insert(0, "."); sys.path.insert(0, "engine")
from dbe.doctor import KOKORO_FILES, KOKORO_URL
d = Path(sys.argv[1]) / "kokoro"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for fn, want in KOKORO_FILES.items():
    p = d / fn
    if p.exists() and sha(p) == want:
        print(f"kokoro {fn}: ok"); continue
    print(f"kokoro {fn}: fetching"); urllib.request.urlretrieve(KOKORO_URL + fn, p)
    assert sha(p) == want, f"{fn}: sha256 mismatch"
import kokoro_voice
print("kokoro timed model:", kokoro_voice.timed_model(d) or "skipped (needs the onnx package)")
from dbe import actout
for kind in actout.MODEL_FILES:
    print("mediapipe", kind, actout.model_path(kind))
from dbe import assists   # WP-43: RIFE 4.9 (in-betweens) and Depth Anything V2 Small (depth), pinned by sha256
for name in ("rife49", "depth_small"):
    print("assist", name, assists.model_path(name))
PYEOF
}

node_deps() {
  if NODE_PATH="${NODE_PATH:-}:$(npm root -g 2>/dev/null)" node -e "require('playwright')" 2>/dev/null; then
    echo "node: playwright ok"
  else
    npm install -g playwright && npx playwright install chromium
  fi
}

oss_deps() {
  local need="" pkgs="pencil2d inkscape synfig libmypaint-1.5-1 mypaint-brushes opencolorio-tools openimageio-tools melt frei0r-plugins krita xvfb"
  for p in $pkgs; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
  if [ -z "$need" ]; then echo "oss: all installed"; return; fi
  echo "oss: installing$need"
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need || (apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need)
}

physics_deps() {
  # deterministic Rapier (Apache-2.0) for physics.solve (WP-09); pinned in tools/physics/package.json
  if [ -d "tools/physics/node_modules/@dimforge/rapier2d-deterministic-compat" ]; then echo "physics: rapier ok"; return; fi
  (cd tools/physics && npm install --no-audit --no-fund)
}

voices_dl() {
  # Piper voices listed with a download URL in voices/registry.json (WP-25: Arabic, Sinhala), checked by sha256
  mkdir -p "$VOICES"
  "$PY" - "$VOICES" "${2:-}" <<'PYEOF'
import sys
sys.path.insert(0, ".")
from dbe.commands import ensure_voice, _json, ROOT
langs = [x for x in sys.argv[2].split(",") if x]
for vid, r in _json(ROOT / "voices" / "registry.json")["voices"].items():
    if r.get("url") and (r.get("fetched") or vid.split("_")[0] in langs):
        print(f"voice {vid}: {ensure_voice(vid)} ({r['status']})")
PYEOF
}

locales_deps() {
  # fonts libass uses for captions in every script, CJK, phonemes for lip-sync, and OCR for film.text_check (WP-25)
  if command -v apt-get >/dev/null; then
    pk="fonts-noto-core fonts-noto-cjk espeak-ng tesseract-ocr tesseract-ocr-ara tesseract-ocr-sin tesseract-ocr-hin tesseract-ocr-heb tesseract-ocr-tha tesseract-ocr-ben tesseract-ocr-tam tesseract-ocr-jpn tesseract-ocr-chi-sim tesseract-ocr-kor tesseract-ocr-rus tesseract-ocr-spa tesseract-ocr-fra tesseract-ocr-urd tesseract-ocr-fas"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $pk || (apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $pk)
  else echo "locales: no apt-get; install Noto fonts, eSpeak NG and Tesseract with its language data"; fi
}

provenance_dl() {
  # c2patool (MIT / Apache-2.0), the Content Authenticity Initiative's reference tool: reads and verifies C2PA content credentials (WP-26)
  local ver="0.27.22" sha="6f138ad53da1a62f1cd6ee71c60727efa27d13b811f4c0ea8c2a8528968b358b"
  if [ -x /opt/c2patool/c2patool ] && /opt/c2patool/c2patool --version 2>/dev/null | grep -q "$ver"; then echo "c2patool: $ver installed"; return; fi
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/c.tgz" "https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v${ver}/c2patool-v${ver}-x86_64-unknown-linux-gnu.tar.gz"
  echo "$sha  $tmp/c.tgz" | sha256sum -c - || { echo "c2patool: checksum mismatch"; rm -rf "$tmp"; return 1; }
  tar xzf "$tmp/c.tgz" -C "$tmp" && mkdir -p /opt/c2patool && cp "$tmp/c2patool/c2patool" /opt/c2patool/ && rm -rf "$tmp"
}

dotlottie_deps() {
  # @lottiefiles/dotlottie-web (MIT; ThorVG in WebAssembly) draws .lottie files and their themes in lottie.dotlottie's checks (WP-23)
  if [ -d "tools/dotlottie/node_modules/@lottiefiles/dotlottie-web" ]; then echo "dotlottie: player ok"; return; fi
  (cd tools/dotlottie && npm install --no-audit --no-fund)
}

plates_dl() {
  # Servier Medical Art anatomy plates (CC BY 4.0), listed with their sha256 in assets/plates/plates.json (WP-16)
  python -m dbe plate.fetch '{}' >/dev/null && echo "plates: ok"
}

map_deps() {
  # d3-geo and topojson-client (ISC) with world-atlas (Natural Earth, public domain): tools/mapboard/make.mjs and check.mjs (WP-16)
  if [ -d "tools/mapboard/node_modules/d3-geo" ]; then echo "maps: d3-geo ok"; return; fi
  (cd tools/mapboard && npm install --no-audit --no-fund)
}

blender_dl() {
  local ver="5.2.3" sha="78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec"
  if [ -x /opt/blender/blender ] && /opt/blender/blender --version 2>/dev/null | grep -q "Blender $ver"; then echo "blender: $ver installed"; return; fi
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/b.tar.xz" "https://download.blender.org/release/Blender${ver%.*}/blender-${ver}-linux-x64.tar.xz"
  echo "$sha  $tmp/b.tar.xz" | sha256sum -c - || { echo "blender: checksum mismatch"; rm -rf "$tmp"; return 1; }
  tar -xf "$tmp/b.tar.xz" -C /opt && ln -sfn "/opt/blender-${ver}-linux-x64" /opt/blender && ln -sf /opt/blender/blender /usr/local/bin/blender
  rm -rf "$tmp"; blender --version | head -1
}

case "$what" in
  system) system ;;
  python) python_deps ;;
  models) models ;;
  node) node_deps ;;
  oss) oss_deps ;;
  blender) blender_dl ;;
  physics) physics_deps ;;
  dotlottie) dotlottie_deps ;;
  maps) map_deps ;;
  plates) plates_dl ;;
  voices) voices_dl "$@" ;;
  locales) locales_deps ;;
  provenance) provenance_dl ;;
  all) system; python_deps; models; node_deps; physics_deps; dotlottie_deps; map_deps; voices_dl; provenance_dl ;;
  *) echo "usage: bash tools/setup.sh [all|system|python|models|node|oss|blender|physics|dotlottie|maps|plates|voices|locales|provenance]"; exit 2 ;;
esac
"$PY" -m dbe engine.doctor '{"deep": false}' | "$PY" -c "import json,sys; r=json.load(sys.stdin); print('doctor:', 'ok' if r['ok'] else 'missing ' + ', '.join(r['missing_required'])); [print('  fix:', f) for f in r['fixes']]"
