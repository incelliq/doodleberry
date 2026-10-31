# Ledger — screwworm 3D short

## Decisions
- **Assets.** The Quaternius animal packs could not be downloaded (Google Drive quota), so the story centres on a person: the
  "what happens if" second-person format suits it. UBC Standard bodies wear minimal black clothing, so the setting is a lakeshore.
- **Taste.** Clinical, not gory: a stylised wound decal, cream maggots, an x-ray view instead of flesh.
- **Facts.** Human cases from PubMed-indexed sources (BMJ news, Feb 2025; a returned traveller from Costa Rica, Travel Med Infect Dis 2025)
  and CDC myiasis guidance (a healthcare provider removes the larvae; cover open wounds; not common in the US). The first US human
  case (Aug 2025) is cited through Wikipedia's reference to The Guardian/Reuters.
- **Case pins** on the map are illustrative positions inside the affected states (as in the 2D film).

## Rounds
| round | change |
|-------|--------|
| 0 (stills) | metals rendered black (no environment) → RoomEnvironment PMREM; x-ray skin invisible → opacity 0.42 + emissive; wound was a flat red disc → ragged painted decal; map case pins too big; plane out of frame → camera tracks the plane; hair/eye normal maps referenced under `_png.png` names → copies added |
| 1 (full render) | first full render | −14.0 LUFS, −1.5 dBTP, all lines traced; 10 near-still holds (x-ray, map, doctor); bandage filled the frame; release boxes fell out of shot |
| 1b | every shot drifts (slow push + orbit around the subject); bandage 3.2×4.2 cm and the doctor camera pulled back; boxes keep the plane's forward speed and stay on screen | all checks pass: 54.8 s, no stills > 0.5 s, −14.0 LUFS, −1.5 dBTP, speech-to-background 17.2 LU, Whisper mean 0.962; render 1609 s for 1644 frames (4 workers, software WebGL) |

## Known nits
- The fly is tiny in the opening wide shot (true to scale); it reads once the camera pushes in.
- UBC Standard has no clothes, so the setting has to justify swimwear; the Source tier or CC0 outfits would widen settings.
