# dbe: the Doodleberry backend engine

One command registry for people and agents, reachable three ways:

| surface | how | for |
|---|---|---|
| CLI | `python -m dbe <command> '<json args>'` | scripts, CI, quick tests |
| HTTP + Studio | `python -m dbe serve [port]` then http://127.0.0.1:8770 | people (Studio UI) and HTTP clients: `GET /api` lists the commands, `POST /api/<command>` runs one (`?async=1` returns a job id) |
| MCP (stdio) | `python -m dbe mcp` | agents: Claude Code, Claude Desktop or any MCP client. Tool names use `_` for `.` (`film_render`) |

Register it with Claude Code: `claude mcp add doodleberry -- python -m dbe mcp` (run from the repo root, with the
environment variables below).

## Environment
| variable | meaning | default |
|---|---|---|
| `DBE_PY` | Python that has piper-tts, faster-whisper, numpy, scipy, pyworld (voice and audio) | the current Python |
| `DBE_VOICES` | folder of Piper `.onnx` voices | `~/voices` |
| `DBE_BLENDER` | Blender 5.x binary (Grease Pencil renderer) | `blender` on PATH |
| `DBE_GP_SAMPLES` | EEVEE anti-aliasing samples for Grease Pencil | 4 |

## Commands
`python -m dbe engine.commands` prints the live list with argument schemas. Summary:

- **engine.info**: versions of every tool found (node, ffmpeg, synfig, blender, piper...).
- **film.create / film.get / film.write**: make a film folder, read it, write brief.md, facts.json, script.json, shots.json or score.json.
- **voice.build**: Piper TTS, Whisper word alignment and viseme lip-sync; writes `timing.json`. Passes the voice licence gate first.
- **voices.list**: Piper voices with licence status from `voices/registry.json` and whether they are installed.
- **cast.list / cast.add / puppet.lint**: the cast library. `cast.add` lints a puppet, accepts only open licences,
  checks its voice is clean, records author, licence, provenance and a content hash in `cast/index.json`, and appends
  to `cast/provenance.jsonl`.
- **film.credits**: credits built from what the film uses (characters with their rights, voices and licences, renderers, and assets from `assets/manifest.json`).
- **film.package**: posting package in `build/package/`:
  - `posts.md` with per-platform captions (takeaway first, hashtags last), a YouTube title, description and chapters, a pinned sources comment, alt text, an engagement prompt, credits and a 48-hour checklist;
  - `cover.png`, a chosen frame with cover text fitted to the safe area.

  It reads `shots.json` `brief` (title, takeaway, hook, hashtags, cover_text, cover_t, prompt, post_date, part/parts, client).
- **asset.check**: every tracked third-party file must be listed in `assets/manifest.json`.
- **Rights:** `cast.add` takes `rights` = open (an open licence), owner (your own IP, with the owner named) or client (made for a client, with owner and terms). Client-work characters render only in films whose `brief.client` matches.
- **Delivery:** finals use `dbe/profiles.json` master (H.264 High, CRF 18, AAC 48 kHz 320 kb/s, faststart, ≤100 MB) and come with `captions.srt` and `captions.vtt`.
- **shot.render**: render one shot with its renderer: `svg` (headless Chromium), `synfig` (Synfig CLI), `grease-pencil` (headless Blender), or `lottie` (lottie-web).
- **film.render**: render all shots, join them, burn in word-timed captions, mix score, effects and voice (−14 LUFS), mux, then run QA.
- **qa.run**: the measured quality bar plus contact sheets, plus layout checks (`dbe/layout_qa.py`):
  - **frame fill:** bare-ground share per scene, sampled every 3 s on the final encode;
  - **text:** every word inside the platform-safe area (9:16: x 64–960, y 200–1560; 16:9: 5% title-safe), and minimum type size;
  - **reading time:** static blocks stay up for at least words ÷ 3 + 1 s; caption flow under 3.2 words/s;
  - **seams:** frame difference at cuts;
  - **cold open:** a character in frame one, and the first words by 1.5 s;
  - **mix:** effects below music; percussive cue onsets within one frame.

  Every film gets the numbers. A layout check fails a film only if the film opts in with
  `"qa": {"enforce": ["text_in_safe_area", ...], "fill_max": 0.4}` in shots.json; thresholds come from flat-paper
  explainers and are calibrated per style first.
- **test**: golden-frame regression test (`tests/golden.json`); `{"update": true}` rewrites the goldens.
- **film.validate**: schemas plus reference checks; runs automatically on `film.write` and before renders.
- **export.lottie / export.synfig / export.web**: a Lottie JSON (with the set embedded as an image), an editable Synfig project, or an interactive web player.
- **film.localize**: copy a film into another language: swap voices, replace lines, re-voice and re-render. Timing re-derives from the new words.
- **film.retime**: re-derive shot boundaries from line references after a voice change.
- **variants.hooks**: render alternative openings (shots.json `hooks`) joined to the rest of the film.

## A film as data: `shots.json`
```json
{"title": "Pip in the park", "size": [1080, 1920], "fps": 30, "captions": true,
 "shots": [
  {"id": "s1", "renderer": "svg", "set": "park", "start": 0, "end": 5.7, "start_line": "hi",
   "cast": [{"puppet": "puppet/examples/pip.puppet.json",
             "place": [[0, {"x": -80, "y": 1500, "s": 0.95}], [1.5, {"x": 540, "y": 1500, "s": 0.95}]],
             "timeline": {"clips": [{"clip": "walk", "start": 0, "end": 1.5}, {"clip": "wave_R", "start": "hi.start-0.2", "end": "hi.start+1.38"}],
                          "visemes_from": "pip", "view": [[0, "front"], ["hi.end", "side"]], "springs": true}}],
   "cues": [{"t": "hi.start+2", "type": "chime"}], "camera": [[0, [540, 960, 1]], [4, [540, 900, 1.15]]]}],
 "hooks": {"question": {"set": "plain"}}}
```
- `renderer` routes each shot. All renderers read the same baked animation (`tools/bake.mjs`): per frame, each part's
  angle, root offset, swaps, view and squash.
- Times can be seconds or line-relative (`"mid.start+0.9"`), resolved against `timing.json` on every read.
- Sets live in `sets/sets.js` (plain, park, clinic, cutaway); `set_opts` recolours them.
- Captions are one film-level pass (`dbe/captions.py`, ASS through libass): chunks of 3 words with the spoken word
  highlighted. `caption_style` in shots.json overrides font size, colours and position.

## Renderer notes
The set is always drawn by the SVG player, so clouds drift, the camera works and characters keep a ground shadow.
Synfig and Grease Pencil draw only the characters, with alpha, and ffmpeg composites them over the set video. Lottie
exports embed the set as a still image (`background: none` exports the characters alone).
Camera keys (`[[t, [cx, cy, zoom]]]`) are folded into each character's baked position and scale, so a push-in
frames the composited characters exactly like the set.

- **svg**: fastest and the reference look (about 25 s for a 5 s shot).
- **synfig**: a `.sif` with one group per part and animated transformations; editable afterwards in Synfig Studio.
- **grease-pencil**: per-frame strokes in Blender 5.x, rendered by EEVEE at half resolution and upscaled. About 4 s
  per frame on software Vulkan. Blender 5.2 quirks handled in `dbe/blender_gp.py`:
  - a stroke fills only when its `fill_id` is non-zero;
  - new materials carry a Principled node tree that must be cleared;
  - GP objects are lit unless `use_grease_pencil_lights` is off;
  - GP colours are linear.
- **lottie**: one shape layer per part, parented like the skeleton, rotation keys about the pivots, swaps and views
  as hold-keyed opacity.

## Licences
- `voices/registry.json` gates voices: only `clean` voices build unless a film's script.json sets
  `"allow_restricted_voices": true`, which is for internal tests only.
- `docs/feature-map.md` is the full feature map and build order.
- `docs/oss-research.md` lists vetted libraries, models and assets, plus the ones to avoid.
- Piper itself (piper-tts ≥ 1.3) and espeak-ng are GPL-3.0. They run as a separate process, which is fine for a
  service, but it matters if Doodleberry is distributed as software.
