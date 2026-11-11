"""Build the account universe from OSHA's public Form 300A summary data.

OSHA publishes one row per reporting establishment (a plant, warehouse or
office) with the owning company's name, EIN, NAICS code and average headcount.
This module rolls establishments up to companies, applies the ICP in
config/icp.toml, and draws a reproducible sample.

What this can and cannot know is written down in docs/universe.md. The short
version: it sees establishments that report to OSHA, grouped by the EIN and
name the employer typed in. It cannot see corporate parents, so a later stage
checks each account on the web before it is trusted as a fit.

Usage:
    python -m whynow.universe data/raw/ITA_300A_Summary_Data_2025.csv
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)

# Legal suffixes dropped when comparing names. "ACME FOODS, INC." and
# "Acme Foods LLC" should land in the same company.
_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD", "LIMITED", "CORP",
    "CORPORATION", "CO", "COMPANY", "THE", "USA", "US",
}
_JUNK_EINS = {"000000000", "111111111", "123456789", "999999999"}


def normalize_name(name: object) -> str:
    """Uppercase, strip punctuation and legal suffixes. Empty string if unusable."""
    if not isinstance(name, str):
        return ""
    text = re.sub(r"[^A-Z0-9 ]+", " ", name.upper().replace("&", " AND "))
    words = [w for w in text.split() if w not in _SUFFIXES]
    out = " ".join(words)
    # Names that are only digits or a single short token are too generic to group on.
    return out if len(out) >= 4 and not out.isdigit() else ""


def clean_ein(ein: object) -> str:
    digits = re.sub(r"\D", "", ein) if isinstance(ein, str) else ""
    return digits if len(digits) == 9 and digits not in _JUNK_EINS else ""


def industry_for(naics: str, industries: dict[str, list[str]]) -> str | None:
    """Target industry whose longest prefix matches this NAICS code, if any."""
    best, best_len = None, 0
    for industry, prefixes in industries.items():
        for prefix in prefixes:
            if naics.startswith(prefix) and len(prefix) > best_len:
                best, best_len = industry, len(prefix)
    return best


class _Groups:
    """Union-find: establishments sharing an EIN or a normalized name are one company."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, key: str) -> str:
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)


def load_establishments(csv_path: Path) -> pd.DataFrame:
    """Read the OSHA file into one clean row per private US establishment."""
    try:
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, dtype=str, low_memory=False, encoding="latin-1")
    df.columns = [c.strip().lower() for c in df.columns]

    required = {
        "establishment_name", "establishment_id", "ein", "company_name", "city",
        "state", "naics_code", "establishment_type", "annual_average_employees",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OSHA file is missing expected columns: {sorted(missing)}")

    df["employees"] = pd.to_numeric(df["annual_average_employees"], errors="coerce")
    df["naics_code"] = df["naics_code"].fillna("").str.replace(r"\D", "", regex=True)
    df["state"] = df["state"].fillna("").str.strip().str.upper()

    df = df[
        (df["establishment_type"].fillna("").str.strip() == "1")
        & df["state"].isin(US_STATES)
        & df["employees"].gt(0)
        & df["naics_code"].str.len().ge(3)
    ].copy()

    # An establishment can appear more than once when a submission was corrected.
    # The column is date_submitted in the 2025 file and created_timestamp in the
    # data dictionary and older files.
    stamp = next((c for c in ("date_submitted", "created_timestamp") if c in df.columns), None)
    if stamp:
        df = df.assign(_ts=pd.to_datetime(df[stamp], errors="coerce")).sort_values("_ts")
    df = df.drop_duplicates("establishment_id", keep="last")

    df["ein_clean"] = df["ein"].map(clean_ein)
    # company_name is optional on the form; fall back to the establishment name.
    df["name_norm"] = df["company_name"].map(normalize_name)
    blank = df["name_norm"] == ""
    df.loc[blank, "name_norm"] = df.loc[blank, "establishment_name"].map(normalize_name)
    df["display_name"] = df["company_name"].where(
        df["company_name"].fillna("").str.strip() != "", df["establishment_name"]
    )
    return df[(df["ein_clean"] != "") | (df["name_norm"] != "")]


def assign_companies(df: pd.DataFrame) -> pd.DataFrame:
    groups = _Groups()
    for ein, name in zip(df["ein_clean"], df["name_norm"]):
        if ein and name:
            groups.union(f"ein:{ein}", f"name:{name}")
    keys = [
        groups.find(f"ein:{ein}" if ein else f"name:{name}")
        for ein, name in zip(df["ein_clean"], df["name_norm"])
    ]
    return df.assign(company_key=keys)


def build_candidates(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Roll establishments up to companies and keep the ones that fit the ICP."""
    industries, size = config["industries"], config["size"]
    df = df.assign(
        is_plant=df["naics_code"].str[:2].isin({"31", "32", "33"}),
        industry=df["naics_code"].map(lambda n: industry_for(n, industries)),
    )

    rows = []
    for key, est in df.groupby("company_key", sort=True):
        plants = est[est["is_plant"]]
        if plants.empty:
            continue
        total = int(est["employees"].sum())
        if not size["min_employees"] <= total <= size["max_employees"]:
            continue
        if not size["min_plants"] <= len(plants) <= size["max_plants"]:
            continue
        # A contractor or distributor with one small shop is not a manufacturer.
        plant_share = plants["employees"].sum() / est["employees"].sum()
        if plant_share < size["min_plant_headcount_share"]:
            continue
        # Primary industry: where most of the plant headcount works. A company
        # whose biggest plant activity is off-target is not a fit.
        by_industry = plants.groupby(plants["industry"].fillna("_other"))["employees"].sum()
        primary = by_industry.idxmax()
        if primary == "_other":
            continue
        biggest = plants.sort_values("employees", ascending=False)
        rows.append({
            "company_key": key,
            "company_name": est["display_name"].mode().iat[0].strip(),
            "industry": primary,
            "employees_reported": total,
            "plant_count": len(plants),
            "establishment_count": len(est),
            "plant_headcount_share": round(float(plant_share), 2),
            "primary_naics": biggest["naics_code"].iat[0],
            "hq_guess_city": biggest["city"].iat[0].strip().title(),
            "hq_guess_state": biggest["state"].iat[0],
            "plant_locations": "; ".join(
                f"{c.strip().title()}, {s}" for c, s in zip(biggest["city"], biggest["state"])
            ),
        })
    return pd.DataFrame(rows)


def select_universe(candidates: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Reproducible sample, split as evenly across target industries as supply allows."""
    target, seed = config["selection"]["universe_size"], config["selection"]["seed"]
    pools = {
        name: pool.sample(frac=1, random_state=seed)
        for name, pool in candidates.groupby("industry", sort=True)
    }
    taken = {name: 0 for name in pools}
    remaining = min(target, len(candidates))
    # Deal one account at a time, round-robin, so a thin industry simply runs out
    # and the others absorb its share.
    while remaining:
        for name, pool in pools.items():
            if remaining and taken[name] < len(pool):
                taken[name] += 1
                remaining -= 1
    picked = pd.concat([pools[n].head(k) for n, k in taken.items()])
    picked = picked.sort_values(["industry", "company_name"]).reset_index(drop=True)
    picked.insert(0, "account_id", [f"A{i:03d}" for i in range(1, len(picked) + 1)])
    return picked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("osha_csv", type=Path, help="OSHA ITA 300A summary CSV")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "icp.toml")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "universe")
    args = parser.parse_args()

    config = tomllib.loads(args.config.read_text())
    establishments = assign_companies(load_establishments(args.osha_csv))
    candidates = build_candidates(establishments, config)
    universe = select_universe(candidates, config)

    args.out.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.out / "candidates.csv", index=False)
    universe.to_csv(args.out / "universe.csv", index=False)
    summary = {
        "run_date": date.today().isoformat(),
        "source_file": args.osha_csv.name,
        "source": "OSHA Injury Tracking Application, Form 300A summary data",
        "establishments_after_cleaning": int(len(establishments)),
        "companies_seen": int(establishments["company_key"].nunique()),
        "candidates_fitting_icp": int(len(candidates)),
        "candidates_by_industry": candidates["industry"].value_counts().to_dict(),
        "universe_size": int(len(universe)),
        "universe_by_industry": universe["industry"].value_counts().to_dict(),
        "seed": config["selection"]["seed"],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
