# motion — films rendered entirely in code

A small, reusable pipeline for short narrated films: SVG scenes where every
value is a function of the frame number, rendered frame-by-frame in headless
Chromium and encoded with ffmpeg; narration, score and effects synthesized in
code; measured QA plus contact sheets for an independent critic pass.

The first film, `films/clover`, is an original explainer ("Why farmers rotate
clover") built to prove out the cartoon cross-section explainer genre: soil
cutaway, prop characters with faces, a magnifier window into a root nodule,
one-word kinetic captions, narration-led.

Later films: `films/clover-friends` (character story), `films/banana-herb` (banana plant rig) and the
research-story pair `films/screwworm` (full, ~3:23) + `films/screwworm-hook` (~41 s), which share
`films/screwworm-shared/` (original rigs, a Natural Earth map built by `tools/mapgen.py`, and a shot-list
sequencer: each cut's `scene.js` is just a list of shots keyed to script lines). `tools/shotstills.mjs` renders
a contact sheet with one still per shot.

## Pipeline

```
script.json ──voice.py──▶ build/voice.wav + timing.json (word times)
                               │
scene.js (frame → SVG) ◀───────┘           score.json
   │  render.mjs --dump-cues ─▶ build/cues.json ──┐
   │                                              ▼
   └─ render.mjs ─▶ build/picture.mp4     audio.py ─▶ build/mix.wav, music.wav
                         └──────── ffmpeg mux ────────▶ build/final.mp4
                                                         │
                                               qa.py ────┘ build/qa.json + contact sheets
```

| file | what it does |
|------|--------------|
| `engine/timeline.js` | easing, closed-form springs, keyframes, seeded noise, blinks, squash-and-stretch pops, timing lookups. No clocks, no `Math.random`. |
| `engine/draw.js` | richer drawing primitives: cel shading with hue-shifted shadows and warm rim light, tapered strokes (veins, root hairs, grass, brows), glossy eyes and shaded spheres, seeded branching rootlets, soft blurred clouds, depth-of-field blur filters, travelling wind gusts, soil-crumb bursts and emphasis marks. `D.begin()` per frame, `D.defs()` once in the frame's SVG, `D.prebuilt()` for art built once. |
| `engine/cast.js` | reusable character rigs built on draw.js: an expressive face (eyelid and brow moods, lip-synced mouth), a kid farmer with posable arms, an earthworm on a flexible spine, and a banana plant (corm and cord roots, sheathed pseudostem, spiral leaves with veins and splits, unrolling cigar leaf, flower spike with lifting bracts, hands of fruit forming tier by tier and ripening, a sucker, optional face). |
| `engine/render.mjs` | loads a film's `index.html`, calls `window.renderFrame(f)` for each frame across N parallel browser pages, pipes PNGs into ffmpeg. `--still 0,60,…` for stills, `--from/--to` for test renders, `--dump-cues` for the sound-cue list. |
| `engine/voice.py` | Piper TTS per script line, faster-whisper word alignment mapped back onto the script's own words, writes `timing.json`. `--audition` renders every voice and reports words per minute. |
| `engine/voicefx.py` | re-voices the narration with the WORLD vocoder: pitch, formant (vocal-tract length) and intonation range change, timing doesn't, so captions and picture stay in sync. Presets `child` and `baby`; set `"voice_fx": "baby"` (or `{"preset": "baby", "pitch": 2.0}`) in `script.json`. |
| `engine/audio.py` | stereo, seeded synth score (pluck, bass, pads, shaker, marimba) on a beat grid from `score.json`; the melody sits an octave above the narrator and thins to quarter notes while they speak. Effects keyed to on-screen cues, each levelled to a per-type target. Narrator cleaned, levelled line to line and gently compressed. Music and effects ducked by a voice-driven presence signal in three bands (hardest at 200 Hz–5 kHz), a seeded stereo room reverb, loudness to −14 LUFS with linked true-peak limiting. Writes stems and a music-only version. |
| `engine/mixcheck.py` | measures a mix: loudness, loudness range, true peak, speech-to-background ratio while talking, music level between lines, effect levels, line-to-line voice spread, music energy in the voice's pitch band, and (`--whisper`) Whisper's confidence on the full mix. |
| `engine/qa.py` | duration / size / fps, frozen-stretch detection, loudness and true peak of the encoded file, fact tracing, 2 fps sound-off sheet and 0.2 s dense sheets. |

A film directory holds `brief.md`, `facts.json`, `script.json`, `score.json`,
`scene.js`, `index.html`, and writes everything generated into `build/`.

## Running it

Requirements: Node with Playwright + Chromium, ffmpeg, Python 3.11+ with
`piper-tts faster-whisper numpy scipy soundfile pyloudnorm pyworld` (pyworld also needs `setuptools<81`), and a Piper voice
(`.onnx` + `.onnx.json`, e.g. from `rhasspy/piper-voices` on Hugging Face).

```bash
F=films/clover
python engine/voice.py $F --voices-dir ~/voices            # narration + timing.json
python engine/voicefx.py $F                                # optional: re-voice (script.json "voice_fx")
node   engine/render.mjs $F --dump-cues                    # sound cues from the scene
python engine/audio.py $F                                  # score, sfx, mix
node   engine/render.mjs $F --workers 4                    # picture
ffmpeg -i $F/build/picture.mp4 -i $F/build/mix.wav -map 0:v -map 1:a \
       -c:v copy -c:a aac -b:a 256k -af apad -t <length> $F/build/final.mp4
python engine/mixcheck.py $F --whisper                     # optional: mix balance and intelligibility
python engine/qa.py $F                                     # measured checks + sheets
```

## Making a new film

1. Copy `films/clover` as a starting point; write `brief.md` and `facts.json`
   first, then `script.json` with each line pointing at a fact id.
2. Build narration, then write `scene.js`: a `frame(f)` function returning SVG
   markup, timed off `T.word(line, word).start`, plus `window.CUES` for sound.
3. Render stills at the key beats before rendering the whole thing.
4. Run `qa.py`, then hand the contact sheets to a reviewer who hasn't seen the
   build; log each round in `ledger.md`.

Fonts are pinned locally (`engine/fonts`, Fredoka, SIL OFL).
