# Ref 3 — rice field, apple snail, duck (57 s)

Uploader "PhD in Produce"; 1080×1920, 30 fps, AV1 video, AAC stereo 44.1 kHz.
Studied 2026-10-31 with: 1 fps contact sheet, multi-threshold scene detection, per-frame
motion, phase-correlation camera tracking, per-act colour clustering, EBU R128 loudness,
Whisper transcription with word times, per-word pitch/timbre clustering for speaker turns,
spectral-flux onset detection, and full-resolution frame study.

## Structure (shot by shot)
| time | what happens | device |
|------|--------------|--------|
| 0.0–2.8 | a rice clump's half-closed eyes at the water line snap open in shock; no words yet | wordless visual hook; first line only at 2.8 s |
| 2.8–12.2 | an apple snail arrives underwater and taunts; the rice glares and argues | villain vs victim banter; eye acting carries it |
| 12.8–24.3 | the snail climbs the stem and chews; a bite wound appears and stays; the rice's eyes go bloodshot | persistent damage; escalating panic |
| 24.7–32.8 | the snail lays a pink egg clutch above the water and gloats ("accomplished"); the rice cries, tears pool on the water surface | low point; physical gag with the medium |
| 33.4–40.1 | standoff, the snail mocks | holding beat before the turn |
| 40.0–41.0 | yellow shock marks pop at the left frame edge, then a duck in a backwards cap steps in, cropped and huge | off-screen anticipation → entrance; costume prop as personality |
| 41.9–47.4 | the duck plunges its head underwater, grabs the snail (bug-eyed in its beak), the empty shell drops out with a smear | pose-to-pose snaps at 45.87 s and 47.33 s; motion-blur smear on the falling shell |
| 48.13 | hard cut | the only camera cut in the film |
| 48.2–56.1 | a human explainer on a field bund (raised path) with the duck in the paddy explains the practice | real-world payoff in a brighter location |
| 56.2–57.1 | ~0.9 s still end frame | |

Story share: ~84 % character comedy, ~16 % explanation. The explanation arrives only after the
audience has watched the problem and the solution happen.

## Picture
- **Waterline split composition.** The water surface crosses the frame about a third of the way down. Everything that crosses it is drawn twice: crisp above, tinted grey-green and lower-contrast below, as if seen through murky water. The rice's eyes sit on the line, so each eye is half clear, half underwater. The surface is a thin pale line. Underwater: murky gradient with soft dark silhouettes of submerged plants; out-of-focus grass in the near foreground at the bottom edge.
- **Locked-off camera for 47 s.** Phase correlation finds no pan or zoom until the cut at 48 s. Life comes from character acting (median frame motion 0.41, ~4× ref 2) and entrances/exits. Only 32 % of frames are nearly still; the longest hold is 0.93 s, at the very end.
- **Eye acting does the heavy lifting:** half-lidded sleep, V-brow glare, wide shock with tiny pupils and red veins (bloodshot), tears. The rice has no visible mouth until it shouts; then the mouth appears below the water line, tinted.
- **Persistent state:** an old jagged stem stub (earlier damage) sits in frame from the start; the new bite wound stays; the egg clutch stays to the end. The world remembers.
- **Physical gags that use the medium:** tears pool as puddles on the water surface under the eyes; the snail puffs a little breath cloud; bubbles.
- **Pose-to-pose snaps** for comedy beats (limited animation) instead of in-betweened moves; a directional smear on a fast-falling object.
- **Off-screen entrance:** shock marks appear at the frame edge a beat before the duck arrives; the duck enters cropped, big in frame.
- **Costume prop:** the duck's backwards cap makes it a character without extra animation.
- **Palette:** muted and desaturated in the story world (mean saturation 0.31, value 0.57; grey-green water 37 % of the frame, rice greens #6c9c3f / #5d835d / #3a5f2a). The explainer location is brighter (value 0.65) with sky-blue water (#d8eaf4, #86acbd) — the palette change signals "back in the real world".
- **Captions:** single words, yellow fill with a heavy black outline, no plate, placed in the lower middle over the water; key words enlarged ("DARE", "ACCOMPLISHED").

## Sound
- −14.1 LUFS integrated, LRA 4.7 LU, sample peak 0.0 dBFS (mastered hot; we keep ≤ −1 dBTP).
- Dialogue covers 80 % of the runtime at 211 wpm while speaking (169 overall): dense and fast.
- At least three voices: two higher character voices trading lines (pitch clusters ≈240 Hz and ≈340 Hz) and a lower ≈150 Hz voice that carries the explainer.
- The music/sfx bed sits only ~2 dB below the speech level between lines — wall-to-wall energy, not a ducked bed.
- ~81 sharp onsets (1.4 per second): nearly every action gets a sound.

## What the engine has vs needs (after this study)
| device | engine today | gap |
|--------|--------------|-----|
| multi-voice dialogue, lip-sync, eyelid moods | yes (`voice.py`, `cast.js`) | add a bloodshot/tiny-pupil shock eye and tears |
| waterline split (two media) | no | `D.waterline`: clip the world above/below a surface, tint + blur + slight refraction below, surface line |
| locked-off, acting-driven staging | possible (camera holds) | idle loops and reaction "takes" per character so a static shot stays alive |
| pose-to-pose snaps + smears | no | pose keys with hold/snap interpolation; directional smear for fast objects |
| persistent damage / decals | ad hoc | a per-character state list (bites, eggs, stains) that persists once set |
| off-screen entrance anticipation | shock marks exist | an "entrance" helper: edge marks, a beat, cropped entrance |
| villain / victim / hero structure; story-first, explanation last | used partly in clover-friends | template the act split (~80/20) |
| one-word yellow-outlined captions | phrases on a plate | a caption style option: single word, no plate, emphasis scaling |
| dense, loud bed (LRA ~4.7, bed ~2 dB under speech) | heavy ducking, LRA ~1.8 | a "bed" mix profile with lighter ducking and less compression |
| real-world explainer in a brighter location after a hard cut | not yet | an adult explainer rig and a palette shift on the cut |
| new rigs for this genre | kid, worm, banana | snail, duck, rice clump (original designs) |
