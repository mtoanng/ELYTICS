SELECT DISTINCT
  sample_name AS sample_name,
  number_of_cells AS number_of_cells,
  ccm_type AS ccm_type,
  is_rising AS is_rising
FROM
  ps_xplatform_dev.pemely_dev.gold_virtual_sensor_soh_cr_sherlock