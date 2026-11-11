# "Why Now" Signal Agent

A proof of concept of a signal-based account prioritization agent. It finds
which accounts an outbound sales team should call this week, and gives each rep
the reason to call, with a source link behind every claim.

The client, Kilnworks, is a **fictional sample client** that sells maintenance
software to mid-sized US manufacturers. The prospect companies are real and
come from public sources. No meetings, pipeline or revenue are claimed
anywhere in this project.

## Design

AI reads, rules decide. A model reads public sources, extracts buying signals
and writes briefs. Plain code applies the weights and produces the rank, so a
rep can read the rules and argue with them.

## Status

Work in progress. Stage 1 is built and run; the rest is not built yet.

| Stage | What it does | Status |
|---|---|---|
| 1. Account universe | 200 candidate manufacturers from OSHA public data | Done |
| 2. Fit check | Confirm each candidate on the web (parent company, size) | Not started |
| 3. Signal detection | Find five buying signals per account, with evidence | Not started |
| 4. Verifier | Re-open each source, confirm sentence and date | Not started |
| 5. Scoring | Weights and time decay in code | Not started |
| 6. Briefs | Top 25 "why now" briefs from verified evidence only | Not started |
| 7. Board and evals | Ranked board, feedback simulator, six accuracy checks | Not started |

## Stage 1: account universe

Built from OSHA's Form 300A establishment data, which is free and needs no
account. See [docs/universe.md](docs/universe.md) for the rules, the counts
from the 2026-11-11 run, and the known gaps. The 200 drawn accounts are in
[data/universe/universe.csv](data/universe/universe.csv). They are candidates,
not confirmed fits: the data cannot see corporate parents, which stage 2
resolves.

### Run it

```bash
pip install pandas pytest
# Download "2025 Summary Data" from
# https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data
# into data/raw/, then:
PYTHONPATH=src python -m whynow.universe data/raw/ITA_300A_Summary_Data_2025_through_08-31-2026.csv
PYTHONPATH=src python -m pytest tests
```

The ideal customer profile is in [config/icp.toml](config/icp.toml).
