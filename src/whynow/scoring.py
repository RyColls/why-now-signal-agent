"""Turn stored signals into a ranked list. No AI in this file.

A signal is a dict with: account_id, type, source_url, published (ISO date),
found (ISO date), sentence, verified (bool). Signals missing any piece of
evidence are dropped, because a claim with no source does not count.

Each signal type counts once per account, using its freshest valid signal, so
five news stories about one expansion score the same as one.

Usage:
    python -m whynow.scoring --as-of 2026-11-11
"""

from __future__ import annotations

import argparse
import json
import tomllib
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_FIELDS = ("source_url", "published", "found", "sentence")
NO_SIGNAL = "no reason to call yet"
NOT_A_FIT = "not a fit"
JOB_POST_TYPES = {"hiring_maintenance", "pain_in_job_post"}


def decay_factor(published: date, as_of: date, decay: dict) -> float:
    age = (as_of - published).days
    if age < 0 or age > decay["zero_after_days"]:
        return 0.0  # a future date is a data error, not a fresh signal
    return 0.5 if age > decay["half_after_days"] else 1.0


def has_evidence(signal: dict) -> bool:
    if any(not str(signal.get(f) or "").strip() for f in EVIDENCE_FIELDS):
        return False
    try:
        date.fromisoformat(signal["published"])
    except ValueError:
        return False
    return str(signal["source_url"]).startswith(("http://", "https://"))


def score_account(signals: list[dict], as_of: date, config: dict) -> dict:
    """Score one account. Returns the total and the signals that counted."""
    weights, counted = config["weights"], {}
    for signal in signals:
        if signal.get("type") not in weights or not has_evidence(signal):
            continue
        if config["rules"]["require_verified"] and not signal.get("verified"):
            continue
        # An expired post means the role was probably filled, so it is not a live reason to call.
        if (config["rules"].get("require_open_job_posts") and signal["type"] in JOB_POST_TYPES
                and signal.get("still_current") is False):
            continue
        published = date.fromisoformat(signal["published"])
        points = weights[signal["type"]] * decay_factor(published, as_of, config["decay"])
        best = counted.get(signal["type"])
        if points > 0 and (best is None or points > best["points"]):
            counted[signal["type"]] = {
                **signal, "points": points, "age_days": (as_of - published).days,
            }
    total = sum(s["points"] for s in counted.values())
    return {
        "score": total,
        "status": "call" if total > 0 else NO_SIGNAL,
        "signals": sorted(counted.values(), key=lambda s: -s["points"]),
    }


def rank(universe: pd.DataFrame, signals: list[dict], as_of: date, config: dict,
         fits: dict[str, str] | None = None) -> list[dict]:
    """Rank accounts. `fits` maps account_id to fit / not_fit / unclear from the fit check.

    not_fit accounts are removed from the call list whatever their signals say.
    unclear accounts stay, and are labelled so a rep sees the risk.
    """
    fits = fits or {}
    by_account: dict[str, list[dict]] = {}
    for signal in signals:
        by_account.setdefault(signal.get("account_id", ""), []).append(signal)
    rows = []
    for account in universe.to_dict("records"):
        result = score_account(by_account.get(account["account_id"], []), as_of, config)
        verdict = fits.get(account["account_id"], "unchecked")
        if verdict == "not_fit":
            result = {**result, "score": 0, "status": NOT_A_FIT, "signals": []}
        rows.append({
            "fit": verdict,
            "account_id": account["account_id"],
            "company_name": account["company_name"],
            "industry": account["industry"],
            **result,
        })
    # Ties break on the freshest signal, then on name so the order is stable.
    rows.sort(key=lambda r: (
        -r["score"],
        min((s["age_days"] for s in r["signals"]), default=10**6),
        r["company_name"].lower(),
    ))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def load_signals(folder: Path) -> list[dict]:
    signals = []
    for path in sorted(folder.glob("*.json")):
        signals.extend(json.loads(path.read_text())["signals"])
    return signals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--universe", type=Path, default=ROOT / "data/universe/universe.csv")
    parser.add_argument("--signals", type=Path, default=ROOT / "data/signals")
    parser.add_argument("--config", type=Path, default=ROOT / "config/scoring.toml")
    parser.add_argument("--fits", type=Path, default=ROOT / "data/research/fits.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/ranked.json")
    args = parser.parse_args()

    config = tomllib.loads(args.config.read_text())
    fits = json.loads(args.fits.read_text()) if args.fits and args.fits.exists() else {}
    ranked = rank(pd.read_csv(args.universe), load_signals(args.signals), args.as_of, config, fits)
    args.out.write_text(json.dumps({"as_of": args.as_of.isoformat(), "accounts": ranked}, indent=2) + "\n")
    with_signal = sum(r["score"] > 0 for r in ranked)
    print(f"{len(ranked)} accounts ranked as of {args.as_of}; {with_signal} have a current signal")


if __name__ == "__main__":
    main()
