# Account universe: source, rules and known gaps

Run date: 2026-11-11

## Source

OSHA's Injury Tracking Application, Form 300A summary data for calendar year
2025 (file `ITA_300A_Summary_Data_2025_through_08-31-2026.csv`, 88 MB), from
<https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data>.

Employers file one row per establishment (a plant, warehouse or office) with
the company name, EIN, address, NAICS code and average headcount. It is free,
public, and needs no account. The raw file is not committed; download it into
`data/raw/` to rerun.

## Rules

All thresholds live in `config/icp.toml`.

1. Keep private-sector establishments in the 50 states and DC.
2. Group establishments into companies when they share an EIN or a
   cleaned-up company name.
3. Keep companies with 200 to 2,000 reported employees and 1 to 6
   establishments that carry a manufacturing NAICS code (31 to 33).
4. Require at least half the reported headcount to work in those plants.
5. Keep companies whose largest plant activity is food and beverage, plastics,
   metal fabrication or packaging.
6. Draw 200 with a fixed seed, split evenly across the four industries.

## Result of this run

| Step | Count |
|---|---|
| Establishments after cleaning | 365,391 |
| Companies after grouping | 112,546 |
| Candidates that pass the rules | 2,252 |
| Drawn for the universe | 200 (50 per industry) |

Candidates by industry: food and beverage 1,015, metal fabrication 717,
plastics 316, packaging 204.

## Known gaps

These 200 are candidates, not confirmed fits. The fit-check stage has to
resolve the first two gaps on the web before any account is trusted.

- **Corporate parents are invisible.** OSHA records who filed, not who owns
  them. Plants of much larger groups appear as mid-sized companies. Reading
  the 200 by eye, names such as Amcor, Tetra Pak and Sealed Air are plainly
  divisions of companies far above 2,000 employees.
- **Headcount is a floor.** Only establishments required to report are in the
  file, so a company's true headcount and plant count can be higher.
- **Name grouping can over-merge.** Two unrelated companies with the same
  generic name are joined. In this run 41 of the 200 accounts span more than
  one EIN.
- **NAICS codes are self-reported** and decide the industry label.
- **The data is for 2025.** Plants opened or closed in 2026 are not reflected.
