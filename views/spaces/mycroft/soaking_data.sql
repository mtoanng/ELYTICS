SELECT
 
    row_number() OVER(PARTITION BY uniquepart_id,process_number, process_step_number ORDER BY result_date_utc DESC) AS rn,
    *
FROM
    ps_xplatform_dev.pemely_dev.silver_mfganalytics_soaking_curves soakingcurves

