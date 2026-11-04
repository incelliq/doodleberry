"""El Niño and Sri Lanka's rain: CHIRPS rainfall over Sri Lanka split by NOAA's relative Oceanic Niño Index (RONI).

Inputs (cache/): chirps_lk_daily.json (CHIRPS v2 daily rain, averaged over the land in a box around Sri Lanka,
79.5-82.0 E and 5.9-9.9 N, from ClimateSERV: tools/fetch_chirps.py), RONI.ascii.txt and oni.ascii.txt (NOAA CPC).

Method:
- A season's rain is the sum of its days: October to December (OND, the northeast monsoon's first half and the
  second inter-monsoon) and the following January to March (JFM).
- An El Niño year is one whose OND season (RONI) is +0.5 or more inside a run of at least five overlapping 3-month
  seasons at +0.5 or more (NOAA CPC's episode rule, on RONI, which CPC uses for ENSO since 2025). La Niña likewise
  at -0.5 or less. The others are neutral.
- Compare El Niño years with neutral years (neither El Niño nor La Niña), since La Niña pushes the other way: mean OND
  rain and the following JFM rain by phase; how many El Niño years were above the neutral years' median ("wetter than
  a typical year with no El Niño or La Niña"); and a one-sided permutation test of the mean difference (20,000
  shuffles, seed 1). The comparison with all other years is kept in analysis.md for the record.
Writes ../data.json (numbers on screen and in the narration) and ../analysis.md (the table behind them).
"""
import json
import random
import statistics as st
from pathlib import Path

here = Path(__file__).resolve().parent
cache = here / "cache"
days = json.loads((cache / "chirps_lk_daily.json").read_text())["days"]

SEAS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def index(file):
    out = []
    for ln in (cache / file).read_text().splitlines()[1:]:
        p = ln.split()
        if len(p) >= 3 and p[0] in SEAS:
            out.append((int(p[1]), SEAS.index(p[0]), float(p[-1])))
    return out


roni = index("RONI.ascii.txt")
oni = index("oni.ascii.txt")


def episodes(series, sign):
    """{(year, season): True} for seasons inside a run of >= 5 at +0.5 (sign 1) or <= -0.5 (sign -1)"""
    hit = [sign * v >= 0.5 for _, _, v in series]
    keep = {}
    i = 0
    while i < len(series):
        if hit[i]:
            j = i
            while j < len(series) and hit[j]:
                j += 1
            if j - i >= 5:
                for k in range(i, j):
                    keep[(series[k][0], series[k][1])] = True
            i = j
        else:
            i += 1
    return keep


nino, nina = episodes(roni, 1), episodes(roni, -1)
val = {(y, s): v for y, s, v in roni}
ond_s = SEAS.index("OND")


def season_rain(y, months):
    tot, n = 0.0, 0
    for (yy, m) in months:
        for d in range(1, 32):
            k = f"{yy:04d}-{m:02d}-{d:02d}"
            if k in days:
                tot += days[k]; n += 1
    return tot, n


rows = []
for y in range(1981, 2026):
    ond, n1 = season_rain(y, [(y, 10), (y, 11), (y, 12)])
    jfm, n2 = season_rain(y + 1, [(y + 1, 1), (y + 1, 2), (y + 1, 3)])
    phase = "el_nino" if nino.get((y, ond_s)) else "la_nina" if nina.get((y, ond_s)) else "neutral"
    rows.append({"year": y, "ond_mm": round(ond, 1), "ond_days": n1, "jfm_mm": round(jfm, 1) if n2 >= 90 else None, "jfm_days": n2,
                 "roni_ond": val.get((y, ond_s)), "phase": phase})

full = [r for r in rows if r["ond_days"] == 92]
el = [r for r in full if r["phase"] == "el_nino"]
other = [r for r in full if r["phase"] != "el_nino"]
med_ond = st.median(r["ond_mm"] for r in full)
jfull = [r for r in full if r["jfm_mm"] is not None]
el_j = [r for r in jfull if r["phase"] == "el_nino"]
oth_j = [r for r in jfull if r["phase"] != "el_nino"]
med_jfm = st.median(r["jfm_mm"] for r in jfull)


def pct(a, b):
    return round(100 * (a / b - 1))


ond_mean_el, ond_mean_oth = st.mean(r["ond_mm"] for r in el), st.mean(r["ond_mm"] for r in other)
jfm_mean_el, jfm_mean_oth = st.mean(r["jfm_mm"] for r in el_j), st.mean(r["jfm_mm"] for r in oth_j)
neu = [r for r in full if r["phase"] == "neutral"]; nina_ = [r for r in full if r["phase"] == "la_nina"]
neu_j = [r for r in jfull if r["phase"] == "neutral"]; nina_j = [r for r in jfull if r["phase"] == "la_nina"]


def perm_p(a, b, sign):
    """one-sided permutation p of mean(a) - mean(b) (sign 1: a larger; -1: a smaller)"""
    obs = st.mean(a) - st.mean(b); allv = a + b; n = len(a); rng = random.Random(1); c = 0
    for _ in range(20000):
        rng.shuffle(allv); x = st.mean(allv[:n]) - st.mean(allv[n:]); c += (x >= obs) if sign > 0 else (x <= obs)
    return round(c / 20000, 3)


med_neu_ond = st.median(r["ond_mm"] for r in neu); med_neu_jfm = st.median(r["jfm_mm"] for r in neu_j)
ph = {"ond": {k: round(st.mean(r["ond_mm"] for r in g)) for k, g in (("el_nino", el), ("neutral", neu), ("la_nina", nina_))},
      "jfm": {k: round(st.mean(r["jfm_mm"] for r in g)) for k, g in (("el_nino", el_j), ("neutral", neu_j), ("la_nina", nina_j))}}
# robustness: the same split by the traditional ONI (the index the brief names), which CPC used before RONI
nino_o, nina_o = episodes(oni, 1), episodes(oni, -1)
ph_o = {r["year"]: ("el_nino" if nino_o.get((r["year"], ond_s)) else "la_nina" if nina_o.get((r["year"], ond_s)) else "neutral") for r in full}
el_o = [r for r in full if ph_o[r["year"]] == "el_nino"]; neu_o = [r for r in full if ph_o[r["year"]] == "neutral"]
mo_ond, mo_jfm = st.median(r["ond_mm"] for r in neu_o), st.median(r["jfm_mm"] for r in neu_o)
oni_split = {"n_nino": len(el_o), "n_neutral": len(neu_o), "nino_years": [r["year"] for r in el_o],
             "ond_mean": {"el_nino": round(st.mean(r["ond_mm"] for r in el_o)), "neutral": round(st.mean(r["ond_mm"] for r in neu_o))},
             "jfm_mean": {"el_nino": round(st.mean(r["jfm_mm"] for r in el_o)), "neutral": round(st.mean(r["jfm_mm"] for r in neu_o))},
             "ond_wet_n": sum(r["ond_mm"] > mo_ond for r in el_o), "jfm_dry_n": sum(r["jfm_mm"] < mo_jfm for r in el_o),
             "p_ond": perm_p([r["ond_mm"] for r in el_o], [r["ond_mm"] for r in neu_o], 1),
             "p_jfm": perm_p([r["jfm_mm"] for r in el_o], [r["jfm_mm"] for r in neu_o], -1)}
latest = roni[-1]; latest_oni = oni[-1]
data = {
    "years": f"{full[0]['year']} to {full[-1]['year']}",
    "n_years": len(full),
    "n_nino": len(el),
    "nino_years": [r["year"] for r in el],
    "ond_mean_nino": round(ond_mean_el), "ond_mean_other": round(ond_mean_oth),
    "ond_pct": pct(ond_mean_el, ond_mean_oth),
    "ond_median_pct": pct(st.median(r["ond_mm"] for r in el), st.median(r["ond_mm"] for r in other)),
    "ond_wet_n": sum(r["ond_mm"] > med_ond for r in el),
    "jfm_n_nino": len(el_j),
    "jfm_mean_nino": round(jfm_mean_el), "jfm_mean_other": round(jfm_mean_oth),
    "jfm_pct": pct(jfm_mean_el, jfm_mean_oth),
    "jfm_drier_pct": -pct(jfm_mean_el, jfm_mean_oth),
    "jfm_median_pct": pct(st.median(r["jfm_mm"] for r in el_j), st.median(r["jfm_mm"] for r in oth_j)),
    "jfm_dry_n": sum(r["jfm_mm"] < med_jfm for r in el_j),
    "n_neutral": len(neu), "n_nina": len(nina_),
    "phase_means": ph,
    "ond_vs_neutral_pct": pct(ph["ond"]["el_nino"], ph["ond"]["neutral"]),
    "jfm_vs_neutral_pct": pct(ph["jfm"]["el_nino"], ph["jfm"]["neutral"]),
    "ond_wet_vs_neutral_n": sum(r["ond_mm"] > med_neu_ond for r in el),
    "ond_dry_vs_neutral_n": sum(r["ond_mm"] <= med_neu_ond for r in el),
    "jfm_dry_vs_neutral_n": sum(r["jfm_mm"] < med_neu_jfm for r in el_j),
    "neutral_median_ond": round(med_neu_ond), "neutral_median_jfm": round(med_neu_jfm),
    "p_ond_vs_neutral": perm_p([r["ond_mm"] for r in el], [r["ond_mm"] for r in neu], 1),
    "p_jfm_vs_neutral": perm_p([r["jfm_mm"] for r in el_j], [r["jfm_mm"] for r in neu_j], -1),
    "p_ond_vs_other": perm_p([r["ond_mm"] for r in el], [r["ond_mm"] for r in other], 1),
    "p_jfm_vs_other": perm_p([r["jfm_mm"] for r in el_j], [r["jfm_mm"] for r in oth_j], -1),
    "oni_split": oni_split,
    "ond_bars": [["El Niño", ph["ond"]["el_nino"]], ["Neither", ph["ond"]["neutral"]], ["La Niña", ph["ond"]["la_nina"]]],
    "jfm_bars": [["El Niño", ph["jfm"]["el_nino"]], ["Neither", ph["jfm"]["neutral"]], ["La Niña", ph["jfm"]["la_nina"]]],
    "roni_latest": {"season": SEAS[latest[1]], "year": latest[0], "value": latest[2]},
    "oni_latest": {"season": SEAS[latest_oni[1]], "year": latest_oni[0], "value": latest_oni[2]},
    "rows": rows,
}
out = here.parent / "data.json"
old = json.loads(out.read_text()) if out.exists() else {}
old.update(data)
out.write_text(json.dumps(old, indent=1, ensure_ascii=False))
md = ["# Analysis: El Niño and Sri Lanka's rain", "", f"CHIRPS v2 over Sri Lanka (box 79.5-82.0 E, 5.9-9.9 N, land cells), {data['years']}; El Niño by RONI (OND season inside a 5-season run at +0.5 or more).", "",
      "| year | RONI OND | phase | OND mm | following JFM mm |", "|---|---|---|---|---|"]
md += [f"| {r['year']} | {r['roni_ond']} | {r['phase']} | {r['ond_mm']} | {r['jfm_mm']} |" for r in rows]
md += ["", f"- El Niño years ({len(el)}): {', '.join(str(r['year']) for r in el)}",
       f"- OND: El Niño mean {round(ond_mean_el)} mm, other years {round(ond_mean_oth)} mm ({data['ond_pct']:+d}%; medians {data['ond_median_pct']:+d}%); {data['ond_wet_n']} of {len(el)} above the all-years median ({round(med_ond)} mm)",
       f"- Following JFM: after El Niño mean {round(jfm_mean_el)} mm, other years {round(jfm_mean_oth)} mm ({data['jfm_pct']:+d}%; medians {data['jfm_median_pct']:+d}%); {data['jfm_dry_n']} of {len(el_j)} below the all-years median ({round(med_jfm)} mm)",
       f"- Against neutral years ({len(neu)}): OND mean El Niño {ph['ond']['el_nino']} / neutral {ph['ond']['neutral']} / La Niña {ph['ond']['la_nina']} mm ({data['ond_vs_neutral_pct']:+d}% El Niño vs neutral, permutation p {data['p_ond_vs_neutral']}); {data['ond_wet_vs_neutral_n']} of {len(el)} El Niño years above the neutral median ({round(med_neu_ond)} mm)",
       f"- Against neutral years: following JFM mean El Niño {ph['jfm']['el_nino']} / neutral {ph['jfm']['neutral']} / La Niña {ph['jfm']['la_nina']} mm ({data['jfm_vs_neutral_pct']:+d}%, p {data['p_jfm_vs_neutral']}); {data['jfm_dry_vs_neutral_n']} of {len(el_j)} below the neutral median ({round(med_neu_jfm)} mm): no clear pattern",
       f"- Against all other years: p {data['p_ond_vs_other']} (OND), {data['p_jfm_vs_other']} (JFM); the JFM contrast is mostly La Niña years being wet",
       f"- By the traditional ONI instead (same rule): {oni_split['n_nino']} El Niño years ({', '.join(map(str, oni_split['nino_years']))}), {oni_split['n_neutral']} neutral; OND {oni_split['ond_wet_n']} of {oni_split['n_nino']} above the neutral median (means {oni_split['ond_mean']['el_nino']} / {oni_split['ond_mean']['neutral']} mm, p {oni_split['p_ond']}); following JFM {oni_split['jfm_dry_n']} of {oni_split['n_nino']} below the neutral median (means {oni_split['jfm_mean']['el_nino']} / {oni_split['jfm_mean']['neutral']} mm, p {oni_split['p_jfm']}). January-March after El Niño is drier on average under both indices; how reliably depends on the index",
       f"- Latest RONI: {SEAS[latest[1]]} {latest[0]} {latest[2]:+.2f}; latest ONI: {SEAS[latest_oni[1]]} {latest_oni[0]} {latest_oni[2]:+.2f}"]
(here.parent / "analysis.md").write_text("\n".join(md) + "\n")
