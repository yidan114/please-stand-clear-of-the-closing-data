-- =============================================================================
-- 02_join.sql  --  Join the sources into one line x month analysis panel
-- =============================================================================
-- This is where the four sources meet. Two things happen:
--
--   1. line_income   -- collapse the spatial overlap x ACS into ONE
--                       population-weighted income (and transit share) per line.
--                       This is the "weighted income in SQL" split we chose:
--                       geopandas drew the polygons, SQL does the weighting.
--
--   2. panel         -- the line x month peak-hour CJTP series, LEFT JOINed to
--                       terminal on-time performance (OTP), to per-line income,
--                       and to the CBTC activation date. One row per line-month.
--
-- Everything is a straightforward JOIN / GROUP BY; no window logic yet.
-- =============================================================================


-- --- 1. Population-weighted service-area income, per line ---------------------
-- A tract contributes to a line in proportion to (a) how much of it sits inside
-- the line's walk-shed and (b) how many transit commuters live there. So the
-- weight is overlap_share * commuters_total, and each line's income is the
-- weighted average of its tracts' median incomes.
--
-- A CTE names the weighted intermediate so the final SELECT reads like the
-- sentence above instead of a nest of subqueries.
CREATE OR REPLACE TABLE line_income AS
WITH tract_weighted AS (
    SELECT
        o.line,
        o.geoid,
        o.overlap_share * a.commuters_total          AS weight,
        a.median_income,
        a.transit_share
    FROM stg_overlap o
    JOIN stg_acs a USING (geoid)          -- inner join: drop tracts with no ACS match
    WHERE a.median_income IS NOT NULL
      AND a.commuters_total IS NOT NULL
)
SELECT
    line,
    SUM(median_income * weight) / SUM(weight)  AS avg_income,
    SUM(transit_share  * weight) / SUM(weight)  AS avg_transit_share,
    COUNT(*)                                     AS n_tracts
FROM tract_weighted
GROUP BY line;


-- --- 2. Collapse OTP from (line, month, day_type) to (line, month) ------------
-- Two day types per month. Recombine by trip volume -- sum the trips, then
-- divide -- rather than averaging two rates, so a light-service weekend doesn't
-- get equal weight to a heavy weekday.
CREATE OR REPLACE TABLE otp_monthly AS
SELECT
    line,
    month,
    SUM(on_time_trips)                          AS on_time_trips,
    SUM(sched_trips)                            AS sched_trips,
    SUM(on_time_trips) * 1.0 / SUM(sched_trips)  AS terminal_otp
FROM stg_otp
GROUP BY line, month;


-- --- 3. The analysis panel: one row per line-month ---------------------------
-- CJTP peak hours is the spine. OTP and income are attached with LEFT JOINs so
-- a line-month is never dropped just because the other feed is missing it
-- (OTP, for instance, doesn't cover every line-month). CBTC activation comes in
-- as a date we can compare against later.
CREATE OR REPLACE TABLE panel AS
SELECT
    c.line,
    c.month,
    CAST(strftime(c.month, '%Y') AS INTEGER)  AS year,
    c.cjtp,
    c.num_passengers,
    o.terminal_otp,
    i.avg_income,
    i.avg_transit_share,
    b.cbtc_activation                          AS cbtc_activation
FROM stg_cjtp c
LEFT JOIN otp_monthly  o ON o.line = c.line AND o.month = c.month
LEFT JOIN line_income  i ON i.line = c.line
LEFT JOIN dim_cbtc     b ON b.line = c.line
WHERE c.period = 'peak'
ORDER BY c.line, c.month;
