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
#   bash tools/setup.sh godot      Godot 4.5 (official build, SHA-512 checked) into /opt/godot: export.godot's real-engine render check (WP-30)
#   bash tools/setup.sh opentoonz  OpenToonz 1.8.0's renderer (tcomposer) built from source (git tag checked by commit) into
#                                  /opt/opentoonz, with its stuff folder: export.opentoonz's render check (WP-34; BSD-3-Clause; ~25 min on 4 cores)
#   bash tools/setup.sh plates     Servier Medical Art anatomy plates (CC BY 4.0) into assets/external/plates, sha256-checked (WP-16)
#   bash tools/setup.sh live       MediaPipe Tasks Vision for the browser (npm, pinned in tools/live/package.json): the /live page (WP-12)
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
# tools go to /opt (root, containers) or, without root, to ~/.local/opt with links in ~/.local/bin; dbe looks in DBE_OPT,
# /opt and ~/.local/opt
if [ "$(id -u)" = 0 ] || [ -w /opt ]; then OPT="${DBE_OPT:-/opt}"; BIN="/usr/local/bin"; else OPT="${DBE_OPT:-$HOME/.local/opt}"; BIN="$HOME/.local/bin"; fi
mkdir -p "$OPT" "$BIN"
# has PATTERN CMD...: CMD's output contains PATTERN. (A pipe into grep -q fails under pipefail: grep exits at the first
# match and CMD dies of SIGPIPE.)
has() { local pat="$1" out; shift; out="$("$@" 2>/dev/null)" || true; [[ "$out" == *"$pat"* ]]; }

system() {
  if command -v apt-get >/dev/null; then
    need=""
    command -v ffmpeg >/dev/null || need="$need ffmpeg"
    command -v git >/dev/null || need="$need git"
    "$PY" -c "import ctypes.util,sys; sys.exit(0 if ctypes.util.find_library('EGL') else 1)" || need="$need libegl1 libgles2"
    if [ -n "$need" ]; then
      echo "apt: installing$need"; (apt-get install -y -q $need || (apt-get update -q && apt-get install -y -q $need))
    else echo "system: ok"; fi
  elif command -v dnf >/dev/null; then   # Fedora: ffmpeg with H.264 is RPM Fusion's (Fedora's own ffmpeg-free has no libx264)
    need=""
    (command -v ffmpeg >/dev/null && has libx264 ffmpeg -hide_banner -encoders) || need="$need ffmpeg"
    command -v git >/dev/null || need="$need git"
    command -v node >/dev/null || need="$need nodejs"
    "$PY" -m pip --version >/dev/null 2>&1 || need="$need python3-pip"
    "$PY" -c "import ctypes.util,sys; sys.exit(0 if ctypes.util.find_library('EGL') else 1)" || need="$need mesa-libEGL libglvnd-gles"
    if [ -z "$need" ]; then echo "system: ok"
    elif [ "$(id -u)" = 0 ]; then dnf install -y $need
    else
      echo "system: missing$need. Run:  sudo dnf install$need"
      case "$need" in *ffmpeg*) echo "  (ffmpeg with H.264 comes from RPM Fusion: https://rpmfusion.org/Configuration, then: sudo dnf swap ffmpeg-free ffmpeg --allowerasing)";; esac
    fi
  else echo "system: no apt-get or dnf; install ffmpeg (with libx264), git, Node.js and libEGL with your package manager"; fi
}

python_deps() {
  # kokoro-onnx 0.6.1 (the narrator) is for Python 3.10 to 3.13; Fedora 43 and newer default to 3.14
  if ! "$PY" -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)"; then
    echo "python: $("$PY" -c 'import sys; print(sys.version.split()[0])') is not supported; use Python 3.11 to 3.13 in its own virtual environment, e.g.:"
    echo "  sudo dnf install python3.13 && python3.13 -m venv ~/.venvs/doodleberry && source ~/.venvs/doodleberry/bin/activate"
    echo "  then: DBE_PY=python bash tools/setup.sh python"
    exit 1
  fi
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
    # root installs it globally; without root it goes into the checkout's node_modules (git-ignored), where the tools'
    # require('playwright') finds it; the browser itself goes to ~/.cache/ms-playwright either way
    # --prefix: install into this checkout even when a folder above it has a package.json; retries for slow links
    local npmo="--no-audit --no-fund --fetch-retries 5 --fetch-retry-mintimeout 20000 --fetch-timeout 300000"
    if [ "$(id -u)" = 0 ]; then npm install -g $npmo playwright@1.63.0
    else npm install --prefix "$PWD" --no-save $npmo playwright@1.63.0; fi \
      || { echo "node: npm could not install playwright; the reason is in the last lines of the newest log:"; ls -t ~/.npm/_logs/*-debug-0.log 2>/dev/null | head -1 | xargs -r tail -n 25; exit 1; }
    npx playwright install chromium || { echo "node: the Chromium download failed (it is about 170 MB); run  npx playwright install chromium  again"; exit 1; }
  fi
}

oss_deps() {
  if command -v apt-get >/dev/null; then
    local need="" pkgs="pencil2d inkscape synfig libmypaint-1.5-1 mypaint-brushes opencolorio-tools openimageio-tools melt frei0r-plugins krita xvfb"
    for p in $pkgs; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
    if [ -z "$need" ]; then echo "oss: all installed"; return; fi
    echo "oss: installing$need"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need || (apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $need)
  elif command -v dnf >/dev/null; then
    # Fedora's names for the same tools (checked against Fedora 44's package index); mypaint2-brushes is the 2.0 set
    # the apt branch gets. Fedora has no Pencil2D package: it comes from Flathub (below).
    local need="" pkgs="inkscape synfig libmypaint mypaint2-brushes OpenColorIO-tools OpenImageIO-utils mlt frei0r-plugins krita xorg-x11-server-Xvfb"
    for p in $pkgs; do rpm -q "$p" >/dev/null 2>&1 || need="$need $p"; done
    if [ -z "$need" ]; then echo "oss: Fedora packages installed"
    elif [ "$(id -u)" = 0 ]; then dnf install -y $need
    else echo "oss: missing$need. Run:  sudo dnf install$need"; fi
    pencil2d_flatpak
  else echo "oss: no apt-get or dnf; install Pencil2D, Inkscape, Synfig, libmypaint with the MyPaint 2.0 brushes, OpenColorIO and OpenImageIO tools, melt, frei0r, Krita and Xvfb"; fi
}

pencil2d_flatpak() {
  # Pencil2D from Flathub, reached as `pencil2d` through a small wrapper in $BIN (dbe looks the program up on PATH)
  if command -v pencil2d >/dev/null; then echo "pencil2d: $(command -v pencil2d)"; return; fi
  if ! command -v flatpak >/dev/null; then echo "pencil2d: not packaged for this system; install flatpak, add Flathub (flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo), then: flatpak install --user flathub org.pencil2d.Pencil2D"; return; fi
  if ! flatpak info org.pencil2d.Pencil2D >/dev/null 2>&1; then
    echo "pencil2d: not installed. Run:"
    echo "  flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"
    echo "  flatpak install --user flathub org.pencil2d.Pencil2D"
    echo "  then  bash tools/setup.sh oss  again"; return
  fi
  printf '%s\n' '#!/bin/sh' '# Pencil2D from Flathub (written by tools/setup.sh oss); host files so dbe can hand it projects and read frames back' \
    'exec flatpak run --filesystem=host --env=QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-}" org.pencil2d.Pencil2D "$@"' > "$BIN/pencil2d"
  chmod +x "$BIN/pencil2d"; echo "pencil2d: wrapper for the Flathub app at $BIN/pencil2d"
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
  local langs="ara sin hin heb tha ben tam jpn chi-sim kor rus spa fra urd fas"
  if command -v apt-get >/dev/null; then
    pk="fonts-noto-core fonts-noto-cjk espeak-ng tesseract-ocr"
    for l in $langs; do pk="$pk tesseract-ocr-$l"; done
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $pk || (apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $pk)
  elif command -v dnf >/dev/null; then
    # Fedora: google-noto-fonts-all is the counterpart of fonts-noto-core (every Noto family); language packs use _ (chi_sim)
    local need="" pk="google-noto-fonts-all google-noto-sans-cjk-fonts espeak-ng tesseract"
    for l in $langs; do pk="$pk tesseract-langpack-${l//-/_}"; done
    for p in $pk; do rpm -q "$p" >/dev/null 2>&1 || need="$need $p"; done
    if [ -z "$need" ]; then echo "locales: installed"
    elif [ "$(id -u)" = 0 ]; then dnf install -y $need
    else echo "locales: missing$need. Run:  sudo dnf install$need"; fi
  else echo "locales: no apt-get or dnf; install Noto fonts, eSpeak NG and Tesseract with its language data"; fi
}

provenance_dl() {
  # c2patool (MIT / Apache-2.0), the Content Authenticity Initiative's reference tool: reads and verifies C2PA content credentials (WP-26)
  local ver="0.27.22" sha="6f138ad53da1a62f1cd6ee71c60727efa27d13b811f4c0ea8c2a8528968b358b"
  if [ -x "$OPT"/c2patool/c2patool ] && has "$ver" "$OPT"/c2patool/c2patool --version; then echo "c2patool: $ver installed"; return; fi
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/c.tgz" "https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v${ver}/c2patool-v${ver}-x86_64-unknown-linux-gnu.tar.gz"
  echo "$sha  $tmp/c.tgz" | sha256sum -c - || { echo "c2patool: checksum mismatch"; rm -rf "$tmp"; return 1; }
  tar xzf "$tmp/c.tgz" -C "$tmp" && mkdir -p "$OPT"/c2patool && cp "$tmp/c2patool/c2patool" "$OPT"/c2patool/ && rm -rf "$tmp"
}

dotlottie_deps() {
  # @lottiefiles/dotlottie-web (MIT; ThorVG in WebAssembly) draws .lottie files and their themes in lottie.dotlottie's checks (WP-23)
  if [ -d "tools/dotlottie/node_modules/@lottiefiles/dotlottie-web" ]; then echo "dotlottie: player ok"; return; fi
  (cd tools/dotlottie && npm install --no-audit --no-fund)
}

live_deps() {
  # @mediapipe/tasks-vision (Apache-2.0): Pose Landmarker in WebAssembly for the /live page, a character following the webcam (WP-12)
  if [ -d "tools/live/node_modules/@mediapipe/tasks-vision" ]; then echo "live: tasks-vision ok"; return; fi
  (cd tools/live && npm install --no-audit --no-fund)
}

godot_dl() {
  # Godot 4.5-stable (MIT), the official Linux build checked against the release's SHA512-SUMS: renders export.godot's projects (WP-30)
  local ver="4.5-stable" sha="b5bd5d8a4dd3f44de1d123361beabaafa4825dd05b5e20fd2bfa540f32594f81d82e7c4e86fae420f4faee77d9def573b570f8b156e9c84a4dc2d5123d09e852"
  if [ -x "$OPT"/godot/godot ] && has "4.5.stable" "$OPT"/godot/godot --version --headless; then echo "godot: $ver installed"; return; fi
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/g.zip" "https://github.com/godotengine/godot/releases/download/$ver/Godot_v${ver}_linux.x86_64.zip"
  echo "$sha  $tmp/g.zip" | sha512sum -c - || { echo "godot: checksum mismatch"; rm -rf "$tmp"; return 1; }
  mkdir -p "$OPT"/godot && python3 -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$tmp/g.zip" "$OPT/godot" && rm -rf "$tmp"
  chmod +x "$OPT/godot/Godot_v${ver}_linux.x86_64" && ln -sf "$OPT/godot/Godot_v${ver}_linux.x86_64" "$OPT"/godot/godot
}

opentoonz_build() {
  # OpenToonz 1.8.0 (BSD-3-Clause): its bundled libtiff (OpenToonz needs its changes), then only the tcomposer target
  local tag="v1.8.0" commit="065cc1404ba43019b22a2577d529134c3e01931b" src="$OPT/src/opentoonz-1.8.0"
  if [ -x "$OPT"/opentoonz/bin/tcomposer ] && [ -d "$OPT"/opentoonz/stuff ]; then echo "opentoonz: tcomposer installed"; return; fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends build-essential cmake pkg-config libboost-all-dev qtbase5-dev libqt5svg5-dev qtscript5-dev qttools5-dev qttools5-dev-tools \
    libqt5opengl5-dev qtmultimedia5-dev libqt5multimedia5-plugins libqt5serialport5-dev libsuperlu-dev liblz4-dev libusb-1.0-0-dev liblzo2-dev \
    libpng-dev libjpeg-dev libglew-dev freeglut3-dev libfreetype-dev libjson-c-dev libmypaint-dev libopencv-dev libturbojpeg0-dev libopenblas-dev xvfb
  [ -d "$src/.git" ] || { mkdir -p "$OPT"/src && git clone --depth 1 --branch "$tag" https://github.com/opentoonz/opentoonz "$src"; }
  [ "$(git -C "$src" rev-parse HEAD)" = "$commit" ] || { echo "opentoonz: $src is not $tag ($commit)"; return 1; }
  (cd "$src/thirdparty/tiff-4.0.3" && { [ -f libtiff/.libs/libtiff.a ] || { ./configure --with-pic --disable-jbig --disable-lzma && make -j"$(nproc)"; }; })
  mkdir -p "$src/toonz/build" && (cd "$src/toonz/build" && cmake ../sources -DCMAKE_BUILD_TYPE=Release -DWITH_TRANSLATION=OFF -DCMAKE_INSTALL_PREFIX="$OPT"/opentoonz \
    && make -j"$(nproc)" tcomposer)
  local b="$src/toonz/build"; mkdir -p "$OPT"/opentoonz/bin "$OPT"/opentoonz/lib/opentoonz
  cp "$b/bin/tcomposer" "$OPT"/opentoonz/bin/ && cp -P "$b"/lib/opentoonz/*.so* "$OPT"/opentoonz/lib/opentoonz/   # export.opentoonz sets LD_LIBRARY_PATH to it
  rm -rf "$OPT"/opentoonz/stuff && cp -r "$src/stuff" "$OPT"/opentoonz/stuff
  LD_LIBRARY_PATH="$OPT"/opentoonz/lib/opentoonz "$OPT"/opentoonz/bin/tcomposer 2>&1 | head -2 || true
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
  if [ -x "$OPT"/blender/blender ] && has "Blender $ver" "$OPT"/blender/blender --version; then echo "blender: $ver installed"; return; fi
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/b.tar.xz" "https://download.blender.org/release/Blender${ver%.*}/blender-${ver}-linux-x64.tar.xz"
  echo "$sha  $tmp/b.tar.xz" | sha256sum -c - || { echo "blender: checksum mismatch"; rm -rf "$tmp"; return 1; }
  tar -xf "$tmp/b.tar.xz" -C "$OPT" && ln -sfn "$OPT/blender-${ver}-linux-x64" "$OPT"/blender && ln -sf "$OPT"/blender/blender "$BIN"/blender
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
  live) live_deps ;;
  plates) plates_dl ;;
  godot) godot_dl ;;
  opentoonz) opentoonz_build ;;
  voices) voices_dl "$@" ;;
  locales) locales_deps ;;
  provenance) provenance_dl ;;
  all) system; python_deps; models; node_deps; physics_deps; dotlottie_deps; map_deps; live_deps; voices_dl; provenance_dl ;;
  *) echo "usage: bash tools/setup.sh [all|system|python|models|node|oss|blender|physics|dotlottie|maps|live|plates|godot|opentoonz|voices|locales|provenance]"; exit 2 ;;
esac
if "$PY" -c "import numpy, jsonschema" 2>/dev/null; then
  "$PY" -m dbe engine.doctor '{"deep": false}' | "$PY" -c "import json,sys; r=json.load(sys.stdin); print('doctor:', 'ok' if r['ok'] else 'missing ' + ', '.join(r['missing_required'])); [print('  fix:', f) for f in r['fixes']]" || echo "doctor: failed; run  $PY -m dbe engine.doctor  to see why"
else echo "doctor: the Python packages are not installed yet; next:  DBE_PY=$PY bash tools/setup.sh python"; fi
