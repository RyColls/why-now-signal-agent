"""Build docs/index.html from the run's data files.

The page is one static file with the data inlined, so it works on GitHub Pages
with no server. Run: python site/build.py
"""

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rank = json.loads((ROOT / "data/ranked.json").read_text())
uni = {r["account_id"]: r for r in __import__("csv").DictReader(open(ROOT / "data/universe/universe.csv"))}
adj = {r["id"]: r for r in json.loads((ROOT / "data/research/adjudication.json").read_text())["results"]}
cands = json.loads((ROOT / "data/research/candidate_signals.json").read_text())
verified = {(s["account_id"], s["source_url"], s["type"]): s
            for s in json.loads((ROOT / "data/signals/research-2026-11-11.json").read_text())["signals"]}
cfg = __import__("tomllib").loads((ROOT / "config/scoring.toml").read_text())

fit_info = {}
for f in glob.glob(str(ROOT / "data/research/output/b*.json")):
    for a in json.loads(Path(f).read_text())["accounts"]:
        fit_info[a["account_id"]] = a["fit"]

# Briefs are parsed from the markdown so the page and the file never disagree.
briefs = {}
text = (ROOT / "data/briefs/briefs-2026-11-11.md").read_text()
for block in text.split("\n## ")[1:]:
    m = re.search(r"\((A\d{3})\)", block.split("\n")[0])
    if not m:
        continue
    fields = {}
    for key, val in re.findall(r"- \*\*(Likely pain|Opening angle|Contact|Caveat):\*\* (.*?)(?=\n- \*\*|\n---|\Z)", block, re.S):
        fields[key] = " ".join(val.split())
    briefs[m.group(1)] = fields

cand_by = {}
for c in cands:
    a = adj[c["id"]]
    why = None
    if not a["counts"]:
        why = a["reason"]
    else:
        v = verified.get((c["account_id"], c["source_url"], c["type"]))
        if v and v.get("still_current") is False:
            why = "The job post had closed, so the role was probably filled."
    cand_by.setdefault(c["account_id"], []).append(
        {"type": c["type"], "published": c["published"], "url": c["source_url"],
         "counts": a["counts"], "closed": bool(why and a["counts"]), "why": why})

accounts = []
for r in rank["accounts"]:
    u = uni[r["account_id"]]
    fi = fit_info.get(r["account_id"], {})
    sigs = []
    for s in r["signals"]:
        sigs.append({
            "type": s["type"], "published": s["published"], "age": s["age_days"], "url": s["source_url"],
            "sentence": s["sentence"], "summary": s["summary"], "role": s["role_to_contact"],
            "factor": s["points"] / cfg["weights"][s["type"]],
        })
    accounts.append({
        "rank": r["rank"], "id": r["account_id"], "name": r["company_name"], "industry": r["industry"],
        "city": u["hq_guess_city"], "state": u["hq_guess_state"], "emp": int(u["employees_reported"]),
        "plants": int(u["plant_count"]), "fit": r["fit"], "status": r["status"], "score": r["score"],
        "fitReason": fi.get("reason", ""), "parent": fi.get("parent_company"),
        "signals": sigs, "cands": cand_by.get(r["account_id"], []), "brief": briefs.get(r["account_id"]),
    })

data = {
    "runDate": rank["as_of"], "weights": cfg["weights"], "decay": cfg["decay"], "accounts": accounts,
}
html = (ROOT / "site/template.html").read_text().replace("/*DATA*/", "const DATA = " + json.dumps(data) + ";")
(ROOT / "docs/index.html").write_text(html)
print("wrote docs/index.html", len(html) // 1024, "KB;", len(accounts), "accounts")
