# Please Stand Clear of the Closing Data

Service quality and transit equity across the NYC subway system.
A rider's hunch, audited against eleven years of MTA data.

## What this is

A 6-page policy brief examining heterogeneity in subway service
quality across lines, peak/off-peak periods, and pre/post-pandemic
recovery, and whether the gaps track the demographics of the
neighborhoods each line serves.

Written in R + RMarkdown; data prep and spatial joins in Python.
Panel regression with line and time fixed effects, cluster-robust
standard errors at the line level.

## Data

- MTA Subway Customer Journey-Focused Metrics, 2015–present
- MTA Subway Terminal On-Time Performance, 2015–2019 (robustness check)
- ACS census tract demographics
- GTFS static feed for line → tract spatial mapping

## Repo layout

    code/             scripts and notebooks, numbered by stage
    data/raw/         downloaded as-is, gitignored
    data/processed/   tidy panels
    output/figures/   pdf + png, brief-ready
    output/brief/     .Rmd source and compiled PDF

## Author

Yidan Kong — QMSS, Columbia.
