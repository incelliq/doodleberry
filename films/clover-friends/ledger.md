# Ledger — "Clover Friends"

Run unattended; gates logged here.

## Decisions
- **References.** Two reels of this genre studied for devices only. From the second: character comedy setup → time-skip card → visible consequence → explanation; several distinct voices; lip-sync; eyelid acting; a blurred foreground layer; weather and wet ground as the "result"; with-vs-without comparison. Nothing copied: original cast, script, layout and music.
- **Cast.** Mina (kid farmer: braids, headband, overalls, rain boots), Wiggs (earthworm with glasses and a bow tie, the explainer), Kernel (hungry corn seedling, the "without" crop), Clover (sprout), a silent tall corn (the "with" crop), rhizobia (silent), narrator (time card).
- **◆ Voices.** Five speakers from four Piper voices, each re-voiced with WORLD: Mina amy + child preset, Kernel ryan pitched up, Wiggs alan (British) pitched up with wide intonation, Clover lessac + baby preset, narrator ryan pitched down. Chosen by measurement, not by ear.
- **Lip-sync.** `voice.py` writes a per-speaker mouth-openness track (one value per frame) from each line's loudness; faces open by it, so only the speaker's mouth moves.
- **Story beats.** Mina sows clover grudgingly; hungry Kernel; Wiggs wakes and pops out; nitrogen in the air bounces off Kernel; Wiggs dives, the camera follows underground; nodules, bacteria, the nodule window and the chemistry; Clover says "Yum!"; MONTHS LATER card; autumn rain, the clover dies, nitrogen released, puddles; spring, Mina plants corn on both sides; the clover-side corn shoots up, Kernel stays small and envious; "the clover fed the soil"; end card "CLOVER first. Then corn."
- **Facts.** Same facts.json as `films/clover`; conversational lines with no claim are marked `fact: null` and the QA accepts them; every claim line cites a fact.

## Rounds
| round | change | measured |
|-------|--------|----------|
| 0 (stills) | first assembly: Mina stood too close to the clover and loomed through the underground and nodule-window shots | — |
| 1 (full render) | Mina moved left (x −40) and underground cameras moved right; rain and calendar-flip effects added to the audio engine; score timed so a beat lands on Wiggs popping out | 48.6 s, 1457 frames, render 315 s; −14.0 LUFS, −1.4 dBTP; speech-to-background 15.5 LU; Whisper on the mix hears 103/103 words, mean confidence 0.971; LRA 1.8 LU; all claims traced |
