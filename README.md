# Please Stand Clear of the Closing Data

*Service quality and transit equity across the NYC subway system.*  
*A rider's hunch, audited against eleven years of MTA data.*

---

I take the B train on weekends. Three out of five times, it delays. I take the 1 train every day, and it just shows up.

I'm not the only one keeping a ledger like this. Most New Yorkers carry a version of it: which line works, which line eats their Saturday, which one they've quietly stopped trusting. This repo runs that ledger against eleven years of MTA performance data, and asks whether what riders feel in their feet lines up with what the numbers say.

Short answer: the 1 really is more reliable than the B. The reason, though, isn't where most equity narratives expect it to be.

## What this is

A policy brief analyzing line-level Customer Journey Time Performance (CJTP) across 21 NYC subway lines over an eleven-year monthly panel. The central finding: service quality varies substantially and persistently across lines, but the variation does not track service-area median household income. It is more clearly organized by capital investment history, specifically which lines have received signaling upgrades.

Methods include two-way fixed-effects panel regression with line-clustered standard errors, an event-study around Communications-Based Train Control (CBTC) activation on the 7 train, and a spatial join between MTA service areas and ACS demographics.

## Pipeline architecture: SQL → Python

The data preparation — loading, cleaning, joining four sources, and building
every model feature — runs in **SQL (DuckDB)**. Python is kept to the two jobs
SQL is genuinely the wrong tool for: the **spatial geometry** upstream and the
**fixed-effects regressions** downstream. Nothing in the middle is pandas.

```
  GTFS + tract shapefile ──►  scripts/build_service_areas.py   (geopandas: 800m buffers → tract overlap)
                                          │
                                          ▼
                              data/processed/line_tract_overlap.csv
                                          │
  CJTP · OTP · ACS · CBTC ──────────────► │
                                          ▼
                            DuckDB:  sql/01_load → 02_join → 03_features
                                          │
                              data/processed/panel_features.parquet
                                          │
                        ┌─────────────────┴──────────────────┐
                        ▼                                     ▼
         Python: PanelOLS fixed-effects            scripts/build_explorer.py
              (run_pipeline.py)                    (interactive Plotly HTML)
```

**Why the spatial step stays in Python.** Assigning each line a service area
means projecting stations to a metric coordinate system (EPSG:2263), drawing
800 m walk-buffers, dissolving them per line, and intersecting with census
tracts. That is coordinate-reference and geometry math; DuckDB's core has no
spatial type, and doing projected buffers in SQL would be fragile. So geopandas
does the geometry and hands SQL a plain, non-spatial table: `line, geoid,
overlap_share`. **The population-weighting itself — the part that is a
`GROUP BY` — is done in SQL** (`sql/02_join.sql`), which is where the clean split
lives: Python draws the polygons, SQL weights them.

**What the SQL layer demonstrates.**

| Technique | Where | Doing what |
|---|---|---|
| Multi-table `JOIN` | `02_join.sql` | CJTP ⋈ OTP ⋈ ACS-derived income ⋈ CBTC dates, to one line-month row |
| `GROUP BY` aggregation | `02_join.sql` | population-weighted income per line; OTP day-types → line-month |
| `CTE` (`WITH … AS`) | `02`, `03` | naming each step (weighted tracts, flags, windows) instead of nesting subqueries |
| Window `LAG()` | `03_features.sql` | month-over-month and year-over-year CJTP change per line |
| Window `AVG() OVER` | `03_features.sql` | 3- and 12-month trailing averages; each line's pre/post-CBTC mean |
| `CASE WHEN` | `03_features.sql` | the CBTC treatment dummy, era label, and `months_since_cbtc` |

The `sql/` files are numbered in execution order and each one only builds on the
tables the previous one created. `run_pipeline.py` runs them in sequence on a
single DuckDB connection, then hands `panel_features` to the regressions.

## Running it

```bash
pip install duckdb geopandas linearmodels requests plotly

# One-time: pull the ACS snapshot from the Census API (needs network).
# Get a free key at https://api.census.gov/data/key_signup.html
export CENSUS_API_KEY=...        # optional but recommended
python scripts/fetch_acs.py      # writes data/raw/acs_2022.csv (commit this)

# Full pipeline: geometry → SQL → regressions
python run_pipeline.py           # writes data/processed/panel_features.parquet + output/model_results.txt

# Interactive explorer (self-contained HTML, opens offline)
python scripts/build_explorer.py # writes output/subway_explorer.html
```

`run_pipeline.py` auto-runs the geometry and ACS steps if their outputs are
missing; use `--sql-only` to just re-run the SQL against existing inputs.

## Read the brief

The compiled PDF: [`output/brief/brief.pdf`](output/brief/brief.pdf)

The RMarkdown source: [`output/brief/brief.Rmd`](output/brief/brief.Rmd)

The interactive explorer: [`output/subway_explorer.html`](output/subway_explorer.html) — pick a line, watch its reliability over time, see where CBTC switched on.

## Data sources

- **MTA Subway Customer Journey-Focused Metrics**, 2015–present (data.ny.gov) — CJTP, monthly × line × period
- **MTA Terminal On-Time Performance**, monthly × line × day-type — a second, independent reliability metric, joined to CJTP on line-month
- **ACS 5-year estimates 2018–2022**, tract-level (Census API) — median income, transit commuting; pulled by `scripts/fetch_acs.py`
- **MTA GTFS static feed** — maps stations to lines and lines to service areas
- **CBTC activation dates** — L (Feb 2012), 7 (Nov 2018); encoded in `sql/01_load.sql`

## Repo layout

```
sql/                  DuckDB pipeline, numbered by execution order
  01_load.sql         clean + type the raw sources into staging tables
  02_join.sql         multi-table joins → the line-month panel
  03_features.sql     window functions + CASE WHEN → model features
scripts/
  fetch_acs.py        pull the ACS snapshot from the Census API
  build_service_areas.py   geopandas: service-area buffers → tract overlap
  build_explorer.py   render the interactive Plotly explorer
run_pipeline.py       orchestrates geometry → SQL → regressions
code/                 original exploratory notebooks (kept as narrative)
data/raw/             downloaded as-is, gitignored (ACS snapshot committed)
data/processed/       tidy panels, gitignored
output/figures/       pdf + png exports embedded in the brief
output/brief/         .Rmd source and compiled PDF
output/subway_explorer.html   interactive line explorer
```

## Author

Yidan Kong, QMSS, Columbia University.
