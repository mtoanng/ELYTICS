SELECT DISTINCT
  testrig_id,
  location,
  CASE
    WHEN lower(location) LIKE '%bap%' THEN 'BaP'
    WHEN lower(location) LIKE '%rng%' THEN 'RnG'
    WHEN lower(location) LIKE '%tbp%' THEN 'TbP'
    WHEN lower(location) IN ('avl', 'liz', 'kst', 'hycenta', 'fz j') THEN 'External'
    ELSE location
  END AS testrig_location
FROM
  ps_xplatform_prod.pemely_dev.silver_dim_testrig
  WHERE
  testrig_id LIKE 'E%'