WITH base AS (

    SELECT
        gs.time,
        gs.order_id,
        gs.jStck,
        gs.uStck,
        gs.tAndeOut,
        gs.pCtdeOut,
        gs.concO2H2,
        gs.concH2O2,
        gs.segment_length_s / 3600.0 AS segment_length_h,
        o.sample_name,
        o.sample_type,
        o.sample_state,
        o.number_of_cells    
    FROM ps_xplatform_dev.pemely_ops.gold_genericstack_static gs
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
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
        CEIL(SUM(gs.segment_length_s / 3600.0)) AS run_hours,
        o.number_of_cells
    FROM ps_xplatform_dev.pemely_ops.gold_genericstack_static gs
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
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
    FROM ps_xplatform_dev.pemely_ops.gold_sample s
    INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
        ON o.sample_id = s.sample_id
),

timeseries_with_runtime AS (
    SELECT
        r.time,
        r.sample_name,
        r.sample_type,
        r.sample_state,
        r.number_of_cells,
        r.jStck,
        r.tAndeOut,
        r.pCtdeOut,
        SUM(r.segment_length_h) OVER (
            PARTITION BY r.sample_name
            ORDER BY r.time
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS runtime_hour,
        CASE
            WHEN r.number_of_cells > 0
            THEN r.uStck / r.number_of_cells
            ELSE NULL
        END AS uCell,
        r.concO2H2,
        r.concH2O2
    FROM base r
),

final_result AS (


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
    NULL AS uCell,                   
    NULL AS concO2H2,                
    NULL AS concH2O2,                
    NULL AS jStck,                   
    NULL AS tAndeOut,                
    NULL AS pCtdeOut                 
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
    NULL AS uCell,                    
    NULL AS concO2H2,                 
    NULL AS concH2O2,                 
    NULL AS jStck,                    
    NULL AS tAndeOut,                 
    NULL AS pCtdeOut                  
FROM ps_xplatform_dev.pemely_ops.gold_sample s
INNER JOIN ps_xplatform_dev.pemely_ops.gold_genericstack_order o
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
    ts.uCell,                         
    ts.concO2H2,                      
    ts.concH2O2,                      
    ts.jStck,                         
    ts.tAndeOut,                      
    ts.pCtdeOut                       
FROM timeseries_with_runtime ts
)

SELECT *
FROM final_result
WHERE 1 = 1
{{filters}}
{{sorting}}
{{limit}}
{{offset}};


