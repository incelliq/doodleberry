# Research log: Closest to the Sun in January

Accessed 2026-11-02. Review level: standard.

## Searches
- USNO seasons and apsides API for 2027 (perihelion, aphelion, solstices, equinoxes).
- NASA / NOAA pages on what causes the seasons (Space Place, NWS Sioux Falls, NASA Earth facts, NSSDC fact sheet).
- JPL approximate positions page (obliquity only; no apsis distances).
- Sri Lanka climate: Department of Meteorology (meteo.gov.lk), World Bank CCKP, Britannica, Met Office, IWMI, Wikipedia.

## Sources
- **usno** (aa.usno.navy.mil/api/seasons?year=2027): perihelion 2027-01-03 02:33 UT; aphelion 2027-07-05 05:06 UT;
  December solstice 2027-12-22 02:42 UT. Verdict: primary for dates.
- **nssdc** (NASA Earth Fact Sheet): perihelion 147.095, aphelion 152.100 (10^6 km), obliquity 23.44°. Verdict: primary for distances.
- **spaceplace** (NASA Space Place): tilt causes seasons; perihelion 91.4 M mi, aphelion 94.5 M mi; perihelion in January.
  Verdict: independent second source for distances and the cause; agrees with NSSDC after conversion (147.1 / 152.1 M km).
- **nws** (NWS Sioux Falls): seasons "have nothing to do with how far the Earth is from the Sun"; tilt average 23.5°,
  varies 22–24.5°. Verdict: independent agency source for the cause.
- **nasa_earth** (NASA Science Earth facts): tilt 23.4°, "This tilt causes our yearly cycle of seasons." Verdict: good.
- **wiki_geo_lk** (Wikipedia, Geography of Sri Lanka, oldid 1381059109): latitude 5–10° N; monsoon seasons; January
  coolest, May hottest. Verdict: usable but tertiary; second source sought (see Open questions).
- F04 (≈5 million km) is arithmetic on NSSDC: 152.100 − 147.095 = 5.005; Space Place's 3.1 M mi ≈ 5.0 M km agrees.

## Rejected
- The brief's draft hook "In January, Earth is at its farthest point from the Sun": contradicted by USNO, NSSDC, NASA
  Space Place and NWS (January is perihelion, the closest point). Escalated at the research checkpoint.
- timeanddate.com (proxy refused), scijinks.gov (403), World Bank CCKP (403), Britannica (403), Met Office travel
  page (404), meteo.gov.lk (connection reset twice): not read, not cited.
- The "3 %" figure: not found in a source that loaded; not used. (The "7 % more sunlight" figure was later found on
  NASA StarChild by the counter-evidence search and is used as F10.)
- Colombo normals: the country page climatestotravel.com/climate/sri-lanka does not carry them; the Colombo page does.

## Open questions
- Sri Lanka monsoon months: now from the Department of Meteorology presentation (2010); meteo.gov.lk itself was not
  reachable (connection reset). Wikipedia's edges differ (NE Dec–Mar, SW mid-May–Oct).
- "January is cold" is partly true locally: Wikipedia says January is Sri Lanka's coolest month. The film must not
  call the January dip false; its point is that the cause is not distance.
- Sri Lanka time for perihelion (08:03) is derived from UT + 5:30.

## Counter-evidence
A fresh counter-evidence agent (2026-11-02) reported:
1. **Contradicts the brief:** the draft hook says Earth is farthest from the Sun in January; USNO gives perihelion 3 Jan
   and aphelion 5 Jul 2027. Response: the myth line becomes the real common belief (seasons come from distance),
   shown as MYTH; the data line says we are closest in January. Escalated to the owner.
2. Perihelion 02:33 UT / 08:03 Sri Lanka checks out. Keep (say "about 8 a.m." if spoken).
3. Distance has a small real effect: about 7 % more sunlight in January (NASA StarChild; (152.100/147.095)^2 = 1.069).
   Response: new fact F10; the film must not say distance does nothing, only that tilt matters far more.
4. "Set by monsoons instead" overstates it for temperature: Sri Lanka's small temperature swing still follows the
   Sun's yearly path (tilt). Response: monsoons set the rain; temperature moves only about 2 °C.
5. Colombo coolest month 27.4 °C (January), warmest 29.2 °C (May), 1991–2020 (climatestotravel, secondary);
   WorldClim 1970–2000 names December coolest. Response: F09 says "about 2 degrees"; no warmest month on screen.
6. Monsoon ranges differ: Department of Meteorology (Dayananda 2010, JMA/WMO workshop) SW May–Sep, NE Dec–Feb,
   inter-monsoons Mar–Apr and Oct–Nov. Response: F08 now cites DoM; Wikipedia secondary.
7. Wikipedia's "January is the coolest month" copies the c.1988 Library of Congress country study. Response: not
   used as the primary source for F09.
8. DoM latitude 05°55'N–09°51'N. Response: F07 says "about 6 to 10 degrees north"; no "on the equator".
Still open: a live meteo.gov.lk page (connection reset) and a peer-reviewed source for the coolest month
(Punyawardena 2020, Springer, behind a login).
