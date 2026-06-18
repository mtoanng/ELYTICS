
-- need clarification on some stuff in here like u_cell_avg in max 

SELECT
  o.order_id,
  o.sample_name,
  samp.name,
  samp.leepa_number,
  samp.type,
  samp.state,
  samp.production_plant,
  samp.description,
  samp.cellunit_name,
  samp.ccm_name,
  samp.ptl_name,
  samp.gdl_name,
  samp.active_area_per_cell,
  o.number_of_cells,
  o.testrig_id,
  o.short_description,
  t.time_test,
  t.time_run,
  t.start_count,
  e.polcurve_count,
  s.j_max,
  s.u_cell_max,
  s.t_an_in_max,
  s.t_an_out_max,
  s.p_cat_out_max,
  s.p_an_in_max,
  s.vf_an_in_max,
  t.mf_h2_max
FROM
  (SELECT * EXCEPT (testrig_id), EXPLODE(testrig_id) AS testrig_id FROM ps_xplatform_prod.pemely_ops.gold_order) o
    LEFT JOIN ps_xplatform_prod.pemely_ops.gold_sample samp
      ON o.sample_id = samp.sample_id
    INNER JOIN (
SELECT
        order_id,
        MAX(
          CASE
            WHEN
              max.j IS NOT NULL
              AND max.j != 'NaN'
            THEN
              max.j
          END
        ) AS j_max,
        MAX(
          CASE
            WHEN
              max.u_cell_avg IS NOT NULL
              AND max.u_cell_avg != 'NaN'
            THEN
              max.u_cell_avg
          END
        ) AS u_cell_max,
        MAX(
          CASE
            WHEN
              max.t_an_in IS NOT NULL
              AND max.t_an_in != 'NaN'
            THEN
              max.t_an_in
          END
        ) AS t_an_in_max,
        MAX(
          CASE
            WHEN
              max.t_an_out IS NOT NULL
              AND max.t_an_out != 'NaN'
            THEN
              max.t_an_out
          END
        ) AS t_an_out_max,
        MAX(
          CASE
            WHEN
              max.p_cat_out IS NOT NULL
              AND max.p_cat_out != 'NaN'
            THEN
              max.p_cat_out
          END
        ) AS p_cat_out_max,
        MAX(
          CASE
            WHEN
              max.p_an_in IS NOT NULL
              AND max.p_an_in != 'NaN'
            THEN
              max.p_an_in
          END
        ) AS p_an_in_max,
        MAX(
          CASE
            WHEN
              max.vf_an_in IS NOT NULL
              AND max.vf_an_in != 'NaN'
            THEN
              max.vf_an_in
          END
        ) AS vf_an_in_max
      FROM
        ps_xplatform_prod.pemely_ops.gold_timeseries_wide_static
      GROUP BY
        order_id
    ) s
      ON o.order_id = s.order_id
    LEFT JOIN (
      SELECT
        order_id,
        CEIL(MAX(calc.time_test)) AS time_test,
        CEIL(MAX(calc.time_run)) AS time_run,
        sum(calc.count_start) as start_count,
        max(max.mf_h2) as mf_h2_max
      FROM
        ps_xplatform_prod.pemely_ops.gold_timeseries_1h
      GROUP BY
        order_id
    ) t
      ON o.order_id = t.order_id
    LEFT JOIN (
      SELECT
        order_id,
        count(event_id) as polcurve_count
      FROM
        ps_xplatform_prod.pemely_ops.gold_event
      WHERE
        event_type = 'ivcurve'
      GROUP BY
        order_id
    ) e
      ON o.order_id = e.order_id