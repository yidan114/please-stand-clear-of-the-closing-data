"""
run_pipeline.py  --  SQL-first pipeline for the NYC subway service-quality study.

Data flow (see README "Pipeline architecture"):

    raw files ─┐
               ├─(Python, geometry)─►  data/processed/line_tract_overlap.csv
    GTFS+tracts┘                                     │
                                                     ▼
    raw CSVs ───────────────────────────►  DuckDB: sql/01 → 02 → 03
                                                     │
                                                     ▼
                              data/processed/panel_features.parquet
                                                     │
                                    ┌────────────────┴───────────────┐
                                    ▼                                ▼
                         Python: panel regressions        build_explorer.py (Plotly)

Python's job is only the two things SQL is the wrong tool for: the spatial
buffer/overlay (upstream) and the fixed-effects regressions (downstream).
All the data cleaning, joining, and feature construction is SQL.

Usage:
    python run_pipeline.py            # run everything, refreshing missing inputs
    python run_pipeline.py --sql-only # assume inputs exist, just (re)run the SQL
"""

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
DB_PATH = PROCESSED / "subway.duckdb"

SQL_FILES = ["01_load.sql", "02_join.sql", "03_features.sql"]


def ensure_inputs() -> None:
    """Create the two file inputs the SQL depends on, if they're missing."""
    overlap = PROCESSED / "line_tract_overlap.csv"
    if not overlap.exists():
        print("[inputs] building service-area overlap (geopandas) ...")
        subprocess.run([sys.executable, "scripts/build_service_areas.py"], cwd=ROOT, check=True)

    acs = ROOT / "data" / "raw" / "acs_2022.csv"
    if not acs.exists():
        print("[inputs] ACS snapshot missing -- fetching from Census API ...")
        subprocess.run([sys.executable, "scripts/fetch_acs.py"], cwd=ROOT, check=True)


def run_sql() -> duckdb.DuckDBPyConnection:
    """Execute the SQL layer in order against a fresh DuckDB file."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    for name in SQL_FILES:
        print(f"[sql] {name}")
        con.execute((SQL_DIR / name).read_text())
    return con


def export(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Persist the SQL outputs for downstream Python and the explorer."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY panel_features TO '{PROCESSED/'panel_features.parquet'}' (FORMAT parquet)"
    )
    con.execute(
        f"COPY (SELECT * FROM line_income ORDER BY avg_income) "
        f"TO '{PROCESSED/'line_income.csv'}' (HEADER, DELIMITER ',')"
    )
    panel = con.execute("SELECT * FROM panel_features").fetchdf()
    print(f"[export] panel_features: {panel.shape[0]} line-months, "
          f"{panel['line'].nunique()} lines, "
          f"{panel['month'].min().date()} → {panel['month'].max().date()}")
    return panel


# ---------------------------------------------------------------------------
# Downstream Python: the regressions SQL can't do.
# ---------------------------------------------------------------------------
def run_models(panel: pd.DataFrame) -> str:
    from linearmodels.panel import PanelOLS

    lines = []
    def say(s=""):
        print(s); lines.append(s)

    # --- Headline: two-way FE effect of CBTC activation ----------------------
    p = panel.dropna(subset=["cjtp", "cbtc_active"]).copy()
    p = p.set_index(["line", "month"]).sort_index()
    res = PanelOLS.from_formula(
        "cjtp ~ 1 + cbtc_active + EntityEffects + TimeEffects", data=p
    ).fit(cov_type="clustered", cluster_entity=True)
    coef = res.params["cbtc_active"]
    pval = res.pvalues["cbtc_active"]
    say("== CBTC activation (two-way FE, line-clustered SE) ==")
    say(f"   cbtc_active coef = {coef:+.4f}  ({coef*100:+.1f} pp)   p = {pval:.3f}")

    # --- Income vs service quality (line-level, 2022+) -----------------------
    recent = panel[panel["year"] >= 2022]
    by_line = (recent.groupby("line")
                     .agg(cjtp_peak=("cjtp", "mean"),
                          avg_income=("avg_income", "first"))
                     .dropna())
    r = np.corrcoef(by_line["avg_income"], by_line["cjtp_peak"])[0, 1]
    say("")
    say("== Service quality vs service-area income (2022+, per line) ==")
    say(f"   Pearson r = {r:.3f}   (n = {len(by_line)} lines)")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql-only", action="store_true",
                    help="skip input refresh; just re-run the SQL layer")
    args = ap.parse_args()

    if not args.sql_only:
        ensure_inputs()

    con = run_sql()
    panel = export(con)
    summary = run_models(panel)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "model_results.txt").write_text(summary + "\n")
    print(f"\n[done] results written to {OUTPUT/'model_results.txt'}")
    print("[done] run  python scripts/build_explorer.py  for the interactive chart")


if __name__ == "__main__":
    main()
