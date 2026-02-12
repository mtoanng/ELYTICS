-- ============================================================
-- Timeseries Raw 1s Export
-- ============================================================

SELECT
    ts.time          AS ts,
    ts.order_id,
    o.testrig_id,
    o.sample_name,
    o.number_of_cells,

    {{raw_signal_select}}

FROM ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1s ts
INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
    ON ts.order_id = o.order_id

WHERE 1 = 1
{{extra_filters}}

ORDER BY ts.time;
