# Results of the 2026-11-11 run

Sample: 60 of the 200 universe accounts, chosen at random with a fixed seed.
The rest were not researched, to limit cost. These are proof-of-concept
figures on a small sample, with a failure list.

## What came out

| Measure | Result |
|---|---|
| Accounts researched | 60 |
| Fit check: fit / unclear / not a fit | 14 / 29 / 17 |
| Candidate signals found by the research workers | 20 |
| Signals the reviewer confirmed under strict rules | 10 of 20 (50%) |
| Signals counted after the final review | 16 of 20 (80%) |
| Of those 16, still current when scored | 8 of 16 (6 job posts were closed) |
| Accounts with a current verified signal | 6 of 60 |

The strict figure is the reviewer's own pass. The final figure includes seven
signals I reinstated because the reviewer objected only to a plant location
differing from the OSHA record while the company was the same, and four I
rejected despite the reviewer's pass or doubt. Every decision and its reason is
in `data/research/adjudication.json`. The 80% is therefore partly a judgment
call, and 50% is the figure that needs no judgment.

## Cost

About 2.3 million Haiku 5.5 tokens, including a first attempt that was cut
short by a usage limit, plus 287 web searches. At list prices that is roughly
$4 to $5 in total, or about $0.07 per researched account. This is an estimate
from token counts, not a bill: the run used a plan's included limits. It
excludes the orchestrating model's own tokens.

## Failure examples

1. **Right company, wrong place.** Seven candidate signals came from a
   different plant than the one in OSHA's record (Danone, Shearer's, American
   Packaging, CEMCO). The reviewer flagged them as wrong company. Fix: treat
   the account as the company and resolve its parent first, so a signal at any
   of its plants counts and is labelled as such.
2. **Not an announcement.** One "expansion" was a state building-project
   registration, and one investment was at the parent group rather than the
   account. In the earlier hand pilot, a news story about Mason Technologies
   was nearly credited to Mason Industries. Fix: require the source to be about
   the account's own legal entity and to be a company or press statement.
3. **Stale job posts.** Six of the seven hiring or job-post signals pointed to
   postings that had already closed. A closed post means the role was probably
   filled. Fix: scoring now ignores closed postings, and the research step
   should check posting status.

## Weaknesses to state plainly

- **The universe leaks.** 17 of 60 (28%) were parts of much larger groups and
  29 could not be classified. OSHA data cannot see ownership, so the fit check
  does the real work.
- **Few current signals.** Six of 60 is 10%. Job-post coverage is thin without
  a jobs database, so recall is probably low. It was not measured.
- **Quotes passed through a page summarizer.** The fetch tool returns
  summaries, so a sentence can differ slightly from the page. The reviewer
  re-checked each, but a human should spot-check.
- **Not done:** the hand-labelled fit sample, the 20-account recall check and
  the blind ranking test all need a person. They are open in the README.
