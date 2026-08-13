# Power BI companion — NYC Subway Service Quality & Transit Equity

A Power BI take on the same analysis as the Python brief in this repo, built on the
same line-level dataset. Same finding, different tool: **lines with modernized
signalling (CBTC) run measurably better, while service quality shows no detectable
relationship with the income of the neighborhoods a line serves** — so the equity
lever is capital investment history, not demographics.

## Files

| File | What it is |
|---|---|
| `nyc_subway_line_month.csv` | The import dataset: one row per line-month (peak hours), 2,466 rows. |
| `nyc_subway_dashboard.html` | A self-contained interactive version of the dashboard — open in any browser (no server, works offline). Use it as the reference for the Power BI build and as a shareable artifact. |
| `nyc_subway.pbix` | *(to add)* the Power BI Desktop file. |

## Dataset

Derived from the Python pipeline in this repo (`run_pipeline.py`), filtered to peak
hours: **2,466 rows, 21 lines, Jan 2015 – Mar 2026.**

| Column | Meaning |
|---|---|
| `Line` | Subway line (1–7, A–W, JZ, L…) |
| `Date` | Month (first of month) |
| `OnTimeRate` | Customer Journey Time Performance — share of journeys completed within 5 min of schedule |
| `AddedJourneyMin` | Average added journey time per trip (platform + train), minutes |
| `Passengers` | Journeys measured that month |
| `TerminalOTP` | Terminal on-time performance (secondary reliability metric) |
| `ServiceAreaIncome` | Commuter-weighted median household income of the line's 800 m service area (ACS 2018–2022) |
| `IncomeBracket` | Low / Medium / High (tertiles of line-level income) |
| `Modernized` | Yes if the line runs CBTC (the 7 and L), else No |
| `CBTCActivation` | CBTC activation date (blank if not modernized) |

## Data model (star schema)

- **Fact_LineMonth** — `Line`, `Date`, `OnTimeRate`, `AddedJourneyMin`, `Passengers`, `TerminalOTP`
- **Dim_Line** — `Line`, `ServiceAreaIncome`, `IncomeBracket`, `Modernized`, `CBTCActivation` (21 rows)
- **Dim_Date** — generated calendar table (DAX `CALENDAR`)

Relationships: `Dim_Line[Line]` → `Fact_LineMonth[Line]` and `Dim_Date[Date]` →
`Fact_LineMonth[Date]`, both one-to-many, single direction.

## Headline numbers

- CBTC lines: **+3.0 pp** on-time vs non-CBTC, two-way fixed-effects estimate (line + month effects, line-clustered SE), *p* = 0.017. The raw 2022–2026 group gap is +6.9 pp.
- Income vs on-time rate: **Pearson r = 0.13** across 21 lines (2022–2026) — no detectable line-level gradient.
