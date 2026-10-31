# Ref 4 — "This New Farming Machine Kills Weeds With Lasers Without Hurting Crops"

Same channel as refs 1–3. 72.4 s, 1080×1920, 30 fps (AV1), stereo AAC 44.1 kHz; about 1.4M views when studied (2026-10-31).
Notes and measurements only: no frames, script or audio kept in the repo.

## Structure: a two-act format (skit, then explainer)
| time | act | what happens (paraphrased) | device |
|------|-----|----------------------------|--------|
| 0–1 s | hook | two oversized weeds flank a small onion; red arrows point at the weeds | an annotation tells you where to look before anyone speaks |
| 1–17 s | conflict | the onion complains; the weeds mock it and hog the nutrients | villain/victim banter, alternating voices |
| 17–29 s | setup | the onion threatens them with the weeding machine; the weeds brag that herbicides can't touch them; the onion puts on sunglasses ("technology got smarter") | the props escalate (sunglasses = confidence); the weeds' brag plants the payoff |
| 29–30 s | entrance | a red machine bar slides down from the top of the frame | off-screen entrance; the machine's scale is implied and never shown whole |
| 30.4–33.3 s | **machine POV** | top-down HUD: crosshairs lock onto weeds, a red laser cone fires, the screen flashes red, weeds get a red X | point-of-view switch; the busiest motion in the film |
| 33.4–39 s | gag | back to the side view: scanning light cones; the weeds think it's a photo ("say cheese") | dramatic irony: the audience already knows what the light is |
| 39–43 s | payoff | thin red beams, white smoke puffs, wilted weeds; the onion gloats in sunglasses | persistent damage (the weeds stay wilted) |
| 44–72 s | explainer | static two-shot: a kid in a blue sweater asks how it spares the crop; a scientist in a straw hat explains cameras + AI → laser heats the growing point → no regrowth → useful against herbicide-resistant weeds, less chemical use | Q&A framing; the background pans as the machine drives behind them |

The explainer's four claims are exactly the four questions the skit raised (how does it tell them apart, what does the laser do, why doesn't the weed grow back, why does that matter). The skit plants them; the scientist cashes them in.

## Measurements
| measure | value |
|---------|-------|
| integrated loudness | −14.1 LUFS |
| loudness range | 4.2 LU |
| speech | 180 words; 149 wpm overall, ≈199 wpm while speaking; speech ≈75 % of runtime |
| voices (median f0) | onion ≈180–270 Hz; weeds ≈330–460 Hz (pitched up); explainer pair ≈109–128 Hz (both low and close in pitch) |
| hard visual changes | none in the first 30 s; 15 in 30–39.5 s (POV cuts, red flashes, beams); one at 44.2 s into the explainer |
| motion by segment (mean abs frame diff, 108×192) | skit 0.15–0.34, nearly-still frames 62–86 %; laser beat 3.29 (10× the skit); explainer 0.5–0.8, nearly-still only 17–23 % (constant background pan) |
| captions | one word at a time, white with a dark outline, placed **on the speaking character's body** (the onion's bulb), not in a lower third |

## What it teaches (for our engine)
1. **Two acts:** a ~40 s character skit that raises questions, then a ~30 s human Q&A that answers them. Our films are narrator-led all the way through, so this is a different format worth having.
2. **Motion as punctuation:** a locked-off, acting-driven skit, then a ~3 s burst of 10× motion for the key event. We now drift every shot; this argues for stillness plus a burst instead, for skit-style films.
3. **Machine POV device:** a HUD overlay with lock-on crosshairs, a beam cone, a red flash, X marks and a frame vignette. It suits any precision-tech topic (lasers, drones, sterile-fly drops).
4. **Dramatic irony gag:** the characters misread the danger ("say cheese") while the audience knows. Cheap to write, strong to watch.
5. **Captions on the character:** one word at a time, placed on the speaker. Combined with ref 3's style, a caption-style option is overdue.
6. **Mix:** LRA 4.2 LU again (ours 1.1–1.5); speech-while-speaking ≈199 wpm (ours 176–191).
