# Ledger — "The Fly That Came Back" (full) and the hook cut

## Decisions
- **Topic.** Chosen from the five US-interest titles; became urgent on research: first US case June 3, 2026 (Zavala County, TX), 71 cases by Oct 30 including dogs and a cat, first Arizona case Oct 28.
- **Two cuts, one library.** `screwworm-shared/art.js` (rigs, backdrops), `film.js` (shot painters, sequencer, captions, cues), `map.js` (generated). Each film's `scene.js` is only a shot list keyed to script lines (optionally to a word inside a line).
- **Facts.** 29 facts with source sentences. Wording choices made to stay inside the sources:
  - "America wiped it out in 1966" follows USDA ARS; Wikipedia notes the 1982 official elimination and the 2016 Keys outbreak (the latter is in the film).
  - Sanibel: ARS says the test "confirmed the theory"; NAL says the team wanted a more conclusive site. The script says "backed the idea ... they wanted proof" and does not claim it failed.
  - Curaçao: weekly airplane releases (ARS); ~70% of egg masses sterile after 3 weeks (ARS); fertile eggs gone within about two months (NAL).
  - Edinburg plant: "100 million at first, 300 million by 2028" without "per week", because the DTN text gives stage totals without the unit.
- **Map.** Natural Earth (public domain) via world-atlas/us-atlas, projected by `tools/mapgen.py`. Infestation regions are schematic. Case dots are illustrative positions inside the affected regions (Zavala County and Cochise County are placed where they are); the "70 mi" pin sits at Sabinas Hidalgo; the "31 mi" pin location is illustrative (the source gives only Coahuila).
- **People.** Knipling and Bushland are generic cartoon scientists identified by name tags; no likeness attempted.
- **Voice.** Piper en_US-ryan-high, length scale 1.06 (full) / 1.04 (hook). Name phonemes checked (Curaçao, Darién, Knipling, Zavala).

## Rounds
| round | change | measured |
|-------|--------|----------|
| 0 (stills) | contact sheet of every shot | map cropped the West Coast → widened to −125.5°; cow and calf heads overlapped → spread apart; swarm flies too small to read → 2.2× |
| 1 (hook render) | first hook render | 41.3 s; −14.0 LUFS; one 0.5 s near-still on the factory; Whisper min word "Full" weak in the voice itself |
| 1b | CTA re-voiced as "Watch the full story…"; factory gets a slow push and flies; end chime moved after the last word (it masked "Watch"); poison stamp softened in the hook | hook Whisper mean 0.889 → 0.934, min 0.01 → 0.28 |
| 2 (full render) | first full render | audio passed (−14.0 LUFS, speech-to-background 16.1 LU) but 38 near-still holds of 0.5–1.9 s on maps, cards and islands |
| 2b | every shot drifts (slow push + sway, per shot); Sanibel chime moved off "backed" | both cuts: no stills > 0.5 s, −14.0 LUFS, −1.4 dBTP, all lines traced; full: Whisper 542 words, mean 0.940; render 1131 s for 6085 frames |

## Known nits
- Some weak Whisper words (e.g. "fly", "weakness") are weak in the dry voice too: Piper delivery, not the mix.
- Wipes are 0.32 s; at 2 fps sampling the sheet shows them as hard cuts.
