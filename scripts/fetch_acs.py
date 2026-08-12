"""
Fetch tract-level ACS 5-year estimates (2018-2022) for the five NYC counties
and write a flat snapshot to data/raw/acs_2022.csv.

Why this is a separate script (and not inside the SQL layer):
the SQL pipeline reads *files*. The Census API is a network dependency, so we
pull it once here and cache the result as a CSV that DuckDB can read offline.
The committed snapshot means anyone who clones the repo can run the whole
pipeline without network access or a Census key; re-run this script only when
you want to refresh the vintage.

Census now generally requires a free API key for tract-level pulls. Get one at
https://api.census.gov/data/key_signup.html and either export it as
CENSUS_API_KEY or pass --key. Small keyless pulls sometimes succeed but are
rate-limited and not guaranteed.

Variables pulled:
    B19013_001E  median household income
    B25044_003E  owner-occupied households, no vehicle
    B25044_010E  renter-occupied households, no vehicle
    B08301_001E  workers 16+ (commute universe)
    B08301_010E  workers commuting by public transit
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAW = Path("data/raw")
YEAR = 2022
STATE_FIPS = "36"                                   # New York
NYC_COUNTY_FIPS = ["005", "047", "061", "081", "085"]  # Bronx, Kings, NY, Queens, Richmond
VARIABLES = ["B19013_001E", "B25044_003E", "B25044_010E", "B08301_001E", "B08301_010E"]

RENAME = {
    "B19013_001E": "median_income",
    "B25044_003E": "owner_no_vehicle",
    "B25044_010E": "renter_no_vehicle",
    "B08301_001E": "commuters_total",
    "B08301_010E": "commuters_transit",
}


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch(key: str | None) -> pd.DataFrame:
    s = _session()
    get = "NAME," + ",".join(VARIABLES)
    frames = []
    for county in NYC_COUNTY_FIPS:
        url = (
            f"https://api.census.gov/data/{YEAR}/acs/acs5"
            f"?get={get}&for=tract:*&in=state:{STATE_FIPS}+county:{county}"
        )
        if key:
            url += f"&key={key}"
        print(f"  county {county} ...", end=" ", flush=True)
        r = s.get(url, timeout=120)
        r.raise_for_status()
        header, *rows = r.json()
        frames.append(pd.DataFrame(rows, columns=header))
        print(f"{len(rows)} tracts")
    return pd.concat(frames, ignore_index=True)


def clean(acs: pd.DataFrame) -> pd.DataFrame:
    acs = acs.rename(columns=RENAME)
    for col in RENAME.values():
        acs[col] = pd.to_numeric(acs[col], errors="coerce")
        # Census uses large negative sentinels (e.g. -666666666) for "no data".
        acs.loc[acs[col] < 0, col] = pd.NA

    # geoid = state + county + tract, matches the 'geoid' field in nyct2020.
    acs["geoid"] = acs["state"] + acs["county"] + acs["tract"]
    acs["no_vehicle"] = acs["owner_no_vehicle"] + acs["renter_no_vehicle"]
    acs["transit_share"] = acs["commuters_transit"] / acs["commuters_total"]

    cols = ["geoid", "median_income", "no_vehicle",
            "commuters_total", "commuters_transit", "transit_share"]
    return acs[cols].sort_values("geoid").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("CENSUS_API_KEY"),
                    help="Census API key (or set CENSUS_API_KEY)")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Fetching ACS {YEAR} 5-year, tract level, NYC ...")
    try:
        raw = fetch(args.key)
    except requests.HTTPError as e:
        print(f"\nCensus API request failed: {e}", file=sys.stderr)
        print("Tip: get a free key at https://api.census.gov/data/key_signup.html "
              "and export CENSUS_API_KEY.", file=sys.stderr)
        sys.exit(1)

    out = clean(raw)
    out_path = RAW / "acs_2022.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}  tracts={len(out)}  "
          f"median_income coverage={out['median_income'].notna().mean():.0%}")


if __name__ == "__main__":
    main()
