-- =============================================================================
-- 03_features.sql  --  Derive model features with window functions
-- =============================================================================
-- The panel from 02 is tidy but "flat": each row only knows about itself. The
-- event-study and the trend visuals need each line-month to know about its
-- neighbours in time -- the month before, a rolling window, its own pre- vs
-- post-CBTC average. That is exactly what window functions are for.
--
-- Structure: two CTEs, then one SELECT.
--   flagged   -- CASE WHEN treatment/era flags (row-local, no ordering needed)
--   windowed  -- LAG / moving-average / partitioned-average over time per line
-- Splitting them keeps each step legible and lets the window layer reuse the
-- flags (e.g. partition by cbtc_active) instead of recomputing them.
--
-- Output: panel_features -- the table run_pipeline.py hands to the regression
-- and plotting step.
-- =============================================================================

CREATE OR REPLACE TABLE panel_features AS
WITH flagged AS (
    SELECT
        line,
        month,
        year,
        cjtp,
        num_passengers,
        terminal_otp,
        avg_income,
        avg_transit_share,
        cbtc_activation,

        -- Is this one of the CBTC-converted lines at all?
        CASE WHEN cbtc_activation IS NOT NULL THEN 1 ELSE 0 END        AS cbtc_line,

        -- The treatment dummy: 1 once the line's own CBTC date has passed.
        -- This is the regressor behind the +3.0pp headline.
        CASE
            WHEN cbtc_activation IS NOT NULL AND month >= cbtc_activation THEN 1
            ELSE 0
        END                                                            AS cbtc_active,

        -- Human-readable era label, handy for group-bys and the viz legend.
        CASE
            WHEN cbtc_activation IS NULL              THEN 'never treated'
            WHEN month >= cbtc_activation            THEN 'post-CBTC'
            ELSE 'pre-CBTC'
        END                                                            AS cbtc_era,

        -- Signed months relative to activation (negative = before). NULL for
        -- lines that never got CBTC. This is the event-study running variable.
        CASE
            WHEN cbtc_activation IS NOT NULL
            THEN date_diff('month', cbtc_activation, month)
        END                                                            AS months_since_cbtc
    FROM panel
),

windowed AS (
    SELECT
        *,

        -- Previous month's CJTP for this line, and the month-over-month change.
        -- LAG walks one row back within each line's time-ordered series.
        LAG(cjtp) OVER w_line                       AS cjtp_prev_month,
        cjtp - LAG(cjtp) OVER w_line                AS cjtp_mom_change,

        -- Year-over-year change: LAG 12 rows back (12 monthly rows).
        cjtp - LAG(cjtp, 12) OVER w_line            AS cjtp_yoy_change,

        -- 3-month trailing moving average -- smooths the monthly noise. The
        -- ROWS frame says "this row and the two before it", per line.
        AVG(cjtp) OVER (
            PARTITION BY line ORDER BY month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        )                                           AS cjtp_ma3,

        -- 12-month trailing average -- the slow trend line for the explorer.
        AVG(cjtp) OVER (
            PARTITION BY line ORDER BY month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        )                                           AS cjtp_ma12,

        -- Each line's mean CJTP within its era (pre vs post its own CBTC date).
        -- Partitioning by cbtc_active gives the before/after baseline the event
        -- study is built around, as a single window expression.
        AVG(cjtp) OVER (PARTITION BY line, cbtc_active)  AS cjtp_era_avg
    FROM flagged
    WINDOW w_line AS (PARTITION BY line ORDER BY month)
)

SELECT *
FROM windowed
ORDER BY line, month;
