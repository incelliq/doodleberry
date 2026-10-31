# Ledger — "Why farmers rotate clover"

Run unattended; the ◆ gates from the workflow are logged here instead of stopping.

## Decisions
- **Reference study.** A reel in this genre was studied for devices and pacing only (frame sheet + cut detection: long continuous shots with no hard cuts, a cutaway soil plane in the lower half, one-word captions centred low, narration at about −14 LUFS). Nothing from it was reused: different subject, characters, layout, script and music.
- **Subject.** Legume nitrogen fixation: an underground mechanism, so it exercises the cutaway and magnifier devices. Every line traced in `facts.json` (Wikipedia, "Nitrogen fixation").
- **◆ Voice audition.** Piper `lessac-high` vs `ryan-high`, same script. I can't listen, so I picked on intelligibility: mean faster-whisper word confidence was 0.978 vs 0.932, so lessac. Tempo set by length_scale 1.36 + 0.5 s gaps → 141.8 wpm overall (target 125–145).
- **◆ Concept.** Three signature moments: *the bounce* (a nitrogen pair shrugged off the hungry seedling), *the window* (a root bump opens into a living view where bacteria take in air nitrogen), *the hand-off* (the old clover sinks and its glow travels to the corn, which shoots up).
- **◆ Style bible.** Sky blue / leaf green / soil brown, nitrogen blue, ammonia lime, cream type plate; warm ink outline; Fredoka (OFL). Style frames = the still sheets rendered before the full pass.
- **◆ Audio.** 100 BPM, offset 0.35 s so beat 14 lands on "Clover has help"; sections: intro → main → reflect (the dying clover) → finale with a resolving F chord under the end card.

## Rounds

| round | change | measured before → after |
|-------|--------|-------------------------|
| 0 (stills) | first pass: subjects about 1/4 frame width, corn unreadable, captions would collide with roots | — |
| 0b (stills) | tighter camera on every shot, corn ×1.35, roots squashed vertically, captions moved to y 1515 on a soil-dark plate; wilt folds leaflets instead of collapsing; sky nitrogen clears when the story goes underground; title words spaced by measured glyph width | — |
| 1 (full render) | first full render + mix | true peak after AAC −0.7 dBTP ✗ → limiter ceiling −2.0 → −1.3 dBTP ✓; −14.2 LUFS; 0 frozen stretches; all lines traced |
