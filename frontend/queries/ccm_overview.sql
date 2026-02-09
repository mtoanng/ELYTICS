
-- -- SELECT *

-- -- FROM
-- --   ps_xplatform_dev.pemely_ops.vav1tb_ccm_table


-- -- CREATE OR REPLACE TABLE ps_xplatform_dev.pemely_ops.vav1tb_ccm_table AS

-- SELECT

-- first_value(ORDR.order_id) AS order_id, -- should be unique, as grouped by sample_id

-- first_value(SAMP.sample_id) AS sample_id, -- should be unique, as grouped by sample_id

-- first_value(SAMP.name) AS sample_name, -- should be unique, as grouped by sample_id

-- first_value(SAMP.leepa_number) AS leepa_number, -- should be unique, as grouped by sample_id

-- first_value(SAMP.ccm_name) AS ccm_name, -- should be unique, as grouped by sample_id

-- first_value(SAMP.active_area_per_cell) AS active_area_per_cell, -- should be unique, as grouped by sample_id

-- first_value(SAMP.ptl_name) AS PTL_name, -- should be unique, as grouped by sample_id

-- first_value(SAMP.gdl_name) AS GDL_name, -- should be unique, as grouped by sample_id

-- SUM(TS.timeFacRun) AS total_runtime, -- CORE metric of this table (per CCM_name)

-- MIN(TS.time) AS start_time, -- first timestamp of order (irrespective of operation)

-- MAX(TS.time) AS end_time, -- last timestamp of order (irrespective of operation)

-- last_value(ORDR.testrig_id) AS testrig_id -- may not be unique, as grouped by sample_id, but OK for now, just take most 'recent'...

-- FROM ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1hr AS TS

-- LEFT JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order AS ORDR ON TS.order_id = ORDR.order_id --get all timeseries stats, inc without order

-- LEFT JOIN ps_xplatform_dev.pemely_ops.gold_sample AS SAMP ON ORDR.sample_id = SAMP.sample_id --get all samples, inc without entry in gold_sample

-- -- GROUP BY SAMP.sample_id -- needed for runtime 'sum' operation per sample

-- GROUP BY TS.order_id -- needed for runtime 'sum' operation per sample

-- ORDER BY ccm_name; -- convenience for visual inspection


SELECT
    ORDR.order_id                                   AS order_id,
    EXPLODED.test_id                                AS test_id,

    first_value(SAMP.sample_id)                     AS sample_id,
    first_value(SAMP.name)                          AS sample_name,
    first_value(SAMP.leepa_number)                  AS leepa_number,
    first_value(SAMP.ccm_name)                      AS ccm_name,
    first_value(SAMP.active_area_per_cell)          AS active_area_per_cell,
    first_value(SAMP.ptl_name)                      AS PTL_name,
    first_value(SAMP.gdl_name)                      AS GDL_name,

    SUM(TS.timeFacRun)                              AS total_runtime,
    MIN(TS.time)                                   AS start_time,
    MAX(TS.time)                                   AS end_time,

    last_value(ORDR.testrig_id)                     AS testrig_id

FROM ps_xplatform_dev.pemely_ops.gold_genericstack_timeseries_1hr TS

LEFT JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order ORDR
    ON TS.order_id = ORDR.order_id

LEFT JOIN ps_xplatform_dev.pemely_ops.gold_sample SAMP
    ON ORDR.sample_id = SAMP.sample_id

-- explode test_id array into one row per test
LATERAL VIEW explode(ORDR.test_id) EXPLODED AS test_id

GROUP BY
    ORDR.order_id,
    EXPLODED.test_id

ORDER BY
    EXPLODED.test_id,
    start_time;