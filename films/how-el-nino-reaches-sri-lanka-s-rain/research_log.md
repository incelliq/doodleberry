# Research log: How El Niño reaches Sri Lanka's rain

Accessed 2026-11-03. Review level: standard. Planned for 2027-01-27 (idea I097, analysis slot).

## Searches
- NOAA CPC ENSO Diagnostic Discussion (current issue, 8 October 2026) for the present state of El Niño.
- NOAA CPC index files: ONI (oni.ascii.txt) and relative ONI (RONI.ascii.txt), which CPC's discussion now uses.
- CHIRPS v2 rainfall over Sri Lanka: IRI Data Library (area average; the server streamed about 50 months in two
  minutes, too slow) and ClimateSERV (NASA/USAID SERVIR) area-average API, used: daily values 1981-01-01 to
  2026-09-30, 16,709 days, none missing.
- De Silva & Hornberger (2019, HESS 23, 1905-1929), from the brief: page read for context (Maha and Yala seasons,
  ENSO and IOD as predictors); its ENSO season-by-season result was not quoted, so it is not cited for a number.

## Sources
- **cpc_ensodisc**: "ENSO Alert System Status: El Niño Advisory"; "reaching +2.1°C in Niño-3.4" (September 2026).
  Verdict: primary for the current state (F01). ONI ASO 2026 +2.46 and RONI ASO 2026 +1.97 agree in sign and size.
- **chirps** via ClimateSERV: box 79.5-82.0 E, 5.9-9.9 N (land cells; CHIRPS has no values over the sea).
  Cross-check: January 1981 sums to 84.4 mm against 82.5 mm from the IRI Data Library's monthly CHIRPS for the
  same box (2.4 percent; the two services take the box edges slightly differently). Verdict: usable for seasons.
- **roni**: episodes by CPC's rule (five overlapping seasons at +0.5 or more, or -0.5 or less), applied to the
  October-December season of each year: 13 El Niño, 13 neutral, 19 La Niña years in 1981-2025.
- **analysis** (analysis/summarise.py, analysis.md, data.json): every number in the film.

## Rejected
- "So this one means a wet end of the year?" and "It leans that way": a forecast for a season that has ended by
  the posting date (fact gate, round 1); now general and in the past tense.
- "Warm water far away, rain right here": claims a direct effect; now "a nudge to the rain".
- The draft's framing "compare El Niño years with other years": the other years include 19 La Niña years, which
  push the other way, so the contrast with them overstates El Niño's effect. In January-March especially, "41 percent
  drier than other years" is mostly La Niña years being wet (426 mm against 248 mm in neutral years). The film
  compares with neutral years instead, and says January-March shows no clear pattern.
- "About 15 percent more rain" (mean against all other years): replaced by the count against neutral years (10 of
  13), which is what the analysis supports most plainly; the mean difference against neutral years (+12 percent) has
  a permutation p of 0.14, so no percentage is narrated.
- IRI Data Library series: too slow to download (timed out twice); used only to cross-check January 1981.

## Open questions
- The Indian Ocean Dipole often goes with El Niño (several of these Octobers to Decembers had a positive IOD); the
  film does not separate the two and says nothing about the mechanism.
- A box over Sri Lanka mixes the wet south-west and the dry zone; a basin-level split (Mahaweli, Kelani) is a
  follow-up.
- The film posts on 27 January 2027: lines are worded for that date (the hook says "in late 2026" and the label dates
  the relative Niño-3.4 figure to September; the question is about El Niño years in general, not this season). At fact lock
  (21 January) re-read the January 2027 CPC discussion and the October-December relative Niño-3.4 values: re-gate if
  the advisory has ended or the values fell clearly below about 2; if they are about 2.5 or more, say "more than two
  degrees" (October 2026 came in at +2.47 relative, fact gate round 3); cite the newer issue in F01 either way.

## Counter-evidence
- Three of the 13 El Niño years (1986, 1987, 1991) had October-December rain at or below the neutral median: said
  in the film ("in three El Niño years it didn't").
- Against neutral years the mean differences are not statistically clear (October-December p 0.14,
  January-March p 0.24, one-sided permutation tests, 20,000 shuffles): the film speaks of a lean and gives counts, not
  a forecast, and sends viewers to the Department of Meteorology.
- The index matters for January-March (fact gate, round 1): by RONI the January-March after El Niño is below the
  neutral median in only 7 of 13 years (p 0.24), but by the traditional ONI (which adds 2014 and 2019 to El Niño and
  moves 2016, 2024 and 2025 from La Niña to neutral) it is 12 of 15 (199 against 301 mm, p 0.028), as De Silva &
  Hornberger also describe. The film now says "drier on average, but less reliably", true under both, and shows
  "depends on the El Niño index" on screen. October-December holds under both (10 of 13; 12 of 15).
- Rounded to one decimal, as CPC's tables print it, RONI makes 2014 an El Niño year too (11 of 14 for
  October-December, 8 of 14 for January-March): the counts are sensitive to borderline years; the film's count uses
  the unrounded index as published in RONI.ascii.txt.
