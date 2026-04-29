SELECT
    batch AS stack_short_nr,
    uniquepart_id,
    CAST(regexp_extract(batch, r'_(\d\d\d)_') AS INT) AS number_of_cells,
    CASE WHEN part_attribute = 0 THEN 'serial part'
         WHEN part_attribute = 1 THEN 'test_part'
         WHEN part_attribute = 2 THEN 'test_part'
         ELSE 'unknown_part'
         END AS part_attribute_description,
    result_date_utc,
    CASE WHEN result_state = 1 THEN 'passed'
         WHEN result_state = 2 THEN 'failed'
         WHEN result_state = 3 THEN 'measured'
         ELSE 'unknown_result_state'
         END AS result_state_description,
    lastknown_proc_no,
    lastknown_proc_no_description,
    order_id
FROM
    ps_xplatform_prod.mas.mfg_db_quality_uniqueparts_raw_sql stack
WHERE
    IPN_NAME = 'PEMELY'
    AND batch LIKE 'P1_1250_%'
ORDER BY
    stack_short_nr, result_date_utc
