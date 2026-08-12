"""
Build subway line service areas and their overlap with census tracts.

This is the ONE step that stays in Python: it is pure geometry (projecting to a
metric CRS, drawing 800 m walk buffers, dissolving them per line, and
intersecting with tract polygons). DuckDB's core has no spatial types, and
getting the projection / buffer math right is exactly the part that is fiddly
and error-prone in SQL. So we keep it in geopandas and hand SQL a clean,
non-spatial table:

    line , geoid , overlap_share

`overlap_share` is the fraction of a tract's area that falls inside a line's
service polygon. Everything downstream -- attaching ACS income, weighting by
population, aggregating to one income number per line -- is a GROUP BY, and
that lives in SQL (see sql/02_join.sql).

Output: data/processed/line_tract_overlap.csv
"""

from pathlib import Path
import warnings

import pandas as pd
import geopandas as gpd

warnings.filterwarnings("ignore", category=UserWarning, module="geopandas")

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

# GTFS route_id -> our line label. J and Z are reported together as "JZ".
ROUTE_TO_LINE = {
    "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
    "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G",
    "J": "JZ", "Z": "JZ",
    "L": "L", "M": "M",
    "N": "N", "Q": "Q", "R": "R", "W": "W",
}

WALK_METERS = 800                 # ~10 minute walk
NY_STATE_PLANE_FT = 2263          # EPSG:2263, US survey feet -- metric-ish, NYC standard
BUFFER_FT = WALK_METERS * 3.281   # 800 m expressed in feet for EPSG:2263


def main() -> None:
    # ---- GTFS chain: trips -> stop_times -> stops, tagged by line -------------
    stops = pd.read_csv(RAW / "gtfs" / "stops.txt")
    trips = pd.read_csv(RAW / "gtfs" / "trips.txt")
    stop_times = pd.read_csv(RAW / "gtfs" / "stop_times.txt")

    trips_main = trips[trips["route_id"].isin(ROUTE_TO_LINE)].copy()
    trips_main["line"] = trips_main["route_id"].map(ROUTE_TO_LINE)

    line_stops = (
        stop_times[["trip_id", "stop_id"]]
        .merge(trips_main[["trip_id", "line"]], on="trip_id")
        [["line", "stop_id"]]
        .drop_duplicates()
    )

    # Collapse platform stop_ids up to their parent station.
    stops["station_id"] = stops["parent_station"].fillna(stops["stop_id"])
    line_stations = (
        line_stops
        .merge(stops[["stop_id", "station_id"]], on="stop_id")
        [["line", "station_id"]]
        .drop_duplicates()
    )

    # ---- Station points -> per-line 800 m buffer polygons --------------------
    station_pts = stops[["station_id", "stop_lat", "stop_lon"]].drop_duplicates("station_id")
    stations_geo = gpd.GeoDataFrame(
        station_pts,
        geometry=gpd.points_from_xy(station_pts["stop_lon"], station_pts["stop_lat"]),
        crs="EPSG:4326",
    ).to_crs(epsg=NY_STATE_PLANE_FT)

    line_geo = gpd.GeoDataFrame(
        line_stations.merge(stations_geo[["station_id", "geometry"]], on="station_id"),
        geometry="geometry",
        crs=f"EPSG:{NY_STATE_PLANE_FT}",
    )
    line_service = (
        line_geo.assign(geometry=line_geo.buffer(BUFFER_FT))
        .dissolve(by="line")[["geometry"]]
        .reset_index()
    )

    # ---- Intersect service polygons with tracts ------------------------------
    tracts = gpd.read_file(RAW / "nyct2020").to_crs(epsg=NY_STATE_PLANE_FT)
    tracts["tract_area"] = tracts.geometry.area

    inter = gpd.overlay(
        line_service,
        tracts[["geoid", "tract_area", "geometry"]],
        how="intersection",
    )
    inter["overlap_share"] = inter.geometry.area / inter["tract_area"]

    out = (
        inter[["line", "geoid", "overlap_share"]]
        .sort_values(["line", "geoid"])
        .reset_index(drop=True)
    )
    out_path = PROCESSED / "line_tract_overlap.csv"
    out.to_csv(out_path, index=False)

    print(f"wrote {out_path}  rows={len(out)}  lines={out['line'].nunique()}")
    print(out.groupby("line").size().rename("n_tracts").sort_values(ascending=False).head(6))


if __name__ == "__main__":
    main()
