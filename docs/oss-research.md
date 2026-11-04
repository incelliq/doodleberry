# Doodleberry: open-source research (November 2026)

> WP-34 (2 November 2026): the decision per part, with licence class and status, is `docs/oss-integration.md`.


Scope: OSS libraries, models, formats and assets that could strengthen Doodleberry, a headless, CPU-only animation backend (SVG frames rendered in Chromium, a cut-out puppet system, Lottie/Synfig/Grease Pencil exporters, three.js 3D, Piper/WORLD audio, and a command registry exposed through a CLI, HTTP and MCP).
This list leaves out what Doodleberry already does.

> **Policy update (2 November 2026):** Doodleberry is an in-house R&D platform, not a distributed product, so every
> licence below is usable in-house: GPL and AGPL code may be linked and modified, and NC or research-only models and
> data may be used for in-house work. The flags below now matter only for what ends up in a publicly posted film, where
> the posting gate flags NC, research-only and share-alike inputs for the owner. "Avoid" verdicts in this file were
> made under the old rule; read them as "flag at posting", not "do not use". See the licence rule in
> `docs/build-plan.md`.

## How to read this

**Licence verification tags**
- **[V]**: I read the project's own LICENSE file (on raw.githubusercontent.com or GitLab), its model card, or its official page during this session.
- **[R]**: I took the licence from registry metadata (PyPI, npm or the Hugging Face API) or from a web-search summary. I did not open the primary file.
- **[U]**: Unverified. This comes from prior knowledge, or the source could not be reached (the GitHub API is blocked from this container, and some repos did not respond on raw). Check these before relying on them.

**Licence flags**
- **COPYLEFT**: GPL or LGPL. Running a GPL tool as a separate process or service is normally fine. Linking it into code you distribute is not.
- **AGPL**: the network clause applies, so avoid importing it into the HTTP/MCP service.
- **NC**: non-commercial.
- **SA**: share-alike, for assets.
- **SRC-AVAIL**: source-available but not open source.

**Effort:** S = under 2 days, M = 1–2 weeks, L = more than 2 weeks.

"Headless CPU" means the tool runs in our container without a display or GPU. I installed nothing. The benchmark in section 5 used only tools that were already in the container: google-chrome, ffmpeg and node.

---

## 0. Findings that need action now (licence risk in the current stack)

1. **None of the Piper voices currently in use is cleanly licensed.** The built films' timing files list `en_GB-alan-medium`, `en_US-amy-medium`, `en_US-lessac-high` and `en_US-ryan-high`. The voices' own MODEL_CARD files on huggingface.co/rhasspy/piper-voices say:
   - **ryan (high): CC BY-NC-SA 4.0** [V]. Non-commercial and share-alike.
   - **lessac (high/medium):** trained on the Blizzard 2013 Lessac data. That data is under a **research licence** from Voice Factory and Lessac Technologies, granted to named licensees [V].
   - **amy (medium):** the card says "License: See URL" and points to the mimic3-voices repo. It was also **fine-tuned from lessac** [V], so it inherits the lessac question.
   - **alan (medium):** based on mimic3 `apope_low`. That voice's LICENSE file reads "Copyright 2022 Mycroft AI. All Rights Reserved" [V].

   The repo-level tag on piper-voices is "MIT", but that does not override the per-voice data licences.

   **Clean replacements** [V]:
   - Trained from scratch on data the voice card lists as public domain:
     - `en_US-kristin-medium`, `en_US-norman-medium`, `en_GB-cori-high` and `en_GB-cori-medium`.
     - `en_US-ljspeech-high` and `en_US-ljspeech-medium` (LJ Speech, public domain).
   - Public domain and not built on lessac:
     - `en_US-john-medium` (fine-tuned from kristin).
     - `en_US-bryce-medium` (the trainer's own voice).
   - Permissive licence but fine-tuned from lessac, so the lessac question remains:
     - `en_US-joe-medium` and `en_US-reza_ibrahim-medium` (CC0).
     - `en_US-sam-medium` (Apache-2.0).
     - `en_US-libritts_r-medium` and `en_GB-alba-medium` (CC BY 4.0).
     - `en_GB-northern_english_male-medium` (CC BY-SA 4.0).

   Kokoro-82M (Apache-2.0, see section 1) is the other clean option for more voices.
2. **The Piper engine moved to GPL.** `rhasspy/piper` (MIT) [V] is archived. Development continues in `OHF-Voice/piper1-gpl`, which is **GPL-3.0** [V]. `piper-tts` on PyPI is now v1.8.0 (2026-09) under `GPL-3.0-or-later` [R]. This is fine for an internal service. It matters if Doodleberry is ever shipped to customers as software. Pin the version you vetted.
3. **espeak-ng is GPL-3.0** [V], and so are `phonemizer` [V] and `phonemizer-fork` [R]. They sit under Piper, Kokoro's fallback G2P and many aligners. Same advice: keep them behind a process boundary if Doodleberry is ever distributed.
4. **Some popular "permissive" aligners default to NC weights.** `ctc-forced-aligner` is BSD-2 code [V], but its default MMS-300m forced-aligner weights are **CC-BY-NC-4.0** [R, HF API]. torchaudio's MMS_FA bundle uses the same MMS lineage [U].

---

## 1. Lip-sync, phoneme alignment and TTS

### 1a. Alignment and viseme extraction

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point in Doodleberry | Effort |
|---|---|---|---|---|---|---|
| **Rhubarb Lip Sync** | github.com/DanielSWolf/rhubarb-lip-sync | MIT, and LICENSE.md says all bundled deps are MIT, BSD or similar [V] | Mature. v1.14.0 is the latest release (April 2025 [U]), and releases are infrequent | Yes. C++ CLI with PocketSphinx; English recogniser, plus a phonetic mode for other languages | New `lipsync.rhubarb` command. It takes a WAV and the known dialogue text, and outputs JSON mouth cues A–H plus X (Preston Blair set). Map those to the mouth swap sets. Use it as a second opinion or QA diff against the espeak+Whisper visemes, and as a fallback when no transcript exists | S |
| **Montreal Forced Aligner (MFA)** | github.com/MontrealCorpusTools/Montreal-Forced-Aligner | MIT [V]. The pretrained `english_mfa` v3.1 acoustic model is **CC BY 4.0** [V, model docs page] | Active, v3.x. Installed from conda-forge; Kaldi-based | Yes, CPU | Phone-level TextGrid with real phone durations, replacing the step that spreads espeak phonemes across Whisper word spans. Feed the phones into the existing viseme map. Many languages have pretrained models and dictionaries; check each model's licence | M (separate conda env, called as a subprocess) |
| **wav2vec2 espeak phoneme CTC** + `torchaudio.functional.forced_align` | huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft, .../wav2vec2-xlsr-53-espeak-cv-ft | **Apache-2.0** weights [R, HF API] | Stable since 2021–2023; heavily downloaded | Yes. About 300M parameters, offline speed is fine on 4 CPUs | Emits espeak-IPA phones with frame timings, which is the same phone set Piper uses, so the viseme table carries over unchanged. Covers many languages. Can force-align against the phoneme string Piper already produced | M |
| **stable-ts** | github.com/jianfch/stable-ts | MIT [V] | v2.19.1 (2025-08) [R] | Yes, works with faster-whisper | `align(audio, known_text)`: more stable word timestamps when the script is known, which it always is | S |
| **WhisperX** | github.com/m-bain/whisperX | BSD-2-Clause [V] | v3.8.6 (2026-05) [R], active | Yes, but slow on CPU | Word and character alignment through wav2vec2. Only a small gain over faster-whisper plus stable-ts. Its diarisation uses pyannote, whose models are gated | S |
| ctc-forced-aligner | github.com/MahmoudAshraf97/ctc-forced-aligner | BSD-2 code [V]; **default MMS weights are NC** (CC-BY-NC-4.0) [R] | v1.0.2 (2025-02) | Yes | Usable only with Apache weights swapped in, which overlaps the wav2vec2 row above | S |
| charsiu | github.com/lingjzhu/charsiu | MIT code [V]; weight licence [U] | Dormant since about 2022 | Yes | Phoneme aligner. Superseded by the wav2vec2 row | — |
| Gentle | github.com/lowerquality/gentle | MIT [V] | Dormant (Kaldi, Docker) | Yes | Not recommended. MFA is the maintained Kaldi option | — |
| Allosaurus | github.com/xinjli/allosaurus | **GPL-3.0** [V] COPYLEFT | Dormant since 2021 | Yes | Universal phone recogniser, only if no other model covers a language | S |
| aeneas | github.com/readbeyond/aeneas | **AGPL-3.0** [V] AGPL | Dormant | Yes | Avoid in the service | — |
| Papagayo-NG | github.com/morevnaproject-org/papagayo-ng | **GPL-2.0-or-later** per source headers [R] COPYLEFT | Last push April 2023 [R] | GUI only | No value headless. Its Moho `.dat` switch format is trivial to emit ourselves if a client needs it | — |
| NVIDIA Audio2Face-3D | github.com/NVIDIA/Audio2Face-3D-SDK | SDK MIT [V]; models under the **NVIDIA Open Model License** [R] | 2025 open release | **No.** Needs a GPU and TensorRT | 3D blendshapes only. Not usable here | — |
| MakeItTalk | github.com/yzhou359/MakeItTalk | **CC BY-NC 4.0** [V] NC | Research code | — | Avoid | — |

### 1b. TTS engines and voices

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **Piper voices: clean subset** | huggingface.co/rhasspy/piper-voices | Per voice; see section 0 [V] | Catalogue updated 2026-10 | Yes | Swap the default cast to kristin, norman, john, bryce, cori and ljspeech. Add a `licence` field to the voice registry and refuse NC or unclear voices by default | S |
| **Kokoro-82M** | huggingface.co/hexgrad/Kokoro-82M, github.com/hexgrad/kokoro | **Apache-2.0** for weights and code [V]. G2P `misaki` is Apache-2.0 [V], but falls back to espeak-ng (GPL) | Very widely used (about 11M downloads); last weights update 2025-04 | Yes. 82M parameters, faster than real time on CPU | Second TTS backend. About 50 voices across 8 languages (en-US, en-GB, es, fr, hi, it, ja, pt-BR, zh), so more characters and multilingual output. It outputs phonemes, and reportedly per-token timestamps for English (verify), which feed the viseme pipeline. Then run it through WORLD and the mastering chain as now | M |
| kokoro-onnx | github.com/thewh1teagle/kokoro-onnx | MIT [V]; its phonemizer dependency `phonemizer-fork` is **GPL-3.0** [R] | v0.6.1 (2026-08) [R] | Yes, onnxruntime | Lighter Kokoro runtime with no torch dependency | S |
| onnx | github.com/onnx/onnx | Apache-2.0 [V] | v1.23.2 installed (2026-11) | Yes (Python, build-time only) | Used once to expose Kokoro's duration output as a model output (plan 2.1); not shipped in films | S |
| **Chatterbox** (Resemble AI) | github.com/resemble-ai/chatterbox | MIT code [V] and weights [R] | Active (2026-06) | Possible but slow (0.5B) | Expressive or emotional lines and zero-shot cloning *of voices you have rights to*. Has built-in watermarking. Offline batch only | M |
| MeloTTS | github.com/myshell-ai/MeloTTS | MIT [V, R] | Last update 2024-12 | Yes, real time on CPU | Multilingual fallback (en/es/fr/zh/ja/ko) | S–M |
| KittenTTS | github.com/KittenML/KittenTTS | Apache-2.0 [V] | 2025, early | Yes, tiny (about 15M) | Draft or preview voices; lower quality | S |
| NeuTTS Air | huggingface.co/neuphonic/neutts-air | Apache-2.0 per the HF card [R] | 2025–26 | Yes (GGUF, about 0.5B) | Cloning alternative. Check the card's terms and its watermarking | M |
| sherpa-onnx | github.com/k2-fsa/sherpa-onnx | Apache-2.0 [V] | Very active (v2.0.1, 2026-10) | Yes | Single C++/Python runtime for Piper, Kokoro, Kitten and Matcha models plus ASR. It may bundle espeak-ng-derived code (GPL); check before distributing [U] | M |
| StyleTTS2 | github.com/yl4579/StyleTTS2 | MIT code [V]. The README asks users of the pretrained LibriTTS weights to tell listeners the speech is synthetic unless they have voice permission [U, wording from memory] | Research code (2023) | Slow on CPU | Not recommended over Kokoro, which is StyleTTS2-derived | — |
| Coqui TTS / XTTS-v2 | github.com/idiap/coqui-ai-TTS (maintained fork) | Code MPL-2.0 [V]; **XTTS-v2 weights: Coqui Public Model License, non-commercial** [R, HF API] NC | Coqui (the company) shut down; the idiap fork keeps the code alive | Slow on CPU | Avoid XTTS weights. The code is fine with your own models | — |
| F5-TTS | github.com/SWivid/F5-TTS | MIT code [V]; **weights CC-BY-NC-4.0** [R] NC | Active | GPU-oriented | Avoid the weights | — |
| Kyutai TTS 1.6B | huggingface.co/kyutai/tts-1.6b-en_fr | CC-BY-4.0 weights [R] | 2025 | GPU-oriented | Skip on CPU | — |

---

## 2. Puppet and 2D rigging runtimes and formats

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **ThorVG** | github.com/thorvg/thorvg | MIT [V]. `thorvg-python` reports **LGPL** in PyPI metadata [R]; verify | Very active (2026). CPU rasteriser with SIMD (AVX2/NEON), per its README [V] | Yes | (a) Render every Lottie export with an independent renderer and diff it against our SVG frames (exporter QA). (b) Benchmark as a fast SVG rasteriser (see section 5). Also the engine inside dotLottie | S–M |
| **lottie-web** | github.com/airbnb/lottie-web | MIT [V] | v5.13.0 (2025-05) [R]; maintenance pace | Yes, in Chromium | Reference renderer for golden-image tests of the Lottie exporter, running in the Chromium we already have | S |
| **dotLottie** (dotlottie-rs, dotlottie-web) | github.com/LottieFiles/dotlottie-rs, .../dotlottie-web | MIT [V] | Very active (dotlottie-web v0.82, 2026-10) [R] | Yes | Package exports as `.lottie`, a zip that can hold several animations, **themes** and state machines. Map palette slots to dotLottie themes and the swap sets or action clips to multiple animations or markers | S–M |
| Lottie format spec and docs | lottie.github.io (Lottie Animation Community); github.com/LottieFiles/lottie-docs | lottie-docs is CC BY 4.0 [V]; spec repo licence [U] | Active, Linux Foundation project | n/a | Validate exporter output against the JSON schema in CI | S |
| rlottie | github.com/Samsung/rlottie | MIT core, with FreeType/pixman/stb/rapidjson parts under their own licences [V]. `rlottie-python` is **LGPL** [R] | Slow maintenance | Yes | Second Lottie renderer if ThorVG falls short. ThorVG is preferred | S |
| **Synfig skeleton features** (already a dependency) | synfig.org; github.com/synfig/synfig | **GPL-3.0** [V] COPYLEFT; fine because it runs as a CLI subprocess | Active (1.5 dev) | Yes, via the CLI | Upgrade the `.sif` exporter. Use the **Skeleton** and **Skeleton Deformation** layers (bone-weighted mesh bending) for soft limbs instead of rigid parts, and the **Switch** layer for swap sets | M |
| Glaxnimate | gitlab.com/mattbas/glaxnimate (now under KDE) | **GPL-3.0-or-later** [V] COPYLEFT | Active (KDE) | Desktop app; has a CLI converter [U] | Hand-off tool so a person can edit our Lottie exports. Converts Lottie, SVG, Rive and others | S |
| python-lottie | gitlab.com/mattbas/python-lottie | **AGPL-3.0-or-later** [V] AGPL | v0.7.2 (2025-05) [R] | Yes | **Do not import into the service.** Offline CLI use only, if at all | — |
| DragonBones | github.com/DragonBones/DragonBonesJS | MIT runtime [V] | Runtime maintained lightly; the editor is discontinued | Yes, in JS | Optional export target (documented JSON) for Phaser, Cocos or Egret clients. Low priority | M |
| Spine runtimes | github.com/EsotericSoftware/spine-runtimes | **Proprietary "Spine Runtimes License"**: "each user of the Products must obtain their own Spine Editor license" [V]. **Not open source** | Very active | Yes | Only as an export target for clients who own Spine. Do not embed the runtime | M |
| Rive | github.com/rive-app/rive-runtime, rive-wasm | Runtimes MIT [V]; **the editor is proprietary SaaS** | Very active | Yes (wasm in Chromium, or C++) | `.riv` files are binary and editor-authored, so generating them is hard. Skip unless clients ask | L |
| Inochi2D | github.com/Inochi2D/inochi2d | BSD-2-Clause [V] | Active (copyright through 2026) | Headless rendering unclear [U]; written in D | Open alternative to Live2D (mesh-deformed puppets driven by parameters). Possible future "2.5D puppet" export. Large effort | L |
| OpenToonz / Tahoma2D | github.com/opentoonz/opentoonz, github.com/tahoma2d/tahoma2d | BSD-3-Clause, with third-party parts under their own licences [V] | Active | `tcomposer` render CLI exists [V: built from 1.8.0 here, renders headless under Xvfb]; needs Qt | `.tnz` scene export for studios: `export.opentoonz` (WP-34), checked by tcomposer itself | L |
| Moho format | lostmarble.com | Proprietary app | — | — | If needed, emit Papagayo/Moho `.dat` switch files from our viseme track (trivial) | S |

---

## 3. Animation maths and procedural acting

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **FABRIK, written in-house** (references: fullik, THREE.IK) | github.com/lo-th/fullik, github.com/jsantell/THREE.IK | Both MIT [V]. Both dormant (about 2018) | Reference code | Yes | Extend the acting layer from two-bone IK to N-bone chains (tails, tentacles, spines, ropes, three-segment arms) with joint limits. About 150 lines; port it rather than add a dependency | S |
| three.js CCDIKSolver | three.js addons (already r160) | MIT | Ships with three.js | Yes | Use for 3D N-bone IK (reaching, look-at chains) on the CC0 characters | S |
| ikpy | github.com/Phylliade/ikpy | Apache-2.0 [V] | v4.3.0 (2026-10) [R] | Yes | Python-side IK if solving happens server-side. Oriented to URDF robots, so FABRIK is a better fit for 2D | S |
| wobble | github.com/skevy/wobble | MIT [V] | Small and stable | Yes | Closed-form damped spring (deterministic, so it fits "frame = f(n)"). Compare against our springs | S |
| three-vrm SpringBone | github.com/pixiv/three-vrm | MIT [V] | Active (2026) | Yes | Secondary motion (hair, tails, cloth strips) on the 3D characters. The algorithm also ports to 2D bone chains | M |
| opensimplex | pypi.org/project/opensimplex | MIT [R] | v0.4.5 (2024) | Yes | Seeded idle noise (breathing, sway, handheld camera) that stays deterministic per frame | S |
| **MediaPipe Pose / Holistic / Face Landmarker** | github.com/google-ai-edge/mediapipe | Apache-2.0 [V]; models Apache-2.0 [U] | Very active (v1.2.0, 2026-10) [R] | Yes, real time on CPU | **"Act it out"**: video in, 33 body points plus hands plus face blendshapes out. Map body points to puppet joint angles and IK targets (foot pins and hands), and blendshapes to mouth and eye swaps. Save the result as an action clip on the nonlinear stack | M |
| **RTMPose / DWPose via rtmlib** | github.com/Tau-J/rtmlib | Apache-2.0 [V]. Underlying MMPose [V] and DWPose [V] are Apache-2.0 | v0.0.16 (2026-08) [R] | Yes (onnxruntime; no mmcv) | Higher-accuracy whole-body (133 keypoints) alternative to MediaPipe for the same pipeline. Measured (`pose.benchmark`, 80 COCO val2017 photos, body model): mean OKS 0.944 against MediaPipe's 0.836, 284 ms against 40 ms per image; its whole-body model has the feet and hands act-out needs (not yet tried) | M |
| **Meta Animated Drawings** | github.com/facebookresearch/AnimatedDrawings | MIT [V] | Research release (2023). Activity since then [U] | Retargeting runs on CPU. Detection uses TorchServe models; rendering uses OpenGL (OSMesa for headless) [U] | (a) Auto-rig from a single drawing: mask, skeleton guess, ARAP mesh. This could seed puppets in Rig Canvas. (b) Its **BVH-to-2D retarget configs** show how to drive 2D puppets from the CMU mocap we already have | M–L |
| Motion-Matching (Daniel Holden) | github.com/orangeduck/Motion-Matching | MIT code [V]; the bundled **LAFAN1 data is CC BY-NC-ND 4.0** [V] NC | Reference implementation | Yes | Locomotion for 3D characters built from a CMU-derived database (not LAFAN1). Optional | L |
| Text-to-motion: MDM, MoMask, T2M-GPT | github.com/GuyTevet/motion-diffusion-model, EricGuo5513/momask-codes, Mael-zys/T2M-GPT | Code MIT / MIT / Apache-2.0 [V]. **Trained on HumanML3D (AMASS) with SMPL**, both non-commercial research licences [U for AMASS; SMPL-X confirmed NC [V]], so the weights are effectively NC | Research | Slow on CPU | Research only; do not ship | — |
| Co-speech gesture: EMAGE / PantoMatrix | github.com/PantoMatrix/PantoMatrix | **Code licence not found** (no LICENSE visible) [R]. BEAT2 data is **CC BY-NC 4.0** per the README [R]. SMPL-X is NC [V] | Active research (news dated 2026-09) | GPU-oriented | Avoid for production | — |
| DiffuseStyleGesture | github.com/YoungSeng/DiffuseStyleGesture | MIT code [V]; trained on ZEGGS (Ubisoft) data, licence [U], likely NC | Research | GPU-oriented | Avoid the weights | — |
| Gesticulator | github.com/Svito-zar/gesticulator | **GPL-3.0** [V] | Dormant | — | — | — |
| audio2photoreal | github.com/facebookresearch/audio2photoreal | **CC BY-NC 4.0** [V] NC | — | GPU | Avoid | — |
| OpenPose | github.com/CMU-Perceptual-Computing-Lab/openpose | **Academic or non-profit, non-commercial only** [V] NC | — | — | Avoid; use MediaPipe or rtmlib | — |
| Ultralytics YOLO-pose | github.com/ultralytics/ultralytics | **AGPL-3.0** [V] AGPL | 8.4.202 [V] | Yes (torch CPU) | In-house only (AGPL allowed for R&D since 2 Nov 2026). Measured (`pose.benchmark`): YOLO11m-pose mean OKS 0.919, 245 ms per image | — |
| Sapiens (Meta) | github.com/facebookresearch/sapiens | **CC BY-NC 4.0** [V] NC | — | — | Avoid | — |

**Recommendation for gestures.** Every open co-speech model I found has NC or unclear terms in its code, data or body model. Build a **prosody-driven beat-gesture scheduler** instead, with no new dependencies:
- **Beat gestures:** pick out F0 peaks (from pyworld, already in the stack) and stressed words (Whisper words with espeak stress marks).
- **Semantic gestures:** have an LLM tag the script (pointing, size, negation, enumeration).
- **Output:** schedule clips from our own action-clip library on the nonlinear stack. Effort S–M.

---

## 4. Vector drawing and cleanup

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **perfect-freehand** | github.com/steveruizok/perfect-freehand | MIT [V] | v1.2.3 (2026-02) [R]; used in tldraw | Yes, pure JS (Python ports exist [U]) | Rig Canvas: pressure-like variable-width strokes turned into outline paths, so hand-drawn parts look inked. Also server-side stroke "re-inking" | S |
| simplify-js | github.com/mourner/simplify-js | BSD-2-Clause [V] | Stable (2020) | Yes | Ramer–Douglas–Peucker plus radial simplification before curve fitting, for smaller parts files | S |
| **vpype** | github.com/abey79/vpype | MIT [R] | v1.15.0 (2025-08) [R] | Yes, Python CLI and library | Server-side line cleanup: merge, simplify, line-sort, de-duplicate and filter short segments for imported line art | S |
| **VTracer** | github.com/visioncortex/vtracer | MIT [V] (`vtracer` on PyPI v0.6.15, 2026-03 [R]) | Active | Yes (Rust with Python wheels) | **Colour** sketch or scan import: turns a bitmap into layered SVG parts for the puppet loader. A permissive alternative to potrace | S |
| potrace | potrace.sourceforge.net (`apt install potrace`, 1.16) | **GPL-2.0** [V via tatarize/potrace and kilobtye/potrace copies] COPYLEFT | Mature, stable | Yes | Best monochrome tracing quality. Used as a CLI subprocess (vendored 1.16, built by `vendor.build`): traces handwriting samples into font outlines (`font.from_samples`, WP-29) | S |
| fontTools | github.com/fonttools/fonttools | MIT [V] | 4.68 | Yes | FontBuilder makes the handwriting fonts (CFF outlines from potrace's paths via its SVG path parser), WP-29 | S |
| autotrace | github.com/autotrace/autotrace | **GPL-2.0** [V] COPYLEFT | Low activity; **not in Ubuntu noble apt** (checked) | Yes | **Centerline** tracing (strokes rather than fills), the mode Inkscape uses. Use only if centerline output matters | M (build from source) |
| ImageTracer.js | github.com/jankovicsandras/imagetracerjs | Unlicense (public domain) [V] | Dormant (2020) | Yes | In-browser tracing in Rig Canvas with no copyleft | S |
| **Clipper2** (pyclipr bindings) | github.com/AngusJohnson/Clipper2; pypi `pyclipr` | Boost Software License 1.0 [V]; pyclipr BSL-1.0 [R] | Clipper2 active; pyclipr v0.1.8 (2026-02) | Yes | Polygon boolean and offset: cel-shading shadow and rim shapes (offset, then intersect with the body), outline thickening, and part trimming. `pyclipper` (MIT, Clipper1) is the older alternative | S |
| skia-pathops | github.com/fonttools/skia-pathops | BSD-3-Clause [V] | v0.9.2 (2026-02) | Yes | Boolean operations on **curves** (keeps Béziers, unlike Clipper, which flattens). Use for clean union and difference of SVG parts | S |
| paper.js | github.com/paperjs/paper.js | MIT [V] | v0.16.0 (2026-10) [R] | Yes, in a browser (or Node with jsdom [U]) | Curve booleans, offsets and hit-testing inside Rig Canvas | S |
| shapely | pypi.org/project/shapely | BSD-3-Clause [R] (GEOS is LGPL, dynamically linked) | v2.2.0 (2026-10) | Yes | Robust polygon operations, buffer, skeleton helpers; Python side | S |
| svgpathtools | github.com/mathandy/svgpathtools | MIT [V] | v1.8.0 (2026-09) [R] | Yes | Path maths in Python: arc length, normals, intersections. Useful for brush placement along paths and caption paths | S |
| **svgo** | github.com/svg/svgo | MIT [V] | v4.1.0 (2026-08) [R] | Yes (Node) | Optimise puppet part files and exported SVGs. Run a "safe" preset that keeps IDs, since pivots and swap-set IDs matter | S |
| scour / picosvg | github.com/scour-project/scour, github.com/googlefonts/picosvg | Both Apache-2.0 [V] | scour dormant (2020); picosvg active (2026-08) | Yes | picosvg flattens SVG to plain paths with no transforms, uses or strokes. Good for normalising imported parts before rigging | S |
| scikit-image `skeletonize`, skan, sknw | scikit-image.org; github.com/jni/skan; github.com/yxdragon/sknw | BSD-3-Clause, all three [V] | Active / active / 2023 | Yes | Skeletonise a drawn silhouette, then turn the skeleton into a bone-graph guess (auto-rig seed, together with Animated Drawings) | M |
| Inkscape CLI (actions) | inkscape.org (`apt` has 1.2.2) | **GPL-2.0-or-later** COPYLEFT; fine as a subprocess | Mature | Yes (`--actions`, `--export-*`) | Batch operations: text-to-path, stroke-to-path, boolean operations, PDF/EPS/EMF import and export, plus raster fallback | S |

---

## 5. Rendering speed

### Measured baseline (this container, 4 CPUs, no GPU)

- **Scene:** a synthetic 1920×1080 frame with 800 stroked or filled cubic paths, a gradient background and one text line. Variant "b" adds a Gaussian-blur filter to 20 paths.
- **Method:** 60 frames per run.
  - Chrome: `google-chrome --headless=new`, driven over CDP from Node. Each frame sets `body.innerHTML` and then calls `Page.captureScreenshot`, which mirrors a Playwright loop.
  - librsvg: the SVG decoder in the local ffmpeg 6.1 build.
- **Harness:** `/tmp/claude-0/-home-user-chalklore-infra/1e07a64a-ba11-5ff4-ad45-442a8e19b6a1/scratchpad/bench/` (`gen.py`, `cdp.mjs`).

| Renderer path | ms per frame |
|---|---|
| Chrome CDP screenshot, PNG, 1 process | **234** (blur variant: 219) |
| Chrome CDP screenshot, JPEG q90, 1 process | **166** (1.4× faster; lossy, so banding on flat cels) |
| Chrome PNG, **4 processes in parallel** (aggregate throughput) | **109** (2.1× throughput) |
| librsvg via ffmpeg, decode and raster, 1 process | 479 (blur variant: 872), about 2× *slower* than Chrome |
| librsvg, 4 processes in parallel (aggregate) | 155 |

**Conclusions**
- Swapping Chromium for librsvg or CairoSVG would make things slower.
- I could not benchmark resvg, ThorVG or skia-python without installing them, so their gains are unproven here. Their published benchmarks and architecture suggest they beat librsvg; whether they beat warm Chromium by 5× on heavy frames needs measuring with the harness above.
- Getting 5–10× overall more realistically comes from stacking several gains:
  - process parallelism: 2× measured;
  - a lighter screenshot path: about 1.4×;
  - **frame dedupe**: about 2× on scenes animated on twos or holds, because frame n is a pure function, so hash the SVG string and reuse the raster;
  - **static-layer caching**: render backgrounds and held layers once and composite only moving puppet layers, with a gain that depends on the scene.

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **Frame dedupe and layer cache** (in-house) | — | — | — | Yes | (1) Before rendering, take an SHA-1 of each frame's SVG string and reuse the raster for repeats. (2) Split each frame into a static background SVG plus a dynamic layer SVG with a transparent background. Composite with numpy or ffmpeg `overlay`. (3) Run a worker pool of N Chromium pages or processes, one per CPU | S–M |
| **resvg** | github.com/linebender/resvg | **Apache-2.0 OR MIT** [V] | Very active (Linebender) | Yes (Rust CLI and library; no Chromium) | Alternative rasteriser for frames that use only static SVG features: no CSS animation, JS or `foreignObject`, and fonts must be loaded explicitly. A per-film switch `renderer=resvg|chromium`, with a pixel-diff check against Chromium | S–M |
| resvg-py (two bindings) | github.com/baseplate-admin/resvg-py (`resvg-py` v0.5.0, 2026-08); github.com/briceyan/resvg-py (`resvg` v0.2.0, 2026-04) | Both MIT [V] | Small projects; vet before use | Yes | In-process Python rendering, from SVG string to PNG bytes or a buffer | S |
| @resvg/resvg-js | github.com/yisibl/resvg-js | **MPL-2.0** [V] (weak file-level copyleft) | Last release 2024-03 [R], so stale | Yes | Not preferred; use the Rust CLI or Python bindings | — |
| tiny-skia | github.com/RazrFalcon/tiny-skia (now under linebender) | BSD-3-Clause [V] | Active | Yes | resvg's rasteriser. Use directly only if we write our own path emitter | — |
| **ThorVG** | github.com/thorvg/thorvg | MIT [V] | Very active; CPU SIMD | Yes | Benchmark it as an SVG rasteriser alongside resvg. It also handles Lottie (see section 2) | S–M |
| skia-python | github.com/kyamagu/skia-python | BSD-3-Clause [V] | v144.1 (2026-10) [R], tracks Skia | Yes | Skia CPU raster, with an SVG DOM module [U] and a canvas API. Same engine as Chrome without the browser overhead. A candidate for in-process rendering | M |
| Blend2D | github.com/blend2d/blend2d | Zlib [V] | Active | Yes (JIT CPU rasteriser) | Very fast, but has **no SVG parser**, so we would emit draw calls from our own scene graph. Only worth it if we move off SVG strings | L |
| Vello / vello_cpu | github.com/linebender/vello | Apache-2.0 / MIT [V] | Active; the GPU path is primary, the CPU path is newer [U] | Partly | Watch list | — |
| skia-canvas / @napi-rs/canvas | npmjs.com/package/skia-canvas, @napi-rs/canvas | MIT [R] | Active (2026-10) | Yes (Node) | Canvas-2D API backed by Skia in Node, if any frames are built with Canvas instead of SVG | M |
| headless-gl (`gl`) | npmjs.com/package/gl | BSD-2-Clause [R] | v8.1.6 (2024-10) | Yes (Mesa/ANGLE) | WebGL 1 only; can't run three.js r160, which needs WebGL 2. Keep Chromium with SwiftShader for 3D | — |
| librsvg, CairoSVG, pycairo | gnome.org; github.com/Kozea/CairoSVG | librsvg LGPL-2.1+; **CairoSVG LGPL-3.0** [V]; pycairo LGPL-2.1 or MPL-1.1 [R] | Mature | Yes | Measured slower than Chromium (librsvg). Not recommended for speed | — |
| **PyAV** | github.com/PyAV-Org/PyAV | BSD-3-Clause [V] | v19.0.2 (2026-10) [R] | Yes | Pipe raw RGBA frames from the renderer straight into libx264 or SVT-AV1. Avoids writing PNGs to disk and re-decoding them | S |
| Encoder tweaks (ffmpeg) | ffmpeg.org | The local build is configured `--enable-gpl` (GPL build) | — | Yes | `libx264 -tune animation` (fits flat cels), `-preset veryfast` for previews and `slow` for finals. Encode in parallel by chunk. **SVT-AV1** is present in the local ffmpeg; its `film-grain` parameter synthesises grain at decode time, so grain costs no extra bits | S |
| Chrome-side tweaks | chromedevtools.github.io | — | — | Yes | Use `chrome-headless-shell` (lighter), set `optimizeForSpeed: true`, prefer JPEG or WebP for previews, and reuse one page per worker (no navigation per frame). Clip screenshots to the dirty rectangle for layer renders | S |

---

## 6. Compositing and effects

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **ffmpeg filter graphs** (already present) | ffmpeg.org/ffmpeg-filters.html | LGPL/GPL; the local build is GPL | Mature | Yes. Confirmed locally: `noise`, `tmix`, `gblur`, `lut3d`, `vignette`, `chromashift`, `curves`, `xfade`, `geq`, `minterpolate`, `frei0r` | A `post` command with presets:<br>• film grain: `noise=alls=6:allf=t`<br>• "paper": overlay a CC0 paper texture with blend=multiply<br>• grading: `lut3d` with a .cube LUT<br>• vignette<br>• chromatic aberration: `chromashift`<br>• transitions: `xfade` | S |
| **Accumulation motion blur** (in-house) | — | — | — | Yes | Frames are pure functions of time, so render k sub-frames at n + i/k and average them (numpy or `tmix`). Cost is k×, so use it only on fast-action shots. A cheaper option is per-part directional `feGaussianBlur` scaled by velocity | S |
| OpenImageIO `oiiotool` | github.com/AcademySoftwareFoundation/OpenImageIO (`apt openimageio-tools` 2.4) | Apache-2.0 [V] | Very active (ASWF) | Yes | Per-frame CLI compositing: over, blur, colour conversion with OCIO, resize, EXR. Useful for 3D passes (three.js or Blender), for example a toon pass composited over a line pass | S |
| frei0r plugins | github.com/dyne/frei0r | **GPL-2.0** [V] COPYLEFT; loaded by ffmpeg at run time | Maintained | Yes (`apt frei0r-plugins` [U]) | Extra effects: cartoon, edge glow, distortions, through ffmpeg's `frei0r` filter | S |
| three.js toon stack | three.js r160 `MeshToonMaterial`, `OutlineEffect`; github.com/pmndrs/postprocessing | three.js MIT; pmndrs/postprocessing Zlib [U] | Active | Yes (SwiftShader) | Gradient-map toon ramps, inverted-hull or edge outlines, SMAA, so 3D characters match the 2D cel look | S–M |
| Blender compositor (already a dependency) | blender.org | GPL (subprocess) | Active | Yes | Already available. Use it for Grease Pencil and 3D passes rather than adding Natron | — |
| Gaffer | github.com/GafferHQ/gaffer | BSD-3-Clause [V] | Active (VFX) | Yes (`gaffer execute`) | Node-based compositor with a permissive licence. Heavy (VFX scale); only worth it if we need reusable node graphs authored by people | L |
| Natron | github.com/NatronGitHub/Natron | **GPL-2.0** [V] COPYLEFT | Low activity | Yes (`NatronRenderer`) [U] | Not recommended: heavy and slow-moving. ffmpeg plus oiiotool covers our needs | — |
| OpenFX | github.com/AcademySoftwareFoundation/openfx | BSD-3-Clause API [V]; plugins vary (openfx-misc is GPL-2.0 [U]) | Active (ASWF) | n/a | Only relevant if we adopt Natron or Gaffer | — |

---

## 7. Assets with clear licences

A note on supply: Doodleberry should keep an **asset licence manifest** (source URL, licence and attribution string per file) and generate end credits and a CREDITS file from it. CC BY assets then become safe to use.

| Asset | Link | Licence (exact) | Notes | Integration point | Effort |
|---|---|---|---|---|---|
| **Open Peeps** (Pablo Stanley) | openpeeps.com | **CC0** [V, site] | SVG mix-and-match bodies, faces, hair and poses | Convert to puppet JSON (parts plus swap sets): instant cast variety | M |
| **Humaaans** (Pablo Stanley) | humaaans.com | **CC0** [V, site] | Mix-and-match SVG people | Same as Open Peeps | M |
| **Kenney** (2D, UI, audio) | kenney.nl | **CC0** for all asset-page assets [V, support page]. Check per-pack licence files for audio | Large and consistent packs | Backgrounds and props; UI sounds and impact SFX | S |
| Tabler Icons | github.com/tabler/tabler-icons | MIT [V] | About 5,900 stroke icons; v3.50 (2026-10) | Explainer pictograms; stroke style fits chalk and line | S |
| Lucide | github.com/lucide-icons/lucide | ISC [V] | Active (2026-10) | Same use as Tabler | S |
| Phosphor | github.com/phosphor-icons/core | MIT [V] | Six weights, including duotone | Same use as Tabler | S |
| Iconoir / Heroicons / Material Symbols / Fluent UI icons | npm | MIT / MIT / Apache-2.0 / MIT [R] | — | More icon styles | S |
| Fluent Emoji (Microsoft) | github.com/microsoft/fluentui-emoji | MIT [V] | Flat, high-contrast and 3D styles | Reaction emoji for characters | S |
| Noto Emoji | github.com/googlefonts/noto-emoji | Images **Apache-2.0**; font **OFL-1.1** [V] | — | Emoji in captions | S |
| Twemoji (jdecked fork) | github.com/jdecked/twemoji | Code MIT; **graphics CC BY 4.0** [V] | Attribution required | Use with the manifest | S |
| OpenMoji | github.com/hfg-gmuend/openmoji | **CC BY-SA 4.0** [V] SA | Share-alike may apply to derived artwork | Avoid unless you accept share-alike | — |
| Google Fonts (OFL families) | github.com/google/fonts | **SIL OFL 1.1** for most families [U per family; check each METADATA.pb] | For example Atkinson Hyperlegible, Patrick Hand, Comic Neue, Fredoka, Andika | Caption and kinetic-type fonts; embed and subset freely (OFL allows that; selling a font on its own is not allowed) | S |
| Freesound | freesound.org | **Per sound**: CC0, CC BY or **CC BY-NC** [U] | Filter by CC0 through the API | SFX search command with a licence filter | S–M |
| Sonniss GDC bundles | sonniss.com/gameaudiogdc | Royalty-free, commercial use OK, **no attribution required**, **no redistribution as sound effects**, **AI/ML training prohibited** [V, page] | Several GB per year | Fine for final mixes. Don't put the raw files in a public repo or dataset | S |
| BBC Sound Effects | sound-effects.bbcrewind.co.uk | **RemArc licence: personal, educational or research use only** [U; page not reachable from the container] NC | — | Avoid for commercial output | — |
| Pixabay audio / music | pixabay.com | Pixabay Content License (not CC0; standalone redistribution banned) [U] | Some tracks trigger Content-ID claims [U] | Use with care | — |
| Kevin MacLeod (incompetech) | incompetech.com | **CC BY 4.0** [U] | Attribution required | Music beds via the manifest | S |
| OpenGameArt | opengameart.org | Mixed per asset (CC0, CC BY, CC BY-SA, GPL) [U] | Filter by CC0 | Music and SFX | S |
| **Servier Medical Art** | smart.servier.com | **CC BY 4.0** [V, site] | Thousands of medical and biology vector illustrations | Medical explainer films (screwworm, anatomy); credit via the manifest | S |
| BodyParts3D | lifesciencedb.jp/bp3d | **CC BY-SA 2.1 Japan** per Z-Anatomy's attribution and Wikipedia [R]. One source claims CC BY 4.0 for v4.0 [R], so check the DBCLS site | 3D anatomy meshes | 3D anatomy shots. Note share-alike on derivatives | M |
| Z-Anatomy | github.com/Z-Anatomy | **CC BY-SA 4.0** [R]. **Some bundled parts are CC BY-NC-SA** (for example the inner ear) [R] SA NC | Blender atlas | Use per-mesh with care; check each component | M |
| Gray's Anatomy (1918) plates | Wikimedia Commons | Public domain (age) [U] | Line plates, good for chalk restyling | Vectorise with VTracer or potrace and use as reference layers | S |
| **Natural Earth** | naturalearthdata.com; github.com/nvkelso/natural-earth-vector | **Public domain** [V] | Vector and raster maps at 1:10m, 1:50m and 1:110m | Map shots: project to SVG with d3-geo (ISC [V]: 3.1.1's package.json and LICENSE) from `world-atlas` TopoJSON (ISC [V]). **Used:** the map board (WP-16, `set: "map"`, tools/mapboard/) | S |
| OpenStreetMap | openstreetmap.org | **ODbL** (attribution plus share-alike on the database) [U] | — | Local maps only, with attribution | — |

---

## 8. Agent and automation glue

| Name | Link | Licence | Maturity / activity | Headless CPU | Integration point | Effort |
|---|---|---|---|---|---|---|
| **OpenTimelineIO** | github.com/AcademySoftwareFoundation/OpenTimelineIO | Apache-2.0 [V] | v0.18.1 (2025-11) [R]; ASWF | Yes | `export.otio`: write each film's shot list, caption track and audio stems (VO, music, SFX) as an `.otio` timeline. Adapters: `otio-cmx3600-adapter` (EDL) and `otio-fcpx-xml-adapter`, both Apache-2.0 [R], plus FCP7 XML and AAF adapters [U]. Editors can then finish in Resolve, Premiere or Kdenlive. It also serves as an internal edit-decision representation | S–M |
| MLT / `melt` | github.com/mltframework/mlt (`apt melt` 7.22) | Framework **LGPL-2.1** [V]; some modules GPL [U] | Very active (Shotcut and Kdenlive engine) | Yes (`melt ... -consumer avformat:out.mp4`) | Timeline assembly with transitions and audio mixing from an XML playlist. Use it to render Kdenlive or Shotcut projects that people edit, closing the round trip | M |
| Inkscape CLI actions | inkscape.org | GPL-2.0-or-later (subprocess) | Mature | Yes | See section 4. Expose as `svg.inkscape` commands in the registry | S |
| inkscape-mcp | pypi.org/project/inkscape-mcp | MIT [R] | v1.3.1 (2026-08), third-party | Yes | Treat as reference code only. Wrap the Inkscape CLI in our own registry so the CLI, HTTP and MCP stay consistent | S |
| blender-mcp | github.com/ahujasid/blender-mcp | MIT [V] | v2.0.0 on PyPI (2026-09) [R]; popular | Designed for a GUI add-on with a socket [U] | Reference for tool shapes (scene introspection, run Python). Our headless Blender scripts already work, so the value is low | — |
| ffmpeg MCP servers | e.g. npm `ffmpeg-mcp` | Often **no licence** (npm `ffmpeg-mcp` v0.0.3 has none) [R] | Immature | Yes | Don't adopt; our registry already wraps ffmpeg | — |
| Motion Canvas | github.com/motion-canvas/motion-canvas | MIT [V] | v3.17.2 (2024-12) [R], so the pace has slowed | Yes (browser) | Reference: its generator-based scene API, signals and timeline-synced audio are good ideas for a scene DSL that agents can write | — (reference) |
| Revideo | github.com/redotvideo/revideo | MIT [V] (Motion Canvas fork) | v0.11.0 (2026-07) [R] | Yes, headless render API | Reference for a headless parallel-render server and audio handling. Closest in spirit to Doodleberry | — (reference) |
| Remotion | github.com/remotion-dev/remotion | **SRC-AVAIL "Remotion License"**: free for individuals, for-profit organisations with up to 3 employees, and non-profits. **A company licence is required otherwise.** Reselling derivatives is banned [V] | Very active (v4.0.539, 2026-10) | Yes | Reference only. Don't embed, given the licence | — |
| Manim CE | github.com/ManimCommunity/manim | MIT [V] | Active | Yes | Reference for maths and diagram explainers. Could become a sub-renderer for equation shots | M |
| MoviePy / editly | github.com/Zulko/moviepy (v2.2.1 [R]); github.com/mifi/editly | MIT [R] / MIT [V] | MoviePy active; editly dormant (2022) | Yes | Not needed; ffmpeg plus OTIO plus MLT cover this | — |

---

## Recommended integration plan (ranked top 10)

| # | Pick | Why | Licence | Effort |
|---|---|---|---|---|
| 1 | **Re-cast to clean-licence voices and add Kokoro-82M** as a second TTS backend (kokoro or kokoro-onnx), with a `licence` field in the voice registry and a refusal gate for NC or unclear voices | Every voice in use today is NC, research-only, "All Rights Reserved" or inherits lessac (section 0). Kokoro adds about 50 voices in 8 languages under Apache-2.0, runs faster than real time on CPU, and exposes phonemes for lip-sync | Piper public-domain voices; Kokoro Apache-2.0 (espeak fallback is GPL, as a subprocess) | S–M |
| 2 | **Phone-level forced alignment**: MFA (MIT, CC BY 4.0 English model) as the accurate path, *or* wav2vec2-espeak CTC (Apache-2.0) with torchaudio `forced_align` as the in-process, multilingual path | Real phone boundaries instead of spreading espeak phonemes across Whisper word spans, giving tighter visemes. The wav2vec2 variant uses the same espeak phone set as the existing viseme table | MIT / Apache-2.0 | M |
| 3 | **Rhubarb Lip Sync** as a QA cross-check and transcript-free fallback | Mature, MIT, one CLI call. A–H,X cues map straight to mouth swap sets. Diffing it against our track catches lip-sync regressions automatically | MIT | S |
| 4 | **Render throughput package**: a Chromium worker pool (1 per CPU), frame-hash dedupe, static-layer caching, PyAV raw piping, and `-tune animation` | Measured here: 2.1× from parallelism and 1.4× from a lighter capture format. Dedupe gives about 2× on cut-out animation shot on twos. Together these plausibly reach 4–8× without changing the renderer | In-house; PyAV BSD-3 | S–M |
| 5 | **Benchmark resvg and ThorVG as alternative rasterisers** (per-film switch plus pixel-diff gate), and use **ThorVG and lottie-web as Lottie exporter QA** | librsvg was measured 2× slower than Chromium, so do not assume native code is faster: measure with the saved harness. ThorVG also gives an independent check that the Lottie exports render correctly | Apache-2.0 / MIT; ThorVG MIT; lottie-web MIT | S–M |
| 6 | **"Act it out": MediaPipe Pose/Holistic (or rtmlib RTMPose)** to turn video into keypoints, then puppet joint angles, IK targets and an action clip | Lets a person or an agent supply reference acting in seconds. CPU real time, Apache-2.0. Face blendshapes also drive eye and mouth swaps | Apache-2.0 | M |
| 7 | **N-bone FABRIK plus a prosody-driven beat-gesture scheduler** (in-house) | Opens up tails, tentacles and spines, and gives automatic co-speech gesture without NC models. Every open gesture model checked has NC data, an NC body model or no code licence | In-house (references MIT) | S–M |
| 8 | **Drawing ingest and cleanup**: perfect-freehand in Rig Canvas, VTracer (colour) and potrace (mono, subprocess) for scans, Clipper2 or skia-pathops for cel-shadow booleans and offsets, picosvg and svgo for normalising parts. Optionally borrow **Animated Drawings'** auto-rig ideas | Better strokes, fast import of hand-drawn or scanned art into puppet parts, and robust shading geometry | MIT, BSL-1.0, BSD-3, Apache-2.0 (potrace GPL as a subprocess) | M |
| 9 | **OpenTimelineIO export** (plus `melt` for round trips) | Hands each film to human editors as EDL, FCPXML or Kdenlive timelines with stems and captions. A clean edit-decision model for agents too | Apache-2.0; MLT LGPL-2.1 | S–M |
| 10 | **Curated asset library with a licence manifest**: Open Peeps and Humaaans (CC0) converted to puppets, Tabler, Lucide and Phosphor icons, Kenney CC0 audio and props, Servier Medical Art (CC BY 4.0), Natural Earth (PD), and OFL fonts, with credits generated automatically | Instant cast and prop variety for explainers, with attribution handled mechanically. Avoids the traps found here: OpenMoji SA, BBC NC, Sonniss AI-training ban, and Z-Anatomy NC parts | CC0, MIT, ISC, CC BY 4.0, PD, OFL | S–M |

**Also worth doing, outside the top 10:**
- Synfig Skeleton Deformation and Switch layers in the `.sif` exporter (M).
- dotLottie packaging with palette slots mapped to themes (S–M). Done in WP-23: `lottie.dotlottie`, checked in @lottiefiles/dotlottie-web 0.82.1 (MIT, ThorVG in WebAssembly), which also serves as the ThorVG check of our Lottie.
- An ffmpeg `post` preset command: grain, LUT, vignette, accumulation motion blur (S).
- oiiotool for 3D pass compositing (S).

**Explicitly avoid:**
- OpenPose (NC).
- Ultralytics (AGPL).
- python-lottie, if imported into the service (AGPL).
- aeneas (AGPL).
- XTTS-v2 and F5-TTS weights (NC).
- MMS aligner weights (NC).
- EMAGE, audio2photoreal, MakeItTalk, Sapiens and LAFAN1 data (NC or unclear).
- Embedding Spine runtimes (per-user editor licence).
- Embedding Remotion (company licence).

## Things I could not verify (treat as open)

- **GitHub access:**
  - The GitHub API is blocked from this container, so stars and last-commit dates come from PyPI, npm and HF registry dates, not GitHub.
  - Licence files for PantoMatrix/EMAGE, Papagayo-NG (licence came from search), MoviePy, node-canvas and headless-gl could not be fetched from raw.githubusercontent.com.
- **Licence questions:**
  - BodyParts3D: CC BY-SA 2.1 JP versus CC BY 4.0. Check the DBCLS site.
  - The exact terms of the BBC RemArc licence, the Pixabay licence and incompetech.
  - `thorvg-python` reports LGPL in PyPI metadata, while ThorVG itself is MIT. Read the binding's repo.
  - Whether sherpa-onnx compiles in GPL espeak-ng code.
  - The StyleTTS2 weight-usage wording.
- **Features and speed:**
  - The Kokoro per-token timestamp feature.
  - Headless operation of tcomposer (OpenToonz), the Glaxnimate CLI and Animated Drawings rendering.
  - resvg, ThorVG and skia-python speed on our frames (not installed, per instructions).

## 9. Addendum: procedural, physics and ecosystem tools (November 2026)

Checked for the procedural brainstorm (`docs/brainstorm/procedural-houdini.md`, which has the full table and the CPU
probe results). Only the tools now named in `docs/build-plan.md` are listed here. Tags as above.

| Tool | Licence | Plan item | Notes |
|---|---|---|---|
| Rapier 2D, deterministic JS build (`@dimforge/rapier2d-deterministic-compat` 0.21.0) | Apache-2.0 [R] | 2.19 | not MIT; keep the NOTICE; measured bit-identical reruns in Node |
| manifold3d 3.5.4 | Apache-2.0 [R] | 1.7 | 2D `CrossSection` offsets as an alternative to pyclipr |
| SAM 2 / 2.1 checkpoints | Apache-2.0 [R] | 1.8b | the SA-V dataset has separate terms; CPU is slow, so suggestions only. In use (WP-18): the tiny model's ONNX export (onnx-community), 4 s to encode a doodle photo on 4 CPUs, 0.3 to 0.5 s a tap |
| Poly Haven, ambientCG | CC0 [R] | 1.6 | record each file in the manifest |
| Depth Anything V2 **Small** | Apache-2.0 [R] | 1.6 | in use (WP-43, `depth.planes`, ONNX on CPU). Base, Large and Giant are CC-BY-NC-4.0: **NC**; Base is wired as an option whose outputs the posting gate flags |
| RIFE 4.9 (Practical-RIFE), ONNX conversion | MIT (upstream; the conversion has no card) [R] | WP-43 | in use: `level.inbetween` proposes in-betweens for drawn levels; 92% accepted on held-out drawings against 58% for holds |
| music21 10.5.2 | BSD-3 [R] | 2.14 | |
| FluidSynth | LGPL-2.1 [R] | 2.14 | **COPYLEFT**: run as a separate process |
| GeneralUser GS 2.0.1 | permissive [R] | 2.14 | sample provenance not guaranteed by its author: review before published films |
| Tone.js 15.1 | MIT [R] | 2.14 | |
| React Flow (`@xyflow/react` 12.12) | MIT [R] | 3.10 | |
| OpenRV | Apache-2.0 [R] | 3.4 | licensed codecs excluded |
| xSTUDIO | Apache-2.0 [V] | 3.4 | |
| Typst (core; Python binding 0.15) | Apache-2.0 [R] | 4.8 | |
| Godot | MIT [R] | 4.8 | |
| usd-core 26.11 | TOST-1.0 [R] | brainstorm 5.9 | Apache-2.0 with a modified trademark section; not OSI/SPDX-listed |
| NVIDIA Warp 1.18 | Apache-2.0 [R] | brainstorm 5C | relicensed from a NVIDIA licence in 2025 |
| Blender (Geometry Nodes, headless) | GPL [R] | brainstorm 5B | already used as a subprocess; keep it that way |
| Krita 5.2.2 (Ubuntu package) | GPL-3.0-or-later [R] | WP-18 | `.kra` files are read by our own reader (tiles, LZF); Krita itself only saves the test's `.kra` under xvfb-run, as a separate program |

**Add to "explicitly avoid":** ToonCrafter (generative video; licence unclear), Stable Audio Open (Stability Community
License, revenue-capped, **SRC-AVAIL**), Depth Anything V2 Base/Large/Giant (**NC**), pymeshlab in-process (GPL-3),
Kitsu in the service (**AGPL**, unverified).
