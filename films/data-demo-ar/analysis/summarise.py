"""Summarise the club's telescope log (cache/log.csv) into ../data.json: monthly nights, total, best month."""
import csv
import json
from pathlib import Path

rows = [(r["month"], int(r["nights"])) for r in csv.DictReader(open(Path(__file__).with_name("cache") / "log.csv"))]
best = max(rows, key=lambda r: r[1])
out = Path(__file__).resolve().parent.parent / "data.json"
old = json.loads(out.read_text()) if out.exists() else {}
old.update({"monthly": [[m, n] for m, n in rows], "total": sum(n for _, n in rows), "best": {"month": best[0], "nights": best[1]},
            "months": len(rows)})
out.write_text(json.dumps(old, indent=1))
