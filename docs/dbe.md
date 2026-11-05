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
- **voices.list**: voices with licence status and install state: Piper voices from `voices/registry.json`, plus every installed Kokoro voice (`kokoro:<name>`, Apache-2.0, 54 voices in 9 languages). Filter with `{"language": "Spanish"}`. Use a Kokoro voice in script.json like any other: `"voice": "kokoro:ef_dora"`.
- **cast.list / cast.add / puppet.lint**: the cast library. `cast.add` lints a puppet, accepts only open licences,
  checks its voice is clean, records author, licence, provenance and a content hash in `cast/index.json`, and appends
  to `cast/provenance.jsonl`.
- **film.credits**: credits built from what the film uses (characters with their rights, voices and licences, renderers, and assets from `assets/manifest.json`).
- **film.package**: posting package in `build/package/`:
  - `posts.md` with per-platform captions (takeaway first, hashtags last), a YouTube title, description and chapters, a pinned sources comment, alt text, an engagement prompt, credits and a 48-hour checklist;
  - `cover.png`, a chosen frame with cover text fitted to the safe area.

  It reads `shots.json` `brief` (title, takeaway, hook, hashtags, cover_text, cover_t, prompt, post_date, part/parts, client).
  With a `titles.json`, the package uses its chosen title, re-runs the truth check on it (`title_true`) and lists the
  covers per cut and platform.
- **Title, thumbnail and cover lab** (plan 3.9, WP-07; `dbe/packaging.py`):
  - **title.check**: the packaging truth check. A title or a double-barrel thumbnail (top and bottom, at most 4 words
    and 18 characters each) may not claim what the film does not support (its fact claims and narration): every
    number must be in them (counts and years exactly), absolutes and superlatives (always, never, only, first, cure,
    deadliest, ...) must be said of the same subject, and a causal claim stated rather than asked needs a fact or line
    on the same subject that is not negated; one the film negates is *contradicted*. A myth film may ask its myth or
    deny it, never state it. Plus the newcomer check: at most 60 characters, no unexplained acronyms, few long words,
    no insider wording (episode numbers, we, our, again, unless quoting the film's own line), no emoji. It is a
    mechanical floor; the writing agent reads the facts on top of it.
  - **title.propose**: mechanical candidates (the film's title and its own questions) with their checks, and the brief
    for a writing agent; **title.set** records candidates in `films/<name>/titles.json` with their checks (failing
    ones are kept with the reason) and the chosen title and thumbnail, which must pass.
  - **cover.make**: for every finished cut (master, sound-off, episode and teaser cuts, other aspects) and every
    platform in `dbe/profiles.json`, the best frame of the cut (least bare ground, a character on screen, at least
    0.5 s from a cut and 1 s from the ends) with the chosen thumbnail text in the brand kit's headline font and
    colours, placed in the calmest band of the platform-safe area so it never sits on the film's own words. A platform
    in another aspect gets the cut in that aspect when it was rendered, else the frame on the brand's paper (never a
    stretch). Writes `build/package/covers/<cut>--<platform>.png` and `covers.json` (with each lettered row's font,
    direction and size). A language version gets its own covers (`film.localize` makes them): a row in a script the
    brand font lacks is lettered in that writing system's caption font (Noto Sans Sinhala, Noto Sans Arabic, found
    through fontconfig), shaped by Pillow's raqm layout, and right-to-left text is set from the right edge, with the
    frame on the left of a wide cover. Test `covers_l10n`: every row's font has all its glyphs, and a clean rendering
    of each row reads back in its script (all words, never better reversed).
  - **titles.status**: the back catalogue: per film, title and thumbnail candidates that pass today's check (facts
    change, so titles are re-checked) and covers missing for rendered cuts.
- **Posting with a human approval per post** (plan 4.15, WP-08; `dbe/posting.py`): nothing is posted without a
  person's approval of that post. `post.queue` makes one post per platform from a film's package (caption, title,
  that platform's cover, subtitles, the audio of its localised versions as extra tracks on YouTube) at its calendar
  row's date and the channel's `post_time` in its `timezone`; a post whose package fails (title not true, no
  subtitles, facts without sources) is blocked, and one with posting flags (non-clean voice, restricted inputs) can be
  approved only with the flags accepted. `post.approve` records the approver's name and time (`post.revoke` takes it
  back). `post.run` sends what is due: through a connector where one is configured (`productions/connectors.json`,
  machine-local; only a `dryrun` test connector ships, since platform APIs need the owner's own app credentials and
  some an app review), otherwise into `out/posting/<date>/<platform>/<film>/` with the files, the text and a
  `reminder.ics` for the person who posts it. Unapproved posts that are due are held, never sent. `post.done` records
  the published link; when all of a row's posts are out, the row is marked posted in the plan with every link.
  `post.status` and the board's Posting section show the queue, with Approve, Revoke and Posted buttons.
- **Renderer parity** (WP-14, `dbe/rparity.py`): `render.parity {name, shot}` draws the shot's cast alone with the
  SVG renderer (`castonly=1`, without line boil) and with Synfig, Lottie and Grease Pencil at the same moments, and
  compares each with SVG: the better of the filled-silhouette overlap and a line F-score (ink within about 4 px of the
  other's), at least 0.85, and the colour difference where both have ink, a pixel in from every edge (lines a
  pixel apart are judged by the line score, not as colour), at most 24 of 255.
  `render.parity_bench` runs every benchmark shot. A renderer that cannot draw a shot says why (`rparity.CAPABILITIES`;
  `shot.render` refuses with the same reason), and styles a renderer draws without (line boil) are listed. What
  parity fixed: the bake now records every swap set's drawing (drawn levels and control-driven swaps were lost to
  the other renderers), auto-camera and float shots carry the SVG player's own camera into the bake
  (`tools/view_keys.mjs`), Synfig and Lottie draw raster parts and drawn levels (import layers and image assets) and
  clip-driven layer order (a layer per order, shown on its frames), Lottie keeps the end of every hold (changes no
  longer smeared back across it) and drawn levels without a hip, Synfig keyframes are reduced (long shots stayed
  over the XML parser's 10 MB limit), and single Synfig frames are asked for in seconds (a bare number is frames).
  Blender 5.2.3 LTS (`bash tools/setup.sh blender`) runs the Grease Pencil renderer.
- **Props, motion effects, the time warp and .blend projects in the other renderers** (WP-14, part 2):
  - **Props**: `tools/bake.mjs` evaluates each prop as the player does (`dbe/player/props.js`: attach keys, flights,
    drops, paths, baked physics; characters evaluated at any time for their hands). Each ball or box becomes a small
    generated puppet drawn as `props.js` draws it, with its position, spin and the camera per frame. It is appended to
    the baked cast, so Synfig, Lottie and Grease Pencil draw it as they draw characters. Squash, stretch and smear
    frames stay SVG-only and are listed as drawn without; props with their own SVG drawing stay SVG-only. Parity:
    props-demo 0.999 to 1.0 (Synfig, Lottie); juggle-demo's five props 0.997 to 1.0 on all three.
  - **Motion effects** (speed lines, dust, impact stars, motion arcs): the bake records each frame's effect markup,
    and `dbe/fxbake.py` turns every distinct frame into a drawing of a swap set on a generated puppet. Synfig gets
    each drawing as a PNG cropped to its ink, drawn by Chromium from the player's own markup, because juggle-demo's
    254 effect drawings as Synfig vectors made a 23 MB file its XML parser refused; as images it is 1.4 MB. Parity at
    moments with effects on screen: fx-demo (without its toon shading) Synfig 0.993 to 0.999, Lottie 1.0;
    juggle-demo Synfig 0.999 to 1.0.
  - **The time warp**: in a time-warped cut (the sound-off cut) the bake runs on the cut's clock, each frame showing
    the film at the warped time, as the player renders it; `render.parity` compares such a cut on its own clock.
    dialogue-demo's sound-off cut: Lottie 1.0, Synfig 0.98 to 0.99.
  - **A saved .blend**: `export.blend {name, shot}` saves the Grease Pencil scene (every frame a keyframe, the
    camera, EEVEE settings, the set's first frame as a background plane) as `build/shots/<shot>.blend`. Test `blend`
    (only when asked): pip-park's shot reopened in Blender renders frame 85 identical to the renderer's own (max
    difference 0).
  - **Compositor planes**: the player renders a compositor shot in two passes, the planes behind the characters
    (`comp=back`, with the stage's set and shadows) and the planes in front (`comp=front`, on transparency). The other
    renderer's characters go between them (Lottie on transparency too). Characters placed on other planes stay
    SVG-only. Parity on night-planes: Synfig 0.98 to 1.0, Lottie 1.0, Grease Pencil 1.0. Test `compplanes` (only when
    asked): night-planes from Lottie against the SVG render, 41.3 to 41.7 dB PSNR.
  - **Speech bubbles** in every renderer: the player's `overlay=1` pass poses the cast (for where the bubbles point)
    but draws only the bubbles and a compositor shot's near planes, on transparency, and it goes over Synfig's,
    Lottie's and Grease Pencil's frames (it replaced the `comp=front` pass). Test `bubbles` (only when asked):
    juggle-demo's shot from Lottie carries the bubble where the SVG renderer draws it, 6.3 levels apart on its 14,051
    pixels against 185 without it.
  - **Toon shading in Synfig and Grease Pencil**. In Synfig each filled stroke of a (non-bendy) part gets a group at
    the toon's opacity: the shape in the shade colour, cut ("alpha over") by the same shape shifted toward the light.
    The shift is in the part's own axes, animated per frame as the part turns, as puppet.js computes it. Grease
    Pencil gets the band as geometry, per frame: the shape minus itself shifted, by polygon difference (shapely),
    drawn as a fill between the stroke's fill and its outline (Lottie: below). Test `toon` (only when asked), on a copy of pip-park
    with `style.toon`. Parity is 1.0 (Synfig) and 0.993 (Grease Pencil). In the band the SVG renderer shades (8,274
    px), Synfig is 4.4 levels from the shaded picture and 44.8 from an unshaded copy. Grease Pencil is 19.6 against
    31.1; it renders at half size, so its edges are softer. (A first measurement on fx-demo had read Synfig as nearer
    the shaded picture while drawing no band at all: `toon: true` became an empty, falsy dict. The test now compares
    against an unshaded copy.)
  - **Media in every renderer** (WP-15): a shot's `style.medium` (pencil, crayon, marker, watercolour) reaches Synfig,
    Lottie and Grease Pencil through the player's own filter. `tools/media_frames.mjs` reads the filter definitions
    from player.js (one definition) and draws each of the renderer's transparent character frames through it before
    they go over the set; Lottie, for such a shot, renders its characters on transparency as it does for a comp. The
    frames are filtered at the film's size: the grain is laid in film pixels, and Grease Pencil renders at half size
    (filtered as they came, its frames read nearer the plain render than the crayon one, 75.9 against 64.1). Under a
    zoomed camera the grain is finer or coarser than the player's. Test `mediarenderers` (only when asked) puts a copy
    of pip-park in crayon and checks each renderer's frame is nearer the crayon SVG render than the plain one, where
    the medium changes it (46,993 px): Synfig 24.4 levels from the crayon render against 92.1 from the plain one,
    Lottie 24.2 against 92.0, Grease Pencil 26.9 against 95.7.
  - **Toon shading in Lottie**: per shaded part, a track matte of its fills over a layer with the shade colour and the
    fills shifted toward the light, at the toon's opacity; clipped per part, not per stroke. In test `toon` (same band)
    Lottie is 2.2 levels from the shaded picture and 41.5 from the unshaded copy, parity 0.994.
- **Compositor and multiplane camera** (WP-36, `dbe/player/comp.js`): a shot's `"comp"` builds it from depth planes,
  far to near, each holding sets (`set`), items (`shape` with SVG, `gradient`, a seeded `stars` field, or any
  overlay) and cast members (`"plane"` on a cast entry; the shot's own set, cast and props are the plane `stage`,
  depth 1). A plane at depth d follows the camera by 1/d and zooms by 1 + (zoom - 1)/d, so far planes move less (true
  parallax); `drift` moves a plane on its own; depth of field blurs each plane by `dof` × |1/d − 1/focus|. Nodes per
  plane: `grade` (brightness, contrast, saturation, tint), `blur`, `glow` (coloured, with strength), `mask` (ellipse,
  rect or path, feathered, inverted, in plane or screen space) and `blend` (any CSS blend mode, opacity). Everything
  is SVG filters and masks: a frame rendered twice is byte-identical. Set `"set": "none"` (transparent) when the
  planes paint the world. Ids start with `comp-`, which the AI-look lint treats as deliberate. `films/night-planes`
  (golden frames): a sky with a glowing moon, hills, a masked and screen-blended mist band, the stage and foreground
  grass under a slow camera push.
- **Parallax set layers** (WP-15): a set may draw itself as depth layers (`layers(t, opts, W, H)` beside `draw`). In a
  shot whose camera moves (keys, automatic camera or float), the player gives each layer the compositor's parallax
  inside the camera's own transform: it follows the camera by 1/depth and zooms by 1 + (zoom - 1)/depth. A still
  camera draws the set flat, exactly as before. The forest set is drawn this way: sky (depth 6), three rows of trees
  (3.5, 2.2, 1.4, with extra trees beyond both edges for pans) and the ground (1). Test `parallax`: under a 300 px pan
  each layer's first shape moves 300/depth px on screen (-50.0, -85.71, -136.36, -214.29, -300 against the same
  wanted), and the panned frame has no uncovered edge.
- **Compositor, part 2** (WP-36):
  - **Camera roll**: `"roll"` in degrees, turning the whole composite about the frame centre.
  - **Keyed values and expressions**: any number in a plane or node, and `roll`, `focus` and `dof`, may be keys
    (`[[t, v], ...]`, linear) or an expression (`"=0.9 + 0.1*sin(2*t)"`). Expressions may use `t`, sin, cos, abs,
    min, max, pow, sqrt, floor, clamp, pi, and `track("id", "x" | "y" | "luma")`. Anything else is refused,
    property access and inherited names included. They are pure functions of time.
  - **Light wrap**: the node `{"type": "lightwrap", "plane": "stage", "radius", "strength", "from"}` takes the planes
    behind (or those named), blurs them, and screens them over the plane through a mask. The mask keeps a band just
    inside the plane's edges (its alpha minus its blurred alpha). It is built from masks and plain filters, not
    `feImage`: Chromium will not read the player's cached raster layers into a filter, and it silently drew nothing.
  - **Region tracker**: `comp.track` follows a rectangle through a plate (an image sequence or a video). It uses
    normalised cross-correlation in a window around the last position, with a parabola through the peak for
    sub-pixel positions (`dbe/comptrack.py`). It writes `comp.tracks.<id>` as `[t, x, y, luma]`. An item with
    `"attach": id` (and `"offset"`) moves with it, and an expression can read the position or the region's
    brightness, so the picture drives a parameter.

  Test `comp2`, on a copy of night-planes:
  - roll asked 8 degrees, measured 7.95 (ORB features, a fitted similarity);
  - a sky grade keyed from 0.4 to 1.4 takes the sky from 23 to 51 levels (36 unkeyed);
  - light wrap in front of a warm plane changes 2.7% of the frame, 98% of it within the wrap radius of an edge and
    all of it brighter (+45 levels);
  - a textured square moving sub-pixel over a textured plate is tracked within 0.26 px mean (0.45 max) over 60
    frames;
  - a dot attached to the track lands within 0.7 px of it in the player.

  **Nested groups and deformers** (WP-36). A comp item `{"type": "group", "items": [...], "pivot", "translate",
  "rotate", "scale", "opacity", "deform"}` moves its items together (translate, then rotate and scale about the pivot,
  each keyed or an expression); groups nest, so a child moves inside its parent's motion. `deform` bends the group's
  drawing in the group's own space, so a deformed child is deformed again by its parent: `wave` (a travelling sine
  along an axis: `amount`, `wavelength`, `speed`), `bend` (x moves by amount times the square of the depth into the
  rect), `shear`, and `noise` (seeded fractal noise, a heat haze or boil). Each is an SVG displacement map built from
  filter primitives alone, strips of flat colour along the ramp blurred along it: an image (a data URL) loads after the
  frame is taken, and `feImage` by reference draws nothing from `<defs>` in Chromium, so both made frames that were not
  pure functions of time. Test `compgroups`: a dot in a scaled, waved child inside a rotating parent lands within
  0.85 px of where the composed motion puts it (at 0, 0.37 and 1 s), the bar follows the scaled wave within 1.33 px,
  a shear of 40 over 300 px moves a bar's foot 38 px (38.7 expected), and a frame renders identically twice.

  **The compositor in the graph view** (WP-36). The graph page (`/graph`) has a view per shot with a comp
  ("compositor · s1"): a box per plane, far to near, each feeding its nodes in order, all into the camera (focus, depth
  of field, roll, zoom) and the frame. Clicking a box shows its values to edit (numbers, keyed values or
  expressions), with the player's frame beside them at a chosen time; a plane's box adds a node (grade, blur, glow,
  mask, blend, light wrap, with defaults), a node's box removes it. Edits go through `comp.edit {name, shot, target,
  set}` (`comp`, `plane:<id>`, `node:<index>`, `node:new`), which checks expressions with the compositor's own sandbox
  and the shot against the schema before keeping it. Test `graphcomp`, on a copy of night-planes: 12 boxes for 6
  planes and 4 nodes, a grade brightened to 1.8 brightens the preview (mean 48.8 to 54.8 levels, 16% of it changed),
  a blur added to the sky shows as a new box, the camera rolled 5 degrees, and "=constructor" refused with nothing
  written.

  night-planes' golden frames are unchanged.
- **Animated primitives and procedural growth** (WP-42), compositor items:
  - `{"type": "prim", "shape": ...}`: circle (`r`), rect (`w`, `h`, `round`), star (`points`, `r`, `inner`),
    polygon (`sides`, `r`), arc (`r`, `start`, `end` in degrees; a pie, or a ring with `"ring": true`) and wave (`w`,
    `amp`, `freq`, `phase`), placed by `x`, `y`, `rotate` and `scale`. Every number may be keyed or an expression,
    so a shape morphs in time ("points": "=5 + floor(t)").
  - `{"type": "growth", "seed", "x", "y", "length", "depth", "start", "duration", "spread", "lean", "colour",
    "leaf"}`: a seeded branching plant. Each branch draws along its length once its parent reaches the fork, two or
    three to a fork, thinner and shorter each level; leaves open at the tips, just as the growth ends. The shape comes
    only from the seed, so a frame is a pure function of time.

  Test `comp3` (stills by `tools/comp_still.mjs`):
  - a circle keyed from radius 50 to 150 is 31,287 pixels at radius 100 (pi r^2 = 31,416);
  - a star whose points are "=5 + floor(t)" has 10 corners at 0 s and 14 at 2 s;
  - a plant growing over 2 s gains ink at every step and is finished by 2.2 s (1,503 -> 23,470 pixels);
  - it renders identically twice, and another seed differs in 36,188 pixels.
- **Drawn levels** (WP-35, puppet format v0.8): hand-drawn animation as a sequence of drawings with an exposure
  sheet. `level.make` builds one from drawings (PNG, transparent) and a timing (on ones, twos, threes, or holds per
  drawing) into `cast/levels/<name>.puppet.json`; `level.xsheet` retimes it or writes the cells; `level.from_pencil2d`
  brings in a Pencil2D animation with its holds; `level.onion` gives the onion-skin drawings around a frame. A shot
  casts a level like a character and starts its clip `play`. `films/level-demo` plays a 12-drawing campfire and a
  12-drawing walk cycle on twos beside Ravi (golden frames in `python -m dbe test`); its drawings are stand-ins made
  by `tools/make_level_demo.py` with MyPaint strokes.
  **Studio drawing page** (http://127.0.0.1:8770/draw, linked from Studio): draw a level frame by frame with a
  pressure pen (perfect-freehand), a MyPaint brush (each stroke painted by libmypaint on the server) or the eraser,
  with onion skins (the two drawings before in red, the next in green) and the exposure sheet beside it: click a
  frame, add a drawing after the current one, hold it a frame longer or shorter, put the whole sheet on ones, twos or
  threes, and play it at the level's rate. `level.new`, `level.get`, `level.draw` (one drawing from the page, a new
  name placed in the sheet), `level.delete_drawing` and `level.list` serve it; `python -m dbe test` (levels) drives
  the page with a pointer like an animator (`tools/draw_check.mjs`).
  Part 3: **`level.cleanup`** turns rough drawings into clean ones (construction lines fainter than `keep` and specks
  go; one ink colour if asked); **`level.capture`** is a pencil test: a photo of a drawing on paper loses its lighting
  and paper, is fitted into the frame and lined up with the drawing before it (phase correlation of the ink, a digital
  peg bar), then joins the sheet; **`level.colour`** paints with named colour styles: a point inside a closed shape
  fills it under the line, a painted drawing's areas are carried to every other drawing, and changing a style
  repaints them all. The page has Capture (the phone's camera or a file), Clean up, Paint, Style and Carry colours.
- **Open-source parts** (WP-34, decisions in `docs/oss-integration.md`): `brush.paint` and `brush.list` (libmypaint
  linked through ctypes, any MyPaint brush preset, pressure strokes onto a transparent PNG), `pencil2d.write` and
  `pencil2d.render` (a drawn level to and from a Pencil2D project, rendered headless with its holds),
  `vector.boolean` (Inkscape's path union, difference, intersection, exclusion and division, headless). Optional:
  `bash tools/setup.sh oss` installs them.
- **research.check**: the research gate (sources, two independent sources for numbers, research log, fact-check clearance, safety clearance for sensitive briefs); renders refuse to start while it reports errors. See `docs/research-standard.md`.
- **critic.pack / ledger.add**: review packets for fresh critic agents (role prompts in `dbe/critic/`), and the ledger of gates and critic rounds with before/after QA numbers.
- **asset.check**: every tracked third-party file must be listed in `assets/manifest.json`.
- **Rights:** `cast.add` takes `rights` = open (an open licence), owner (your own IP, with the owner named) or client (made for a client, with owner and terms). Client-work characters render only in films whose `brief.client` matches.
- **Delivery:** finals use `dbe/profiles.json` master (H.264 High, CRF 18, AAC 48 kHz 320 kb/s, faststart, ≤100 MB) and come with `captions.srt` and `captions.vtt`.
- **shot.render**: render one shot with its renderer: `svg` (headless Chromium), `synfig` (Synfig CLI), `grease-pencil` (headless Blender), or `lottie` (lottie-web).
- **film.render**: render the shots whose inputs changed (a content hash per shot covers the shot, puppets, clips, lip-sync data and renderer code; `only` forces a list), join them, burn in word-timed captions, mix score, effects and voice (−14 LUFS), mux, then run QA.
- **qa.run**: the measured quality bar plus contact sheets, plus layout checks (`dbe/layout_qa.py`):
  - **frame fill:** bare-ground share per scene, sampled every 3 s on the final encode;
  - **text:** every word inside the platform-safe area (9:16: x 64–960, y 200–1560; 16:9: 5% title-safe), and minimum type size;
  - **reading time:** static blocks stay up for at least words ÷ 3 + 1 s; caption flow under 3.2 words/s;
  - **seams:** frame difference at cuts;
  - **cold open:** a character in frame one, and the first words by 1.5 s;
  - **mix:** effects below music; percussive cue onsets within one frame.

  - **AI look** (WP-04, `tools/ailook.mjs`): drop shadows, gradient fills over 3% of the frame, blur glows, emoji, and
    layouts where every text box is centred (at least three texts); the house set library's own gradients and
    filters are exempt.

  Every film gets the numbers. Thresholds and enforced checks come per style (WP-04, `dbe/profiles.json`
  `layout_styles`): a film's style is `shots.json` `"style"`, else doodle (a doodle-template character), cartoon
  (humanoid cast) or explainer (no cast). Each style was calibrated on its reference films' final encodes, each
  threshold just above the worst reference: frame fill (bare share) explainer 0.62, doodle 0.85, cartoon 0.80 (flat
  painted ground counts as bare, so this catches an empty frame, not a sparse one); first words by 1.5 s for
  explainers and 2.5 s for action-led doodle and cartoon openings; caption pace 3.2 words/s, 3.8 for cartoon
  dialogue. Enforced in every style (a failure fails QA): frame fill, text in the safe area, type size, AI look,
  cold open, reading time, effects below music and cue sync. Seams stay advisory until transitions exist (WP-15).
  A film's `"qa"` in shots.json may tighten thresholds and add enforced checks. Text measurement counts only words a
  viewer can see (not hidden, clipped or covered, not pushed out of frame) and leaves set text magnified past 1.25
  by a camera push-in out of the safe-area rule. Cue sync times percussive cues only (whooshes and swishes ramp in),
  each from halfway after the previous cue.
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

## Hand-made look, bubbles and ink puppets
- **`puppet.from_ink`:** a photo or scan of a drawing plus a parts spec (polygons, pivots, swaps) becomes a raster-part
  puppet in the artist's own line (`dbe/ink.py`). See `puppet/examples/make_nib_photo.py` for a full example.
- **Shot `style`:**
  - `{"boil": {"fps": 12, "amount": 5, "freq": 0.022}}` makes characters, bubbles and signs shimmer like redrawn frames;
  - `{"step": 12}` animates on 12s;
  - `{"shadow": false}` drops ground shadows.
- **Sets:** `paper` (ruled notebook) alongside plain, park, clinic and cutaway.
- **Overlays:** `[{"type": "sign" | "text", "text", "x", "y", "size", "start", "end"}]`, drawn in the same ink.
- **Speech bubbles:**
  - `"bubbles": true` turns each voiced line into a bubble from its speaker (cast `speaker` ids);
  - script lines can set `style` (say, shout, whisper) and `bubble` (on-screen wording, revealed over the spoken line);
  - placement avoids signs, overlays and the characters;
  - `extra_bubbles: [{who, text, start, end, slow}]` adds silent bubbles.
- Fonts: Fredoka (captions) and Patrick Hand (bubbles, signs), both OFL.

## Aspect ratios (one film, several native cuts)
- `film.render {"name": ..., "aspect": "16:9"}` (or "1:1") renders the same film for another frame: same script,
  voice, timings and acting.
- Re-staging recomposes each shot: characters keep their share of the frame height (1.3× in wide frames) and spread
  wider; off-screen entrances stay off-screen; overlays and camera keys are mapped too.
- Every set has its own landscape design rather than a crop.
- Fix any shot by hand in shots.json:
  `"aspects": {"16:9": {"shots": {"s1": {"cast": [{"place": {...}}], "overlays": [...]}}}}`
  (cast entries merge by index).
- Output goes to `build/final_16x9.mp4` and `captions_16x9.srt`. The derived film folder `films/<name>--16x9/` is
  rebuilt each time and is not committed.
- Bubbles, captions and QA use the right safe area for each aspect.

## Explainer scene library (overlays)
Timed with `start` and `end`, line-relative allowed. Sizes default to the aspect's type minimums.
- **`card`:** `{title, body, x, y, w}`, a definition card.
- **`counter`:** `{from, to, prefix, suffix, decimals, label, duration}`, a number counting up.
- **`console`:** `{lines, cps}`, typed commands. Lines starting with `>` are output and `!` errors.
- **`bars`:** `{data | data_from: "key" in the film's data.json, unit, title, colors, max}`, an animated bar chart
  whose numbers come from data.
- **`quote`:** `{text, by}`.
- **`citation`:** `{text}`, small mono on a soft plate, inside the safe area.
- **`wordmark`:** `{text, accent_text, accent}`.
- **Signs and text:** as before.
- **`style.float: true`:** a slow camera drift and breath, so no frame is dead.

Fonts: Fredoka (body), Atkinson Hyperlegible Mono (consoles, citations), Patrick Hand (bubbles, signs), all OFL.
`films/explainer-demo` uses all of these and passes the research gate.

## Brand kit
- `brand/brand.json` holds the palette, accents, the text pairs the brand uses, fonts, the wordmark, caption colours and
  exclusion rules.
- **`brand.check`** measures:
  - WCAG contrast for every declared text pair;
  - colour-blind separation of the accents (Machado 2009 simulation, CIEDE2000, checked against the Sharma reference
    pairs);
  - distance from Facebook, LinkedIn, YouTube and TikTok interface colours.

  It found the original blue accent nearly identical to LinkedIn's blue (ΔE 2.0) and that a green accent would merge
  with the berry for colour-blind viewers (ΔE 2.3). The palette now uses violet `#5a3fc0` (separation 20.2, at least
  15.7 from every platform colour).
- **`brand.assets`** writes profile tiles (720/400/180) and YouTube, Facebook, LinkedIn and story covers with text
  inside each platform's safe area, plus QA overlays. It refuses a palette that fails the check.
- **Films opt in** with `"brand": true` in shots.json: caption colours, the wordmark and explainer accents come from the
  brand, and explicit values in a film still win.

## Render speed
`tools/three/run3d.mjs` runs one browser process per CPU on contiguous frame ranges, uses Chrome's fast capture, and
encodes with `-tune animation`. It hashes each frame's SVG and links repeats instead of capturing them. Shots animated on
12s (`style.step: 12`) reuse about 60% of frames. Measured on pip-park shot 1 (171 frames, 4 CPUs): 116 → 82 ms/frame,
and 62 ms/frame when stepped.

**Static plates and the boil (WP-15).** Profiling a doodle film on twos (`nib-hello`, paper set, boil, 12 drawings a
second at 30 fps) showed where a frame goes: building and hashing it takes about 20 ms, the screenshot over a second,
of which the boil filter is about half and PNG-encoding a full page of paper grain most of the rest; frame reuse was
already working (117 of 195 frames). So:
- **Plates.** When a shot's set is the same on every frame (`window.platePrepare` checks every frame's set markup and
  that nothing would scale it: no camera keys, auto camera, float or depth planes; no text, which needs the page's
  fonts), the player draws it once into a PNG plate, the renderer captures the frames without it on a transparent
  background, and ffmpeg lays them over the plate. Frames laid over the plate match frames drawn whole within one
  level. `DBE_PLATE=0` turns it off. Sets that change within a shot keep a per-frame raster cache when their markup
  repeats (`?rastercache=0` turns both off).
- **Every image decoded.** Frames now wait for every image to decode, raster puppet parts (data URIs) included; one
  not yet decoded was sometimes captured missing.
- The boil filter's id carries its phase, and its region is only as large as the displacement needs.
- Measured end to end on `nib-hello` (195 frames, 4 workers, including the encode): 117.3 s before, 64.9 s now
  (55%). Reused frames are the first paint of their step; rendering every frame instead differs in 2 parts in
  100,000 of the pixels (at most 73 levels, in boiled lines), because Chrome paints identical boil markup slightly
  differently when it follows itself. Two every-frame renders differ from each other by a tenth of that.
  `DBE_DEDUPE=0` captures every frame and `DBE_KEEP_FRAMES=dir` keeps the PNGs. The `stepped` test lays three
  frames over the plate and compares them with the frames drawn whole.

## Film graph, estimates and progress (WP-20)
**The graph.** `graph.get` returns a film's data flow: facts, script, score and sound edits (the files people edit),
the voice and timing, each shot, the picture (shots joined), the mix, the final film and QA, with edges between
them. Whenever a node is made (`voice.build`, a shot render, `film.render`) what it was made from is recorded with
it, each input as a content hash (`build/graph.json`, `build/shots/<id>.inputs.json`), and for a shot also its
resolved entry in shots.json. Comparing that record with the inputs as they are now gives each node a state:
**fresh**; **stale**, with the inputs that changed ("the shot's entry in shots.json: `overlays[0].duration`",
"puppet cast/generated/momo.puppet.json", "line l2", "renderer code dbe/player/player.js"); **waiting** on a stale node
upstream; **missing** (never made here); or **unknown** (made before records were kept). `graph.cook` makes a node
again and only what lies downstream of it: a shot re-renders alone, then the picture, mix, final and QA are made
again from it and the other shots' renders as they were; the voice re-voices and re-renders the shots whose lines
moved; the mix, picture, final or QA re-assemble without rendering a shot. It returns the nodes made and the ones
left alone. The Studio page http://127.0.0.1:8770/graph?film=FILM draws the graph with React Flow (vendored with
React 18, `dbe/studio/vendor/`): colours by state, a click shows what changed, and **Re-make this and what
follows** runs `graph.cook` as a job with a progress bar.

**Estimates.** `render.estimate` says how long a render will take before it starts, from what has been measured on
this machine (`dbe/estimate.py`). A film's render is its shots' bakes and renders plus the work after the shots
(join, captions, sound, mux, QA). Every shot render appends a row to `out/render_log.jsonl` (frames, captured and
reused, render and bake seconds, its probe), every film render one with its total and the seconds of each stage
after the shots. The estimate takes, best first: a shot rendered here before with the same frames: its last times;
otherwise its **probe** (`tools/probe_rate.mjs`, cached by the shot's render hash in `out/probe_cache.json`): a few
of its frames rendered the way the renderer will (four browsers, the plate when there is one), timing the capture,
reuse and x264 encode of a frame and the start-up, plus a 1- and a 31-frame bake; render = start-up + k x (capture
x captured + reuse x reused + encode x frames), with k fitted on probe-and-render pairs (0.9 here). Per-frame cost
differs by a factor of three or more between sets and effects (a classroom about 0.15 s a frame with four workers,
a night sky 0.55 s, a boiled raster doodle about 0.5 s plus its grain plate's encode), and an automatic camera adds
up to 0.08 s a frame of baking. The work after the shots is this film's own last time, else a rough rate per second
of film from the other films. `render.bench_estimate` renders benchmark films in full. Measured on six benchmark
films (nib-hello, review-demo, data-demo, telescope-talk, fx-demo, props-demo; 58 to 471 s), each render estimated
from what was logged before it started: within 16.5% (worst nib-hello; the others 1 to 8%), which the `estimate`
test checks. For a film never rendered here the estimate is rough: off by up to 44%, because the work after the
shots varies by a factor of three between films of the same length (fx-demo's captions and final encode of busy
frames take 89 s, props-demo's 26 s), which six films are too few to model.

**Progress and webhooks.** Long commands report progress (`progress(stage=..., percent=...)` in `dbe/__init__.py`):
`film.render` says which shots it will render and the estimate, each shot as it starts and ends, assembly, and the
end, with a percent of the estimate. An HTTP call with `?async=1` runs as a job: `GET /api/jobs/<id>` has its events
and percent, and `?async=1&webhook=URL` also POSTs each event to URL (failures are noted on the job, never stop it);
`DBE_PROGRESS=stderr` prints events from the CLI.

## Sticker packs and Lottie QA (WP-23)
`sticker.pack` makes a character's sticker pack for messaging platforms. Each move (default wave, celebrate, jump;
WhatsApp packs need 3 to 30) is made once by `sticker.make`: the move is baked (`tools/bake.mjs`, eased in from rest
and back out before the end so it loops without a jump, a happy face for the cheerful moves), drawn from the baked
poses on a transparent 512 x 512 canvas framed to the whole move (`tools/sticker_frames.mjs`), and, for a vector
character, the same baked poses placed on the canvas become Lottie. Each platform's file is then encoded from those
frames (`dbe/stickers.py`), **fitted** (quality, then frame rate, come down until the file is inside the limit) and
**checked** against every limit:

| platform | file | limits checked |
|---|---|---|
| Telegram video | WebM, VP9 with alpha | one side 512 px, the other at most 512; at most 3 s and 30 fps; 256 KB; no sound |
| Telegram animated | TGS (gzipped Lottie, `"tgs": 1`) | 512 x 512; at most 3 s; 30 or 60 fps; 64 KB; no images; no expressions; renders alike in two renderers |
| WhatsApp | animated WebP, plus a 96 x 96 PNG tray icon | 512 x 512; at most 10 s; 500 KB; tray 50 KB |
| Giphy | GIF with real transparency (Bayer-dithered palette with a transparent slot) | at least 2 frames; at least 20% of the first frame transparent |
| iMessage | APNG | 300, 408 or 618 px square (408 here); 500 KB |

Limits are from [Telegram's sticker docs](https://core.telegram.org/stickers), WhatsApp's sticker guidance (512 x
512, 500 KB animated, 10 s), [Giphy's sticker best practices](https://support.giphy.com/hc/en-us/articles/360019683472)
and [Apple's HIG for stickers](https://developer.apple.com/design/human-interface-guidelines/imessage-apps-and-stickers);
Giphy states no file size cap. Measured on Pip (out/stickers/pip): every file of the three moves inside every limit;
Telegram WebM 165 to 210 KB, TGS 8 to 9 KB, WhatsApp 329 to 443 KB, Giphy 282 to 505 KB, iMessage 369 to 481 KB.

`lottie.qa` checks a Lottie file (or TGS) in two independent renderers, lottie-web (the web player, vendored) and
rlottie (Samsung's renderer, which Telegram uses; `rlottie-python`, LGPL), against each other and, when given, the
frames it was made from: silhouettes (IoU of the alpha) and colour where both draw. The two renderers must agree
closely (IoU at least 0.99, colour within 3 levels); against the frames drawn by the SVG renderer the silhouette must
hold (IoU at least 0.93). Pip's TGS stickers: the renderers agree at IoU 0.998 (colour within 1 level); against the
master frames 0.940 to 0.964. Making them pass fixed three things in the Lottie exporter (`dbe/exporters.py`, so shot
exports gain too): Lottie draws the first item on top, so strokes are now listed last-drawn first and each outline
before its fill (the nose, blush, collar and hem had been hidden under fills and ears drawn over the head); every
keyframe now carries its end value and position keys their spatial tangents; and the last keyframe carries no
easing, which had stopped rlottie drawing the layers after frame 0. The SVG renderer had drawn the legs a few pixels
(up to 4) from where Lottie draws them: it wrote each part's matrix to 2 decimals, and its rotation terms multiply
artboard coordinates of up to 1000 units; at 5 decimals Pip's celebrate and jump match Lottie exactly (IoU 1.0, was
0.965). The `stickers` test makes Pip's pack and checks all of it.

**Emoji.** `sticker.pack` with platforms `telegram_emoji` (WebM VP9 with alpha, 100 x 100, at most 3 s, 30 fps and
256 KB), `discord` (GIF, 128 x 128, 256 KB) and `slack` (GIF, 128 x 128, 128 KB) makes the same moves as custom emoji,
fitted (fewer colours, then frames) and checked the same way. Pip's three moves: Telegram emoji 26 to 33 KB, Discord
106 to 191 KB, Slack 76 to 106 KB (Slack's 128 KB cap takes fewer colours and frames).

## dotLottie with palette themes (WP-23)
`export.lottie slots=true` (and `sticker.make`'s masters, which `lottie.dotlottie` re-exports) give every colour taken
from a puppet's palette a **slot** named after the palette entry: the property carries `"sid": "skin"` and the
animation's root `"slots": {"skin": {"p": {"a": 0, "k": [r, g, b, 1]}}}` (with several characters in a shot, the slot
is `<puppet>.skin`). `lottie.dotlottie` packs animations into one dotLottie 2.0 file (`dbe/dotlottie.py`, after
[the 2.0 spec](https://dotlottie.io/spec/2.0/)): `manifest.json` (`"version": "2"`, the animations, the themes),
`a/<id>.json`, and one `t/<theme>.json` per theme, a list of `Color` rules for those slots. Themes are presets worked
out from the palette (`original` to switch back, `night` a cool, darker cast over every colour alike, `pastel`,
`mono`) or given by slot name (`{"team": {"cloth1": "#2a9d8f"}}`; a slot the characters do not have is refused).
`sticker.pack` with platform `dotlottie` puts the whole pack in one file with the four presets.

Each file is checked by reading it back (ZIP with deflate, manifest fields, every animation and theme present, ids
allowed, every rule a colour of a known slot, every slotted property backed by a slot) and by drawing every animation
in every theme in the **dotLottie player** (`@lottiefiles/dotlottie-web`, ThorVG in WebAssembly, in Chromium:
`tools/dotlottie_frames.mjs`; `bash tools/setup.sh dotlottie`) and in **lottie-web** from the same animation with the
theme's colours written in (`DL.themed`): the two must agree (IoU at least 0.98, colour within 4 levels), each theme
other than `original` must change the picture, and `original` must not. Pip's pack: 27 KB for three moves and four
themes; the two renderers agree at IoU 0.998, colour within 1.5 levels; the themes move colour by 33 to 39 levels.

## Alpha video, film formats and print stills (WP-23)
`shot.alpha` delivers a shot's characters alone with alpha for an editor or compositor: the player draws the cast
without the set, bubbles or captions (`castonly=1`) and `tools/three/run3d.mjs` captures it on a transparent page
(`DBE_ALPHA=1`, the PNG frames kept), then **WebM** (VP9, `yuva420p`, CRF 24) and **ProRes 4444** (`prores_ks`,
`yuva444p10le`, 16-bit alpha, in .mov) are encoded. Each is read back with an alpha-aware decoder (libvpx for WebM:
ffmpeg's own VP9 decoder drops the alpha) and compared with its frames at five points: silhouette IoU at least 0.97
(WebM) or 0.995 (ProRes), colour within 8 or 2 levels. nib-hello's shot: WebM 1.0 MB, IoU 0.993 to 0.997, colour 1.4
to 1.8; ProRes 57 MB, IoU 0.997 to 0.999, colour 0.04. The test also checks the WebM's `alpha_mode` tag and the
ProRes profile and pixel format.

`film.formats` turns the finished film into image animations (silent; width 480 and 15 fps by default; `start` and
`seconds` for a clip): **GIF** (one palette of 256 for the clip, error-diffusion dithered), **APNG** (full colour)
and a **line-art GIF** (32 colours, ordered Bayer dithering: a flat, printed look in about half the size). Each is
read back: width, frame count and length, colours within the palette, and closeness to the film's own frames (mean
difference after a light blur, since dithering trades exact pixels for the right average). nib-hello, 3 s: GIF
2.2 MB (difference 0.9), APNG 8.6 MB (0), line-art 1.2 MB with 31 colours (1.1).

`film.still` makes a print-ready still of one moment (`time` in seconds or a line reference): the player draws the
frame at print resolution (`tools/still.mjs`, a device scale factor, the raster cache off), since its drawing is
vector; drawn at 2.7 times, its steepest edges are twice as steep as the video frame enlarged. It covers the trim and
the bleed (3 mm by default, cut from the frame's edges) and is saved as an RGB PNG with its dpi, a **PDF** whose
TrimBox and BleedBox are set, with crop marks in a 10 mm slug, and a **CMYK TIFF** converted through an ICC profile
(the printer's own via `cmyk_profile`, else a generic public-domain one: ArgyllCMS's "Chemical proof", which Krita
installs) with the total ink reported (nib-hello: 220% at the 99.9th percentile; flagged above 320%). Captions are off
by default; film-level grading and grain are a video pass and not applied. `transparent=true` draws the characters
alone on a transparent background as a PNG at that resolution, for merch. The `alpha` test covers all three commands.

**Several outputs from one pass.** `shot.outputs` draws a shot once into RGBA frames (the cast alone by default,
`castonly: false` for the whole frame) and encodes every output from them: the PNG sequence itself, WebM and ProRes
4444 with alpha (read back and compared as `shot.alpha` does), and an MP4 and a GIF over a `background` colour (each
checked for its frame count). It reports the pass and each encode separately. nib-hello's 195-frame shot: one 8 s pass,
then WebM 43 s, ProRes 22 s, GIF 16 s, MP4 7 s (on 4 cores, with another job running), all checks passing.

**Channels view** (http://127.0.0.1:8770/channels, linked from Studio). It shows a shot's RGBA frames, or any PNG
dropped on it, one view at a time: over a checkerboard, RGB with the alpha ignored, alpha alone, red, green, blue,
premultiplied, and matte edges (partly transparent pixels in orange, a quick look at the antialiasing). It also gives
the share of transparent and partly transparent pixels. **Render RGBA frames** runs `shot.outputs` (PNG only); the page
reads frames through `shot.frames`. Test `outputs`: all five outputs come from one pass and pass their checks, the
MP4's corner is the white background, and on frame 100 of that shot the alpha view equals the frame's own alpha
channel, pixel for pixel (98% transparent, 2% edge).


**SVG frames** (`export.svg {name, time}` or `{name, start, end, fps}`, `tools/svg_frame.mjs`): the player's own SVG
markup made standalone, in out/svg/<film>/: rasterized static layers (blob images in the page) become data URIs,
the fonts its text uses are embedded (data URIs) and each text element carries its computed font, at the film's
size. The animated form holds each frame as a group shown for 1/fps s, looping (SMIL, discrete: it plays in a
browser without script), each frame's ids prefixed so their definitions cannot clash, and images repeated exactly
stored once (`<use>`). Test `svgexport` (nib-hello: raster Nib on the rasterized set, a sign with text): the frame
drawn from its SVG in a blank page matches the player exactly (difference 0.0), and a 1.5 s animated SVG at 12 fps
(18 frames, 0.55 MB with its five images shared, 4.5 MB without) matches the player at three moments, exactly. Long
stretches make large files: it suits stickers and loops.

## Accessibility: flashes, colour vision, audio description, reduced motion, aspects (WP-24)
**Flash check** (`dbe/access.py`, in `qa.run` as `flash_wcag_2.3.1`, failing the film). WCAG 2.2 success criterion
2.3.1 and its definitions: a *transition* is a change in relative luminance of at least 0.1 where the darker image is
below 0.80; a *flash* is a pair of opposing transitions; more than three flashes in any one second fail when the
flashing area covers at least 25% of a 10-degree field of view. *Red flash*: the same for saturated red
(R / (R + G + B) >= 0.8, change in (R - G - B) x 320 above 20). Three choices make it measure flashes and not motion,
each found on our own films: luminance is averaged over blocks a 30th of the short side (as broadcast analysers,
ITU-R BT.1702, average areas; per pixel, a character's ink outline shifting by one pixel counted as flashing);
flashes are counted per block (a pan sweeping the dark chalkboard edge across the frame changes each block once and
is no flash); and the 10-degree field is sized from how wide the frame looks: 13 degrees for portrait and square
video on a phone at about 30 cm (10 degrees is three quarters of the width), 30 for landscape on a desktop or TV (a
third of the width, WCAG's own 341 x 256 of 1024 x 768). With the window a third of a portrait frame, a character
walking across a light background "flashed". On made clips: full-screen flashing at 5 Hz fails and at 2 Hz passes,
45% of the frame at 5 Hz fails, a corner passes, red flashing fails the red check, a fade and a pan pass. Every
rendered film passes (at most 2 flashes in a second, in films with handheld cameras).

**Colour vision.** Machado, Oliveira and Fernandes (2009) matrices at full severity for protanopia, deuteranopia
and tritanopia, in linear RGB. `qa.run` samples a frame every 2 s and reports colour pairs that a viewer with normal
vision tells apart (Delta E 76 >= 15), that touch in the picture, and that fall below 7 under a simulation
(advisory: dark greens against browns in the classroom set are the usual ones); chart colours (an overlay's
`colors`) must stay at least 15 apart under every simulation (`chart colours apart in colour-blind vision`, failing).
Red and green chart colours: 7.3 for deuteranopes; blue and orange: 97 or more.

**Audio description** (`film.describe`, `dbe/audiodesc.py`, made by every `film.render` unless shots.json
`"audio_description": false`; the `audio_description` QA check). What the picture shows that the words do not is
already in shots.json: the set, who is in a shot and how they come in, what they do (their clips and held faces),
and text, numbers and charts on screen. Each shot gives short present-tense sentences ("Ravi and Priya are in a
classroom." "Ravi points." "A bar chart, Telescope nights per month: 4 bars, highest for March at 9."); on-screen
text the narration already says is not read again; a shot's own `"describe": "..."` replaces the generated words
(`false` leaves it out). Sentences go in the **pauses** between lines first (0.15 s clear of speech, before the shot
ends, minor parts dropped and then read up to 20% faster if needed) with the film's sound 10 dB lower under them.
How long a sentence takes is measured: every sentence and its shorter forms are first read by the description voice
(a guess from the words could not count Sinhala or Chinese words, and placed 4.5 s of Sinhala in a 1 s pause).
Our films leave about 0.4 s between lines, so most descriptions do not fit: what matters (the setting, who comes in,
text, numbers and charts) is then **extended** (WCAG 1.2.7): the picture holds on the frame at the end of the line
being spoken (a hold never splits a line), the description is read in silence, and the film carries on; gestures
and faces are read in pauses or left out (an earlier version extended every nod and shrug and nearly doubled a
12.8 s film). The described cut, `build/final_ad.mp4`, has the described track marked `visual_impaired` and
`descriptions` (and the film's own track as well when nothing was extended); `build/ad.vtt` (WebVTT descriptions),
`build/captions_ad.vtt` (the captions retimed to the holds) and `build/ad.json` go with it. The voice is a clean
Kokoro voice no speaker of the film uses. Checks from the file: no description over speech, every shot with
something to describe reached, -14 LUFS and true peak below -1 dBTP, the track marked, the length the holds account
for. dialogue-demo: 1 description in a pause and 1 hold (12.8 s to 15.5 s); data-demo: 3 holds (9.6 s to 20.8 s,
the chart is read out); Whisper hears every held description (100% of their words).
When the extended cut needed holds, a **standard cut** is made beside it (`build/final_ad_std.mp4`, `ad_std.vtt`,
`ad_std.json`): only what fits the pauses, at the film's own length and timing, with the film's sound and the
described one as two tracks, so a platform or viewer can take the one they want. It reports its coverage (the share of
shots with something to describe that it reaches) instead of requiring it: dialogue-demo's standard cut reaches every
described shot at 12.8 s. In the standard cut each description may also be said tersely, the important parts in as
few words as they go ("Ravi is in a classroom." -> "Classroom."; a chart -> "Chart: March highest, 9."; a sign ->
"Sign: OPEN."), into pauses from 0.4 s, read up to 1.35 times as fast; the terse forms are made from the English and
machine-translated with it. data-demo's standard cut, with nothing before, now says "Night sky." in its last pause
(coverage 0.33); its other two shots have no pause long enough even tersely, which is what its extended cut is for.
The held picture is made piece by piece (each stretch from its own seek, each hold from one frame, joined without
re-encoding): one filter graph reading the film several times buffered the whole film and was killed for memory on
a 23-minute film.

**Reduced motion** (`film.reduced_motion`): the film without what can trouble viewers whom movement unsettles: no
handheld drift, punch-ins or automatic reframing, camera moves held at their widest framing, no line boil, slides,
wipes and irises made dissolves, speed lines and impact bursts dropped; acting, timing and words unchanged. Built as
`<name>--calm`, copied to `build/final_calm.mp4` with its own QA and audio description. Camera movement is measured
from both files by phase correlation: dialogue-demo 2,340 px/s at the 95th percentile, 0 after.

**All aspects from one command** (`film.aspects`): 9:16, 16:9 and 1:1 rendered (re-staged, `film.render aspect`),
each with its own QA (17 checks on nib-hello, among them layout, the flash check and audio description) and a row
per aspect: its file, failed checks, ok. The described cuts of the other aspects are copied next to the master
(`final_ad_16x9.mp4`). The `access` test covers all of it.

## World languages (WP-25)
A language version is one command: `film.localize {"name": ..., "lang": "ar"}` makes `films/<name>-<lang>`. What it
needs is in `films/<name>/i18n/<lang>.json`, a translator's file that `film.strings {"name", "lang"}` writes: every
string a viewer reads or hears, by key (`line:<id>`, `shot:<id>:overlay:<n>:<field>`, `shot:<id>:set:board:<i>`,
`data:<path>` for chart labels, a line's own bubble text `line:<id>:bubble` (optional: without it the bubble shows
the translated line, never the source's), the title, brief and posting titles), with optional `"voices"` per speaker,
`"swaps"` (props by id, sets by name, clips), `"rules_off"` and `"digits": "native"`. A translation must keep every
`{{...}}` data binding (numbers come from data.json in every language; a dropped binding is refused); month and
weekday names in charts and data come from CLDR (Babel) when not translated. Numbers on screen and in words use the
locale's separators with Latin digits, or the language's own digits throughout with `"digits": "native"`
(Babel keeps Latin digits, so `dbe/databind.py` writes the numbering system's own; Chrome's Intl draws the same).

**Writing systems** (`engine/fonts/scripts.json`): a rounded font per script matching Fredoka's look, all OFL and
bundled as WOFF2 (about 2 MB): Baloo Bhaijaan 2 (Arabic), Baloo 2, Da 2, Paaji 2, Bhai 2, Bhaina 2, Thambi 2,
Tammudu 2, Tamma 2 and Chettan 2 (the Indic scripts), Varela Round (Hebrew), Mitr (Thai), Comfortaa (Greek and
Cyrillic), Jua (Hangul) and Noto Sans Sinhala; Han and kana, Myanmar, Ethiopic, Georgian, Armenian, Khmer and Lao use
installed Noto fonts. The player lists them after Fredoka and Patrick Hand (Latin keeps its own fonts) and loads the
ones a film's text uses before its first frame. Text other than Latin is measured in the fonts it is drawn in (canvas
measureText; counting letters made Sinhala signs overflow their boards and bubbles land on them, as vowel signs are
letters of their own); Latin keeps its one-per-letter estimate, so English layouts do not move. Lines are wrapped at
the words Intl.Segmenter finds in scripts written without spaces (Thai, Lao, Khmer, Myanmar, CJK);
typewriter reveals step by grapheme, so a vowel sign never hangs alone; shouted bubbles in joined or stacked scripts
are drawn whole, never a letter at a time.

**Right to left.** Every frame, text holding right-to-left letters gets `direction="rtl"` with its anchor flipped to
the same side (under rtl, `start` is the right end: measured in Chrome), so it reads correctly and stays in place;
films in a right-to-left language (`"dir": "rtl"` in shots.json, set by film.localize from CLDR) also lay
left-aligned text out from the right: cards, quotes, chart titles, source lines (mirrored across the frame) and the
classroom board; titles pop their words in from the right. Captions: libass shapes and orders Arabic only with its
own bidi (`Encoding -1`); in its default, VSFilter-compatible mode the letters came out unjoined and reversed, so
films whose lines hold non-Latin text use -1 and every caption is set in the script's Noto font (Latin-only films are
unchanged).

**Voices.** `voices/registry.json` now lists every Piper voice of forty world languages (115, read from their model
cards in November 2026 and classified the way the registry always has: trained from scratch on CC0, public-domain, CC
BY or Apache data is clean; fine-tuned from lessac (research licence) or with no licence stated is unclear;
non-commercial, share-alike, or fine-tuned from ryan (CC BY-NC-SA) is restricted), with Kokoro for English, Spanish,
French, Hindi, Italian, Japanese, Portuguese and Chinese, and a Sinhala Piper voice (MIT model, trained on OpenSLR 30,
CC BY-SA 4.0: restricted). Voices are fetched (checksummed) when a film uses them, or with `bash tools/setup.sh voices
de,uk`. film.localize picks the best voice for the language (clean first); one that is not clean is allowed in-house
and flagged at posting (film.provenance). Non-English Piper voices are loaded with their phoneme alignments, so lip-sync
follows the model's own timings: the Arabic version's lip-sync check failed (Ravi's mouth correlated 0.11 with his
voice, visemes spread over Whisper's word times) and passes with them (0.42). `locales.list` shows, per language, script, direction, fonts, OCR and the best voice
with its status: clean voices exist here for English, Hindi, Spanish, French, Portuguese, Italian, Japanese, Chinese,
German, Dutch, Czech, Greek, Ukrainian, Swedish, Norwegian, Telugu and Kazakh; every one of the forty can ship with
translated text and captions.

**Cultural rules** (`dbe/cultures.json`): gestures some audiences read as rude are swapped when a film is localised
(left-hand waves, points and presentations become right-hand ones for Arabic, Persian, Urdu and South Asian
languages; a pointed finger becomes an open palm for Malay, Indonesian, Thai and Filipino), and words a locale's
reviewers should look at (alcohol and pork, beef, dogs indoors, the number four, a thumbs-up) are flagged, never
changed: whether to change them is a person's decision. Each rule says why; they are defaults for review.

**Read back** (`film.text_check`, run by film.localize): every on-screen string (overlays, the set's words, bubbles)
and the first chunk of every caption is found in a frame where it is fully shown and read by Tesseract in its
script, in several views (grey, inverted, coloured lettering alone, the bright fill of outlined letters, two page
layouts; captions and titles cropped to their own band); its words of three letters or more must be found (75% alike
each, any order: OCR may put a number on either side of right-to-left words), and words that read better backwards
are reported as reversed. A bubble or caption that does not read in its first frame is read again a little later in
the same showing (up to three frames, the best kept), so one frame catching a bubble on its way in or out does not
fail it. Piper voices are seeded (`engine/piper_seed.py`): Piper's model draws its noise from unseeded random nodes,
so the same Sinhala line came out 24,832 to 26,368 samples long in three runs, and with each voicing the line times,
Whisper's words, caption chunks and the frames read moved (the l10n test failed on a different string, and once on
caption type size, in four runs). With the seed, the same script voices identically; a session continues its random
sequence from line to line, so it is the order of the lines that repeats. It caught three real faults on the way: the reversed, unjoined Arabic captions, Sinhala
bubbles still in English (a line's `bubble` text was not translated), and Sinhala signs overflowing their boards.

**The done-when.** `data-demo` in Arabic (`films/data-demo-ar`): Arabic voice (Piper kareem, unclear licence,
flagged), the board, chart title, month labels, source line and titles in Arabic, right to left, Arabic captions;
every QA check passes (lip-sync included) and all 9 on-screen strings and caption chunks read back. `nib-hello` in
Sinhala (`films/nib-hello-si`): Sinhala voice (restricted, flagged), sign and bubbles in Sinhala (the shout keeps the
original's short line), Sinhala subtitles (.srt, .vtt); every QA check passes and its 3 strings read back. The
`l10n` test makes both from scratch copies. Language versions carry audio description: its English sentences are
machine-translated (NLLB, recorded in provenance.json and flagged for review) and read by a voice of the language;
in Sinhala the opening description becomes a 5.8 s hold, since the Sinhala voice reads it more slowly than the
pauses allow. Bar charts run right to left in right-to-left films, and each version gets covers lettered in its own
script. **Open:** long bubbles in wide scripts wrap into tall, narrow bubbles (the row limit was tuned for English);
NLLB transliterates some names and verbs ("Nib hops" comes out as its sound in Sinhala
letters), so its description drafts need a reader of the language.

## Analytics and a plan that re-ranks itself (WP-31)
What each post did lives with the plan, in `plan/channels/<id>/analytics.json`: one record per post (a calendar row
on one platform, known from the row's `posted` links), with dated snapshots of its numbers (earlier reads are kept),
its retention curve and its countries. **In:** `analytics.import` reads the CSV a creator downloads from YouTube
Studio, TikTok Studio or Instagram's insights (headers matched by name; unknown ones are reported and can be mapped
with `columns`; a totals row is skipped; durations, percentages and thousands separators parsed), a country
breakdown (`kind=geography`) or one post's retention export (`kind=retention`), and matches each row to a post by its
link, the video id in its link, or its title; `analytics.youtube_api` reads the same numbers from the YouTube Analytics
API with the owner's token (production registry `connectors.json`; nothing ships with one). TikTok's and
Instagram's numbers come by export: their APIs need app review. Simulated numbers (`synthetic=true`, for rehearsals
and tests) mark their posts and can never be mixed with measured ones or teach a real plan.

**The 48-hour checklist** (`analytics.checklist`): each post's reads at 1, 24 and 48 hours and nine checks judged
against this channel: views against its median at the same age, the share that stayed rather than swiped, the hook's
hold at 3 s, percentage viewed, shares, saves, comments and subscribers per thousand views, click-through; each
check that needs attention names its action (the cold open, a hook variant, pacing, the payoff, the end card, title and
thumbnail). **Retention onto the film** (`analytics.retention`): the curve laid over the film's shots and lines, the
percent lost per second in each and against the curve's own smooth decay, the three places that lose most beyond it.
**Lessons** (`analytics.lessons`, E11): every mapped post pooled: hook hold by format, and whether faster lines lose
viewers faster, with the pace above which they do when the correlation is clear (r >= 0.4). **Hook tests**
(`analytics.hooks`): alternative openings (`variants.hooks`) posted separately, their hold compared with Beta
posteriors; a variant wins at 0.95, else the test says undecided. **Polls** (`analytics.poll`): a poll between a
film's true titles (titles.json, WP-07) within the platform's option count and length; with the votes, a Dirichlet
posterior picks the title at 0.9 and records it as chosen.

**Re-ranking** (`analytics.effects`, `plan.rerank`): a post's performance is log2 of its 48-hour views over the
platform's median (a doubling is +1), averaged over its platforms. The effects of fields, sweeps, formats, local or
not and calendar roles are estimated together by ridge regression (features that travel together, such as local
stories in one field, are told apart; each pulled toward zero as if by three pseudo-posts). Every idea's score becomes
its own score plus half its features' effects, explained point by point; `plan.rerank` plans the quarter with those
scores and as it would have been without them, under the same rules, and each row says why it holds what it holds:
unchanged, moved (its slot went to another idea and the rules placed it elsewhere) or entered the quarter, with the
measured reasons; the ideas that left are listed with theirs; plan.check checks the result. Per-feature means were
tried first: they could not tell the local effect from the fields it travels with, and scores clamped at 5 made the
explanations compare equal scores. **Business** (`analytics.business`, Studio page `/business`): revenue and views by
platform and country, RPM, revenue by month, the films that earn most, catalogue value (the last complete month's
revenue carried forward two years with the channel's own decay), and what performed; with no measured posts the page
says so (rehearsal numbers only with `?synthetic=1`).

**Rehearsal and the done-when.** No film has been posted yet, so there are no measured numbers: the `analytics` test
rehearses the whole loop in a scratch plan on simulated numbers (Q1 2027's 52 rows posted on three platforms, their
exports made with known effects: space & physics x2, the tool sweep x0.57, local stories x1.3, imported at 1, 24 and
48 hours): the effects come back with the right signs (+0.56, -0.23, +0.13 after shrinkage), Q2 is re-planned with 8
ideas entering, 35 moving and 8 leaving, every row explained and plan.check passing. Q2 2027's real calendar is planned
with `plan.rerank {"quarter": "2027-Q2"}` once Q1's posts have their 48-hour numbers (from April 2027).

## Provenance, disclosure and consent (WP-26)
**Content credentials.** Every `film.render` signs its finals (`film.sign`; shots.json `"sign": false` to skip): a
C2PA manifest (c2pa-python) embedded in final.mp4 and final_ad.mp4 with `c2pa.actions.v2` (created by Doodleberry;
IPTC digital source type `compositeWithTrainedAlgorithmicMedia` when a synthetic voice or model shaped the film,
else `digitalCreation`), `stds.schema-org.CreativeWork` (title, channel), `c2pa.training-mining` (generative training,
training, inference and data mining: not allowed), `org.doodleberry.provenance` (each voice with its licence status
and consent basis, models that touched the picture, the disclosure text) and `org.doodleberry.recipe` (E14: sha256 of
shots, script, timing, data, facts, score and sound; of every engine file; the commit; the hash of all frame keys and
twelve sampled frames' keys). The signer is the studio's own chain, made on first use in the production registry's
`keys/` (never in git): a root CA and an ES256 signing certificate it issues, with digitalSignature and the
document-signing and email-protection usages (C2PA refuses self-signed signers). `build/trust_anchors.pem` (the root)
is written beside each signed film. Read back with **c2patool 0.27.22**, the reference tool (`bash tools/setup.sh
provenance`): Trusted with the root as a trust anchor (`assertion.bmffHash.match`, `claimSignature.validated`,
`signingCredential.trusted`); without it, Valid with `signingCredential.untrusted` (a certificate from a CA on the
C2PA trust list can replace the studio's). A copy with 64 bytes changed reads Invalid (`assertion.bmffHash.mismatch`);
the QA check `content_credentials` holds every render to Trusted. **Timestamps**: `film.sign` with `timestamp` (an
RFC 3161 authority's URL) has the signature countersigned with the authority's time, so the credentials stay checkable
after the signing certificate expires. Test `timestamp` (only when asked: it reaches DigiCert's public authority,
http://timestamp.digicert.com): c2patool reads the film Trusted with `timeStamp.validated`, and the signed time is
0.4 s from this machine's clock.

**Recipes** (`film.verify`): the credentials, then the recipe against the film as it is now: which data and engine
files differ from what was signed, and the twelve signed frames re-made in the player (`tools/frame_keys.mjs`, the
same markup hashing as the renderer, plate included) composed into film-frame keys as the render composes them. On
nib-hello all twelve match; after the sign's text changes, shots.json is named and none match.

**Disclosure** (`film.disclosure`, in `film.package`'s posts and package.json): each platform's setting, on or off,
whether required, and the caption line saying what is synthetic, from `dbe/disclosure.json`, whose rules were read
from each platform's help page on 3 November 2026: YouTube's "AI use" is required only for realistic content
(animation exempt; C2PA content may be labelled automatically); Meta requires its AI label on "realistic-sounding
audio", naming a reel narrated with a realistic AI voiceover, so Instagram and Facebook get it for our synthetic
narration; LinkedIn shows a C2PA icon; TikTok's and X's pages could not be read here and are marked unverified
(TikTok's label is turned on with any synthetic voice, cautiously).

**Consent** (`consent.add`, `consent.revoke`, `consent.check`; `consent/records.json`): a record says who, a voice or
a likeness, which uses (commercial or not, platforms), from when, until when, and the hash of the signed form kept off
git. voice.build checks every voice before its licence: a stock synthetic voice stands on its licence; a voice made
from a person (registry `kind` clone, person or recording) needs a live record named in its `consent`, and a puppet
depicting a real person (`meta.likeness`) the same; nothing waives it (`allow_restricted_voices` concerns licences
only). The `provenance` test: a cloned voice with no record is refused, allowed once recorded, refused once revoked; a
record that starts tomorrow is not yet in force.

## Corrections, companions and living films (WP-27)
**One correction, everywhere** (`film.correct {"name", "key", "to", "why", "kind", "credit"}`): the text is changed by
its key (the keys `film.strings` lists: `line:<id>`, `shot:<id>:overlay:<n>:<field>`, `titles:<n>`, `thumb:<n>:top`,
and `fact:<id>` for a claim), logged in `films/<name>/corrections.json` with the date, what it said, what it says,
why, its kind (error, update, clarification) and who reported it, and carried to every surface: a line is re-voiced
and the film re-rendered (voice, burned-in and sidecar captions, its bubble: a line's own bubble text gives way to the
corrected line), a title or thumbnail line updates titles.json and the covers, the credits gain a dated corrections
section with thanks, the film's page (`film.page`, build/page/index.html: title, film, what it says, sources, credits,
the log with "what we got wrong" apart from updates and clarifications) shows it, and the posting package is remade.
Each surface is read back: the QA checks, the corrected words on screen by OCR (film.text_check), the title in
titles.json, the reason in the credits and on the page. A correction may not change a `{{...}}` data binding: wrong
numbers are corrected in the data (film.data).

**Companion guides** (`film.companion`): build/companion/ holds the film's analysis (scripts, sources.json, cached
source files), numbers.json (every number the film shows or says, with where: each binding in its lines and on
screen, every value of its charts) and guide.py with guide.md (the same, readable): it re-runs the analysis in a
scratch folder, checks each cached source against the sha256 recorded when the film was made, and prints every number
beside the number it gets. data-demo's guide finds its 8 numbers and reproduces all of them; with a cached source
changed it reports the sha256 mismatch and the numbers that differ.

**Living films** (`film.living`): the film's sources fetched again and its analysis re-run (film.data refresh); when
a number the film uses changes, the lines that say it are re-voiced, the shots that show it re-rendered, and a dated
update naming the numbers is logged (page and credits). **Send-a-myth** (`plan.intake`): a viewer's myth enters the
idea bank as an evergreen myth-vs-data idea with status `intake` (no sources yet, so the scheduler leaves it until
research fills it in), credited to the sender if named; the same myth again is counted on the idea, not added.
**Rebrand** (`catalogue.rebrand`, E30): the channel takes another brand kit and every film on the old kit (or the
house kit) moves to it and is re-rendered with its covers and package. The `living` test covers all of it on scratch
copies.

## Series production (WP-28)
A series is data in `series/<id>/`: **bible.json** (the format, a `film.from_template` one; the cast by role, each
with its puppet and voice; the posting cadence; the **props** that persist, each with an owner, the episode it first
appears in and the one it is lost in, its drawing and where it is held; the **running gags**, each a line for a role
and/or an acting direction with a cadence, every n episodes from one; and what the characters **learn**, a fact with
keywords and the episode a role learns it in) and **briefs.json** (each episode's title, topic, exchanges and facts
with their sources and quotes).

- `series.plan` gives each episode its number, its posting date from the cadence, the gags due, the props it carries
  and what each role knows by then (series/<id>/episodes.json) and writes schedule.ics.
- `series.make` makes each episode's film from the format and its brief, with the gag lines in place (an expert's
  rides on the last answer, a learner's before the button) and the persisting props held by their owners in every
  shot they are in. It writes the episode's research_log.md from its sources and the gate review, then voices, acts
  (the gesture planner, then the gags' acting directions) and renders. Continuity is then checked across every
  episode made.
- `series.gate` records a fresh fact-gate reviewer's verdicts per episode in series/<id>/gate.json, each tied to a
  hash of the facts it read. A verdict is carried to an episode's ledger only while those facts are unchanged; a
  changed fact needs a new review. Renders refuse an episode without a clearance (the research gate), as for any film.
- `series.continuity` (E16) reads the films themselves, so a hand edit is checked too:
  - the same puppet and voice for a role in every episode;
  - each persisting prop on screen with its owner from the episode it appears in until it is lost, and never before
    or after;
  - gags on their cadence;
  - nobody speaking of a fact before the episode they learn it, and the learner not asking again;
  - every episode within the length band.
- `teach.tutorial` turns a film's pipeline into a step-by-step tutorial (build/tutorial/index.md): the brief, the
  script, each character's model sheet, the voice, the acting, a frame of every shot, and the command behind each step.

**Ask Ravi** (`series/ask-ravi`) is ten weekly episodes on sky questions, each sourced from a NASA Space Place page.
It posts Thursdays from 7 January 2027. Momo carries a notebook from episode 2 and Ravi a star map in episodes 5 to 8.
Momo's notebook line runs every episode from 2 and Ravi's "Big word, small idea" every third. Momo learns what a
light-year is in 3 and what an orbit is in 6. The `series` test plans it, finds no break in the ten films as made, and
catches each of eight planted breaks: a re-voiced Ravi, a re-drawn Momo, the star map before it appears and after it
is lost, a missing notebook, a fact used before it is learnt, a gag off its cadence, and a question asked again.

## Library economics and creator packages (WP-29)
**Screen time per asset** (`usage.report`, E15) reads every film's shots.json and counts seconds for each:
- **puppet**: the shots it is in;
- **clip**: from its start to its end, its own length, or the shot's end for a loop;
- **set**, **prop**, overlay **icon**, and **boil** preset (style.boil_preset);
- **voice**: while its lines are spoken.

Overlapping uses in one film count once. A hand-coded film (scene.js, no shots.json) is one **scene** asset for its
length, and its voices are counted from its timing. A film still on narration slots counts its picture but no voice,
and is listed as planned.

Owners come from:
- the cast library (rights owner, or author) for puppets;
- the pack that installed a clip or preset (puppet/clips/packs.json);
- the voice registry for voices;
- the house, for everything else.

The report covers the whole catalogue (44 films when it was written). It names unregistered puppets and pays them nothing. It
writes out/usage/usage.json and usage.csv. With rates (per second by owner, else an asset's own royalty terms, else
by kind) it gives each owner's payout.

**Contributors** come in through `cast.add`, with their name as the rights owner, their licence, a `contact`, and
`royalty` terms ({per_second, currency}), which the usage report pays.

**Creator packs** (`pack.make`, `pack.install`; dbe/packs.py) are zips with pack.json: the kind, id, version,
author, licence, royalty, what they need (template, puppet format) and a sha256 for every file.
- A **rig** template (a rigged .puppet.json) installs into cast/packs/<id>/. It is linted there with the receiving
  project's own loader and template, then registered in that project's cast library with the pack it came from.
- A **loop pack** (clips for a template) installs into that template's clip library (puppet/clips/<template>.json and
  .js, which the bake and every renderer read), each clip marked with its pack. A clip name already taken by
  something else is refused.
- A **boil preset** installs into presets/boil/ and is put on a film's shots with `boil.apply`, which records it so
  its use is counted.

A pack changed after it was made fails its hash and is refused.

The `library` test checks the catalogue report, a contributor's payout, and three packs made here and installed into
a second checkout (a git worktree in out/). There, its own `cast.list` lists the rig and its own bake.mjs plays the
installed hop loop on the installed rig (the torso swings 0 to 9 degrees on the clip's beat). Both projects credit
all three to their author with the pack's royalty, and a tampered pack and a clashing clip are both refused.

**Handwriting fonts.** `font.sheet` prints an A4 sheet at 300 dpi: one box per character with its label, a
baseline and an x-height line in a light blue that drops out of a scan, and corner squares for registration.
`font.from_samples` takes the filled sheet, scanned or photographed:
1. finds the corner squares and warps the page back to the sheet;
2. keeps each box's ink (the guides fall below the threshold) and removes specks;
3. traces each box with potrace (vendored 1.16, built by `vendor.build`);
4. places each glyph on its box's baseline at the font's x-height, with bearings from its ink;
5. builds an OpenType (CFF) font with fontTools, crediting the artist in the name table, and writes a preview.

The `handfont` test uses synthetic samples. It fills a sheet with Patrick Hand glyphs (OFL), jittered and
photographed at an angle with tint, noise and blur. Every character comes back, and each glyph matches its sample
as written: mean shape IoU 0.89, worst 0.77. Letters sit on the baseline (median bottom 3.5 units) and x reaches
476 of the 500-unit x-height.

## Other mediums (WP-30)
Each export works from the film's data alone.

**Comics and storybooks** (`film.comic {"name", "kind": "comic" | "storybook"}`, dbe/comic.py, Typst 0.14 through
typst-py):
- Every voiced line becomes a panel: the player's frame at 60% of the line, drawn without its speech bubbles or
  captions (`?bubbles=0`). It is cropped at 4:3 around the characters, with room above the highest head.
- The line is set as a balloon whose tail points at the speaker's head (the player reports each head's screen
  position in `window.HEADS`); a narrator's line is set as a caption box. A shot with no lines gets a silent panel.
- A comic puts six panels on an A4 page in Patrick Hand. A storybook puts a title page and then one picture per square
  page, with the words below in prose ("..." said Momo).
- The PDF is read back: every line's words must be in it, with one picture per panel.

**Interactive web films** (`export.interactive`, dbe/player/interactive.js): the player draws the film live beside a
panel built from its data:
- chapters, one per shot;
- the transcript, highlighted word by word (tap a line to hear it);
- a pause after every question, with "What do you think? Have a guess, then hear the answer";
- each line's source from facts.json, and the list of sources.

Scripts, the Fredoka font and the soundtrack are inlined or copied beside the page. `window.IFILM` exposes seek, play,
pause and state, and the export is driven in Chromium to check it (tools/interactive_check.mjs). Building it also
fixed `export.web`: since the world-script fonts arrived (WP-25) its page linked fonts by a path that does not
resolve from build/web/, so the page never became ready. The fonts are now copied beside the page.

**Godot** (`export.godot`, dbe/godot_export.py) writes a Godot 4.5 project:
- a scene per shot: the set as a plate, every part and swap drawing as a Sprite2D whose texture is that drawing as an
  SVG in the puppet's artboard, and an AnimationPlayer with a transform track per drawing from the bake (camera folded
  in), plus visibility and z_index tracks where swaps, views or layer order change;
- main.tscn with a script that plays the shots in order with the sound (Ogg Vorbis).

The set is a video (Ogg Theora, which Godot plays itself) drawn by the player frame by frame, so the set's own life
and each character's ground shadow move as in the film; a still plate is used only if the video cannot be made (a
still plate had left a walking character's shadow where the shot began).

Two checks. An independent reader of the .tscn evaluates the tracks and composes three frames, which renderer
parity's measures compare with the player's (pip-park s1: line F-score 1.0, filled silhouette 0.92 to 0.97). And,
where Godot is installed (`bash tools/setup.sh godot`: the official 4.5-stable build, SHA-512 checked, in
/opt/godot), the engine itself imports the project headless and renders the first shot with Movie Maker under Xvfb
(software OpenGL 4.5, llvmpipe); three whole frames against the player's: pip-park s1 differs by 0.85 to 1.9 levels
on average, 0.2 to 1.2% of pixels by more than 32 (Theora's compression of the set, and anti-aliasing), line
F-score 1.0. 171 frames take about 35 s.

The `mediums` test covers dialogue-demo as a comic and an interactive film, and pip-park as a storybook and a Godot
project.

## Team roles and permissions (WP-39)
Every command goes through one check (`dbe.call`, dbe/team.py) whichever door it comes in by.

**Who is acting**: the CLI and the MCP server read `DBE_AS`; the HTTP API reads the `X-DBE-As` header. The value is
`"<id>"`, or `"<id>:<role>"` to act in one of that person's roles. team/people.json lists the people and agent sessions
(`team.add`); each agent session gets its own id and role. With no people file and nobody named, the local user is the
owner, so one person working alone loses nothing.

**Roles** (team/roles.json) are command patterns, plus the read commands everyone has:
- owner: everything;
- director: everything except consent records, environment builds and team membership;
- artist: characters, levels, drawing, fonts, packs and stickers;
- reviewer: notes, critic packs and gate verdicts;
- editor: renders, cuts, sound, exports and delivery.

Sign-off commands (post.approve and revoke, prod.approve and decide, film.sign, series.gate) run only for roles that
list them. `post.approve` records the acting person's name.

**Assignments and locks** (team/state.json, machine-local) apply to a film or a character:
- `team.assign`: only the assignees, the owner and directors may then change it;
- `team.lock`: only the holder may change it until `team.unlock`; the owner may break a lock.

A command's target comes from its arguments: a film's `name`, a puppet `path`, or a cast `id`.

**Audit** (team/audit.jsonl, machine-local; `team.audit` filters it): every change and every refusal is logged with
time, who, role, door (cli, http or mcp), command, target, an argument digest and the result. Reads are not logged.
Internal steps of an allowed command run as part of it.

The `team` test checks, in a scratch team folder:
- an artist saves a character, but post.approve ("signs something off") and film.render are refused;
- a director's approval passes the check;
- a lock stops another artist until the owner breaks it;
- an assignment keeps the other editor off nib-hello;
- an unknown name is refused;
- over HTTP, the header names the artist;
- the audit holds all 15 changes and refusals and no reads.

## The director's desk (WP-21)
`desk.say {"name", "text", "apply"}` reads notes in plain English, sentence by sentence (dbe/desk.py). It routes each
one to the commands that make the change:

| kind | say | what changes |
|---|---|---|
| line | "Change Ravi's first line to "..."" | script.json; the voice is rebuilt, the shots re-timed and the acting re-planned |
| timing | "Hold shot 2 a second longer", "Make shot 1 half a second shorter" | a pause after the shot's last line, or the tail of the last shot |
| camera | "Push in on shot 1", "Go wider on the last shot" | the shot's auto-camera framing (hand-set camera keys are left for the timeline) |
| set | "Put shot 2 in the park" | the shot's set (one of the known sets) |
| music | "Make the music calmer", "livelier" | the score's tempo, 14 bpm a step, kept between 70 and 140 |
| acting | any sentence naming a character and an action | `acting.direct` |
| preview | "Show me" | the storyboard and animatic |

A sentence of no known kind comes back as not understood. Nothing is guessed.

With `apply` false, the desk only says what it would do (a dry run). Every routed command runs as the person or agent
at the desk (WP-39), and the first refusal stops the rest. Each exchange is kept in films/<name>/desk.json: what was
said, understood, run, refused and not run. Studio `/desk` puts the notes beside the storyboard strip and the animatic,
with an "Acting as" field (the `X-DBE-As` header).

Roles for the specialist agents (team/roles.json):
- animator: acting, timeline, act it out, physics, shot renders and previews;
- critic: notes, critic packs, critic rounds, QA reads;
- fact-checker: research, gate verdicts, `series.gate`, corrections and living data.

The `desk` test uses a copy of dialogue-demo. The director's three notes change Ravi's line (re-voiced: timing.json
has the new words), the shot's length, its camera, its set (the park), the music (96 to 82 bpm) and Priya's acting
(a shrug), then make the storyboard and animatic. "Make everything purple" is not understood. The artist's note to
change a line is refused at `film.write`, and nothing after it runs. Each of the seven roles is refused one command
outside its subset.

## Act it out 2 (WP-12)
- **Head turn.** The nose's offset between the ears (or the eyes) gives the performer's yaw in the picture. About 45
  degrees counts as a full turn, and looking toward the right of the picture is positive. For a character with a
  `turn` control, the yaw becomes a **clip control track** (`"controls": {"turn": [[t, v], ...]}`, puppet format
  v0.10). While the clip plays, the track is weighted like an additive layer and added to the timeline's own control
  keys. Controls resolve into angles, shifts, swaps and layer order inside acting.js, so the bake and every renderer
  follow. Puppets that gain a clip with controls are marked v0.10.
- **A moving camera** (`stabilize`: auto, on or off). Corners outside every person's box are tracked frame to frame
  and back (pyramidal Lucas-Kanade; tracks that do not return within half a pixel are dropped). The median motion of
  the rest is the camera's, which `stabilize` subtracts from every point, so the root's travel is the performer's
  own. A frame with less than a fifth of the picture outside the people, or fewer than 20 good tracks, is not
  trusted. "auto" takes the motion out only when it is over 20 px and at least 80% of frames are trusted; otherwise
  it says the camera was taken as still.
- **Several people** (`people`: up to 4). `detect` keeps every pose and `split_people` follows each person's hips and
  shoulders from frame to frame (the closest assignment over all orderings), numbering people left to right as first
  seen. Each person becomes a clip (`<name>`, `<name>_2`, ...), on `puppets` if given.

The `actout2` test uses synthetic takes:
- A head turn comes back as a turn track (mean error 0.04), and Pip's bake turns its face 15 px at the peak.
- A 240 px pan, drawn as video over a textured background, is recovered to within 0.75 px. Root travel is 265 px
  raw and 2.7 px once stabilised.
- Two people, listed in shuffled order, come back as their two clips (1.1 and 1.2 degrees).

A real take of a performer filling the frame in front of a plain wall gives a turn range of -0.74 to 0.06. Its camera
estimate is refused (0% of frames trusted) rather than guessed: the earlier phase-correlation version had read 433 px
of motion that was not there.

**Live** (http://127.0.0.1:8770/live, `bash tools/setup.sh live` once). A character follows the webcam in real time.
MediaPipe Pose Landmarker runs in the page (`@mediapipe/tasks-vision` 1.2.0, WebAssembly on the CPU, the same
`pose_landmarker_full.task` act-out uses, served from the models folder at `/models/`). Each frame goes through the
act-out retarget, one frame at a time: the bone directions minus the rest directions `actout.rest` reports for that
character give world angles, and each part's angle is its world angle minus its parent's. The same clamps apply
(hands within 45 degrees, the part's limits, the head's roll within 40). A One Euro filter smooths each angle (none,
some or lots). A part out of sight for a second eases back to rest. Live stays in place and only the head's roll
reaches the face; record a take in Act It Out for travel, contacts and face drawings. `?video=` plays a file instead
of the camera, `?puppet=` picks the character.

The `live` test checks it two ways. First, synthetic takes (forward kinematics through Ravi, 1.5 px noise) go through
the page's per-frame solve, unsmoothed. The angles come back within 1.33, 1.10 and 1.01 degrees mean (wave_R,
celebrate, shrug; worst frame 4.3). Second, Chromium's fake webcam plays a COCO photo of a whole person (padded to
720 x 1280). MediaPipe in the page and Python MediaPipe on the same frames, both through the page's solve, agree to
within 0 to 1.6 degrees per part, median over the frames. Their landmarks differ by 0.2% of the frame. A pose takes
120 to 260 ms per frame here (software, 4 cores, two runs). That is 4 to 8 frames a second, so the page drops frames
rather than falling behind; a laptop's GPU delegate is faster. Per frame, the detector itself wavers on an ambiguous
wrist (one forearm read from 25 to 3 degrees over 20 frames of a still photo), which is why the comparison is per
part, over the frames.

## Acting intelligence 2 (WP-10, part 1)
**Personality profiles** (cast/profiles.json, E13) shape the gesture planner (`acting.plan`):
- tempo (gesture speed) and energy (beat size and gain);
- the least gap between gestures and beats per words;
- what an exclamation, a question and a point become (a shy character only glances);
- how strongly it nods while listening, and how far its eyes drift off the speaker;
- clips it never plays, and its reaction in a stare.

`neutral` keeps the planner's earlier gesture choices. The others are shy, excitable, calm, grumpy and thoughtful.
Every profile now also holds the emotion each line's words carry on the face, and has listeners react to it. A character's
profile comes from the film (`script.json` `speakers.<id>.profile`), its puppet (`"acting": {"profile": ...}`) or its cast entry
(`cast.profile`).

**Semantic gestures** (`acting.tag`): an agent tags words with gestures by meaning (big, think, no, yes, wow, oops,
cheer, unsure, point, present, ...) or by clip name. Each tag is checked against what the character can play (its
template's library and its own clips, through the semantic table for its template) and against its profile, and
refused with the reason and the valid names. Accepted tags are kept on the script's lines, and the planner places
them on their words before anything else.

**Camera beats in gags**: a stare is a line marked `"beat": "stare"`, or, with `gag_beats` in the script, a pause of
0.8 s or more after an exclamation, question or trailing off. During it the auto camera holds on whoever reacts and
pushes in (`camera_auto.beats`), and the reactor plays its profile's reaction clip.

**A blind critic** (`critic.blind_pair`): two versions of a scene as contact sheets at the same moments, ordered by a
coin, with the key kept outside the packet.

The `acting2` test uses copies of dialogue-demo:
- With the profiles swapped, Ravi moves 4.7 against 1.6 and Priya 8.2 against 1.7 (mean angle change per frame,
  excitable against shy), and a shy character never points, opens its palms or celebrates.
- Of three tags, "big" is placed on its word, "point" on shy Priya is refused, and "moonwalk" is refused.
- A marked stare pushes the camera in on Ravi from zoom 1.9 to 2.45.

The blind pair was **lost** twice, each time judged by a different fresh critic. clips-demo (hand-keyed) was set
against the planner, with an excitable Momo, a calm Ravi and three agent tags.
- **Round 1 (26 to 17):** the planner put the jump on "I did it!" and the sad tilt on "Oh no", but left both
  characters near neutral between gestures, held no emotion and gave the listener no reaction.
- **Changes after round 1:** the planner now reads each line's emotion from its words and holds it on the face
  through and after the line. Listeners mirror it and react (consoling a sad line, clapping a happy one).
- **Round 2 (25 to 19):** better, but a body preset per emotion read as a stiff held pose, and a hand on the tail gave
  the gag away. The presets were then removed; that version has not been judged.

The verdicts are in out/critic/blind_keys/.

**Blind comparisons repeated** (4 Nov 2026). The same procedure (`critic.blind_pair`, a fresh critic per packet, the
packet copied to a neutral folder so its path does not tell which is which, the key read only after the verdict) on
two more scenes. In each, the planner's version is the scene with its hand-keyed gestures removed and `acting.plan`
run on it:
- direct-demo: hand-keyed preferred, 27 to 21 (acting 7 against 5, timing 6 against 6);
- review-demo: hand-keyed preferred, 27 to 17 (acting 7 against 5, timing 7 against 4).
Both critics named the same gaps:
- the planner's point lands on the pointing words, late in the line;
- there is no reaction beat after the punchline (the hand-keyed versions have a sheepish head-scratch);
- the character denying stands neutral through the denial.
With the earlier single win on clips-demo, the planner stands at one blind win in six. Not met on these scenes.
Then the first gap was fixed: a point now rises with the clause, up to 1.5 s before the pointing word (never before
the line or a gesture still playing), and is held to the line's end. In a question it stays a quick point on the word.
A third fresh critic on review-demo still preferred hand-keyed, but 27 to 22 (was 27 to 17). It called the planner's
held point on "behind your back" more direct than the hand-keyed one. It faulted the ending: Momo points flatly on
"That telescope" with no sheepish head-scratch. That critic saw a version where Ravi also held a point through his
opening question; that is what made questions keep the quick point. One blind win in seven.

**Denials and punchlines** (5 Nov 2026). The planner now acts the other two gaps (`dbe/gestures.py`):
- a denial: a plain no ("no", "not", "never", "didn't"...) shakes the head on the word; pretended ignorance, the other
  speaker's word echoed back as a question ("Telescope? What telescope?"), shrugs from the first word through the
  line (and drops the question's end shrug);
- the punchline: the scene's last line said as an admission ("Oh. That telescope.", an opening interjection) gets an
  open hand toward the listener after the interjection, held through the line, then a sheepish head-scratch after it;
  the listener holds a long look at the one caught out instead of nodding.
`acting2` checks both on a scripted exchange. Blind rounds 3 and 4, fresh critics, packets in neutral folders, keys
read after (out/critic/blind_keys/):
- round 3 (head-scratch in, no gesture on the admission; Momo's point on "That" removed): hand-keyed preferred twice,
  23 to 19 on direct-demo and 26 to 22 on review-demo. Both critics saw the head-scratch land at the same moment as
  the hand-keyed one and credited the hand-keyed arm held out on "Oh. That telescope." as owning up.
- round 4 (an open hand on the admission instead): review-demo **won by the planner**, 24 to 23 (its point aims at
  Momo on the right words; the hand-keyed one swings toward the board first); direct-demo lost narrowly, 27 to 25
  (the hand-keyed Momo glances back with an open mouth before "Oh"; the planner's stands still through "Oh").
The planner stood at two blind wins in eleven. What critics asked for next: a reaction before the admission (the
caught glance), more personality in the accuser, and less static tails after the last line. So:
- caught out: as the accusing line ends, the one accused starts (a surprised face and clip), the eyes dart away and
  come back in the pause, and the face turns worried before the admission;
- the accuser stands confident on the accusing line, then folds the arms (after a point held to the line's end) and
  keeps them folded through the admission;
- tails: after the punchline the one caught grins, glances away and back, then shrugs; the accuser, after the stare,
  shakes the head slowly and a smile breaks.
`acting2` checks the timing of all three on the scripted exchange. Round 5, fresh critics, new coins: the planner won
**both**, review-demo 28 to 21 (the start "on 'back'" and the folded arms "read clearly as an unimpressed 'I'm
waiting'"; the hand-keyed Ravi "stands with his arms limp through the payoff") and direct-demo 27 to 23 (the folded
arms give "a clear, patient-but-unimpressed manner"; the planner's Momo "uses the 1.2 s pause before 'Oh.' better").
Still faulted in both: Momo's open hand on "That telescope" reads as pointing away. So when the accusing line puts
the thing on the one accused ("behind your back", "in your pocket", `ON_ME`), the admission's open hand goes toward
it, away from the listener, with a look round at it on the word and back to the listener by the line's end (`acting2`
checks it). Round 6, fresh critics, coins flipped (the planner was Version 2 both times): the planner won **both**
again, review-demo 28 to 22 and direct-demo 28 to 21 ("pulls the telescope round on 'That telescope'"; the
hand-keyed arm held out "points away from the prop"). The planner stands at six blind wins in fifteen, and has won
the last five of six.

## Sound depth (WP-13, part 1)
**Footsteps by surface.** engine/audio.py synthesises a step for each floor:
- grass: a soft-onset brush of noise and almost no thump;
- tile: a hard heel click with a ringing tile body;
- wood: a hollow knock around 250 Hz;
- concrete: a dull thump and a gritty scuff;
- carpet: only a muffled thump.

Automatic foley tags each step cue with its shot's set's surface (sets/acoustics.json).

**A room per set.** Each set names a room (outdoors, small room, classroom, clinic, hall: a reverb time and how wet
effects and voices are). The mix feeds each room's reverb only its own stretch of the film, with 0.05 s crossfades,
so a hall's tail rings on past a cut into the park. A film whose sets have no entry is mixed exactly as before.

The `sound2` test:
- Eight steps per surface, compared by log-mel spectrum: every pair is told apart by 25 to 152 times the steps' own
  spread, and grass brushes in over 6 ms where tile clicks in 0.1 ms.
- The outdoor room falls 30 dB in 0.16 s, the hall in 0.68 s.
- In a foley-enabled copy of pip-park, all of Pip's steps land on grass and the park's outdoor room goes to the mix.

Open: recorded voice-over into slots, checked against hand-marked timings; prosody direction (done since: see
Prosody direction).

**Recorded samples** (WP-13). `sound.import_pack` copies a folder of recordings into `assets/external/sounds/<pack>/`
(not in git) and records it in `assets/sounds.json` (in git): every file's sha256, the licence and its class, and
which cues the pack stands in for (`"step/grass": "kenney-impact:footstep_grass"`, `"thud": ...`). `sound.samples`
says which packs are here and intact. A film plays them only when its score says `"samples": true` (or lists pack
ids). Then a mapped cue plays the recording, mono, at 48 kHz, its leading silence trimmed, and levelled like any
effect. A group's variants take turns in cue order, so the choice is a pure function of the cue list. A file whose
hash no longer matches is skipped, and its cue is synthesized as before. Unmapped cues (tile steps, pops, whooshes)
stay synthesized. `build/samples_used.json` lists what played, and `film.provenance` lists each pack used with its
licence class for the posting gate. Without `"samples"`, the mix is unchanged.

The pack here is Kenney's Impact Sounds 1.0 (CC0, 130 files: footsteps on carpet, concrete, grass, snow and wood, and
21 kinds of impact). kenney.nl refuses downloads from this container. So the files came from a copy on GitHub and
were checked against Kenney's own zip, downloaded on the owner's machine by the Remote Control helper. Ten of the 130
sha256 hashes were compared one by one across ten groups and all matched. Both copies hold 128 distinct files with the
same two duplicate pairs. The copy had renamed `impactBell_heavy_000` to `impact_bell_heavy_000`; the library keeps
Kenney's names.
Test `samples` uses a 7 s music-and-effects film with four grass steps, two wood steps, a thud and a pop:
- with samples on, the four grass steps play four different recordings and the two wood steps two;
- the recordings are told apart (spectral centroid 3.4 to 4.2 kHz on grass, 0.29 to 0.32 kHz on wood);
- the pop stays synthesized, the mix holds -14.0 LUFS and -1.6 dBTP, and the posting gate lists the pack (CC0, not
  flagged);
- with samples off, nothing is listed.

## Bubbles and text, finished (WP-17)
- **Thought clouds**: a script line with `"style": "thought"` is drawn as a cloud with round bumps all the way round,
  trailing three shrinking puffs to the thinker's head.
- **Narration boxes**: a line with `"style": "narration"`, or (in a cut with `narration_boxes`, which the sound-off
  cut turns on) any line whose speaker is not on screen, is typed into a caption box at the top of the safe area.
  The sound-off cut then shows no separate captions.
- **Typewriter pauses**: letters typed out (silent bubbles, custom bubble text spread over a line, narration boxes)
  pause after punctuation: a comma, semicolon or colon holds four letters' time, a full stop, ! or ? eight. Voiced
  bubbles still reveal word by word with the voice.
- The reading-time rule now covers a sound-off cut's bubbles, thoughts and narration boxes: each needs words / 3 + 1 s
  on screen on the cut's own clock. The cut is rendered through `film.heal`.

The `text2` test uses zz-text, a copy of dialogue-demo with a narrator line first and a thought of Priya's. In the
middle of each line its sound-off cut draws a narration box for the narrator, a thought for Priya's thought and
speech bubbles for the rest. The narration's typed letters hold at "One afternoon," for three of forty ticks.

## Templates: a quadruped, a bird and an object with a face (WP-16, part 1)
`puppet/examples/make_critters.py` writes three new templates (puppet/templates/), their clip libraries
(puppet/clips/, read by the player and the bake) and an original character for each, drawn from shapes:

| template | character | parts | clips |
|---|---|---|---|
| quadruped | Biscuit, a dog | body on the hips, head, two ears, a tail, four two-part legs (far and near) | idle, walk (a trot), wag, bark (the mouth opens), sit, talk |
| bird | Pim | round body, head with a crest, a beak that talks (the mouth swap), two wings, a tail, two thin legs | idle, flap, hop, peck, talk |
| object | Kettle, a teapot | a body that carries the face, lid, spout, handle, optional stubby arms | idle, bounce, wave, whistle (the lid rattles), talk |

They are ordinary cut-out puppets, so every tool draws them. The `templates` test lints each against its template and
plays its whole clip library in one shot. Renderer parity then holds against Synfig, Lottie and Grease Pencil: scores
of 0.991 to 1.0, and fills identical. Parity's colour check now looks a pixel in from every edge. A pale fill inside
thick dark ink (Kettle) had read as 24 to 27 levels off along every outline, though its fills match exactly; a
deliberately recoloured render still reads 38.

## Raster parts to vector (WP-14, WP-33)
`puppet.vectorize {"path"}` traces a puppet's raster parts (and swap drawings and views) into filled vector shapes,
written beside it as `<name>.vector.puppet.json`. Flat art (its opaque pixels fit within six colours, mean error under
14 levels: line art and cartoon fills) is traced one colour at a time with potrace, the largest colour first;
painted art goes through vtracer in colour mode, stacked, with colours merged to 5 bits a channel. Each colour
becomes a palette slot (`vec0`, ...), so palette variants recolour it. Both tracers are the vendored sources built
with their own recipes (`vendor.build`: potrace 1.16's configure and make, vtracer 0.6.5's cargo build), built on
first use.

Test `vectorize`: Nib (raster line art, 263 KB) becomes one ink colour in 76 KB; in the player the vector Nib covers
the raster Nib's pixels (filled-silhouette IoU 0.994 to 0.999 through a walk-in, hop and talk); Grease Pencil, which
refuses the raster Nib, draws the vector one, and Synfig, Lottie and Grease Pencil pass renderer parity (0.889 to
0.992). A painted disc (hue round the circle, light to the edge, brush noise) goes through vtracer as 167 shapes and
covers the same pixels (IoU 0.984).

## Anatomy plates (WP-16)
`{"type": "plate", "plate": "heart" | "brain" | "lungs", "x", "y", "w", "labels": [{"at": [u, v], "text", "side",
"start"}]}` shows an anatomy plate from Servier Medical Art (CC BY 4.0) on a card. Each label is joined by a leader
line to its point on the drawing (`at` is a fraction of the image) and appears at its `start`; a label is kept
inside the frame. The plate's credit sits under the card, and `film.credits` adds the source, licence and changes
for every plate a film shows; the audio description names the drawing and its labels. The images are not committed:
assets/plates/plates.json lists each with its URL, size and sha256, and `plate.fetch` (or `bash tools/setup.sh
plates`) downloads them into assets/external/plates/ and refuses a file whose hash has changed. Test `plates`: the
brain plate's image fills half its box in the real player (not an empty card), its labels are absent before their
time and drawn after, and the credits and audio description name it.

## Outfits as swap sets (WP-16)
A generated character can carry outfits: `cast.generate` spec `"outfits": {"coat": {"top": {...}, "bottom": {...}},
"gown": {...}}`. Each outfit is drawn by the generator like the character's own clothes, and every body part it draws
differently becomes a swap that replaces the part while the outfit is worn, with its own palette slots for the
colours it changes (`coat_cloth1`, ...). The puppet's `meta.outfits` lists, for each outfit, the swaps it selects; a
shot's cast entry picks one with `"outfit": "coat"`, which the shot loader turns into the timeline's `set` keys.
The puppet format is unchanged: swaps that replace a part (as hand poses do) already reach the player, the bake and
every exporter. Test `outfits`: a character with a coat (jacket, trousers) and a gown (a dress) lints clean; a shot
in each draws alike in Synfig, Lottie and Grease Pencil (1.0); against its own clothes the torso changes (mean
difference 50 and 73 levels) and the face does not (0).

## Kenney prop library (WP-16)
Kenney's Generic Items (CC0) is 163 sprites named only by number, so each was labelled by eye from its drawing (on
light and dark grounds, since some are white): `assets/props/kenney-generic-items.json` holds each item's number,
label, category (kitchen 28, tools 23, computer 18, electronics 16, medical 14, travel 14, stationery 13, camera 10,
household 7, science 7, games 4, money 4, art 3, icons 2) and the sha256 of its file; nine that could be read
otherwise are marked `unsure` (a caulking gun, a camera boom, a tripod head, a closed laptop, a handheld device, an
e-reader, a flashlight, a patterned bowl, a glue gun). `props.import_kenney {zip}` unpacks a pack downloaded from
kenney.nl on the owner's machine into `assets/external/kenney/` (not in git) and checks every file against the index
(this copy was fetched here through the page's own download flow, which imitates a browser; that is not repeated, so
the other packs wait for the owner's downloads). `props.library {query, category}` searches the labels; `props.make {item, r, x, y}` turns one into a shots.json prop
(its drawing as the body, its largest side 2r), to attach, path or drop like any prop (SVG renderer: a prop with its
own drawing). Test `kenneyprops`: 163 items, every file matching; a teapot made this way into a pip-park copy shows
10,315 pixels of its blue where it stands, none elsewhere and none without it.

## Open Peeps (WP-16)
`cast.import_peeps` (with `"fetch": true` to download first; CC0, by Pablo Stanley) turns openpeeps.com's per-peep
SVGs into one puppet. The site offers only finished peeps, not the parts kit, which is a Sketch or Figma file behind
a Gumroad checkout that asks for an email. But every finished peep is the same 240 x 324 bust, with its pieces in
named groups at fixed offsets: `body/`, `head/` (head with hair or hat), `face/`, `facial-hair/`, `accessories/`.
So reading all 49 recovers the kit, each piece once and already placed: 22 bodies, 30 heads, 18 faces, 9 facial hairs
and 7 accessories (plus "none"). The puppet (doodle template) is hip -> body -> head -> face, beard and glasses. Each
category is a swap set replacing its part: `outfit`, `hair`, `expression`, `beard_style`, `accessory`. A pose or cast
entry mixes them by name (`{"hair": "Turban", "expression": "Smile-Big"}`). Ink is the palette's `ink`, the white
fill `paper`. `meta.sources` lists every SVG read, with its sha256. The format is unchanged: replacing swaps already
reach the player, the bake and the exporters.

Test `peeps` (skipped when the SVGs are not here): the puppet lints clean, and four peeps rebuilt from its swap sets,
drawn by the loader, match their own SVGs drawn by Chromium. Ink IoU is 0.997 to 0.9996, white areas 0.998 to
0.9996.

**The full kit.** The owner downloaded the Gumroad kit ("Flat Assets") on their machine. Its "Separate Atoms" are one
SVG per piece on a shared canvas per category. The same 166 files are on GitHub (jenshor/open-peeps). The helper
session hashed the owner's copy, and 22 of those hashes, from every folder, were compared with the GitHub copy: all
equal, with the same count in each folder. That copy is in `assets/external/openpeeps-kit/` (not in git). Each atom
goes into the bust at the scale the site's busts use (150/710) and each category's offset, and lands within 0.06 px of
the site's piece. `cast.import_peeps` uses the kit when it is here: 30 bodies, 46 heads, 30 faces, 17 facial hairs
(with none) and 9 accessories. The `peeps` test rebuilds the same four site peeps from the kit puppet (ink IoU 0.989
to 0.998). The site calls one face "Smiling", which is the kit's "Smile"; the test matches it by its drawing.

**Talking and gesturing peeps.** The kit draws each face whole, so for lip-sync each is split at its nose (the piece
almost every face shares): what starts below it is the mouth. The faces lose their mouths, and a `mouth` swap set takes
the kit's own mouths for the visemes (closed from Serious, small Cute, mid Concerned Fear, wide Explaining, O Cheeky,
F/V Hectic's teeth, smile Smile, frown Solemn; the faces share one frame, so a mouth from one face sits right on
another) and each face's own as `rest-<face>`; a layer set per face picks the face with its resting mouth. The bust
bodies draw their arms into one outline with the body, so arms are added: original ones in the kit's manner (a white
sleeve and hand, a heavy black line), hung from each shoulder behind the body. The arm parts draw nothing themselves;
their drawings are swaps that a gesture clip shows while it plays, so no arm shows at rest, even through an outfit's
gaps (a mug, hands on hips). The humanoid arm clips (point, wave, present, open palms, shrug) are copied in, and the
puppet's `acting.gestures: "humanoid"` lets the gesture planner use them. An outfit with arms drawn at its sides keeps
them, so while a gesture plays that side shows two arms. Renderers: the kit draws everything as filled shapes with
even-odd holes nested to any depth, which Synfig and Grease Pencil (and the USD export) took as one outline with holes;
they now split an even-odd fill by nesting (`evenodd_groups`: a contour inside an even number of others fills, inside
an odd number cuts, each hole going to the smallest contour round it). Test `peepstalk` (only when asked): all 30
faces split, nothing left below a nose; the eight mouths change nothing above the nose (0 px) and the closest two
differ by 89 px; across 30 outfits a rest frame with arms equals the one without, pixel for pixel, while a point, a
wave and a present bring out 14,473 to 17,326 px of arm; the planner gives a peep a point and open palms; Synfig,
Lottie and Grease Pencil draw a pointing, talking peep as the SVG renderer does (parity 1.0, 1.0, 1.0; before the
even-odd fix Synfig and Grease Pencil were 85.6 and 37.9 levels off in colour). Sana's hijab (one hole) is unchanged
(parity 1.0, colour 0).

**Full-body peeps** (`"body": "standing"` or `"sitting"`). The kit's 34 headless poses (23 standing, 11 sitting)
get the head on top at the kit's own full-size layout. That layout was read from the kit's "a person" files and 48
templates on the owner's machine: every standing template puts the head (124.68, -107.60) from the pose and every
sitting one (106.82, -114.43), at a quarter scale. At full size: pose (-121, 634), head (404, 180) standing; (-81, 637)
and (345, 180) sitting; inside the head, face (159, 186), facial hair (123, 338), accessories (47, 241). The puppet is
hip -> body (the pose) -> head -> face, beard and glasses, at 0.3 of the kit's size, with a `pose` swap set beside
the other five. The head turns at the neck. In the `peeps` test both kinds lint clean, and for every pose the
drawing just under the head's bottom edge passes within 21 units of the head's centre (the neck under the head).

Open: the faces are whole expressions, not mouth shapes, so lip-sync needs a mouth drawn per face; the bust's arms
are part of each body drawing, so they cannot gesture.

## Humaaans (WP-16)
`cast.import_humaaans` turns the Humaaans kit's "Single Pieces" (18 heads, 10 bodies, 8 standing and 4 sitting
bottoms; by Pablo Stanley) into one puppet. The finished figures stack a head at (82, 0), a body at (22, 82) and the
legs at (0, 187) of a 300 x 426 figure; figures that turn a head or lean a body move these, so only unturned ones set
the rest layout. The puppet is hip -> legs -> body -> head. The body turns at the waist (the top centre of the legs)
and the head at the neck (the bottom centre of the head's skin), drawn head first, then legs, then body, as the
figures stack them (the collar over the neck). Swap sets replace each part: `hair`, `outfit`, `legs` (sitting ones
are `sit-...`). Fills become palette slots. Arms are drawn into each body, so they do not move on their own.

The kit came the same way as Open Peeps' (Gumroad, on the owner's machine). Its 79 SVGs are on GitHub
(Calinou/humaaans); 13 hashes from every folder matched the owner's copy. That mirror says CC BY 4.0, the licence of
the 2019 release; humaaans.com says CC0 today. The manifest records it as attribution, so Pablo Stanley is credited.

Test `humaaans`: the puppet lints clean, and the five finished standing figures at the rest layout, rebuilt from its
swap sets, match their own SVGs (silhouette IoU 0.997 to 0.999). The figures recolour the skin, so colour agrees on
75 to 99% of shared pixels. A 12 degree lean and a 10 degree nod change the upper half of the frame (5.0 levels mean)
and leave the legs untouched (0.0).

## Character bibles and continuity (WP-16)
`cast.bible {"id", "set"}` keeps a character's bible in cast/bible/<id>.json: personality, voice (with a voice per
language, `by_lang`), acting profile, gesture tendencies in words, clips it never plays, look (outfit, what it always
wears, family), catchphrases, relationships, continuity notes, and films allowed to differ (`exceptions`, with why).
What the cast registry already knows is filled in, and what is still missing is listed. `cast.continuity {"id"}` (or
every character with a bible) finds the films whose shots use the character's puppet and reports a voice other than
the bible's for the film's language, a language with no voice chosen, an acting profile that overrides the bible's,
a clip the bible rules out, and a puppet file changed since it was registered.

Ravi and Momo have bibles, written from the Ask Ravi series bible and from what their 23 and 21 films actually use
(Ravi speaks as am_michael in 20, Momo as af_heart with her pitch and formant in 18). The check reports one real
issue: in data-demo-ar Momo speaks Arabic with the only Arabic voice installed, a low male voice; choosing an Arabic
voice for her is open. Test `bible`: a scratch film that gives Ravi another voice and a clip his bible rules out,
and Momo a French line with no French voice chosen, is caught on all three.

## Character family looks (WP-16)
A family is a look shared by a set of characters, on top of `cast.generate`: `line` (stroke weight factor), `eye`
(eye and pupil size factor), `head` (head size factor) and `ink` (line colour), plus palettes the members' tops,
bottoms and hair are drawn from (cast/families.json: `house`, the style of every character so far; `bold-round`,
heavy navy line with bigger heads and eyes; `fine`, thin warm-grey line, smaller eyes). `cast.family {"family",
"members": [{id, spec}]}` makes and registers each member (the member's own spec wins; colours go round the family's
palettes by the member's place, so a family stays varied) and marks the cast entry with its family. The generator
takes the same `look` in any spec. With no look, a generated character is exactly as before.

Test `family`: three members (a teen, an adult with glasses, an elder) in each family. Inside a family the median
stroke width is the same for all; against the house family, line weight, eye radius and head radius stand at the
family's factors (bold-round 1.5, 1.456, 1.12; fine 0.7, 0.816, 0.96; each within 3%); ink and colours come from the
family; every member lints clean; a shot with one member of each family draws alike in Synfig, Lottie and Grease
Pencil (1.0).

## Prosody direction (WP-13)
A script line's `"delivery"`: `whisper`, `shout`, `excited`, `calm` or `sad`. Kokoro and Piper take no SSML, so the
delivery is made from the voice itself, in the same WORLD resynthesis as the speaker's own fx (engine/voicefx.py
DELIVERY): pitch and intonation range, spectral tilt above 1 kHz (brighter for a shout, darker for sad), speaking
rate (the TTS length scale) and level; a whisper is resynthesised with no voicing at all, noise through the same
vocal tract. Words are aligned after, so lip-sync and captions follow.

Measured (test `prosody`: one sentence as Ravi, plain and in each delivery): voiced share 0.51 plain against 0.04
whispered (loud frames with a periodic autocorrelation peak; WORLD's own pitch tracker reports 0.32 for the whisper,
because it finds "pitch" in noise); shout 136 Hz against 107 and a spectral centroid of 3.9 kHz against 2.2;
excited the widest intonation (0.31 against 0.23) and 10% quicker; calm and sad narrower (0.15, 0.14) and slower;
sad the lowest (100 Hz) and darkest (1.5 kHz). faster-whisper transcribes all six without an error.

## Automatic vertex weights (WP-11)
`puppet.auto_weights {"puppet", "part", "chain", "out", "step"}` (dbe/autoweights.py) turns a drawing made in one
piece over several parts, an image stroke on `part`, into a skinned mesh stroke (format v0.5) that bends at the
joints of `chain` (e.g. `["thigh_L", "shin_L", "foot_L"]`). A grid of triangles (`step` artboard units) covers the
drawing's ink, cells without ink left out; each part's bone runs from its pivot to the next part's (the last one on
in the same direction); every vertex is weighted by inverse squared distance to the bones, the weights are diffused
over the mesh's edges (six passes) so a joint bends in an arc, and each vertex keeps its three strongest parts above
2%. The result renders wherever mesh strokes do (the SVG player; the other exporters skip them). Test `autoweights`:
a striped leg drawn in one piece on Pip (217 vertices, 342 triangles, weighted over thigh, shin and foot) draws as
the image at rest (IoU 0.9998); with the knee bent 75 degrees it matches the same drawing cut rigidly at the joints
(IoU 0.855, below the knee 0.33 px apart on average) and stays one piece, bending in an arc where the rigid cut
leaves a notch; left unskinned it does not bend (IoU 0.33 against the bent cut).

## Sprite sheets (WP-30)
`export.sprites {"puppet", "clips", "fps", "scale"}` draws each clip of a character alone (the player, transparent) at
the sheet's frame rate, trims every frame to its ink and packs them into one PNG (shelves, tallest first). Beside it:
the atlas in TexturePacker's JSON hash layout (frames with their rectangle, trim, untrimmed size and pivot, plus an
`animations` map clip -> frames), read by Phaser, PixiJS, Cocos, Defold and Unity's TexturePacker importer; and a
Godot 4 SpriteFrames resource, one animation per clip, each frame an AtlasTexture whose margin restores the untrimmed
frame. Test `sprites` (Biscuit, six clips, 65 frames at 12 fps): no rectangle overlaps, every frame rebuilt from the
sheet equals the player's own still exactly, and Godot 4.5 plays "wag" from the SpriteFrames identically to the
stills (mean difference 0.0). Unity itself is not run here.

## Pose detectors compared (WP-12)
`pose.benchmark {"detectors", "limit"}` runs MediaPipe Pose Landmarker (what act-out uses), RTMPose (rtmlib
"balanced": a YOLOX-m person detector, then RTMPose-m, ONNX on the CPU) and Ultralytics YOLO11m-pose on 80
single-person photos from COCO val2017 (tests/posebench: the first 80 with one annotated person, at least 14
labelled keypoints and an area over 40,000 px; images fetched from their URLs) and scores each image by COCO's
keypoint similarity (OKS, COCO's per-keypoint sigmas, the person's area as scale, over the labelled keypoints).
MediaPipe's 33 landmarks map onto COCO's 17. Results in out/posebench/result.json. Test `posebench` (only when
asked by name: minutes of CPU).

**Measured** (80 images, 4 CPU cores):

| Detector | mean OKS | OKS >= 0.5 | OKS >= 0.75 | missed | ms per image |
|---|---|---|---|---|---|
| RTMPose-m (rtmlib) | 0.944 | 0.988 | 0.975 | 0 | 284 |
| Sapiens pose 0.3B (top-down on the same YOLOX boxes) | 0.930 | 0.988 | 0.963 | 0 | about 13,400 |
| YOLO11m-pose | 0.919 | 0.988 | 0.963 | 0 | 245 |
| OpenPose (CMU's COCO body model, PyTorch, 4 scales) | 0.916 | 0.975 | 0.925 | 0 | about 12,500 |
| MediaPipe Pose (full) | 0.836 | 0.963 | 0.825 | 1 | 40 |

What this does and does not say: RTMPose and YOLO11 learnt COCO's own keypoint definitions (where a hip or an ear is
marked) from COCO train2017, which these val2017 images are not part of; MediaPipe learnt its own 33-landmark
definition, so part of its gap is a different idea of where a joint is, not only error. These are still photos, not
takes: act-out also needs MediaPipe's heels, toes and hand points, which COCO's 17 do not have, and runs seven times
faster. Act-out keeps MediaPipe; RTMPose is the one to try first where body accuracy matters more than speed (rtmlib's
whole-body model, DWPose's 133 points, has the feet and hands; not yet tried). OpenPose runs as CMU's own body
model (non-commercial licence, sha256 pinned) in the PyTorch port vendored in vendor/openpose (controlnet_aux 0.0.10,
Apache-2.0), bottom-up, searching the four scales OpenPose's own evaluation uses. It is fourth (0.916), level with
YOLO11, and about 45 times slower; its time was measured beside other jobs. Sapiens (Meta's 0.3B model, CC BY-NC 4.0, 1.3 GB, sha256
pinned) runs top-down on rtmlib's YOLOX person boxes, its 308 Goliath points mapped to COCO's 17: second on accuracy
(0.930), about fifty times slower than the rest on this CPU (13.4 s an image alone; the 80-image run, 16.7 s, shared the
machine with other tests, as did the others' times in it, which the table gives as measured alone).

## OpenToonz scenes (WP-34)
`export.opentoonz {"name", "shot", "render"}` writes a shot's drawn levels (template "level") as an OpenToonz 1.8
scene in build/opentoonz/<shot>/: `scene.tnz`, a raster level per drawn character (one PNG per drawing at its
artboard size, 120 dpi, so a drawing pixel is a camera pixel at 100%), the xsheet exposing each frame's drawing as
the bake has it (a clip's timing, speed and loops come over exactly), and each column's pegbar keyed on every frame
with the character's position (its ground point, as the player places it), scale and flip. The folder is its own
OpenToonz project (`scenes.xml` and `doodleberry_otprj.xml`), so OpenToonz opens it and its renderer finds it.
Cut-out puppets are not OpenToonz levels: they are listed under `not_exported`. In the file, every `id='n'` is one
object table for the whole scene (levels, columns and fxs share it), as OpenToonz reads it.

With `render` (default) and OpenToonz's renderer installed (`bash tools/setup.sh opentoonz`: OpenToonz 1.8.0 from
source, the tag checked by commit, its bundled libtiff and only the `tcomposer` target, about 25 minutes on four
cores, into /opt/opentoonz), `tcomposer` renders the scene under Xvfb, and three frames are compared with the
player's drawing of the same characters alone (a scratch copy of the shot without the cut-out cast). Test `opentoonz`
(level-demo s1: the campfire and the walking doodle, Ravi not exported): the xsheet read back from scene.tnz exposes
the bake's drawing on every frame of both columns, and tcomposer's 147 frames match the player at frames 0, 73 and
146 (alpha IoU 0.998 to 0.999, mean colour difference 0.31 to 0.33 on 0-255).

## Machine-translation drafts (WP-25)
`film.translate {"name", "lang"}` drafts every untranslated string of a film into i18n/<lang>.json with NLLB-200
(Meta's distilled 600M checkpoint, converted here to CTranslate2 int8 once; CC BY-NC 4.0). Each {{...}} binding is
swapped for a distinct number while translating and put back; a string whose binding does not come back is left empty
and listed. Strings a person wrote are never touched; the file records which strings are machine drafts. Sinhala:
NLLB learnt it with the zero-width joiner stripped, so a rakaransaya or yansaya comes out as a hal kirima, a space and
ra or ya ("රාත් රී" for "රාත්‍රී"); that cannot be told from a word boundary, so such drafts carry a note for the
reviewer rather than a guess. `film.localize` lists the machine strings nobody has reviewed (`reviewed` in the i18n
file clears them) and records the model in the version's provenance.json, so the posting gate flags it.

Audio description now follows the version's language: the describer writes English and translates its sentences with
the same model before they are placed, voiced by a voice for the language the speakers do not use (Kokoro where it
speaks the language, else Piper).

Measured (test `translate`, data-demo): Spanish 19 strings and Sinhala 20 drafted in about 4 s each on the CPU, every
binding kept, the hand-written string untouched; 9 Sinhala drafts carry the conjunct note.

Charts read right to left in right-to-left films (test `rtl_chart`: data-demo-ar's bars, from the left, are
data-demo's reversed).

Voices registered without their own URL are fetched from the rhasspy piper-voices catalogue (its path and md5).

## CMU motion capture and hugs (WP-12, WP-11)
`clip.cmu_import {"subject", "trial", "puppet", "name", "plane", "save"}` turns a take from the CMU Graphics Lab
Motion Capture Database (ASF skeleton and AMC motion, 120 fps; fetched once into out/cmu/, not committed; CMU: free
for all uses, not to be resold) into a 2D clip. Forward kinematics as the format defines it (each bone's rotation is
its axis frame C times the frame's rotations M times C inverse, after its parent's), then the take seen from the
side (the actor's way of travel to the right; for walks, runs and jumps on side-view puppets) or the front. Each
part's angle is its bone's direction on screen against the puppet's own rest direction for that part (the next joint
of its chain: CMU's rest pose is a T-pose, the puppet's is arms down); a bone pointing at the camera holds its
angle; resampled to 30 fps, keys reduced. The BVH importer now reads a motion-capture actor as facing the camera, so
their left arm drives the puppet's right-of-picture arm (`facing`: "camera" or "away").

Test `cmu` (subject 02 trial 01, a walk, on Pip): bones keep their length through the take; from the side the thighs
alternate (correlation -0.89) through 50 degrees, each arm swings against its own leg (-0.82, -0.93), the stride is
1.05 Hz and the root travels forward; from the front the same take has no stride (the legs swing towards the camera:
+0.81); it plays on Pip in the player.

Hugs (a shot's interact block, `"hugs": [{a, b, start, hold, reach}]`): both arms of each character go round the other's back by IK, to
points on the partner's torso, blending in and out; heads turn to each other. In the `interact` test (a copy of
handshake-demo where the two walk closer and hug) all four hands stay on their targets while the hug holds (0 px on
the baked frames) at 72% of arm reach.

## Branching interactive films (WP-30)
shots.json `"branches": [{"after": "s2", "prompt": "What do you want to know?", "choices": [{"label": "How far is
it?", "shots": ["s3"]}, {"label": "Why is it warm, then?", "shots": ["s4"]}], "then": "s5"}]` makes the interactive
page (`export.interactive`) a branching film. The film is still rendered whole, every branch in order (so the video
and every other format stay linear); the page plays one path through it: at the end of `after` it stops and offers
the choices, plays the chosen shots, and at their end jumps to `then`. Scrubbing back before a branch asks again;
`IFILM.choose(i)` and `IFILM.state().path` are there for scripts. A branch naming a missing shot, or with fewer than
two choices, is refused. Test `branching` (a scratch copy of closest-to-the-sun-in-january): the page stops at
11.55 s with both choices, the second plays from 19.1 s, and at its end the page is at s5 (21.25 s) without having
shown s3.

## BVH motion out and in (WP-12)
`clip.bvh_export {"puppet", "clip"}` writes a clip as BVH: the puppet's part tree is the skeleton (each joint named
after its part, offset from its parent's pivot, y up) and the clip is sampled per frame the way the player plays it
(smoothstep between keys); each joint's Z rotation is the part's angle, negated because the artboard's y points
down; the root carries the clip's offset. `clip.bvh_import {"bvh", "puppet", "name", "save"}` reads one back: our
own files by their Z rotations, other skeletons by joint name (Hips, Spine, LeftArm, LeftForeArm, mixamorig:,
UpperArm_L, ...), posed in 3D with their own channel order and seen from the front (each bone, or for a bone with no
length its own axis, against its rest direction on the picture plane); keys are reduced, and `save` adds it to the
puppet's own clips. tools/blender/bvh_check.py prints the joint positions Blender's importer reads.

Test `bvh` (four humanoid clips on Ravi, one with a moving root): the BVH's joints sit where the puppet's own
geometry puts them (within 0.0003 artboard px), Blender reads the same positions (within 0.0003), and the clips
come back within 0.48 degrees, both as our skeleton and with the joints renamed to motion-capture names.

**A real take** (BEAT: a man talking with his hands, 120 fps, 74 joints with fingers, T-pose rest; CC BY-NC 4.0,
in-house; the first 20 s cut from the head of a public 142 MB take by a byte range, `out/bvh_real/`, not committed).
Read against its own rest, the T-pose put his hanging arms at 74 degrees on the puppet. So a motion-capture bone is now
read against the puppet's own rest direction along the same bone (from its pivot to the child part the skeleton
aims at); the root and bones aimed at unmatched joints keep the skeleton's rest; a hand or head keeps its bend
against its parent as the skeleton has it, within 100 degrees; a bone aimed at the camera (seen shorter than a third
of its length) holds its last angle; and no joint turns faster than 900 degrees a second, so a released hold or a
wrist flipping between its two readings swings instead of jumping. Test `bvhreal` (only when asked: it fetches the
8 MB and runs Blender): our forward kinematics matches Blender's importer within 0.00006 on every joint; the hand
moves 25 units in depth against 32.5 across (real out-of-plane motion); the upper arms hang at 12.6 and -14.3
degrees; every arm and leg bone's direction on the picture matches Blender's projected bones within 0.56 degrees
(median 0.02) where it is not aimed at the camera; forearms are aimed at the camera in 12 to 24% of frames and hold
there; the fastest joint turns 946 degrees a second. Seen beside Blender's skeleton from the front, Ravi raises the
same hand to his chin, keeps the other hand at his chest and shifts his weight to the same leg.

## Map board (WP-16)
`"set": "map"` puts a framed map on a wall (the characters stand in front of it), or fills the frame with
`"full": true`. The map data are Natural Earth countries (world-atlas TopoJSON, public domain) projected by d3-geo's
Natural Earth 1 projection into SVG paths: `node tools/mapboard/make.mjs <name> <110m|50m|10m> <centre lon> [lon0 lat0
lon1 lat1]` writes sets/maps/<name>.js (the box keeps what lies inside it plus 12 degrees). Made so far: `world`
(1:110m), `south-asia` (1:50m, 60-100 E) and `indo-pacific` (1:110m, centred on 160 E, so the Pacific is not cut).
The player page loads only the maps its shots use. Everything placed on the map uses the set's own copy of the
projection (`MAPS.project`), so a pin lands where the data puts the place. `set_opts`:

| key | what |
|---|---|
| `map` | which map (default `world`) |
| `view` | `[lon0, lat0, lon1, lat1]` shown whole in the board, or keys `[{t, view}]` eased between (a pan or zoom); `t` in film time, as a line reference (`"ask.start"`) |
| `highlight` | `[{country, colour, start}]`: a country fills in from `start` |
| `pins` | `[{lon, lat, label, start, colour}]`: a pin drops in with a bounce, then its label |
| `routes` | `[{from, to, start, dur, colour, bend}]`: from and to are `[lon, lat]` or a country; a dashed curve draws itself |
| `boxes` | `[{lon0, lat0, lon1, lat1, label, start, colour}]`: a region outlined (Natural Earth bends its sides) |
| `labels` | `[{country or lon, lat, text, start}]` |
| `title`, `land`, `sea`, `wall`, `floor`, `fit` | the board's title strip and colours; `fit: "cover"` fills the board instead |

Times are film seconds written as line references (`"hook.start+1.2"`), resolved like every shot time, so re-voicing keeps the map in step. Faint swell marks drift on the sea so a held map never freezes. Every label is text, so it translates with the film.
Setup: `bash tools/setup.sh maps` (d3-geo 3.1.1, topojson-client 3.1.0, world-atlas 2.0.2, pinned in
tools/mapboard/package.json; ISC). Test `mapboard`: on every map the set's projection agrees with d3-geo's on a
7.5 by 5 degree grid (largest difference 0), five capitals are inside their countries, the same time draws the same
SVG, and in the real player page a pin's red is at the projected point after it drops and absent before.

## Palette variants per scene (WP-16)
A shot with `"palette_variant": "night"` (or `sick`, `cold`, `warm`; cast/palette_variants.json) recolours its
characters: every palette colour and every literal colour in their drawings (strokes, swap shapes, view overrides)
is pulled toward grey by `desat`, mixed toward `tint` by `tint_amt`, multiplied channel by channel by `mult`, clamped
and rounded. The same arithmetic is in the player (`Puppet.recolour` in puppet/loader/puppet.js) and the bake
(`geom.recolour`): the bake writes a recoloured copy of each puppet beside the shot
(build/shots/<shot>.cast<i>.<variant>.puppet.json), so Synfig, Lottie and Grease Pencil draw what the player draws.
Raster parts are not recoloured. The variants file is renderer input, so changing it re-renders the shots that use it.

Test `palette`: the player and the bake give the same colours for all 20 cast and example puppets in all 4 variants.
A shot of Pip and Biscuit by day and by night draws alike in Synfig, Lottie and Grease Pencil (score 1.0, colour
difference 0.1 to 0.2). The night version is darker (mean luma 85 against 143) and bluer (blue share 0.36 against
0.23).

## Render farm (WP-38, part 1)
`farm.render {"name", "workers", "pin", "cache", "fresh", "assemble"}` (dbe/farm.py) splits a film into one task per
shot that is neither already rendered nor in the shared cache. Tasks go into a queue on disk (out/farm/runs/<run>/),
dearest first by `render.estimate`. `workers` processes (`farm.worker`) each claim a task by renaming its file into
their own folder; the rename is atomic, so no shot is taken twice. Each worker renders the shot with one browser and
puts it in the **shared cache** (out/farm/cache/) under its content hash: the same hash `film.render` uses to decide
a shot is fresh (the resolved shot, puppets, clip libraries, lip-sync cues, renderer code). Then `film.render`
assembles, finding every shot fresh. Here each worker is pinned to its own CPU core to stand for one machine; on
several machines the workers share the repository and out/farm over a network filesystem. `farm.longform` voices,
acts and renders a synthetic counting episode of a given length on the farm and reports its time, memory, cache size,
assembly time and QA.

**Measured** on a seven-shot synthetic dialogue (1,768 frames, four shots in the 3D layer): one worker took 894 s
and three workers 320 s, 0.358 of the time (the best split of these shots over three workers: 0.353), each busy
262 to 318 s; every shot's decoded frames identical (frame MD5) between the two renders; assembly re-rendered
nothing; a second run took all seven shots from the shared cache in 0.2 s.

Pinned workers run with `tools/farm/keep_affinity.c` preloaded (built by `farm.render`). SwiftShader, Chromium's
software WebGL, pins its own worker threads to core 0 upwards whatever cores the process may use, so before it every
worker drew its 3D on core 0: the same film then took 0.609 of one worker's time, each shot 1.8 times slower, with
frames still identical. (The first run, with other work on the fourth core, took 2,145 s and 756 s; 3 of its 7
shots then differed frame by frame, which has not recurred in the two runs since.)

**Long form** (`farm.longform`, measured 4 Nov 2026): a synthetic counting episode of 23.5 minutes (1,409 s, 136
shots, 42,283 frames), voiced and acted in 762 s. The farm rendered it in two sessions: the first stopped at a 2-hour
limit after 42 shots (with tests running beside it: 13,275 s of one core's work in 6,407 s); the second rendered the
other 94 alone, 20,868 s of work in 6,969 s, 0.334 of one core's time (0.392 over both). The shared cache holds
608 MB. Assembly (join, captions, mix, mux, QA, audio description, signing) took 7,343 s, with the largest single
process at 12.0 GB; every QA check passes, the audio description included (1 description in a pause and 2 holds,
4.2 s added). The run found three limits, now fixed: the mix was killed for memory at 13.9 GB (the limiter and the
true-peak check upsampled the whole film 4x at once, reverb ran one FFT over it: now chunked and overlap-add, the same
output, 11.0 GB, then buffers freed as soon as used), the described picture's single filter graph buffered the
whole film and was killed (now built piece by piece), and the mix alone took 60 minutes.

**A leaner mixer** (WP-38, measured 4 Nov 2026 on the 23-minute film's mix inputs, each run alone): a profile
showed the limiter's true-peak pass taking half the time, mostly in strided maxima over the 4x-oversampled signal,
and the memory peaking in the multiband ducker, which held five full-length temporaries. Now:
- the true peak takes its maxima channel by channel and over each sample's four values with `np.maximum`;
- the limiter scales the mix in place;
- the ducker combines its bands block by block into the low band's buffer;
- the WAVs are written block by block.
Each step keeps the arithmetic per sample, so the output is the same: all six files (mix, music, effects and the
three stems) are byte-identical to before. The time went from 785 s to 572 s, and the peak memory from 8.9 GB to
7.0 GB. A 3-million-sample check confirms the ducker alone is bit-identical.

**Loudness block by block** (5 Nov 2026): the mixer's integrated-loudness passes (voice, music, music-only mix,
final mix) used pyloudnorm's meter, which copies and filters the whole signal. `lufs` in engine/audio.py runs the same
K-weighting filters block by block with their state carried on (the same recursion), keeps the mean squares per
100 ms segment and builds each 400 ms gating block from four of them (its bounds are the same samples), so only the
summation order differs. Test `lufsstream`: on stereo, mono, short, gated and silent signals it equals pyloudnorm
within 4e-15 LU; on 5 minutes of stereo it needs 59 MB of working memory against 346 MB (on 20 minutes, 59 MB against
1,382 MB, and 5.2 s against 7.4 s). A film's mix, music and effects come out byte-identical (ask-ravi-e01, rendered by
the engine before and after). The reverbs already run in chunks with overlap-add.

**Open:**
- A mixer bounded in memory whatever the length would also have to synthesise the music and lay the effects into
  the mix block by block (today they are full-length buffers).

The `farm` test runs this end to end. Its pass mark: the three workers' time within 15% of the best split of these
shots over three workers (from the one worker's own shot times), or under 0.4.

## Kinetic typography (WP-15)
An overlay `{"type": "kinetic", "text", "x", "y", "size", "line": "l2", "style": "pop" | "rise" | "slide", "width",
"color", "accent": [word indexes], "accent_color"}` brings each word on as it is spoken: the line's own word times
from timing.json, by position (without a `line`, one word every `every` s from `start`), each over 0.25 s, popping
from 60% size, rising or sliding in. Words wrap into centred rows of at most `width` px, measured in their own font
(a canvas measures them as the page draws them), and run right to left in right-to-left films. A pure function of
time, like every overlay. Test `kinetic`: on a copy of dialogue-demo, OCR reads no word before the line, exactly the
five words already spoken at 1.7 s ("did you know the library", none of the rest) and all eight by its end.
The same test draws a line off both ways (kit `draw` with `off`): half way through, the half it clears first is
empty (ink 0.004 against 0.35) and the other still drawn; after it, nothing is left.
Kit `draw` also takes a **width profile** and a **colour ramp** along its paths (`"profile": [[0, 4], [0.5, 40], [1,
4]]`, position 0..1 to width; `"colors": [[0, "#ff0000"], [1, "#0000ff"]]`): the path is sampled in the page and drawn
as `segments` (48) round-capped pieces, each with its width and colour, revealed and cleared in order as the line
draws on and off. In the test the line measures 8 px near its ends and 40 in its middle, red (247, 0, 8) at its start
and blue (8, 0, 247) at its end.

**Sub-frame motion blur**: a shot style's `"motion_blur": {"samples": 8, "shutter": 0.5}` renders `samples` moments
per frame, spread over `shutter` of the frame interval and centred on the frame's time (0.5 is a 180-degree shutter),
and averages each group back into one frame (the player's `?sub=N&shutter=s`, then ffmpeg `tmix`); each frame's key
is its samples' keys together, so film.diff still sees what changed. It costs `samples` times the render. Test
`motionblur`: Pip carried 700 px in 0.5 s with 8 samples and a full shutter: 30 frames as without; a blurred frame
equals the mean of its eight samples drawn as stills (0.12 on 0-255, encoding included); blur changes a moving frame
(3.0 against the sharp render) and leaves a still one alone (0.04).

**Match cuts** (`film.match_cut {name, shot}`): the incoming shot's camera is set so its main character lands where the
outgoing shot's main character was at the cut, at the same size (the box from the head to the feet: zoom is the
outgoing height over the incoming one, centre and feet aligned), as a held camera key at its start; a zoom under 1
(wider than the set) is applied but reported. Test `matchcut`: Pip large on the left at the end of one shot and small
on the right at the start of the next overlap at IoU 0.0 across the cut, and at 1.0 after the match (zoom 2.08).

**Media** (`"style": {"medium": "pencil" | "crayon" | "marker" | "watercolour"}`): the characters' ink drawn as if made
with that medium, by one fixed SVG filter per medium (fixed seeds, so a drawing comes out the same on every frame):
pencil greys the colour and lets fine paper tooth through, crayon keeps its colour but a coarse waxy grain breaks the
fills, marker is slightly see-through with darker rims where strokes end and overlap, watercolour bleeds its edges by
noise into a soft wash with pigment pooled at the rims and paper texture through it. Test `media` (Pip standing,
against his plain drawing's ink): pencil keeps 23% of the saturation and 83% coverage, crayon 81% and 86%, marker all
of it and 11 levels lighter inside, watercolour all of it and 2% of the ink bled past the plain edges. Parity frames
compare geometry without it; the other renderers draw plain lines.

**Boil only while moving**: a shot style's `"boil": {"while_moving": true, "still": 0.5}` advances the line boil on a
boil step only if a character moved during it (its root, or any part beyond `still` degrees or px), so a held drawing
holds still and the lines live when the acting does; on a still step the boil keeps the phase of the last moving one
(found within 2 s, from poses without springs: cheap, and a spring only follows motion already counted). Test
`boilmove`: frames one boil step apart differ by 0.66 while Pip waves and by 0.0003 once he stands still (a spring
settling), where the ordinary boil keeps changing (0.31).

## Transitions (WP-15)
A shot can come in from the one before with `"transition": {"kind": "dissolve" | "wipe" | "slide" | "dip" | "iris",
"dur": 0.5 | "auto", "dir": "left" | "right" | "up" | "down", "color": "black" | "white"}`. Transitions are made when
the shots are joined (ffmpeg `xfade`), centred on the cut: the outgoing shot runs on past its end and the incoming
one starts early, over **handles** the SVG player renders (`?pre=&post=` seconds; the shot keeps its own set, cast
and acting through them); other renderers hold their first and last frames instead. The cut stays at the shot's start,
so the picture keeps its length and the sound its sync, and each shot's own `<id>.mp4` stays exact (cut from
`<id>.hd.mp4`) for the hand-off and edits. `dur: "auto"` sizes a transition from the rendered shots: how different
they are across the cut (for a dip, each one's distance from the colour), so the blend alone changes each frame by
at most 75% of the seam limit, up to 1.25 s each side. The transitions made are in `build/transitions.json`, and the
seam check (layout QA) scores a transitioned cut by its mean change per frame over the transition, reporting the
largest single step too; a hard cut is still scored by its largest step. Measured on `data-demo`, whose three shots
change set at each cut (hard cuts 68 and 168): an auto dissolve (28 frames) scores 2.86 and an auto wipe (66 frames)
3.25 against the 3.5 limit, the film keeps its 288 frames and QA passes with no advisories. The `transitions` test
joins three coloured shots with a dissolve and an auto dip: 180 frames, half-way at the cut, pure colour outside,
hard cuts 30 and 40 fail and the transitions 1.76 and 2.69 pass.

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

## Drawing import (plan 1.3)
Three ways in, one way out:

| Command | Takes | Gives |
|---|---|---|
| `puppet.import` | a layered `.svg` (Inkscape layers or groups), `.psd` or `.ora` (Krita, GIMP, MyPaint export) | a vector (SVG) or raster-part (PSD/ORA) puppet |
| `puppet.from_blend` | a recipe (`cast/recipes/*.json`) pointing at a Blender cut-out rig | a raster-part puppet with springs, phonemes, blinks, brows and hand poses |
| `puppet.export_layers` | any puppet | a layered `.svg`, `.ora` or `.psd` for an artist to repaint (then `puppet.import` it back) |

**Layer names** map to the template: `head`, `upperarm_R`, `Upper arm R`, `lower leg left`; swap shapes as `mouth/closed`
or a `mouth` group of shape layers (hidden shape layers are kept); `pivot:<part>` and `anchor:<name>` dots; a
`ground` line; `guide`, `sketch`, `ref`, `background` layers skipped. In SVG, colours become palette slots named after
the parts they paint (or `data-slot` attributes), and transforms, `<use>`, basic shapes and gradients are flattened.

**Pivots** come from markers when present, else from the drawing: a part that shares its parent's joint in the
template takes the parent's pivot; otherwise the centre of the rounded cap at the near end of whichever of the two
shapes is limb-like (checked against their overlap). Parts that do not overlap their parent are reported, because
the joint will gap. Measured on Pip through SVG and ORA: mean pivot error 9 units on a 1000-unit artboard
(`python -m dbe test '{"film": "imports"}'` runs both round trips).

**Blender cut-out rigs** (`dbe/blender_cutout.py` inside Blender, scripts off; `dbe/cutout_import.py` outside):
- every rendered mesh is flattened to front-view triangles with UVs and depth, and rasterised from its texture (no
  renderer; 2.7x texture slots are matched by name cues and UV alpha coverage, or set in `spec.materials`);
- meshes land on template parts by the bone that carries them (screen right = template R); skinned meshes are split by
  vertex weights with overlap at the joints; every mesh keeps its own depth as a child layer;
- each deforming bone of a chain that is not a template part (hair locks, skirt panels, a ponytail, a tail) becomes its
  own spring part, so meshes weighted along the chain bend smoothly; skinned meshes are subdivided once and their
  weights diffused (`mesh_subdivide`, `mesh_smooth`) so bends are arcs, not kinks;
- `keep_pose` in a recipe keeps chosen bones in the pose saved in the file (Carrot's tail curl) for the base state;
- variants (bone poses, actions, shape keys) become swaps: sprite-sheet lips and hands, lid planes and shape-key
  blinks, brow controls. Region patches carry jaw and lid deformation; mouth patches keep only what lies in front of
  the pupils, so gaze still works.

Third-party rigs stay out of git (`assets/external/`, `cast/external/`); the recipe and its credit line are committed,
and `assets/manifest.json` "external" records licence and source. Pepper and Carrot (Nikolai Mamashev, after David
Revoy's Pepper&Carrot, CC-BY 4.0) are the showcase (`cast/recipes/pepper.json`, `cast/recipes/carrot.json`). Skinned meshes that span several parts become v0.5 mesh strokes (smooth knees, hips, skirts); single-bone
meshes stay rigid layers. Limit: raster and mesh parts render in the SVG renderer only.

## Explainer kit 2 and Sinhala text (from the reference reels)
`dbe/player/kit.js` adds elements for history, science and motivational shorts. Put them in a shot's `overlays`
(in front of the cast) or the new `underlays` (behind it). All are pure functions of time, seeded where random, and
have a little idle life once settled (no dead frames).

| Type | Does | Key fields |
|---|---|---|
| `draw` | paths draw themselves, then optionally fill; and draw off again; widths and colours along them (WP-15) | `paths`, `duration` or `until`, `stagger`, `stroke`, `width`, `fill`; `off` (a time, line-relative allowed), `off_duration`, `off_from`: `start` or `end`; `profile` [[pos, width]], `colors` [[pos, "#hex"]], `segments` |
| `title` | bold outlined words pop in one by one | `text`, `y`, `size`, `per_word`, `color`, `outline` |
| `paper` | torn-paper sign with tape; `[bracketed]` words in the accent colour | `text` (lines), `y`, `size`, `accent`, `rotate` |
| `roots` | a root system grows from a point (red taproot optional) | `x`, `y`, `depth`, `levels`, `branches`, `spread`, `seed`, `until`, `main` |
| `section` | ground strata for cross-sections, with pebbles | `y`, `layers: [{h, color, pebbles}]`, `seed` |
| `water` | a water body with a moving surface, a level that can change, flow lines along paths | `x`, `w`, `level: [[t, y]...]`, `bottom`, `flows: [{path, speed}]` |
| `face` | a face for any object: eyes, pupils, brows, mouth; lip-sync from a speaker; blinks, gaze, moods | `x`/`y` or `attach: {cast, part, at}`, `speaker`, `look`, `mood`, `s` |

`until` (like `start`, `end` and `t`) may be line-relative, so growth can finish exactly when a line starts.
Text in every element, and in bubbles, cards and captions, may be Sinhala: font stacks fall back to Noto Sans Sinhala
(OFL, `engine/fonts/`) per glyph, and the page waits for it to load. `films/kit-demo` uses every element.
Gap: no clean Sinhala text-to-speech voice exists yet (the open MMS model is non-commercial), so Sinhala films are
sound-off with music, or use a recorded human voice.

## Motion effects (plan 2.20)
`"fx"` on a shot turns on effects computed from the motion itself (`dbe/player/fx.js`), so nothing is placed by hand
and any frame renders on its own:
- `speed_lines: true | {"parts": ["hand_R", "hand_L"], "min": 650}`: three tapered strokes trail a part whose speed in
  the frame passes `min` px/s;
- `dust: true | {"min_drop": 14}`: puffs at the feet when a character lands (its hips decelerate sharply after a drop);
- `impacts: true`: a star burst where a prop arrives at the end of its travel (a catch or a drop);
- `arcs: true | {"props": ["red"], "length": 0.5}`: the motion arc a moving prop has just travelled, a fading dotted
  trail like an animator's arc guide (WP-09).
Per prop (WP-09): `"stretch": true` stretches it along its velocity (area kept), `"squash": true` squashes it on every
contact (catches, bounces, baked hits) and wobbles back, `"smear": true` draws a smear frame with multiples when it
moves more than its radius in one frame. Off by default, so existing films are unchanged. `films/fx-demo` is the props
demo with the first three on; `films/juggle-demo` uses all of them.

## Cartoon physics for props (plan 2.19, first part)
A prop's attach key can ask for physics (SVG player; deterministic, so frames stay pure):
- `"flight": "ballistic"`: a true gravity arc from the previous parent to this target, landing exactly at the end of
  `travel`, or at `"arrive"`, which may be line-relative (`"arrive": "catch.end+0.45"`): the catch stays on the words
  after re-voicing or translation.
- `"drop": {"floor": y, "x": x, "e": 0.55, "roll": 0.75}`: released at the key time, the prop falls, bounces with
  restitution `e`, rolls towards `x` and spins as it rolls. With `fx.impacts` on, each bounce draws a ring.
`gravity` (px/s², default 2600) is set per prop. Prop motion lives in `dbe/player/props.js`, shared by the player, the
effects and the Node solvers.

## Juggling and multi-body physics (WP-09)
- `juggle.solve {name, shot}` reads the shot's `"juggle"` block (`pattern`: a vanilla siteswap such as `"3"`, `"441"`,
  `"531"`; `start`, `end` (line-relative allowed); `every` beats per throw; `dwell` in throws; `subdiv` of the beat;
  `height`; `balls`) and writes one prop per ball (held in a palm, then ballistic flights) and both arms' IK keys,
  with every throw and catch on the beat grid of `score.json`. Output is tagged `"solved": "juggle"`; re-solving after a
  tempo or voice change replaces it.
- `physics.solve {name, shot}` bakes the shot's `"physics"` block with Rapier's deterministic build
  (`bash tools/setup.sh physics`): `bodies` (balls and boxes, or `{"id", "prop": true}` to take over a prop from its
  own motion at `start`), `static` boxes or segments (`"draw": true` shows them), `floor`, `walls`, `impulses`
  (`{t, body, v}`), `retime` (the strongest contacts move to the nearest grid point; between them time is warped by
  0.75 to 1.33×). The result is a `track` per prop (`{t0, fps, frames: [[x, y, deg]], contacts}`) and the bake's
  sha256 in the block; a rerun reproduces it byte for byte (`python -m dbe test '{"film": "motion"}'`).
- Timeline `ik_bend` (`{"arm_L": 1}`) picks which way an elbow or knee bends; a `null` IK key lets the limb go.

## Interaction and locomotion (WP-11, part 1)
- A cast entry may walk a path: `"place": {"path": {"points": [[x, y], ...], "start": t, "speed": px/s | "end": t,
  "ease": s, "s": 0.7 | "s_by_y": [y0, s0, y1, s1], "face": "auto"}}`. The root follows a Catmull-Rom curve through the
  points by arc length and faces the way it goes; the player, the bake and so every renderer use the same
  `Acting.pathAt`. With `pins`, a planted foot keeps its place along x while the root moves (up and down the frame is
  depth: it rides the ground line under the hips) and keeps the clip's heel roll.
- Timeline `ik_weight` (`{"arm_R": [[t, 0], [t2, 1]]}`) blends between the clips' pose and the IK reach target. IK key
  values and look-at targets may be `{x, y}` (a frame point) or `{cast, part, at}` (a point on another character): the
  player and the bake evaluate everyone once, then those with such targets again against the others' first poses.
  Look-at entries take `start`, `end` and `ease`. A clip layer may start `phase` seconds into its clip.
- `interact.solve {name, shot}` reads the shot's `"interact"` block: `walks` (`{cast, points, start, speed, ease,
  s_by_y, view}`: the clip's speed matches the root to the stride measured over a whole stance, the clip starts at
  mid-stance and ends on a passing step), `handshakes` (`{a, b, start | "arrive", hold, pumps, amp, reach, arm}`: b
  holds out a hand to the meeting point and pumps it, a takes b's hand; both blended in and out) and `eye_contact`
  (`{a, b, start, end}`). `interact.measure` reports planted-foot slide and hand gaps on the baked frames (the
  `interact` test requires at most 1 px and 2 px). `films/handshake-demo` is the demo.
- Part 2 (puppet format v0.9, `puppet/spec/puppet-format.md`): timeline `scales` (`{"head": [[t, 0.86]]}`: per-part
  squash and stretch), `ik_stretch` (`{"arm_R": 1.8}`: stretchy limbs), `copy_rotation`, `z` (layer order keys); on the
  puppet, `swaps[sid].by_angle`, `lipsync`, per-pose `z`, part `attrs` and stroke `rule: "evenodd"`. A prop may follow
  a path: `"path": {"points", "start", "end" | "speed", "ease", "orient": true}`. `interact.measure` also takes
  `points` (how far a part is from a frame point at a time). `films/stretch-demo` is the demo. `render.parity` compares
  the characters even in shots with props or effects, and lists those as `not_compared` (planes still refuse).
- Part 3 (puppet format v0.11): timeline `grow` (`{"head": [[0, 1], [1.5, 1.4]]}`) scales a part and everything
  below it uniformly about its pivot (a bigger hand on a bigger arm), where `scales` stretches the part alone; controls
  drive it (`grow.<part>`) and IK reaches with the grown bones. Every renderer follows it (Lottie as the part layer's
  scale, which its parenting carries down). Test `grow`.
- Part 4 (format v0.12): `correctives` on the puppet ("smart bones"): a part's final angle drives angles, shifts,
  scales, grow, swaps or layer order through key curves, as a control's value does (scales and grow multiply what the
  pose has). Resolved in acting.js after IK, limits and springs, so every renderer follows. Test `correctives`: Pip's
  forearm, bent to -130 by the thinking clip, drives its bicep's scale and its hand's angle exactly (21 samples), and
  Synfig (0.996), Lottie and Grease Pencil (1.0) draw it as the player does.
- The player writes each part's rotation-and-scale terms to 5 decimals (2 put far parts up to 4 px from where Lottie
  and the bake place them: the stickers' legs, WP-23); golden frames updated for it.

## Procedural and 3D layer (WP-42, part 1)
A shot's `"proc": {"floor": 1500, "nodes": {...}}` is a graph cooked into the shot by `proc.cook {name, shot, force}`
(`dbe/proc.py`). Nodes: `scatter` (seeded points with a minimum spacing in a region), `crowd` (cast members on the
points: puppets picked by seed, facing the centre, idles out of phase, reactions such as `clap` at seeded times; with
`"depth": [near, far]` each stands on its own compositor depth plane, where the ground of that depth meets the frame),
`particles` (confetti, snow or rain: seeded, a pure function of time, on a compositor plane) and `gn_set` (a Blender
Geometry Nodes set, `dbe/blender_gn.py`: blocks scattered on a lot, random sizes and shades, cel-shaded with ink lines,
rendered by EEVEE through a camera derived from the shot's 2D camera keys, into a screen-locked compositor plate). Each
node is cached by a hash of its operation, parameters, inputs and the context it reads (camera, span, script), so a
change re-cooks that node and what reads it: a crowd edit does not render the city again. With a 3D set the compositor
zooms its planes in true perspective (`"zoom": "dolly"`), so the 2D planes and the 3D render share one camera exactly.
Frames with images wait until they have decoded. `films/city-parade` is the demo.

**Rigid bodies** (WP-42). A `rigid` node, `{"op": "rigid", "bodies": [{"shape": "box" | "ball", "size", "at": [x px,
depth m, height m], "rot", "colour", "mass", "friction", "bounce", "velocity"}], "substeps", "iterations"}`, drops
props into the same Blender scene and camera as `gn_set` under Bullet (Blender's rigid body world: a passive ground,
active bodies, a fixed number of substeps), bakes the simulation, then renders it into a screen-locked plate; the
node's output also records where each body is on every rendered frame (`bodies`). Test `rigid` (Blender renders
twice, so only when asked): three boxes dropped into a stack and a ball come to rest with their centres at 0.5, 1.5
and 2.5 m and 0.4 m above the ground (exactly the sizes), move under a millimetre over the last second, and a second
cook gives the same positions and the same pixels. **Cloth strips**: a body `{"shape": "cloth", "size": [w, h], "at": [x
px, depth m, height of its top edge m], "res"}` is a strip pinned along its top edge (a banner, a flag, a cape on a
3D set) under Blender's cloth simulation, with the node's `"wind"` (a wind over the scene; a few hundred moves a
banner). In the same test a 2 m banner hangs 2.004 m below its pinned edge when still, and in a wind of 800 its free
end swings over 1.04 m while the pinned edge does not move. **Separate EEVEE passes**: a `gn_set` or `rigid` node's
`"passes": ["z", "mist", "normal", "position", "vector", "emit", "cryptomatte_object", ...]` writes them beside the
plate, one multilayer EXR per rendered frame (Blender 5 writes each pass as its own part: read `parts`, not only the
first; and with the OpenEXR binding read the header and the channels through separate opens, as each empties the
other). In `rigid` they agree with the scene: the ground's position within 0.8 mm of its height and its normal
straight up, mist rising from 0.002 by the camera to 0.51 at the horizon, Cryptomatte naming every body, and emission
(the cel shading is emissive) within 0.005 of the picture on the objects. **Line art as editable strokes**:
`"lineart": true` draws the 3D set's ink with Grease Pencil 3's Line Art instead of Freestyle (the camera keyed at the
rendered frames so the bake sees what the renders see), bakes it to Grease Pencil strokes saved in `lineart.blend`
(editable in Blender), and projects each frame's strokes to frame pixels in `lineart.json` (the ink as vectors for the
2D side). In `rigid`: 12 and 16 strokes on the two frames checked, every sampled point within 2.5 px of an edge of the
picture, and the saved .blend opens with the same strokes.

**Live renders from a game engine** (WP-42). An `engine` node, `{"op": "engine", "project": "<a Godot 4 project>",
"scene": "res://...", "plane": "engine"}`, renders the project in Godot's Movie Maker mode (a fixed step per frame, so
a frame is a function of its number) at the shot's size and frame rate under a virtual display (Xvfb), into a
screen-locked compositor plate; a transparent viewport (`rendering/viewport/transparent_background`) composites over
the shot. The shot's span and camera reach the project as `--doodleberry-request=<json>` for scripts that follow the
2D camera; the node's cache key covers every file of the project. Test `engine` with `tests/godot/spin` (a turning
box) in front of a scratch copy of pip-park's first shot: 171 frames, every one different, the same pixels on a forced
second cook, and the player's frame equal to Godot's plate wherever the box is (all of its 296,933 pixels).

## ML assists, in-house (WP-43, part 1)
Models used as assistants whose output is data a person accepts, on CPU (onnxruntime), pinned by sha256
(`dbe/assists.py`, fetched by `bash tools/setup.sh models` or on first use):
- `level.inbetween {name, pairs, t}` proposes in-between drawings for a drawn level with RIFE 4.9 (MIT); each proposal
  is a drawing `<a>-<b>` with status `proposed`, not exposed until `level.accept {name, drawings, reject}` takes it
  into the exposure sheet (it takes the second half of the first drawing's hold) or drops it.
- `depth.planes {image, planes, model, film}` estimates relative depth with Depth Anything V2 (Small: Apache-2.0;
  Base: CC BY-NC 4.0) and cuts the picture into far-to-near layers with suggested compositor depths.
- Every output records its model and licence class (a level's `meta.assists`, a film's `provenance.json`), and
  `film.provenance` (the posting gate) flags non-commercial or research-only ones.
- `assist.bench` measures each against its baseline on our own material: in-betweens against holds and dissolves on
  held-out true drawings of the level demo (accepted when the line art is within 2 px: RIFE 92%, holds 58%, dissolves
  50%); depth against "lower is nearer" on Geometry Nodes renders with their true depth (pixel pairs ordered right:
  99.7% against 88.6%).

**Turns between views** (WP-43: morphs between views; puppet format v0.14, `dbe/turns.py`). A view switch on a
timeline (front to side) used to cut with a 0.09 s squash. `puppet.turns {puppet, a, b, steps}` draws the in-betweens
as ordinary views, `turn:<a>><b>:<k>`, so the bake, every renderer and every exporter already play them. Per part,
the strokes of the two views are paired by fill, then by how near they are in place and size (an ear with an ear, not
with the skull beside it); each pair is resampled to 64 points by arc length, lined up in start point and direction,
and blended; a stroke without a partner shrinks to its centre underneath the others (the far ear goes behind the
head) or grows from it; pivots blend; layer order and swap drawings (eyes, mouth) come from the nearer end. The loader
shows in-between k for one step each, centred on the switch (the puppet's `acting` `turn_step`, on twos by default), the other way
round reversed, and drops the squash there. Test `turns` (only when asked) on pip, front to side in three: at rest
the silhouette's IoU with the front drawing falls 1.0, 0.863, 0.747, 0.654, 0.601 while with the side one it rises
0.601, 0.692, 0.798, 0.918, 1.0; in pip-park's third shot (a turn to the side and back) the bake plays the three two
frames each around both switches, the second time reversed, with no squash; Synfig, Lottie and Grease Pencil draw an
in-between as the SVG renderer does (parity 1.0, 1.0, 1.0). Golden frames unchanged.

## Film-grade masters (WP-37, part 1)
- `film.master {name, scale: 2, fps: 0, passes}` renders the film from the SVG player at `scale` times its size (4K for
  a 1080x1920 film) and any frame rate, in four passes (beauty; line: the visible ink, un-composited from white;
  fill: flat colour without ink; matte: the characters' coverage), and writes one multi-layer OpenEXR per frame:
  half float, premultiplied, ACEScg through OpenColorIO 2.6's built-in ACES 2.1 studio config, lossless ZIP. The
  package in `films/<name>/build/master/` adds a slate (EXR and PNG), the mixed audio (24-bit WAV), captions and a
  checksum manifest, and records that OpenImageIO and ffmpeg read the files.
- `film.from_master {name, size, view}` derives the social encode from the master (`build/final_from_master.mp4`): the
  beauty layer back to sRGB (the inverse texture transform, so the colours are exactly the artist's; `view: "aces"`
  gives the ACES output transform for review), scaled and encoded with the master's audio, checked by the QA bar and
  compared with the film's own render.
- `image.scopes {image}`: histogram, waveform and vectorscope of a frame.
- **Looks** (ASC CDL, part 2): `look.save {name, id, slope, offset, power, saturation}` writes
  `films/<name>/looks/<id>.cc`, a ColorCorrection file that Resolve, Baselight, Nuke and OpenColorIO read. The grade
  is applied in ACEScct, the log space colourists use with ACES: OpenColorIO's CDL transform in the ASC style, with its
  clamps. `look.preview {name, id, time}` shows a frame before and after, with scopes; `film.from_master {look}` grades
  the master's straight colour (un-premultiplied, then premultiplied again) before the view. The `looks` test:
  - the .cc reads back through OpenColorIO exactly as saved;
  - OpenColorIO's CDL matches the ASC v1.2 formula within 1e-5;
  - an identity look leaves a frame of nib-hello's mean colour unchanged;
  - a warm look warms it. In ACEScct a slope of 0.9 on blue is strong: the frame's mean blue fell from 223 to 112.
- **Object ids and motion vectors** (part 3): `film.master {passes: [..., "id", "motion"]}` adds
  - **Cryptomatte** layers (`CryptoObject00`, `CryptoObject01`: four ranks of id and coverage, full 32-bit float), with
    the standard metadata (`cryptomatte/<key>/name`, `hash` MurmurHash3_32, `conversion` uint32_to_float32, and the
    `manifest` of names and hashes), so Nuke's, Resolve's or Blender's Cryptomatte picker isolates any part. Each
    object is "<speaker or puppet>/<part>" ("/@<swap>" for a swap drawing). The player's `?idpass=1` draws the cast
    with every part one flat colour (`Puppet.render`'s `ids`: fills, outlines and raster ink through an alpha-threshold
    filter) with crisp edges, at twice the master's scale; coverage is the share of each pixel's four samples.
  - **Forward motion vectors** (`forward.u`, `forward.v`, master pixels): where each pixel's part will be one frame on,
    from the parts' screen matrices now and next (`window.PARTMATS`) and the ID pass. A swap drawing moves with its
    anchor part (a pupil's own glance is not in the vector), and squash is not.
  - The `masterpasses` test, on a span of handshake-demo: all 39 visible objects decode back from the EXR exactly
    (max error 0.0 against the ID render), the ranks add up to the characters' matte (mean difference 0.002), oiiotool
    lists the layers, and warping the next frame back along the vectors matches this frame with a mean error of 0.028
    on the moving pixels, against 0.223 left in place.
  - **Depth** (`depth.Z`, full float): the depth of the nearest compositor plane covering each pixel (1 everywhere in
    a shot without a comp; 0 where nothing is drawn). The player's `?depthpass=1` fills each plane's coverage with a
    colour that encodes its depth in thousandths, crisp and opaque (blends, opacity and light wrap left out, so a
    half-transparent mist counts where it covers more than half). Two traps on the way, both Chromium's: filters work
    in linear light at 8 bits unless told `color-interpolation-filters="sRGB"`, which rounded small code bytes away
    (depth 1 read back as 0.232); and flooding before thresholding the alpha left edge pixels with scaled codes. The
    ID pass's raster filter had both and is fixed the same way. In `masterpasses`, a frame of night-planes holds only
    its planes' depths (8 for 56% of it, 3, 2, 1 for 28%, 0.6), and every character pixel is at 1.
- **HDR10 deliverable** (part 3): `film.hdr {name, white_nits: 203}` encodes the master as
  `build/final_hdr10.mp4`: HEVC Main 10 (x265), BT.2020 primaries, PQ (SMPTE ST 2084), limited range, with mastering-
  display and content-light metadata (MaxCLL is graphics white: nothing in the picture is brighter). The film is graded
  for SDR, so its colours go into the HDR programme as ITU-R BT.2408 asks: linear light, BT.709 to BT.2020 primaries
  (BT.2087), graphics white at 203 cd/m2, with no expansion above white. It is checked by decoding it back. On
  stretch-demo's full 4K master (134 frames, 7 min): the tags all read back; white decodes at 201.6 cd/m2; taken back
  to SDR it matches the master's own picture at 42.3 to 43.2 dB. The decoded peak reaches 215 to 261 cd/m2 at hard
  edges; our assumption, not measured, is that this is 4:2:0 and HEVC ringing above the 203 that was encoded. The
  `hdr` test runs the same check on a three-frame master (201.6 cd/m2; 40.8 to 41.0 dB).
- **Stereoscopic output** (part 3): `film.stereo {name, layout: sbs | anaglyph | both, start, end}` draws the film for
  each eye (the player's `?eye=left|right`) and packs it full side by side (`build/final_stereo_sbs.mp4`, 2W x H, left
  eye first) and as a red-cyan anaglyph (ffmpeg's Dubois matrix, `build/final_anaglyph.mp4`). The depth comes from the
  compositor: each eye sees a plane shifted by half of separation x (1/convergence - 1/depth) (the comp's `"stereo"`, default
  24 px at infinity and convergence 1), so the stage, where the characters stand, is on the screen, farther planes
  behind it and nearer ones in front; a shot without a comp is flat. Test `stereo`: dots on planes at depths 8, 1 and
  0.6 with a separation of 40 sit 34.99, 0.0 and -26.71 px apart between the eyes (35, 0 and -26.67 asked); a span of
  night-planes packs to 2160 x 1920 side by side and 1080 x 1920 anaglyph, 9 frames each.
- **EXR input** (part 3): `comp.ingest_exr {name, src, id, layer, colorspace, view}` turns an OpenEXR sequence from
  another tool (a 3D render, a plate, our own master) into plate frames the player draws (`build/plates/<id>/`, sRGB
  with straight alpha) and returns the comp item. Its colour space is read from the file's chromaticities (ACEScg,
  ACES2065-1, Rec.709, P3-D65 or Rec.2020 primaries, linear; none means Rec.709, as the EXR spec says); `view: aces`
  applies the ACES output transform for scene-referred renders. Test `exrin`: a frame of stretch-demo as our master's
  beauty layer (ACEScg), as a plain linear Rec.709 EXR and with Rec.2020 primaries comes back to the picture it was,
  exactly (max error 0).
- **Linear light** (part 3): a comp's `"linear": true` runs its planes' filters (grade, blur, glow, depth of field) in
  linear light, where light adds as it does in a camera: the `stereo` test blurs a bright dot on a dark field and finds
  the halo at 40 and 60 px at 103 and 54 levels, against 56 and 26 in sRGB. Blending between planes (`blend` nodes,
  plane opacity) in the player stays the browser's, which composites in sRGB (CSS has no linear-light compositing),
  so `comp.linear` does it outside the browser: each plane rendered alone on transparency (the player's
  `?compplane=<id>`, `@top` for the bubbles; `tools/comp_planes.mjs`, which also reads each plane's blend mode and
  opacity per frame), then composited far to near in float linear light (`dbe/master.py composite_linear`: normal,
  multiply, screen, lighten, darken, overlay, plus-lighter, difference; a light wrap screens a blur of what lies behind
  the plane onto its inner edges, as the player's, its `from` read as everything behind). `film.master`
  with `linear: true` takes compositor shots' beauty frames from it. Test `linearplanes`: a red veil at half opacity
  over green comes out at [167, 120, 59], the linear mix exactly (the browser gives the sRGB mix, [135, 104, 59]);
  where nothing is translucent the two agree to the level; a screened soft glow's falloff reads 117 against 103; a
  light wrap on the stage lifts the characters' inner edges by 43 levels and changes nothing deep inside or outside them.

**OpenUSD** (WP-42). `export.usd {name, shot, ascii}` writes the shot as a USD stage (`build/shots/<shot>.usda`, with
its textures beside it; `dbe/usdexport.py`, on usd-core 26.11) from the bake every renderer draws: each part an Xform
whose transform is sampled every frame (the camera folded in), its drawing as meshes (ear-clipped fills) and curves
(outlines with their width), raster drawings as textured quads (UsdPreviewSurface), swap drawings shown only on their
frames, each view a character uses as its own parts shown on that view's frames, bendy limbs with their points
sampled per frame as the player bends them, layer order as depth, and an orthographic camera framing the shot. Open
it in usdview, Blender, Houdini, Maya or Omniverse. It is checked with OpenUSD's own validation framework (30
validators; no errors). Test `usd` on handshake-demo's walk (side views, 270 frames, 36 parts and 36 swap drawings):
read back through OpenUSD, every part's pivot sits exactly where the bake puts it (0.0 px) on three frames, the mouth
shown is the bake's on all six cast-frames, and the stage's own fill meshes, drawn flat, cover the characters as the
player draws them at IoU 0.958 to 0.966 (the rest is the outlines, left out of that check).

## Editor hand-off (WP-22)
`film.handoff {name}` (after `film.render`) writes `films/<name>/build/handoff/`: the shots as rendered (`media/`), the
stems at their mixed level (`audio/voice.wav`, `music.wav`, `sfx.wav`), the captions (SRT, VTT; also markers in the
timelines), each shot's camera per frame (`camera/<shot>.chan` for Nuke-style tools, `.csv` of the 2D camera) and the
cut as timeline.otio (OpenTimelineIO), timeline.kdenlive (KDE's adapter; Kdenlive 25.04 and later open the
OTIO file natively), timeline.mlt, timeline.xml (Final Cut Pro 7 XML: DaVinci Resolve, Premiere), timeline.fcpxml
and timeline.edl (CMX 3600, picture). Every file is read back with OTIO (clips, stem tracks, length); melt plays the
Kdenlive project and renders the MLT one, compared with the shots frame by frame in YUV (identical on our films).

## Sound editing (WP-40)
The Studio sound page (`/sound?film=<name>`, linked from the timeline) draws waveform lanes for the mix, voice, music
and effects (vendored wavesurfer.js 8). Drag a cue on the effects lane to move it (snapped to frames), click it to
change its sound or level or delete it; click a music section's chip, or drag across the music lane, to swap a span to
another kind (main, intro, finale, reflect, none). Remix saves the edits to `films/<name>/sound.json` (`sound.edit`)
and makes the mix again without rendering a frame (`sound.remix`), then reports where each moved cue is heard in the
effects stem and the level of each swapped span. The edits apply on every render: cues are derived again each time
and edits find them by type and nearest time; music swaps cut the score's sections on the beat grid. `sound.lanes`
serves the page; `sound.audacity` writes an Audacity project (the stems at their offsets, cue and music label tracks).

## Drawing coach (plan 1.10)
`puppet.coach` checks a character (a puppet, or a layered drawing before import) and returns advice with measured values
and an annotated PNG (problems circled and numbered): missing parts and swap shapes; joints that do not overlap their
parent, or open a gap when bent (each joint is bent +-50 degrees and the hole beside it measured); pivots outside their
drawing; upper-to-lower limb proportions and left/right mismatch; eyes, pupils and mouths needed to blink, look and
lip-sync; scale on the artboard and feet on the ground line; layers the importer could not place. `puppet.import` runs
it automatically and returns the advice with the puppet.

## Toon shading and finishing (plan 1.7)
- **Toon shading** (`style.toon` on a shot: `true` or `{"dir": [-0.6, -0.8], "d": 11, "shade": "#2a1a10", "opacity": 0.26, "rim": 0.3}`):
  every filled vector shape gets a cel-shadow band on the side away from the light (and an optional rim light towards
  it). Pure SVG: the shape is clipped to itself and repainted shifted towards the light; the light stays fixed in the
  world as parts rotate; outlines are drawn last. Raster and mesh parts already carry their painted light.
- **Finishing** (`"post"` in shots.json: `crisp`, `film`, `warm`, `cool`, `paper`, `noir`, or
  `{"preset", "grade": "<ffmpeg filters>", "vignette": 0-1, "grain": 0-20, "lut": "file.cube"}`): applied to the
  joined picture before captions, so text stays crisp; grain uses a fixed seed. Grain costs file size (fx-demo: 2 MB
  to 10 MB).
Open: cross-dissolves between shots (they change timing), sub-frame motion blur (needs a second render pass).

## Sets and icons (plan 1.6)
`sets/more.js` adds eleven sets drawn in code, each aspect-independent (`draw(t, opts, W, H)`, `floorAt(W, H)`), with a
little ambient life: `kitchen` (kettle steam), `classroom` (`opts.board`: chalkboard lines, any script), `office` (city
window), `street`, `farm` (crop rows, for plant explainers), `bedroom` (`opts.night`), `forest` (parallax depths), `lab`
(bubbling flasks, live monitor), `night` (twinkling stars), `reservoir` (an earthen bund in cross-section,
`opts.level` 0-1, `opts.paper` for an ink-on-paper look) and `stage` (presenter spotlight). With the five originals
that is 16 sets. Icons: every Lucide icon (2015, ISC, `assets/icons/lucide.js`) as a kit element
`{"type": "icon", "name": "droplets", "x", "y", "size", "color", "badge"}` that pops in.

## Character generator and cast (plan 1.5)
`cast.generate` makes an original, fully rigged humanoid from a short spec and registers it (CC0, the spec recorded as
provenance): `build` (slim, average, broad), `age` (child, teen, adult, elder), `skin`, `hair` (short, bob, long, curly,
bun, ponytail, spiky, bald, hijab), `top` (tee, shirt, hoodie, sweater, jacket, dress, overalls), `bottom` (trousers,
shorts, skirt), `shoes`, `eyes`, `accessories` (glasses, beard, moustache, freckles, earrings, tie). Every character gets
the template parts, blink, pupils with iris colour, four brows, eight mouths, hand poses, a `turn` control and springy
hair, so it works with every clip and acting tool. `cast/generated/specs.json` holds the starting cast of twelve (Ama,
Ravi, Mei, Olu, Sana, Kofi, Lena, Tomas, Nimal, Zara, Ike, Priya); all pass the drawing coach with no warnings.
Strokes may set `"rule": "evenodd"` for shapes with holes (the hijab's face opening).

## Rig Canvas drawing upgrade and model sheets (plan 1.4)
The Rig Canvas (`puppet/canvas/index.html`) now has:
- **Ink** strokes from perfect-freehand (MIT, vendored): pen pressure when there is a pen, speed-simulated pressure with a
  mouse; outlines simplified (Ramer-Douglas-Peucker) so drawings stay light. Fill shapes are simplified the same way.
- **Bucket**: click inside an area outlined in ink and it fills with the selected palette slot; gaps up to about 10 px in
  the outline are closed for you, the fill is tucked under the ink, and an open outline is refused with a message.
- **Sheet**: a model sheet of the character (rest, wave, turned both ways, every drawn view; every mouth, brow, eye state
  and gaze close up), downloadable as SVG. `puppet.sheet` renders the same sheet to PNG (`tools/sheet.mjs`,
  `puppet/loader/sheet.js`).
- **Boards** (WP-18, the menu beside Sheet; `puppet.board` renders them to PNG): the **mouth chart** puts every mouth
  shape side by side in close-up, each with a blue onion ghost of the closed mouth, so size, placement and line
  weight can be compared; **expressions** does the same for brows, eyes, gaze and the five emotions, over a ghost of
  the neutral face; the **turnaround** stands the front view, every other view and each view mirrored (the other
  side) on one ground line at one scale, with the front view's height lines across them (top of head with what
  hangs from it, eyes, chin, hips, knees, ground). Boxes are measured on the rendered drawing (`getBBox`), so any
  path data and raster parts count. For a turnaround `puppet.board` also measures each view's landmarks against the
  front's and lists views off by more than `tolerance` (3% of the height). The `boards` test renders Pip's three
  boards (the mouth chart's ghost shows as 798 changed pixels when the closed mouth is emptied), finds the side view
  on model, and catches a copy whose side view stands 40 units taller at the hips (4.9% off).

## Gesture planner (plan 2.3)
`acting.plan` makes every speaking cast member act from the script and the voice, with no hand-placed clips. Emphasis
per word comes from the recorded voice (loudness, pitch via WORLD, length per letter, as z-scores within the line):
beats land on the most emphasised words (at most one every 0.9 s); one point per line on a pointing word ("you",
"this", "look"...), aimed at the listener (`point_R` or the new mirrored `point_L`); open palms on an exclamation's
strongest word; a shrug (humanoid) or tilt (doodle) ending a question. Listeners look at the speaker, nod after each of
their lines and blink on their pauses. Gesture clips get weight 3 so they read over the idle loop. Generated clips are
tagged `"auto": true` and replaced on each run; hand-placed clips are kept. `films/dialogue-demo` (Ravi and Priya,
classroom) is acted entirely this way.

## Camera grammar (plan 2.6)
`"camera_auto": true | {"zoom": 1.45, "zoom_single": 1.9, "medium": 0.62, "punch": 0.05, "handheld": 0.3, "ease": 0.6}` on a shot
without camera keys frames it automatically, as a pure function of time: a waist-up medium shot on whoever is speaking
(from 0.3 s before the line), a wide shot fitting the whole cast otherwise, eased between; small punch-ins on emphasised
words (long or exclaimed); seeded handheld drift; clamped so the frame never leaves the set; heads kept high, with room
below for captions. Explicit `camera` keys always win.

## Automatic foley (plan 2.7)
`"foley": true` in shots.json adds sound cues found in the motion itself (`window.FOLEY` in the player, run by
`tools/foley.mjs` during `film.render`): a footstep each time a walk clip's foot contact turns on, a thud when a
character lands (hips decelerating after a drop) and on each bounce of a dropped prop (quieter each time), a swish when a
hand passes 1400 px/s, and a small pop where a prop is caught. Each cue is panned by its screen position. New
synthesised sounds in `engine/audio.py`: `step`, `thud`, `swish`; any cue may carry `pan` (-1 left .. 1 right).

## Visual lint (plan 2.8)
`python -m dbe film.lint '{"name": "FILM"}'` plays the film in the player (`window.LINT`, run by `tools/lint.mjs`,
every 3rd frame) and reports picture problems in screen space, camera included, as frame ranges in `build/lint.json`:
- **error**: a head cut by the frame while the body is in shot; a speech bubble covering a face;
- **warn**: a hand leaving the frame; feet cropped in a wide shot (camera zoom under 1.05, where nothing should be
  cropped); a face in the caption band; an arm locked straight because its IK target is out of reach; a prop inside
  the head of someone who is not holding it;
- **info**: a silhouette just touching the frame edge, or two characters just touching.

Characters who are wholly out of shot (the camera is on the other speaker) are skipped, and one-sample warnings
(a camera move passing by) are dropped. `qa.run` (so also `film.render`) runs the lint and reports the counts as
`lint`; it is advisory unless shots.json says `"qa": {"enforce": ["lint"]}`, which fails the film on any error.
`python -m dbe test` includes `tests/lint/broken_staging.json`: the dialogue demo staged badly on purpose, and each
listed check must fire.

## Sound-off cut (plan 2.13)
Most viewers scroll with the sound off, so every film can ship a second cut made for reading.
`python -m dbe film.soundoff '{"name": "FILM"}'` (or `"soundoff": true` in shots.json, which makes `film.render`
build it too) writes the derived film `FILM--soundoff` and copies its render to `build/final_soundoff.mp4`:
- no voice: music and effects only (`score.json "voice": false` in the derived film; the music is not ducked);
- every line spoken by someone on screen becomes a speech bubble; narration with nobody to speak it keeps the
  word-timed captions (`"caption_lines"`);
- each line is held long enough to read: 0.4 s plus its words at `wpm` (default 170), at least 1.2 s, at most
  `max_stretch` (2.5) times its voiced length. Lines that still fall short are reported (`short_by_s`).

The hold is a time warp, not a freeze: shots.json `"timewarp": [[cut time, film time], ...]` makes the SVG player
render on the cut's clock and show the film at the warped time (`window.TIMEWARP`), so a held line plays its
acting slower instead of stopping. Effect cues and captions are re-timed through the same warp. Only SVG-player
shots can be warped for now.

Speech bubbles are laid out in screen space after the camera (they used to be drawn in the world and could be
zoomed out of frame), and in shots with bubbles `camera_auto` frames singles less tight (`zoom_bubble`, 1.5) with
the head top at about 31% of the frame, leaving room for the bubble above it.

Move-bound sound accents, added to automatic foley: a boing each time a character's hips leave the ground fast
(`"foley": {"hop": "swish"}` or `false` to change it), and a pen-scratch bed (`scratch`, synthesised, with a
duration) while a kit `draw` element draws itself (`"sound": false` on the element, or `"foley": {"scratch": false}`).
Any cue may carry `dur` for sounds that last.

## Clip library, chains and principles (plan 2.5)
The humanoid library has 23 clips (doodle 10): idle, walk, run, jump, nod, shrug, think, surprised, wave_R/L,
point_R/L, present_R/L, talk_beat, talk_open_palms, celebrate, clap, cross_arms, scratch_head, facepalm, sad, stomp.
Jump, run and stomp carry foot contacts, so foley (step, landing thud, hop boing) and dust find them.

Puppet format v0.6 (puppet/spec/puppet-format.md) adds joint limits, FABRIK chains, emotion-aware mouth charts and
an anticipation/overshoot filter, all inside `Acting.evaluate`, so the bake, `dbe/geom.py` and every exporter get them
from the baked angles. The generator takes `"tail": {"segments", "length", "color", "color2", "wag", "spikes"}`;
Momo (cast/generated/momo) wears a dino hoodie with a six-segment tail. In a shot timeline:
`"chains": {"tail": [[t, [x, y]]]}` (reach), `"emotion": [[t, "happy"]]`, `"principles": {"snap": 0.35}`.

Clip blending changed: a gesture at weight 1 now plays at full size over idle (foreground clips override the base
layer per track) instead of being averaged with it. The gesture planner's weight 3 still works. `films/clips-demo`
shows all of it and renders the same in SVG, Lottie and Synfig.

## Beat grid and master-to-many cuts (plan 2.14)
A production is rendered once per aspect (the master: `film.render`, plus `film.render` with `"aspect": "16:9"`) and
cut many ways from it.
- **Grid:** `python -m dbe film.beats '{"name": "FILM"}'` gives the score's beats and bars (from `score.json` bpm and
  offset) and how far each shot change and line start sits from them. `"beat_cuts": true` in shots.json moves every
  shot change onto the bar line in the pause it falls in (else the nearest beat, never into a line), so scene
  changes, episode splits and music phrases coincide.
- **Edit list:** `films/FILM/edit.json` declares the cuts:
  ```json
  {"cuts": {"full": {"aspect": "16:9", "ranges": "all"},
            "ep": {"aspect": "9:16", "split": 4},
            "teaser": {"aspect": "9:16", "ranges": [["m1.start", "m1.end"], ["m5.start", "p3.end"]]},
            "recap": {"ranges": [{"film": "other-film", "from": "bar:2", "to": "l3.end"}]}}}
  ```
  Range ends are seconds, `bar:N` or line-relative times. Each is snapped outward: out of any spoken line, then onto a
  bar line in that pause, else a beat, else the middle of the pause. `split` makes N episodes at the scene changes
  (or the longest pauses nearest to equal parts). A range from another film is an insert, cut on that film's grid.
- **Assembly:** `python -m dbe film.cuts '{"name": "FILM"}'` (`plan_only` to see the cut points, `only` for some
  cuts) writes `build/cuts/<cut>.mp4`, a `.srt` on the cut's clock and an OpenTimelineIO `.otio` edit (Timeline.1
  JSON, no library needed) for finishing in an NLE. Picture comes from the master render. Audio comes from the
  master's mixed stems (voice, music, effects at their mixed levels, so each segment sounds as it does in the master),
  with equal-power crossfades at joins, the music faded in when a cut starts mid-score and out over the last 0.9 s,
  levelled to -14 LUFS with the master limiter. Each cut reports its loudness and true peak.

`films/moon-night` is the test production: a four-scene story made once, cut into the full film at 16:9, four 9:16
episodes and a teaser.

## Phone-level lip-sync and the lip-sync check (plans 2.1, 2.2)
**Alignment.** Kokoro predicts how many 25 ms frames each phoneme lasts before it makes any sound. `engine/kokoro_voice.py`
exposes that duration output once (`timed_model` writes `kokoro-v1.0-timed.onnx` next to the model, with the `onnx`
package from requirements-audio.txt), and kokoro-onnx turns it into phoneme timings. Measured over five voices and
21 lines against the audio, those timings sit about 80 ms after the sound, so they are shifted back by `PHONE_LEAD`
(0.08 s). `engine/voice.py` then takes, for every Kokoro line:
- visemes from the phones (`visemes.phone_visemes`): stress and length marks extend the phone before them, a
  silence between phones (the pauses Kokoro inserts after punctuation) closes the mouth;
- word times from the phones (`visemes.phone_words`): spoken words between spaces are grouped with the script's
  words by a small DP on phoneme counts, so "for a" run together, "25" read as two words and "Dr." all map;
- `"align": "model"` on the line in timing.json (`"whisper"` when it fell back).
Compared on the same audio, the previous method (Whisper word times, phonemes spread across each word) was 70-87 ms
off on average and showed the right mouth class on only 24-33% of frames. With timings on, Kokoro also inserts its
sentence and clause pauses, so re-voiced lines can be a little longer than before. Piper voices and recordings still
use Whisper words with spread phonemes.

**Check.** `python -m dbe lipsync.check '{"name": "FILM"}'`, also run by `qa.run` as the `lipsync` check, compares each
speaker's viseme track with how open the jaw should be, read from `build/voice.wav` as first-formant energy
(300-1200 Hz) inside that speaker's lines. It reports the best lag (positive: mouths after the voice) and the
correlation there, and fails beyond +-2 frames or below 0.2. With `DBE_RHUBARB` pointing at a Rhubarb Lip Sync
binary (MIT), each line is also read by Rhubarb and its Preston Blair cues are compared class by class (closed,
narrow, open, round; fails below 50% agreement).

## Self-healing and layout auto-repair (plans 2.9, 2.18)
`python -m dbe film.heal '{"name": "FILM"}'` renders the film, reads every failure (the QA bar, all measured layout
checks including the advisory ones, and visual-lint errors), applies the known repair for each to shots.json,
re-renders what changed (incremental shot hashes) and repeats, up to `rounds` (3). Before re-voicing it anchors
hard shot times to their lines, so the picture follows the slower voice. The shots.json from before the
first round stays in `build/shots.before_heal.json`; the result lists each round's failures and edits, and what still
fails with the reason a person is needed (for example cold open, or bare frames with no character to enlarge). Repairs
(`dbe/heal.py`):
- frozen stretch: low `style.step` goes back to 12; a shot with no camera gets the float camera; cast get idle;
- text outside the safe area: moved in by exactly the overshoot plus 8 px (`x`/`y` of the kit element);
- type too small: size raised to the platform minimum (26 px for 9:16, 24 px for 16:9);
- reading time: a timed text block stays up words / 3 + 1 s, within its shot; captions flowing faster than 3.2
  words/s re-voice the script slower when `revoice` is true (then the gestures are re-planned);
- frame fill: the shot's cast is scaled up once (feet stay on the floor, at most 1.3x); if the next render shows
  the bare share down by less than 3 points the scale-up is undone (the shot needs content, not a bigger character);
- lint, head cut by the frame: an auto camera frames singles less tight; a static shot scales the character down
  and moves it in; lint, bubble over a face: an auto camera leaves more headroom, else that shot goes back to
  captions.
`films/heal-demo` is the kit demo with failures seeded on purpose (animation once a second, a 20 px sign up for
0.8 s, the title below the safe area).

## Acting from prose, gags and rig-aware writing (plans 2.4, 2.11, 2.12)
**Directions.** A script line can carry `"direction"` (anchored to that line), a shot can carry one too, or text can
be passed straight to `python -m dbe acting.direct '{"name": "FILM", "text": "...", "shot": "s1"}'`. One action per
sentence (or clause after "then"):
- who: a speaker in the shot; he, she, they = the last one named;
- when: `when Ravi says 'back'` (that word), `after/before/during the line` or `after Priya's line`, `at the start`,
  `at the end`, `then` (after that character's previous action), else with the line (or right after the same
  character's last action);
- what: an emotion (happy, sad, angry, surprised, worried/nervous, neutral and synonyms), a gaze (`glances at` is
  brief, `looks at` holds), `walks to` someone (moving placement plus the walk clip), or one of the clip verbs: nod,
  shake their head, shrug, clap, jump, celebrate/cheer, facepalm, cross their arms, think, scratch their head,
  stomp, slump/sigh, wave, point, present/show, run (wave, point and present turn toward their target);
- at whom: another character, or the camera, up, down, left, right, the sky, the moon, the board, the door;
- how: slowly, quickly, a little, hugely (speed and size).
The result is written into shots.json line-relative where it was anchored to a line, so re-voicing keeps it on the
words. Directed clips are tagged and the earlier gaze, emotion, blinks and placement are kept under `undirected`, so
running `acting.direct` again replaces the last direction instead of piling up. With exactly two characters, an
untargeted gaze goes to the other one. `acting.plan` (talk gestures from the voice) and `acting.direct` combine: run
the planner first.

**Gags** (`dbe/director.py`): `does a double take` (look, look away as if nothing happened, a beat, snap back
surprised with a blink), `gives a long stare` (2.6 s held look, blinks on a slow count, idle damped), `slow burn`
(neutral to the camera, then angry, arms crossed), `deadpan` / `looks at the camera`, `button` (a small happy nod),
`rule of three` (three times / three verbs: twice as set-up, the third bigger and later).

**Rig abilities.** `python -m dbe puppet.abilities '{"puppet": "cast/generated/momo.puppet.json"}'` lists what a
character does for free (clips whose parts it has, emotions whose mouths and brows are drawn, glances, blinks,
lip-sync, turn, tail) and what each costly move needs drawn. `python -m dbe script.rigcheck '{"name": "FILM"}'` reads
every direction in the film and lists per character the moves that are free and exactly which drawings are missing,
with the sentences that need them. `films/direct-demo` is staged from its directions alone; with Momo recast as the
doodle Nib, the same script asks for seven drawings (pupils, two brows, two mouths, a shrug and a head-scratch clip for
the doodle template).

## Narration slots (plan 2.16)
`python -m dbe script.slots '{"name": "FILM", "wpm": 135}'` gives every script line a fixed `"slot": [start, max_s]`
(words at `wpm` plus 0.25 s, the script's gaps and pauses between) before any voice exists. With no voice yet it also
writes a draft timing.json from the slots (words spread by letters), so the picture and the sound-off cut can be made
first: the sound-off cut is the master. From then on `voice.build` places every line at its slot start and keeps the
slot's end as the line's end, so line-relative shot times never move. A line longer than its slot uses its short
alternate (`"alt"` in script.json) if that is shorter, then up to 15% faster speech; whatever still overflows runs
into the following pause and is reported (`overflow_s`; `fit` says what was done; `spoken` when the alternate was
used). `films/slots-demo` was cut on slots, then voiced twice with different casts (the second slowed 35% so line l3
falls back to its alternate and l4 speeds up 1.18x): the shot changes are identical in all three states
(s1 0-7.283 s, s2 7.283-17.338 s).

## Data-bound visuals and original analysis (plan 2.17)
Every number on screen or in the narration can come from `data.json`, written by the film's own analysis:
- `films/FILM/analysis/sources.json` lists the inputs: `{"id", "file", "url", "terms", "version"}`. `film.data`
  downloads each `url` once into `analysis/cache/` (again only with `refresh`), and records the access date and
  sha256; local inputs just get their hash.
- `analysis/*.py` run in name order with DBE_PY, from the analysis folder, reading the cache and writing
  `../data.json`. `film.data` adds `_provenance` (script hashes, sources with terms, version, access date, sha256).
- Bindings: any text in shots.json or in script lines may hold `{{path}}` or `{{path|format}}` (`1` decimals,
  `comma`, `int`, `pct`, `pct1`, `word`, `upper`); paths walk data.json (`best.month`, `monthly.2.1`). A chart's
  `data_from` is inlined. Bindings are filled when shots are resolved and when the script is voiced (voice.build
  refuses unresolved bindings).
- `python -m dbe film.data '{"name": "FILM", "revoice": true, "render": true}'` reruns the analysis and reports which
  data keys changed, which shots' pictures change and which narrated lines' words change, then re-voices those
  lines and re-renders only those shots (shot hashes cover only the lines and mouth cues a shot shows).
`films/data-demo` charts an illustrative club log (labelled as demo data). Changing one month in `analysis/cache/log.csv`
re-rendered the chart shot and the "best month" shot and re-voiced their two lines; the intro shot stayed as it was.

## Format templates (plan 2.15)
`python -m dbe film.from_template '{"name": "NEW", "format": "dialogue", "brief": {...}}'` writes a whole
storyboard from a format and a brief, then checks it:
- formats (`dbe/formats.py`): `myth_vs_data` (myth, question, finding, why, source), `explainer` (hook, point,
  detail, source; optional question; the calendar's analysis and news slots), `dialogue` (topic and
  `exchanges` of q/a; the learner asks, the expert answers, E28), `wonder_story` (imagine, build, reveal, reflect),
  `we_reran_it` (old_claim, new_finding, changed, source), `anniversary` (years, event, changed, now) and `series`
  (`parts`, each with its own format; edit.json splits it into episodes). Any beat's text can be overridden in
  `lines`, roles recast in `cast` (default expert Ravi, learner Momo, narrator Priya), sets in `sets`;
- every film gets script.json with narration slots (135 wpm, draft timing), one shot per scene (line-relative,
  listeners added in conversation scenes, an auto camera when two or more are on screen, a float camera when none),
  kit signs held words / 3 + 1.2 s, prediction prompts ("What do you think?") that stay up through the question and
  a silent count before the reveal, charts from `data`, citations, and facts marked `needs_check` until sourced;
- `python -m dbe storyboard.check '{"name": "FILM"}'` runs the cold-open rule (a character in frame one, words by
  1.5 s) and the reading-time rules (signs up long enough, captions at most 3.2 words/s) on the storyboard before
  or after voicing, and lists facts still waiting for a source.
`films/telescope-talk` came from the dialogue template and a three-question brief; it passed the storyboard check
before voicing and the full QA after.

## Studio timeline (plan 3.1)
`python -m dbe serve` then http://127.0.0.1:8770/timeline?film=FILM (also linked from the Studio header). The page shows:
- a live preview (the film's own player page, scaled): click or drag the ruler to scrub, Play (space) runs it
  against `build/mix.wav`;
- lanes: shots, one dialogue lane per speaker (lines with word ticks), and one lane per character with their clip
  layers (hand-placed orange, planned from the voice grey, from directions purple; overlapping clips stack in rows,
  looping base layers such as idle run as a thin bar);
- editing: drag a clip to re-time it (its end moves with it), drag its right edge to change its length, double-click
  a character's lane to add a clip, Delete removes the selected clip, ←/→ nudge one frame (Shift: ten), Ctrl+Z
  undoes. Moves snap to frames, and to word starts within 6 px ("snap to words").
Every edit goes through `timeline.edit` (`move_clip`, `resize_clip`, `add_clip`, `delete_clip`) into shots.json and
the preview reloads. A time written line-relative stays line-relative (`l2.start+0.61`), re-anchored to the line
the clip now sits by when it moves away from its old one, so re-voicing still carries the edit; a planned clip that
is edited by hand loses its `auto` tag, so `acting.plan` keeps it. `timeline.get` returns what the page draws;
`film.preview` writes the player page. `tools/timeline_check.mjs` drags a gesture in a headless browser.

**Cuts, lines and camera keys on the timeline** (WP-19). The cut between two shots has a handle on the shots lane:
dragging it moves the first shot's end and the next shot's start together (`timeline.edit` `move_cut`; a cut at
less than 0.3 s from either shot's other end is refused). A line on a dialogue lane can be dragged:
`timeline.move_line {name, line, start}` changes the silence before it (the pause after the line before, the lead-in
for the first, or the slot of a slotted line) and re-voices the film, so the lines after it move with it and
everything anchored to lines follows; Undo restores script.json and re-voices. The **camera lane** shows each shot's
camera keys as diamonds: double-click adds one (`add_camkey`) with the framing the shot already has there, anchored
to the line it sits by; drag re-times it (`move_camkey`), selecting it shows its framing to type (`set_camkey`
[x, y, zoom]), Delete removes it (`delete_camkey`). Test `timeline2` (only when asked: it re-voices a scratch copy of
pip-park twice) drives the page in Chromium: the cut moved 0.39 s for a 0.40 s drag (to the frame), a camera key
added as `mid.start+2.03` at [540, 960, 1], moved 0.3 s, set to zoom 1.2 and deleted, and the last line moved 0.38 s
for a 0.36 s drag (to the frame, after re-voicing) with the line before unmoved, then undone.

**Notes about the timing of lines** (WP-19). `review.fix` reads a note about when a line comes in ("give the last line
a beat before it", "the pause before the first line is too long", "the answer comes in too late", "less of a gap
before the second line by 0.3 s"; `dbe/review.py timing_intent`; notes that name a gesture, a body part or the camera
are left to the other readers) and finds the line: named (an id in quotes, first, second, last), else the one under
the note's frame, else the next. It changes the silence before it by the amount (a beat 0.5 s, a bit 0.25, a lot 0.8,
or "by 0.3 s" or "by 10 frames") through `timeline.move_line`, re-voicing, and the critic listens: in the voice track,
the line's speech must start later or earlier by at least 60% of the asked amount, measured from the end of the line
before, and no earlier line may move. Then the film is rendered and QA must not get worse; otherwise script.json is
restored and the film re-voiced. Test `reviewtiming` (only when asked: it re-voices and renders a scratch copy of
pip-park): "give the last line a beat before it" moved the speech onset +0.50 s (+0.50 asked) and "the pause before
the first line is too long" -0.40 s (-0.40 asked), both verified; "this line feels somehow wrong" went to a person.

**Over-the-shoulder framing** (WP-19, `shot.ots`, `dbe/framing.py`). Look past one character (`over`) at the other
(`on`), for a whole shot or, with `line`, only while a line plays: the shot is cut into before / over-the-shoulder /
after, the cuts written as line-relative times (just before the line starts and just after it ends, within half the
gap to the lines around it; a piece under 0.8 s joins the over-the-shoulder shot). The camera is held (one key) on
`on` at the size asked (MS by default, MCU, CU: the share of the figure shown, capped by how wide its head may be in a
tall frame) with its head on the far third. `over` is drawn 1.45 times its size on screen, its head just reaching the
other's, at least 30% of the frame width in from the near edge and cut by it, drawn last (in front; cast references
renumbered), quiet (its big gestures in that shot dropped, since one started earlier can hold into it) and seen from
behind: a `views.back` made from its puppet (the face swaps and face parts drawn empty, the head's face marks gone and
its skull filled with the hair colour, the back hair over the head, left and right limbs swapping depth about the
torso), written beside the film as `cast/<name>.back.puppet.json` unless the puppet draws its own. It keeps the side of
the frame it has in the wide shot, so the 180-degree line holds. Everything is a camera key, a place and a view key,
which the shared bake carries to every renderer. `film.continuity` names an over-the-shoulder shot's size from `on`
(the near character is bigger but is not what the shot shows) and checks that `on`, where it looks sideways, looks
toward `over`. `review.fix` reads notes such as "make Momo's answer an over-the-shoulder" or "over Ravi's shoulder on
Momo for the second line" (`dbe/review.py ots_intent`): the line named, or that speaker's line nearest the note, or the
one under it; whom we look at named, else the line's speaker; past whom named, else the other character. The critic
measures the baked frames (`ots_measure`): `on` at a medium shot or closer, its head in frame and at most 15% under
the near head, `over` cut by the frame, in front and on its wide-shot side; then continuity and QA, or the shots are
put back. Test `ots` (only when asked) on a copy of review-demo: "Make Momo's answer an over-the-shoulder", pinned
during Ravi's first line, framed line l2 over Ravi's shoulder; "over Momo's shoulder on Ravi for the third line" framed
the reverse on l3. Both verified: the on character at MS with 6% (5.5%) of its head under the near one, the near
one cut by the frame on its wide-shot side (left, then right) and seen from behind; continuity has no issue, the
left-right order Ravi, Momo in all four shots (FS, MS, MS, FS, the over-the-shoulder ones named from Momo and Ravi);
QA holds; the over-the-shoulder shot from Synfig, Lottie and Grease Pencil matches the SVG renderer's (parity 1.0,
1.0, 0.999).

**Curve editor** (WP-19). A key may carry the easing of the move that leaves it, as a third element: `[t, value,
ease]` with `smooth` (the default, smoothstep, as before), `linear`, `hold` (the value stays until the next key) or a
cubic Bezier `[x1, y1, x2, y2]` as in CSS (y may overshoot). `Acting.sampleKeys` plays it, so the player, the bake
and every renderer follow, and `dbe/keys.py` (loaded by Blender's camera script) does the same in Python; line-relative
times resolve on three-element keys too. On the timeline, a selected camera key with a key after it shows the curve
(time across the move, how far along it is up the side), drawn by `Acting.ease` itself: presets (smooth, linear, ease
in, ease out, ease in-out, overshoot, hold) or the two handles dragged, saved on release (`set_camkey` `ease`). In
`timeline2`, "ease in" is stored as [0.42, 0, 1, 1], a dragged handle as [0.42, 0, 0.81, 1.35], a curve that
overshoots (the zoom, moving from 1.2 to 1.4, peaks at 1.411 before it settles); the JS and Python samplers agree
exactly on that move (and to 1e-15 on every preset).

## Storyboard strip and animatic (plan 3.2)
`python -m dbe film.storyboard '{"name": "FILM"}'` takes one still per shot from the player (a moment into the
shot's first line, so the auto camera is on the speaker; the middle of the shot when nobody speaks; drawn without
captions) and writes to `build/storyboard/`: `strip.png` (every shot in a grid with its id, times, set and lines),
`contact.pdf` (three shots a page with notes: times and length, set, cast, the lines, and any directions), and the
stills (`s1.png`, ...). `python -m dbe film.animatic '{"name": "FILM"}'` holds those stills for their shots' lengths
over the film's sound (the mix if rendered, else the voice) as `build/animatic.mp4`, in seconds, for judging pacing
before a render. Studio has Storyboard and Animatic buttons; the timeline has Animatic.

## Posing in the Rig Canvas (plan 3.3)
The Rig Canvas has a **Pose** tool. The character stands on the ground line with handles: hands and feet (orange)
are placed by two-bone IK (`Acting.ik2`, the solver films use; Shift flips the elbow or knee), the head and chest
(blue) turn about their joints, the hips (green) move up and down with both feet kept planted (the legs are
re-solved, knees splayed outward). Joint limits apply. Mouth, brows and eyes come from the character's drawn
shapes. **Save pose** stores it in the character's `poses` (used by `poses: [[t, name]]` in any timeline); **Key**
records the current pose at a time and **Save clip** turns the keys into a clip in the character's own `clips`
(puppet format v0.7), which `Acting.evaluate` merges over the template library, so shots, the bake and every
renderer play it. Saved poses and clips also appear in the live preview menu. Opened from Studio (served by
`python -m dbe serve`), **Save to cast** writes the character through `puppet.save` (schema-checked, only under
`cast/`, new files registered in the cast library). `tools/pose_check.mjs` does the whole round in a headless
browser; the golden case `tests/poses/rig_canvas_pose.json` plays the saved pose and clip.

## Review room (plan 3.4)
http://127.0.0.1:8770/review?film=FILM (linked from Studio): the render with frame stepping (`,` `.`), a bar with
every note pinned at its frame, and a box to pin a note at the current frame. (Where the browser cannot decode the
render, the page shows the live player at the same frame instead.) **Fix open notes with the critic** runs
`review.fix`:
- the note is read (`dbe/review.py interpret`): what to change (earlier, later, faster, slower, bigger, smaller,
  longer/hold, shorter, remove), by how much ("by 10 frames", "by 0.5 s", "a bit", "a lot"), which body part,
  character, side and gesture it names;
- the clip making that motion at that frame is found (`locate`): the named character, a clip whose tracks move that
  part, active at the frame or the move just before or after it; the part to measure is what that clip moves most;
- the edit goes through `timeline.edit` (move, resize, `set_clip` speed/gain, delete); gestures that come back to
  rest are slowed or sped up to hold longer or shorter, poses that hold are extended;
- the critic probes the part's on-screen path over the same window before and after (`window.PROBE`,
  `tools/probe.mjs`): an earlier move must reach half-way sooner by at least 60% of the asked amount, a bigger one
  must travel 10% further, a slower one must take 10% longer, a longer hold must last 0.15 s more, a removed one must
  all but stop; then the film is re-rendered and QA must not get worse. Verified notes close with an after-still in
  `build/review/`; anything else is reverted and marked `needs_human` with the reason.
Notes live in `films/FILM/review.json` (`review.add`, `review.list`, `review.fix`). `films/review-demo`: "raise
the arm earlier" on frame 120 moved Momo's shrug 0.33 s earlier (measured 0.33 s), "Ravi should point bigger" on
frame 180 (379 px, was 300), "hold the scratch head longer" (held 1.65 s, was 1.16 s); "this bit feels off somehow"
went to a person.

**Review on a phone** (WP-19). `python -m dbe serve 8770 0.0.0.0` (or `DBE_HOST`) serves the Studio to other
machines on the network and prints a link with a key (`DBE_KEY`, else a new random one each start): the API runs any
command, so a request from anywhere but this machine is refused (403) unless it brings the key, once in the link and
then as an HttpOnly cookie. The review room fits a phone: the picture takes at most 56% of the screen height, the
bar is 40 px tall and scrubs under a thumb (tap or drag), the frame buttons are full-width, and the note box stays at
the bottom of the screen (16 px text, so iOS does not zoom). Test `reviewphone`: the key gate checked over HTTP from
another loopback address (page, API and a wrong key refused; the key lets in and sets the cookie, which then works
for the API); on an emulated iPhone 13 (390 x 664) nothing scrolls sideways, a tap at 30% of the bar lands on frame
130 and a drag to 60% on frame 260 (both exact), a step goes to 261 and a note pinned from the box lands on 261.

**Gaze notes (WP-19).** A note about where someone looks ("Ravi should look at Momo when she answers", "Momo should
look at Ravi during l3", "make Ravi glance at Momo while she talks", "look away from ...") is read for who looks, at
whom, and when: the target's line at or next after the note's frame, a line by id, or while they talk. The look keys
over that line are set toward the other character (by where each stands, in screen terms), line-relative so they
follow re-voicing: the turn starts just after the last earlier key that looks the same way (at most 0.2 s ahead of
the line; a key in the half second before that looks elsewhere is dropped, so the eyes do not flick away first) and
eases back 0.3 s after the line to the look the curve had there. The critic probes the gaze over the line
(`window.PROBE(ci, '@look', ...)`) and needs the asked direction in at least 90% of its frames and more than before;
then the film is re-rendered, QA must hold, and the note records the diff. On `review-demo` Ravi now looks at Momo
in 97% of her answer's frames (was 0%: he looked to camera from 3.3 s).

**What changed (WP-19).** `film.diff` compares two versions of a film; `review.fix` keeps the version before each fix
(`build/versions/prev.mp4` and its keys). Each render keeps a key per frame (`build/frame_keys.json`, from the
markup keys the SVG renderer writes per shot: what the frame draws, both shots inside a transition, the caption
showing and the finishing), so a frame is changed exactly when its key differs; re-encoding moves pixels in every
frame, and comparing pixels instead marked 319 of `review-demo`'s 433 frames for that gaze fix. By keys: 64 frames,
3.27-4.20 s and 4.33-5.53 s (the gap is a blink, when the pupils are hidden and the gaze cannot show). The result
has a box per changed frame and a strip of the most changed (before, after, the change in red: Ravi's eyes). The
Studio page http://127.0.0.1:8770/diff?film=FILM ("What changed" in the review room) marks the changed spans on a
bar, steps from change to change and shows both versions side by side at that frame. The `gaze` test does all of
this on a copy of `review-demo` (Ravi's look put back to camera first): verified at 97% from 0%, no changed frame
outside the line's window, and the page shows the same spans.

**Placement and camera notes (WP-19).** "Ravi should stand a little further left", "Momo is too far right", "move Ravi
closer to Momo", "Momo should step away from Ravi" (the character named first moves; 120 px, 60 for "a little",
240 for "a lot", or "by N px"), and "push in" / "go wider" / "too tight". A placement note moves the cast entry's
`place.x`. A camera note steps the shot's automatic camera 0.25 closer or wider, as the director's desk does; a
shot with hand-set camera keys is left to a human. The critic measures on the baked frames. The character's median
screen position must move the asked way by at least half the distance, or the main character's height on screen must
grow or shrink by 10% (the shot size is reported, ELS to ECU). `film.continuity` must find no new issue: a move that
puts two characters on the wrong sides of the line across a cut is reverted. Then the film is rendered and QA must
hold. Test `layoutnotes` on a copy of `review-demo`:
- "Ravi should stand a little further left": verified, 300 -> 240 px on screen;
- "push in on this": verified, Ravi 818 -> 1759 px tall, full shot -> medium long shot. The shot had no automatic
  camera, so the note turned it on one step closer than its defaults: a large first step;
- "Priya should stand further right" (nobody of that name in the shot): left to a human.

**Review in OpenRV or xSTUDIO** (WP-19, through OpenTimelineIO). `review.otio_export` writes
`build/review/<film>_review.otio`: the finished film as one clip with a marker per note at its frame. The note's text
is the marker's name and its status the colour (open red, verified green, needs a human yellow); id, reviewer and
status go in the marker's metadata. A reviewer opens it in a tool that reads OTIO and adds markers. `review.otio_import`
turns each new marker into a note at its frame, and leaves alone the markers that came from notes, or were imported
already. Test `reviewotio`: two notes go out at frames 60 and 102; a marker added at 4.5 s comes back as a note at
frame 135; a second import adds nothing. Neither OpenRV nor xSTUDIO is installed here, so the round trip is checked
with the OpenTimelineIO library they use, not in the players themselves.

**Continuity** (`film.continuity {name}`, `dbe/continuity.py`, WP-19), measured on the baked frames (screen positions
with the shot camera folded in), written to `build/continuity.json`:
- *180-degree rule*: each pair of characters keeps the left-right order of the last shot that showed them both (a
  scene, not only neighbouring shots: singles in between do not reset it). A shot with `"cross_line": true` crosses
  on purpose and draws the line anew.
- *Screen direction*: a character travelling more than a tenth of the frame in consecutive shots keeps going the
  same way.
- *Eyeline*: in a shot / reverse-shot pair (two singles of characters last seen together), each looks (pupils) towards
  where the other stood.
- *Shot size* per shot from its largest character: ELS, LS, FS (whole figure under 15%, under a third, more), then by
  how much of the figure from the head down is in frame: MLS (72%), MS (half), MCU (a third), CU (18%), ECU.
The `continuity` test cuts dialogue-demo into six shots (two-shot, two singles with the camera at 2.5x, two-shot,
two walks): no issues and the singles sized MS against the two-shots' FS; then sides swapped against the establishing
shot, an eyeline turned away and a walk reversed are each found by their rule and shots, and the marked cross passes.

## Act it out (plan 3.5)
http://127.0.0.1:8770/actout (linked from Studio): **Use camera** and **Record 5 s** (a 3-2-1 count, then five seconds
from the webcam or phone camera), or pick a video file; choose a character and a clip name, then **Make clip**. The
character plays the new clip in step with the take, and the report says what was captured, what was left out and why.
The same thing as a command (CLI, HTTP, MCP):

    python -m dbe actout.clip '{"video": "take.mp4", "puppet": "cast/generated/ravi.puppet.json", "name": "thumbs_up", "duration": 5}'

What happens (`dbe/actout.py`):
- **Detect.** ffmpeg decodes the take at 30 fps (phone rotation applied, `mirror` flips a selfie first); MediaPipe
  Pose gives 33 body points with visibility and depth, and Face Landmarker, run on a crop around the head, gives 52
  blendshapes. Keypoints are cached in `out/actout/` by file content and options, so re-targeting the same take onto
  another character skips detection.
- **Retarget** onto the character's own rest pose, in image space (the arm on the left of the picture drives the
  `_L` part, drawn on the left of the artboard). Each bone's world rotation is the take's segment angle minus the
  same bone's angle in the drawing (pivot to child pivot); the track is that minus the parent's, as `puppet.js`
  composes angles. The spine comes from hips to shoulders, or from the shoulder line in a waist-up take; the head
  rolls with the eye and ear lines. Segments pointing at the lens (too short on screen) are bridged, and parts seen
  in less than 60% of the take are left out (`dropped` in the report), so idle or other clips fill them.
- **Arms** (`arms`): `angles` (default) copies joint angles, which keeps natural silhouettes on a flat character
  whose forearm cannot foreshorten toward the lens; `reach` places the hands where the take's hands are relative to
  the shoulders, scaled to this body, with the elbow on the take's side: claps and hands on the body meet, but a
  short-armed character wings its elbows out for a hand held near the chest.
- **Root** (`root`): `move` turns hip travel into the clip's offset; when both legs are seen, ankle height and speed
  give foot `contacts` and the vertical offset is solved so planted soles sit on the ground line (forward kinematics
  through the clip's own legs), with the take's jump carried between contacts. A waist-up take never moves the root
  vertically. `in_place` drops travel.
- **Face** (`face`): `upper` (default) makes eye (open, half, closed), brow (raised, worried, angry) and gaze keys;
  `all` adds the mouth (wide, mid, small, O, smile, frown), which overrides lip-sync while the clip plays, so it is
  for silent reactions. Only drawings the character has are used (with fallbacks), and short flickers are held.
- **Layer order**: when the take's wrist is clearly nearer the lens than the shoulders, a forearm and hand drawn
  behind the body come in front (clip `swaps.z`, the existing pose `z` override; Lottie and Synfig keep their fixed
  order, as with control-driven z).
- **Keys** are reduced against the curve `Acting.evaluate` actually plays (smoothstep between keys), seeded with the
  clear turning points and split where the played curve strays most, to `tolerance` degrees (default 1.5).
- **Save**: the clip goes into the character's `clips` (puppet format v0.7, version raised to 0.7 if older) through
  `puppet.save`, with a `source` note. Any shot plays it by name; `film.validate` accepts a character's own clips.
  `out/actout/<name>_sheet.png` shows six moments of the take above the character.

Warnings in the report: the performer's size on screen changing by more than 25% (a zoom or a moving camera reads
as travel: use `in_place`), and a face found in under 80% of the take. Takes, keypoints and sheets stay in `out/`
(git-ignored). MediaPipe (`requirements-tools.txt`) needs libEGL (`apt install libegl1`); its two Apache-2.0 model
files are fetched once into `DBE_MODELS` and checked against pinned hashes.

Measured: a 5-second phone take (waist up, Pexels test clip) became a 184-key clip on Ravi in 17 s from upload
through the page (decode 3 s, detection 8 s, retarget under 0.1 s), legs left to idle; a full-body take with a
camera zoom was flagged. `python -m dbe test` runs the Act it out self-test (in `dbe/actout.py`): takes made by forward kinematics through a
character must come back as the clips that made them (wave, celebrate, shrug under 1.5° mean), a jump's contacts
within 0.08 s with planted soles within 5 units of the ground, a waist-up take must not guess legs, `reach` must
keep a long-armed performer's clap together (0.035 torso lengths, against 0.17 for angles), and face keys must
follow blendshapes (`upper` never touches the mouth).

## Phone-first creator flow and drawing requests (plan 3.6)
http://127.0.0.1:8770/doodle (linked from Studio; laid out for a phone): draw a character with a dark pen (a closed
loop for the head, one for the body, eyes and a mouth inside the head, stick arms), then:
1. **Snap** (`doodle.snap`): the photo is turned upright (EXIF), cropped to the ink and scaled to about 900 px
   (`out/doodle/<id>/`). `dbe/autorig.py` closes small gaps in the line and reads it: the two largest stacked closed
   loops are the head and body (one loop: a blob, all head, resting on the ground); marks well inside the head that
   are not joined to its outline are the eyes (upper) and the mouth (the lowest wide one); strokes leaving the body's
   sides at its height are arms, with the pivot where they meet it; a second, lower side stroke is a tail; marks above
   the body (ears, hair, a hat) ride with the head; legs and feet stay on the body. Every guess is reported with a
   reason, and notes say what it could not find.
2. **Check the cuts**: each piece is tinted over the photo; drag a dot to move a pivot (or the mouth centre), tap a
   piece to leave it on the body; `doodle.cut` rebuilds.
3. **See it move and talk** (`doodle.say`): one line in a clean Kokoro voice, run as its own process
   (`engine/say_line.py`), with lip-sync cues from the model's phoneme timings; the acting is idle, a wave on a
   greeting, a hop on an exclamation, head and body beats while talking, blinks. Hop, Wave, Tilt, Shake (and Wag with
   a tail) play on tap.
4. **Keep it** (`doodle.keep`): `cast/drawn/<name>.puppet.json`, registered with owner rights and its voice.

The puppet is built by `dbe/ink.py` in the artist's own line. Eyes blink by squashing the drawn eyes. The mouth gets
talking shapes (closed, small, mid, wide, O, FV, smile) drawn in the doodle's ink and line weight: the drawn mouth
is `closed`; with none drawn, all are made; a drawn mouth joined to another line stays drawn and the dark open shapes
cover it (reported, so the person checks the mouth box). Measured on a synthetic cat doodle through the page at phone
size: cut in 3 s, talking 11 s after the photo was picked.

**Drawing requests** (feature map E20): `drawing.requests` lists every drawing a character is missing, for one
film's directions (`film`, from `script.rigcheck`) or for all its costly moves (`puppet.abilities`), as requests in
`<puppet>.requests.json` with the reason and a ghost guide (`out/requests/`): the character faintly at rest on its own
artboard, the related drawing it has a little stronger, and a dashed box where the new drawing goes. On the page,
**Draw it** opens the guide to draw over with a finger; a drawing on paper photographed at the same framing works too.
`drawing.fulfil` lifts the ink inside the box (`ink.extract`), stores it as the swap shape (a new swap if needed, e.g.
brows) or part (a tail, pivoted where the stroke is nearest the body), saves the character, and closes the request
only when the rig check no longer lists it, reporting the moves that became free; with `render` it re-renders the
film that asked. Since WP-18, pupils and a turned view are drawn over a ghost too (below); chains and missing clips
are still listed for the Rig Canvas.
Drawn shapes are raster strokes (SVG renderer). `python -m dbe test` cuts three synthetic doodles (head and body,
blob, cat with a tail and ears; pivots within 11 px), snaps the cat, builds its queue, draws raised brows into the box
and checks happy and surprised become free, and voices a line when Kokoro is installed.

**A page of doodles, pupils and a turned view (WP-18).** `doodle.page` takes a photo of a page with several
doodles: the ink is grouped by closing gaps of about 2.5% of the page and filling loops (eyes stay with their head),
groups under 8% of the ink are specks, and each group is cropped with the others painted out in the paper colour
and goes through `doodle.snap`, in reading order (`names` gives each its name). The phone page always calls it and
shows a chip per doodle when there are several. Two more requests are drawn over ghosts:
- **pupils**: the box is the eyes, shown stronger; the dots drawn there become the `pupils` swap. Ink of the eyes
  within a few pixels of them is painted out of the open eyes (a drawn dot would otherwise stay), and `movable` is
  0.6 of the room the eye leaves around the pupil. `look` then moves them in every renderer.
- **three-quarter view**: the box is the head; the person draws the head turned to the right without a face. It
  becomes `views.three_quarter.parts.head`, and the face swaps (eyes, pupils, mouth, brows) get shapes in that view
  slid toward the side it faces and narrowed with the head (the mapping is kept in `meta.face_map`, so pupils drawn
  later follow it). A timeline turns the character with `view: [[t, "three_quarter"], ...]`, and the rig check
  counts the view as the turn ability.
The `doodle` test splits a synthetic page of a person and a cat into two puppets (the cat with its tail), draws dots
in the cat's eyes and a turned head on their ghosts, checks both requests close and free "glance / look at" and
"turn (three-quarter)", renders looks left and right (pupils 20.7 px apart, `movable` 10.2) and the turned view (the
head 28 px to the right, nothing below the head changed), and runs the phone page in Chromium
(`tools/doodle_page_check.mjs`): two chips, the second picked with its tail, pupils and three-quarter requests listed.
The arm finder no longer drops short arms: a side stroke counts from six square line widths, not 0.15% of the
drawing's box. Writing and objects in the photo are told apart from drawings (WP-18): a group of several separate marks of a
similar height in one short, wide line is writing (a sum such as 2 + 3 = 5, a name), and solid ink (most of it
deeper than 3 px, not line work) that reaches the photo's edge is a hand or a pen. Both are left out with the reason
(`left_out`), and the phone page says so. Test `pagesort`: a page with two doodles, a written sum and a hand holding a
pen from the corner gives the two doodles, the sum as writing and the hand and pen as not a drawing; the same two
doodles alone still give two.

**Mirror tool** (WP-18). `puppet.mirror {puppet, part, to, axis, replace, out}` copies a part drawn on one side, and
everything hanging from it, to the other side across the body's centre line (by default the middle of the parent's
drawing). Raster drawings are flipped and moved across, vector paths reflected, pivots reflected, and joint limits
[lo, hi] become [-hi, -lo]. Names swap sides (`arm_L` -> `arm_R`, `forearm_R` -> `forearm_L`), and an existing
part is only redrawn with `replace`. Test `mirror`: Nib's left arm (raster) mirrored to the right, and Ravi's right
arm chain (upper arm, forearm, hand; vector) mirrored to the left. With the arms posed at +-angles, each puppet's
arms draw as mirror images of each other (symmetry IoU 1.0 and 0.998), and both lint clean.

**Editing a cut's outline** (WP-18). On the phone page each suggested cut shows its polygon's vertices as small
squares: drag one to move it, double-tap one to remove it (a cut keeps three), double-tap the outline to add a vertex on
its nearest edge. OK then cuts again from the edited outlines (`doodle.cut`). In the `doodle` test, on the second
doodle of the synthetic page, a vertex of the tail's cut is removed (19 -> 18), one added on the longest edge (-> 19),
and the vertex farthest from the pivot dragged 70% of the way to it: it lands where it was let go (0 px off), the saved
spec holds the edited outline, and the re-cut tail's drawing changes. Two page bugs found on the way: the drag's pointer
capture sent the double-tap to the overlay, not the vertex (now found by position), and a native drag cancelled the
pointer after the first move (now prevented).

**Chains over ghosts** (WP-18). A character without a chain gets a drawing request for one ("a chain of parts
(tail)", once left to the Rig Canvas): its ghost shows the tail it has, with room to draw it longer. The tail drawn
over the ghost is lifted and split along its length: the ink's distance from where it meets the body (measured along
the stroke) is cut into four equal bands, each a raster part pivoting where the band before it ends, overlapping by 4
px so bent joints show no gaps; the chain replaces the old tail part (its first link keeps the name, so clips that
move `tail` still do), waves gently (`chains.tail.wave`) and its joints are limited to +-40 degrees. Ghost guides are
now drawn flush with the artboard: `tools/pose_still.mjs` kept the browser's 8 px page margin, so a drawing traced
over a ghost landed 8 px off (`"flush": true` in a pose_still spec; the golden pose frames keep the margin). In the
`doodle` test a wavy tail is drawn over the second doodle's ghost: the request closes and frees "tail / chain"; the
four links pivot along the stroke, the chain at rest covers all of the drawn ink (100%), and bent 28 degrees at each
joint either way the tail stays one piece (no gaps) while about 1,270 px of the picture change.

**Layer sets, gradient and texture fills** (WP-18, puppet format v0.13). `layer_sets` names several swap picks that go
together (a costume, a season): a pose's `layer_set`, or a timeline's held `layer_set` keys, pick them all, and a pick
the pose makes itself wins. `gradients` (linear or radial, in rest units, stops by colour or palette slot) paint a
stroke's fill through its `gradient`; `textures` (a tile laid over the fill, multiplied by default) through its
`texture`. Test `dressup` on `tests/poses/dressup.puppet.json` (Pip with a hat and a scarf, two sets, three gradients
and a hatch): a set and a timeline keying it draw pixel-identically (0 px differ), as do the set and its picks spelled
out, and an own pick over a set; `dbe/geom.py` resolves sets the same way. Gradients against the SVG loader: Lottie
46.1 dB PSNR (29.5 with the flat fill), Synfig 38.9 dB (29.1 flat); Grease Pencil draws the flat fill and textures are
SVG-only, which `render.parity` reports as drawn without. Golden pose case `dressup`.

**Tap to cut (WP-18, plan 1.8b).** When a cut is wrong or missing, `doodle.click` takes taps on the photo
(`[x, y]` inside the piece, `[x, y, 0]` outside) and cuts that piece with SAM 2.1 tiny (Apache-2.0; onnx-community's
ONNX export, two graphs with external weights, pinned by sha256 in `dbe/assists.py` and downloaded on first use):
the picture is encoded once (about 4 s on 4 CPUs; cached in `out/doodle/<id>/sam.npz`) and each tap then takes
0.3 to 0.5 s. The mask takes the ink around it and is outlined, grown by the line width. For a limb the head and
body loops are taken off it (their insides as autorig finds them, out to their lines), and a new limb is pivoted by
following the stroke's own direction from its end nearest the body to the body's line; a head pivots at the bottom
of its mask. The page's **✂ Tap to cut** button and piece menu do this; `doodle.cut` records SAM 2.1 in the
puppet's `meta.assists` when a cut came from it. Measured on the synthetic cat, each limb left out and cut again
with one tap on its stroke: left arm IoU 0.83 with the automatic cut and pivot 10.4 px from where it was drawn
(automatic: 10.5), right arm 0.79 and 7.5 px (8.5), tail 0.97 and 5.4 px (3.2). On the phone page, the left arm
of the second doodle on a page, removed and tapped back, returns with the model 65% sure.

**Krita .kra import (WP-18).** `puppet.import` reads `.kra` files directly (`dbe/drawing_import.py`): the layer
tree from `maindoc.xml` (groups give swap sets, hidden layers count as for ORA), and each paint layer's tiles
(version 2: 64-px tiles, LZF-compressed planar BGRA, or raw), cropped to the drawing. 8-bit RGBA is tested; 16-bit
layers are converted down, and other colour spaces or layer kinds (vector, file, fill, filter layers) are reported
in `skipped` with what to do in Krita. The `kra` test reads `tests/fixtures/kra/tiny.kra` (saved by Krita 5.2.2
from `tiny.ora`: groups, a hidden swap shape, a hidden sketch layer) and finds every layer identical to the ORA's,
pixel for pixel; with Krita installed (`tools/setup.sh oss`, run under `xvfb-run`), Pip exported as ORA and saved
by Krita as `.kra` imports identically from both (18 parts).

## Production orchestrator and board (plan 3.7)
http://127.0.0.1:8770/board (linked from Studio): a posting calendar by week, and a card per film with its state,
where it stands against its posting date, the checkpoints (research, first shot, final, approved, merged) with the
orchestrator's verdicts, the final's measurements (length, loudness, true peak, QA checks passed, layout advisories,
the director's verdict), escalations, narrowings and the owner's buttons: Approve, Merge, Stop, Relaunch, Narrow, and
Proceed / Narrow / Stop on an escalation. The page reads `prod.status` every 4 s.

    python -m dbe prod.plan '{"film": "kit-demo", "post_on": "2026-11-10"}'          # runner: pipeline | claude | manual
    python -m dbe prod.launch '{"max_parallel": 3}'                                    # every planned film

Each film gets a git worktree next to the repository (`<repo>-films/<film>`, branch `film/<film>`) and a session:
- **pipeline**: `tools/film_agent.py` rebuilds an existing film through every gate: research gate, voice (when the
  workspace has none), the first shot, the full render with QA (one round of `film.heal` if QA fails), a builder
  entry in the ledger, a commit on the branch. This is how every film is re-made after an engine change.
- **claude**: Claude Code headless (`claude -p --output-format json --max-budget-usd N`, command in the registry's
  `runners.claude`) with the protocol and `docs/director-prompt.md`, allowed to run `python -m dbe`, commit, read
  and edit, and search and fetch the web for research, for new films from a brief (`prod.plan` with `brief` writes it
  into the workspace). Each session stops at its budget (`budget_usd` on the film, else the board's, default 25).
  When it ends, what it spent (dollars, minutes, turns, tokens) is read from its JSON result into the film's
  `costs`; the board shows each film's spend and the total (WP-03).
- **manual**: nothing is started; the protocol is written to `.production/PRODUCTION.md` in the workspace for any
  agent to follow. `prod.session_prompt` (the board's "Copy session prompt") gives the protocol and the director
  prompt ready to paste into a Claude Code session, here or in the cloud, working in that workspace.

Owner notifications (WP-03): an escalation, a final ready for approval, a failed session, a final that still fails
after the session's repairs, and a session stopped by its budget each notify the owner: a line in
`productions/notifications.jsonl` (the board shows the latest), and a POST of the same JSON to every webhook in
`productions/notify.json` (`{"webhooks": [{"url": ..., "events": ["escalated", "waiting_owner", ...]}]}`,
machine-local) that asks for that kind. A webhook that fails is recorded and never stops production.

The protocol is three checkpoint calls, `prod.checkpoint {film, stage, report}`, which a session in its workspace
sends to the shared registry (`DBE_PRODUCTION`, set by the launcher). The orchestrator never takes the report's word:
it measures for itself in the film's workspace. Research runs `research.check` there and reads the ledger; a
counter-evidence entry that contradicts or blocks (or contradictions the session lists) **escalates**: the film
stops until the owner decides with `prod.decide`. Proceed carries on as briefed; narrow appends the owner's change of
scope to the film's brief and delivers it with the next answer; stop ends the film. The first shot must exist at the
film's frame size, and a still goes to the board. The final reads `qa.json` and the director's ledger verdict, then
copies the render, QA report and a poster for the board; it is not ready while the film's own director (its latest
`director` ledger entry) asks for "one more pass" (WP-03). The answer carries the verdict (ok, ready, fail, blocked,
escalate), the reasons, the owner's pending instructions and `continue`: a stopped or escalated film's session ends.

Owner controls: `prod.stop` (the session's process group), `prod.narrow`, `prod.relaunch` (renders in the workspace
are reused), `prod.approve` (only a final that passed QA), `prod.merge`. Merge needs approval and refuses a branch
that changes anything outside `films/<film>/` (new characters may go in `cast/drawn/`); it merges `--no-ff` and puts
the approved render next to the film data. `prod.status` also starts queued films as running ones finish (at most
`max_parallel` sessions), and marks a film failed when its session ends without a final checkpoint, or
`needs_work` when its final still fails QA after the session's own repair round.

Schedule: each milestone is due a number of days before posting (`lead_days`: research 10, first shot 6, final 3,
approval 1); a film is on_track, due_soon (within a day), late, or needs_owner while escalated.

The registry (`productions/registry.json`, git-ignored, with session logs and render copies for the board) is
written under a file lock, because sessions report concurrently. `python -m dbe test` runs `production.self_test`
on a throwaway clone of the working tree with a manual session. It covers launch into a worktree, research ok, an
escalation from a counter-evidence entry, narrowing, a first shot at the wrong size, a failing then passing final,
approval refused before a pass, a merge refused for a stray edit outside the film, a clean merge, and the schedule
states.

Measured (a scratch clone of the repository, 4 CPU cores, `max_parallel` 3, a simulated owner acting through the
same commands as the board): ten films (nib-hello, kit-demo, fx-demo, props-demo, heal-demo, clips-demo, data-demo,
direct-demo, review-demo, dialogue-demo) posting between 9 and 27 November went from planned to merged in 19.5
minutes, never more than three sessions at once. Every final passed QA 7 of 7 at -14.0 LUFS. The run also covered:
fx-demo's seeded session crash, which was caught as "ended before the final checkpoint" and relaunched; kit-demo,
stopped by the owner after its first shot and relaunched, which reused its renders; and data-demo, whose
counter-evidence escalated it at research, was narrowed by the owner, and merged with the narrowing in its brief.
Each merge touched only its own film's folder. The run found two bugs, both fixed: the merge did not check that the
session had committed, and a hand-written ledger entry without metrics broke the ledger writer. A merge now refuses
while the session runs or while the film's work is uncommitted. The claude runner is wired, but no Claude Code
session was run in this test.

## Content planner (plan 3.8)
http://127.0.0.1:8770/plan (linked from Studio): the quarter's calendar by week, every spread rule with its verdict,
the idea bank's counts, and each row's field, sweep, role, start-by date, fact-lock date and status and live stage,
with **Brief** and **Brief + board** buttons, for the channel picked at the top. Files, per channel (in git: the
studio's plan): `plan/channels/<id>/channel.json`, `ideas.json`, `<quarter>.json`; `plan/channels.json` names the
default channel.

0. **Channels** (WP-32): the studio can run several series side by side, each with its own audience, fields, locale,
   rules, brand kit, cast and voices. Every `plan.*` command takes `channel` (default: the default channel);
   `plan.channels` lists them with their brand colour, cast, series and quarters; `plan.channel` with a new id starts
   one from the defaults. A channel's films inherit its brand kit (`shots.json` `"brand": "<id>"` reads
   `brand/<id>.json`; `true` stays the house kit), its cast (template roles to characters) and its voices, through
   `plan.brief`. `plan.cross` lines every channel's quarter up week by week and flags two channels posting the same
   subject in one week. The board colours each film by its channel and filters by channel. `science` is the live
   channel; `brand/sample-kids.json` and the test channel in `planner.KIDS_SAMPLE` are samples for a second series.

1. **Channel** (`plan.channel`): audience, topic fields, the locale for local stories, brand kit, cast and voices, and the rules: posting days, the
   weekly series (day, name, format), at most one post per field per week, days between posts in a field, local
   stories per week, an analysis every N weeks, the tolerance for dated hooks, and lead and fact-lock days per sweep.
2. **Sweeps** (`plan.sweep_prompt`): six research prompts for agents with web search: dated hooks (anniversaries,
   international days, sky events, launches in the quarter, dates checked on official pages), recent developments
   (with `fresh_until`), evergreen myths and questions (the series), tools, original analyses (data with its terms and
   a published figure to check against) and local stories. Each asks for real sources the agent opened and nothing
   invented, with research leads and cautions.
3. **Idea bank** (`plan.ideas_add`, `plan.ideas`): ideas are briefs in waiting: a draft hook, angle, why now,
   starting-point sources, research leads, cautions, field, sweep, format and score. Each is validated. Near-duplicates
   are refused. Every cited URL is fetched: a source that does not exist (404, or a host that does not resolve) is
   dropped, an idea left with none is refused, and the rest record "ok" or "blocked" (a site that refuses robots).
4. **Schedule** (`plan.schedule`): dated hooks on their day (capped so each week keeps room for its series episode
   and local story), the series slot (a hook on the series day moves the episode to another free day that week; a
   hook blocking the series day's field is set aside when that is the only way to place the episode), the local quota,
   the analysis cadence (any week of its span), a repair pass (a week short of its local story or series episode, or a
   span short of its analysis, takes the slot of one of its dated hooks, never the one on the series day), then the
   open slots. Measured on made-up banks for two channels: 47 of 48 quarters pass every rule (the scheduler before
   WP-32 passed 29 of 48 for the science channel alone); a miss is a bank short of fitting ideas, and the check says
   which week. An open slot goes to
   a field with no post yet, then the least-used field, then the higher score; recent stories must still be fresh and
   every idea must be startable by its lead time. Each row gets `start_by` and a `fact_lock` date: the day the film's
   facts must be cleared by the fact gate (`ledger.add role=fact_gate verdict=cleared`).
5. **Check** (`plan.check`): every rule, computed independently of the scheduler, so a hand-edited calendar is checked
   the same way: slots filled, posts per week, topic diversity, field gap, local quota, analysis cadence, series
   cadence, timeliness (dated hooks on the day, recent stories while fresh), lead times, a fact-lock date on every row,
   an empty field getting the next open slot, no repeats, distinct topics (no two films on one subject in a quarter:
   titles sharing two or more words and most of the shorter title, or title, angle and hook sharing most of their
   words, with accents folded and plurals stripped), sources on every idea.
6. **Brief, storyboard and launch** (WP-06, feature map E24): `plan.brief` writes the row's brief and drafts its
   storyboard with `film.from_template` from the format the row names (`myth_vs_data`, `explainer`, `dialogue`),
   in the idea's own words: the hook, the angle's first two sentences, a short citation of the first source. Every
   fact starts unsourced (the research gate holds the film) and `script.json` carries `"draft"`, which `voice.build`
   refuses until the session has rewritten the lines after research. With `launch` it is one command from calendar
   to session: the film goes onto the board with its plan row (quarter, start-by, fact-lock date, role, review
   level), its brief and draft storyboard are committed on its branch in its workspace (nothing is left in the main
   checkout, so the merge meets no untracked copies), and its session starts (or queues behind `max_parallel`).
   The board shows each card's plan row. `plan.track` reads the films
   and the production registry and shows each row's stage (planned, briefed, in production, final ready, approved,
   merged, posted), its fact-lock status from the film's ledger, and what is overdue. `plan.posted` records the link.

Measured, for Q1 2027, planned on 2 November 2026: six research agents ran the six sweeps in parallel, taking 7 to 18
minutes each, and returned 100 ideas: 20 dated hooks, 16 recent stories, 22 evergreen ideas (18 myths), 12 tools,
12 analyses and 18 local stories. All passed validation and the duplicate check, and every source URL resolved.
93 sources loaded; 3 refused automated requests and are recorded as "blocked". The agents reported what they dropped
or demoted to research leads: pages they could not open, dates they could not confirm, and datasets whose licence
did not allow reuse. The scheduler filled all 52 posting days (Mon, Wed, Fri, Sat). Each field got 8 to 10 posts;
there were 14 dated hooks, 13 series episodes, 7 analyses, and at least one local story in every week. All 14 rules
pass. Adding the topic rule caught four duplicate subjects across sweeps: perihelion, the reservoir cascades, the two
monsoons, and Sri Lanka's kidney disease. A fifth, El Niño, was found once accents were folded. The rule errs on the
side of caution: it also pairs two monsoon-wind ideas that are different films. Many ideas carry a Sri Lanka angle,
so 35 of the 52 posts are local; the quota is a minimum, and the channel's rules can change that balance.
`python -m dbe test` runs `planner.self_test` on a synthetic bank: the scheduler's quarter passes every rule, and five
calendars broken on purpose are caught by the right rule.


## Setting up a machine (WP-02)
    bash tools/setup.sh            # everything; idempotent (about 2 minutes fresh, 11 s when nothing is missing)
    python -m dbe engine.doctor    # what is there, what is missing, and the exact fix for each gap

`engine.doctor` checks three groups. **core** (needed for the engine, Studio, SVG renders and `python -m dbe test`)
covers Python 3.11+, `requirements-core.txt` (numpy, Pillow, jsonschema, scipy), ffmpeg, ffprobe, git, Node,
Playwright, that headless Chromium actually starts, and free disk. **audio** covers `requirements-audio.txt` and the
Kokoro model files, checked against pinned sha256 hashes, plus the timed model and the Piper voices installed.
**tools** covers `requirements-tools.txt` (psd-tools, MediaPipe), libEGL, the MediaPipe models (hashed), Synfig,
Blender and melt. `ok` means every required check passed; the self-test fails if one does not. With `deep: false` it
skips the browser start and the hashing (about 1 s instead of 5).

`tools/setup.sh [all|system|python|models|node]` applies the fixes: apt packages (ffmpeg, git, libEGL); Python
requirements, with the pinned large wheels first fetched over plain HTTP by `tools/fetch_wheels.py` (pip stalled on
large wheels behind this environment's proxy), choosing the wheel by the interpreter's own compatibility tags so an
ARM or macOS build is never picked; the Kokoro files (verified by hash), the timed model and the MediaPipe models;
and Playwright only if `require('playwright')` fails. For a cloud environment, put `bash tools/setup.sh` in its setup
script. Models live in `DBE_VOICES` (default `~/voices`) and `DBE_MODELS` (default `~/.cache/doodleberry/models`),
wheels in `DBE_WHEELS`; none of them go in git.

## Keeping the docs true (WP-01)
`python -m dbe docs.check` (also in `python -m dbe test`) checks that the build plan, the feature map, the work
packages and the command registry agree:
- every command named in backticks in the docs is registered;
- every feature-map row marked ⬜ or 🟡 names its work package (WP-nn) or says "not planned";
- every WP-nn mentioned exists in `docs/work-packages.md`;
- every item in the build plan's phase tables has a status row or a work package covering it;
- every work package is in the at-a-glance table and the order of work.

The feature map was reconciled against the code on 2 November 2026. 238 open rows were reviewed: built rows now
name the command or plan item that built them, partial rows say what is left and where, and every open row points
at its work package. The map went from about 90 rows marked built to 162 built, 53 partial and 72 open (P2 and
emergent rows included).

## Expert review and honest labels (WP-05)
Health, legal and finance films get an expert reviewer. The channel's rules (`plan.channel`, `rules.expert_review`:
fields such as "life & health" and keywords such as disease, drug, dose, treatment, law, invest) decide which calendar
rows are marked `review: expert`; `plan.brief` writes the review row and an "Expert review" section into the brief.
`research.check` then requires `omits` on every fact and reports `expert_review: pending` until a reviewer records
`ledger.add role=expert_review verdict=cleared`; the final checkpoint carries the status to the board, and
`prod.approve` refuses the film until it is cleared. `plan.check` gained a rule, `expert_review_marked`. In Q1 2027 the
ten health posts are marked.

Facts labelled "re-analysis", "illustration" or "preliminary" show that label on screen while a line citing them plays
(a tag at the top of the text-safe area, drawn with the captions by `film.render`). No existing film has labelled
facts, so no golden frame changed.

## Licence ledger and vendored code (WP-33)
Doodleberry is in-house R&D, so any licence may be used; the ledger records which, so a public post can be judged.
- `licence.ledger` lists every component with its licence class: manifest files and tools, vendored code, voices and
  cast puppets. Classes: public-domain, permissive, attribution, weak-copyleft, copyleft, network-copyleft,
  share-alike, source-available, non-commercial, research-only, proprietary (the owner's own work).
- `film.provenance` lists what shaped a film (characters, voices, the third-party files its renderers and captions
  use, and models recorded in the film's `provenance.json`) and flags what restricts a public post: voices not marked
  clean, and non-commercial, research-only, share-alike or source-available inputs. `film.package` carries the flags
  and `clear_to_post`.
- Vendored code has an `UPSTREAM.json` next to it (repository, version, archive and sha256, licence and class,
  licence files, what was taken, patches, a build recipe and the binary it makes). `vendor.check` (in
  `python -m dbe test`) checks every record, its licence files and its manifest row; no class is refused.
  `vendor.build NAME` builds a component in a copy, into `out/vendor-build/NAME/` (git-ignored).
- Vendored so far: lottie-web, three.js and perfect-freehand (JavaScript, as before), and the sources of Potrace 1.16
  (GPL-2.0-or-later, monochrome tracing) and VTracer 0.6.4 (MIT or Apache-2.0, colour tracing), unmodified, for
  WP-18's scan-to-vector work. **Not built yet:** building runs the upstreams' own configure, make and cargo
  scripts, which this environment's safety check refused to run without the owner's permission.
