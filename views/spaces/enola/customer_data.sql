SELECT 
  sample_id,
  customer_name,
  customer_country,
  customer_city AS end_customer_city,
  lifecycle_status,
  plant_id,
  module_position,
  stack_position,
  max_runtime,
  -- Installed power based on the overridden lifecycle status
  CASE 
    WHEN lifecycle_status IN ('Installation - System FAT', 'In Warranty Period') THEN 1.25
    ELSE 0
  END AS installed_power_mw,
  longitude,
  latitude
FROM (
  SELECT 
    g.sample_id,
    g.customer_name,
    g.customer_country,
    g.customer_city,
    g.lifecycle_status,
    g.plant_id,
    g.module_position,
    g.stack_position,
    COALESCE(t.max_runtime, 0) AS max_runtime,
    p.longitude,
    p.latitude
  FROM ps_xplatform_dev.pemelydasop_ops.gold_sample g
  LEFT JOIN (
    SELECT 
      sample_id,
      ROUND(MAX(runtime/3600), 2) AS max_runtime
    FROM ps_xplatform_dev.pemelydasop_ops.gold_genericstack_timeseries_1s
    GROUP BY sample_id
  ) t
    ON g.sample_id = t.sample_id
  LEFT JOIN ps_xplatform_dev.pemelydasop_dev.silver_dim_plant p
    ON g.plant_id = p.plant_id
)