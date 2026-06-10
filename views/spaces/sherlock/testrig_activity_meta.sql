SELECT DISTINCT
  testrig_id,
  location,
  CASE
      WHEN lower(location) LIKE '%bap%' THEN 'BaP'
      WHEN lower(location) LIKE '%liz%' THEN 'Liz'
      WHEN lower(location) LIKE '%rng%' THEN 'Rng'
      WHEN lower(location) LIKE '%tbp%' THEN 'TbP'
      WHEN lower(location) LIKE '%syv%' THEN 'Syv'
      WHEN lower(location) IN ('avl', 'linde', 'kst', 'hycenta') THEN 'External'
      WHEN lower(location) LIKE 'fz j%' THEN 'External'
      ELSE location
    END AS testrig_location
FROM
  ps_xplatform_prod.pemely_dev.silver_dim_testrig
  WHERE
  testrig_id LIKE 'E%'