#!/usr/bin/env bash
# One-step setup for a fresh machine or container (work package WP-02). Idempotent: run it again any time.
#   bash tools/setup.sh            everything
#   bash tools/setup.sh system     apt packages (ffmpeg, libEGL for MediaPipe, git)
#   bash tools/setup.sh python     core, audio and tools requirements (large wheels fetched with plain HTTP first)
#   bash tools/setup.sh models     Kokoro voice model files (+ the timed model) and MediaPipe models, checked by sha256
#   bash tools/setup.sh node       Playwright and its Chromium, only if `require('playwright')` fails
#   bash tools/setup.sh oss        optional open-source parts (WP-34): Pencil2D, Inkscape, Synfig, libmypaint and the
#                                  MyPaint brushes, OpenColorIO and OpenImageIO tools (not part of "all": about 700 MB)
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
  local need="" pkgs="pencil2d inkscape synfig libmypaint-1.5-1 mypaint-brushes opencolorio-tools openimageio-tools"
  for p in $pkgs; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
  if [ -z "$need" ]; then echo "oss: all installed"; return; fi
  echo "oss: installing$need"
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need || (apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need)
}

case "$what" in
  system) system ;;
  python) python_deps ;;
  models) models ;;
  node) node_deps ;;
  oss) oss_deps ;;
  all) system; python_deps; models; node_deps ;;
  *) echo "usage: bash tools/setup.sh [all|system|python|models|node|oss]"; exit 2 ;;
esac
"$PY" -m dbe engine.doctor '{"deep": false}' | "$PY" -c "import json,sys; r=json.load(sys.stdin); print('doctor:', 'ok' if r['ok'] else 'missing ' + ', '.join(r['missing_required'])); [print('  fix:', f) for f in r['fixes']]"
