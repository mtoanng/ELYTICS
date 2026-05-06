SELECT
    sample_name                                   AS sample_name,
    runtime_hours                                 AS runtime_hours,
    absolute_timestamp                            AS absolute_timestamp,
    sensor_type                                   AS sensor_type,
    number_of_cells                               AS number_of_cells,
    IVnumber                                      AS IVnumber,
    ccm_type                                      AS ccm_type,
    tAndeIn                                       AS tAndeIn,
    pAndeOut                                      AS pAndeOut,
    pCtdeOut                                      AS pCtdeOut,
    jStck                                         AS jStck,
    uCellAvg                                      AS uCellAvg,
    soh_lin_stack                                 AS soh_lin_stack,
    soh_kin_stack                                 AS soh_kin_stack,
    model_min_obj_stack                           AS model_min_obj_stack,
    is_rising                                     AS is_rising,
    `model_uCellAvg_pc_3-0_stack`,
    `model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_stack`,
    `model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_stack`,
    `model_uCellAvg_BoL_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1delta_Rohm-0_stack`

FROM ps_xplatform_dev.pemely_dev.gold_virtual_sensor_soh_cr_sherlock

ORDER BY
    sample_name,
    sensor_type,
    runtime_hours;

