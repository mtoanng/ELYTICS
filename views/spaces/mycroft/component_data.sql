SELECT
    stack_short_nr,
    uniquepart_id,
    number_of_cells,
    part_attribute_description,
    location_result_uid,
    NULL as location_result_state_description,
    componentclass,
    componentidentifier,
    component_type,
    component_type_number,
    NULL as line,
    NULL as state_description,
    batch,
    result_date_utc,
    location_result_state,
    uniquepart_part_attribute  
FROM
    ps_xplatform_prod.mas.mfg_db_quality_components_raw_sql components
INNER JOIN
    (
        SELECT
            batch AS stack_short_nr,
            uniquepart_id AS uniquepart_id_stack,
            CAST(regexp_extract(batch, r'_(\d\d\d)_') AS INT) AS number_of_cells,
            CASE WHEN part_attribute = 0 THEN 'serial part'
                WHEN part_attribute = 1 THEN 'test_part'
                WHEN part_attribute = 2 THEN 'test_part'
                ELSE 'unknown_part'
                END AS part_attribute_description    
        FROM
            ps_xplatform_prod.mas.mfg_db_quality_uniqueparts_raw_sql
        WHERE
            IPN_NAME = 'PEMELY'
            AND batch LIKE 'P1_1250_%'
    ) stack
ON
    uniquepart_id_stack = uniquepart_id
