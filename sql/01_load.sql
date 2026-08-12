-- =============================================================================
-- 01_load.sql  --  Load & clean raw sources into typed staging tables
-- =============================================================================
-- Runs first. Every later script builds on the stg_* tables created here.
-- Raw files are read straight off disk with read_csv_auto; the job of this
-- script is only to (1) give columns clean snake_case names, (2) cast types,
-- and (3) restrict to the 21 "main" lines the study covers. No joins, no
-- aggregation, no business logic yet -- those live in 02 and 03.
--
-- Paths are relative to the repo root, which is where run_pipeline.py opens the
-- DuckDB connection.
-- =============================================================================


-- The 21 revenue lines the analysis covers. The three shuttles (S 42nd,
-- S Fkln, S Rock) and GTFS-only artifacts (FS, GS, H) are intentionally out.
-- A one-column dimension table reads better than repeating a 21-item IN (...)
-- list in every downstream query.
CREATE OR REPLACE TABLE dim_line AS
SELECT * FROM (VALUES
    ('1'),('2'),('3'),('4'),('5'),('6'),('7'),
    ('A'),('B'),('C'),('D'),('E'),('F'),('G'),
    ('JZ'),('L'),('M'),('N'),('Q'),('R'),('W')
) AS t(line);


-- CBTC (Communications-Based Train Control) activation dates. Only two lines
-- were fully converted inside the sample window: the L (Feb 2012) and the
-- 7 (Nov 2018). Storing this as a table -- rather than a hard-coded dict buried
-- in Python -- makes the treatment definition auditable and easy to extend.
CREATE OR REPLACE TABLE dim_cbtc AS
SELECT * FROM (VALUES
    ('L', DATE '2012-02-01'),
    ('7', DATE '2018-11-01')
) AS t(line, cbtc_activation);


-- Customer Journey Time Performance: share of trips completed within 5 minutes
-- of schedule. Native grain is month x line x period (peak / offpeak).
-- Note the double-quoted source columns: the raw CSV header has spaces.
CREATE OR REPLACE TABLE stg_cjtp AS
SELECT
    CAST(month AS DATE)                              AS month,
    line,
    period,
    CAST(num_passengers AS DOUBLE)                   AS num_passengers,
    CAST("customer journey time performance" AS DOUBLE) AS cjtp,
    CAST("over_five_mins_perc" AS DOUBLE)            AS over_five_mins_perc
FROM read_csv_auto('data/raw/cjm_2015_present.csv', header = true)
WHERE line IN (SELECT line FROM dim_line);


-- Terminal On-Time Performance: a *different* reliability metric (did the train
-- hit its terminal on schedule), from a separate MTA feed. Native grain is
-- month x line x day_type (1 = weekday, 2 = weekend). We keep the raw trip
-- counts so 02 can recombine day types by volume rather than a naive mean.
CREATE OR REPLACE TABLE stg_otp AS
SELECT
    CAST(month AS DATE)                 AS month,
    line,
    CAST(day_type AS INTEGER)           AS day_type,
    CAST(num_on_time_trips AS BIGINT)   AS on_time_trips,
    CAST(num_sched_trips AS BIGINT)     AS sched_trips
FROM read_csv_auto('data/raw/otp_2015_2019.csv', header = true)
WHERE line IN (SELECT line FROM dim_line);


-- Tract-level ACS 5-year estimates (2018-2022), one row per census tract.
-- Produced by scripts/fetch_acs.py. geoid = state+county+tract, which matches
-- the geoid field on the tract polygons used in the spatial step.
CREATE OR REPLACE TABLE stg_acs AS
SELECT
    CAST(geoid AS VARCHAR)              AS geoid,
    CAST(median_income AS DOUBLE)       AS median_income,
    CAST(transit_share AS DOUBLE)       AS transit_share,
    CAST(commuters_total AS DOUBLE)     AS commuters_total
FROM read_csv_auto('data/raw/acs_2022.csv', header = true);


-- line x tract overlap shares from the geopandas step (scripts/build_service_areas.py).
-- overlap_share = fraction of a tract's area inside the line's 800 m service polygon.
-- This is the hand-off from Python geometry to SQL: from here on it's all joins
-- and aggregation.
CREATE OR REPLACE TABLE stg_overlap AS
SELECT
    line,
    CAST(geoid AS VARCHAR)      AS geoid,
    CAST(overlap_share AS DOUBLE) AS overlap_share
FROM read_csv_auto('data/processed/line_tract_overlap.csv', header = true)
WHERE line IN (SELECT line FROM dim_line);
