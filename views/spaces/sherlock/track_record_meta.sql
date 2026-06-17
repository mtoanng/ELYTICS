WITH runtime_per_sample AS (
  SELECT
    o.sample_name,
    MAX(o.sample_type) AS sample_type,
    MAX(o.sample_state) AS sample_state,
    CONCAT(MAX(o.sample_type), ' - ', MAX(o.sample_state)) AS sample_type_state,
    ceil(sum(hr.calc.time_fac_run)) AS run_hours,
    MAX(o.number_of_cells) AS number_of_cells
  FROM
    ps_xplatform_prod.pemely_ops.gold_timeseries_1h hr
      INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
        ON hr.order_id = o.order_id
  WHERE
    o.sample_type = 'Gen 1'
    AND o.sample_state = 'Proto 1'
    AND hr.order_id IS NOT NULL
  GROUP BY
    o.sample_name
),
ranked AS (
  SELECT
    r.*,
    ROW_NUMBER() OVER (ORDER BY r.run_hours DESC, r.sample_name ASC) AS rn
  FROM
    runtime_per_sample r
),
sample_metadata AS (
  SELECT
    s.name AS sample_name,
    MAX(s.leepa_number) AS leepa_number,
    MAX(s.production_plant) AS production_plant,
    MAX(s.description) AS description,
    MAX(s.cellunit_name) AS cellunit_name,
    MAX(s.ccm_name) AS ccm_name,
    MAX(s.ptl_name) AS ptl_name,
    MAX(s.gdl_name) AS gdl_name,
    MAX(s.active_area_per_cell) AS active_area_per_cell
  FROM
    ps_xplatform_prod.pemely_ops.gold_sample s
  GROUP BY
    s.name
)
SELECT
  r.sample_name,
  r.sample_type,
  r.sample_state,
  r.sample_type_state,
  r.run_hours,
  r.number_of_cells,
  r.rn,
  CASE
    WHEN r.rn <= 5 THEN TRUE
    ELSE FALSE
  END AS is_top5,
  m.leepa_number,
  m.production_plant,
  m.description,
  m.cellunit_name,
  m.ccm_name,
  m.ptl_name,
  m.gdl_name,
  m.active_area_per_cell
FROM
  ranked r
    LEFT JOIN sample_metadata m
      ON r.sample_name = m.sample_name