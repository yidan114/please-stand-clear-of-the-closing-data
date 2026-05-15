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

## Read the brief

The compiled PDF: [`output/brief/brief.pdf`](output/brief/brief.pdf)

The RMarkdown source: [`output/brief/brief.Rmd`](output/brief/brief.Rmd)

## Data sources

- MTA Subway Customer Journey-Focused Metrics, 2015–present (data.ny.gov)
- ACS 5-year estimates 2018–2022, tract-level (Census API)
- MTA GTFS static feed, used to map stations to lines and lines to service areas

## Repo layout
## Author

Yidan Kong, QMSS, Columbia University.
