-- ============================================================
-- Timeseries Exploration (Dynamic Signals)
-- ============================================================

WITH filtered_ts AS (

    SELECT
        ts.time                     AS time,
        ts.order_id                 AS order_id,

        -- Metadata
        o.sample_name               AS sample_name,
        o.number_of_cells           AS number_of_cells,
        o.testrig_id                AS testrig_id,

        -- Raw location from dimension table
        tr.location                 AS raw_location,

        -- Normalized location
        CASE
            WHEN lower(tr.location) LIKE '%bap%' THEN 'BaP'
            WHEN lower(tr.location) LIKE '%rng%' THEN 'RnG'
            WHEN lower(tr.location) LIKE '%tbp%' THEN 'TbP'
            WHEN tr.location IN ('AVL', 'Liz') THEN 'External'
            ELSE tr.location
        END AS location_norm,

        -- Label for UI
        CONCAT(
            o.testrig_id, ' - ',
            CASE
                WHEN lower(tr.location) LIKE '%bap%' THEN 'BaP'
                WHEN lower(tr.location) LIKE '%rng%' THEN 'RnG'
                WHEN lower(tr.location) LIKE '%tbp%' THEN 'TbP'

                WHEN lower(tr.location) LIKE '%avl%' THEN 'External'
                WHEN lower(tr.location) LIKE '%liz%' THEN 'External'
                WHEN lower(tr.location) LIKE '%kst%' THEN 'External'
                WHEN lower(tr.location) LIKE '%hycenta%' THEN 'External'
                WHEN lower(tr.location) LIKE '%fz j%' THEN 'External'

                ELSE tr.location
            END
        ) AS testrig_label,

        -- Dynamically injected raw signals
        {{raw_signal_select}}

    FROM ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1s ts
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
        ON ts.order_id = o.order_id
    LEFT JOIN ps_xplatform_prod.pemely_dev.silver_dim_testrig tr
        ON o.testrig_id = tr.testrig_id

    WHERE 1 = 1
    {{filters}}
)

SELECT
    {{time_bucket_expr}} AS ts,
    order_id,
    testrig_label,
    sample_name,
    number_of_cells,
    {{agg_signal_select}}
FROM filtered_ts
GROUP BY
    ts,
    order_id,
    testrig_label,
    sample_name,
    number_of_cells
{{sorting}}
{{limit}}
{{offset}};