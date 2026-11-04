"""Fetch CHIRPS v2 daily rainfall averaged over a box around Sri Lanka (79.5-82.0 E, 5.9-9.9 N; land cells only:
CHIRPS has no values over the sea) from ClimateSERV (NASA/USAID SERVIR), year by year, into ../cache/chirps_lk_daily.json.
Not run by film.data (it is a job API, not a plain download): run it by hand to refresh, then film.data.
    python analysis/tools/fetch_chirps.py [first_year last_year [part_file]]
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://climateserv.servirglobal.net/api/"
BOX = {"type": "Polygon", "coordinates": [[[79.5, 5.9], [82.0, 5.9], [82.0, 9.9], [79.5, 9.9], [79.5, 5.9]]]}
y0, y1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1981, 2026)
out = Path(__file__).resolve().parent.parent / "cache" / (sys.argv[3] if len(sys.argv) > 3 else "chirps_lk_daily.json")   # a part file, to fetch in parallel; merge after
have = json.loads(out.read_text()) if out.exists() else {"query": {"api": API, "datatype": 0, "operationtype": 5, "geometry": BOX}, "days": {}}


def get(path, **q):
    with urllib.request.urlopen(API + path + "/?" + urllib.parse.urlencode(q), timeout=120) as r:
        return json.loads(r.read())


for y in range(y0, y1 + 1):
    end = f"12/31/{y}" if y < 2026 else "09/30/2026"
    jid = get("submitDataRequest", datatype=0, begintime=f"01/01/{y}", endtime=end, intervaltype=0, operationtype=5, geometry=json.dumps(BOX))[0]
    for _ in range(200):
        if float(get("getDataRequestProgress", id=jid)[0]) >= 100:
            break
        time.sleep(2)
    rows = get("getDataFromRequest", id=jid)["data"]
    for r in rows:
        have["days"][f"{r['year']:04d}-{r['month']:02d}-{r['day']:02d}"] = r["value"]["avg"]
    print(y, len(rows), flush=True)
    out.write_text(json.dumps(have, sort_keys=True))
