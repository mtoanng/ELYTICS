WITH base AS (

    SELECT
        gs.time,
        gs.order_id,
        gs.j,
        gs.u,
        gs.t_an_out,
        gs.p_cat_out,
        gs.c_o2inh2,
        gs.c_h2ino2,
        gs.segment_length / 3600.0 AS segment_length_h,
        o.sample_name,
        o.sample_type,
        o.sample_state,
        o.number_of_cells    
    FROM ps_xplatform_prod.pemely_ops.gold_timeseries_wide_static gs
    INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
        ON gs.order_id = o.order_id
    WHERE
        o.sample_type = 'Gen 1'
        AND o.sample_state IN ('Proto 1', 'Proto 2')
),

runtime_per_stack AS (
    SELECT
        o.sample_name,
        o.sample_type,
        o.sample_state,
        CONCAT(o.sample_type, ' - ', o.sample_state) AS sample_type_state,
        CEIL(SUM(gs.segment_length / 3600.0)) AS run_hours,
        o.number_of_cells
    FROM ps_xplatform_prod.pemely_ops.gold_timeseries_wide_static gs
    INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
        ON gs.order_id = o.order_id
    WHERE
        o.sample_type = 'Gen 1'
        AND o.sample_state IN ('Proto 1', 'Proto 2')
    GROUP BY
        o.sample_name,
        o.sample_type,
        o.sample_state,
        o.number_of_cells
),


ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY run_hours DESC) AS rn
    FROM runtime_per_stack
),

top_5 AS (
    SELECT * FROM ranked WHERE rn <= 5
),

sample_metadata AS (
    SELECT
        s.name AS sample_name,
        s.leepa_number,
        s.production_plant,
        s.description,
        s.cellunit_name,
        s.ccm_name,
        s.ptl_name,
        s.gdl_name,
        s.active_area_per_cell,
        o.order_id
    FROM ps_xplatform_prod.pemely_ops.gold_sample s
    INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
        ON o.sample_id = s.sample_id
),

timeseries_with_runtime AS (
    SELECT
        r.time,
        r.sample_name,
        r.sample_type,
        r.sample_state,
        r.number_of_cells,
        r.j,
        r.t_an_out,
        r.p_cat_out,
        SUM(r.segment_length_h) OVER (
            PARTITION BY r.sample_name
            ORDER BY r.time
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS runtime_hour,
        CASE
            WHEN r.number_of_cells > 0
            THEN r.u / r.number_of_cells
            ELSE NULL
        END AS u_cell_avg,
        r.c_o2inh2,
        r.c_h2ino2
    FROM base r
)


-- =====================================================
-- 1. RUNTIME RANKING
-- =====================================================
SELECT
    'RUNTIME_RANKING' AS block,      
    t.sample_name,                   
    t.sample_type,                   
    t.sample_state,                  
    t.sample_type_state,            
    t.run_hours,                    

    m.leepa_number,                  
    m.production_plant,              
    m.description,                   
    m.cellunit_name,                 
    m.ccm_name,                      
    m.ptl_name,                     
    m.gdl_name,                     
    m.active_area_per_cell,         
    m.order_id,      

    t.number_of_cells,               

    NULL AS runtime_hour,          
    NULL AS u_cell_avg,                   
    NULL AS c_o2inh2,                
    NULL AS c_h2ino2,                
    NULL AS j,                   
    NULL AS t_an_out,                
    NULL AS p_cat_out                 
FROM top_5 t
LEFT JOIN sample_metadata m
    ON t.sample_name = m.sample_name

UNION ALL

-- =====================================================
-- 2. SAMPLE TABLE (ALL Gen 1 Proto 1 & 2)
-- =====================================================
SELECT
    'SAMPLE_TABLE' AS block,         
    s.name AS sample_name,            
    o.sample_type,                    
    o.sample_state,                   
    CONCAT(o.sample_type, ' - ', o.sample_state), 
    CAST(NULL AS DOUBLE) AS run_hours,

    s.leepa_number,                   
    s.production_plant,               
    s.description,                    
    s.cellunit_name,                  
    s.ccm_name,                       
    s.ptl_name,                       
    s.gdl_name,                      
    s.active_area_per_cell,           
    o.order_id,    

    o.number_of_cells,                   

    NULL AS runtime_hour,             
    NULL AS u_cell_avg,                    
    NULL AS c_o2inh2,                 
    NULL AS c_h2ino2,                 
    NULL AS j,                    
    NULL AS t_an_out,                 
    NULL AS p_cat_out                  
FROM ps_xplatform_prod.pemely_ops.gold_sample s
INNER JOIN ps_xplatform_prod.pemely_ops.gold_order o
    ON o.sample_id = s.sample_id
WHERE
    o.sample_type = 'Gen 1'
    AND o.sample_state IN ('Proto 1', 'Proto 2')

UNION ALL

-- =====================================================
-- 3. TIMESERIES
-- =====================================================
SELECT
    'TIMESERIES' AS block,            
    ts.sample_name,                    
    ts.sample_type,                    
    ts.sample_state,                   
    CONCAT(ts.sample_type, ' - ', ts.sample_state) AS sample_type_state,
    CAST(NULL AS DOUBLE) AS run_hours,

    NULL AS leepa_number,             
    NULL AS production_plant,         
    NULL AS description,              
    NULL AS cellunit_name,            
    NULL AS ccm_name,                 
    NULL AS ptl_name,                 
    NULL AS gdl_name,                 
    NULL AS active_area_per_cell,     
    NULL AS order_id,  

    ts.number_of_cells,

    ts.runtime_hour,                  
    ts.u_cell_avg,                         
    ts.c_o2inh2,                      
    ts.c_h2ino2,                      
    ts.j,                         
    ts.t_an_out,                      
    ts.p_cat_out                       
FROM timeseries_with_runtime ts;