# "Why Now" Signal Agent

A proof of concept of a signal-based account prioritization agent. It finds
which accounts an outbound sales team should call this week, and gives each rep
the reason to call, with a source link behind every claim.

The client, Gantrywell, is a **fictional sample client** that sells maintenance
software to mid-sized US manufacturers. The prospect companies are real and
come from public sources. No meetings, pipeline or revenue are claimed
anywhere in this project.

## Design

AI reads, rules decide. A model reads public sources, extracts buying signals
and writes briefs. Plain code applies the weights and produces the rank, so a
rep can read the rules and argue with them.

## Status

Proof of concept, run on 2026-11-11 on a sample of 60 of the 200 universe
accounts. No account has a client, meetings or pipeline attached; none are
claimed. Numbers, failures and costs are in [docs/results.md](docs/results.md).
The six briefs are in [data/briefs](data/briefs/briefs-2026-11-11.md).

| Stage | What it does | Status |
|---|---|---|
| 1. Account universe | 200 candidate manufacturers from OSHA public data | Done |
| 2. Fit check | Confirm each candidate on the web (parent company, size) | Done for 60 accounts, by Haiku research workers |
| 3. Signal detection | Find five buying signals per account, with evidence | Done for 60 accounts: 20 candidates |
| 4. Verifier | Re-open each source, confirm sentence and date | Done: separate worker, then a judged final call |
| 5. Scoring | Weights and time decay in code | Done |
| 6. Briefs | "Why now" briefs from verified evidence only | 6 briefs (only 6 accounts had a current signal) |
| 7. Board and evals | Ranked board, feedback simulator, accuracy checks | Not started; three checks need a human |

## How the research was run

The research workers were Claude Haiku 5.5 instances with web search and web
fetch, run inside an interactive session, with prompts in [prompts](prompts).
A separate set of workers re-opened every source, and the final call on each
signal is recorded in `data/research/adjudication.json`. To rerun the same
stages through the API instead, copy `.env.example` to `.env` and set
`ANTHROPIC_API_KEY`; no code in this repo reads that key yet.

No signal is invented. A signal counts only with a source URL, a printed
publication date and a supporting sentence, and only after it is re-checked.

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
PYTHONPATH=src python -m whynow.scoring --as-of 2026-11-11
PYTHONPATH=src python -m pytest tests
```

Scoring rules are in [config/scoring.toml](config/scoring.toml).

The ideal customer profile is in [config/icp.toml](config/icp.toml).
